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

