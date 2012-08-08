from django.db import models

# Create your models here.
#
class SmallMolecule(models.Model):
   facility_id = models.CharField(max_length=15, unique=True)
   pub_date = models.DateTimeField('date published')
   def __unicode__(self):
        return self.facility_id

class Cell(models.Model):
   facility_id = models.CharField(max_length=15, unique=True)
   pub_date = models.DateTimeField('date published')
   def __unicode__(self):
        return self.facility_id
