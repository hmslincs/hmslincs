from collections import OrderedDict
from django.db import connection, DatabaseError
from tastypie.utils.urls import trailing_slash
from db.views import _get_raw_time_string
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
from db.models import SmallMolecule, SmallMoleculeBatch, Cell, \
    CellBatch, Protein, ProteinBatch, \
    Antibody, AntibodyBatch, OtherReagent, OtherReagentBatch, \
    Library, DataSet, DataRecord, DataColumn, FieldInformation, \
    get_detail_bundle, get_fieldinformation, get_schema_fieldinformation,\
    camel_case_dwg, get_fieldinformation, get_listing, get_detail_schema, get_detail
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
       
    class Meta:
        queryset = SmallMolecule.objects.all()
        excludes = ['column']
        allowed_methods = ['get']
        filtering = {'date_loaded':ALL, 'date_publicly_available':ALL, 'date_data_received':ALL }
        
    def dehydrate(self, bundle):
        
        def _filter(field_information):
            return (not bundle.obj.is_restricted 
                    or field_information.is_unrestricted )

        bundle.data = get_detail_bundle(bundle.obj, ['smallmolecule',''], _filter=_filter)

        smbs = ( SmallMoleculeBatch.objects.filter(reagent=bundle.obj)
            .exclude(batch_id=0) )
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

        
class CellResource(ModelResource):
    
    class Meta:
        queryset = Cell.objects.all()
        allowed_methods = ['get']
        excludes = []
        filtering = {'date_loaded':ALL, 'date_publicly_available':ALL, 'date_data_received':ALL }
        
    def dehydrate(self, bundle):
        def _filter(field_information):
            return (not bundle.obj.is_restricted 
                    or field_information.is_unrestricted )

        bundle.data = get_detail_bundle(bundle.obj, ['cell',''], _filter=_filter)

        batches = ( CellBatch.objects.filter(reagent=bundle.obj)
            .exclude(batch_id=0) )
        bundle.data['batches'] = []
        for batch in batches:
            bundle.data['batches'].append(
                get_detail_bundle(batch, ['cellbatch',''], _filter=_filter))
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
        queryset = Antibody.objects.all()
        allowed_methods = ['get']
        excludes = []
        filtering = {'date_loaded':ALL, 'date_publicly_available':ALL, 'date_data_received':ALL }
        
    def dehydrate(self, bundle):
        def _filter(field_information):
            return (not bundle.obj.is_restricted 
                    or field_information.is_unrestricted )

        bundle.data = get_detail_bundle(bundle.obj, ['antibody',''], _filter=_filter)

        batches = ( AntibodyBatch.objects.filter(reagent=bundle.obj)
            .exclude(batch_id=0) )
        bundle.data['batches'] = []
        for batch in batches:
            bundle.data['batches'].append(
                get_detail_bundle(batch, ['antibodybatch',''], _filter=_filter))
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
        queryset = OtherReagent.objects.all()
        allowed_methods = ['get']
        excludes = []
        filtering = {'date_loaded':ALL, 'date_publicly_available':ALL, 'date_data_received':ALL }
        
    def dehydrate(self, bundle):
        def _filter(field_information):
            return (not bundle.obj.is_restricted 
                    or field_information.is_unrestricted )

        bundle.data = get_detail_bundle(bundle.obj, ['otherreagent',''], _filter=_filter)

        batches = ( OtherReagentBatch.objects.filter(reagent=bundle.obj)
            .exclude(batch_id=0) )
        bundle.data['batches'] = []
        for batch in batches:
            bundle.data['batches'].append(
                get_detail_bundle(batch, ['otherreagentbatch',''], _filter=_filter))
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
        queryset = Protein.objects.all()
        allowed_methods = ['get']
        excludes = []
        filtering = {'date_loaded':ALL, 'date_publicly_available':ALL, 'date_data_received':ALL }
            
    def dehydrate(self, bundle):
        def _filter(field_information):
            return (not bundle.obj.is_restricted 
                    or field_information.is_unrestricted )

        bundle.data = get_detail_bundle(bundle.obj, ['protein',''], _filter=_filter)

        batches = ( ProteinBatch.objects.filter(reagent=bundle.obj)
            .exclude(batch_id=0) )
        bundle.data['batches'] = []
        for batch in batches:
            bundle.data['batches'].append(
                get_detail_bundle(batch, ['proteinbatch',''], _filter=_filter))
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
        queryset = Library.objects.all()
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
    
    def to_csv(self, cursor, options=None):

        raw_data = StringIO.StringIO()
                
        if(isinstance(cursor,dict) and 'error_message' in cursor):
            logger.info(str(('report error', cursor)))
            raw_data.writelines(('error_message\n',cursor['error_message'],'\n'))
            return raw_data.getvalue() 
        
        writer = csv.writer(raw_data)
        i=0
        cols = [col[0] for col in cursor.description]
        
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
        raw_data = StringIO.StringIO()
                
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
        

