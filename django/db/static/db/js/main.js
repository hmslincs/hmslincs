define(['jquery', 'jqueryui'], function (jQuery, jqueryui) {

/**
 * Create a download survey popup dialog that will serve a Qualtrics survey.
 * The 'QUALTRICS_SURVEY_ID' template variable should be set in the Django view.
 */
jQuery(document).ready(
    function ($) {
        var DIALOG_TITLE_TEXT = 'Please answer a survey about your data usage:';
        var SURVEY_HOST = 'https://hms.az1.qualtrics.com';
        var SURVEY_URL = SURVEY_HOST + '/SE/?SID=' + QUALTRICS_SURVEY_ID;
        var RETRY_INTERVAL = 3;
        var SHOW_ON_INITIAL = true;
        var COOKIE_NAME = 'hmsLINCSsurvey';
        var EXPIRES_ON = 'Fri, 31 Dec 9999 23:59:59 GMT';
        var COOKIE_PATTERN = new RegExp( COOKIE_NAME + "=([^;]+)", "i" );
        var FACILITY_ID_PATTERN = new RegExp( "datasets/(\\d+)/", "i" );
        var MAX_STORED_FACILITY_IDS = 20;
        var $dialog = $('#modal-download-dialog');
        
        if (QUALTRICS_SURVEY_ID 
            && window.location.pathname.search(/.*\/results$/) != -1) 
        {
            $('#search_export').find('a').click(function(e) {
              // Firefox issue: 
              // The download event blocks the survey iframe from loading.
              // Prevent the default download event, and
              // send the download to a hidden frame.
              e.preventDefault();
              document.getElementById('hiddenDownloadiFrame').src = e.target.href;
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
            var $dialog = $('#modal-download-dialog');
            var url = SURVEY_URL + '&datasetIds=' + encodeURIComponent(facilityIds);
            var iframe_html = document.createElement('iframe');
            iframe_html.src = url;
            iframe_html.setAttribute('frameborder',0);
            iframe_html.setAttribute('marginheight',0);
            iframe_html.setAttribute('marginwidth',0);
            iframe_html.style.width = '100%';
            iframe_html.style.height = '500px';
            $dialog.html(iframe_html);
    
            window.addEventListener('message',function(event) {
                // Detect the survey completion event:
                // Note: cannot reliably detect the end-of-survey in our code;
                // instead, detect non-official "EOS" event from Qualtrics
                if (event.origin !== SURVEY_HOST) {
                    return;
                }
                else if (event.data &&
                         event.data.indexOf('QualtricsEOS|' + QUALTRICS_SURVEY_ID) >= 0) 
                {
                    // Add a "close" button / remove the other buttons
                    var $button = $('<button>', {
                      type: 'button',
                      class: 'ui-button ui-widget ui-state-default ui-corner-all ui-button-text-only',
                      role: 'button' });
                    var $buttonSet = $dialog.parent().find('.ui-dialog-buttonset');
                    $button.html('<span class="ui-button-text">Close</span>');

                    $button.click(function(){
                      $dialog.dialog('close');
                    });
                    turnOffCookie();
                    $buttonSet.empty();
                    $buttonSet.append($button);
                }
            });
  
            $dialog.dialog({
                title: DIALOG_TITLE_TEXT,
                modal: true,
                resizable: false,
                width: '' + DIALOG_TITLE_TEXT.length + 'em',
                dialogClass: 'hmslincssurvey',
                position: {
                    my: 'center top', at: 'center top', of: this 
                },
                buttons: {
                    'Not Now': function(e) {
                        $dialog.dialog('close');
                    },
                    "Don't ask again": function(e) {
                        turnOffCookie();
                        $dialog.dialog('close');
                    }
                },
                open: function (event, ui) {
                    $(this).before($(this).parent().find('.ui-dialog-buttonpane'));
                }                
            });
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
    }
);

});
