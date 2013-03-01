"""
"""
import time

from django.test import TestCase
from django.utils import timezone

from db.models import SmallMolecule
from db.models import PubchemRequest
from hms.pubchem import pubchem_database_cache_service

import logging


"""
About testing:

From: https://docs.djangoproject.com/en/dev/topics/testing/overview/s
The test database
Tests that require a database (namely, model tests) will not use your "real"
(production) database. Separate, blank databases are created for the tests.

Regardless of whether the tests pass or fail, the test databases are destroyed 
when all the tests have been executed.

By default the test databases get their names by prepending test_ to the value 
of the NAME settings for the databases defined in DATABASES. When using the 
SQLite database engine the tests will by default use an in-memory database 
(i.e., the database will be created in memory, bypassing the filesystem entirely!). 
If you want to use a different database name, specify TEST_NAME in the dictionary 
for any given database in DATABASES.

Aside from using a separate database, the test runner will otherwise use all of
the same database settings you have in your settings file: ENGINE, USER, HOST, 
etc. The test database is created by the user specified by USER, so you'll need
to make sure that the given user account has sufficient privileges to create a
new database on the system.
"""

logger = logging.getLogger(__name__)

class PubchemSearchTest(TestCase):

    
    def setUp(self):
        pass


    def tearDown(self):
        pass


    def testSubmitSearch(self):
        """
        Accomplishes 3 things:
        - submit items to the queue (db), and process them
        - process items in the queue    
        - clear items from the queue:
        -- fullfilled if age x
        -- errored if age y
        """
        
        logger.info('start testSubmitSearch')
        kwarg_tuple = ( 
            { 'smiles': 'CC(N1C=NC2=C1N=C(N[C@H](CC)CO)N=C2NCC3=CC=CC=C3)C', 'type':'identity' },
            { 'smiles': 'CC(N1C=NC2=C1N=C(N[C@H](CC)CO)N=C2NCC3=CC=CC=C3)C', 'type':'similarity' },
            { 'smiles': 'CC(N1C=NC2=C1N=C(N[C@H](CC)CO)N=C2NCC3=CC=CC=C3)C', 'type':'substructure' },)
        ids = []      
        for kwargs in kwarg_tuple:          
            search_request_id = pubchem_database_cache_service.submit_search(**kwargs)
            logger.info(str(('request submitted', search_request_id)))
            request = PubchemRequest.objects.get(pk=int(search_request_id));
            self.assertIsNotNone(request, str(('submitted search was not cached',kwargs)))
            ids.append(search_request_id)
        logger.info('service (search on) items in the cache');
        pubchem_database_cache_service.service_database_cache()
        
        logger.info('sleep for 5 seconds')
        time.sleep(5)
        all_satisfied = False;
        tries = 0
        while not all_satisfied and tries < 20 :
            all_satisfied = True;
            for id in ids:
                request = PubchemRequest.objects.get(pk=int(search_request_id));
                if request.date_time_fullfilled:
                    logger.info(str(('pubchem request fullfilled', request)))
                else:
                    logger.info(str(('pubchem request not fullfilled', request)))
                    all_satisfied = False;
            logger.info('sleep for 3 seconds')
            time.sleep(3)
            tries += 1
        self.assertTrue(all_satisfied, 'All searches were not satisified')
        
        # test some clearing

        time1 = time.time()
        ids2 = []
        # create a good one, that will not be purged
        kwarg = { 'smiles': 'ClC1=CC(NC2=NC=CC(C3=CC=NC(NCCCO)=C3)=N2)=CC=C1', 'type':'identity' };
        search_request_id = pubchem_database_cache_service.submit_search(**kwarg);
        ids2.append(search_request_id)
        # create an errored one, that will be purged
        kwarg = { 'smiles': '000))))ClC1=CC(NC2=NC=CC(C3=CC=NC(NCCCO)=C3)=N2)=CC=C1', 'type':'identity' };
        tempid = pubchem_database_cache_service.submit_search(**kwarg);
        ids2.append(tempid)
        logger.info('2nd time: service (search on) items in the cache');
        pubchem_database_cache_service.service_database_cache()
        
        all_satisfied = False;
        tries = 0
        while not all_satisfied and tries < 20 :
            all_satisfied = True;
            for id in ids2:
                request = PubchemRequest.objects.get(pk=int(search_request_id));
                if request.date_time_fullfilled:
                    logger.info(str(('pubchem request fullfilled', request)))
                else:
                    logger.info(str(('pubchem request not fullfilled', request)))
                    all_satisfied = False;
            logger.info('sleep for 3 seconds')
            time.sleep(3)
            tries += 1
        self.assertTrue(all_satisfied, 'All 2nd searches were not satisified')
        
        pubchem_database_cache_service.clear_database_cache(
            days_to_cache=0,seconds_to_cache=(int(time.time()-time1)),days_to_cache_errors=0,seconds_to_cache_errors=1)
        
        query = PubchemRequest.objects.all()
        
        self.assertEquals(len(query),1,"there should only be one item left, the rest are old, and should be cleared")
        self.assertEquals(query[0].id, search_request_id, str(('the wrong id is left', query)))


class SimpleTest(TestCase):
    def test_basic_addition(self):
        """
        Tests that 1 + 1 always equals 2.
        """
        self.assertEqual(1 + 1, 2)

    def test_create_small_molecule(self):
        """
        Tests that we can create a small molecule entity.
        """
        
        facilityId = "HMSL10001"
        sm = SmallMolecule(facility_id=facilityId)
        sm.save()
        
        print "New ID: %d" % sm.id
        self.assertTrue(sm.id is not None, "No ID was assigned")
        
        sm2 = SmallMolecule.objects.get(pk=sm.id)
        self.assertTrue(sm2 is not None, "Couldn't find the object")
        self.assertTrue(sm2.facility_id == facilityId)
        
        print "Created the Small Molecule: ", sm
        

