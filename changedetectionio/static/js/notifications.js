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

// Turn a single Apprise URL into a friendly {icon, label} for the recipient chips.
function describeNotificationUrl(url) {
    var u = (url || '').trim();
    if (!u) return null;

    var isEmailPreset = false;
    if (typeof email_notification_prefix !== 'undefined' && email_notification_prefix) {
        var base = email_notification_prefix.indexOf('{TO}') !== -1
            ? email_notification_prefix.split('{TO}')[0]
            : email_notification_prefix;
        isEmailPreset = base && u.indexOf(base) === 0;
    }

    if (/^mailtos?:\/\//i.test(u) || isEmailPreset) {
        var addr = null;
        var toMatch = u.match(/[?&]to=([^&]+)/i);
        if (toMatch) {
            addr = decodeURIComponent(toMatch[1]);
        } else if (isEmailPreset) {
            var base2 = email_notification_prefix.indexOf('{TO}') !== -1
                ? email_notification_prefix.split('{TO}')[0]
                : email_notification_prefix;
            addr = u.substring(base2.length);
        } else {
            var m = u.match(/^mailtos?:\/\/([^?@\/]+@[^?\/]+)/i);
            if (m) addr = m[1];
        }
        return {type: 'email', icon: '✉', label: addr || u};
    }

    var scheme = (u.split('://')[0] || '').toLowerCase();
    var names = {
        discord: 'Discord', tgram: 'Telegram', telegram: 'Telegram', slack: 'Slack',
        tgrams: 'Telegram', gets: 'Webhook', posts: 'Webhook', get: 'Webhook', post: 'Webhook'
    };
    return {type: scheme || 'other', icon: '🔔', label: names[scheme] || (scheme || u)};
}

function notificationLines() {
    return ($('textarea.notification-urls').val() || '')
        .split('\n').map(function (s) { return s.trim(); }).filter(function (s) { return s.length; });
}

// Re-render the recipient chips from the textarea (the textarea stays the source of truth).
function renderNotificationRecipients() {
    var $container = $('#notification-recipients');
    if (!$container.length) return;
    var lines = notificationLines();
    $container.empty();
    if (!lines.length) { $container.hide(); return; }
    $container.show();

    lines.forEach(function (line) {
        var d = describeNotificationUrl(line);
        if (!d) return;
        var $chip = $('<span class="notification-chip"></span>').attr('data-url', line);
        $chip.append($('<span class="notification-chip-icon"></span>').text(d.icon));
        $chip.append($('<span class="notification-chip-label"></span>').text(d.label).attr('title', line));
        var $x = $('<a class="notification-chip-remove" title="Remove">✕</a>');
        $x.on('click', function (e) {
            e.preventDefault();
            removeNotificationLine(line);
        });
        $chip.append($x);
        $container.append($chip);
    });
}

function appendNotificationUrl(url) {
    var $ta = $('textarea.notification-urls');
    var cur = $.trim($ta.val() || '');
    $ta.val(cur ? cur + '\n' + url : url);
    $ta.trigger('input');
}

