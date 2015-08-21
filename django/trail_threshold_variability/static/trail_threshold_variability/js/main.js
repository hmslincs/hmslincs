define(['jquery', 'jqueryui'], function (jQuery, jqueryui) {

jQuery(document).ready(
    function ($) {

        var $hotspots = $('.lookup-table-hotspot');
        $hotspots.click(function() {
            var cell_class = $.grep(this.className.split(/\s+/), function(c) {
                return c.indexOf('cell-') === 0;
            })[0];
            var $popup = $('.lookup-table-popup.' + cell_class);
            $popup.dialog({
                resizable: false,
                width: 939,
                open: function (event) { media_ondemand_load(event.target); }
            });
        });

        // Quickly disable accessibility links.
        $hotspots.children('a').removeAttr('href');

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
