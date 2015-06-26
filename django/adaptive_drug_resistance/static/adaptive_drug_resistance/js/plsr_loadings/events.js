'use strict';
define( [ 'jquery', 'd3', 'hmslincs/utils', 'common', 'hmslincs/colorserver'  ],
function ( $      ,  d3 ,  u              ,  c      ,  color_server ) {

    var fmtxy = d3.format( '.1f' )

    ,   dispatch = d3.dispatch(
                                  'fg_focus'
                                , 'fg_blur'
                                , 'fg_pick'
                              )
    ;

    var events = {

        dispatch: dispatch,

        init: function () {

            var dispatch = events.dispatch

            ,   cl_key = 'Cell_line'
            ,   fg_key = 'RPPA_measurement'
            ,   tp_key = 'Timepoint_hr'

            ,   picker = ( function () {
                               var p = d3.map();
                               d3.selectAll( '.track-container' )
                                 .each( function () {
                                            var $this = d3.select( this );
                                            p.set( $this.select( '.title' ).text(), $this );
                                        } );
                               return p;
                           } )()
            ,   $fg_picker = picker.get( fg_key )
            ,   $fg_lis = $fg_picker.selectAll( 'li' )
            ,   $fg_reset = $fg_picker.select( '.reset' )


            ,   $cl_picker = picker.get( cl_key )
            ,   $cl_lis = $cl_picker.selectAll( 'li' )
            ,   $cl_reset = $cl_picker.select( '.reset' )

            ,   $points = null
            ,   $targets = d3.selectAll( '.point-set' )
                             .selectAll( '.point' )
                             .filter( ':not(.null)' )
                             .selectAll( '.target' )

            ,   $xy_box = d3.select( '.xy-box' )
            ,   $xy = $xy_box.selectAll( 'span' )

            ,   point_md = function ( d, i ) {
                               return [ i,
                                        d[ fg_key ], d[ tp_key ],
                                        d[ 'x_rank' ], d[ 'y_rank' ] ];
                           }

            ,   $md_box = d3.select( '.md-box' )
            ,   $md = $md_box.selectAll( 'span' )

            ,   color_class_prefix = 'c-'

            ,   strip = ( function ( pfx ) {
                              var regex = new RegExp( '^' + pfx + '\\d+$' );
                              return function () {
                                         var cl = this.classList;
                                         u.to_array( cl )
                                          .filter( function ( c ) { return regex.test( c ) } )
                                          .forEach( function ( c ) { cl.remove( c ); } );
                                     };
                          } )( color_class_prefix )

            ,   ncolors = d3.select( '.track-container.rppa-measurement' )
                            .selectAll( 'li' )
                            .size() - 1

            ,   cs = color_server().prefix( color_class_prefix )
                                   .size( ncolors )

            ,   stage = ( function ( main, back ) {
                              var $stage = d3.select( main )
                              ,   selector = '.svg-wrapper'
                              ,   update_points =
                                        function () {
                                            $points = $stage.selectAll( '.point-set' )
                                                            .selectAll( '.point' )
                                                            .filter( ':not(.null)' );

                                            cs.reset();
                                            $fg_lis.filter( '.li-picked' )
                                                   .each( function ( d ) {
                                                       dispatch.fg_focus( d );
                                                       dispatch.fg_pick( d );
                                                   } )
                                        }
                              ,   _mv = function ( n, from, to ) {
                                            $( n ).detach( from ).appendTo( to );
                                            update_points();
                                        }
                              ,   _up = function ( cl, from, to ) {
                                            var node = d3.select( from )
                                                         .selectAll( selector )
                                                         .filter( function ( d ) {
                                                                      return d.value == cl;
                                                                  } )
                                                         .node();

                                            _mv( node, from, to );
                                        }
                              ,   _dn = function ( cl, from, to ) { _up( cl, to, from ) }
                              ;

                              return {
                                  update_points: update_points
                                  ,

                                  show_for: function ( cl, show ) {
                                                ( show ? _up : _dn )( cl, back, main );
                                            }
                                  ,

                                  clear_main: function  () {
                                                  d3.select( main )
                                                    .selectAll( selector )
                                                    .each( function () {
                                                               _mv( this, main, back );
                                                           } );
                                              }
                              }

                          } )( '#main-stage', '.svg-stage.off-stage' )
            ;

            function fg_reset () {
                d3.selectAll( '.point-set .point' )
                  .attr( 'class', null )
                  .classed( 'point', true )
                ;

                $fg_lis.each( strip )
                       .classed( { 'li-focus': false,
                                   'li-picked': false } )
                ;

                cs.reset();
                $fg_reset.attr( 'disabled', 'disabled' );
            }

            // -----------------------------------------------------------------

            stage.update_points();

            $cl_lis
                .on( 'mouseenter',
                     function ( cl ) {
                         d3.select( this )
                           .classed( { 'cl-focus': true, 'li-focus': true } )
                     } )
                .on( 'mouseleave',
                     function ( cl ) {
                         d3.select( this )
                           .classed( { 'cl-focus': false, 'li-focus': false } )
                     } )
                .on( 'click',
                     function ( cl ) {
                         var $this = d3.select( this )
                         ,   show = ! $this.classed( 'li-picked' )
                         ;

                         stage.show_for( cl, show );

                         $this.classed( { 'cl-picked': show, 'li-picked': show } );

                         var no_picks = $cl_lis.filter( '.li-picked' ).empty();

                         $cl_reset.attr( 'disabled', no_picks ? 'disabled' : null );
                         // $fg_picker.style( 'visibility',
                         //                   no_picks ? 'hidden' : 'visible' );
                     } )
            ;


            $cl_reset
                .on( 'click',
                     function ( d ) {
                         $cl_lis.attr( 'class', 'item' );
                         $cl_reset.attr( 'disabled', 'disabled' );
                         stage.clear_main();
                     } )
            ;


            $fg_lis
                .on( 'mouseenter', function ( d ) {
                    dispatch.fg_focus( d );
                } )
                .on( 'mouseleave', function ( d ) {
                    dispatch.fg_blur( d );
                } )
                .on( 'click', function ( d ) {
                    dispatch.fg_focus( d );
                    dispatch.fg_pick( d );
                } )
            ;

            $fg_reset.on( 'click', fg_reset );

            $targets
                .on( 'mouseenter',
                     function ( d, _, j ) {
                         $md.data( point_md( d, j ) )
                            .html( u.identity );
                         $md_box.style( 'visibility', 'visible' );

                         dispatch.fg_focus( d[ fg_key ] );
                     } )
                .on( 'mouseleave',
                     function ( d ) {
                         $md_box.style( 'visibility', 'hidden' );

                         dispatch.fg_blur( d[ fg_key ] );
                     } )
                .on( 'click',
                     function ( d ) {
                         dispatch.fg_pick( d[ fg_key ] );
                     } )
            ;


            dispatch
                .on( 'fg_focus',
                     function ( fg ) {
                         var isviability = fg == 'Viability'
                         ,   color_class = isviability ? 'viability' : cs.css_class();

                         $points.filter( function ( d, i ) { return d[ fg_key ] == fg } )
                                .classed( 'fg-focus', true )
                                .filter( ':not(.fg-picked)' )
                                .classed( color_class, true );

                         $fg_lis.filter( function ( d, i ) { return d == fg } )
                                .classed( 'li-focus', true )
                                .filter( ':not(.li-picked)' )
                                .each( strip )
                                .classed( cs.css_class(), !isviability );
                     } )
                .on( 'fg_blur',
                     function ( fg ) {
                         var color_class = fg == 'Viability' ? 'viability' : cs.css_class();

                         $points.filter( function ( d, i ) { return d[ fg_key ] == fg } )
                                .classed( 'fg-focus', false )
                                .filter( ':not(.fg-picked)' )
                                .classed( color_class, false );

                         $fg_lis.filter( function ( d, i ) { return d == fg } )
                                .classed( 'li-focus', false )
                                .filter( ':not(.li-picked)' )

                                .classed( cs.css_class(), // sic: the
                                                          // 'viability'
                                                          // should
                                                          // never be
                                                          // removed
                                          false );
                     } )
                .on( 'fg_pick',
                     function ( fg ) {
                         var $to_pick =
                             $points.filter( function ( d, i ) { return d[ fg_key ] == fg } )
                                    .filter( ':not(.fg-picked)' );

                         $to_pick.classed( { 'fg-focus': false,
                                             'fg-picked': true } );

                         $fg_lis.filter( function ( d, i ) { return d == fg } )
                                .filter( ':not(.li-picked)' )
                                .classed( { 'li-focus': false,
                                            'li-picked': true } );

                         if ( fg != 'Viability' ) cs.next();

                         $fg_reset.attr( 'disabled', null );
                     } )

            ;

            d3.selectAll( '.plot-region' )
              .on( 'mousemove', function () {
                  var xy = this.invert_xy( d3.mouse( this ) );
                  $xy.data( xy.map( fmtxy ) )
                     .html( u.identity );
              } )
              .on( 'mouseenter', function () {
                  $xy_box.style( 'visibility', 'visible' );
              } )
              .on( 'mouseleave', function () {
                  $xy_box.style( 'visibility', 'hidden' );
              } )
            ;

        }
    };

    return events;
}

);
