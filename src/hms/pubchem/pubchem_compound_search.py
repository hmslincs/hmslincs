import argparse
import logging
import requests
import re

from datetime import timedelta
from datetime import datetime

import time
import json

#import os
#import os.path as op


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

PUBCHEM_BASE_URL = 'http://pubchem.ncbi.nlm.nih.gov/rest/pug/'


KEY_CANONICAL_SMILES = 'CanonicalSMILES'
KEY_CID = 'CID'
KEY_MOLECULAR_FORMULA = 'MolecularFormula'
KEY_INCHI_KEY = 'InChIKey'


OUTPUT_FORMAT = 'JSON'
DEFAULT_TIMEOUT = 10
DEFAULT_MAX_WAIT = 30
DEFAULT_INITIAL_WAIT = 3
DEFAULT_TRIES = 6

from hms.pubchem import PubchemError

def identity_exact_search(smiles='', sdf='', timeout=DEFAULT_TIMEOUT):
    """
    returns a list of cids found for the smiles identity search
    NOTE: it's not clear from the pug REST documentation what this search is exactly.
    It is similar to the "identity" search /pug/compound/identity, but this search 
    is synchronous, and does not always match to our database.  Therefore, I am 
    calling it the "identity exact" match.  For now, we will not use it from the UI. - sde4
    """
    
    url = PUBCHEM_BASE_URL
    url += 'compound/' # + quote(smiles)
    if smiles and sdf:
        raise PubchemError('This function accepts either smiles or sdf arguments')
    
    if smiles:
        payload = { 'smiles': smiles }
        url += 'smiles'
        url += '/cids/' + OUTPUT_FORMAT
    if sdf:
        url += 'sdf/'
        logger.info(str(('sdf',sdf)))
        url +=  'cids/' + OUTPUT_FORMAT
    logger.info(str(('url:',url)))
    try:
        if(sdf != ''):
            r = requests.post(url, files=sdf, timeout=timeout )
        else:
            r = requests.post(url, data=payload, timeout=timeout )
    except Exception, e:
        logger.error(str(('exception recorded while contacting pubchem server', e)))
        raise e
    if(r.status_code != 200): 
        raise PubchemError(json.dumps(r.json)) 
    logger.info(str(('recieved from pubchem: ', r.text)))
    results = json.loads(r.text)
    key1 = 'IdentifierList'
    key2 = 'CID'
    if(results.has_key(key1)):
        if(results[key1].has_key(key2)):
            return results[key1][key2]

def sid_search(sids='', timeout=DEFAULT_TIMEOUT):
    """
    returns a list of two-tuples of the form: [(sid_input, cid_reported)]
    """
    url = PUBCHEM_BASE_URL
    if(sids != ''):
        url += 'substance/' # + quote(smiles)
        payload = {'sid': sids }
        url += 'sid'
        url += '/cids/' + OUTPUT_FORMAT
        try:
            r = requests.post(url, data=payload, timeout=timeout )
        except Exception, e:
            logger.error(str(('exception recorded while contacting pubchem server', e)))
            raise e
        if(r.status_code != 200): 
            raise PubchemError(str(('HTTP response', r.status_code, json.dumps(r.json) ))) 

        results = json.loads(r.text)
        key1 = 'InformationList'
        key2 = 'Information'
        cid_key = 'CID'
        sid_key = 'SID'
        if(results.has_key(key1)):
            if(results[key1].has_key(key2)):
                return zip( [x[sid_key] for x in results[key1][key2]],
                            map(lambda x: x[cid_key] if x.has_key(cid_key) else '',results[key1][key2]))
#                return map(lambda x: x[cid_key],filter(lambda x:x.has_key(cid_key), results[key1][key2]) )


def identity_similarity_substructure_search(smiles='',sdf='', type='identity', timeout=DEFAULT_TIMEOUT, max_wait_s=DEFAULT_MAX_WAIT, tries_till_fail=DEFAULT_TRIES):
    """
    queries the pubchem database for a compound by either identity, similarity, or substructure similarity
    
    param - type - one of [similarity,substructure]
    
    NOTE: see http://pubchem.ncbi.nlm.nih.gov/pug_rest/PUG_REST.html

    """
