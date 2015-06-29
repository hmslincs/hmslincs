'use strict';
define(    [  'hmslincs/picker', 'hmslincs/utils', 'jquery', 'd3' ],
    function ( picker          ,  u              ,  $      ,  d3 ) {

        return function ( levels ) {

            // FIXME: the fixes to levels done by the following assignment
            // should not be necessary; the JSON upload should already by in the
            // desired form
            levels = levels.map( function ( l ) {
                return {   context: u.to_identifier( l[ 0 ] )
                         , content: { title: l[ 0 ],
                                      items: l[ 1 ],
                                      initial_value: l[ 2 ] }
                       }
            } )

            var _
            ,   context_class = u.item_getter( 'context' )
            ,   titles = levels.map( u.first )
            ,   level_sets = levels.map( u.second )
            ,   pickers = {}

            ,   $ul = d3.select( '.left-panel' )
                        .selectAll( '.list-container' )
                        .data( levels ).enter()
                      .append( 'div' )
                        .classed( { 'list-container': true,
                                    hidden: true,
                                    'while-loading': true } )
                      .append( 'ul' )
                        .attr( 'class', context_class )
            ,   $li
            ;

            $ul.append( 'div' )
                .classed( 'title', true )
                .html( u.item_getter( 'content', 'title' ) )
            ;

            $li = $ul.selectAll( 'li' )
                     .data( function ( d ) {
                         return d.content.items.map( function ( e ) {
                             return { context: d.context, content: e };
                         } );
                     } ).enter()
                   .append( 'li' )
                     .attr( 'class', context_class )
                     .classed( 'item', true )
                     .html( function ( d ) { return d.content } );
            ;
        }
    }

);
