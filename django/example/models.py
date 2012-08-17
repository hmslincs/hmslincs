from django.db import models

# Create your models here.
#
class SmallMolecule(models.Model):
   facility_id = models.CharField(max_length=15, unique=True)
   name = models.CharField(max_length=256)
   alternate_names = models.TextField()
   salt_id = models.IntegerField()
   smiles = models.TextField()
   pub_date = models.DateTimeField('date published')
   def __unicode__(self):
        return self.facility_id

class Cell(models.Model):
   facility_id = models.CharField(max_length=15, unique=True)
   name = models.CharField(max_length=256, unique=True)
   clo_id = models.CharField(max_length=128, default='')
   alternate_name = models.CharField(max_length=256, default='')
   alternate_id = models.CharField(max_length=256, default='')
   center_name = models.CharField(max_length=256, default='')
   center_specific_id = models.CharField(max_length=256, default='')
   pub_date = models.DateTimeField('date published')
   def __unicode__(self):
        return self.facility_id
