jQuery(document).ready(
    function ($) {

        function cell_name(popup_elt) {
            var matches = $.map(popup_elt.classList, function (c, i) {
                var filtered = c.replace(/^cell-/, '');
                return filtered !== c ? filtered : null;
            });
            return matches[0];
        }

        var $sb = $('.sibling-browser');
        var $sb_list = $sb.find('.sibling-browser-list');
        $sb.mouseenter(function() { $sb_list.stop().slideDown(); });
        $sb.mouseleave(function() { $sb_list.stop().slideUp(); });

        var $hotspots = $('.lookup-table-hotspot');
        $hotspots.click(function() {
            var cell_class = $.grep(this.classList, function(c) {
                return c.indexOf('cell-') === 0;
            })[0];
            var $popup = $('.lookup-table-popup.' + cell_class);
            $popup.dialog({
                resizable: false,
                show: 'blind',
                position:  {my: 'left', at: 'right', of: this},
            });
            
        });

    }
);
