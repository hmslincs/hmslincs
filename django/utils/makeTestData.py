"""
populate the database with dummy data
"""

from django.utils import timezone
from example.models import SmallMolecule

class SimplePopulate():
    def populate(self):
        facilityIdBase = "HMSL"
        for x in range(100) :
            sm = SmallMolecule(facility_id=facilityIdBase + str(20000+x),pub_date=timezone.now())
            sm.save()

SimplePopulate().populate()
