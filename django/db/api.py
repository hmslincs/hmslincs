# this file is for the tastypie REST api
# db/api.py - tastypie resources
from collections import OrderedDict
from django.db import connection, DatabaseError
try:
    from db import views
except DatabaseError, e:
    if not 'no such table: db_fieldinformation' in str(e):
        raise
    else:
        import os
        if os.environ.get('HMSLINCS_DEV', 'false') != 'true':
            raise

from db.DjangoTables2Serializer import DjangoTables2Serializer, \
    get_visible_columns
from db.models import SmallMolecule, SmallMoleculeBatch, DataSet, Cell, Protein, Library, DataRecord, \
    DataColumn, FieldInformation, get_fieldinformation, get_listing, \
    get_detail_schema, get_detail, get_detail_bundle, get_fieldinformation, get_schema_fieldinformation,\
    Antibody, OtherReagent
from django.conf.urls.defaults import url
from django.core.serializers.json import DjangoJSONEncoder
from django.http import Http404, HttpResponse
from django.utils.encoding import smart_str
from tastypie.authorization import Authorization
from tastypie.bundle import Bundle
from tastypie.resources import ModelResource, Resource
from tastypie.serializers import Serializer
from tastypie import fields
from tastypie.constants import ALL

import StringIO
import csv
import json
import logging
import re
import math
        
logger = logging.getLogger(__name__)


class SmallMoleculeResource(ModelResource):
#    batches = fields.ToManyField('db.api.SmallMoleculeBatchResource', attribute='batches', related_name='batches')
       
    class Meta:
        queryset = SmallMolecule.objects.all()
        # to override: resource_name = 'sm'
        excludes = ['column']
        allowed_methods = ['get']
        filtering = {'date_loaded':ALL, 'date_publicly_available':ALL, 'date_data_received':ALL }

#        authentication = MultiAuthentication(BasicAuthentication(), SessionAuthentication())
        
    def dehydrate(self, bundle):
        _filter = ( 
            lambda field_information: 
                ( not bundle.obj.is_restricted 
                    or field_information.is_unrestricted ) )
        bundle.data = get_detail_bundle(bundle.obj, ['smallmolecule',''], _filter=_filter)
        
        smbs = SmallMoleculeBatch.objects.filter(smallmolecule=bundle.obj)
        bundle.data['batches'] = []
        for smb in smbs:
            bundle.data['batches'].append(
                get_detail_bundle(smb, ['smallmoleculebatch',''], _filter=_filter))
        return bundle

    def build_schema(self):
        schema = super(SmallMoleculeResource,self).build_schema()
        schema['fields'] = get_detail_schema(SmallMolecule(),['smallmolecule'])
        return schema 
    
    def override_urls(self):
        """ Note, will be deprecated in >0.9.12; delegate to new method, prepend_urls
        """
        return self.prepend_urls();
    
    def prepend_urls(self):

        return [
            url(r"^(?P<resource_name>%s)/(?P<facility_id>\d+)\-(?P<salt_id>\d+)/$" % self._meta.resource_name, 
                self.wrap_view('dispatch_detail'), name="api_dispatch_detail"),
        ]

# TODO: fix this after upgrading to Tastypie >= 0.9.14 (latest) - it should work but it doesn't find the smallMolecule resource
#class SmallMoleculeBatchResource(ModelResource):
##    smallMolecule  = fields.ForeignKey(SmallMolecule, 'smallMolecule')
##    smallMolecule = fields.ToOneField(SmallMoleculeResource, 'smallMolecule')
#
#    smallMolecule = fields.ToOneField('api.SmallMoleculeResource', attribute = 'smallMolecule', related_name='smallMolecule', full=True) #, null=True)
#    class Meta:
#        resourceName = "batch"
#        # TODO: authorization
#        # TODO: it would be good to feed these from the view/tables2 code; or vice versa
#        queryset = SmallMoleculeBatch.objects.all()
#        # to override: resource_name = 'sm'
#        excludes = []
#        allowed_methods = ['get']
#
##        authentication = MultiAuthentication(BasicAuthentication(), SessionAuthentication())
#        
#    def dehydrate(self, bundle):
#        _filter = lambda field_information: not bundle.obj.is_restricted or field_information.is_unrestricted # or is_authorized
#        bundle.data = get_detail_bundle(bundle.obj, ['smallmoleculebatch',''], _filter=_filter)
#        return bundle
#
#    def build_schema(self):
#        schema = super(SmallMoleculeBatchResource,self).build_schema()
#        schema['fields'] = get_detail_schema(SmallMoleculeBatch(),['smallmoleculebatch'])
#        return schema 
#    
#    def override_urls(self):
#        """ Note, will be deprecated in >0.9.12; delegate to new method, prepend_urls
#        """
#        return self.prepend_urls();
#    
#    def prepend_urls(self):
#
#        return [
#            url(r"^(?P<resource_name>%s)/(?P<smallmolecule_id>\d+)\-(?P<facility_batch_id>\d+)/$" % 
#                self._meta.resource_name, self.wrap_view('dispatch_detail'), name="api_dispatch_detail"),
#        ]
        

