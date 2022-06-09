// Copyright (C) 2021 Leigh Morresi (dgtlmoon@gmail.com)
// All rights reserved.
// yes - this is really a hack, if you are a front-ender and want to help, please get in touch!
//
// Refactored into a reusable factory: window.initVisualSelector(opts)
//   - edit.html drives it from stored screenshot + xpath-data URLs (auto-init at bottom of file)
//   - the Add Watch UI drives it from inline snapshot data fetched on demand
// Both share the same hover/highlight/select core.

        if (scaleByBrowserWidth && selectorData && selectorData['browser_width']) {
            // xpath box coords are CSS pixels (getBoundingClientRect) and the scraper reports
            // browser_width = window.innerWidth (also CSS px). The screenshot is displayed with a
            // preserved aspect ratio, so a single uniform factor (displayed width / page CSS width)
            // maps both axes in sync, regardless of the capture's device-pixel-ratio.
            xScale = yScale = selectorImageRect.width / selectorData['browser_width'];
        } else {
            xScale = selectorImageRect.width / selectorImage.naturalWidth;
            yScale = selectorImageRect.height / selectorImage.naturalHeight;
        }

        ctx.strokeStyle = STROKE_STYLE_HIGHLIGHT;
        ctx.fillStyle = FILL_STYLE_REDLINE;
        ctx.lineWidth = 3;
        console.log("Scaling set  x: " + xScale + " by y:" + yScale);
        $("#selector-current-xpath").css('max-width', selectorImageRect.width);
    }

    function bindElementHandlers() {
        // Store handler references for later use
        elementHandlers.handleMouseMove = handleMouseMove.debounce(5);
        elementHandlers.handleMouseDown = handleMouseDown.debounce(5);
        elementHandlers.handleMouseLeave = highlightCurrentSelected.debounce(5);

        $selectorCanvasElem.bind('mousemove', elementHandlers.handleMouseMove);
        $selectorCanvasElem.bind('mousedown', elementHandlers.handleMouseDown);
        $selectorCanvasElem.bind('mouseleave', elementHandlers.handleMouseLeave);
    }

    function handleMouseMove(e) {
        if (!e.offsetX && !e.offsetY) {
            const targetOffset = $(e.target).offset();
            e.offsetX = e.pageX - targetOffset.left;
            e.offsetY = e.pageY - targetOffset.top;
        }

        ctx.fillStyle = FILL_STYLE_HIGHLIGHT;

        selectorData['size_pos'].forEach(sel => {
            if (e.offsetY > sel.top * yScale && e.offsetY < sel.top * yScale + sel.height * yScale &&
                e.offsetX > sel.left * yScale && e.offsetX < sel.left * yScale + sel.width * yScale) {
                setCurrentSelectedText(sel.xpath);
                drawHighlight(sel);
                currentSelections.push(sel);
                currentSelection = sel;
                highlightCurrentSelected();
                currentSelections.pop();
            }
        })
    }

    function setCurrentSelectedText(s) {
        // Selectors come from the scraped page, display them as text and never as markup
        $selectorCurrentXpathElem[0].textContent = s;
    }

    function drawHighlight(sel) {
        ctx.strokeRect(sel.left * xScale, sel.top * yScale, sel.width * xScale, sel.height * yScale);
        ctx.fillRect(sel.left * xScale, sel.top * yScale, sel.width * xScale, sel.height * yScale);
    }

    function handleMouseDown() {
        // If we are in 'appendToList' mode, grow the list, if not, just 1
        currentSelections = appendToList ? [...currentSelections, currentSelection] : [currentSelection];
        highlightCurrentSelected();
        updateFiltersText();
    }

    function reflowSelector() {
        $(window).off('resize.visualselector').on('resize.visualselector', () => {
            setScale();
            highlightCurrentSelected();
        });

        setScale();

        console.log(selectorData['size_pos'].length + " selectors found");

