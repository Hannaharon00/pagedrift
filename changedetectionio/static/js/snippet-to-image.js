/**
 * snippet-to-image.js
 * Converts selected diff content to a shareable JPEG image with metadata
 */

// Constants
const IMAGE_PADDING = 5;
const JPEG_QUALITY = 0.95;
const CANVAS_SCALE = 1;
const RENDER_DELAY_MS = 50;

/**
 * Utility: Get the target URL from global watch_url or fallback to current URL
 */
function getTargetUrl() {
    return (typeof watch_url !== 'undefined' && watch_url) ? watch_url : window.location.href;
}

/**
 * Utility: Get formatted current date with timezone
 */
function getFormattedDate() {
    return new Date().toLocaleString(undefined, {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        timeZoneName: 'short'
    });
}

/**
 * Expands a selection range to include complete lines
 * If a user selects partial text, this ensures full lines are captured
 */
function expandRangeToFullLines(range, container) {
    const newRange = range.cloneRange();

    // Expand start to line beginning
    if (newRange.startContainer.nodeType === Node.TEXT_NODE) {
        const text = newRange.startContainer.textContent;
        const lastNewline = text.lastIndexOf('\n', newRange.startOffset - 1);
        if (lastNewline !== -1) {
            newRange.setStart(newRange.startContainer, lastNewline + 1);
        } else {
            const lineStart = findLineBoundary(newRange.startContainer, container, true);
            if (lineStart) {
                newRange.setStart(lineStart.node, lineStart.offset);
            } else {
                newRange.setStart(container, 0);
            }
        }
    }

    // Expand end to line end
    if (newRange.endContainer.nodeType === Node.TEXT_NODE) {
        const text = newRange.endContainer.textContent;
        const nextNewline = text.indexOf('\n', newRange.endOffset);
        if (nextNewline !== -1) {
            newRange.setEnd(newRange.endContainer, nextNewline);
        } else {
            const lineEnd = findLineBoundary(newRange.endContainer, container, false);
            if (lineEnd) {
                newRange.setEnd(lineEnd.node, lineEnd.offset);
            } else {
                const lastNode = getLastTextNode(container);
                newRange.setEnd(
                    lastNode || container,
                    lastNode ? lastNode.textContent.length : container.childNodes.length
                );
            }
        }
    }

    return newRange;
}

/**
 * Create footer with metadata (URL, version info, line count)
 */
function createFooter(selectedLines, totalLines) {
    const url = getTargetUrl();
    const versionInfo = getVersionInfo();
    const lineInfo = (selectedLines && totalLines) ? ` - ${selectedLines} of ${totalLines} lines selected` : '';

    const footer = document.createElement("div");
    footer.innerHTML = `
        <div style="
            position: relative;
            z-index: 1;
            background-color: #1324fd;
            color: #fff;
            padding: 10px;
            margin-top: 10px;
            font-size: 12px;
            font-family: Arial, sans-serif;
            line-height: 1.5;
            border-top: 1px solid #ccc;
        ">
            Watched URL: <strong>${url}</strong><br>
            ${versionInfo}${lineInfo}<br>
            Monitored via automated content change detection on public webpages. Data reflects observed text updates, not editorial verification.
        </div>
    `;

    return footer.firstElementChild;
}

