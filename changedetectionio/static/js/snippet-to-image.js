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
 * Utility: Get version comparison info from the diff selectors
 */
function getVersionInfo() {
    const fromSelect = document.getElementById('diff-from-version');
    const toSelect = document.getElementById('diff-to-version');

    if (!fromSelect || !toSelect) {
        return '';
    }

    const fromOption = fromSelect.options[fromSelect.selectedIndex];
    const toOption = toSelect.options[toSelect.selectedIndex];
    const fromLabel = fromOption ? (fromOption.getAttribute('label') || fromOption.text) : 'Unknown';
    const toLabel = toOption ? (toOption.getAttribute('label') || toOption.text) : 'Unknown';

    return `Change comparison from <strong>${fromLabel}</strong> to <strong>${toLabel}</strong>`;
}

/**
 * Helper: Find text node containing newline in a given direction
 */
function findTextNodeWithNewline(node, searchBackwards = false) {
    if (node.nodeType === Node.TEXT_NODE) {
        const text = node.textContent;
        const idx = searchBackwards ? text.lastIndexOf('\n') : text.indexOf('\n');
        if (idx !== -1) {
            return { node, offset: searchBackwards ? idx + 1 : idx };
        }
    } else {
        const walker = document.createTreeWalker(node, NodeFilter.SHOW_TEXT);
        let textNode;
        while (textNode = walker.nextNode()) {
            const text = textNode.textContent;
            const idx = searchBackwards ? text.lastIndexOf('\n') : text.indexOf('\n');
            if (idx !== -1) {
                return { node: textNode, offset: searchBackwards ? idx + 1 : idx };
            }
        }
    }
    return null;
}

/**
 * Helper: Walk through siblings in a given direction to find line boundary
 */
function findLineBoundary(node, container, searchBackwards = false) {
    let currentNode = node;

    while (currentNode && currentNode !== container) {
        const sibling = searchBackwards ? currentNode.previousSibling : currentNode.nextSibling;
        let currentSibling = sibling;

        while (currentSibling) {
            const result = findTextNodeWithNewline(currentSibling, searchBackwards);
            if (result) {
                return result;
            }
            currentSibling = searchBackwards ? currentSibling.previousSibling : currentSibling.nextSibling;
        }

        currentNode = currentNode.parentNode;
    }

    return null;
}

/**
 * Helper: Get the last text node in a container
 */
