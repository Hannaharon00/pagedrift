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

