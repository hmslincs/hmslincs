import argparse
from datetime import timedelta
import logging
from multiprocessing import Process


__version__ = "$Revision: 24d02504e664 $"

## ---------------------------------------------------------------------------
#import os
#import setparams as _sg
#
#_params = dict(
#    VERBOSE = False,
#    APPNAME = 'db',
#)
#_sg.setparams(_params)
#del _sg, _params
#
#from os import path
#_mydir = path.abspath(path.dirname(__file__))
#_djangodir = path.normpath(path.join(_mydir, '../django'))
#import sys
#sys.path.insert(0, _djangodir)
#sys.path.insert(0, _mydir)
#
#import chdir as cd
#with cd.chdir(_djangodir):
#    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hmslincs_server.settings')
#del _mydir, _djangodir
#
## ---------------------------------------------------------------------------

#with chdir.chdir('../../../django'):
#os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hmslincs_server.settings')

from db.models import PubchemRequest
from django.utils import timezone
from django.db.models import Q

from hms.pubchem import PubchemError
from hms.pubchem.pubchem_compound_search import identity_similarity_substructure_search


logger = logging.getLogger(__name__)

PUBCHEM_BASE_URL = 'http://pubchem.ncbi.nlm.nih.gov/rest/pug/'


KEY_CANONICAL_SMILES = 'CanonicalSMILES'
KEY_CID = 'CID'
KEY_MOLECULAR_FORMULA = 'MolecularFormula'
KEY_INCHI_KEY = 'InChIKey'


OUTPUT_FORMAT = 'JSON'

DAYS_TO_CACHE = 10
DAYS_TO_CACHE_ERRORS = 1




def submit_search(smiles='', molfile='', type='identity'):
    if smiles and molfile:
        msg = 'Cannot have both smiles and sdf inputs'
        logger.error(str((msg, smiles, molfile)))
        raise PubchemError(msg)
    
    kwargs = { 'smiles':smiles, 'molfile':molfile, 'type':type }
    query = PubchemRequest.objects.filter(**kwargs)
    
    if len(query)==1 :
        logger.info(str(('found cached request', query[0])))
        return query[0]
    elif len(query)>1:
        msg = 'too many cached requests found, will delete them.'
        logger.info(str((msg, query)))
        query.delete();

    logger.info(str(('create pubchem request', kwargs)))
    pubchemRequest = PubchemRequest(**kwargs)
    pubchemRequest.save()
    return pubchemRequest.id;

def service_database_cache():
    for pqr in PubchemRequest.objects.filter(date_time_fullfilled__exact=None):
        logger.info(str(('start process...')))
        p = Process(target=pubchem_search,args=(pqr.id,) )
        p.daemon = True
        p.start();
    logger.info('servicing completed')
    
import time
def service(loop_time_seconds=3, time_to_run=60):
    time_start = time.time()
    while time.time()-time_start < time_to_run:
        service_database_cache()
        time.sleep(loop_time_seconds)
    logger.info(str(('service loop exit: run time (s): ', (time.time()-time_start))) )    
        
        
def pubchem_search(request_id):  
    logger.info(str(('conduct search for pending request',request_id)))
    pqr = PubchemRequest.objects.get(pk=int(request_id))
    logger.info(str(('pending request:', pqr)))
    try:
        cids = identity_similarity_substructure_search(type=pqr.type, smiles=pqr.smiles, sdf=pqr.molfile)
        if(logger.isEnabledFor(logging.DEBUG)): 
            logger.debug(str(('pubchem cids returned',cids, pqr.id)))
        pqr.cids = ','.join(str(x) for x in cids)
        pqr.date_time_fullfilled = timezone.now() #datetime.now()
        pqr.save()
    except PubchemError, e:
        logger.info(str(('pubchem error reported',e)))
        # TODO: delete, but maybe cache for a day?
        pqr.pubchem_error_message = e.args
        pqr.date_time_fullfilled = timezone.now() #datetime.now()
        pqr.save()
    except Exception, e:
        # TODO: this is a program error, need to signal to the client that there is an error, but not to cache this result if the error is fixed
        logger.info(str(('error reported',e))) 
        pqr.error_message = e.args
        pqr.date_time_fullfilled = timezone.now() #datetime.now()
        pqr.save()

def clear_database_cache(days_to_cache=DAYS_TO_CACHE, 
                         seconds_to_cache=0, 
                         days_to_cache_errors=DAYS_TO_CACHE_ERRORS, 
                         seconds_to_cache_errors=0 ):
    logger.info(str(('purge cached errored pubchem requests:', timezone.now())))
    query = PubchemRequest.objects.filter(
        date_time_fullfilled__lt=(timezone.now()-timedelta(days=days_to_cache, seconds=seconds_to_cache)));
    logger.info(str(('clear cache, remove old fullfilled requests: ', len(query))))
    query.delete();
    
    query = PubchemRequest.objects.filter(
        Q(error_message__isnull=False) | Q(pubchem_error_message__isnull=False)
        ).filter(date_time_fullfilled__lt=(
        timezone.now()-timedelta(days=days_to_cache_errors, seconds=seconds_to_cache_errors)));
    logger.info(str(('clear cache, remove old errored requests: ', len(query))))
    query.delete();
    
parser = argparse.ArgumentParser(description='Pubchem database caching service')

parser.add_argument('-d', action='store', dest='days_to_cache',
                    metavar='DAYS_TO_CACHE', required=True, type=int, 
                    help='the number of days to cache a fullfilled request')
parser.add_argument('-de', action='store', dest='days_to_cache_errors',
                    metavar='DAYS_TO_CACHE_ERRORS', required=True, type=int, 
                    help='the number of days to cache an errored request (pubchem or system)')
parser.add_argument('-lt', action='store', dest='service_loop_time_s',
                    metavar='SERVICE_LOOP_TIME', required=True, type=int, 
                    help='Number of seconds between each check for new pending requests in the database')
parser.add_argument('-rt', action='store', dest='run_time_s',
                    metavar='RUN_TIME', required=True, type=int, 
                    help='Number of seconds to run and then exit')

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
    
    service(loop_time_seconds=args.service_loop_time_s, time_to_run=args.run_time_s);    
    clear_database_cache(days_to_cache=args.days_to_cache,days_to_cache_errors=args.days_to_cache_errors)

