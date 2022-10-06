// Restock price/stock timeline - a hand-rolled smoothed SVG line graph.
// Line segments are green where the item was in stock and red where it was out of stock.
//
// Two consumers:
//   * the restock diff page (#restock-graph), which fetches window.restock_data_url and also
//     builds the data table below it; and
//   * the watchlist inline roll-down, which calls window.renderRestockGraph(el, series, currency, i18n).
//
// Series shape (oldest -> newest): [{timestamp: <epoch sec>, price: <float|null>, in_stock: <bool|null>}]

(function ($) {
    'use strict';

    const SVG_NS = 'http://www.w3.org/2000/svg';
    const COLOR_IN = '#1fa463';   // in stock = green
    const COLOR_OUT = '#e74c3c';  // out of stock = red
    const COLOR_UNKNOWN = '#999'; // stock state not known
    const HEIGHT = 320;          // default (diff page); the inline watchlist graph passes a shorter one
    const PAD = { top: 20, right: 16, bottom: 30, left: 52 };
    const MAX_X_LABELS = 6;       // keep the date axis uncluttered

    const DEFAULT_I18N = { in_stock: 'In stock', out_of_stock: 'Out of stock',
        no_data: 'No price data available to graph yet.', load_error: 'Could not load price history.',
        changes: 'Changes', avg_price: 'Average price',
        price_low: 'Currently low', price_typical: 'Currently typical', price_high: 'Currently high',
        // {pct} is substituted with an already-formatted percentage, e.g. "80%". The percent sign is
        // NOT part of the msgid on purpose: a bare "%" followed by a letter (" of") parses as a
        // python-format conversion ("% o"), which makes pybabel reject any translation of it.
        cheaper_than: 'cheaper than {pct} of tracked prices',
        pricier_than: 'more expensive than {pct} of tracked prices',
        typical_note: 'around the usual price', avg_label: 'avg' };
    const OVERLAY_MIN_POINTS = 5; // need enough history for low/typical/high to be meaningful

    function el(name, attrs) {
        const e = document.createElementNS(SVG_NS, name);
        for (const k in attrs) e.setAttribute(k, attrs[k]);
        return e;
    }

    function stockColor(inStock) {
        if (inStock === true) return COLOR_IN;
        if (inStock === false) return COLOR_OUT;
        return COLOR_UNKNOWN;
    }

    // X-axis label: day + short month + short year, e.g. "21 Jun '25".
    function fmtAxisDate(epoch) {
        const d = new Date(epoch * 1000);
        const dm = d.toLocaleDateString(undefined, { day: 'numeric', month: 'short' });
        return `${dm} '${String(d.getFullYear()).slice(-2)}`;
    }

    function fmtDateTime(epoch) {
        // undefined locale => the browser's locale; explicit options for a clean, complete format.
        return new Date(epoch * 1000).toLocaleString(undefined, {
            year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
        });
    }

    function fmtPrice(v, currency) {
        const n = Math.round(v * 100) / 100;
        return (currency || '') + (Number.isInteger(n) ? n : n.toFixed(2));
    }

    // Thin a large price series down to ~target points for drawing (you can't perceive more
    // points than pixels). Always keeps the first, last and the true min/max points so the line
    // still touches its extremes. The axis range + summary stay computed over the FULL data.
    function downsample(arr, target) {
        if (arr.length <= target) return arr;
        const keep = new Set([0, arr.length - 1]);
        let minI = 0, maxI = 0;
        for (let i = 1; i < arr.length; i++) {
            if (arr[i].price < arr[minI].price) minI = i;
            if (arr[i].price > arr[maxI].price) maxI = i;
        }
        keep.add(minI); keep.add(maxI);
        const step = arr.length / target;
        for (let i = 0; i < target; i++) keep.add(Math.floor(i * step));
        return Array.from(keep).sort((a, b) => a - b).map(i => arr[i]);
    }

    // Monotone cubic spline (Fritsch–Carlson). A gentle, smooth curve that — unlike Catmull-Rom —
    // is guaranteed NOT to overshoot beyond the actual data points: tangents are clamped so the
    // line never dips below / rises above neighbouring values. So the curve stays faithful to the
    // real prices (no phantom dips/spikes) while still looking soft. Returns an SVG path string.
    function monotonePath(pts) {
        const n = pts.length;
        if (n < 2) return '';
        const xs = pts.map(p => p.x), ys = pts.map(p => p.y);
        if (n === 2) return `M ${xs[0].toFixed(1)} ${ys[0].toFixed(1)} L ${xs[1].toFixed(1)} ${ys[1].toFixed(1)}`;

        const dx = [], slope = [];
        for (let i = 0; i < n - 1; i++) {
            const h = xs[i + 1] - xs[i];
            dx.push(h);
            slope.push(h === 0 ? 0 : (ys[i + 1] - ys[i]) / h);
        }

        const m = new Array(n);
        m[0] = slope[0];
        m[n - 1] = slope[n - 2];
        for (let i = 1; i < n - 1; i++) {
            // Local extremum (slope changes sign) → flat tangent so the curve doesn't overshoot.
            m[i] = (slope[i - 1] * slope[i] <= 0) ? 0 : (slope[i - 1] + slope[i]) / 2;
        }
        // Fritsch–Carlson: clamp tangents so each segment stays monotone (no overshoot).
        for (let i = 0; i < n - 1; i++) {
            if (slope[i] === 0) { m[i] = 0; m[i + 1] = 0; continue; }
            const a = m[i] / slope[i], b = m[i + 1] / slope[i], s = a * a + b * b;
            if (s > 9) {
                const t = 3 / Math.sqrt(s);
                m[i] = t * a * slope[i];
                m[i + 1] = t * b * slope[i];
            }
        }

        let d = `M ${xs[0].toFixed(1)} ${ys[0].toFixed(1)}`;
        for (let i = 0; i < n - 1; i++) {
            const h = dx[i];
            const c1x = xs[i] + h / 3, c1y = ys[i] + m[i] * h / 3;
            const c2x = xs[i + 1] - h / 3, c2y = ys[i + 1] - m[i + 1] * h / 3;
            d += ` C ${c1x.toFixed(1)} ${c1y.toFixed(1)} ${c2x.toFixed(1)} ${c2y.toFixed(1)} ${xs[i + 1].toFixed(1)} ${ys[i + 1].toFixed(1)}`;
        }
        return d;
    }

    function draw($container, series, currency, i18n, summary, height) {
        height = height || HEIGHT;
        // Only points that actually have a price can sit on the line.
        const data = (series || []).filter(p => p.price !== null && p.price !== undefined);
        if (data.length < 2) {
            $container.html($('<p class="pure-form-message-inline"></p>').text(i18n.no_data));
            return;
        }

