"""
This file demonstrates writing tests using the unittest module. These will pass
when you run "manage.py test".

Replace this with more appropriate tests for your application.
"""

from django.test import TestCase
from django.utils import timezone
from db.models import SmallMolecule

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
        pubDate = timezone.now()
        sm = SmallMolecule(facility_id=facilityId,pub_date=pubDate)
        sm.save()
        
        print "New ID: %d" % sm.id
        self.assertTrue(sm.id is not None, "No ID was assigned")
        
        id = sm.id
        
        sm2 = SmallMolecule.objects.get(pk=id)
        
        self.assertTrue(sm is not None, "Couldn't find the object")
        self.assertTrue(sm.facility_id == facilityId)
        self.assertTrue(sm.pub_date == pubDate)
        
        print "Created the Small Molecule: id: %d, facilityId: %s, pubDate: %s" % ( sm.id, sm.facility_id, sm.pub_date )
        

    def test_create_multiple_small_molecules(self):
        """
        Tests that we can create a few small molecule objects in the db, and select a subset
        """
        
        facilityIdBase = "HMSL"
        
        for x in range(100) :
            sm = SmallMolecule(facility_id=facilityIdBase + str(10000+x),pub_date=timezone.now())
            sm.save()
        
        self.assertEqual(100, SmallMolecule.objects.all().count(), "Should be 100 items, but was %d" % SmallMolecule.objects.all().count())
        
        # read back a small sample
        resultSet = SmallMolecule.objects.filter(id__lt=50)
        
        self.assertEquals(resultSet.count(), 49, "Actual size of subqery return is %d" % resultSet.count())
        
        for y in resultSet :
            print "Small Molecule: id: %d, facilityId: %s, pubDate: %s" % ( y.id, y.facility_id, y.pub_date )
        
        
        