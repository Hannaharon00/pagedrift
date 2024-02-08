// Copyright (C) 2021 Leigh Morresi (dgtlmoon@gmail.com)
// All rights reserved.
// yes - this is really a hack, if you are a front-ender and want to help, please get in touch!
//
// Refactored into a reusable factory: window.initVisualSelector(opts)
//   - edit.html drives it from stored screenshot + xpath-data URLs (auto-init at bottom of file)
//   - the Add Watch UI drives it from inline snapshot data fetched on demand
// Both share the same hover/highlight/select core.

window.initVisualSelector = function (opts) {
    // ---- DOM references (passed in, no globals) ----
    const $selectorCanvasElem = opts.$canvas;
    const $includeFiltersElem = opts.$includeFilters;
    const $selectorBackgroundElem = opts.$background;
    const $selectorCurrentXpathElem = opts.$xpathDisplay;          // the inner <span>
    const $fetchingUpdateNoticeElem = opts.$fetchingNotice || $();
    const $selectorWrapperElem = opts.$wrapper;
    const $clearSelectorElem = opts.$clearButton || $();

    // edit.html supplies an AJAX url for the element data; the add-watch UI supplies data inline
    const xpathDataUrl = opts.xpathDataUrl;
    const isImageProcessor = !!opts.processorIsImage;
    // Stored watch screenshots are DPR-1, so X scales by the screenshot's natural width.
    // The live browser-steps capture (used by Add Watch) may render at device-scale-factor != 1,
    // so its X must scale by the page's CSS width (browser_width) instead - exactly like
    // browser-steps.js does. Y always scales by the screenshot's natural height.
    const scaleByBrowserWidth = !!opts.scaleByBrowserWidth;

    // ---- state ----
    let runInClearMode = false;
    let selectionEnabled = opts.enableSelection !== false;
    let currentSelections = [];
    let currentSelection = null;
    let appendToList = false;
    let c, xctx, ctx;
    let xScale = 1, yScale = 1;
    let selectorImage, selectorImageRect, selectorData;
    let elementHandlers = {}; // Store references to element selection handlers (needed for draw mode toggling)

    // Box drawing mode variables (for image_ssim_diff processor)
    let drawMode = false;
    let isDrawing = false;
    let isDragging = false;
    let drawStartX, drawStartY;
    let dragOffsetX, dragOffsetY;
    let drawnBox = null;
    let resizeHandle = null;
    const HANDLE_SIZE = 8;

    // Color constants
    const FILL_STYLE_HIGHLIGHT = 'rgba(205,0,0,0.35)';
    const FILL_STYLE_GREYED_OUT = 'rgba(205,205,205,0.95)';
    const STROKE_STYLE_HIGHLIGHT = 'rgba(255,0,0, 0.9)';
    const FILL_STYLE_REDLINE = 'rgba(255,0,0, 0.1)';
    const STROKE_STYLE_REDLINE = 'rgba(225,0,0,0.9)';

    function clearReset() {
        if (ctx) {
            ctx.clearRect(0, 0, c.width, c.height);
        }

        if ($includeFiltersElem.val().length) {
            alert(i18nT('vsFiltersCleared', "Existing filters under the 'Filters & Triggers' tab were cleared."));
        }
        $includeFiltersElem.val('');

        currentSelections = [];

        // Means we ignore the xpaths from the scraper marked as sel.highlight_as_custom_filter (it matched a previous selector)
        runInClearMode = true;

        highlightCurrentSelected();
    }

    function splitToList(v) {
        return v.split('\n').map(line => line.trim()).filter(line => line.length > 0);
    }

    function sortScrapedElementsBySize() {
        // Sort the currentSelections array by area (width * height) in descending order
        selectorData['size_pos'].sort((a, b) => {
            const areaA = a.width * a.height;
            const areaB = b.width * b.height;
            return areaB - areaA;
        });
    }

    $(document).on('keydown keyup', (event) => {
        if (event.code === 'ShiftLeft' || event.code === 'ShiftRight') {
            appendToList = event.type === 'keydown';
        }

        if (event.type === 'keydown') {
            if ($selectorBackgroundElem.is(":visible") && event.key === "Escape") {
                clearReset();
            }
        }
    });

    $clearSelectorElem.on('click', () => {
        clearReset();
    });

    // ---- public: (re)load a screenshot + element data into the selector ----
    // source = { screenshotSrc: <url|dataURI>, xpathData: <object|undefined> }
    function load(source) {
        currentSelections = [];
        runInClearMode = false;

        $selectorBackgroundElem
            .off("load error")
            .on("error", () => {
                $fetchingUpdateNoticeElem.html("<strong>Ooops!</strong> The VisualSelector tool needs at least one fetched page, please unpause the watch and/or wait for the watch to complete fetching and then reload this page.")
                    .css('color', '#bb0000');
                $('#selector-current-xpath, #clear-selector').hide();
            })
            .on('load', () => {
                console.log(`Loaded background ${$selectorBackgroundElem[0].naturalWidth}px`);
                // For the UI width of the whole edit area
                document.documentElement.style.setProperty('--visualselector-max-width', `${$selectorBackgroundElem[0].naturalWidth}px` );
                c = $selectorCanvasElem[0];
                xctx = c.getContext("2d");
                ctx = c.getContext("2d");
                // Drop any handlers left over from a previous load BEFORE (re)building the
                // selector - applyElementData() runs synchronously for inline xpathData and
                // binds the element handlers itself, so unbinding afterwards would silently
                // kill hover/click selection on the add-watch snapshot path.
                $selectorCanvasElem.off("mousemove mousedown mouseleave");
                if (source.xpathData) {
                    // Inline data (add-watch snapshot) - no extra round trip needed
                    applyElementData(source.xpathData);
                } else {
                    fetchData();
                }
            });

        // data: URIs must be used verbatim; real URLs get a cache-buster
        let src = source.screenshotSrc;
        if (src && src.indexOf('data:') !== 0) {
            src = `${src}?${new Date().getTime()}`;
        }
        $selectorBackgroundElem.attr("src", src);
    }

    function alertIfFilterNotFound() {
        let existingFilters = splitToList($includeFiltersElem.val());
        let sizePosXpaths = selectorData['size_pos'].map(sel => sel.xpath);

        for (let filter of existingFilters) {
            if (!sizePosXpaths.includes(filter)) {
                alert(`One or more of your existing filters was not found and will be removed when a new filter is selected.`);
                break;
            }
        }
    }

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

        let existingFilters = splitToList($includeFiltersElem.val());

        selectorData['size_pos'].forEach(sel => {
            if ((!runInClearMode && sel.highlight_as_custom_filter) || existingFilters.includes(sel.xpath)) {
                console.log("highlighting " + c);
                currentSelections.push(sel);
            }
        });


        highlightCurrentSelected();
        updateFiltersText();

        if (selectionEnabled) {
            bindElementHandlers();
        }
    }

    function highlightCurrentSelected() {
        if (!xctx) return;
        xctx.fillStyle = FILL_STYLE_GREYED_OUT;
        xctx.strokeStyle = STROKE_STYLE_REDLINE;
        xctx.lineWidth = 3;
        xctx.clearRect(0, 0, c.width, c.height);

        currentSelections.forEach(sel => {
            //xctx.clearRect(sel.left * xScale, sel.top * yScale, sel.width * xScale, sel.height * yScale);
            xctx.strokeRect(sel.left * xScale, sel.top * yScale, sel.width * xScale, sel.height * yScale);
        });
    }

    // Toggle hover/click element selection on the fly (Add Watch "by element" mode)
    function setSelectionEnabled(enabled) {
        selectionEnabled = enabled;
        if (!c) return; // not loaded yet, will respect the flag in reflowSelector

        if (enabled) {
            if (!drawMode) {
                bindElementHandlers();
                if ($selectorCurrentXpathElem.length) {
                    $selectorCurrentXpathElem[0].innerHTML = 'Hover over elements to select';
                }
            }
        } else {
            $selectorCanvasElem.unbind('mousemove mousedown mouseleave');
            currentSelections = [];
            $includeFiltersElem.val('');
            highlightCurrentSelected();
            if ($selectorCurrentXpathElem.length) {
                $selectorCurrentXpathElem[0].innerHTML = '';
            }
        }
    }

    // ============= BOX DRAWING MODE (for image_ssim_diff processor) =============

    function initializeDrawMode() {
        if (!isImageProcessor || !c) return;

        const $selectorModeRadios = $('input[name="selector-mode"]');
        const $boundingBoxField = $('#bounding_box');
        const $selectionModeField = $('#selection_mode');

        // Load existing selection mode if present
        const savedMode = $selectionModeField.val();
        if (savedMode && (savedMode === 'element' || savedMode === 'draw')) {
            $selectorModeRadios.filter(`[value="${savedMode}"]`).prop('checked', true);
            console.log('Loaded saved mode:', savedMode);
        }

        // Clear the canvas
        if (ctx && xctx) {
            ctx.clearRect(0, 0, c.width, c.height);
            xctx.clearRect(0, 0, c.width, c.height);
        }

        // Redraw if we have an existing box
        if (drawnBox) {
            drawBox();
        }
    }

    function disableDrawMode() {
        console.log('Disabling draw mode, switching to element mode...');

        // Unbind draw handlers
        $selectorCanvasElem.unbind('mousedown mousemove mouseup mouseleave');

        // Reset cursor
        $selectorCanvasElem.css('cursor', 'default');

        // Clear drawn box
        drawnBox = null;
        $('#bounding_box').val('');

        // Clear the canvases
        if (ctx && xctx) {
            ctx.clearRect(0, 0, c.width, c.height);
            xctx.clearRect(0, 0, c.width, c.height);
        }

        // Restore element selections from include_filters
        currentSelections = [];
        if (selectorData && selectorData['size_pos']) {
            let existingFilters = splitToList($includeFiltersElem.val());

            selectorData['size_pos'].forEach(sel => {
                if ((!runInClearMode && sel.highlight_as_custom_filter) || existingFilters.includes(sel.xpath)) {
                    console.log("Restoring selection: " + sel.xpath);
                    currentSelections.push(sel);
                }
            });
        }

        // Re-enable element selection handlers using stored references
        if (elementHandlers.handleMouseMove) {
            $selectorCanvasElem.bind('mousemove', elementHandlers.handleMouseMove);
            $selectorCanvasElem.bind('mousedown', elementHandlers.handleMouseDown);
            $selectorCanvasElem.bind('mouseleave', elementHandlers.handleMouseLeave);
        }

        // Restore the element selection display
        $selectorCurrentXpathElem.html(i18nT('vsHover', 'Hover over elements to select'));

        // Highlight the restored selections
        highlightCurrentSelected();
    }

    function handleDrawMouseDown(e) {
        const rect = c.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;

