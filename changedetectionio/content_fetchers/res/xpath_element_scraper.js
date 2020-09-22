async (options) => {

    let visualselector_xpath_selectors = options.visualselector_xpath_selectors
    let max_height = options.max_height

    var scroll_y = 0;
    try {
        scroll_y = +document.documentElement.scrollTop || document.body.scrollTop
    } catch (e) {
        console.log(e);
    }

// Include the getXpath script directly, easier than fetching
    function getxpath(e) {
        var n = e;
        // A double quote cannot be expressed inside a double-quoted xpath literal, and an angle
        // bracket would carry page markup into whatever displays the selector later, so for those
        // ids build the positional path below instead of an unusable '//*[@id="..."]'.
        if (n && n.id && !/["<>]/.test(n.id)) return '//*[@id="' + n.id + '"]';
        for (var o = []; n && Node.ELEMENT_NODE === n.nodeType;) {
            for (var i = 0, r = !1, d = n.previousSibling; d;) d.nodeType !== Node.DOCUMENT_TYPE_NODE && d.nodeName === n.nodeName && i++, d = d.previousSibling;
            for (d = n.nextSibling; d;) {
                if (d.nodeName === n.nodeName) {
                    r = !0;
                    break
                }
                d = d.nextSibling
            }
            o.push((n.prefix ? n.prefix + ":" : "") + n.localName + (i || r ? "[" + (i + 1) + "]" : "")), n = n.parentNode
        }
        return o.length ? "/" + o.reverse().join("/") : ""
    }

    const findUpTag = (el) => {
        let r = el
        chained_css = [];
        depth = 0;

        //  Strategy 1: If it's an input, with name, and there's only one, prefer that
        if (el.name !== undefined && el.name.length) {
            var proposed = el.tagName + "[name=\"" + CSS.escape(el.name) + "\"]";
            var proposed_element = window.document.querySelectorAll(proposed);
            if (proposed_element.length) {
                if (proposed_element.length === 1) {
                    return proposed;
                } else {
                    // Some sites change ID but name= stays the same, we can hit it if we know the index
                    // Find all the elements that match and work out the input[n]
                    var n = Array.from(proposed_element).indexOf(el);
                    // Return a Playwright selector for nthinput[name=zipcode]
                    return proposed + " >> nth=" + n;
                }
            }
        }

        // Strategy 2: Keep going up until we hit an ID tag, imagine it's like  #list-widget div h4
        while (r.parentNode) {
            if (depth === 5) {
                break;
            }
            if ('' !== r.id) {
                chained_css.unshift("#" + CSS.escape(r.id));
                final_selector = chained_css.join(' > ');
                // Be sure theres only one, some sites have multiples of the same ID tag :-(
                if (window.document.querySelectorAll(final_selector).length === 1) {
                    return final_selector;
                }
                return null;
            } else {
                chained_css.unshift(r.tagName.toLowerCase());
            }
            r = r.parentNode;
            depth += 1;
        }
        return null;
    }


// @todo - if it's SVG or IMG, go into image diff mode

    var size_pos = [];
// after page fetch, inject this JS
// build a map of all elements and their positions (maybe that only include text?)
    var bbox;
    console.log(`Scanning for "${visualselector_xpath_selectors}"`);

    function collectVisibleElements(parent, visibleElements) {
        if (!parent) return; // Base case: if parent is null or undefined, return


        // Add the parent itself to the visible elements array if it's of the specified types
        const tagName = parent.tagName.toLowerCase();
        if (visualselector_xpath_selectors.split(',').includes(tagName)) {
            visibleElements.push(parent);
        }

        // Iterate over the parent's children
        const children = parent.children;
        for (let i = 0; i < children.length; i++) {
            const child = children[i];
            const computedStyle = window.getComputedStyle(child);

            if (
                child.nodeType === Node.ELEMENT_NODE &&
                computedStyle.display !== 'none' &&
                computedStyle.visibility !== 'hidden' &&
                child.offsetWidth >= 0 &&
                child.offsetHeight >= 0 &&
                computedStyle.contentVisibility !== 'hidden'
            ) {
                // If the child is an element and is visible, recursively collect visible elements
                collectVisibleElements(child, visibleElements);
            }
        }
    }

