function setupDiffNavigation() {
    var $fromSelect = $('#diff-from-version');
    var $toSelect = $('#diff-to-version');
    var $fromSelected = $fromSelect.find('option:selected');
    var $toSelected = $toSelect.find('option:selected');

    if ($fromSelected.length && $toSelected.length) {
        // Find the previous pair (move both back one position)
        var $prevFrom = $fromSelected.prev();
        var $prevTo = $toSelected.prev();

        // Find the next pair (move both forward one position)
        var $nextFrom = $fromSelected.next();
        var $nextTo = $toSelected.next();

        // Build URL with current diff preferences
        var currentParams = new URLSearchParams(window.location.search);

        // Previous button: only show if both can move back
        if ($prevFrom.length && $prevTo.length) {
            currentParams.set('from_version', $prevFrom.val());
            currentParams.set('to_version', $prevTo.val());
            $('#btn-previous').attr('href', '?' + currentParams.toString());
        } else {
            $('#btn-previous').remove();
        }

        // Next button: only show if both can move forward
        if ($nextFrom.length && $nextTo.length) {
            currentParams.set('from_version', $nextFrom.val());
            currentParams.set('to_version', $nextTo.val());
            $('#btn-next').attr('href', '?' + currentParams.toString());
        } else {
            $('#btn-next').remove();
        }
    }

    // Keyboard navigation
    window.addEventListener('keydown', function (event) {
        // Don't trigger if user is typing in an input field
        if (event.target.tagName === 'INPUT' || event.target.tagName === 'TEXTAREA' || event.target.tagName === 'SELECT') {
            return;
        }

        var $fromSelected = $fromSelect.find('option:selected');
        var $toSelected = $toSelect.find('option:selected');

        if ($fromSelected.length && $toSelected.length) {
            if (event.key === 'ArrowLeft') {
                var $prevFrom = $fromSelected.prev();
                var $prevTo = $toSelected.prev();
                if ($prevFrom.length && $prevTo.length) {
                    var prevHref = $('#btn-previous').attr('href');
                    if (prevHref) {
                        event.preventDefault();
                        window.location.href = prevHref;
                    }
                }
            } else if (event.key === 'ArrowRight') {
                var $nextFrom = $fromSelected.next();
                var $nextTo = $toSelected.next();
                if ($nextFrom.length && $nextTo.length) {
                    var nextHref = $('#btn-next').attr('href');
                    if (nextHref) {
                        event.preventDefault();
                        window.location.href = nextHref;
                    }
                }
            }
        }
    }, false);
}

$(document).ready(function () {
    $('.needs-localtime').each(function () {
        for (var option of this.options) {
            var dateObject = new Date(option.value * 1000);
            var formattedDate = dateObject.toLocaleString(undefined, {dateStyle: "full", timeStyle: "medium"});
            // Preserve any existing text in the label (like "(Previous)" or "(Current)")
            var existingText = option.text.replace(option.value, '').trim();
            option.label = existingText ? formattedDate + ' ' + existingText : formattedDate;
        }
    });

    // Setup keyboard navigation for diff versions
    if ($('#diff-from-version').length && $('#diff-to-version').length) {
        setupDiffNavigation();
    }

    // Load it when the #screenshot tab is in use, so we dont give a slow experience when waiting for the text diff to load
    window.addEventListener('hashchange', function (e) {
        toggle(location.hash);
    }, false);

    toggle(location.hash);

    function toggle(hash_name) {
        if (hash_name === '#screenshot') {
            $("img#screenshot-img").attr('src', screenshot_url);
            $("#settings").hide();
        } else if (hash_name === '#error-screenshot') {
            $("img#error-screenshot-img").attr('src', error_screenshot_url);
            $("#settings").hide();
        } else if (hash_name === '#extract') {
            $("#settings").hide();
        } else {
            $("#settings").show();
        }
    }

    const article = $('#difference')[0];

    // We could also add the  'touchend' event for touch devices, but since
    // most iOS/Android browsers already show a dialog when you select
    // text (often with a Share option) we'll skip that
    if (article) {
        article.addEventListener('mousedown', clean, false);
    }

    // Because they might 'mouse up' outside the article but on the page
    const d_page = $(".difference-page")[0]
    if (d_page ) {
        d_page.addEventListener('mouseup', dragTextHandler, false);
    }


    $('#highlightSnippetActions a').bind('click', function (e) {
        if (!window.getSelection().toString().trim().length) {
            alert('Oops no text selected!');
            return;
        }

        $.ajax({
            type: "POST",
            url: highlight_submit_ignore_url,
            data: {'mode': $(this).data('mode'), 'selection': window.getSelection().toString()},
            statusCode: {
                400: function () {
                    // More than likely the CSRF token was lost when the server restarted
                    alert("There was a problem processing the request, please reload the page.");
                }
            }
        }).done(function (data) {
            // @todo some feedback
            alert("'Ignore' Filters for this watch were updated.")
            clean();

