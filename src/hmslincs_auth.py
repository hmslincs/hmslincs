import argparse
import logging
import requests
import re

from datetime import timedelta
from datetime import datetime

#import os
#import os.path as op
from urllib import unquote_plus


#_mydir = op.abspath(op.dirname(__file__))
#_djangodir = op.normpath(op.join(_mydir, '../django'))
#import sys
#sys.path.insert(0, _djangodir)
#import chdir as cd
#with cd.chdir(_djangodir):
#    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hmslincs_server.settings')
#del _mydir, _djangodir

__version__ = "$Revision: 24d02504e664 $"
# $Source$

# ---------------------------------------------------------------------------

#import setparams as _sg
#_params = dict(
#    VERBOSE = False,
#    APPNAME = 'db',
#)
#_sg.setparams(_params)
#del _sg, _params

# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)

#class EcommonsAthenticator(object):
def authenticate(ecommons_id, ecommons_password):
    """
    Authenticate against the settings ADMIN_LOGIN and ADMIN_PASSWORD.

    Use the login name, and a hash of the password. For example:

    ADMIN_LOGIN = 'admin'
    ADMIN_PASSWORD = 'sha1$4e987$afbcf42e21bd417fb71db8c66b321e9fc33051de'

 * Performs authentication of a user via an eCommons ID and password. Sends
 * an HTTP request to an HMS-hosted eCommons authentication server, using a <a
 * href="http://www.oasis-open.org/committees/tc_home.php?wg_abbrev=security">SAML</a>-inspired
 * format. See <a
 * href="https://wiki.med.harvard.edu/IT/RITG/AuthenticationWebService">HMS
 * Authentication Web Service Notes</a> for more details.
 * <p>
 * This code must be executed on a host with an IP address that is explicitly
 * registered with the eCommons authentication server (orchestra and trumpet are
 * approved).  You will also need a valid "issuer ID".
    """
    PATTERN_STATUS_CODE = r'.*<StatusCode>(\d+)</StatusCode'
    PATTERN_STATUS_CODE_CATEGORY = r'.*<StatusCodeCategory>(\w+)</StatusCodeCategory'
    PATTERN_STATUS_MESSAGE = r'.*<StatusMessage>([^<]+)</StatusMessage'

    url = 'https://authenticate.med.harvard.edu/wsAuthenticate.asp'
            
    authreq = """<AuthNRequest>
<RequestId>{9BA34ADF-287E-47CE-8F61-8795943FEC1C}</RequestId>
<Issuer>Orchestra_ATTR_CLIENT</Issuer>
<Signature>ExampleRequestSignature</Signature>
<IssueInstant>%s</IssueInstant>
<ValidityInterval>
<NotBefore>%s</NotBefore>
<NotAfter>%s</NotAfter>
</ValidityInterval>
<RequestApp>HMSLINCS</RequestApp>
<AuthNData>
<Id>%s</Id>
<Password>%s</Password>
</AuthNData>
</AuthNRequest>"""

    logger.info( 'Authenticating %s ...' % ecommons_id) 
    
    headers = {'Content-Type':'text/xml',
               'SOAPMethodName':'urn:myserver:AuthenticationReply#GetXIDAuthenticateResponse'}
    issue_instant = datetime.now()
    not_before = issue_instant  # 2012-10-14 11:00:26
    not_after = issue_instant + timedelta(days=7)
    prepared_req = authreq %(issue_instant, not_before, not_after, ecommons_id, ecommons_password)
    logger.info(str(('authreq',prepared_req)))
    r = requests.post(url, data=prepared_req, headers=headers, timeout=10 )
    if(r.status_code != 200): 
        raise Exception(str(('HTTP response', r.status_code, r)))

    logger.info('response')
    logger.info(r.text)
    matchObject = re.match(PATTERN_STATUS_CODE, r.text)
    if(matchObject):
        status=matchObject.group(1)
        if(status=='2000'):
            logger.info('successful authentication for ' + ecommons_id)
            return True
        else:
            logger.warn(str(('failed authentication', status,'ecommons_id', ecommons_id,
                             re.match(PATTERN_STATUS_CODE_CATEGORY,r.text).group(1),
                             unquote_plus(str(re.match(PATTERN_STATUS_MESSAGE,r.text).group(1))))))
            return False
    else:
        msg =str(('ecommons authentication request not recognized (cannot find the status, looking for the pattern)', r.text, PATTERN_STATUS_CODE))
        logger.error(msg)
        raise Exception(msg)

parser = argparse.ArgumentParser(description='Authenticate User')
parser.add_argument('-i', action='store', dest='id',
                    metavar='ID', required=True,
                    help='eCommons ID')
parser.add_argument('-p', action='store', dest='pw',
                    metavar='PW', required=True,
                    help='eCommons password')
parser.add_argument('-v', '--verbose', dest='verbose', action='count',
                help="Increase verbosity (specify multiple times for more)")    

if __name__ == "__main__":
    args = parser.parse_args()

    log_level = logging.WARNING # default
    if args.verbose == 1:
        log_level = logging.INFO
    elif args.verbose >= 2:
        log_level = logging.DEBUG
    # NOTE this doesn't work because the config is being set by the included settings.py, and you can only set the config once
    logging.basicConfig(level=log_level, format='%(msecs)d:%(module)s:%(lineno)d:%(levelname)s: %(message)s')        
    logger.setLevel(log_level)
    authenticate(args.id,args.pw)
