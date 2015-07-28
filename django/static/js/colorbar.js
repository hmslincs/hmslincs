'use strict';
define(     [ 'd3', 'utils' ],
function ( d3 ,  u ) {

    function colorbar () {

        function scale_range ( H, m, M, t0, tn, h0, h1, n ) {

            var h = h0 + h1  // "assert h < H"
            ,   r = M - m
            ,   ninv = 1/n
            ,   i
            ,   offsets_lengths
            ,   ol
            ,   min = Infinity
            ,   ret
            ;

            function fl ( v ) {
                return n * Math.floor( Math.abs( v ) * ninv );
            }

            offsets_lengths =
                [
                  { offset:  0, length: fl(   H                              ) },
                  { offset: h0, length: fl( ( H - h0 ) * ( r / ( M  - t0 ) ) ) },
                  { offset:  0, length: fl( ( H - h1 ) * ( r / ( tn - m  ) ) ) },
                  { offset: h0, length: fl( ( H - h  ) * ( r / ( tn - t0 ) ) ) }
                ]
            ;

            for ( i = 0; i < offsets_lengths.length; ++i ) {
                ol = offsets_lengths[ i ];
                if ( min > ol.length ) {
                    min = ol.length;
                    ret = [ ol.offset, ol.offset + ol.length ];
                }
            }

            return ret;
        }

        // -----------------------------------------------------------------
        // closurevars
        var _

        ,   UNSPECIFIED = {}

        ,   TICKS_LENGTH = 5
        ,   TICKS_MARGIN = 2
        ,   BAR_MARGIN = 5

        ,   COLOR_SCALE = {
                stepped:    d3.scale
                              .linear()
                              .domain( [ 0, 1 ] )
                              .range( [ 'white', 'black' ] )

              , continuous: d3.scale
                              .linear()
                              .domain( [ 0, 0.5, 1 ] )
                              // .range( [ 'white', 'black' ] )
                              .range( [ 'red', 'white', 'blue' ] )
            }

        ,   color_scale = UNSPECIFIED
        ,   stepped = false
        ,   values = UNSPECIFIED
        ,   orientation = 'vertical'

        ,   height = 200
        ,   width = 12
        // ,   font_size = 13
        ;

        function bar ( selection ) {

            selection.each( function ( data ) {
                if ( color_scale === UNSPECIFIED ) {
                    color_scale = COLOR_SCALE[ stepped ? 'stepped' : 'continuous' ];
                }

                var _
                ,   horizontal = orientation === 'horizontal'
                ,   domain = color_scale.domain()

                ,   ticks_length
                ,   ticks_margin

                ,   bar_margin

                ,   vertical = ! horizontal
                ,   continuous = ! stepped

                ,   position_scale = d3.scale
                                       .linear()
                                       .domain( d3.extent( domain ) )

                // ,   t0 = Math.min.apply( null, stepped ? domain : values )

                // ,   tn = Math.max.apply( null, stepped ? domain : values )

                // ,   m  = Math.min.apply( null, domain )
                // ,   M  = Math.max.apply( null, domain )

                // ,   h0
                // ,   h1
                // ;

                // h0 = Math.ceil ( d3.select( 'g:first-child > text' )
                //                    .node().getBBox().height/2 );
                // h1 = Math.floor( d3.select( 'g:last-child > text' )
                //                    .node().getBBox().height/2 );
                // range = scale_range( height, m, M, t0, tn, h0, h1, n );

                ,   range
                ,   n
                ,   H
                ;

                if ( values === UNSPECIFIED ) {
                    values = position_scale.ticks( 5 );
                    // if ( stepped ) {
                    //     values = [ 0, 0.25, 0.5, 0.75, 1 ];
                    // }
                }

                if ( stepped ) {
                    ticks_length = ticks_margin = 0;
                    bar_margin = BAR_MARGIN;

                    n = values.length;
                    H = height * ( n - 1 )/n;

                    position_scale.domain( d3.extent( values ) );
                }
                else {
                    ticks_length = TICKS_LENGTH;
                    ticks_margin = TICKS_MARGIN;
                    bar_margin = 0;
                    H = height;
                }

                position_scale.range( horizontal ? [ 0, H ] : [ H, 0 ] );

                var $parent = d3.select( this );

                if ( ! ( this instanceof SVGElement ) ) {
                    $parent = $parent.append( 'svg' );
                }

                var _
                ,   $top_g = $parent.selectAll( 'g.colorbar' )
                                  .data( [ data ] ).enter()
                                    .append( 'g' )
                                    .attr( 'class', 'colorbar' )

                ,   $rot = $top_g.append( 'g' )
                ,   $tra = $rot.append( 'g' )
                ;

                var legend_labels = $tra.append( 'g' )
                                          .attr( 'class', 'legend-labels' )
                                          .selectAll( 'g' )
                                          .data( values ).enter()
                                        .append( 'g' )
                ;

                legend_labels
                           .append( 'text' )
                             .text( String )
                             .attr( { 'text-anchor': 'end',
                                      'line-height': 'normal',
                                      'dominant-baseline': 'middle' } )
                ;

                var _
                ,   labels_width =
                        Math.max.apply( null,
                                        legend_labels[ 0 ].map( function ( n ) {
                                            return n.getBBox().width;
                                        } ) )
                ,   labels_offset = [ labels_width, 0 ]
                ;

                if ( continuous ) {
                    var legend_ticks = $tra.append( 'g' )
                                           .attr( 'class', 'legend-ticks' )
                                           .attr( 'transform',
                                                  u.translate( labels_width +
                                                               ticks_margin, 0 ) )
                                           .selectAll( 'g' )
                                           .data( values ).enter()
                                           .append( 'g' )
                    ;

                    legend_ticks
                        .append( 'line' )
                        .attr( { x0: 0, x1: ticks_length, y1: 0, y2: 0 } )
                    ;
                }

                var tile_data
                ,   tile_height
                ,   step
                ;

                function stepper ( dy ) {
                    return function ( d ) {
                               return u.translate( 0, position_scale( d ) + dy );
                           };
                }

                step = stepper( 0 );

                if ( stepped ) {
                    tile_data = values;
                    tile_height = height / n;
                    legend_labels.attr( 'transform', stepper( tile_height / 2 ) );
                }
                else {
                    tile_data = d3.range( height + 1 )
                                  .map( position_scale.invert );
                    tile_height = 1;
                    legend_ticks.attr( 'transform', step );
                    legend_labels.attr( 'transform', step );
                }

                var $tiles_g = $tra.append('g')

                                     .attr('class', 'legend-tiles')

                                     .attr( 'transform',
                                            u.translate( labels_width +
                                                         ticks_margin +
                                                         ticks_length +
                                                         bar_margin, 0 ) );

                var _
                ,   $tiles_backdrop = $tiles_g.append( 'rect' )
                                              .attr( 'class', 'tiles-backdrop' )
                ,   legend_tiles =
                    $tiles_g.selectAll( 'g' )
                            .data( tile_data ).enter()
                          .append( 'g' )
                            .attr( 'transform', step )
                ,   $tiles
                ,   temp_width = 1
                ;

                $tra.select( '.legend-labels' )
                      .attr( 'transform',
                             u.translate.apply( null, labels_offset ) )
                ;

                $tiles = legend_tiles.append( 'rect' )
                                       .attr( 'height', tile_height )
                                       .style( 'fill', color_scale );

                $tiles.attr( 'width', stepped ? width - 2 : width );

                var cb_bbox = $top_g.select( '.legend-tiles' ).node().getBBox();

                $tiles_backdrop.attr(
                                      {
                                          width: cb_bbox.width
                                        , height: cb_bbox.height
                                        , y: -0.5
                                      }
                                    )
                               .attr( { fill: 'none' } )
                ;

                if ( horizontal ) {
                    var angle = -90;
                    $rot.attr( 'transform',
                               u.translate( 0, $tra.node().getBBox().width )
                               + ' ' +
                               u.rotate( angle )
                             )
                    ;
                }

                $top_g.attr( 'transform',
                             u.translate( 0, -$top_g.node().getBBox().y ) );

            } ); // selection.each( function ( data ) {

        } // function bar ( selection ) {

        // -----------------------------------------------------------------
        // accessors

        bar.scale = function ( _ ) {
            if ( !arguments.length ) return color_scale;
            color_scale = _;
            return bar;
        };

        bar.stepped = function ( _ ) {
            if ( !arguments.length ) return stepped;
            stepped = _;
            return bar;
        };

        bar.values = function ( _ ) {
            if ( !arguments.length ) return values;
            values = _;
            return bar;
        };

        bar.orientation = function ( _ ) {
            if ( !arguments.length ) return orientation;
            orientation = _;
            return bar;
        };

        // bar.font_size = function ( _ ) {
        //     if ( !arguments.length ) return font_size;
        //     font_size = _;
        //     return bar;
        // };

        bar.width = function ( _ ) {
            if ( !arguments.length ) return width;
            width = _;
            return bar;
        };

        bar.height = function ( _ ) {
            if ( !arguments.length ) return height;
            height = _;
            return bar;
        };

        // -----------------------------------------------------------------

        return bar;

    } // function colorbar () {

    return colorbar;

}

);
