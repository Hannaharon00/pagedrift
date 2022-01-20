function checkDiscordHtmlWarning() {
    var urls = $('textarea.notification-urls').val() || '';
    var format = $('select.notification-format').val() || '';
    var isDiscord = /discord:\/\/|https:\/\/discord(?:app)?\.com\/api/i.test(urls);
    var isHtml = format === 'html' || format === 'htmlcolor';
    if (isDiscord && isHtml) {
        $('#discord-html-format-warning').show();
    } else {
        $('#discord-html-format-warning').hide();
    }
}

// Build a mailto-style Apprise URL from an email address using the configured preset.
// Supports a {TO} token anywhere in the preset; falls back to prefix+address.
function buildEmailUrl(email) {
    var p = (typeof email_notification_prefix !== 'undefined' && email_notification_prefix) ? email_notification_prefix : 'mailto://';
    if (p.indexOf('{TO}') !== -1) {
        return p.replace('{TO}', email);
    }
    return p + email;
}