class CellResource(ModelResource):
    class Meta:
        # TODO: authorization
        # TODO: it would be good to feed these from the view/tables2 code; or vice versa
        queryset = Cell.objects.all()
        # to override: resource_name = 'sm'
        allowed_methods = ['get']
        excludes = []
        filtering = {'date_loaded':ALL, 'date_publicly_available':ALL, 'date_data_received':ALL }
        
    def dehydrate(self, bundle):
        bundle.data = get_detail_bundle(bundle.obj, ['cell',''])
        return bundle

    def build_schema(self):
        schema = super(CellResource,self).build_schema()
        schema['fields'] = get_detail_schema(Cell(),['cell'])
        return schema 
    
    def override_urls(self):
        """ Note, will be deprecated in >0.9.12; delegate to new method, prepend_urls
        """
        return self.prepend_urls();
    
    def prepend_urls(self):
        return [
            url(r"^(?P<resource_name>%s)/(?P<facility_id>\d+)/$" % self._meta.resource_name, self.wrap_view('dispatch_detail'), name="api_dispatch_detail"),
        ]
    
class AntibodyResource(ModelResource):
    class Meta:
        # TODO: authorization
        # TODO: it would be good to feed these from the view/tables2 code; or vice versa
        queryset = Antibody.objects.all()
        # to override: resource_name = 'sm'
        allowed_methods = ['get']
        excludes = []
        filtering = {'date_loaded':ALL, 'date_publicly_available':ALL, 'date_data_received':ALL }
        
    def dehydrate(self, bundle):
        bundle.data = get_detail_bundle(bundle.obj, ['antibody',''])
        return bundle

    def build_schema(self):
        schema = super(AntibodyResource,self).build_schema()
        schema['fields'] = get_detail_schema(Antibody(),['antibody'])
        return schema 
    
    def override_urls(self):
        """ Note, will be deprecated in >0.9.12; delegate to new method, prepend_urls
        """
        return self.prepend_urls();
    
    def prepend_urls(self):
        return [
            url(r"^(?P<resource_name>%s)/(?P<facility_id>\d+)/$" % self._meta.resource_name, self.wrap_view('dispatch_detail'), name="api_dispatch_detail"),
        ]
    
class OtherReagentResource(ModelResource):
    class Meta:
        # TODO: authorization
        # TODO: it would be good to feed these from the view/tables2 code; or vice versa
        queryset = OtherReagent.objects.all()
        # to override: resource_name = 'sm'
        allowed_methods = ['get']
        excludes = []
        filtering = {'date_loaded':ALL, 'date_publicly_available':ALL, 'date_data_received':ALL }
        
    def dehydrate(self, bundle):
        bundle.data = get_detail_bundle(bundle.obj, ['otherreagent',''])
        return bundle

    def build_schema(self):
        schema = super(OtherReagentResource,self).build_schema()
        schema['fields'] = get_detail_schema(OtherReagent(),['otherreagent'])
        return schema 
    
    def override_urls(self):
        """ Note, will be deprecated in >0.9.12; delegate to new method, prepend_urls
        """
        return self.prepend_urls();
    
    def prepend_urls(self):
        return [
            url(r"^(?P<resource_name>%s)/(?P<facility_id>\d+)/$" % self._meta.resource_name, self.wrap_view('dispatch_detail'), name="api_dispatch_detail"),
        ]
    
class ProteinResource(ModelResource):
    class Meta:
        # TODO: authorization
        # TODO: it would be good to feed these from the view/tables2 code; or vice versa
        queryset = Protein.objects.all()
        # to override: resource_name = 'sm'
        allowed_methods = ['get']
        excludes = []
        filtering = {'date_loaded':ALL, 'date_publicly_available':ALL, 'date_data_received':ALL }
            
    def dehydrate(self, bundle):
        bundle.data = get_detail_bundle(bundle.obj, ['protein',''])
        return bundle

    def build_schema(self):
        schema = super(ProteinResource,self).build_schema()
        schema['fields'] = get_detail_schema(Protein(),['protein'])
        return schema 
    
    def override_urls(self):
        """ Note, will be deprecated in >0.9.12; delegate to new method, prepend_urls
        """
        return self.prepend_urls();
    
    def prepend_urls(self):
        return [
            url(r"^(?P<resource_name>%s)/(?P<lincs_id>\d+)/$" % self._meta.resource_name, self.wrap_view('dispatch_detail'), name="api_dispatch_detail"),
        ]
    
