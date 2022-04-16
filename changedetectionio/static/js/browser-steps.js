$(document).ready(function () {

    var browsersteps_session_id;
    var browser_interface_seconds_remaining = 0;
    var apply_buttons_disabled = false;
    var include_text_elements = $("#include_text_elements");
    var xpath_data = false;
    var current_selected_i;
    var state_clicked = false;
    var c;

    // redline highlight context
    var ctx;
    var last_click_xy = {'x': -1, 'y': -1}

    $(window).resize(function () {
        set_scale();
    });
    // Should always be disabled

    $('#browsersteps-click-start').click(function () {
        $("#browsersteps-click-start").fadeOut();
        $("#browsersteps-selector-wrapper .spinner").fadeIn();
        start();
    });

    $('a#browsersteps-tab').click(function () {
        reset();
    });

    window.addEventListener('hashchange', function () {
        if (window.location.hash == '#browser-steps') {
            reset();
        }
    });

        // Debounce and find the current most 'interesting' element we are hovering above
        $('#browsersteps-selector-canvas').bind('mousemove', function (e) {
            if (!xpath_data) {
                return;
            }

            // checkbox if find elements is enabled
            ctx.clearRect(0, 0, c.width, c.height);
            ctx.fillStyle = 'rgba(255,0,0, 0.1)';
            ctx.strokeStyle = 'rgba(255,0,0, 0.9)';

            // Add in offset
            if ((typeof e.offsetX === "undefined" || typeof e.offsetY === "undefined") || (e.offsetX === 0 && e.offsetY === 0)) {
                var targetOffset = $(e.target).offset();
                e.offsetX = e.pageX - targetOffset.left;
                e.offsetY = e.pageY - targetOffset.top;
            }
            current_selected_i = false;
            // Reverse order - the most specific one should be deeper/"laster"
            // Basically, find the most 'deepest'
            var possible_elements = [];
            xpath_data['size_pos'].forEach(function (item, index) {
                // If we are in a bounding-box
                if (e.offsetY > item.top * y_scale && e.offsetY < item.top * y_scale + item.height * y_scale
                    &&
                    e.offsetX > item.left * y_scale && e.offsetX < item.left * y_scale + item.width * y_scale

                ) {
                    // Ignore really large ones, because we are scraping 'div' also from xpath_element_scraper but
                    // that div or whatever could be some wrapper and would generally make you select the whole page
                    if (item.width > 800 && item.height > 400) {
                        return
                    }

                    // There could be many elements here, record them all and then we'll find out which is the most 'useful'
                    // (input, textarea, button, A etc)
                    if (item.width < xpath_data['browser_width']) {
                        possible_elements.push(item);
                    }
                }
            });

            // Find the best one
            if (possible_elements.length) {
                possible_elements.forEach(function (item, index) {
                  if (["a", "input", "select", "textarea", "button"].includes(item['tagName'])) {
                      current_selected_i = item;
                  }
                });

                if (!current_selected_i) {
                    current_selected_i = possible_elements[0];
                }

                sel = xpath_data['size_pos'][current_selected_i];
                ctx.strokeRect(current_selected_i.left * x_scale, current_selected_i.top * y_scale, current_selected_i.width * x_scale, current_selected_i.height * y_scale);
                ctx.fillRect(current_selected_i.left * x_scale, current_selected_i.top * y_scale, current_selected_i.width * x_scale, current_selected_i.height * y_scale);
            }


        }.debounce(10));
    });

