import argparse
import time
import logging
import os
import sys
from datetime import timedelta
from multiprocessing import Process
from django.db import transaction
from django.utils import timezone
from django.db.models import Q

from db.models import PubchemRequest
from hmslincs_server import settings

from hms.pubchem import PubchemError
from hms.pubchem.pubchem_compound_search import identity_similarity_substructure_search

__version__ = "$Revision: 24d02504e664 $"

logger = logging.getLogger('hms.pubchem.pubchem_database_cache_service')

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
        return query[0].id
    elif len(query)>1:
        msg = 'too many cached requests found, will delete them.'
        logger.info(str((msg, query)))
        query.delete();

    logger.info(str(('create pubchem request', kwargs)))
    pubchemRequest = PubchemRequest(**kwargs)
    pubchemRequest.save()
    return pubchemRequest.id;

#@transaction.commit_on_success
def service_database_cache():
    logger.debug('service db cache')
    for pqr in PubchemRequest.objects.filter(date_time_processing__exact=None):
        logger.info(str(('start process...')))
        pqr.date_time_processing = timezone.now()
        pqr.save()
        p = Process(target=pubchem_search,args=(pqr.id,) )
        # make the parent process wait: if set to true, then the parent process won't wait.  p.daemon = True
        p.start();
    logger.debug('servicing completed')
#    transaction.commit()
    
def service(loop_time_seconds=3, time_to_run=60):
    logger.debug(str(('service:', loop_time_seconds, time_to_run)))
    time_start = time.time()
    while time.time()-time_start < time_to_run:
        service_database_cache()
        time.sleep(loop_time_seconds)
    logger.debug(str(('service loop exit: run time (s): ', (time.time()-time_start))) )    
       
#@transaction.commit_on_success
def pubchem_search(request_id):  
    logger.info(str((os.getpid(),'conduct search for pending request',request_id)))
    pqr = PubchemRequest.objects.get(pk=int(request_id))
    logger.info(str((os.getpid(),'pending request:', pqr)))
    try:
        cids = identity_similarity_substructure_search(type=pqr.type, smiles=pqr.smiles, sdf=pqr.molfile)
        if(logger.isEnabledFor(logging.DEBUG)): 
            logger.debug(str((os.getpid(),'pubchem cids returned',cids, pqr.id)))
        pqr.cids = ','.join(str(x) for x in cids)
        pqr.date_time_fullfilled = timezone.now() #datetime.now()
        pqr.save()
    except PubchemError, e:
        logger.info(str((os.getpid(),'pubchem error reported',e)))
        # TODO: delete, but maybe cache for a day?
        pqr.pubchem_error_message = e.args
        pqr.date_time_fullfilled = timezone.now() #datetime.now()
        pqr.save()
    except Exception, e:
        # TODO: this is a program error, need to signal to the client that there is an error, but not to cache this result if the error is fixed
        logger.info(str((os.getpid(),'error reported',e))) 
        pqr.error_message = e.args
        pqr.date_time_fullfilled = timezone.now() #datetime.now()
        pqr.save()
#    finally:
#        transaction.commit()
        
#@transaction.commit_on_success
def clear_database_cache(days_to_cache=DAYS_TO_CACHE, 
                         seconds_to_cache=0, 
                         days_to_cache_errors=DAYS_TO_CACHE_ERRORS, 
                         seconds_to_cache_errors=0 ):
    logger.info(str(('purge cached errored pubchem requests:', timezone.now())))
    
    query = PubchemRequest.objects.filter(
        date_time_fullfilled__lt=(timezone.now()-timedelta(days=days_to_cache, seconds=seconds_to_cache)));
    logger.info(str(('clear cache, remove old fullfilled requests: ', len(query))))
    query.delete();
        
    # TODO: this may not be sufficient; how to purge pending requests?
    query = PubchemRequest.objects.filter(
        date_time_fullfilled__exact=None ).filter( 
        date_time_processing__lt=(timezone.now()-timedelta(days=days_to_cache, seconds=seconds_to_cache)));
    logger.info(str(('clear cache, remove old processing but unfullfilled requests: ', len(query))))
    query.delete();
    
    query = PubchemRequest.objects.filter(
            Q(error_message__isnull=False) | Q(pubchem_error_message__isnull=False)
        ).filter(date_time_fullfilled__lt=(
            timezone.now()-timedelta(days=days_to_cache_errors, seconds=seconds_to_cache_errors)));
    logger.info(str(('clear cache, remove old errored requests: ', len(query))))
    query.delete();
    transaction.commit()
    
parser = argparse.ArgumentParser(description='Pubchem database caching service')

parser.add_argument('-d', action='store', dest='days_to_cache',
                    metavar='DAYS_TO_CACHE', required=True, type=int, 
                    help='the number of days to cache a fullfilled request')
parser.add_argument('-de', action='store', dest='days_to_cache_errors',
                    metavar='DAYS_TO_CACHE_ERRORS', required=True, type=int, 
                    help='the number of days to cache an errored request (pubchem or system)')
parser.add_argument('-ds', action='store', dest='seconds_to_cache',
                    metavar='SECONDS_TO_CACHE', required=False, type=int, 
                    help='the number of seconds (in addition to the days) to cache a fullfilled request')
parser.add_argument('-des', action='store', dest='seconds_to_cache_errors',
                    metavar='SECONDS_TO_CACHE_ERRORS', required=False, type=int, 
                    help='the number of seconds (in addition to days) to cache an errored request (pubchem or system)')
parser.add_argument('-lt', action='store', dest='service_loop_time_s',
                    metavar='SERVICE_LOOP_TIME_SEC', required=True, type=int, 
                    help='Number of seconds between each check for new pending requests in the database')
parser.add_argument('-rt', action='store', dest='run_time_s',
                    metavar='RUN_TIME_SEC', required=True, type=int, 
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
    if args.verbose:
        # NOTE: when running with the django settings file, the logging configured there will augment this, and 
        # cause double logging. So this will manually override that.
        # Probably a better solution would be to configure this utility as a "management command"
        # and then let manage.py run it.  see: https://docs.djangoproject.com/en/1.4/howto/custom-management-commands/
        logging.basicConfig(level=log_level, format='%(msecs)d:%(module)s:%(lineno)d:%(levelname)s: %(message)s')   
        logger.setLevel(log_level)
    
    print 'run cache service', timezone.now()
    try:
        service(loop_time_seconds=args.service_loop_time_s, time_to_run=args.run_time_s);  
        
        kwargs = { 'days_to_cache':args.days_to_cache, 'days_to_cache_errors':args.days_to_cache_errors }
        if args.seconds_to_cache:
            kwargs['seconds_to_cache'] = args.seconds_to_cache
        if args.seconds_to_cache_errors:
            kwargs['seconds_to_cache_errors'] = args.seconds_to_cache_errors
        clear_database_cache(**kwargs)
    except Exception, e:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]      
        logger.error(str((exc_type, fname, exc_tb.tb_lineno)))
        logger.error(str(('in structure search', e)))
        raise e
    print 'exit cache service', timezone.now()