class LibraryResource(ModelResource):
    class Meta:
        # TODO: authorization
        # TODO: it would be good to feed these from the view/tables2 code; or vice versa
        queryset = Library.objects.all()
        # to override: resource_name = 'sm'
        allowed_methods = ['get']
        excludes = []
        filtering = {'date_loaded':ALL, 'date_publicly_available':ALL, 'date_data_received':ALL }
        
    def dehydrate(self, bundle):
        bundle.data = get_detail_bundle(bundle.obj, ['library',''])
        return bundle

    def build_schema(self):
        schema = super(LibraryResource,self).build_schema()
        schema['fields'] = get_detail_schema(Library(),['library'])
        return schema 
    
    def override_urls(self):
        """ Note, will be deprecated in >0.9.12; delegate to new method, prepend_urls
        """
        return self.prepend_urls();
    
    def prepend_urls(self):
        return [
            url(r"^(?P<resource_name>%s)/(?P<lincs_id>\d+)/$" % self._meta.resource_name, self.wrap_view('dispatch_detail'), name="api_dispatch_detail"),
        ]
        

class DataSetResource(ModelResource):
    """
    This version of the database export shows the DatasetData columns serially, 
    as is specified for the SAF version 0.1 data interchange format for the LIFE system.
    """
    absolute_uri = 'http://lincs.hms.harvard.edu/db/api/v1/datasetdata/'
    
    class Meta:
        queryset = DataSet.objects.all() #.filter(is_restricted==False)
        # TODO: authorization
        allowed_methods = ['get']
        excludes = ['lead_screener_firstname','lead_screener_lastname','lead_screener_email']
        filtering = {'date_loaded':ALL, 'date_publicly_available':ALL, 'date_data_received':ALL }
     
    def dispatch(self, request_type, request, **kwargs):
        """ override in order to be able to grab the request uri
        """
        
        self.absolute_uri = request.build_absolute_uri()
        return super(DataSetResource,self).dispatch(request_type, request, **kwargs)  
         
    def dehydrate(self, bundle):
        _facility_id =str(bundle.data['facility_id'])
        dataset_id = bundle.data['id']
        
        datasetDataColumns = DataSetDataResource.get_datasetdata_camel_case_columns(dataset_id)
        bundle.data = get_detail_bundle(
            bundle.obj, ['dataset',''],
            _override_filter=lambda x: x.show_in_detail or x.field=='bioassay' )
        saf_uri = self.absolute_uri.replace('dataset','datasetdata')
        saf_uri = saf_uri.replace('json','csv');

        datacolumns = list( DataColumn.objects.all().filter(dataset_id=dataset_id) )
        # TODO: drive the columns to show here from fieldinformation inputs
        dc_fieldinformation = FieldInformation.objects.all().filter(table='datacolumn', show_in_detail=True)
        dc_field_names = [fi.get_camel_case_dwg_name() for fi in dc_fieldinformation]
        datapoints = [ dict(zip(dc_field_names, [ getattr(x,fi.field) for fi in dc_fieldinformation ] )) for x in datacolumns ]

        # Custom fields for SAF: TODO: generate the names here from the fieldinformation
        bundle.data['datapointFile'] = {'uri': saf_uri,
                                       'noCols':len(datasetDataColumns),
                                       'cols':datasetDataColumns,
                                       'noDatapoints': len(datapoints),
                                       'datapoints': datapoints
                                       }
        
        bundle.data['safVersion'] = '0.1'  # TODO: drive this from data
        bundle.data['screeningFacility'] = 'HMS' #TODO: drive this from data
        return bundle
    
    def build_schema(self):
        schema = super(DataSetResource,self).build_schema()
        original_dict = schema['fields'] # TODO: reincorporate this information (this default information is about the DB schema definition)
        fields = get_detail_schema(DataSet(), 'dataset', lambda x: x.show_in_detail )
        # Custom fields for SAF: TODO: generate the names here from the fieldinformation
        fields['datapointFile'] = get_schema_fieldinformation('datapoint_file','')
        fields['safVersion'] = get_schema_fieldinformation('saf_version','')
        fields['screeningFacility'] = get_schema_fieldinformation('screening_facility','')
        schema['fields'] = OrderedDict(sorted(fields.items(), key=lambda x: x[0])) # sort alpha, todo sort on fi.order
        
        ds_fieldinformation = DataSetDataResource.get_datasetdata_column_fieldinformation()
        ds_fieldinformation.append(('datapoint_value',get_fieldinformation('datapoint_value',[''])) )
        ds_fieldinformation.append(('timepoint',get_fieldinformation('timepoint',[''])) )
        ds_fieldinformation.append(('timepoint_unit',get_fieldinformation('timepoint_unit',[''])) )
        ds_fieldinformation.append(('timepoint_description',get_fieldinformation('timepoint_description',[''])) )
        
        meta_field_info = get_listing(FieldInformation(),['fieldinformation'])
    
        fields = {}
        for field,fi in ds_fieldinformation:
            field_schema_info = {}
            for item in meta_field_info.items():
                meta_fi_attr = item[0]
                meta_fi = item[1]['fieldinformation']
                field_schema_info[meta_fi.get_camel_case_dwg_name()] = getattr(fi,meta_fi_attr)
            fields[fi.get_camel_case_dwg_name()]= field_schema_info
        schema['datasetDataFile'] = OrderedDict(sorted(fields.items(), key=lambda x: x[0])) # sort alpha, todo sort on fi.order

        dc_fieldinformation = FieldInformation.objects.all().filter(table='datacolumn', show_in_detail=True)
        datapoint_fields = {}
        for fi in dc_fieldinformation:
            field_schema_info = {}
            for item in meta_field_info.items():
                meta_fi_attr = item[0]
                meta_fi = item[1]['fieldinformation']
                field_schema_info[meta_fi.get_camel_case_dwg_name()] = getattr(fi,meta_fi_attr)
            datapoint_fields[fi.get_camel_case_dwg_name()]= field_schema_info
        schema['datapointInformation'] = OrderedDict(sorted(datapoint_fields.items(), key=lambda x: x[0])) # sort alpha, todo sort on fi.order
        
        return schema 
    
    def override_urls(self):
        """ Note, will be deprecated in >0.9.12; delegate to new method, prepend_urls
        """
        return self.prepend_urls();
    
    def prepend_urls(self):
        return [
            url(r"^(?P<resource_name>%s)/(?P<facility_id>\d+)/$" % self._meta.resource_name, self.wrap_view('dispatch_detail'), name="api_dispatch_detail"),
        ]


