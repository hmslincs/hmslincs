jQuery(document).ready(function ($) {

    var touched = false;

    $('.pathway-target').mouseenter(function (e) {
	var $popup = get_popup(e.target);
	if (!touched && $popup !== null) {
            hide_popups();
	    $popup.show();
	}
    });
    $('.pathway-target').click(function (e) {
	var $popup = get_popup(e.target);
        if ($popup !== null) {
            hide_popups();
	    $popup.show();
	}
        return false;
    });

    $('.signature-popup').mouseenter(function () {
       touched = true;
    });

    /*
    $('.closebutton').click(function (e) {
	var $popup = get_popup(e.target.parentNode);
	if ($popup !== null) {
            hide_popups();
	}
    });
    */

    $('#pathway-container').click(function (e) {
        hide_popups();
    });

    $('.pathway-target').each(function(idx, elt) {
	var $popup = get_popup(elt);
	if ($popup !== null) {
            $elt = $(elt)
            var target_pos = $elt.position()
            var left = target_pos.left + $elt.width() + 15;
            var top = target_pos.top;
	    var offset = {'left': left, 'top': top};
	    $popup.offset(offset);
	}
    });

    /* Return a jQuery object for the popup corresponding to an area element */
    function get_popup(area) {
	return area.id !== null ? $('#signature-' + area.id) : null;
    }

    function hide_popups() {
        $('.signature-popup').hide();
        touched = false;
    }

});
