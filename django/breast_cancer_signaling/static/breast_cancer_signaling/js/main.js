define(['jquery', 'jqueryui'], function (jQuery, jqueryui) {

jQuery(document).ready(
    function ($) {

        var $sb = $('.sibling-browser');
        $sb.mouseenter(function() {
            var $sbl = $('.sibling-browser-list', this);
            var $sb = $(this);
            $sbl.show();
            if (!sb_visible_downward($sb)) {
		// If there's no room to display the list downward, display
		// upward from the pseudo-button instead by setting the bottom
		// coordinate to the height of the button.
		var offset = $sb.find('.pseudo-button').outerHeight();
                $sbl.css('bottom', offset + 'px');
            }
        });
        $sb.mouseleave(function() {
	    // Hide list and reset the upward display override.
            $('.sibling-browser-list', this).hide().css('bottom', '');
        });

        var $hotspots = $('.lookup-table-hotspot');
        $hotspots.click(function() {
            var cell_class = $.grep(this.className.split(/\s+/), function(c) {
                return c.indexOf('cell-') === 0;
            })[0];
            var $popup = $('.lookup-table-popup.' + cell_class);
            $popup.dialog({
                resizable: false,
                width: 'auto',
                height: 'auto',
                position: {my: 'left top', at: 'right top', of: this},
                open: function (event) { media_ondemand_load(event.target); }
            });
        });

        /*
          Turn specific image links into lightbox-style viewers. Any <a> element
          with the class "lightbox-link" will be converted. When clicked, the
          linked image will pop up in a centered, modal dialog box. This has a
          nice fallback behavior since the original markup is just a plain link
          to the file.
         */
        var $lbl = $('a.lightbox-link');
        $lbl.click(function () {
            // Typical usage is to wrap a small image with a link to a larger
            // version. This grabs the wrapped image.
            var $orig_img = $(this).children('img');
            // Create the new img element dynamically outside the DOM.
            var $img = $('<img class="lightbox">');
            // Copy the href from the original link to the img's src.
            $img.attr('src', $(this).attr('href'));
            // Set up some code to run after the new image is loaded and its
            // dimensions known.
            $img.load(function () {
                // Guard against the possibility the dialog was already closed.
                if ($.contains(document, this)) {
                    var img_width = $(this).prop('naturalWidth');
                    var img_height = $(this).prop('naturalHeight');
                    var win_width = $(window).width();
                    var win_height = $(window).height();
                    var dialog_width = 'auto', dialog_height = 'auto';
                    if (img_width !== undefined) {
                        // Is image aspect ratio wider than window's?
                        if (img_width / img_height > win_width / win_height) {
                            // If wider, use image width to set dialog
                            // width. Limit width to window width minus a margin.
                            dialog_width = Math.min(img_width, win_width * 0.95);
                        } else {
                            // Otherwise use height.
                            dialog_height = Math.min(img_height, win_height * 0.95);
                        }
                    } else {
                        // If img.naturalWidth is unsupported, just make the
                        // dialog fill most of the window.
                        //
                        // FIXME this ends up stretching the img, a div wrapping
                        // the img should fix it but that is probably a good
                        // idea anyway.
                        dialog_width = win_width * 0.90;
                        dialog_height = win_height * 0.90;
                    }
                    $(this).dialog('option', {
                        position: {my: 'center', at: 'center', of: window},
                        width: dialog_width,
                        height: dialog_height,
                    });
                }
            });
            $img.dialog({
                modal: true,
                draggable: false,
                resizable: false,
                // Initialize the dimensions to match the wrapped image. This is
                // just a reasonable starting point as the img load handler
                // above will reset them anyway.
                width: $orig_img.width(),
                height: $orig_img.height(),
                // Since our content is dynamically created on each link click,
                // we need to destroy the chrome elements on close or they will
                // stay around forever.
                close: function () { $(this).dialog('destroy'); }
            });
            // Implement "click outside the dialog to close". This is normally
            // harder, but with modal dialogs we have the overlay element as a
            // convenient place to hang a click handler.
            $('.ui-widget-overlay').click(function () { $img.dialog('close'); });
            // Prevent the original link click event from triggering navigation.
            return false;
        });

        function sb_visible_downward($sb) {
	    /*
	      Determine if sibling-browser-list would be fully visible if it
	      were to display downward.
	    */
            var $window = $(window);
            var $sbl = $sb.find('.sibling-browser-list');
            var sbl_bottom = ($sbl.offset().top + $sbl.outerHeight() -
			      $(window).scrollTop());
            var offset = $window.height() - sbl_bottom;
            return offset > 0;
        }

        function media_ondemand_load(target) {
            /*
              Implement semi-semantic lazy loading of media elements.
              =====

              target: DOM node or jQuery selector denoting container within
                which to perform loading.

              This page has many initially hidden jquery-ui dialogs containing
              <img> tags, but we want the browser to put off fetching their
              content until it's actually displayed. The typical img trick of
              converting it to a css background is undesirable as the image is
              the actual content.

              Here we use an idiom in which we include the media tag as usual
              except for stripping off the src attribute. We then put an <a> tag
              with a class of "media-ondemand" immediately preceeding the media
              tag, and set its href attribute to the value of the stripped src
              attribute from the media tag. Here on dialog open we reverse that
              transformation, leaving only fully functional media elements
              behind.
            */
            $('a.media-ondemand', target).each(function () {
                var $link = $(this);
                var $media = $link.next();
                // Copy the <a>'s href to the media's src.
                $media.attr('src', $link.attr('href'));
                // Delete the <a> entirely.
                $link.remove();
            });
        }
    }
);

});
