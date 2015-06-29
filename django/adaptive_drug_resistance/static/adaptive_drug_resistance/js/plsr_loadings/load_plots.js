'use strict';
define(    [  'jquery', 'd3', 'underscore', 'config', 'common', 'hmslincs/utils', 'hmslincs/scatterplot' ],
    function ( $      ,  d3 ,  _          ,  cfg    ,  c      ,  u              ,  sp ) {

        function rank ( arr ) {
            return arr.map( function ( e, i ) { return [ e, i ] } )
                      .sort( d3.descending )
                      .map( function ( e, j ) { return e.concat( [ j ] ) } )
                      .sort( function ( a, b ) { return a[ 1 ] - b[ 1 ] } )
                      .map( function ( e ) { return e[ 0 ] === null ? null : e[ 2 ] } );
        }

        return function ( data ) {

            var width = cfg.width
            ,   height = cfg.height

            ,   target_size = cfg.target_size

            ,   x_axis_label = cfg.x_axis_label
            ,   y_axis_label = cfg.y_axis_label

            ,   xval = function ( d ) { return +d[ x_axis_label ] }
            ,   yval = function ( d ) { return +d[ y_axis_label ] }

            ,   isnull = function ( d ) { return    d[ x_axis_label ] === null
                                                 || d[ y_axis_label ] === null }
            ,   plot_range = ( function ( data ) {
                                   var xys = data.map( function ( d, i ) {
                                                           return [ xval.call( data, d, i ),
                                                                    yval.call( data, d, i ) ];
                                                       } )
                                   ;
                                   return { x: d3.extent( xys, u.first ),
                                            y: d3.extent( xys, u.second ) };

                                   // ,   rng = d3.extent( d3.merge( d3.transpose( xys ) ) )
                                   // ;
                                   // return { x: rng, y: rng };

                               } )( c.flatten( data ) )

            ,   symbol = ( function () {
                               var memo = d3.map()
                               ,   scale = cfg.point_to_target_ratio * target_size
                               ;
                               Object.keys( cfg.hr_to_size ).forEach( function ( k ) {
                                   var size = scale * cfg.hr_to_size[ k ]
                                   ,   type = k === 'v' ? 'circle' : cfg.point_shape
                                   ;

                                   memo.set( k, d3.svg.symbol()
                                                      .type( type )
                                                      .size( size * size ) )
                                   ;
                               } )
                               ;

                               function symbol ( d, i ) {
                                   var key = d[ 'RPPA_measurement' ] === 'Viability'
                                                 ? 'v'
                                                 : c.parse_timepoint( d[ 'Timepoint_hr' ] )
                                   ,   sym = memo.get( key )
                                   ;

                                   return sym( d, i );
                               }

                               return symbol;
                           } )()

            ,   $stage = d3.select( '.global' )
                           .selectAll( '.svg-stage.offstage' )
                           .data( [ data ] )
                           .enter()
                           .append( 'div' )
                           .classed( { 'svg-stage': true,
                                       'off-stage': true } )

            ,   $svg_wrappers = $stage.selectAll( '.svg-wrapper' )
                                      .data( data )
                                    .enter()
                                      .append( 'div' )
                                      .attr( 'class', 'svg-wrapper' )

            ,   $svg = $svg_wrappers.append( 'svg' )
                                    .attr( 'width', width )
                                    .attr( 'height', cfg.outer_margin.top + height * 2 )
            ;

            $svg.each( function ( d0 ) {

                  var cell_line = d0.value,
                      w_wo = d0.data,
                      $svg = d3.select( this );

                  $svg.append( 'text' )
                      .text( cell_line )
                      .style( 'text-anchor', 'middle' )
                      .attr( 'class', 'svg-title' )
                      .attr( 'y', cfg.outer_margin.top / 2 )
                      .attr( 'dy', '0.7ex' )
                      .attr( 'x', width / 2 );

                  $svg.selectAll( 'g' )
                      .data( w_wo.map( function ( d ) { return c.flatten( d.data ) } ) )
                    .enter().append( 'g' )
                      .attr(
                             'transform',
                             function ( _, i ) {
                                 return u.translate( 0, cfg.outer_margin.top + i * height );
                             }
                           )
                      .each( function ( _, i ) {

                                 var plot_title = w_wo[ i ].value
                                 ,   spch = sp().width( width )
                                                .height( height )
                                                .margin( cfg.inner_margin )
                                                .plotRange( plot_range )
                                                .pointStyle( { symbol: symbol } )
                                                .axisLabel( { x: x_axis_label,
                                                              y: y_axis_label } )
                                                .plotTitle( plot_title )
                                                .x( xval )
                                                .y( yval )
                                 ,   $parent = d3.select( this )
                                 ;

                                 spch( $parent );
                             } );
              } );

            var $points =
            $stage

                .selectAll( '.scatterplot' )
                    .each( function () {
                               var invert_x = this.invert_x
                               ,   invert_y = this.invert_y
                               ,   g = d3.select( this )
                                         .selectAll( '.plot-region' )
                                         .node()
                               ;

                               g.invert_xy = function ( xy ) {
                                                 return [ invert_x( xy[ 0 ] ),
                                                          invert_y( xy[ 1 ] ) ];
                                             };
                           }
                         )

                .selectAll( '.point-set' )
                    .each( function ( dd ) {
                               var xys = dd.map( function ( d ) {
                                                     return [ d[ x_axis_label ],
                                                              d[ y_axis_label ] ]
                                                 } )
                               ,   x_ranks = rank( xys.map( u.first ) )
                               ,   y_ranks = rank( xys.map( u.second ) )
                               ;

                               dd.forEach( function ( e, i ) {
                                   e[ 'x_rank' ] = x_ranks[ i ];
                                   e[ 'y_rank' ] = y_ranks[ i ];
                               } );
                           }
                         )

                .selectAll( '.point' )

                .each( function ( d ) {
                           if ( d[ 'RPPA_measurement' ] === 'Viability' ) {
                               d3.select( this ).classed( 'viability', true );
                           }
                       } )

                // this filter has a side effect, so that henceforth
                // the same selection can be obtained with the
                // selector ':not(.null)'

                .filter( function ( d ) {
                             if ( isnull( d ) ) {
                                 d3.select( this ).classed( 'null', true );
                                 return false;
                             }
                             return true;
                         } )
            ;

            $points.selectAll( 'path' )
                   .style( cfg.point_style )
            ;

            $points.append( 'g' )
                   .attr( 'class', 'target' )
                   .each( function () {
                              this.plot_region_rect =
                                  $( this ).closest( '.plot-region' )
                                           .find( 'rect' )
                                           .get( 0 );
                          } )
                   .append( 'path' )
                   .attr( 'd', d3.svg.symbol().size( target_size * target_size ) )
                   .each( function () {
                              this.plot_region_rect = this.parentNode.plot_region_rect;
                          } )
            ;

            return $svg;

        };

    }

);
