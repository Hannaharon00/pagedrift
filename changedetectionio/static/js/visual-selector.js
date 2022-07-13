// Copyright (C) 2021 Leigh Morresi (dgtlmoon@gmail.com)
// All rights reserved.
// yes - this is really a hack, if you are a front-ender and want to help, please get in touch!
//
// Refactored into a reusable factory: window.initVisualSelector(opts)
//   - edit.html drives it from stored screenshot + xpath-data URLs (auto-init at bottom of file)
//   - the Add Watch UI drives it from inline snapshot data fetched on demand
// Both share the same hover/highlight/select core.

    function fetchData() {
        $fetchingUpdateNoticeElem.html(i18nT('vsFetching', "Fetching element data.."));

        $.ajax({
            url: xpathDataUrl,
            context: document.body
        }).done((data) => {
            applyElementData(data);
        });
    }

    function applyElementData(data) {
        $fetchingUpdateNoticeElem.html(i18nT('vsRendering', "Rendering.."));
        selectorData = data;

        sortScrapedElementsBySize();
        console.log(`Reported browser width from backend: ${data['browser_width']}`);

        // Little sanity check for the user, alert them if something missing
        alertIfFilterNotFound();

        setScale();
        reflowSelector();

        // Initialize draw mode after everything is set up
        initializeDrawMode();

        $fetchingUpdateNoticeElem.fadeOut();
    }

    function updateFiltersText() {
        // Assuming currentSelections is already defined and contains the selections
        let uniqueSelections = new Set(currentSelections.map(sel => (sel[0] === '/' ? `xpath:${sel.xpath}` : sel.xpath)));

        if (currentSelections.length > 0) {
            // Convert the Set back to an array and join with newline characters
            let textboxFilterText = Array.from(uniqueSelections).join("\n");
            $includeFiltersElem.val(textboxFilterText);
        }
    }

    function setScale() {
        $selectorWrapperElem.show();
        selectorImage = $selectorBackgroundElem[0];
        selectorImageRect = selectorImage.getBoundingClientRect();

        $selectorCanvasElem.attr({
            'height': selectorImageRect.height,
            'width': selectorImageRect.width
        });
        $selectorWrapperElem.attr('width', selectorImageRect.width);
        $('#visual-selector-heading').css('max-width', selectorImageRect.width + "px")

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