def camel_case(string):
    
    return string;

#    field_name = re.sub(r'[_\s]+',' ',string)
#    
#    field_name = field_name.title()
#    field_name = re.sub(r'[_\s]+','',field_name)
#    temp = field_name[0].lower() + field_name[1:]
#    logger.info(str(('camelcased:', string,temp)))
#    return temp

class CursorSerializer(Serializer):
    """
    A simple serializer that takes a cursor, queries it for its columns, and outputs 
    this as either CSV or JSON.
    (The CSV output is used with SAF)
    """
    
    formats = ['json', 'jsonp', 'xml', 'yaml', 'csv']
    content_types = {
        'json': 'application/json',
        'jsonp': 'text/javascript',
        'xml': 'application/xml',
        'yaml': 'text/yaml',
        'csv': 'text/csv',
    }

#    def get_saf_columns(self, query):
#        return ['one','two', 'three']
    
    def to_csv(self, cursor, options=None):
        logger.info(str(('typeof the object sent to_csv',type(cursor))))
        raw_data = StringIO.StringIO()
                
        # this is an unexpected way to get this error, look into tastypie sequence calls
        if(isinstance(cursor,dict) and 'error_message' in cursor):
            logger.info(str(('report error', cursor)))
            raw_data.writelines(('error_message\n',cursor['error_message'],'\n'))
            return raw_data.getvalue() 
        
        # no response header needed?
        #        response = HttpResponse(mimetype='text/csv')
        #        response['Content-Disposition'] = 'attachment; filename=%s.csv' % unicode('test.output').replace('.', '_')
        #        raw_data.write(response)
        writer = csv.writer(raw_data)
        i=0
        cols = [col[0] for col in cursor.description]
        
        # TODO: grab the column names here
        writer.writerow(cols)

        for row in cursor.fetchall():
            writer.writerow([self._write_val_safe(val) for val in row])
            i += 1

        logger.info('done, wrote: %d' % i)
        return raw_data.getvalue()
    
    
    def _write_val_safe(self,val):
        # for #185, remove 'None' values
        if not val: return ''
        return smart_str(val, 'utf-8', errors='ignore')

    def to_json(self,cursor, options=None):
        
        logger.info(str(('typeof the object sent to_json',type(cursor))))
