'use strict';
define( [ 'd3', 'underscore' ],
function ( d3, _ ) {

    var $$ = {}
    ,   _fn = Function.prototype
    ,   _ar = Array.prototype
    ,   _slice = _fn.call.bind( _ar.slice )
    ,   _forEach = _fn.call.bind( _ar.forEach )
    ;

    $$.assert = function ( bool, msg ) {
        if ( bool ) return;
        var _
        ,   pfx = 'Assertion failed'
        ,   error = arguments.length < 2 ? pfx : pfx + ': ' + msg
        ;
        throw new Error( error );
    };

    $$.to_array = function ( list ) { return _slice( list ) };

    $$.first = function ( e ) { return e[ 0 ] };
    $$.second = function ( e ) { return e[ 1 ] };

    $$.item_getter = function () { return _get_getter( 'item', arguments ) };
    $$.thunk_getter = function () { return _get_getter( 'thunk', arguments ) };

    function _get_getter ( which, args ) {

        function _get ( obj, key ) {
            var nargs = arguments.length;
            $$.assert( nargs > 1 );

            var newobj = obj[ key ];
            if ( nargs == 2 ) return newobj;

            var args = [ newobj ].concat( _slice( arguments, 2 ) );
            return _get.apply( this, args );
        }

        $$.item_getter = function ( key ) {
            if ( arguments.length == 1 ) { // common special case
                return function ( d ) { return d[ key ] };
            }

            var args = $$.to_array( arguments );

            return function ( d ) {
                return _get.apply( this, [ d ].concat( args ) );
            };
        };

        $$.thunk_getter = function ( key ) {
            if ( arguments.length == 1 ) { // common special case
                return function ( d ) { return d[ key ]() };
            }

            var args = $$.to_array( arguments );

            return function ( d ) {
                return _get.apply( this, [ d ].concat( args ) )();
            };

        }

        return $$[ which + '_getter' ].apply( this, args );
    }

    $$.identity = function ( e ) { return e };

    $$.sum = function () {
        var add2 = function ( a, b ) { return a + b };
        $$.sum = function ( arr ) {
            return $$.to_array( arr ).reduce( add2 );
        };
        return $$.sum.apply( this, arguments );
    };

    $$.average = function ( arr ) {
        return  $$.sum( arr ) / arr.length;
    };

    $$.translate = function () {
        return 'translate(' + $$.to_array( arguments ) + ')';
    };

    $$.rotate = function ( a ) {
        return 'rotate(' + a + ')';
    };

    $$.scale = function () {
        return 'scale(' + $$.to_array( arguments ) + ')'
    };

    $$.pixels = function ( s ) {
        return parseInt( s, 10 );
    };

    function _canonicalizer( sep, invalid ) {
        var _

        ,   qsep = d3.requote( sep )
        ,   to_replace_minimal = new RegExp( '[^a-zA-Z0-9' + qsep + ']', 'g' )
        ,   to_replace = new RegExp( to_replace_minimal.source + '+', 'g' )
        ,   trim = new RegExp( '(?:^' + qsep + '+|' + qsep + '+$)', 'g' )

        ,   core = [ // 0: aggressive transform
                     function ( s ) {
                         return s.toLowerCase()
                                 .replace( to_replace, sep )
                                 .replace( trim, '' );
                     },

                     // 1: minimal transform
                     function ( s ) {
                         return s.replace( to_replace_minimal, sep )
                     }

                   ]

        ,   err = function ( s ) {
                return new Error( 'Transformed string is invalid: "' + s + '"' );
            }

        ,   suite
        ,   retval

        ;

        if ( invalid ) {
            suite = core.map( function ( c ) {
                return function ( s ) {
                    var retval = c.apply( this, arguments );
                    if ( retval.length == 0 || invalid.test( retval ) ) {
                        throw err( retval );
                    }
                    return retval;
                }
            } );
        }
        else {
            suite = core.map( function ( c ) {
                return function () {
                    var retval = c.apply( this, arguments );
                    if ( retval.length == 0 ) throw err( '' );
                    return retval;
                }
            } );
        }

        retval = suite[ 0 ];
        for ( var i = 0; i < suite.length; ++i ) {
            // NB: despite what the next line may suggest, retval is a function
            // object, whereas suite is an array
            retval[ i ] = suite[ i ];
        }

        // NB: at this point retval is just "shorthand" for retval[ 0 ];
        // i.e. retval === retval[ 0 ]
        return retval;
    }

    $$.to_attr = function () {

        // Transform a string into a form suitable as a class name or element
        // id, or part thereof.
        //
        // The default behavior is to produce the shortest lower-case transform
        // that will serve as a valid class name or element id:
        //
        // > $$.to_attr( 'No soap?  Radio!' )
        // < "no-soap-radio"
        //
        // To get a less aggressive transformation of the input string, use the
        // variant at index = 1:
        //
        // > $$.to_attr[ 1 ]( 'No soap?  Radio!', true )
        // < "No-soap---Radio-"
        //
        // An error is thrown if the transformation results in an invalid
        // string.  For example, if `raw_string` had the value '123 Elm St.',
        // then calling `$$.to_attr( raw_string )` would fail, because the
        // standard transformation in this case would produce the invalid string
        // `123-elm-st'.  This can be prevented by always capping the beginning
        // of the argument to `$$.to_attr` with a safe prefix:
        //
        // > $$.to_attr( 'myprefix-' + raw_string )
        // < "myprefix-123-elm-st"

        $$.to_attr = _canonicalizer( '-', new RegExp( '^(?:-?\d|--)' ) );

        return $$.to_attr.apply( this, arguments );
    };

    $$.to_identifier = function () {

        // Transform a string into a form suitable as a JavaScript
        // dot-notation-compatible object key, or part thereof.
        //
        // The primary difference between $$.to_identifier and $$.to_attr is
        // that they use '_' and '-', respectively, as the replacement
        // character.  See the documentation for $$.to_attr for additional
        // details.

        $$.to_identifier = _canonicalizer( '_', new RegExp( '^\d' ) );
        return $$.to_identifier.apply( this, arguments );
    };

    $$.make_obj = function () {
        // Make object from list of key-value pairs.
        //
        // In standard JavaScript, the lexical items before the ':' in
        // expressions of the form:
        //
        //     {key0: val0, key1: val1, key2: val2, ...}
        //
        // are not evaluated (as are the items after the ':'), but rather are
        // interpreted as strings.
        //
        // This means that one cannot write an object initializer whose keys are
        // specified through variables.  For example, if
        //
        //     key0 = 'foo'; key1 = 'bar'; key2 = 'baz'; ...
        //
        // then after the assignment
        //
        // > obj = { key0: 3, key1: 1, key2: 4, ... }
        //
        // the value of `obj` will not be
        //
        //     {'foo': 3, 'bar': 1, 'baz': 4, ...}
        //
        // but rather
        //
        //     {'key0': 3, 'key1': 1, 'key2': 4, ...}
        //
        // When keys are specified through variables, $$.make_obj gives a simple
        // expression for the corresponding object that can be used, e.g., as
        // initializer
        //
        // > obj = $$.make_obj( [ key0, 3 ], [ key1, 1 ], [ key2, 4 ], ... )
        // < Object {foo: 3, bar: 1, baz: 4, ...}

        var obj = {};
        _forEach( arguments, function ( e ) {
            obj[ e[ 0 ] ] = e[ 1 ];
        } );
        return obj;
    };

    $$.id_server = function () {
        // Make a generator of unique id strings.
        //
        // usage:
        //
        // var next_id = id_server().prefix( 'No soap?  Radio!' )
        //                          .format( '3d' );
        //
        // console.log( next_id() );  // --> 'no-soap-radio-000'
        //
        // ...
        //
        // $thing.attr( 'id', next_id );
        // console.log( $thang.node().id ) // --> 'no-soap-radio-001'
        //
        // $thang.datum( 42 )
        //       .attr( 'id',
        //              function ( d ) {
        //                  return [ next_id(), d ].join( '-' );
        //              } );
        // console.log( $thang.node().id ) // --> 'no-soap-radio-002-42'

        var _
        ,   prefix = 'el-'  // short for "element"
        ,   format = d3.format( 'd' )
        ,   last
        ;

        function server () {
            last = next;
            next += 1;
            return prefix + format( last );
        }

        // accessors
        server.prefix = function ( _ ) {
            if ( !arguments.length ) return prefix;
            prefix = $$.to_attr( _ ) + '-';
            return server;
        };

        server.next = function ( _ ) {
            if ( !arguments.length ) return next;
            next = _;
            return server;
        };

        server.start = server.next;

        server.format = function ( _ ) {
            if ( !arguments.length ) return format;
            format = typeof( _ ) === 'string' ? d3.format( _ ) : format;
            return server;
        };

        return server;
    };

    $$.text_width = function ( t ) {
        var get_bbox = t.getBBox ? 'getBBox' : 'getBoundingClientRect';
        return Math.ceil( t[ get_bbox ]().width );
    };

    $$.rounder = function ( d ) {
        var m0 = Math.pow( 10, d )
        ,   m1 = 1/m0
        ;
        return function ( f ) {
            return Math.round( m0 * f ) * m1;
        }
    };

    $$.interpolate = function ( interval, t ) {
        return interval[ 0 ] * ( 1 - t ) + interval[ 1 ] * t;
    };

    $$.pad_interval = function ( interval, relative_padding ) {
        return [ $$.interpolate( interval, - relative_padding ),
                 $$.interpolate( interval, 1 + relative_padding ) ];
    };

    return $$;
}

);
