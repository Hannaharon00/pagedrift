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