#        logger.info(str(('to_csv for SAF for cursor', cursor)))
        raw_data = StringIO.StringIO()
                
        # this is an unexpected way to get this error, look into tastypie sequence calls
        if isinstance(cursor,dict) and 'error_message' in cursor :
            logger.info(str(('report error', cursor)))
            raw_data.writelines(('error_message\n',cursor['error_message'],'\n'))
            return raw_data.getvalue() 
        elif isinstance(cursor,dict) :
            # then in this case, this is a non-error dict, probably for the schema, dump and return.
            raw_data.writelines(json.dumps(cursor))
            return raw_data.getvalue()
        # TODO: sort the fields?
        i=0
        cols = [col[0] for col in cursor.description]
        
        raw_data.write('[')
        for row in cursor.fetchall():
            if i!=0:
                raw_data.write(',\n')
            raw_data.write(json.dumps(OrderedDict(zip(cols, row)),skipkeys=False,ensure_ascii=True,check_circular=True, allow_nan=True, cls=DjangoJSONEncoder))
            #            raw_data.write(json.dumps(dict(zip(cols, row))))
            i += 1
        raw_data.write(']')

        logger.info('done, wrote: %d' % i)
        return raw_data.getvalue()
    
    
    def to_jsonp(self, table, options=None):
        return 'Sorry, not implemented yet. Please append "?format=csv" to your URL.'
        #return super.to_jsonp(table.data.list, options)

    def to_xml(self, table, options=None):
        return 'Sorry, not implemented yet. Please append "?format=csv" to your URL.'
        #return super.to_xml(table.data.list,options)
    
    def to_yaml(self, table, options=None):
        return 'Sorry, not implemented yet. Please append "?format=csv" to your URL.'
        #return super.to_yaml(table.data.list, options)
        
    def from_csv(self, content):
        pass
        #raw_data = StringIO.StringIO(content)
        #data = []
        # Untested, so this might not work exactly right.
        #for item in csv.DictReader(raw_data):
        #    data.append(item)
        #return data
        


