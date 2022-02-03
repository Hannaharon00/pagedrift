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

