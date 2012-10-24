jQuery(document).ready(function ($) {
    var touched = false;
    $('.pathway-target').mouseenter(function (e) {
	var $popup = get_popup(e.target);
	if ($popup !== null) {
	    $('.signature-popup').hide();
	    $popup.show();
	}
    });
    $('.signature-popup').mouseenter(function () {
	touched = true;
    });
    $('.signature-popup').mouseleave(function () {
	if (touched) {
	    $('.signature-popup').hide();
	    touched = false;
	}
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

});