class DataSetDataResource(Resource):
    """
    This version of the database export shows the DatasetData columns serially,
    except for the timepoint columns (which are still flattened),
    as is specified for the SAF version 0.1 data interchange format for the LIFE system.
    
    This class is a complete override of the read functionality of tastypie; 
    because serializing the dataset data is not possible using ORM code.
    """
    
    # TODO: version 2: use the manager, not the tables2
    class Meta:
        fields = []
        serializer = CursorSerializer()
        allowed_methods = ['get']

    def get_object_list(self, request):
        """
        A hook to generate the list of available objects.
        override tastypie.resources.Resource
        - we do this because this is a custom resource (not, for instance, a ModelResource)
        Note: this function will hand off to the Serializer.
        """
        logger.info(str(('get_object_list', request.path, request.GET)))
        matchObject = re.match(r'.*datasetdata/(\d+)/', request.path) # TODO: there must be a way to get the request path variable automagically
        if(matchObject):
            facility_id = matchObject.group(1)
            try:
                dataset = DataSet.objects.get(facility_id=facility_id)
                logger.info(str(('DataSetData2Resource', facility_id,dataset)))
                if(dataset.is_restricted and not request.user.is_authenticated()):
                    raise Http401
                
                return self.get_datasetdata_cursor(dataset.id)
            
            
            except DataSet.DoesNotExist, e:
                logger.error(str(('no such facility id', facility_id)))
                raise e
        else:
            raise Http404(str(('no facility id given',request.path)))
    
    @staticmethod
    def get_dataset_columns(dataset_id, unit_types_only=[]):
        datacolumns = DataColumn.objects.filter(dataset_id=dataset_id)
        
        # filter for the columns that are identified as having these unit fields
        if unit_types_only:
            datacolumns = datacolumns.filter(unit__in=unit_types_only)
            
        return datacolumns

    @staticmethod
    def get_datasetdata_column_fieldinformation(): #TODO: is this cached by python?
        """
        returns a list of [('table.field', fieldinformation )]
        """
        # TODO: only include cell, protein if they are present in the dataset
        # Note, case is erased when cursor.description is filled, so use underscores, and leave the camelcasing for later
        
        table_fields = ['datarecord.id',
                        'dataset.facility_id',
                        'smallmolecule.facility_id', 
                        'smallmolecule.salt_id', 
                        'smallmoleculebatch.facility_batch_id', 
                        'smallmolecule.lincs_id',
                        'smallmolecule.name',
                        'cell.name',
                        'cell.cl_id',
                        'cell.facility_id',
                        'protein.name',
                        'protein.lincs_id',
                        'datarecord.plate',
                        'datarecord.well',
                        'datarecord.control_type',
                        'datacolumn.name',
                        'datacolumn.unit',  ]
        tablefields_fi = [];
        for tablefield in table_fields:
            tflist = tablefield.split('.') 
            tablefields_fi.append((tablefield, get_fieldinformation(tflist[1],[tflist[0]])))
            
        return tablefields_fi
    
    @staticmethod
    def get_datasetdata_camel_case_columns(dataset_id):
        camel_columns = [x[1].get_camel_case_dwg_name() 
                         for x in DataSetDataResource.get_datasetdata_column_fieldinformation()]
        timepoint_columns = DataSetDataResource.get_dataset_columns(dataset_id, ['day','hour','minute','second'])
        for i in xrange(len(timepoint_columns)):
            camel_columns.append('timepoint'+ ('','_'+str(i))[i>0]) # FYI we have to label manually, because timepoint is an alias, not real DataColumn
            camel_columns.append('timepoint_unit'+ ('','_'+str(i))[i>0])
            camel_columns.append('timepoint_description'+ ('','_'+str(i))[i>0])
        datapoint_value_fi = get_fieldinformation('datapoint_value', ['']) 
        camel_columns.append(datapoint_value_fi.get_camel_case_dwg_name())
        return camel_columns
                     
    @staticmethod
    def get_datasetdata_cursor(dataset_id):
        timepoint_columns = DataSetDataResource.get_dataset_columns(dataset_id, ['day','hour','minute','second'])
        logger.info(str(('timepoint_columns', timepoint_columns)))
        datapoint_columns = DataSetDataResource.get_dataset_columns(dataset_id)
        datapoint_columns = [col for col in datapoint_columns if col not in timepoint_columns]
        
        # pivot out the timepoint columns only
        timepoint_column_string = '';
        for i,dc in enumerate(timepoint_columns):
            alias = "dp_"+ str(i)
            
            tp_name = "timepoint"
            tp_unit_name = "timepoint_unit"
            tp_desc_name = "timepoint_description"
            if i>0: 
                tp_name += "_" + str(i)
                tp_unit_name += "_" + str(i)
                tp_desc_name += "_" + str(i)

            # note: timepoint values are probably text, but who knows, so query the type here
            column_to_select = None
            if(dc.data_type == 'Numeric' or dc.data_type == 'omero_image'):
                if dc.precision == 0 or dc.data_type == 'omero_image':
                    column_to_select = "int_value"
                else:
                    column_to_select = "round( float_value::numeric, 2 )" # TODO: specify the precision in the fieldinformation for this column
            else:
                column_to_select = "text_value"
            timepoint_column_string += (    
                ",(SELECT " + column_to_select + " FROM db_datapoint " + alias + 
                " where " + alias + ".datacolumn_id="+str(dc.id) + 
                " and " + alias + ".datarecord_id=datarecord.id) as " + tp_name )
            timepoint_column_string += ", '" + dc.unit + "' as " + tp_unit_name
            if dc.description:
                timepoint_column_string += ", '" + dc.description  + "' as " + tp_desc_name
        

             
        sql = "select "
        # patterns to match the protein and cell fields, which will be handled differently below,
        # because they can be linked through the DataRecord or the DataColumn
        protein_pattern = re.compile(r'protein.(.*)') 
        cell_pattern = re.compile(r'cell.(.*)')
        meta_columns_to_fieldinformation = DataSetDataResource.get_datasetdata_column_fieldinformation()
        for i,(tablefield,fi) in enumerate(meta_columns_to_fieldinformation):
            if i!=0: 
                sql += ', \n'
            # NOTE: Due to an updated requirement, proteins, cells may be linked to either datarecords, or datacolumns, 
            # so the following ugliness ensues
            m = protein_pattern.match(tablefield)
            m2 = cell_pattern.match(tablefield)
            if m:
                sql += ( '(select p.' + m.group(1) + 
                    ' from db_protein p where p.id in (datacolumn.protein_id,datarecord.protein_id))' + 
                    ' as "' + fi.get_camel_case_dwg_name() +'"' ) 
            elif m2:
                sql += ( '(select c.' + m2.group(1) + 
                    ' from db_cell c where c.id in (datacolumn.cell_id,datarecord.cell_id))' + 
                    ' as "' + fi.get_camel_case_dwg_name() +'"' ) 
            else:
                # TODO: this information is parsed when deserializing to create the "camel cased name"
                sql += tablefield + ' as "' + fi.get_camel_case_dwg_name() +'"' 
        datapoint_value_fi = get_fieldinformation('datapoint_value', [''])  
        sql += ', coalesce(dp.int_value::TEXT, dp.float_value::TEXT, dp.text_value) as "' + datapoint_value_fi.get_camel_case_dwg_name() +'"\n'
            
        sql += timepoint_column_string
        
        # Note: older simple left join to proteins
        #             left join db_protein protein on (datarecord.protein_id=protein.id)
        # Also, cells:
        #            left join db_cell cell on (datarecord.cell_id=cell.id)
        # has been replaced to 
        #            left join ( select datarecord.id as dr_id, * from db_protein p where p.id in (datarecord.protein_id,datacolumn.protein_id)) protein on(dr_id=datarecord.id)
        sql += """
            from db_dataset dataset 
            join db_datarecord datarecord on(datarecord.dataset_id=dataset.id) 
            join db_datacolumn datacolumn on(datacolumn.dataset_id=dataset.id) 
            left join db_smallmolecule smallmolecule on (datarecord.smallmolecule_id=smallmolecule.id) 
            left join db_smallmoleculebatch smallmoleculebatch 
                on(smallmoleculebatch.smallmolecule_id=smallmolecule.id 
                    and smallmoleculebatch.facility_batch_id=datarecord.sm_batch_id)
            , db_datapoint dp 
            where dp.datarecord_id=datarecord.id and dp.datacolumn_id=datacolumn.id 
            and dataset.id = %s 
            """
        if len(timepoint_columns) > 0: 
            sql += " and datacolumn.id not in (" + ','.join([str(col.id) for col in timepoint_columns]) + ") "    
        sql += " order by datarecord.id, datacolumn.id "
        
        logger.info(str(('sql',sql)))
        cursor = connection.cursor()
        cursor.execute(sql, [dataset_id])
        #                query = DataRecord.objects.filter(dataset_id=dataset_id)
        #                logger.info(str(('query returns', query)))
        return cursor

    def build_schema(self):
        schema = super(DataSetDataResource,self).build_schema()
        original_dict = schema['fields'] # TODO: reincorporate this information (this default information is about the DB schema definition)

        ds_fieldinformation = DataSetDataResource.get_datasetdata_column_fieldinformation()
        ds_fieldinformation.append(('datapoint_value',get_fieldinformation('datapoint_value',[''])) )
        ds_fieldinformation.append(('timepoint',get_fieldinformation('timepoint',[''])) )
        ds_fieldinformation.append(('timepoint_unit',get_fieldinformation('timepoint_unit',[''])) )
        ds_fieldinformation.append(('timepoint_description',get_fieldinformation('timepoint_description',[''])) )
        
        meta_field_info = get_listing(FieldInformation(),['fieldinformation'])
    
        fields = {}
        for __,fi in ds_fieldinformation:
            field_schema_info = {}
            for item in meta_field_info.items():
                meta_fi_attr = item[0]
                meta_fi = item[1]['fieldinformation']
                field_schema_info[meta_fi.get_camel_case_dwg_name()] = getattr(fi,meta_fi_attr)
            fields[fi.get_camel_case_dwg_name()]= field_schema_info
        schema['fields'] = OrderedDict(sorted(fields.items(), key=lambda x: x[0])) # TODO, use the fieldinformation order
        
        return schema 
    
    def obj_get_list(self, request=None, **kwargs):
        logger.info('obj_get_list')
        # Filtering disabled for brevity...
        return self.get_object_list(request)
    
    def obj_get(self, request=None, **kwargs):
        logger.info('obj_get')
        return self.get_object_list(request)
    
    def get_detail(self, request, **kwargs):
        logger.info('get_detail')
        return self.create_response(request,self.get_object_list(request))
    def override_urls(self):
        """ Note, will be deprecated in >0.9.12; delegate to new method, prepend_urls
        """
        return self.prepend_urls();
    
    def prepend_urls(self):
        return [
            url(r"^(?P<resource_name>%s)/(?P<facility_id>\d+)/$" % self._meta.resource_name, self.wrap_view('dispatch_detail'), name="api_dispatch_detail"),
        ]
    
    def dehydrate(self, bundle):
        # TODO: for datasetdata, show the column information that was entered
        return bundle            