function getLastTextNode(container) {
    const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
    let lastNode = null;
    let textNode;
    while (textNode = walker.nextNode()) {
        lastNode = textNode;
    }
    return lastNode;
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
 * Create a temporary element with the selected content styled for capture
 */
function createCaptureElement(selectedFragment, originalElement) {
    const originalStyles = window.getComputedStyle(originalElement);

    // Create container with watermark background
    const container = document.createElement("div");
    container.innerHTML = `
        <div style="
            position: absolute;
            left: -9999px;
            top: 0;
            padding: 2px;
            background-color: transparent;
        ">
        <div style="
            background-color: #ffffff;
            width: ${originalElement.offsetWidth}px;
            border: 1px solid #ccc;
            border-radius: 4px;
            overflow: hidden;
        ">
            <!-- Watermark background -->
            <div style="
                position: absolute;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                overflow: hidden;
                pointer-events: none;
                z-index: 0;
                background-image: url(&quot;data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='400' height='200' viewBox='0 0 400 200'><g font-family='Arial' font-size='18' font-weight='700' fill='%23e8e8e8' transform='rotate(-45 200 100)'><text x='0' y='40'>changedetection.io   changedetection.io   changedetection.io</text><text x='0' y='100'>changedetection.io   changedetection.io   changedetection.io</text><text x='0' y='160'>changedetection.io   changedetection.io   changedetection.io</text></g></svg>&quot;);
                background-repeat: repeat;
                background-size: 400px 200px;
            "></div>

            <!-- Content -->
            <pre id="temp-capture-element" style="
                position: relative;
                z-index: 1;
                white-space: ${originalStyles.whiteSpace};
                font-family: ${originalStyles.fontFamily};
                font-size: ${originalStyles.fontSize};
                line-height: ${originalStyles.lineHeight};
                color: ${originalStyles.color};
                word-wrap: ${originalStyles.wordWrap};
                overflow-wrap: ${originalStyles.overflowWrap};
                background-color: transparent;
                padding: ${IMAGE_PADDING}px;
                border: ${originalStyles.border};
                box-sizing: border-box;
                margin: 0;
            "></pre>
        </div>
        </div>
    `;

    const outerWrapper = container.firstElementChild;
    const innerWrapper = outerWrapper.querySelector('div');
    const tempElement = innerWrapper.querySelector('#temp-capture-element');
    tempElement.appendChild(selectedFragment);

    // Store innerWrapper for footer appending
    outerWrapper._innerWrapper = innerWrapper;

    return outerWrapper;
}

/**
 * Count lines in a text string or document fragment
 */
function countLines(content) {
    if (!content) return 0;

    let text = '';
    if (typeof content === 'string') {
        text = content;
    } else if (content.textContent) {
        text = content.textContent;
    }

    // Count newlines + 1 (for the last line)
    const lines = text.split('\n').length;
    return lines > 0 ? lines : 1;
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

/**
 * Add EXIF metadata to JPEG image
 */
function addExifMetadata(jpegDataUrl) {
    if (typeof piexif === 'undefined') {
        return jpegDataUrl;
    }

    try {
        const url = getTargetUrl();
        const timestamp = new Date().toISOString();

        const exifObj = {
            "0th": {
                [piexif.ImageIFD.Software]: "changedetection.io",
                [piexif.ImageIFD.ImageDescription]: `Diff snapshot from ${url}`,
                [piexif.ImageIFD.Copyright]: "Generated by changedetection.io"
            },
            "Exif": {
                [piexif.ExifIFD.DateTimeOriginal]: timestamp,
                [piexif.ExifIFD.UserComment]: `URL: ${url} | Captured: ${timestamp} | Source: changedetection.io`
            }
        };

        const exifBytes = piexif.dump(exifObj);
        return piexif.insert(exifBytes, jpegDataUrl);
    } catch (error) {
        console.warn("Failed to add EXIF metadata:", error);
        return jpegDataUrl;
    }
}

/**
 * Convert data URL to Blob for sharing
 */
function dataURLtoBlob(dataURL) {
    const parts = dataURL.split(',');
    const byteString = atob(parts[1]);
    const mimeString = parts[0].split(':')[1].split(';')[0];
    const ab = new ArrayBuffer(byteString.length);
    const ia = new Uint8Array(ab);
    for (let i = 0; i < byteString.length; i++) {
        ia[i] = byteString.charCodeAt(i);
    }
    return new Blob([ab], { type: mimeString });
}

/**
 * Download the image
 */
function downloadImage(jpegDataUrl) {
    const a = document.createElement("a");
    a.href = jpegDataUrl;
    a.download = "changedetection-diff-" + Date.now() + ".jpg";
    a.click();
}

/**
 * Copy image to clipboard
 */
async function copyImageToClipboard(jpegDataUrl) {
    try {
        const blob = dataURLtoBlob(jpegDataUrl);
        await navigator.clipboard.write([
            new ClipboardItem({ 'image/jpeg': blob })
        ]);
        alert(i18nT('imgCopied', 'Image copied to clipboard!'));
    } catch (error) {
        console.error('Failed to copy image:', error);
        alert(i18nT('imgCopyFailed', 'Failed to copy image. Your browser may not support this feature.'));
    }
}

/**
 * Share via Web Share API or fallback to platform-specific sharing
 */
async function shareImage(platform, jpegDataUrl) {
    const url = getTargetUrl();
    const shareText = `Check out this change detected on ${url} via changedetection.io`;
    const filename = "changedetection-diff-" + Date.now() + ".jpg";

    // Try Web Share API first (works on mobile and some desktop browsers)
    if (platform === 'native' && navigator.share) {
        try {
            const blob = dataURLtoBlob(jpegDataUrl);
            const file = new File([blob], filename, { type: 'image/jpeg' });

            await navigator.share({
                title: 'Change Detection Diff',
                text: shareText,
                files: [file]
            });
            return;
        } catch (error) {
            if (error.name !== 'AbortError') {
                console.error('Web Share API failed:', error);
            }
            return;
        }
    }

    // Platform-specific fallbacks
    const encodedText = encodeURIComponent(shareText);
    const encodedUrl = encodeURIComponent(url);

    let shareUrl;
    switch (platform) {
        case 'twitter':
            shareUrl = `https://twitter.com/intent/tweet?text=${encodedText}`;
            break;
        case 'facebook':
            shareUrl = `https://www.facebook.com/sharer/sharer.php?u=${encodedUrl}&quote=${encodedText}`;
            break;
        case 'linkedin':
            shareUrl = `https://www.linkedin.com/sharing/share-offsite/?url=${encodedUrl}`;
            break;
        case 'reddit':
            shareUrl = `https://reddit.com/submit?url=${encodedUrl}&title=${encodeURIComponent('Change Detection Diff')}`;
            break;
        case 'email':
            shareUrl = `mailto:?subject=${encodeURIComponent('Change Detection Diff')}&body=${encodedText}`;
            break;
        default:
            return;
    }

    window.open(shareUrl, '_blank', 'width=600,height=400');
}

