'use strict';

// define( [ 'jquery', 'd3', 'hmslincs/utils' ],
// function ( $      ,  d3 ,  u ) {

define( [],

function () {

    var _
    ,   $$ = {}

    ,   FACTORS
    ,   NFACTORS

    ,   DISPATCH

    ,   STATE = {
                    picked: undefined
                  , focus: undefined
                  , current: undefined
                }

    ,   ALT = false
    ,   SUBSTATES = Object.keys( STATE )
    ,   PICKED
    ,   FOCUS
    ,   CURRENT

    ,   CHANGES
    ,   CHANGED

    ,   DEBUG = false
    ;

    function _clone ( o ) {

        if ( o === null || typeof( o ) !== 'object' ) return o;

        var retval = {};
        for ( var p in o ) {
            retval[ p ] = _clone( o[ p ] );
        }
        return retval;
    }

    function _transpose ( sobj ) {
        var retval = {};
        for ( var s in sobj ) {
            var fobj = sobj[ s ];
            for ( var f in fobj ) {
                var o = retval[ f ] || {};
                o[ s ] = fobj[ f ];
                retval[ f ] = o;
            }
        }
        return retval;
    }

    function _update ( which, updates, alt ) {

        var _
        ,   ch = CHANGES[ which ] || {}
        ,   substate = STATE[ which ]
        ;

        var f, v, i;

        for ( i = 0; i < NFACTORS; ++i ) {
            f = FACTORS[ i ];
            if ( f in updates ) {
                v = updates[ f ];
                if ( substate[ f ] != v ) {
                    ch[ f ] = substate[ f ] = v;
                    CHANGED = true;
                    CHANGES[ which ] = ch;
                }
            }
        }

        if ( arguments.length > 2 ) ALT = alt;
    }

    function _reset () {
        CHANGED = false;
        CHANGES = {};
    }

                function _tostr ( o ) {
                    if ( typeof( o ) !== 'object' ) return '' + o;
                    var kvs = [];
                    for ( var k in o ) {
                        kvs.push( k + ': ' + _tostr( o[ k ] ) );
                    }
                    return '{ ' + kvs.join( ', ' ) + ' }';
                }

    function _dispatch () {
        if ( ! CHANGED ) return;

        var _

        ,   changes = _clone( CHANGES )
        ,   state = _clone( STATE )

        ,   message = {
                        changes: {
                                   substates: changes,
                                   factors:   _transpose( changes )
                                 },

                        state:   {
                                   substates: state,
                                   factors:   _transpose( state )
                                 }
                      }
        ;

        if ( DEBUG ) console.log( 'state: ' + _tostr( state ) );

        DISPATCH( message );

        _reset();
    }

    function _nulls ( factors ) {
        var i, n = factors.length, updates = {};
        for ( i = 0; i < n; ++i ) {
            updates[ factors[ i ] ] = null
        }
        return updates;
    }

    $$.init = function ( factors, dispatch ) {
        FACTORS = factors;
        NFACTORS = factors.length;
        DISPATCH = dispatch;

        PICKED = STATE.picked = {};
        FOCUS = STATE.focus = {};
        CURRENT = STATE.current = {};

        _reset ();
    };

    $$.update_picked = function ( choice ) {
        _update( 'picked', choice );
        _update( 'focus', choice );
        _update( 'current', choice );
        _dispatch();
    };

    $$.update_focus = function ( choice ) {
        _update( 'focus', choice );
        if ( ALT ) _update( 'current', choice );
        _dispatch();
    };

    $$.lose_focus = function ( factors ) {
        _update( 'focus', _nulls( factors ) );
        if ( ALT ) {
            var i, f, n = factors.length, updates = {};
            for ( i = 0; i < n; ++i ) {
                f = factors[ i ];
                updates[ f ] = PICKED[ f ];
            }
            _update( 'current', updates );
        }
        _dispatch();
    };

    $$.update_policy = function ( alt ) {
        if ( alt === ALT ) return;

        var i, f, updates;
        if ( alt ) {
            updates = {};
            for ( i = 0; i < NFACTORS; ++i ) {
                f = FACTORS[ i ];
                if ( FOCUS[ f ] ) updates[ f ] = FOCUS[ f ];
            }
        }
        else {
            updates = PICKED;
        }

        _update( 'current', updates, alt );
        _dispatch();
    }

    return $$;
}

);
