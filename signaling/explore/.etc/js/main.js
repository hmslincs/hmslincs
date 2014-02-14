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