class DataSetFlattenedResource(ModelResource):
    """
    This version of the database export shows the DatasetData columns in a pivoted, flattened table,
    in the same form as the web UI
    """
    absolute_uri = 'http://lincs.hms.harvard.edu/db/api/v1/datasetdata/'
    
    class Meta:
        queryset = DataSet.objects.all() #.filter(is_restricted==False)
        # TODO: authorization
        # TODO: it would be good to feed these from the view/tables2 code; or vice versa
        allowed_methods = ['get']
        excludes = ['lead_screener_firstname','lead_screener_lastname','lead_screener_email']

    def dispatch(self, request_type, request, **kwargs):
        """ override in order to be able to grab the request uri
        """
        
        self.absolute_uri = request.build_absolute_uri()
        return super(DataSetFlattenedResource,self).dispatch(request_type, request, **kwargs)  
         
    def dehydrate(self, bundle):
        # TODO: the following call executes the query *just* to get the column names
        _facility_id =str(bundle.data['facility_id'])
        visibleColumns = get_visible_columns(views.DataSetManager(bundle.obj).get_table())
        bundle.data = get_detail_bundle(bundle.obj, ['dataset',''])
        saf_uri = self.absolute_uri.replace('dataset','datasetdata')
        saf_uri = saf_uri.replace('json','csv');
        bundle.data['datapointFile'] = {'uri': saf_uri,
                                       'noCols':len(visibleColumns),
                                       'cols':visibleColumns.values()
                                       }
        return bundle

    def build_schema(self):
        schema = super(DataSetResource,self).build_schema()
        # TODO: build the schema from the fieldinformation
        schema['fields'] = get_detail_schema(DataSet(),['dataset'])
        return schema 
    
    def override_urls(self):
        """ Note, will be deprecated in >0.9.12; delegate to new method, prepend_urls
        """
        return self.prepend_urls();
    
    def prepend_urls(self):
        return [
            url(r"^(?P<resource_name>%s)/(?P<facility_id>\d+)/$" % self._meta.resource_name, self.wrap_view('dispatch_detail'), name="api_dispatch_detail"),
        ]

    