class DataSetResource2(ModelResource):
    '''
    New version of the Dataset endpoint:
    - support for multiple reagents associated with an assay well
    '''
    
    class Meta:
        queryset = DataSet.objects.all()
        allowed_methods = ['get']
        excludes = [
            'lead_screener_firstname',
            'lead_screener_lastname',
            'lead_screener_email' ]
        filtering = {
            'date_loaded':ALL, 
            'date_publicly_available':ALL, 
            'date_data_received':ALL,
            'date_updated': ALL,
            'dataset_type': ALL,
            'bioassay':ALL }
        ordering = ['facility_id','date_updated']
        detail_uri_name = 'facility_id'
        resource_name = 'dataset'
              
    def dehydrate(self, bundle):
        
        dataset_id = bundle.data['id']

        bundle.data = get_detail_bundle(
            bundle.obj, ['dataset',''],
            _override_filter=lambda x: x.show_in_detail or x.field=='bioassay')
        
        datapointFileSchema = DataSetDataResource2.generate_schema(dataset_id)
        _uri = self.get_resource_uri(bundle)
        saf_uri = _uri.replace('dataset','datasetdata')
        saf_uri = saf_uri + '?format=csv'
        datapointFileSchema['uri'] = bundle.request.build_absolute_uri(saf_uri)
        
        bundle.data['datapointFile'] = datapointFileSchema
        bundle.data['safVersion'] = '0.1'  
        bundle.data['screeningFacility'] = 'HMS' 
        return bundle
    
    def build_schema(self):
        
        fields = get_detail_schema(
            DataSet(), 'dataset', lambda x: x.show_in_detail )

        fields['datapointFile'] = get_schema_fieldinformation(
            'datapoint_file','')
        fields['safVersion'] = get_schema_fieldinformation('saf_version','')
        fields['screeningFacility'] = get_schema_fieldinformation(
            'screening_facility','')

        schema['fields'] = OrderedDict(sorted(
            fields.items(), key=lambda x: x[0])) 
        return schema 
    
    def override_urls(self):
        """ Note, will be deprecated in >0.9.12; delegate to prepend_urls
        """
        return self.prepend_urls();
    
    def prepend_urls(self):

        return [
            url(r"^(?P<resource_name>%s)/schema%s$" 
                % ( self._meta.resource_name, trailing_slash()),
                self.wrap_view('get_schema'), name="api_get_schema"),
            url(r"^(?P<resource_name>%s)%s$" 
                % ( self._meta.resource_name, trailing_slash()),
                self.wrap_view('dispatch_list'), name="api_dispatch_list"),
            url(r"^(?P<resource_name>%s)/(?P<facility_id>\d+)%s$" 
                % ( self._meta.resource_name, trailing_slash()), 
                self.wrap_view('dispatch_detail'), name="api_dispatch_detail"),
        ]
        

