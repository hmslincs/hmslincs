define(['jquery', 'jqueryui'], function (jQuery, jqueryui) {

    module = {
        init: function(survey_id) {
/**
 * Create a download survey popup dialog that will serve a Qualtrics survey.
 */
jQuery(document).ready(
    function ($) {
        var DIALOG_TITLE_TEXT = 'HMS LINCS Database Download Survey';
        var SURVEY_HOST = 'https://hms.az1.qualtrics.com';
        var SURVEY_URL = SURVEY_HOST + '/SE/?SID=' + survey_id;
        var RETRY_INTERVAL = 3;
        var SHOW_ON_INITIAL = true;
        var COOKIE_NAME = 'hmsLINCSsurvey';
        var EXPIRES_ON = 'Fri, 31 Dec 9999 23:59:59 GMT';
        var COOKIE_PATTERN = new RegExp( COOKIE_NAME + "=([^;]+)", "i" );
        var FACILITY_ID_PATTERN = new RegExp( "datasets/(\\d+)/", "i" );
        var MAX_STORED_FACILITY_IDS = 20;
        var $dialog = $('#modal-download-dialog');
        
        if (survey_id
            && window.location.pathname.search(/.*\/results$/) != -1) 
        {
            $('#search_export').find('a').click(function(e) {
              // Firefox issue: 
              // The download event blocks the survey iframe from loading.
              // Prevent the default download event, and
              // send the download to a hidden frame.
              e.preventDefault();

              function parseUrl(link){
                var a = document.createElement('a');
                a.href = link;
                return a;
              };
              function isSameOrigin(link1, link2) {
                  return (parseUrl(link1).hostname === parseUrl(link2).hostname);
              };              
              if ( !isSameOrigin(window.location, e.target.href)){
                window.open(e.target.href);
              } else {
                var downloadIframe = document.getElementById('tempdownloadframe');
                if (!downloadIframe){
                  downloadIframe = document.createElement('iframe');
                  downloadIframe.id = 'tempdownloadframe';
                  downloadIframe.style.display = 'none';
                  document.getElementById('innercontent').appendChild(downloadIframe);
                }
                downloadIframe.src = e.target.href;
              }
              testSurveyCookie();
            });
        }
        
        /** Read the survey cookie and test for survey display conditions **/
        function testSurveyCookie() {
            var cookie = getCookie();
            if (cookie) {
                cookie.count = cookie.count+1;
                cookie.facilityIds = cookie.facilityIds + ',' + getFacilityId();
                if (cookie.allowRetry) {
                    setCookie(cookie.count, true, cookie.facilityIds);
                    if (cookie.count % RETRY_INTERVAL == 0) {
                        createSurvey(cookie.facilityIds);
                    }
                }
            }else{
                setCookie(1, true, getFacilityId());
                if (RETRY_INTERVAL==1 || SHOW_ON_INITIAL){
                  createSurvey(getFacilityId());
                }
            }
        }
        
        function createSurvey(facilityIds) {
            var url = SURVEY_URL + '&datasetIds=' + encodeURIComponent(facilityIds);
            var $dialog = $('#modal-dialog-div');
            
            if ($dialog.length == 0){
                $dialog = $('<div>', {id: 'modal-dialog-div'});
                $('<iframe>', {
                    frameborder: 0,
                    marginheight: 0,
                    marginwidth: 0,
                    src: url,
                }).css({width: '100%', height: '500px'}).appendTo($dialog);
                $dialog.appendTo($('#innercontent'));
            }
    
            window.addEventListener('message',function(event) {
                // Detect the survey completion event:
                // Note: cannot reliably detect the end-of-survey in our code;
                // instead, detect non-official "EOS" event from Qualtrics
                if (event.origin !== SURVEY_HOST) {
                    return;
                }
                else if (event.data &&
                         event.data.indexOf('QualtricsEOS|' + survey_id) >= 0) 
                {
                    turnOffCookie();
                    // Add a "close" button / remove the other buttons
                    var $button = $('<button>Close survey window</button>')
                        .button()
                        .click(function(){
                            $dialog.dialog('close');
                        });
                    $dialog.parent().find('.ui-dialog-buttonset')
                        .empty().append($button);
                }
            });
  
            $dialog.dialog({
                title: DIALOG_TITLE_TEXT,
                modal: true,
                resizable: false,
                width: '' + DIALOG_TITLE_TEXT.length + 'em',
                // height: 600,
                dialogClass: 'hmslincssurvey',
                position: {
                    my: 'center top', at: 'center top', of: this 
                },
                buttons: {
                    'Not now': function(e) {
                        $dialog.dialog('close');
                    },
                    "Don't ask me again": function(e) {
                        turnOffCookie();
                        $dialog.dialog('close');
                    }
                },
            });
            // Chrome (at least) focuses the first button on dialog creation,
            // which draws too much attention to it with our style. Blur it.
            $('.ui-button').blur()
        }
        
        function getFacilityId() {
            var match = window.location.pathname.match( FACILITY_ID_PATTERN );
            if (match) {
                return match[1];
            }else{
                console.log('no facilityIds found in the path! ', 
                    FACILITY_ID_PATTERN, window.location.pathname );
            }
            return null;
        }
  
        function getCookie() {
            var vals;
            var match = document.cookie.match( COOKIE_PATTERN );
            if (match) {
                vals = decodeURIComponent(match[1]).split('&');
                return {
                    count: parseInt(vals[0]),
                    allowRetry: parseInt(vals[1]),
                    facilityIds: vals[2]
                }
            }
            return null;
        }
        
        function turnOffCookie() {
            var cookie = getCookie();
            if (cookie) {
                setCookie(cookie.count,false,cookie.facilityIds);
            }else{
                setCookie(0,false, getFacilityId());
            }
        }
        
        function setCookie(count,allowRetry,facilityIds) {
            var facilityIds, cookieVal;
            facilityIds = facilityIds.split(',');
            if (facilityIds.length > MAX_STORED_FACILITY_IDS) {
                facilityIds = facilityIds.slice(
                    facilityIds.length-MAX_STORED_FACILITY_IDS);
            }
            facilityIds = facilityIds.join(',');
            cookieVal = encodeURIComponent(count + "&" + (allowRetry ? 1 : 0 ) 
                + "&" + facilityIds);
            document.cookie = ( 
                COOKIE_NAME + "=" + cookieVal + "; expires=" + EXPIRES_ON);
        }

        
        /** 
         * Utility function: provide a javascript text toggle.
         * - Included here for convenience.
         * - see the smallMoleculeDetail.html template for example usage.
         */
        (function collapsible_text_toggle() {
          $('.toggle_text_collapsed').click(function(e){
            $('.toggle_text_collapsed').toggle();
            $('.toggle_text_expanded').toggle();
          });
        })();
        
    }
);

        }
    };

    return module;

});
