'use strict';
define( [ 'd3', 'underscore' ],
function ( d3, _ ) {

    function flatten ( data ) {
        return _.flatten( data.map( function ( e ) {
            return ( 'data' in e ) ? flatten( e.data ) : [ e ];
        } ) );
    }

    function parse_timepoint ( a ) {
        function avg( p, q ) { return ( p + q ) / 2 }
        return eval( a + '' )
    }

    return {
          flatten: flatten
        , parse_timepoint: parse_timepoint
    };
}

);