class DataSetDataResource2(Resource):
    '''
    New version of the Dataset data endpoint:
    - support for multiple reagents associated with an assay well
    '''

    datapoint_cols = {
        'timepoint': [
            "timepoint",
            "timepointUnit",
            "timepointDescription",
            ],
        'small_molecule': [
            "smCenterCompoundID",
            "smSalt",
            "smCenterSampleID",
            "smLincsID",
            "smName",
            ],
        'protein': [
            "ppName",
            "ppLincsID",
            "ppCenterSampleID",
            ],
        'cell': [
            "clName",
            "clCenterSpecificID",
            "clCenterSampleID",
            ],
        'antibody': [
            "abName",
            "abCenterSpecificID",
            "abCenterSampleID",
            ],
        'otherreagent': [
            "orName",
            "orCenterSpecificID",
            "orCenterSampleID",
            ]
        }

    class Meta:
        fields = []
        serializer = CursorSerializer()
        allowed_methods = ['get']
        resource_name = 'datasetdata'

    def get_detail(self, request, **kwargs):
        facility_id = kwargs.get('facility_id', None)
        if not facility_id:
            raise Http404(str(('no facility id given',request.path)))
        response  = self.create_response(
            request,self.get_object_list(request, **kwargs))
        name = 'dataset_%s_%s' % (facility_id, _get_raw_time_string())
        response['Content-Disposition'] = 'attachment; filename=%s.csv' % name
        return response

    def get_object_list(self, request, **kwargs):

        facility_id = kwargs.get('facility_id', None)
        if not facility_id:
            raise Http404(str(('no facility id given',request.path)))
            
        try:
            dataset = DataSet.objects.get(facility_id=facility_id)
            if(dataset.is_restricted and not request.user.is_authenticated()):
                raise Http401
            return self.get_datasetdata_cursor(dataset.id)
        except DataSet.DoesNotExist, e:
            logger.exception('no such facility id %r' % facility_id)
            raise e

    @staticmethod
    def get_datasetdata_cursor(dataset_id):
        
        dataset = DataSet.objects.get(id=dataset_id)
        
        timepoint_columns = ( 
            DataColumn.objects.all()
                .filter(dataset_id=dataset_id)
                .filter(unit__in=['day','hour','minute','second']) )
        
        reagent_columns = ( DataColumn.objects.filter(dataset_id=dataset_id)
            .filter(data_type__in=[
                'small_molecule','cell','protein','antibody','otherreagent']) )
        
        dc_ids_to_exclude = [dc.id for dc in timepoint_columns]
        dc_ids_to_exclude.extend([dc.id for dc in reagent_columns])
        
        col_query_string = (
            ', (SELECT '
            ' {column_to_select} '
            ' FROM db_datapoint as {alias} '
            ' WHERE {alias}.datacolumn_id={dc_id} '
            ' AND {alias}.datarecord_id=datarecord.id ) as "{column_name}" '
            )
        timepoint_unit_string = ',$${dc_unit}$$ as "{dc_name}_timepointUnit" '
        timepoint_description_string = (
            ',$${dc_description}$$ as "{dc_name}_timepointDescription" ')
        
        query_string = (
            'WITH drs as ('
            ' SELECT '
            ' datarecord.id as "datarecordID"'
            ', dataset.facility_id as "hmsDatasetID"'
            ', datarecord.plate as "recordedPlate"'
            ', datarecord.well as "recordedWell"'
            ', datarecord.control_type as "controlType"'
            )        
        alias_count = 0
        for dc in timepoint_columns:
            column_to_select = None
            alias_count += 1
            alias = 'dp_%d'%alias_count
            column_name = '%s_timepoint' % camel_case_dwg(dc.name)
            if(dc.data_type == 'Numeric' or dc.data_type == 'omero_image'):
                if dc.precision == 0 or dc.data_type == 'omero_image':
                    column_to_select = "int_value"
                else:
                    column_to_select = "round( float_value::numeric, 2 )"
            else:
                column_to_select = "text_value"
            query_string += col_query_string.format(
                column_to_select=column_to_select,
                alias=alias,dc_id=dc.id,column_name=column_name)
            query_string += timepoint_unit_string.format(
                dc_unit=dc.unit, dc_name=camel_case_dwg(dc.name))

            if dc.description:
                query_string += timepoint_description_string.format(
                    dc_description=dc.description, 
                    dc_name=camel_case_dwg(dc.name))

        reagent_id_query = (
             ', (SELECT r.facility_id '
             ' FROM db_reagent r '
             ' JOIN db_reagentbatch rb on rb.reagent_id=r.id '
             ' JOIN db_datapoint {alias} on rb.id={alias}.reagent_batch_id '
             ' WHERE {alias}.datarecord_id=datarecord.id '
             ' AND {alias}.datacolumn_id={dc_id} ) as "{column_name}" '
            )
        sm_salt_query = (
             ', (SELECT r.salt_id'
             ' FROM db_reagent r '
             ' JOIN db_reagentbatch rb on rb.reagent_id=r.id '
             ' JOIN db_datapoint {alias} on rb.id={alias}.reagent_batch_id '
             ' WHERE {alias}.datarecord_id=datarecord.id '
             ' AND {alias}.datacolumn_id={dc_id} ) as "{column_name}" '
            )
        sm_lincs_id_query = (
             ', (SELECT r.lincs_id'
             ' FROM db_reagent r '
             ' JOIN db_reagentbatch rb on rb.reagent_id=r.id '
             ' JOIN db_datapoint {alias} on rb.id={alias}.reagent_batch_id '
             ' WHERE {alias}.datarecord_id=datarecord.id '
             ' AND {alias}.datacolumn_id={dc_id} ) as "{column_name}" '
            )
        reagent_batch_id_query = (
             ', (SELECT '
             " CASE WHEN rb.batch_id = '0' THEN '' ELSE rb.batch_id END"
             ' FROM db_reagent r '
             ' JOIN db_reagentbatch rb on rb.reagent_id=r.id '
             ' JOIN db_datapoint {alias} on rb.id={alias}.reagent_batch_id '
             ' WHERE {alias}.datarecord_id=datarecord.id '
             ' AND {alias}.datacolumn_id={dc_id} ) as "{column_name}" '
            )
        reagent_name_query = (
             ', ( SELECT r.name '
             ' FROM db_reagent r '
             ' JOIN db_reagentbatch rb on rb.reagent_id=r.id '
             ' JOIN db_datapoint {alias} on rb.id={alias}.reagent_batch_id '
             ' WHERE {alias}.datarecord_id=datarecord.id '
             ' AND {alias}.datacolumn_id={dc_id}  ) as "{column_name}" '
            )
        
        prefixes = { 'small_molecule': 'sm', 'protein': 'pp', 'antibody': 'ab',
            'otherreagent': 'or', 'cell': 'cl'}
        for dc in reagent_columns:
            prefix = prefixes[dc.data_type]
            if dc.data_type == 'small_molecule':
                alias_count += 1
                alias = 'dp_%d' % alias_count
                query_string += sm_salt_query.format(
                    alias=alias,
                    dc_id=dc.id,
                    column_name='%s_%s%s' 
                        % (camel_case_dwg(dc.name),prefix,'Salt'))

                alias_count += 1
                alias = 'dp_%d' % alias_count
                query_string += reagent_id_query.format(
                    alias=alias,
                    dc_id=dc.id,
                    column_name='%s_%s%s' 
                        % (camel_case_dwg(dc.name),prefix,'CenterCompoundID'))

                alias_count += 1
                alias = 'dp_%d' % alias_count
                query_string += sm_lincs_id_query.format(
                    alias=alias,
                    dc_id=dc.id,
                    column_name='%s_%s%s' 
                        % (camel_case_dwg(dc.name),prefix,'LincsID'))
            
            else:
                alias_count += 1
                alias = 'dp_%d' % alias_count
                query_string += reagent_id_query.format(
                    alias=alias,
                    dc_id=dc.id,
                    column_name='%s_%s%s' 
                        % (camel_case_dwg(dc.name),prefix,'CenterSpecificID'))
            
            alias_count += 1
            alias = 'dp_%d' % alias_count
            query_string += reagent_batch_id_query.format(
                alias=alias,
                dc_id=dc.id,
                column_name='%s_%s%s' 
                    % (camel_case_dwg(dc.name),prefix,'CenterSampleID'))
                
            alias_count += 1
            alias = 'dp_%d' % alias_count
            query_string += reagent_name_query.format(
                alias=alias,
                dc_id=dc.id,
                column_name='%s_%s%s' 
                    % (camel_case_dwg(dc.name),prefix,'Name'))
                
        query_string += """
            from db_dataset dataset 
            join db_datarecord datarecord on(datarecord.dataset_id=dataset.id) 
            and dataset.id = %s )  
            """

        query_string += 'SELECT drs.* '
        query_string += ', dc.name as "datapointName" '
        query_string += ', dc.unit as "datapointUnit" '
        query_string += (
            ', coalesce(dp.int_value::TEXT, dp.float_value::TEXT, dp.text_value) as "%s" '
                % 'datapointValue' )
        query_string += """ 
            FROM drs 
            JOIN db_datapoint dp on dp.datarecord_id=drs."datarecordID" 
            join db_datacolumn dc on dp.datacolumn_id=dc.id  
            where dp.dataset_id = %s """
        if dc_ids_to_exclude: 
            query_string += ( 
                " and dp.datacolumn_id not in (%s)" 
                    % ','.join([str(x) for x in dc_ids_to_exclude]))    
        query_string +=' order by "datarecordID",dc.id '
        
        logger.info('query_string: %s' % query_string)
        cursor = connection.cursor()
        cursor.execute(query_string, [dataset_id,dataset_id])
        return cursor
  
    @staticmethod
    def get_datarecord_fields(dataset_id): 
        
        base_cols = [
            "datarecordID",
            "hmsDatasetID",
            "recordedPlate",
            "recordedWell",
            "controlType",
            "datapointName",
            "datapointUnit",
            "datapointValue"            
            ]
        
        timepoint_columns = ( 
            DataColumn.objects.all()
                .filter(dataset_id=dataset_id)
                .filter(unit__in=['day','hour','minute','second']) )
        timepoint_col_count = len(timepoint_columns)

        data_columns = DataColumn.objects.filter(dataset_id=dataset_id)
        for dc in data_columns:
            name = dc.name
            if dc.unit in ['day','hour','minute','second']:
                for colname in DataSetDataResource2.datapoint_cols['timepoint']:
                    # for legacy compatibility, omit the dc name if  
                    # if there is only one timepoint column (which is the norm)
                    if timepoint_col_count == 1:
                        base_cols.append('%s' % colname)
                    else:
                        base_cols.append('%s_%s' % (name,colname))
                        
            elif dc.data_type in [
                'small_molecule','cell','protein','antibody','otherreagent']:
                for colname in DataSetDataResource2.datapoint_cols[dc.data_type]:
                    base_cols.append('%s_%s' % (name,colname))
        
        return base_cols
    
    @staticmethod
    def get_datapoint_fields(dataset_id):
        
        data_columns = ( DataColumn.objects.filter(dataset_id=dataset_id)
            .exclude(data_type__in=[
                'small_molecule','cell','protein','antibody','otherreagent',
                'omero_image'])
            .exclude(unit__in=['day','hour','minute','second']) )
        
        datapoint_fields = OrderedDict()
        meta_field_info = get_listing(DataColumn(),['datacolumn'])
        
        for dc in data_columns.order_by('display_order'):
            specific_name = dc.name
            field_schema = {}
            for item in meta_field_info.items():
                meta_fi_attr = item[0]
                meta_fi = item[1]['fieldinformation']
                field_schema[meta_fi.get_camel_case_dwg_name()] = (
                    getattr(dc,meta_fi_attr) )
            datapoint_fields[specific_name] = field_schema
        return datapoint_fields
    
    @staticmethod
    def get_reagent_columns(dataset_id):
        
        col_field_info = {}
        for fi in FieldInformation.objects.all().filter(
            table__in=['smallmolecule','protein','cell','antibody','otherreagent',
                'smallmoleculebatch','proteinbatch','cellbatch','antibodybatch','otherreagentbatch']):
            col_field_info[fi.get_camel_case_dwg_name()] = {
                'reagentType': fi.table,
                'dwgName': fi.dwg_field_name,
                'description': fi.description 
                }
        
        data_columns = ( DataColumn.objects.filter(dataset_id=dataset_id)
            .filter(data_type__in=[
                'small_molecule','cell','protein','antibody','otherreagent']) )
        reagent_fields = OrderedDict()
        meta_field_info = get_listing(DataColumn(),['datacolumn'])
        for dc in data_columns.order_by('display_order'):
            specific_name = dc.name
            field_schema = {}
            for item in meta_field_info.items():
                meta_fi_attr = item[0]
                meta_fi = item[1]['fieldinformation']
                field_schema[meta_fi.get_camel_case_dwg_name()] = (
                    getattr(dc,meta_fi_attr) )
            reagent_fields[specific_name] = field_schema
            reagent_fields[specific_name]['columns'] = {}
            for dwg_name in DataSetDataResource2.datapoint_cols[dc.data_type]:
                col_name = '%s_%s' % (specific_name,dwg_name)
                reagent_fields[specific_name]['columns'][col_name] = col_field_info.get(dwg_name, {})
        return reagent_fields
        
    def get_schema(self, request, **kwargs):
        
        bundle = self.build_bundle(request=request)
        return self.create_response(request, self.build_schema(**kwargs))
        
    def build_schema(self,**kwargs):
        
        facility_id = kwargs.get('facility_id', None)
        if not facility_id:
            raise Http404(str(('no facility id given',request.path)))

        try:
            dataset = DataSet.objects.get(facility_id=facility_id)
            if(dataset.is_restricted and not request.user.is_authenticated()):
                raise Http401
            return self.generate_schema(dataset.id)
        except DataSet.DoesNotExist, e:
            logger.error(str(('no such facility id', facility_id)))
            raise e
    
    @staticmethod
    def generate_schema(dataset_id):    
        
        schema = {}
        cols = sorted(DataSetDataResource2.get_datarecord_fields(dataset_id))
        schema['cols'] = cols
        datapoints = DataSetDataResource2.get_datapoint_fields(dataset_id)
        schema['datapoints'] = datapoints
        schema['reagents'] = DataSetDataResource2.get_reagent_columns(dataset_id)
        schema['noCols'] = len(cols)
        schema['noDatapoints'] = len(datapoints)
        return schema

    def prepend_urls(self):
        
        return [
            url(r"^(?P<resource_name>%s)/(?P<facility_id>\d+)/schema%s$" 
                % ( self._meta.resource_name, trailing_slash()),
                self.wrap_view('get_schema'), name="api_get_schema"),
            url(r"^(?P<resource_name>%s)/(?P<facility_id>\d+)%s$" 
                % ( self._meta.resource_name, trailing_slash()), 
                self.wrap_view('dispatch_detail'), name="api_dispatch_detail"),
        ]                     



class Http401(Exception):
    pass


