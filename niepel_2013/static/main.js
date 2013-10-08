jQuery(document).ready(
    function ($) {

        var $sb = $('.sibling-browser');
        var $sb_list = $sb.find('.sibling-browser-list');
        $sb.mouseenter(function() {
            $sb_list.stop().slideDown(400, function() {
                $(this).css('overflow','visible');
            });
        });
        $sb.mouseleave(function() {
            $sb_list.stop().slideUp(400);
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

    }
);
