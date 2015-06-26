'use strict';

var FATAL = function () { Error.apply( this, arguments ); this.name = "FATAL"; },
    ABORT = function () {
                if ( window.QUIT ) {
                    throw new FATAL( 'bailing...' );
                }
            },
    QUIT = false,
    BAIL = function () { QUIT = true; };

FATAL.prototype = Object.create( Error.prototype );

( function () {
var js_dir = '../'
,   lib_dir = js_dir + 'lib/'
,   ext_dir = js_dir + 'ext/'
;

require.config(

    {
        paths: {
                   hmslincs: lib_dir + 'hmslincs'
                 , d3: ext_dir + 'd3/d3'
                 , jquery: ext_dir + 'jquery/jquery'
                 , underscore: ext_dir + 'lodash/lodash'
               }
      , shim: { d3: { exports:'d3' } }
    }

);

require( [ 'app' ], function ( app ) { app() } );

} )();
