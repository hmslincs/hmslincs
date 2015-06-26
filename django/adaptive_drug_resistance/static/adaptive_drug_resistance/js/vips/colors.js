'use strict';
define( [ 'd3' ],
function ( d3 ) {

    function quantizer ( step ) {
        return function ( x ) { return step * Math.round( x /step ); };
    }

    // like d3.range, but including both endpoints
    function closed_range ( from, to, step ) {
        return d3.range( from, to + step, step );
    }

    var _
    ,   data_limits = [ -2.7212, 3.5739 ]
    ,   step = 0.5
    ,   nominal_domain = data_limits.map( quantizer( step ) )
    ,   make_series = function ( interval, step ) {
                          return closed_range.apply( this, interval.concat( step ) )
                      }

    ,   aux = ( function () {
                    // gamut below is based on the 11-class RdBu palette from
                    // colorbrewer2.org

                    var _
                    ,   range = [
                                  "#053061", "#2166ac", "#4393c3", "#92c5de", "#d1e5f0",
                                  "#f7f7f7",
                                  "#fddbc7", "#f4a582", "#d6604d", "#b2182b", "#67001f"
                                ]
                    ,   max = Math.max.apply( this, nominal_domain.map( Math.abs ) )
                    ,   domain = closed_range( -max, max,
                                               ( 2 * max )/( range.length - 1 ) )
                    ;

                    return d3.scale
                             .linear()
                             .domain( domain )
                             .range( range )

                } )()

    ,   domain = [
                   nominal_domain[ 0 ] - step/2,
                   nominal_domain[ 1 ] + step/2
                 ]

    ,   range = closed_range.apply( this, nominal_domain.concat( step ) )
                            .map( aux )

    ,   color_scale = d3.scale
                        .quantize()
                        .domain( domain )
                        .range( range )

    ,   $$ = {}

    ;

    $$.color_scale = color_scale;

    $$.bw_scale = function ( v ) {
                      var l = d3.rgb( color_scale( v || 0 ) ).hsl().l;
                      return l > 0.69 ? 'black' : 'white'
                  };

    return $$;
}

);