# TODO:    returns a list of cids found for the smiles substructure search
    
    url = PUBCHEM_BASE_URL
    url += 'compound/'
    url += type + '/';
    if smiles and sdf:
        raise PubchemError('This function accepts either smiles or sdf arguments')
    
    if smiles:
        payload = { 'smiles': smiles }
        url += 'smiles/'
    if sdf:
        url += 'sdf/'
    url += OUTPUT_FORMAT
    if type=='identity':
        url += '?identity_type=same_tautomer' # TODO: incorporate identity_type in the UI
    logger.info(str(('query url',url )))
    try:
        if(sdf != ''):
            r = requests.post(url, files=sdf, timeout=timeout )
        else:
            r = requests.post(url, data=payload, timeout=timeout )
    except Exception, e:
        logger.error(str(('exception recorded while contacting pubchem server', e)))
        raise e
    if(r.status_code != 200): 
        raise PubchemError(str(('HTTP response', r.status_code, json.dumps(r.json) ))) 
    # TODO: how to put a dict in the exception and then use it later in the UI
    #logger.info(r.text)
    results = json.loads(r.text)
    logger.info(str(('initial request result', results)))
    
    if (results.has_key('Waiting')):
        list_key = results['Waiting']['ListKey']
        logger.info(str(('pubchem listKey received: ', list_key)))

        begin_time = datetime.now()
#        url = PUBCHEM_BASE_URL + 'compound/listkey/'+ list_key + '/property/MolecularFormula,InChIKey,CanonicalSMILES/' + OUTPUT_FORMAT
        url = PUBCHEM_BASE_URL + 'compound/listkey/'+ list_key + '/cids/' + OUTPUT_FORMAT
        
        wait_s = DEFAULT_INITIAL_WAIT
        time.sleep(wait_s)
        r = requests.post(url, timeout=timeout )
        if(r.status_code != 200): 
            raise PubchemError(str(('HTTP response', r.status_code, r)))
        results = json.loads(r.text)
        
        tries = 1
        time.sleep(wait_s)
        
        while(results.has_key('Waiting')):
            if(tries != 1 and wait_s < max_wait_s):
                wait_s += 3
            time.sleep(wait_s)
            logger.info(str(('checked pubchem listkey', list_key, 'tries', tries, 'elapsed', (datetime.now()-begin_time).seconds, 'seconds')))
            r = requests.post(url, timeout=timeout )
            if(r.status_code != 200): 
                raise PubchemError(str(('HTTP response', r.status_code, r)))
        
            results = json.loads(r.text)
            tries += 1
            if (tries > tries_till_fail):
                raise PubchemError(str(('maximum allowed tries reached', tries)))
            
        logger.info(str(('pubchem results returned, interval', 
                         (datetime.now()-begin_time).seconds, 'seconds' )))  # note timedelta has days, seconds, microseconds

        key1 = 'IdentifierList'
        key2 = 'CID'
        if(results.has_key(key1)):
            if(results[key1].has_key(key2)):
                return results[key1][key2]
    else:
        raise PubchemError(str(('unknown response:', results)))
        

parser = argparse.ArgumentParser(description='Pubchem Similarity Search')
parser.add_argument('-s', action='store', dest='smiles',
                    metavar='SMILES', required=True,
                    help='Smiles string of the substructure')

parser.add_argument('-t', action='store', dest='type',
                    metavar='TYPE', required=True,
                    choices=('identity','substructure'),
                    help='search for <identity|substructure>')

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
    
    search_params = { 'smiles' : args.smiles }
    
    if(args.type == 'identity'):
        results = identity_exact_search(**search_params)
        print 'results', len(results), results
    elif(args.type == 'substructure'):
        results = identity_similarity_substructure_search(**search_params)
        print 'results', len(results), results
    else:
        print 'unknown type option', args.type