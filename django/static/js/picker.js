'use strict';
define(     [ 'd3', 'utils' ],
    function ( d3 ,  u ) {

        function retval () {

            var title = ''
            ,   item = u.identity
            ,   MIN_ROWS = 3
            ,   HPADDING = 10
            ,   HMARGIN = 10
            ,   BORDERWIDTH = 1

            ;

            function min_colwidth_hack ( data, $parent ) {

                var all_widths = ( function () {

                                       var $offstage = $parent
                                                         .append( 'div' )
                                                         .style( { top: '-1000000px',
                                                                   position: 'absolute' } )
                                                         .classed( 'track-container', true )

                                       ,   $ul = $offstage.append( 'div' )
                                                          .classed( 'list-container-base', true )
                                                          .append( 'ul' )

                                       ,   lis = $ul.selectAll( 'li' )
                                                    .data( data )
                                                    .enter()
                                                    .append( 'li' )
                                                    .text( function ( d ) { return d } )
                                                    .style( 'display', '' )
                                                    .style( 'visibility', 'visible' )
                                                    [ 0 ]

                                       ,   ret = lis.map( u.text_width )
                                                    .sort( d3.descending )
                                       ;

                                       $offstage.remove();

                                       return ret;

                                   } )()

                ,   max_acceptable = Math.floor( data.length / ( MIN_ROWS * 2 ) )

                ;

                return all_widths[ max_acceptable ];
            }

            function get_ncols ( n, min_colwidth, max_width ) {

                var min_padded_colwidth = min_colwidth + ( 2 * BORDERWIDTH ) + HPADDING

                ,   max_ncols = 1 + ~~( ( n - 1 ) / MIN_ROWS )

                ,   ncols_0 = Math.max(1, Math.min( max_ncols,
                                                  ~~( max_width / ( min_padded_colwidth + HMARGIN ) ) ) )

                ;

                if ( ncols_0 > 1 ) {
                    var nrows = Math.max( MIN_ROWS, Math.ceil( n / ncols_0 ) ),
                        ncols_1 = Math.ceil( n / nrows );

                    if ( ncols_1 < ncols_0 ) return ncols_1;
                }

                return ncols_0;
            }

            var columnate = ( function () {

                var sentinel = String.fromCharCode( 29 );

                function _pad_array ( array, n ) {
                    return array.concat( d3.range( n - array.length )
                                           .map( function () { return sentinel } ) );
                }

                function _chunk ( array, chunksize ) {
                    return d3.range( array.length / chunksize )
                             .map( function ( i ) {
                                       var s = i * chunksize;
                                       return array.slice( s, s + chunksize );
                                   } );
                }

                function columnate ( array, ncols ) {

                    if ( ncols == 1 ) return array;

                    // assert ncols > 0

                    var nrows = Math.max( MIN_ROWS, Math.ceil( array.length / ncols ) ),
                        incols = d3.transpose( _chunk( _pad_array( array, nrows * ncols ),
                                                       nrows ) );

                    return d3.merge( incols )

                             .filter( function ( e ) { return e !== sentinel } )

                    ;
                }

                columnate.sentinel = sentinel;

                return columnate;

            } )();

            function style_ul ( ul, max_width, ncols ) {
                var colwidth = ( ~~( max_width / ncols ) ) - HMARGIN;

                // var ulwidth = ncols * ( colwidth + HMARGIN );
                // ul.style( 'width', ulwidth + 'px' );

                ul.selectAll( 'li' )
                  .style( 'padding', '0 ' + ( HPADDING / 2 ) + 'px' )
                  .style( 'margin', '0 ' + ( HMARGIN / 2 ) + 'px' )
                  .style( 'width', colwidth + 'px' );
            }


            function picker ( selection ) {

                selection.each( function ( data ) {

                    var parent = d3.select( this )
                    ,   max_width = u.pixels( parent.style( 'width' ) ) - 2 * BORDERWIDTH
                    ,   min_colwidth = min_colwidth_hack( data, parent )
                    ,   ncols = get_ncols( data.length, min_colwidth, max_width )
                    ,   items = columnate( data, ncols )

                    ;

                    parent.datum( items );

                    var top_button_bar =
                          parent.append( 'div' )
                          .attr( 'class', 'button-bar' )

                    ,   toggle_button =
                          top_button_bar.append( 'button' )

                    ,   list_container =
                          parent.append( 'div' )
                                .attr( 'class', 'list-container-base list-container' )

                    ,   ul = list_container.append( 'ul' )

                    ,   title_div = ul.append( 'div' )
                                      .attr( 'class', 'title' )
                                      .text( title )

                    ,   _ = list_container.append( 'br' )

                    ,   bottom_button_bar =
                          list_container.append( 'div' )
                                        .attr( 'class', 'button-bar' )

                    ,   reset_button =
                          bottom_button_bar.append( 'button' )
                                           .attr( 'class', 'reset' )
                                           .attr( 'disabled', 'disabled' )
                                           .html( 'reset' )

                    ,   lis = ul.selectAll( 'li' )
                                .data( items )
                              .enter()
                                .append( 'li' )
                                .attr( 'class', 'item' )
                                .text( item )
                    ;

                    style_ul( ul, max_width, ncols );

                } );

            }

            // -----------------------------------------------------------------
            // accessors

            picker.title = function ( _ ) {
                if ( !arguments.length ) return title;
                title = _;
                return picker;
            };

            picker.item = function ( _ ) {
                if ( !arguments.length ) return Object.create( item );
                item = _;
                return picker;
            };

            // -----------------------------------------------------------------

            return picker;
        }

        return retval;
    }
);
