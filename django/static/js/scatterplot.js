'use strict';
define(     [ 'd3', 'utils' ],
    function ( d3 ,  u ) {

        function retval () {

            var margin = { top: 20, right: 20, bottom: 30, left: 40 }

            ,   iWidth = 500
            ,   iHeight = 500

            ,   oWidth = iWidth + margin.left + margin.right
            ,   oHeight = iHeight + margin.bottom + margin.top

            ,   xValue = u.first
            ,   yValue = u.second

            ,   xScale = d3.scale.linear()
            ,   yScale = d3.scale.linear()

            ,   xAxis = d3.svg.axis()
                              .scale( xScale )
                              .orient( 'bottom' )
                              .tickSize( 6, 0 )

            ,   yAxis = d3.svg.axis()
                              .scale( yScale )
                              .orient( 'left' )
                              .tickSize( 6, 0 )

            ,   plotRange = { x: null, y: null }

            ,   axisLabel = { x: null, y: null }

            ,   plotTitle = null

            ,   symbol = d3.svg.symbol().type( 'circle' )

            ;

            function update_plot_range ( data ) {
                if ( plotRange.x !== null && plotRange.y !== null ) { return; }

                var xys = data.map( function ( d, i ) {
                                        return [ xValue.call( data, d, i ),
                                                 yValue.call( data, d, i ) ];
                                    } );

                if ( plotRange.x === null ) {
                    plotRange.x = d3.extent( xys, u.first );
                }

                if ( plotRange.y === null ) {
                    plotRange.y = d3.extent( xys, u.second );
                }
            }

            function chart ( selection ) {

                selection.each( function ( data ) {

                    var parent = d3.select( this )
                                   .attr( 'width', oWidth )
                                   .attr( 'height', oHeight )
                    ,   $top_g = parent.append( 'g' )
                                       .attr( 'class', 'scatterplot' )
                                       .attr( 'transform',
                                              u.translate( margin.left, margin.top ) )
                    ,   top_g = $top_g.node()
                    ;

                    // compute scaling
                    update_plot_range( data );

                    xScale.range( [ 0, iWidth ] )
                          .domain( plotRange.x ).nice();

                    yScale.range( [ iHeight, 0 ] )
                          .domain( plotRange.y ).nice();

                    // add title
                    if ( plotTitle !== null ) {
                        $top_g.append( 'text' )
                              .text( plotTitle )
                              .style( 'text-anchor', 'middle' )
                              .attr( 'class', 'scatterplot-title' )
                              .attr( 'x', u.average( xScale.range() ) );
                    }

                    // ---------------------------------------------------------
                    // add axes
                    var axes = $top_g.append( 'g' )
                                     .attr( 'class', 'axes' )

                    ,   xaxis = axes.append( 'g' )
                                    .attr( 'class', 'x axis' )
                                    .attr( 'transform',
                                           u.translate( 0, yScale.range()[ 0 ] ) )
                                    .call( xAxis )

                    ,   yaxis = axes.append( 'g' )
                                     .attr( 'class', 'y axis' )
                                     .call( yAxis );

                    if ( axisLabel.x !== null ) {
                        xaxis.append( 'text' )
                             .text( axisLabel.x )
                             .style( 'text-anchor', 'middle' )
                             .attr( 'class', 'x-axis-label' )
                             .attr( 'y', margin.bottom / 2 )
                             .attr( 'dy', '1.5ex' )
                             .attr( 'x', u.average( xScale.range() ) );
                    }

                    if ( axisLabel.y !== null ) {
                        yaxis.append( 'text' )
                             .attr( 'transform', 'rotate(-90)' )
                             .text( axisLabel.y )
                             .style( 'text-anchor', 'middle' )
                             .attr( 'class', 'y-axis-label' )
                             .attr( 'y', -20 )
                             .attr( 'dy', '-0.5ex' )
                             .attr( 'x', -u.average( yScale.range() ) );
                    }


                    // ---------------------------------------------------------
                    var $plot = $top_g.append( 'g' )
                                      .attr( 'class', 'plot-region' );

                    $plot.append( 'rect' )
                         .attr( 'width', xScale.range()[ 1 ] )
                         .attr( 'height', yScale.range()[ 0 ] )
                         .style( { stroke: 'none', 'fill-opacity': 0 } );

                    // add points
                    $plot.append( 'g' )
                         .attr( 'class', 'point-set' )
                         .selectAll( '.point' )
                         .data( data )
                       .enter()
                         .append( 'g' )
                         .attr( 'class', 'point' )

                         .attr( 'transform',
                                function ( d, i ) {
                                    return u.translate( xScale( xValue( d, i ) ),
                                                        yScale( yValue( d, i ) ) );
                                } )

                         .append( 'path' )
                         .attr( 'd', symbol );

                    top_g.invert_x = xScale.invert;
                    top_g.invert_y = yScale.invert;

                } );

            }

            // -----------------------------------------------------------------
            // accessors

            chart.margin = function ( _ ) {
                if ( !arguments.length ) return Object.create( margin );
                for ( var p in margin ) {
                    if ( p in _ ) {
                        margin[ p ] = _[ p ];
                    }
                }
                return chart;
            };

            chart.width = function ( _ ) {
                if ( !arguments.length ) return oWidth;
                oWidth = _;
                iWidth = _ - margin.left - margin.right;
                return chart;
            };

            chart.height = function ( _ ) {
                if ( !arguments.length ) return oHeight;
                oHeight = _;
                iHeight = _ - margin.top - margin.bottom;
                return chart;
            };

            chart.x = function ( _ ) {
                if ( !arguments.length ) return Object.create( xValue );
                xValue = _;
                return chart;
            };

            chart.y = function ( _ ) {
                if ( !arguments.length ) return Object.create( yValue );
                yValue = _;
                return chart;
            };

            chart.pointStyle = function ( _ ) {
                if ( !arguments.length ) return Object.create( pointStyle );
                var sym = _.symbol
                ,   callback = ( sym || {} ).call && sym
                ,   size = _.size
                ;

                if ( sym ) {
                    symbol = callback || d3.svg.symbol().type( sym );
                }

                if ( size && !callback ) {
                    symbol.size( size * size );
                }

                return chart;
            };

            chart.plotRange = function ( _ ) {
                if ( !arguments.length ) return Object.create( plotRange );
                if ( 'x' in _ ) { plotRange.x = _.x; }
                if ( 'y' in _ ) { plotRange.y = _.y; }
                return chart;
            };

            chart.axisLabel = function ( _ ) {
                if ( !arguments.length ) return Object.create( axisLabel );
                if ( 'x' in _ ) { axisLabel.x = _.x; }
                if ( 'y' in _ ) { axisLabel.y = _.y; }
                return chart;
            };

            chart.plotTitle = function ( _ ) {
                if ( !arguments.length ) return plotTitle;
                plotTitle = _;
                return chart;
            };

            // -----------------------------------------------------------------

            return chart;
        }

        return retval;
    }
);
