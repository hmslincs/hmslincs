'use strict';

define(

        [ 'jquery', 'd3', './config', './add_pickers', 'lib/utils', './events', './colors', 'lib/colorbar' ],

function ( $      ,  d3 ,  cfg    ,    add_pickers ,    u         ,  events ,    colors,     colorbar ) {

    var _

    ,   SCALE = { x: null, y: null }

    ,   BASE_SCALING = 0.75
    ,   BASE_HEIGHT = 800
    ,   BASE_WIDTH = 800

    ,   UNIT = 4
    ,   VPADDING = UNIT
    ,   HPADDING = UNIT
    ,   CORNER_RADIUS = UNIT

    ,   DUMMY_CLASS = 'dummy-class'
    ;

    function load_json ( path, handler ) {
        d3.json( path, function ( error, json ) {
            if ( error ) throw error;
            handler( json );
        } );
    }

    function build_heatmap ( data ) {

        var _
        ,   heatmap = data.heatmap
        ,   nacolor = colors.nacolor
        ,   scale = colors.color_scale
        ;

        d3.select( '.colh-div' )

          .selectAll( '.colh' )
            .data( heatmap.cols ).enter()

          .append( 'span' )
            .attr( 'class', 'colh' )
          .append( 'span' )
            .html( u.identity )
        ;

        function _context_maker ( factors ) {
            var i, n = factors.length;
            return function ( values ) {
                var ctx = {};
                for ( i = 0; i < n; ++i ) {
                    ctx[ factors[ i ] ] = values[ i ];
                }
                return ctx;
            };
        }

        // FIXME: the structure of the `data.heatmap` input needs to match more
        // closely the structure of the corresponding DOM sub-tree; at the
        // moment it's very hard to follow what's going on here.
        function _distribute_context ( d ) {
            var ctx = d.context;
            return d.content.map( function ( d0 ) {
                return { context: ctx, content: d0 }
            } );
        }

        var _

        ,   rowh = heatmap.factors

        ,   rows = d3.select( '.rows' )

                     // ugly hack...
                     .datum( { context: rowh,
                               content: heatmap.data } )

        ,   factors = rowh.map( u.to_identifier )
        ,   make_context = _context_maker( factors )

        ,   super_row =

                rows
              .selectAll( '.super-row' )
                .data( heatmap.data ).enter()

              .append( 'span' )
                .attr( 'class', 'super-row' )

        ,   row =
              super_row
              .selectAll( '.row' )
                .data( function ( d ) {

                    return d.map( function ( d0 ) {
                        return { context: make_context( d0[ 0 ] ),
                                 content: d0 }
                    } );

                } ).enter()

              .append( 'span' )
                .attr( 'class',
                       function ( d ) {
                           return 'row ' + d.content[ 0 ].join( '-' );
                       } )

        ,   sub_row =
              row
              .selectAll( '.sub-row' )
                .data( _distribute_context ).enter()

              .append( 'span' )
                .classed( {
                              'sub-row': true
                            , 'rowh': function ( _, i ) { return i == 0 }
                            , 'body': function ( _, i ) { return i == 1 }
                          } )
              .append( 'span' )

        ,   cell =
              sub_row.selectAll( '.cell' )
                     .data( _distribute_context ).enter()
                   .append( 'span' )
                     .attr( 'class', 'cell' )
        ;

        row.selectAll( '.rowh > span' )
           .selectAll( '.cell' )
           .each( function ( _, i ) {
                      d3.select( this ).classed( factors[ i ], true );
                  } )
           .text( u.item_getter( 'content' ) )
        ;

        cell.filter( '.body .cell' )
            .classed( 'na', function ( d ) { return d.content === null; } )
            .style( 'background-color',
                    function ( d, _, j ) {
                        var v = d.content;
                        return v === null ? null : scale( v );
                    } )
            .attr( 'title',
                   function ( d ) {
                       var v = d.content;
                       return v === null ? '(na)' : '' + v;
                   } )
        ;
    }

    function build_graph ( data ) {
        var _
        ,   graph = data.graph

        ,   svg = d3.select( '.svg-stage' )
                  .append( 'div' )
                    .classed( 'svg-wrapper', true )
                  .append( 'svg' )

        ,   side = '17'
        ,   halfSide = '' + parseInt(side)/2
        ,   $patt = svg.append( 'defs' )
                       .append( 'pattern' )
                       .attr(
                           {
                             id: 'striped',
                             x: '0',
                             y: '0',
                             width: side,
                             height: side,
                             patternUnits: 'userSpaceOnUse'
                           }
                       )

        ,   $root = svg.append( 'g' )
                       .append( 'g' )
                         .classed( 'root', true )
        ;

        $patt.append( 'rect' )
             .attr( { width: side, height: side, fill: '#ffffff' } );

        $patt.append( 'g' )
             .attr( { transform: 'translate(' + halfSide + ', ' + halfSide + ') rotate(-45)' } )
             .selectAll( 'rect' )
             .data( [ -9, -3, 3, 9 ] ).enter()
             .append( 'rect' )
             .attr(
                 {
                     x: '-13',
                     y: function ( d ) { return '' + d; },
                     width: '26',
                     height: '3',
                     fill: '#eeeeee'
                 } );



        $root.selectAll( '.link' )
          .data( graph.links ).enter()
        .append( 'line' )
          .classed( 'link', true )
          .classed( 'hidden', function ( d ) { return !! d.hidden } )
        ;

        $root.selectAll( '.node' )
          .data( graph.nodes ).enter()
        .append( 'g' )
          .classed( 'node', true )
          .classed( 'labeled', function ( d ) { return !! d.data.label } )
          .classed( 'mutable', function ( d ) { return !! d.data.RPPA_measurement } )
          .classed( 'hidden', function ( d ) { return !! d.hidden } )
          .classed( 'process', function ( d ) { return d.type === 'process' } )
        ;
    }

    function add_label ( d ) {

        var _
        ,   $node = d3.select( this )
        ,   label = d.data.label
        ;

        var _
        ,   $node_frame =
                d3.select( $node.node()
                           .appendChild(
                               make_node_frame(
                                   [ [ label ] ]
                               )
                           )
                         )

        ,   $slots = $node_frame
                       .select( '.slots' )
                       .selectAll( '.slot' )
                       .data( u.identity ).enter()
                     .append( 'g' )
                       .classed( { slot: true,
                                   label: true } )

        ,   $strips = $slots
                        .selectAll( '.strip' )
                        .data( u.identity ).enter()
                      .append( 'g' )
                        .classed( { strip: true } )

        ,   block = textblock( { justify: 'center' } )
                             ( $node.selectAll( '.label .strip' ) )

        ,   $text = $node_frame.select( '.label-text' )
        ,   $rect = $node_frame.select( '.label-rect' )
        ;

        // $rect.attr( { rx: CORNER_RADIUS } );

        if ( d.is_growth_factors_cytokines_node /* a sorry hack */ ) {
            var _

            ,   y0 = d.y
            ,   y1 = d.y1

            ,   offset = 4 * HPADDING
            ,   w = SCALE.y( y0 ) - SCALE.y( y1 ) + 2 * offset
            ;

            block.width( w );

            $node_frame.attr( 'transform',
                              'rotate(-90) ' +
                              u.translate( - offset,
                                           - $node_frame.node()
                                                        .getBBox()
                                                        .height / 2 )
                            )
            ;
        }
        else {
            center_node_frame( $node_frame );
        }
    }

    function textblock ( params ) {
        var _
        ,   width = 0
        ,   vpadding
        ,   hpadding
        ,   voffset
        ,   $rect
        ,   $text
        ,   unit = UNIT
        ,   cfg = ( function () {
                        var _
                        ,   font_units = 4
                        ,   padding =
                                { t: unit, r: unit, b: unit, l: unit }
                        ;
                        return {
                              font_size: ( font_units * unit )
                            , font_units: null
                            , padding: padding
                            , justify: 'left'
                            , callback: u.identity
                        }
                    } )()
        ,   p
        ;

        for ( p in params ) cfg[ p ] = params[ p ];

        if ( 'font_units' in params ) cfg.font_size = params.font_units * unit;
        if ( 'font_size' in params ) cfg.font_size = params.font_size;

        vpadding = cfg.padding.t + cfg.padding.b;
        hpadding = cfg.padding.l + cfg.padding.r;

        function _min ( bbox, p ) {
            if ( bbox.length == 0 ) return -1;
            return Math.max.apply( null, bbox.map( u.item_getter( p ) ) );
        }

        function _update () {

            if ( $text.empty() ) return;

            var _
            ,   bbox
            ,   w
            ,   h
            ,   x
            ,   y
            ;

            bbox = $text[ 0 ].map( function ( e ) { return e.getBBox() } );

            w = width = Math.max( width, _min( bbox, 'width' ) + hpadding );
            h = _min( bbox, 'height' ) + vpadding;

            switch ( cfg.justify ) {
            case 'right':
                x = function () {
                        return w - this.getBBox().width - cfg.padding.r
                    };
                break;
            case 'center':
                x = function () {
                        return ( cfg.padding.l +
                                 ( w - hpadding - this.getBBox().width ) / 2 );
                    };
                break;
            default:
                x = cfg.padding.l;
                break;
            }

            y = voffset + cfg.padding.t;

            $text.attr( { x: x, y: y } );
            $rect.attr( { width: w, height: h } );

            return block;
        }

        function block ( $sel ) {
            $rect = $sel.append( 'rect' )
                        .classed( 'label-rect', true )
            ;

            $text = $sel.append( 'text' )
                        .classed( 'label-text', true )
                        .text( cfg.callback )
            ;

            $text.style( 'font-size', cfg.font_size );

            voffset = - $text.node().getBBox().y;

            return _update();
        }

        block.width = function ( _ ) {
            if ( !arguments.length ) return width;
            width = _;
            return _update();
        };

        return block;
    }

    function vstack ( $sel ) {
        if ( $sel.empty() || $sel.node().tagName !== 'g' ) return;

        $sel.classed( DUMMY_CLASS, true );
        $sel.each( function () {
            vstack( d3.select( this )
                      .selectAll( '.' + DUMMY_CLASS + ' > g' ) )
            ;
        } );
        $sel.classed( DUMMY_CLASS, false );

        var y = 0;
        $sel.attr( 'transform', function ( _, i ) {
            var ret = u.translate( 0, y );

            // subtracting 0.5 from the height for the y-increment prevents some
            // thin gaps that otherwise occur in some places (e.g in the p70S6K
            // node at { cell_line: 'LOXIMVI', timepoint_hr: 48 })

            y += this.getBBox().height - 0.5;

            return ret;
        } );
    }

    function center_g ( $g ) {
        var bbox = $g.node().getBBox();
        $g.attr( 'transform',
                 u.translate( - bbox.width / 2, - bbox.height / 2 ) );
    }

    function clippath_id () {
        var i = 0
        ,   fmt = d3.format( '02d' )
        ,   pfx = 'cp-'
        ;
        clippath_id = function () { return pfx + fmt( i++ ) };
        return clippath_id();
    }

    function make_node_frame ( data ) {
        var _
        ,   unattached_g = document.createElementNS( d3.ns.prefix.svg, 'g')
        ,   $node_frame = d3.select( unattached_g )
                            .classed( { 'node-frame': true } )
        ;

        if ( data !== undefined ) $node_frame.data( [ data ] );

        $node_frame.append( 'defs' );

        $node_frame
            .append( 'g' )
              .classed( { 'slots': true } );

        return $node_frame.node();
    }

    function center_node_frame ( $node_frame ) {
        var bbox = $node_frame.node().getBBox();
        $node_frame
              .attr( 'transform',
                     u.translate( - bbox.width / 2, - bbox.height / 2 ) );
    }

    function add_info ( d ) {

        var _
        ,   $node = d3.select( this )
        ,   label = d.data.label
        ,   RPPA_measurement = d.data.RPPA_measurement
        ;

        var _
        ,   $node_frame =
                d3.select( $node.node()
                           .appendChild(
                               make_node_frame(
                                   [ [ label ], RPPA_measurement ]
                               )
                           )
                         )

        ,   $node_info = $node_frame
                           .select( '.slots' )
                           .classed( { 'node-info': true } )

        ,   $slots = $node_info
                       .selectAll( '.slot' )
                       .data( u.identity ).enter()
                     .append( 'g' )
                       .attr( 'class',
                              function ( _, i ) {
                                  return i == 0 ? 'label' : 'info';
                              } )
                       .classed( { slot: true } )

        ,   $strips = $slots
                        .selectAll( '.strip' )
                        .data( u.identity ).enter()
                      .append( 'g' )
                        .classed( { strip: true } )
        ;

        ( function () {

            var blocks = [
                  textblock( { justify: 'center' } )
                           ( $node.selectAll( '.label .strip' ) )

                , textblock( { font_units: 3.2, callback: u.first } )
                           ( $node.selectAll( '.info .strip' ) )
            ];

            var w = Math.max.apply( null,
                                    blocks.map( u.thunk_getter( 'width' ) ) );
            blocks.forEach( function ( e ) { e.width( w ) } );

            vstack( $slots );


            // below we sort the $slots so that the .label slot comes
            // after in the DOM, and thus visually overlaps the .info
            // slot; otherwise the .info slot sometimes obscures the
            // .label slot's stroke

            function keyfunc ( d ) {
                return +( typeof( d[ 0 ] ) === 'string' );
            }

            $slots.sort( function ( a, b ) {
                return keyfunc( a ) - keyfunc( b );
            } );

        } )();

        center_node_frame( $node_frame );

        var _
        ,   cp_id = clippath_id()
        ,   bbox = $node_frame.node().getBBox()
        ;

        $node_frame
          .insert( 'rect', '.node-info.slots' )
            .attr( bbox )
            .classed( 'node-background', true )
            .style( 'fill', 'url(#striped)' );
        ;

        bbox.rx = CORNER_RADIUS;

        $node_frame
          .append( 'rect' )
            .attr( bbox )
            .classed( 'node-outline', true )
        ;

        $node_frame
            .select( 'defs' )
          .append( 'clipPath' )
            .attr( 'id', cp_id )
          .append( 'rect' )
            .attr( bbox )
        ;

        $node_info.attr( 'clip-path', 'url(#' + cp_id + ')' );

        $node.selectAll( '.info .label-rect' )
             .append( 'title' );

    }

    function build_app ( data ) {

        add_pickers( data.levels );

        build_heatmap( data );

        ( function () {
            var n = data.graph.nodes;
            data.graph.links.forEach( function ( l ) {
                if ( typeof l.source == 'number' ) l.source = n[ l.source ];
                if ( typeof l.target == 'number' ) l.target = n[ l.target ];
                l.hidden = l.source.hidden || l.target.hidden;
            } );
        } )();

        build_graph( data );

        var _
        ,   root = d3.select( '.svg-stage .root' )
        ,   node = root.selectAll( '.node' )
        ;

        /* ------------------------------------------------------------------ */

        root.selectAll( '.node:not(.labeled), .node.mutable' )
            .each(
                function ( d ) {
                    var $this = d3.select( this );
                    $this
                        .append( 'circle' )
                        .attr( 'r', 10 )
                    ;
                } );


        node.filter( '.mutable' ).each( add_info );

        /* ------------------------------------------------------------------ */

        [ 'x', 'y' ].forEach( function ( xy ) {

            var ex =
                d3.extent(
                    data.graph.nodes
                        .map( function ( n ) { return n[ xy ]; } )
                );

            SCALE[ xy ] =
                d3.scale
                  .linear()
                  .domain( u.pad_interval( ex, 0.1 ) )
            ;

        } );

        update_scale();


        d3.select( '.left-panel' )
          .append( 'div' )
          .attr( 'class', 'colorbar-panel' )
          .call( colorbar().scale( colors.color_scale )
                           .stepped( true )
                           .values( d3.range( -2.5, 4, 0.5 ) )
               );

        /* ------------------------------------------------------------------ */

        // extend colorbar to include "(na)"
        var g = d3.select( '.colorbar-panel svg' )
                .append( 'g' )
                  .attr( { transform: 'translate( 0, 215 )' } );

               g.append( 'g' )
                  .attr( { transform: 'translate( 27, 0 )' } )
                .append( 'rect' )
                  .attr( { width: '9',
                           height: '15',
                           fill: 'url(#striped)',
                           'shape-rendering': 'crispEdges',
                           'stroke-width': '1px',
                           stroke: '#ccc' } )
               ;

               g.append( 'g' )
                  .attr( { transform: 'translate( 23, 8.5 )' } )
                .append( 'text' )
                  .attr( {
                           'text-anchor': 'end',
                           'line-height': 'normal',
                           'dominant-baseline': 'middle'
                         } )
                  .text( '(na)' )
                ;

        /* ------------------------------------------------------------------ */

        $( '#loading' ).remove();
        d3.selectAll( '.while-loading' )
            .classed( { hidden: false,
                        'while-loading': false } );

        events.init();
    }

    function update_scale ( size ) {

        size = size || {};

        var _

        ,   scaling = ( size.scaling || 1 ) * BASE_SCALING

        ,   default_height = BASE_HEIGHT * scaling
        ,   default_width = BASE_WIDTH * scaling

        ,   height = size.height || default_height
        ,   width = size.width || default_width

        ,   svg = d3.select( '.svg-stage svg' )
        ,   root = svg.select( '.root' )
        ,   node = root.selectAll( '.node' )
        ,   link = root.selectAll( '.link' )
        ,   bbox
        ;

        svg
            .attr( 'width', width )
            .attr( 'height', height )
        ;

        SCALE.x.range( [ 0, width ] );
        SCALE.y.range( [ height, 0 ] );

        link.attr( 'x1', function ( d ) { return SCALE.x( d.source.x ) } )
            .attr( 'y1', function ( d ) { return SCALE.y( d.source.y ) } )
            .attr( 'x2', function ( d ) { return SCALE.x( d.target.x ) } )
            .attr( 'y2', function ( d ) { return SCALE.y( d.target.y ) } )
        ;

        node.attr( 'transform',
                   function ( d ) {
                       return u.translate( SCALE.x( d.x ), SCALE.y( d.y ) );
                   } );

        root.selectAll( '.node.labeled:not(.mutable)' )
            .each( add_label );

        // center graph
        bbox = root.node().getBBox();
        root.attr( 'transform',
                   u.translate( -bbox.x + ( width - bbox.width ) / 2,
                                -bbox.y + ( height - bbox.height ) / 2 ) );
    }

    function start () {

        d3.json( window.__STATIC_URL__ + 'cfg/vips/custom.json',
                 function ( error, custom_config ) {

            if ( error ) {
                if ( error.status != 403 &&
                     error.status != 404 ) throw error;
            }

            cfg._.update_config( custom_config );

            d3.json( cfg.data_path, function ( error, data ) {
                if ( error ) throw error;
                build_app( data );
            } );

        } );
    };

    return start;
}

);
