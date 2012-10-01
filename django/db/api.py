# this file is for the tastypie REST api
# db/api.py - tastypie resources
from tastypie.resources import ModelResource
from tastypie import fields

from db.models import SmallMolecule,DataSet,Cell 

class SmallMoleculeResource(ModelResource):
    class Meta:
        queryset = SmallMolecule.objects.all()
        # to override: resource_name = 'sm'
        excludes = ['column']

class CellResource(ModelResource):
    class Meta:
        queryset = Cell.objects.all()
        # to override: resource_name = 'sm'
        excludes = []
        
class DataSetResource(ModelResource):
    cells = fields.ToManyField(CellResource, 'cells', full=False)
    class Meta:
        queryset = DataSet.objects.all()
        # to override: resource_name = 'sm'
        excludes = []        