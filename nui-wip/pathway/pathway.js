jQuery(document).ready(function ($) {
    var touched = false;
    $('#pathwaymap > area').mouseenter(function (e) {
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

    $('#pathwaymap > area').each(function(idx, elt) {
	var $popup = get_popup(elt);
	if ($popup !== null) {
	    var target_bounds = area_bounds(elt);
	    var offset = {left: target_bounds.right + 30, top: target_bounds.top};
	    $popup.offset(offset);
	}
    });

    /* Return a jQuery object for the popup corresponding to an area element */
    function get_popup(area) {
	return area.id !== null ? $('#signature-' + area.id) : null;
    }

    /* Return the left/right/top/bottom of an area element */
    function area_bounds(area) {
	var x = [], y = [];
	var coords = area.coords.split(',');
	for (var i = 0; i < coords.length / 2; ++i) {
	    x[i] = parseInt(coords[i*2]);
	    y[i] = parseInt(coords[i*2+1]);
	}
	function cmp(a,b) { return a-b }
	x.sort(cmp);
	y.sort(cmp);
	return {left: x[0], right: x[x.length-1],
		top: y[0], bottom: y[y.length-1]};
    }
});
