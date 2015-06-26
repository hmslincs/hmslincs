'use strict';
define( [ 'd3' ],

function ( d3 ) {

    function d3_identity ( d ) {
      return d;
    }

    // The fixed property has three bits:
    // Bit 1 can be set externally (e.g., d.fixed = true) and show persist.
    // Bit 2 stores the dragging state, from mousedown to mouseup.
    // Bit 3 stores the hover state, from mouseover to mouseout.
    // Dragend is a special case: it also clears the hover state.

    function d3_layout_forceDragstart ( d ) {
        d.fixed |= 2; // set bit 2
    }

    function d3_layout_forceDragend ( d ) {
        d.fixed &= ~6; // unset bits 2 and 3
    }

    function d3_layout_forceMouseover ( d ) {
        d.fixed |= 4; // set bit 3
        d.px = d.x, d.py = d.y; // set velocity to zero
    }

    function d3_layout_forceMouseout ( d ) {
        d.fixed &= ~4; // unset bit 3
    }

    function d3_layout_forceAccumulate ( quad, alpha, charges ) {
        var cx = 0
        ,   cy = 0
        ,   point_charge
        ;

        quad.charge = 0;

        if ( ! quad.leaf ) {
            quad.nodes.forEach( function ( node ) {
                if ( node == null ) return;

                d3_layout_forceAccumulate( node, alpha, charges );
                quad.charge += node.charge;
                cx += node.charge * node.cx;
                cy += node.charge * node.cy;

            } );
        }

        if ( quad.point ) {

            // jitter internal nodes that are coincident
            if ( ! quad.leaf ) {
                quad.point.x += Math.random() - 0.5;
                quad.point.y += Math.random() - 0.5;
            }

            quad.pointCharge =
                point_charge = alpha * charges[ quad.point.index ];

            quad.charge += point_charge;
            cx += point_charge * quad.point.x;
            cy += point_charge * quad.point.y;

        }

        quad.cx = cx / quad.charge;
        quad.cy = cy / quad.charge;
    }

    var d3_layout_forceLinkDistance = 20
    ,   d3_layout_forceLinkStrength = 1
    ,   d3_layout_forceChargeDistance2 = Infinity;


    // A rudimentary force layout using Gauss-Seidel.
    return function () {

        var Force = {}

        ,   Event = d3.dispatch( 'start', 'tick', 'end' )
        ,   Drag

        ,   Distances
        ,   Strengths
        ,   Charges

        ,   NODES = []
        ,   LINKS = []
        ,   SIZE = [ 1, 1 ]
        ,   LINK_DISTANCE = d3_layout_forceLinkDistance
        ,   LINK_STRENGTH = d3_layout_forceLinkStrength
        ,   FRICTION = 0.9
        ,   CHARGE = -30
        ,   CHARGE_DISTANCE_2 = d3_layout_forceChargeDistance2
        ,   GRAVITY = 0.1
        ,   THETA2 = 0.64
        ,   ALPHA

        ,   Center_X = SIZE[ 0 ] / 2
        ,   Center_Y = SIZE[ 1 ] / 2
        ;

        function repulse ( node ) {

            return function ( quad, x1, _, x2 ) {

                if ( quad.point !== node ) {

                    var dx = quad.cx - node.x
                    ,   dy = quad.cy - node.y
                    ,   dn = dx * dx + dy * dy
                    ,   dw = x2 - x1

                    ,   charge
                    ,   point_charge
                    ;

                    // Barnes-Hut criterion
                    if ( dw * dw < dn * THETA2 ) {
                        if ( dn < CHARGE_DISTANCE_2 ) {
                            charge = quad.charge / dn;
                            if ( ! node.fixed_x ) node.px -= dx * charge;
                            if ( ! node.fixed_y ) node.py -= dy * charge;
                        }
                        return true;
                    }
                    if ( quad.point && dn && dn < CHARGE_DISTANCE_2 ) {
                        point_charge = quad.pointCharge / dn;
                        if ( ! node.fixed_x ) node.px -= dx * point_charge;
                        if ( ! node.fixed_y ) node.py -= dy * point_charge;
                    }
                }

                return ! quad.charge;
            };

        }

        Force.tick = function () {

            // simulated annealing, basically
            ALPHA *= 0.99;

            if ( ALPHA < 0.005 ) {
                ALPHA = 0;
                Event.tick( { type: 'end', alpha: 0 } );
                console.log( 'done' );
                return true;
            }

            // Gauss-Seidel relaxation for links
            LINKS.forEach( function ( link, i ) {

                var _
                ,   src = link.source
                ,   tgt = link.target
                ,   lx = tgt.x - src.x
                ,   ly = tgt.y - src.y
                ,   l2 = lx * lx + ly * ly
                ;

                if ( ! l2 ) return;

                var _
                ,   l = Math.sqrt( l2 )
                ,   k = ALPHA * Strengths[ i ] * ( l - Distances[ i ] ) / l
                ,   dlx = lx * k
                ,   dly = ly * k
                ,   ws = src.weight / ( tgt.weight + src.weight )
                ,   wt = 1 - ws
                ;

                if ( ! tgt.fixed_x ) tgt.x -= dlx * ws;
                if ( ! tgt.fixed_y ) tgt.y -= dly * ws;

                if ( ! src.fixed_x ) src.x += dlx * wt;
                if ( ! src.fixed_y ) src.y += dly * wt;

            } );

            // apply gravity forces
            if ( GRAVITY ) {
                var ag = ALPHA * GRAVITY;

                NODES.forEach( function ( node ) {
                    if ( ! node.fixed_x ) node.x += ( Center_X - node.x ) * ag;
                    if ( ! node.fixed_y ) node.y += ( Center_Y - node.y ) * ag;
                } );
            }

            // compute quadtree center of mass and apply charge forces
            if ( CHARGE ) {
                var quadtree = d3.geom.quadtree( NODES );
                d3_layout_forceAccumulate( quadtree, ALPHA, Charges );

                NODES.forEach( function ( node ) {
                    if ( ! node.fixed ) quadtree.visit( repulse( node ) );
                } );
            }

            // position Verlet integration
            NODES.forEach( function ( node ) {
                var tmp;

                if ( node.fixed ) {
                    if ( ! node.fixed_x ) node.x = node.px;
                    if ( ! node.fixed_y ) node.y = node.py;
                }
                else {
                    if ( ! node.fixed_x ) {
                        tmp = node.x - ( node.px - node.x ) * FRICTION;
                        node.px = node.x;
                        node.x = tmp;
                    }

                    if ( ! node.fixed_y ) {
                        tmp = node.y - ( node.py - node.y ) * FRICTION;
                        node.py = node.y;
                        node.y = tmp;
                    }
                }

            } );

            Event.tick( { type: 'tick', alpha: ALPHA } );
        };

        // accessors

        Force.nodes = function ( x ) {
            if ( ! arguments.length ) return NODES;
            NODES = x;
            return Force;
        };

        Force.links = function ( x ) {
            if ( ! arguments.length ) return LINKS;
            LINKS = x;
            return Force;
        };

        Force.size = function ( x ) {
            if ( ! arguments.length ) return SIZE;
            SIZE = x;

            Center_X = SIZE[ 0 ] / 2
            Center_Y = SIZE[ 1 ] / 2;

            return Force;
        };

        Force.linkDistance = function ( x ) {
            if ( ! arguments.length ) return LINK_DISTANCE;
            LINK_DISTANCE = typeof x === 'function' ? x : +x;
            return Force;
        };

        // For backwards-compatibility.
        Force.distance = Force.linkDistance;

        Force.linkStrength = function ( x ) {
            if ( ! arguments.length ) return LINK_STRENGTH;
            LINK_STRENGTH = typeof x === 'function' ? x : +x;
            return Force;
        };

        Force.friction = function ( x ) {
            if ( ! arguments.length ) return FRICTION;
            FRICTION = +x;
            return Force;
        };

        Force.charge = function ( x ) {
            if ( ! arguments.length ) return CHARGE;
            CHARGE = typeof x === 'function' ? x : +x;
            return Force;
        };

        Force.chargeDistance = function ( x ) {
            if ( ! arguments.length ) return Math.sqrt( CHARGE_DISTANCE_2 );
            CHARGE_DISTANCE_2 = x * x;
            return Force;
        };

        Force.gravity = function ( x ) {
            if ( ! arguments.length ) return GRAVITY;
            GRAVITY = +x;
            return Force;
        };

        Force.theta = function ( x ) {
            if ( ! arguments.length ) return Math.sqrt( THETA2 );
            THETA2 = x * x;
            return Force;
        };

        Force.alpha = function ( x ) {
            if ( ! arguments.length ) return ALPHA;
            x = +x;
            if ( ALPHA ) {          // if we're already running
                ALPHA = x > 0 ? x   // we might keep it hot
                              : 0;  // or, next tick will dispatch 'end'
            }
            else if ( x > 0 ) {     // otherwise, fire it up!
                ALPHA = x;

                Event.start( { type: 'start', alpha: ALPHA } );

                d3.timer( Force.tick );
            }
            return Force;
        };

        Force.start = function () {

            var _
            ,   width = SIZE[ 0 ]
            ,   height = SIZE[ 1 ]
            ,   neighbors
            ;

            NODES.forEach( function ( node, i ) {
                node.index = i;
                node.weight = 0;
            } );

            LINKS.forEach( function ( link ) {
                if ( typeof link.source == 'number' ) link.source = NODES[ link.source ];
                if ( typeof link.target == 'number' ) link.target = NODES[ link.target ];
                ++link.source.weight;
                ++link.target.weight;
            } );

            NODES.forEach( function ( node, i ) {
                if ( isNaN( node.x ) ) node.x = position( 'x', width, i );
                if ( isNaN( node.y ) ) node.y = position( 'y', height, i );
                if ( isNaN( node.px ) ) node.px = node.x;
                if ( isNaN( node.py ) ) node.py = node.y;
            } );

            Distances = new Array( LINKS.length );

            if ( typeof LINK_DISTANCE === 'function' ) {
                LINKS.forEach( function ( link, i ) {
                    Distances[ i ] = +LINK_DISTANCE.call( this, link, i );
                } );
            }
            else {
                LINKS.forEach( function ( link, i ) {
                    Distances[ i ] = LINK_DISTANCE;
                } );
            }

            Strengths = new Array( LINKS.length );

            if ( typeof LINK_STRENGTH === 'function' ) {
                LINKS.forEach( function ( link, i ) {
                    Strengths[ i ] = +LINK_STRENGTH.call( this, link, i );
                } );
            }
            else {
                LINKS.forEach( function ( link, i ) {
                    Strengths[ i ] = LINK_STRENGTH;
                } );
            }

            Charges = new Array( NODES.length );

            if ( typeof CHARGE === 'function' ) {
                NODES.forEach( function ( node, i ) {
                    Charges[ i ] = +CHARGE.call( this, node, i );
                } );
            }
            else {
                NODES.forEach( function ( node, i ) {
                    Charges[ i ] = CHARGE;
                } );
            }

            // inherit node position from first neighbor with defined
            // position or if no such neighbors, initialize node
            // position randomly; initialize neighbors lazily to avoid
            // overhead when not needed
            function position ( dimension, size, i ) {

                if ( ! neighbors ) {
                    neighbors = [];
                    NODES.forEach( function () {
                        neighbors.push( [] );
                    } );
                    LINKS.forEach( function ( link ) {
                        var s = link.source
                        ,   t = link.target
                        ;
                        neighbors[ s.index ].push( t );
                        neighbors[ t.index ].push( s );
                    } );
                }

                var candidates = neighbors[ i ]
                ,   j = -1
                ,   x;

                while ( ++j < candidates.length ) {
                    x = candidates[ j ][ dimension ];
                    if ( ! isNaN( x ) ) return x;
                }

                return Math.random() * size;
            }


            return Force.resume();
        };

        Force.resume = function () {
            return Force.alpha( 0.1 );
        };

        Force.stop = function () {
            return Force.alpha( 0 );
        };

        // use `node.call(Force.drag)` to make nodes draggable
        Force.drag = function () {

            if ( ! Drag ) {
                Drag = d3.behavior
                    .drag()
                    .origin( d3_identity )
                    .on( 'dragstart.force', d3_layout_forceDragstart )
                    .on( 'drag.force', dragmove )
                    .on( 'dragend.force', d3_layout_forceDragend );
            }

            if ( ! arguments.length ) {
                return Drag;
            }

            this.on( 'mouseover.force', d3_layout_forceMouseover )
                .on( 'mouseout.force', d3_layout_forceMouseout )
                .call( Drag );
        };

        function dragmove ( d ) {
            d.px = d3.event.x;
            d.py = d3.event.y;
            Force.resume();
        }

        return d3.rebind( Force, Event, 'on' );
    };

} );
