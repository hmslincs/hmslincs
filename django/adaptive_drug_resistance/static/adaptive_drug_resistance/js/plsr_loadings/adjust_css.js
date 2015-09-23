'use strict';
define(    [  'jquery', './config' ],
    function ( $      ,  cfg ) {

        var $left_panel = $( '#scatterplots-content .left-panel' )
        ,   left_panel_top_padding = cfg.info_box_height;

        return function ( data ) {
            // doing with JS what should be done with, eg, SASS...
            $( '.xy-box > div, .md-box > div' ).css( 'height',
                                                     cfg.info_box_height );

            $left_panel.css( 'padding-top', left_panel_top_padding + 'px' );


            //------------------------------------------------------------------

            ( function () {
                  var n_cols = Math.ceil( data.length / cfg.n_rows )
                  ,   $parent = $( '.svg-stage' )
                  ,   $svg_wrappers = $parent.find( '.svg-wrapper' )
                  ;

                  $svg_wrappers.css( 'margin', cfg.plot_margin );
                  // $parent.width( ( cfg.width + 2 * cfg.plot_margin ) * n_cols );
              } )();

            //------------------------------------------------------------------

        };
    }
);
