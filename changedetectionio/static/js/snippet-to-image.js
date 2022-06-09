/**
 * snippet-to-image.js
 * Converts selected diff content to a shareable JPEG image with metadata
 */

// Constants
const IMAGE_PADDING = 5;
const JPEG_QUALITY = 0.95;
const CANVAS_SCALE = 1;
const RENDER_DELAY_MS = 50;

/**
 * Utility: Get the target URL from global watch_url or fallback to current URL
 */
function getTargetUrl() {
    return (typeof watch_url !== 'undefined' && watch_url) ? watch_url : window.location.href;
}

/**
 * Utility: Get formatted current date with timezone
 */
function getFormattedDate() {
    return new Date().toLocaleString(undefined, {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        timeZoneName: 'short'
    });
}

