// JavaScript Document

var defaultSearchText = "SEARCH";

jQuery(function($){
	// Setup search form
	if($('#searchform input#s').val() == "") {
		$('#searchform input#s').val(defaultSearchText);
	}
	
	$('#searchform input#s').focus(function(){
		if($('#searchform input#s').val() == defaultSearchText) {
			$('#searchform input#s').val("");
		}
		$(this).addClass('focused');
		$(this).select();
	});
	$('#searchform input#s').blur(function(){
		if($('#searchform input#s').val() == "") {
			$('#searchform input#s').val(defaultSearchText);
		}
		$(this).removeClass('focused');
	});
	
	// Adjust images (get images to fit in content area)
	var imgs = $('#content img');
	var container = $('#content');
	var maxWidth = container.width();	
	for (i=0; i<imgs.length; i++) {
		var img = $(imgs[i]);
		if (img.width() > (maxWidth - 10)) {
			var ratio = img.height() / img.width();
			img.width(maxWidth - 10);			// Allow for caption borders.
			img.height((maxWidth - 10) * ratio);
			var pars = img.parents();
			
			for (j=0;j<pars.length;j++) {
				var parent = $(pars[j]);
				if (parent.attr('id') == 'content') break;	// Reached the top.
				if (parent.width() > maxWidth) {
					parent.width(maxWidth);
				}
			}
			
		}
	}
	
	// Add bg header image, if not on home.
	var numImages = 2;		// How many total images we have available
									// Note that associated bg styles are required as well...
	if ($("body.home").length == 0) {
		var imgIndex = Math.ceil(Math.random() * numImages);
		var styleName = "header" + imgIndex;
		$('#pagebody').addClass(styleName);
	} else {
		// Otherwise, make visible image rotator
		$('#cimy_div_id').show();
	}
});