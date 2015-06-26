'use strict';
define( [ 'jquery' ],
function ( $ ) {

    // default configuration

    var default_config =
        {
            _: null

          , data_path: window.__STATIC_URL__ + 'data/vips/input.json'

          , x_axis_label: 'PC1_laodings'
          , y_axis_label: 'PC2_laodings'

          , point_style: {}
          , point_shape: 'triangle-down'

          , point_to_target_ratio: 1.5
          , hr_to_size: {
                          1: 1,
                          5: 1.5,
                          10: 1.75,
                          24: 2,
                          48: 2.3,
                          v: 2.15
                        }

          , n_rows: 2

          // css-related nonsense
          , right_panel_pseudo_margin_left: 5
          , plot_margin: 5
          , info_box_height: 20

          , width: null
          , height: null

          , meta: { scale: 1 }

          // scale-dependent defaults

          , size: 400

          , inner_margin: {
                              top: 10
                            , bottom: 40
                          }

          , outer_margin: {
                              top: 30
                            , right: 0
                            , bottom: 0
                            , left: 0
                          }
        };

    var config = {};

    $.extend( true, config, default_config, { _: {} } );

    config._.update_config = function ( custom_config ) {

        // ---------------------------------------------------------------------
        if ( custom_config ) {
            for ( var p in custom_config ) {
                if ( p === '_' ) continue;
                config[ p ] = custom_config[ p ];
            }
        }

        // ---------------------------------------------------------------------
        var size = ( config.size || config.width || config.height );

        config.size = config.size || size;
        config.width = config.width || size;
        config.height = config.height || size;

        config.target_size = config.target_size || size / 100;

        // ---------------------------------------------------------------------
        var scale = config.meta.scale;

        config.size *= scale;
        config.width *= scale;
        config.height *= scale;
        config.target_size *= scale;

        // ---------------------------------------------------------------------
        delete config.meta;
        delete config._.update_config;
    }

    config._.default_config = default_config;

    return config;
}

);
