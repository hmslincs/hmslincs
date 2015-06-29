'use strict';

define( [ 'jquery', 'd3', 'underscore', 'hmslincs/utils', 'model', 'colors' ],

function ( $      ,  d3 ,  __         ,  u              ,  M     ,  colors) {

    var _
    ,   $$ = {}
    ;

    $$.init = function () {

        var _
        ,   EMPTY_SELECTION = d3.select()

        ,   FACTORS
        ,   NFACTORS
        ,   DISPATCH

        ,   EVENT = 'state_change'

        ,   VIEWS = {}

        ,   INITIAL_VALUES
        ;


        ( function () {

            var ul_data = d3.selectAll( '.list-container ul' ).data();

            INITIAL_VALUES = ul_data.map( u.item_getter( 'content',
                                                         'initial_value' ) );

            FACTORS = ul_data.map( u.item_getter( 'context' ) );
            u.assert( __.isEqual( FACTORS,
                                  d3.select( '.heatmap .rows' )
                                    .datum()
                                    .context
                                    .map( u.to_identifier ) ) );

            NFACTORS = FACTORS.length;

        } )();


        d3.selectAll( '.list-container ul' ).each( function ( d, i ) {
            var _
            ,   NAME = d.context
            ,   $this = d3.select( this )
            ;

            VIEWS[ NAME ] = { init: init };

            function init ( dispatch, model ) {

                var _
                ,   VIEW_STATE
                ,   $UL = $this
                ,   LOOKUP = {}
                ;

                // register LISTEN as listener for model's change event
                dispatch.on( EVENT + '.' + NAME, listen );

                // initialize internal VIEW_STATE
                // NB: view's VIEW_STATE variable mirrors model (INFO LEAK?)
                VIEW_STATE = {
                                 picked: { val: null,
                                           sel: EMPTY_SELECTION }
                               , focus: { val: null,
                                          sel: EMPTY_SELECTION }
                               , current: { val: null,
                                            sel: EMPTY_SELECTION }
                             };

                // cache DOM elements
                $UL.selectAll( 'li' ).each( function ( d ) {
                    LOOKUP[ d.content ] = d3.select( this );
                } );

                // FIXME: the following adapter function should not be
                // necessary; the element's __data__ should have the information
                // already in the right form readily available
                function _make_li_choice ( _, d ) {
                    return u.make_obj( [ d.context, d.content ] );
                }

                // initialize handlers for interaction events
                $UL
                   .on( 'mouseleave',
                        function ( d ) {
                            model.lose_focus( [ d.context ] );
                        } )

                 .selectAll( 'li' )
                   .on( 'click',
                        function ( d ) {
                            model.update_picked( _make_li_choice( this, d ) );
                        } )
                   .on( 'mouseover',
                        function ( d ) {
                            model.update_focus( _make_li_choice( this, d ) );
                        } )
                ;

                function listen ( message ) {
                    // listens for changes in the model

                    // extracts relevant state info from the model's
                    // (generic/abstract/impartial) message and passes this info
                    // to UPDATE
                    update( message.changes.factors[ NAME ] );
                }

                function update ( state ) {
                    if ( ! state ) return;

                    var s, prev, newval, newsel;

                    for ( s in state ) {
                        prev = VIEW_STATE[ s ];
                        newval = state[ s ];

                        // state-based optimization 1
                        if ( prev.val == newval ) continue;

                        // remove classes of previous
                        // state-based optimization 2
                        prev.sel.classed( s, false );

                        // add classes to new
                        newsel =   newval === null
                                 ? EMPTY_SELECTION
                                 : LOOKUP[ newval ];

                        newsel.classed( s, true );

                        VIEW_STATE[ s ] = { val: newval,
                                            sel: newsel }
                    }
                }
            }

        } );


        ( function () {
            var _
            ,   NAME = 'graph'
            ;
            VIEWS[ NAME ] = { init: init };

            function init ( dispatch, _ ) {

                // NB: 'graph' is a "stateless view"

                // registers LISTEN as listener for model's change event
                dispatch.on( EVENT + '.' + NAME, listen );

                function listen ( message ) {
                    // listens for changes in the model

                    // extracts relevant state info from the model's
                    // (generic/abstract/impartial) message and passes this info
                    // to UPDATE
                    if ( message.changes.substates.current ) {
                        update( message.state.substates.current );
                    }
                }

                // -------------------------------------------------------------

                var _
                ,   nacolor = colors.nacolor
                ,   color_scale = colors.color_scale
                ,   bw_scale = colors.bw_scale

                ,   $rect = d3.selectAll( '.info .label-rect' )
                ,   $text = d3.selectAll( '.info .label-text' )
                ,   $tooltip = $rect.selectAll( 'title' )
                ;

                function update ( state ) {
                    if ( ! state ) return;

                    var _
                    ,   cl = state.cell_line
                    ,   tp = state.timepoint_hr
                    ;

                    $rect
                        .style( {
                            fill: function ( d ) {
                                      var v = d[ 1 ][ cl ][ tp ];
                                      return v === null ? nacolor : color_scale( v );
                                  },
                            'fill-opacity': function ( d ) {
                                                var v = d[ 1 ][ cl ][ tp ];
                                                return v === null ? 0 : 1;
                                            }
                                } )
                    ;

                    $text
                        .style( 'fill', function ( d ) {
                            return bw_scale( d[ 1 ][ cl ][ tp ] );
                        } )
                    ;

                    $tooltip
                        .text( function ( d ) {
                            var v = d[ 1 ][ cl ][ tp ];
                            return v === null ? '(na)' : v;
                        } )
                    ;
                }

            } // function init ( dispatch ) {

        } )();


        ( function () {
            var _
            ,   NAME = 'heatmap'
            ;

            VIEWS[ NAME ] = { init: init };

            function init ( dispatch, model ) {

                var _
                ,   VIEW_STATE
                ,   SUBSTATES = [ 'picked', 'focus', 'current' ]
                ,   NSUBSTATES = SUBSTATES.length
                ,   DFLT = SUBSTATES[ 0 ]
                ,   $HM
                ,   $ROWS
                ,   LOOKUP = {}
                ;

                function _make_key ( obj, dflt ) {
                    var _
                    ,   sep = String.fromCharCode( 28 )
                    // ,   sep = '::'
                    ,   keys = Object.keys( obj )
                    ,   n = keys.length
                    ,   vals = new Array( n )
                    ,   i
                    ;

                    function _islevel ( v ) {
                        return v != null && v != undefined;
                    }

                    _make_key = function ( obj, dflt ) {
                        var match = false;
                        for ( i = 0; i < n; ++i ) {
                            var k = keys[ i ], v = obj[ k ];
                            if ( _islevel( v ) ) {
                                match = true;
                            }
                            else if ( dflt ) {
                                v = dflt[ k ];
                            }
                            vals[ i ] = v;
                        }
                        return match ? vals.join( sep ) : null;
                    }

                    return _make_key.apply( this, arguments );
                }

                // registers LISTEN as listener for model's change event
                dispatch.on( EVENT + '.' + NAME, listen );

                // initializes internal VIEW_STATE
                // NB: view's VIEW_STATE variable mirrors model (INFO LEAK?)
                VIEW_STATE = {
                                 picked: { val: null,
                                           sel: EMPTY_SELECTION }
                               , focus: { val: null,
                                          sel: EMPTY_SELECTION }
                               , current: { val: null,
                                            sel: EMPTY_SELECTION }
                             };

                // caches its DOM elements
                $HM = d3.select( '.heatmap .rows' );

                $ROWS = $HM.selectAll( '.row' )
                    .each( function ( d ) {
                        LOOKUP[ _make_key( d.context ) ] = d3.select( this );
                    } );

                // initialize handlers for interaction events
                $HM
                   .on( 'mouseleave',
                        function ( d ) {
                            model.lose_focus( FACTORS );
                        } )

                 .selectAll( '.row' )
                   .on( 'click',
                        function ( d ) {
                            model.update_picked( d.context );
                        } )
                   .on( 'mouseover',
                        function ( d ) {
                            model.update_focus( d.context );
                        } )
                ;


                function listen ( message ) {
                    // listens for changes in the model

                    // extracts relevant state info from the model's
                    // (generic/abstract/impartial) message and passes this info
                    // to UPDATE
                    update( message.state.substates );
                }

                function update ( state ) {
                    if ( ! state ) return;

                    var i, s, prev, newval, newsel
                    ,   dflt = state[ DFLT ]
                    ,   found = 0
                    ;

                    for ( i = 0; i < NSUBSTATES; ++i ) {
                        s = SUBSTATES[ i ];
                        if ( ! ( s in state ) ) continue;
                        ++found;
                        prev = VIEW_STATE[ s ];
                        newval = _make_key( state[ s ], dflt );

                        // state-based optimization 1
                        if ( prev.val == newval ) continue;

                        // remove classes of previous
                        // state-based optimization 2
                        prev.sel.classed( s, false );

                        u.assert( newval === null || newval in LOOKUP );

                        // add classes to new
                        newsel =   newval === null
                                 ? EMPTY_SELECTION
                                 : LOOKUP[ newval ];

                        newsel.classed( s, true );

                        VIEW_STATE[ s ] = { val: newval,
                                            sel: newsel }
                    }

                    u.assert( found == Object.keys( state ).length );
                }
            }

        } )();

        ( function () {
            VIEWS[ 'body' ] = {
                // global interactions

                init: function ( _, model ) {
                    var throttle = 20
                    ,   count = throttle
                    ;

                    d3.select( 'body' )
                        .on( 'keyup',
                             function () {
                                 model.update_policy( d3.event.shiftKey );
                                 count = throttle;
                             } )

                        .on( 'keydown',
                             function () {
                                 if ( count % throttle ) {
                                     count += 1;
                                     return;
                                 }
                                 model.update_policy( d3.event.shiftKey );
                                 count = 1;
                             } )
                    ;
                }
            }
        } )();

        DISPATCH = d3.dispatch( EVENT );

        // initialize model
        M.init( FACTORS, DISPATCH[ EVENT ].bind( DISPATCH ) );

        // ---------------------------------------------------------------------
        // initialize views
        for ( var v in VIEWS ) VIEWS[ v ].init( DISPATCH, M );
        var initial_state = u.make_obj.apply( this,
                                              __.zip( FACTORS,
                                                      INITIAL_VALUES ) );
        M.update_picked( initial_state );
        M.lose_focus( FACTORS, false );

    };

    return $$;
}

);
