jQuery(document).ready(
    function ($) {

        var $sb = $('.sibling-browser');
        $sb.mouseenter(function() {
            $('.sibling-browser-list', this).show();
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

    }
);