class DataSetDataFlattenedResource(Resource):
    """
    This class is a complete override of the read functionality of tastypie; 
    because serializing the dataset data is not possible using ORM code.
    """
    
    # TODO: version 2: use the manager, not the tables2
    class Meta:
        #queryset = DataRecord.objects.all()
        # to override: resource_name = 'sm'
        fields = []
        allowed_methods = ['get']
        serializer = DjangoTables2Serializer()
    
    def get_object_list(self, request):
        matchObject = re.match(r'.*datasetdata/(\d+)/', request.path) # TODO: there must be a way to get the request path variable automagically
        if(matchObject):
            facility_id = matchObject.group(1)
            try:
                dataset = DataSet.objects.get(facility_id=facility_id)
                logger.info(str(('DataSetDataResource', facility_id,dataset)))
                if(dataset.is_restricted and not request.user.is_authenticated()):
                    raise Http401
                manager = views.DataSetManager(dataset)
                return manager.get_table()
            except DataSet.DoesNotExist, e:
                logger.error(str(('no such facility id', facility_id)))
                raise
        else:
            raise Http404(str(('no facility id given',request.path)))
    
    def obj_get_list(self, request=None, **kwargs):
        logger.info('obj_get_list')
        # Filtering disabled for brevity...
        return self.get_object_list(request)
    
    def obj_get(self, request=None, **kwargs):
        logger.info('obj_get')
        return self.get_object_list(request)
    
    def get_detail(self, request, **kwargs):
        logger.info('get_detail')
        return self.create_response(request,self.get_object_list(request))
        
    def detail_uri_kwargs(self, bundle_or_obj):
        logger.info(str(('detail_uri_kwargs', bundle_or_obj)))
        kwargs = {}

        if isinstance(bundle_or_obj, Bundle):
            kwargs['pk'] = bundle_or_obj.obj.uuid
        else:
            kwargs['pk'] = bundle_or_obj.uuid

        return kwargs    
    
    def override_urls(self):
        """ Note, will be deprecated in >0.9.12; delegate to new method, prepend_urls
        """
        return self.prepend_urls();
    
    def prepend_urls(self):
        return [
            url(r"^(?P<resource_name>%s)/(?P<facility_id>\d+)/$" % self._meta.resource_name, self.wrap_view('dispatch_detail'), name="api_dispatch_detail"),
        ]
    
    def dehydrate(self, bundle):
        # TODO: for datasetdata, show the column information that was entered
        return bundle    

class Http401(Exception):
    pass


