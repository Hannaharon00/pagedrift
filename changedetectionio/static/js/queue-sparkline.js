/*
 * Queue activity sparkline — a compact "is it alive?" activity strip for the sidebar.
 *
 * UX goal: answer the user's gut question "is this thing actually doing anything?".
 *   - A pinned, gently PULSING leading dot at the right edge beats like a heartbeat
 *     even when totally idle, so the UI always reads as alive/monitoring — a frozen
 *     dot would read as broken.
 *   - Real in-flight work bumps the line, which then scrolls left across the window,
 *     so you can see it really does check things over the last few minutes.
 *
 * Signal plotted = queue_size + checking_now  (total in-flight work). Either being
 * non-zero lifts the trace; plain queue size alone sits at 0 while workers drain it.
 *
 * Rendering: a scrolling strip chart. The right edge is "now", the left edge is
 * "now - WINDOW_SECONDS". New samples always enter from the right; old data scrolls
 * off the left and fades out as it goes (left-edge brightness ramp).
 *
 * Hardening (lessons from common sparkline libs, e.g. fnando/sparkline #14/#24):
 *   - Autoscaled 0..max with headroom + a MIN floor, so it always stays inside the
 *     canvas height and never divides by zero on a flat/all-zero queue.
 *   - devicePixelRatio aware (crisp on retina), re-measured on resize (the rail
 *     expands 64px->190px on hover).
 *   - Pauses the rAF loop when the tab is hidden.
 *
 * History survives a full page reload via localStorage: we persist the queue/checking
 * EVENT LOG (a small step-function, not pixels). On load we sample that log across the
 * visible window, so the strip immediately shows the last few minutes instead of a
 * blank screen.
 *
 * Fed by the same Socket.IO 'queue_size' / 'checking_now' events as realtime.js.
 */
(function () {
    "use strict";

    const STORE_KEY = "cdio-queue-spark-v1";
    const WINDOW_SECONDS = 180;      // how much recent history the strip shows (a few minutes)
    const RETAIN_MS = WINDOW_SECONDS * 1000 * 1.5; // keep a little more than one screenful
    const MAX_EVENTS = 600;          // hard cap on stored events (localStorage size guard)
    const MIN_SCALE = 1;             // autoscale floor: avoids /0 and stops a 0/1 queue filling the panel
    const PULSE_MS = 1500;           // leading-dot heartbeat period — liveness even when idle
    const RISE_LERP = 0.30;          // autoscale rises quickly so a new bump shows promptly
    const FALL_LERP = 0.04;          // ...and falls slowly so it doesn't jitter
    const reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const FRAME_MS = reduceMotion ? 250 : 100; // 10fps (plenty here); slower under reduced-motion

    // --- Shared state across all canvases (desktop rail + mobile drawer share one history) ---
    let eventLog = [];          // [{t: epoch_ms, v: number}] step-function of total activity
    let currentQueue = 0;
    let currentChecking = 0;

    function totalNow() { return currentQueue + currentChecking; }

