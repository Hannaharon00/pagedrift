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

    function buildTable($table, series, currency, i18n) {
        const $tbody = $table.find('tbody');
        if (!$tbody.length) return;
        $tbody.empty();
        series.slice().reverse().forEach(p => {
            let stock = '-';
            if (p.in_stock === true) stock = $('<span class="restock-badge in-stock"></span>').text(i18n.in_stock);
            else if (p.in_stock === false) stock = $('<span class="restock-badge out-of-stock"></span>').text(i18n.out_of_stock);
            const price = (p.price !== null && p.price !== undefined) ? fmtPrice(p.price, currency) : '-';
            $('<tr></tr>')
                .append($('<td></td>').text(fmtDateTime(p.timestamp)))
                .append($('<td></td>').append(stock))
                .append($('<td></td>').text(price))
                .appendTo($tbody);
        });
    }

    // Redraw a graph only if its container width actually changed (skips redundant redraws and
    // prevents ResizeObserver feedback loops).
    function redraw($c) {
        const ctx = $c.data('rg');
        if (!ctx) return;
        const w = Math.round($c.width());
        if (w === ctx.lastWidth) return;
        ctx.lastWidth = w;
        draw($c, ctx.series, ctx.currency, ctx.i18n, ctx.summary, ctx.height);
    }

    // Watch the container's own size, not just the window: the content area also changes width
    // when the action sidebar expands on hover (no window 'resize' event fires for that).
    const hasRO = typeof ResizeObserver !== 'undefined';
    let ro = null;
    if (hasRO) {
        let roTimer;
        const pending = new Set();
        ro = new ResizeObserver(function (entries) {
            entries.forEach(e => pending.add(e.target));
            clearTimeout(roTimer);
            roTimer = setTimeout(function () {
                pending.forEach(t => redraw($(t)));
                pending.clear();
            }, 120);
        });
    } else {
        // Fallback for browsers without ResizeObserver: window resize only.
        let resizeTimer;
        $(window).on('resize.restockgraph', function () {
            clearTimeout(resizeTimer);
            resizeTimer = setTimeout(function () {
                $('.js-restock-graph').each(function () { redraw($(this)); });
            }, 150);
        });
    }

    // Public reusable renderer. Stores its context on the element and observes the element so
    // it redraws on any size change; usable from anywhere (e.g. the watchlist inline roll-down).
    window.renderRestockGraph = function (container, series, currency, i18n, summary, height) {
        const $c = $(container);
        if (!$c.length) return;
        const merged = $.extend({}, DEFAULT_I18N, i18n || {});
        // Seed lastWidth to the current width so the immediate ResizeObserver callback (which
        // fires once on observe()) doesn't trigger a redundant redraw.
        $c.addClass('js-restock-graph').data('rg', {
            series: series || [], currency: currency || '', i18n: merged, summary: summary || null,
            height: height || HEIGHT, lastWidth: Math.round($c.width())
        });
        draw($c, series || [], currency || '', merged, summary || null, height || HEIGHT);
        if (ro) {
            try { ro.unobserve($c[0]); } catch (e) {}
            ro.observe($c[0]);
        }
    };

    // Diff page bootstrap: fetch the timeline, render the graph + the data table.
    $(function () {
        const $container = $('#restock-graph');
        if (!$container.length || !window.restock_data_url) return;
        const i18n = $.extend({}, DEFAULT_I18N, window.restock_i18n || {});
        $.getJSON(window.restock_data_url).done(function (data) {
            const series = (data && data.series) || [];
            window.renderRestockGraph($container, series, (data && data.currency) || '', i18n, (data && data.summary) || null);
            buildTable($('#restock-history-table'), series, (data && data.currency) || '', i18n);
        }).fail(function () {
            $container.html($('<p class="pure-form-message-inline"></p>').text(i18n.load_error));
        });
    });

