'use strict';
define(     [ 'd3' ],
    function ( d3 ) {

        var index_to_color =
                (
                    function () {
                        var mult = 360
                        ,   offset = 2/3
                        ,   step = Math.sqrt(5) - 2
                        ;
                        function h ( i ) {
                            return mult * ( ( offset + i * step ) % 1 );
                        }

                        return function ( i ) {
                            return d3.hsl( h( i ), 0.6, 0.6 ).toString();
                        };
                    }
                )()
        ;

        // ---------------------------------------------------------------------

        function retval () {

            var size = Infinity
            ,   start = 0
            ,   prefix = ''
            ,   format_string = '02d'
            ,   fmt = d3.format( format_string )

            ,   index = null
            ,   current_color = null
            ,   current_class = null
            ;

            function css_class ( pfx, i ) {
                return prefix + fmt( i % size );
            }

            function update () {
                current_color = index_to_color( index % size );
                current_class = css_class( prefix, index );
            }

            function server () { return current_color }

            // -----------------------------------------------------------------
            // accessors

            server.start = function ( _ ) {
                if ( !arguments.length ) return start;
                start = _;
                return server;
            };

            server.size = function ( _ ) {
                if ( !arguments.length ) return size;
                size = _;
                update();
                return server;
            };

            server.index = function ( _ ) {
                if ( !arguments.length ) return index;
                index = _;
                update();
                return server;
            };

            server.prefix = function ( _ ) {
                if ( !arguments.length ) return prefix;
                prefix = _;
                update();
                return server;
            };

            server.format = function ( _ ) {
                if ( !arguments.length ) return format_string;
                format_string = _;
                fmt = d3.format( format_string );
                update();
                return server;
            };

            // -----------------------------------------------------------------

            server.reset = function () { server.index( start ) };

            server.next = function () { server.index( index + 1 ); return current_color; };

            server.prev = function () { server.index( index - 1 ); return current_color; };

            server.css_class = function ( pfx, i ) {
                if ( !arguments.length ) return current_class;
                if ( pfx === undefined ) pfx = prefix;
                if ( i === undefined ) i = index;
                return css_class( pfx, i );
            };

            server.ith = function ( i ) { return index_to_color( i % size ) };

            // -----------------------------------------------------------------

            server.reset();

            return server;
        }

        return retval;
    }
);
