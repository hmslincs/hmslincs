'use strict';

define(

        [ 'jquery', 'd3', 'config', 'common', 'adjust_css', 'add_pickers', 'load_plots', 'events' ],

function ( $      ,  d3 ,  cfg    ,  c      ,  adjust_css ,  add_pickers ,  load_plots ,  events ) {

    function load_json ( path, handler ) {
        d3.json( path, function ( error, json ) {
            if ( error ) throw error;
            handler( json );
        } );
    }

    function build_app ( data ) {

        load_plots( data );

        var picker =
        add_pickers( data );

        events.init();

        [ 'C32', 'WM115' ].forEach( picker.Cell_line.pick );

        [

          'Viability',
          'p-Histone H3(S10)',
          'p27 Kip1',
          'p-AKT(S473)',
          'pERK(T202/Y204)',
          'Bim',
          'Total c-Jun',
          'p-S6(S235/236)',
          'pMEK(S217/221)'

        ].forEach( picker.RPPA_measurement.pick );

        adjust_css( data );

        $( '#loading' ).remove();
        $( '.hidden.while-loading' )
            .removeClass( 'hidden' )
            .removeClass( 'while-loading' )
        ;
    }

    function start () {

        d3.json( window.__STATIC_URL__ + 'cfg/plsr_loadings/custom.json',
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
