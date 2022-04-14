/**
 * Interactive Image Comparison Slider
 *
 * Allows users to drag a vertical slider to reveal differences between
 * two images (before/after comparison).
 */
(function() {
    'use strict';

    function initComparisonSlider() {
        const container = document.getElementById('comparison-container');
        const slider = document.getElementById('comparison-slider');
        const afterWrapper = container ? container.querySelector('.comparison-after') : null;
        const handle = slider ? slider.querySelector('.comparison-handle') : null;

        if (!container || !slider || !afterWrapper || !handle) {
            return;
        }

        let isDragging = false;
        let isMouseOverContainer = false;
        let mouseY = 0;

        /**
         * Update handle position - follows mouse if hovering, or viewport center
         */
        function updateHandlePosition() {
            const containerRect = container.getBoundingClientRect();
            let handleTop;

            if (isMouseOverContainer) {
                // Mouse is over container - follow the mouse Y position
                handleTop = mouseY - containerRect.top;
            } else {
                // Mouse not over container - use viewport center
                const viewportCenter = window.innerHeight / 2;

                if (containerRect.top > viewportCenter) {
                    // Container is below viewport center - position handle at container top
                    handleTop = 0;
                } else if (containerRect.bottom < viewportCenter) {
                    // Container is above viewport center - position handle at container bottom
                    handleTop = containerRect.height;
                } else {
                    // Container spans viewport center - position handle at viewport center
                    handleTop = viewportCenter - containerRect.top;
                }
            }

