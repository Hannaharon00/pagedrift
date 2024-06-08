$(function () {
    function normalizeUrl(el) {
        const val = el.value.trim();
        if (val && !/^[a-zA-Z][a-zA-Z\d+\-.]*:/.test(val)) {
            el.value = 'https://' + val;
        }
    }

    $('#url').on('blur keydown', function (e) {
        if (e.type === 'blur' || e.key === 'Enter') {
            normalizeUrl(this);
        }
    });

    $('form').on('submit', function () {
        normalizeUrl($('#url')[0]);
    });

    // Remove unviewed status when normally clicked
    $('.diff-link').click(function () {
        $(this).closest('.unviewed').removeClass('unviewed');
    });

    $('td[data-timestamp]').each(function () {
        $(this).prop('title', new Intl.DateTimeFormat(undefined,
            {
                dateStyle: 'full',
                timeStyle: 'long'
            }).format($(this).data('timestamp') * 1000));
    })

    $("#checkbox-assign-tag").click(function (e) {
        $('#op_extradata').val(prompt("Enter a tag name"));
    });

    // Bulk "Browser" / "Proxy" actions: open a modal with the same radio choices as the
    // edit page, then set #op_extradata and fire the (hidden) real operation button so the
    // existing socket.io / form submit path applies the choice to the selected watches.
    // Title / button text come from the button's data-* attributes so they pass through
    // server-side i18n (the static JS can't call gettext itself).
    function showBulkChoiceModal($btn, templateId, radioName, hiddenBtnId) {
        const tmpl = document.getElementById(templateId);
        if (!tmpl || typeof ModalDialog === 'undefined') {
            return;
        }
        ModalDialog.confirm({
            type: 'info',
            title: $btn.data('modal-title'),
            message: '<div class="bulk-choice-list">' + tmpl.innerHTML + '</div>',
            confirmText: $btn.data('modal-apply'),
            onConfirm: function () {
                const checked = document.querySelector('.modal-dialog input[name="' + radioName + '"]:checked');
                $('#op_extradata').val(checked ? checked.value : '');
                $('#' + hiddenBtnId).trigger('click');
                // Feedback is server-driven: the backend emits a 'toast' event with the real
                // count/result, handled in realtime.js (and the form fallback flashes on redirect).
            }
        });
    }

    $("#checkbox-set-browser").click(function (e) {
        showBulkChoiceModal($(this), 'bulk-browser-options', 'bulk-fetch-backend', 'op-set-fetch-backend');
    });

    $("#checkbox-set-proxy").click(function (e) {
        showBulkChoiceModal($(this), 'bulk-proxy-options', 'bulk-proxy', 'op-set-proxy');
    });


    $('.history-link').click(function (e) {
        // Incase they click 'back' in the browser, it should be removed.
        $(this).closest('tr').removeClass('unviewed');
    });

    // Inline restock price/stock graph: for restock_diff rows the History button rolls down a
    // price/stock graph (no LLM needed), styled like the AI summary roll-down. Registered before
    // the LLM handler and stops propagation so AI mode never turns these into LLM summaries.
    $(document).on('click', 'tr.processor-restock_diff .ai-history-btn', function (e) {
        e.preventDefault();
        e.stopImmediatePropagation();

        if (!dataUrl) { showError(); return; }

        $.getJSON(dataUrl).done(function (data) {
            var series = (data && data.series) || [];
            var graphI18n = {
                in_stock: i18n.inStock, out_of_stock: i18n.outOfStock,
                no_data: i18n.noPriceData, load_error: i18n.priceHistoryError,
                changes: i18n.changes, avg_price: i18n.avgPrice,
                price_low: i18n.priceLow, price_typical: i18n.priceTypical, price_high: i18n.priceHigh,
                cheaper_than: i18n.cheaperThan, pricier_than: i18n.pricierThan,
                typical_note: i18n.typicalNote, avg_label: i18n.avgLabel
            };
            if (window.renderRestockGraph) {
                // Shorter graph inline in the watchlist roll-down than on the full /diff page.
                window.renderRestockGraph($r.find('.restock-inline-graph')[0], series, (data && data.currency) || '', graphI18n, (data && data.summary) || null, 230);
            }
        }).fail(showError);
    });

    $('.with-share-link > *').click(function () {
        $("#copied-clipboard").remove();

        var range = document.createRange();
        var n = $("#share-link")[0];
        range.selectNode(n);
        window.getSelection().removeAllRanges();
        window.getSelection().addRange(range);
        document.execCommand("copy");
        window.getSelection().removeAllRanges();

        $('.with-share-link').append('<span style="font-size: 80%; color: #fff;" id="copied-clipboard">Copied to clipboard</span>');
        $("#copied-clipboard").fadeOut(2500, function () {
            $(this).remove();
        });
    });

    $(".watch-table tr").click(function (event) {
        var tagName = event.target.tagName.toLowerCase();
        if (tagName === 'tr' || tagName === 'td') {
            var cb = $('input[type=checkbox]', this)[0];
            if (cb) {
                // Forward the shiftKey so shift-clicking anywhere on a row does a
                // range-select (a plain $(cb).click() would drop the modifier).
                cb.dispatchEvent(new MouseEvent('click', { bubbles: true, shiftKey: event.shiftKey }));
            }
        }
    });

    // ---- Cross-page selection store -------------------------------------------
    // Selection is a Set of watch UUIDs (the source of truth) rather than the DOM,
    // so it spans paginated pages. Persisted in sessionStorage scoped to the
    // watch-list page + the active tag (only): a selection survives switching the
    // status/processor/search/pagination views, but each tag group (and the
    // untagged "all" view) gets its own selection bucket. The "/uuids" endpoint
    // supplies the full matching id list for "select all matching".
    const sel = window.cdioWatchSelection = (function () {
        const KEY = 'cdio-watch-selection';
        function scopeKey() {
            const tag = new URLSearchParams(location.search).get('tag') || '';
            return location.pathname + (tag ? '?tag=' + tag : '');
        }
        let uuids = new Set();
        try {
            const obj = JSON.parse(sessionStorage.getItem(KEY) || 'null');
            if (obj && obj.scope === scopeKey() && Array.isArray(obj.uuids)) {
                uuids = new Set(obj.uuids);
            }
        } catch (e) { /* private mode / corrupt — best effort */ }
        function persist() {
            try {
                sessionStorage.setItem(KEY, JSON.stringify({ scope: scopeKey(), uuids: Array.from(uuids) }));
            } catch (e) { /* quota / private mode */ }
        }
        return {
            has: (u) => uuids.has(u),
            add: (u) => { uuids.add(u); persist(); },
            remove: (u) => { uuids.delete(u); persist(); },
            toggle: (u) => { if (uuids.has(u)) { uuids.delete(u); } else { uuids.add(u); } persist(); },
            addMany: (arr) => { arr.forEach((u) => uuids.add(u)); persist(); },
            clear: () => { uuids.clear(); persist(); },
            all: () => Array.from(uuids),
            size: () => uuids.size
        };
    })();

    // Individual row checkbox toggled (direct click, or via the row-click handler).
    $(document).on('change', 'input[name="uuids"][type=checkbox]', function () {
        if (this.checked) { sel.add(cbUuid(this)); } else { sel.remove(cbUuid(this)); }
        const visible = $rowCbs().get();
        $('#check-all').prop('checked', visible.length > 0 && visible.every((el) => el.checked));
        refreshSelectionUI();
    });

    // Check-all (this page only).
    $("#check-all").click(function () {
        const on = this.checked;
        $rowCbs().each(function () {
            this.checked = on;
            if (on) { sel.add(cbUuid(this)); } else { sel.remove(cbUuid(this)); }
        });
        refreshSelectionUI();
    });

    // Invert this page's selection.
    $("#check-invert").click(function () {
        $rowCbs().each(function () { sel.toggle(cbUuid(this)); });
        applySelectionToDom();
        refreshSelectionUI();
    });

    // Cancel: clear the whole cross-page selection (incl. the stored browser data)
    // and dismiss the operations bar.
    $("#check-cancel").click(function () {
        sel.clear();
        applySelectionToDom();
        refreshSelectionUI();
    });

    // "Select all N matching" — pull the full matching id list from the server.
    $(document).on('click', '#select-all-matching', function () {
        if (!selCfg.uuidsUrl) return;
        const $btn = $(this).prop('disabled', true);
        $.getJSON(selCfg.uuidsUrl + location.search)
            .done(function (data) {
                if (data && Array.isArray(data.uuids)) {
                    sel.addMany(data.uuids.map((u) => ('' + u).trim()));
                    applySelectionToDom();
                    refreshSelectionUI();
                }
            })
            .always(function () { $btn.prop('disabled', false); });
    });

    // "Clear selection" link inside the banner.
    $(document).on('click', '#select-all-clear', function () {
        sel.clear();
        applySelectionToDom();
        refreshSelectionUI();
    });

    const time_check_step_size_seconds=1;

