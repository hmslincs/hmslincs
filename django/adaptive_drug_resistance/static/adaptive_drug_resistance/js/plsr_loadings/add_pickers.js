'use strict';
define(    [  'hmslincs/picker', 'hmslincs/utils', 'common', 'jquery', 'd3' ],
    function ( picker          ,  u              ,  c      ,  $      ,  d3 ) {

        function _add_pickers ( flat_data ) {

            function get_levels ( key ) {
                function level ( d ) { return d[ key ] };
                return _.uniq( flat_data.map( level ) );
            }

            var titles = [ 'Cell_line', 'RPPA_measurement' ]
            ,   level_sets = titles.map( get_levels )
            ,   pickers = {}
            ;

            d3.select( '.left-panel' )
                .selectAll( '.track-container' )
                .data( level_sets )
              .enter()
                .append( 'div' )
                .attr( 'class', 'track-container' )
                .classed( { hidden: true,
                            'while-loading': true } )
                .each( function ( d, i ) {
                           var title = titles[ i ]
                           ,   pkr = picker().title( title )
                           ,   $this = $( this )
                           ;

                           $this.addClass( u.to_attr( title ) );

                           pkr( d3.select( this ) );

                           $this.find( '.button-bar' ).first().remove();

                           $this.find( 'li' )
                                .each( function ( _, e ) {
                                           var $e = $( e );
                                           $e.addClass( u.to_attr( $e.text() ) );
                                       } );

                           pkr.pick = function ( v ) {

                               $this
                                 .find( 'li' )
                                 .filter( function ( _, e ) {
                                     return $( e ).text() === v;
                                  } )
                                 .click();
                           };

                           pickers[ title ] = pkr;

                       } )
                ;

            return pickers;
        }

        return function ( data ) {
            return _add_pickers( c.flatten( data ) );
        };
    }
);
