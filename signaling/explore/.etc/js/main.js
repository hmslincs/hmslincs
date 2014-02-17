jQuery(document).ready(
    function ($) {

        var $sb = $('.sibling-browser');
        $sb.mouseenter(function() {
            var $sbl = $('.sibling-browser-list', this);
            var $sb = $(this);
            $sbl.show();
            if (sb_visible($sb)) {
                $sbl.css('bottom', '');
            } else {
                // FIXME: figure out why we need the extra +8
                $sbl.css('bottom', ($sb.height() + 8) + 'px');
            }
        });
        $sb.mouseleave(function() {
            $('.sibling-browser-list', this).hide();
        });

        var $hotspots = $('.lookup-table-hotspot');
        $hotspots.click(function() {
            var cell_class = $.grep(this.className.split(/\s+/), function(c) {
                return c.indexOf('cell-') === 0;
            })[0];
            var $popup = $('.lookup-table-popup.' + cell_class);
            $popup.dialog({
                resizable: false,
                show: 'blind',
                width: 'auto',
                height: 'auto',
                position:  {my: 'left', at: 'right', of: this},
            });
            
        });

        /*
          Turn specific image links into lightbox-style viewers. Any <a> element
          with the class "lightbox-link" will be converted. When clicked, the
          linked image will pop up in a centered, modal dialog box. This has a
          nice fallback behavior since the original markup is just a plain link
          to the file.
         */
        $lbl = $('a.lightbox-link');
        $lbl.click(function () {
            // Typical usage is to wrap a small image with a link to a larger
            // version. This grabs the wrapped image.
            var $orig_img = $(this).children('img');
            // Create the new img element dynamically outside the DOM.
            var $img = $('<img>');
            // Copy the href from the original link to the img's src.
            $img.attr('src', $(this).attr('href'));
            $img.load(function () {
                // Guard against the possibility the dialog was already closed.
                if ($.contains(document, this)) {
                    // Set width/height to auto and reset the position, to take
                    // into account the now-known image dimensions.
                    $img.dialog('option', {
                        position: {my: 'center', at: 'center', of: window},
                        width: 'auto',
                        height: 'auto',
                    });
                }
            });
            $img.dialog({
                modal: true,
                draggable: false,
                // Initialize the dimensions to match the wrapped image. This
                // will make the image appear smaller than the original due to
                // the dialog's "chrome" but it's a reasonable starting
                // point. The img load handler above will reset these anyway.
                width: $orig_img.width(),
                height: $orig_img.height(),
                // Leave a 5% margin to make sure the dialog isn't bigger than
                // the window.
                maxWidth: $(window).width() * .90,
                maxHeight: $(window).height() * .90,
                // Since our content is dynamically created on each link click,
                // we need to destroy the chrome elements or they will stay
                // around forever.
                close: function () { $(this).dialog('destroy') },
            });
            // Implement "click outside the dialog to close". This is normally
            // harder, but with modal dialogs we have the overlay element as a
            // convenient place to hang a click handler.
            $('.ui-widget-overlay').click(function () { $img.dialog('close') });
            // Prevent the original link click event from triggering navigation.
            return false;
        });

        function sb_visible($sb) {
            var $window = $(window);
            var $sbl = $sb.find('.sibling-browser-list');
            var sbl_bottom = ($sb.offset().top - $(window).scrollTop() +
                              $sb.height() + $sbl.height())
            var offset = $window.height() - sbl_bottom;
            return offset > 10;
        }
    }
);
