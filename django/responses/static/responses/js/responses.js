jQuery(document).ready(function ($) {

    var slider_images = [
        'pakt,igf-1,100,10__perk,fgf-1,100,10.png',
        'pakt,igf-1,100,30__perk,fgf-1,100,30.png',
        'pakt,igf-1,100,90__perk,fgf-1,100,90.png'
    ];
    var timepoints = [10, 30, 90];

    $("#slider").slider({
        value: 0,
        min: 0,
        max: 2,
        slide: function(event, ui) {
            slide_to(ui.value);
        }
    });
    slide_to($("#slider").slider("value"));

    function slide_to(value) {
        var $img = $("#slider-img");
        var src = $img.attr('src');
        var new_src = src.substr(0, src.lastIndexOf('/') + 1) + slider_images[value];
        $img.attr('src', new_src);
        $("#timepoint").val(timepoints[value] + " min");
    }

    // ------------------------------------------------------------------------
    // scatterplot popups

    var POINTMAP = hmslincs.POINTMAP;
    var CLICK_RADIUS = 8;
    var CLICK_RADIUS_2 = CLICK_RADIUS*CLICK_RADIUS;
    function get_popup_rows(image_id, coords) {
        var points = POINTMAP[image_id];
        var x = coords.x; var y = coords.y;
        var rows = [];
        for (var i = 0; i < points.length; i++) {
            var coords = points[i].coords;
            var dx = x - coords.x; var dy = y - coords.y;
            if (dx*dx + dy*dy < CLICK_RADIUS_2) rows.push(points[i].row);
        }
        return rows;
    }

    function remove_popup(e) {
        e.stopPropagation();
        $('#popup').remove();
    }

    $(window).bind({
        mousedown: remove_popup,
        resize: remove_popup,
        scroll: remove_popup,
    });

    function pxtoint(s) {
        return parseInt(s.replace(/px\s*$/i, ''));
    }

    function get_popup_margins($popup) {
        var margins = {t: pxtoint($popup.css('margin-top')),
                       r: pxtoint($popup.css('margin-right')),
                       b: pxtoint($popup.css('margin-bottom')),
                       l: pxtoint($popup.css('margin-left'))};
                       
        // function redefines itself as a closure, with memoized return value
        get_popup_margins = function ($p) { return margins; }
        return get_popup_margins($popup);
    }

    function get_popup_lr_offset($popup) {
        // returns x- and y-offsets of popup's lower-right corner
        // (relative to popup's position)
        var margins = get_popup_margins($popup);
        var slack = 1;
        var dx = margins.r + slack;
        var dy = margins.b + slack;

        // function redefines itself as a closure
        get_popup_lr_offset = function ($p) {
            return {x: $p.outerWidth() + dx, y: $p.outerHeight() + dy};
        }

        return get_popup_lr_offset($popup);
    }

    var CURSORWIDTH = 12;

    $('.scatterplot').bind({
        mousedown: function (e) {
            e.stopPropagation();
            remove_popup(e);
            var offset = $(this).offset();
            var coords = {x: e.pageX - offset.left, y: e.pageY - offset.top};
            var target = e.target;
            var imgid = target.src.
                        replace(/^(https?:\/\/[^\/]+)?/, '').
                        replace(window.IMGBASE, '').
                        replace(/\.[^\.]+$/, '');
            var rows = get_popup_rows(imgid, coords);
            if (!rows.length) return;
            var inner = '';
            for (var i = 0; i < rows.length; ++i) inner += rows[i];
            var $popup = $('<div id="popup"><table>' + inner + '</table></div>').
                         appendTo('body');

            // x0 and y0 give the preferred offset for the popup,
            // barring conflicts with the current viewport's edges
            var x0 = e.pageX + CURSORWIDTH;
            var y0 = e.pageY;

            var lr_offset = get_popup_lr_offset($popup);
            var margins = get_popup_margins($popup);

            var $win = $(window);

            // l, r, t, and b give the x- (l, r) or y-coordinates (t,
            // b) for of the current viewport's left, right, top, and
            // bottom edges, respectively
            var l = $win.scrollLeft();
            var r = l + $win.width();
            var t = $win.scrollTop();
            var b = t + $win.height();

            // xl and xr give the x-offsets that would put the popup
            // up against the viewport's left and right edges,
            // respectively
            var xl = l + margins.l;
            var xr = r - lr_offset.x;

            // yt and yb give the y-offsets that would put the popup
            // up against the viewport's top and bottom edges,
            // respectively
            var yt = t + margins.t;
            var yb = b - lr_offset.y;

            // the expression below implements the following policy
            // (for the horizontal and vertical dimensions considered
            // separately):
            // - if the viewport is not wide|tall enough to fully
            //   contain the popup, position the popup against the
            //   viewport's left|top edge;
            // - otherwise, if positioning the popup at x0|y0 would
            //   cause it to extend beyond the viewport's right|bottom
            //   edge, then position it against the viewport's
            //   right|bottom edge instead;
            // - otherwise, position the popup at x0|y0.
            $popup.offset({left: Math.max(xl, Math.min(xr, x0)),
                           top:  Math.max(yt, Math.min(yb, y0))});
        },
    });
});
