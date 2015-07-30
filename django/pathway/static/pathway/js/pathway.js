define(['jquery'], function (jQuery) {

jQuery(document).ready(function ($) {

    /*
      The behavior for hiding and displaying popups is as follows:

      A. 1. Hovering over a protein hotspot on the pathway will display the
            corresponding popup and hide any other popups.
         2. When the pointer leaves the protein, a timer is set to hide the
            popup in 1 second.
         3. If the same protein is hovered again before its popup gets hidden,
            be sure to cancel the timer.
      B. 1. Hovering over a popup disables the timer for hiding it.
         2. When the pointer leaves the popup, set the same 1 second hide timer
            from A.2.
      C. 1. Any clicks (from frustration) on the pathway outside hotspots or
            popups will hide all popups.
     */

    var hide_timers = {};

    $('.pathway-hotspot').bind({
        mouseenter: function (e) {
            var $popup = get_popup_for_hotspot(e.target);
            cancel_hide_popup($popup); // A.3
            hide_popups(); // A.1
            $popup.show(); // A.1
        },
        mouseleave: function (e) {
            var $popup = get_popup_for_hotspot(e.target);
            schedule_hide_popup($popup); // A.2
        }
    });

    $('.signature-popup').bind({
        mouseenter: function (e) {
            var $popup = get_parent_popup(e.target);
            cancel_hide_popup($popup); // B.1
        },
        mouseleave: function (e) {
            var $popup = get_parent_popup(e.target);
            schedule_hide_popup($popup); // B.2
        }
    });

    $('#pathway-container').click(function (e) {
        hide_popups(); // C.1
    });

    $('.pathway-hotspot').each(function(idx, elt) {
        var $popup = get_popup_for_hotspot(elt);
        if ($popup.length) {
            $elt = $(elt)
            var target_pos = $elt.position()
            var left = target_pos.left + $elt.width() + 15;
            var top = target_pos.top;
	    // move popup left of hotspot if it would extend off the right side of the map
	    if (left + $popup.width() >= $('#pathway-container').width()) {
		left = target_pos.left - $popup.width() - 15;
	    }
	    // move popup above hotspot if it's very close to the bottom
	    if (top >= $('#pathway-container').height() - 100) {
		top = target_pos.top - $popup.height() + 10;
	    }
            var offset = {'left': left, 'top': top};
            $popup.offset(offset);
        }
    });

    /* Return a jQuery object for the popup corresponding to a 'hotspot' div */
    function get_popup_for_hotspot(elt) {
        return $('#signature-' + elt.id);
    }

    function get_parent_popup(elt) {
        while (!elt.id.match('^signature-') && elt.parentNode !== null) {
            elt = elt.parentNode;
        }
        return elt.parentNode === null ? null : $(elt);
    }

    function hide_popups() {
        $.each(hide_timers, function(id, timer) {
            var $popup = $('#' + id);
            cancel_hide_popup($popup);
            hide_popup($popup);
        });
    }

    function hide_popup($popup) {
        $popup.hide();
    }

    function schedule_hide_popup($popup) {
        if ($popup.length) {
            hide_timers[$popup.attr('id')] = setTimeout(
                function () { hide_popup($popup); },
                1000
            );
        }
    }

    function cancel_hide_popup($popup) {
        var id = $popup.attr('id');
        if (id in hide_timers) {
            clearTimeout(hide_timers[id]);
            delete hide_timers[id];
        }
    }

});

});
