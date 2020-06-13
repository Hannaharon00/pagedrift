async (options) => {

    let visualselector_xpath_selectors = options.visualselector_xpath_selectors
    let max_height = options.max_height

    var scroll_y = 0;
    try {
        scroll_y = +document.documentElement.scrollTop || document.body.scrollTop
    } catch (e) {
        console.log(e);
    }

