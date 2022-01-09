$(document).ready(function () {

    // Find all <span> elements inside pre#difference
    var inputs = $('#difference span').toArray();
    inputs.current = 0;

    // Setup visual minimap of difference locations (cells are pre-built in Python)
    var $visualizer = $('#cell-diff-jump-visualiser');
    var $difference = $('#difference');
    var $cells = $visualizer.find('> div');
    var visualizerResolutionCells = $cells.length;
    var cellHeight;

    if ($difference.length && visualizerResolutionCells > 0) {
        var docHeight = $difference[0].scrollHeight;
        cellHeight = docHeight / visualizerResolutionCells;

        // Add click handlers to pre-built cells
        $cells.each(function(i) {
            $(this).data('cellIndex', i);
            $(this).on('click', function() {
                var cellIndex = $(this).data('cellIndex');
                var targetPositionInDifference = cellIndex * cellHeight;
                var viewportHeight = $(window).height();

                // Scroll so target is at viewport center (where eyes expect it)
                window.scrollTo({
                    top: $difference.offset().top + targetPositionInDifference - (viewportHeight / 2),
                    behavior: "smooth"
                });
            });
        });
    }

    $('#jump-next-diff').click(function () {
        if (!inputs || inputs.length === 0) return;

        // Find the next change after current scroll position
        var currentScrollPos = $(window).scrollTop();
        var viewportHeight = $(window).height();
        var currentCenter = currentScrollPos + (viewportHeight / 2);

        // Add small buffer (50px) to jump past changes already near center
        var searchFromPosition = currentCenter + 50;

        var nextElement = null;
        for (var i = 0; i < inputs.length; i++) {
            var elementTop = $(inputs[i]).offset().top;
            if (elementTop > searchFromPosition) {
                nextElement = inputs[i];
                break;
            }
        }

        // If no element found ahead, wrap to first element
        if (!nextElement) {
            nextElement = inputs[0];
        }

        // Scroll to position the element at viewport center
        var elementTop = $(nextElement).offset().top;
        var targetScrollPos = elementTop - (viewportHeight / 2);

        window.scrollTo({
            top: targetScrollPos,
            behavior: "smooth",
        });
    });

