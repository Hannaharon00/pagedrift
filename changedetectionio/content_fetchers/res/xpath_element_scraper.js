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

// Create an array to hold the visible elements
    const visibleElementsArray = [];

// Call collectVisibleElements with the starting parent element
    collectVisibleElements(document.body, visibleElementsArray);


    visibleElementsArray.forEach(function (element) {

        bbox = element.getBoundingClientRect();

        // Skip really small ones, and where width or height ==0
        if (bbox['width'] * bbox['height'] < 10) {
            return
        }

        // Don't include elements that are offset from canvas
        if (bbox['top'] + scroll_y < 0 || bbox['left'] < 0) {
            return
        }

        // @todo the getXpath kind of sucks, it doesnt know when there is for example just one ID sometimes
        // it should not traverse when we know we can anchor off just an ID one level up etc..
        // maybe, get current class or id, keep traversing up looking for only class or id until there is just one match

        // 1st primitive - if it has class, try joining it all and select, if theres only one.. well thats us.
        xpath_result = false;
        try {
            var d = findUpTag(element);
            if (d) {
                xpath_result = d;
            }
        } catch (e) {
            console.log(e);
        }
        // You could swap it and default to getXpath and then try the smarter one
        // default back to the less intelligent one
        if (!xpath_result) {
            try {
                // I've seen on FB and eBay that this doesnt work
                // ReferenceError: getXPath is not defined at eval (eval at evaluate (:152:29), <anonymous>:67:20) at UtilityScript.evaluate (<anonymous>:159:18) at UtilityScript.<anonymous> (<anonymous>:1:44)
                xpath_result = getxpath(element);
            } catch (e) {
                console.log(e);
                return
            }
        }

        let label = "not-interesting" // A placeholder, the actual labels for training are done by hand for now

        let text = element.textContent.trim().slice(0, 30).trim();
        while (/\n{2,}|\t{2,}/.test(text)) {
            text = text.replace(/\n{2,}/g, '\n').replace(/\t{2,}/g, '\t')
        }

        // Try to identify any possible currency amounts "Sale: 4000" or "Sale now 3000 Kc", can help with the training.
        const hasDigitCurrency = (/\d/.test(text.slice(0, 6)) || /\d/.test(text.slice(-6))) && /([€£$¥₩₹]|USD|AUD|EUR|Kč|kr|SEK|,–)/.test(text);
        const computedStyle = window.getComputedStyle(element);

        if (Math.floor(bbox['top']) + scroll_y > max_height) {
            return
        }

        size_pos.push({
            xpath: xpath_result,
            width: Math.round(bbox['width']),
            height: Math.round(bbox['height']),
            left: Math.floor(bbox['left']),
            top: Math.floor(bbox['top']) + scroll_y,
            // tagName used by Browser Steps
            tagName: (element.tagName) ? element.tagName.toLowerCase() : '',
            // tagtype used by Browser Steps
            tagtype: (element.tagName.toLowerCase() === 'input' && element.type) ? element.type.toLowerCase() : '',
            isClickable: computedStyle.cursor === "pointer",
            // Used by the keras trainer
            fontSize: computedStyle.getPropertyValue('font-size'),
            fontWeight: computedStyle.getPropertyValue('font-weight'),
            hasDigitCurrency: hasDigitCurrency,
            label: label,
        });

    });


