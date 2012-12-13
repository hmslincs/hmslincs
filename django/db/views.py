import urllib2
import csv
import xlwt
import re

from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import render
from django.db import models
from django.db import connection
from django.utils.encoding import smart_str
from django.forms import ModelForm
from django.http import Http404,HttpResponseRedirect
from django.utils.safestring import mark_safe
from django.http import HttpResponse
from django.conf import settings
import django_tables2 as tables
from django_tables2 import RequestConfig
from django_tables2.utils import A  # alias for Accessor
from django.core.servers.basehttp import FileWrapper
import os

from db.models import SmallMolecule, SmallMoleculeBatch, Cell, Protein, DataSet, Library, FieldInformation,AttachedFile,DataRecord,DataColumn,LibraryMapping
#from db.CustomQuerySet import CustomQuerySet
from db.models import get_detail
from collections import OrderedDict
from PagedRawQuerySet import PagedRawQuerySet

import logging

logger = logging.getLogger(__name__)
APPNAME = 'db',
COMPOUND_IMAGE_LOCATION = "compound-images-by-facility-salt-id"  
AMBIT_COMPOUND_IMAGE_LOCATION = "ambit-study-compound-images-by-facility-salt-id"  
DATASET_IMAGE_LOCATION = "dataset-images-by-facility-id" 
facility_salt_id = " sm.facility_id || '-' || sm.salt_id " # Note: because we have a composite key for determining unique sm structures, we need to do this
facility_salt_batch_id = facility_salt_id + " || '-' || smb.facility_batch_id " # Note: because we have a composite key for determining unique sm structures, we need to do this
facility_salt_batch_id_2 = " trim( both '-' from (" + facility_salt_id + " || '-' || coalesce(smb.facility_batch_id::TEXT,'')))" # need this one for datasets, since they may be linked either to sm or smb - sde4
OMERO_IMAGE_COLUMN_TYPE = 'omero_image'

from dump_obj import dumpObj
def dump(obj):
    dumpObj(obj)

# --------------- View Functions -----------------------------------------------

def main(request):
    search = request.GET.get('search','')
    if(search != ''):
        queryset = SiteSearchManager().search(search, is_authenticated=request.user.is_authenticated());
        if(len(queryset) > 0):
            table = SiteSearchTable(queryset)
            RequestConfig(request, paginate={"per_page": 25}).configure(table)
            return render(request, 'db/index.html', {'table': table, 'search':search })
        else:
            return render(request, 'db/index.html')
    else:
        return render(request, 'db/index.html')

def cellIndex(request):
    search = request.GET.get('search','')
    logger.info(str(("is_authenticated:", request.user.is_authenticated(), 'search: ', search)))
    if(search != ''):
        criteria = "search_vector @@ to_tsquery(%s)"
        if(get_integer(search) != None):
            criteria = '(' + criteria + ' OR facility_id='+str(get_integer(search)) + ')' # TODO: seems messy here
        where = [criteria]
        if(not request.user.is_authenticated()): 
            where.append("( not is_restricted or is_restricted is NULL )")
        # postgres fulltext search with rank and snippets
        queryset = Cell.objects.extra(    # TODO: evaluate using django query language, not extra clause
            select={
                'snippet': "ts_headline(" + CellTable.snippet_def + ", to_tsquery(%s))",
                'rank': "ts_rank_cd(search_vector, to_tsquery(%s), 32)",
                },
            where=where,
            params=[search+":*"],
            select_params=[search,search],
            order_by=('-rank',)
            )        
    else:
        where = []
        if(not request.user.is_authenticated()): where.append("( not is_restricted or is_restricted is NULL)")
        queryset = Cell.objects.extra(
            where=where,
            order_by=('facility_id',))        
 
    if(len(queryset)>0):
        table = CellTable(queryset, template="db/custom_tables2_template.html")
        RequestConfig(request, paginate={"per_page": 25}).configure(table)
        outputType = request.GET.get('output_type','')
        if(outputType != ''):
            return send_to_file(outputType, 'cells', table, queryset, request )
    else:
        table = None
    return render(request, 'db/listIndex.html', {'table': table, 'search':search, 'heading': 'Cells' })

    
def cellDetail(request, facility_id):
    try:
        cell = Cell.objects.get(facility_id=facility_id) # todo: cell here
        if(cell.is_restricted and not request.user.is_authenticated()):
            return HttpResponse('Log in required.', status=401)
        details = {'object': get_detail(cell, ['cell',''])}
        dataset_ids = find_datasets_for_cell(cell.id)
        if(len(dataset_ids)>0):
            logger.info(str(('dataset ids for sm',dataset_ids)))
            where = []
            if(not request.user.is_authenticated()): 
                where.append("(not is_restricted or is_restricted is NULL)")
            queryset = DataSet.objects.filter(pk__in=list(dataset_ids)).extra(where=where,
                       order_by=('facility_id',))        
            details['datasets'] = DataSetTable(queryset)
        
        return render(request, 'db/cellDetail.html', details)
    except Cell.DoesNotExist:
        raise Http404

 
def proteinIndex(request):
    search = request.GET.get('search','')
    logger.info(str(("is_authenticated:", request.user.is_authenticated(), 'search: ', search)))
    if(search != ''):
        # NOTE: - change plaintext search to use "to_tsquery" as opposed to
        # "plainto_tsquery".  The "plain" version does not recognized the ":*"
        # syntax (override of the weighting syntax to do a greedy search)
        #        criteria = "search_vector @@ plainto_tsquery(%s)"
        criteria = "search_vector @@ to_tsquery(%s)"
        if(get_integer(search) != None):
            criteria = '(' + criteria + ' OR lincs_id='+str(get_integer(search)) + ')' # TODO: seems messy here
        where = [criteria]
        if(not request.user.is_authenticated()): 
            where.append("(not is_restricted or is_restricted is NULL)")
        # postgres fulltext search with rank and snippets
        queryset = Protein.objects.extra(
            select={
                'snippet': "ts_headline(" + ProteinTable.snippet_def + ", to_tsquery(%s))",
                'rank': "ts_rank_cd(search_vector, to_tsquery(%s), 32)",
                },
            where=where,
            params=[search+":*"],
            select_params=[search,search],
            order_by=('-rank',)
            )        
    else:
        where = []
        if(not request.user.is_authenticated()): where.append("(not is_restricted or is_restricted is NULL)")
        queryset = Protein.objects.extra(
            where=where,
            order_by=('lincs_id',))
    
    if(len(queryset)>0):
        table = ProteinTable(queryset)
        RequestConfig(request, paginate={"per_page": 25}).configure(table)
        outputType = request.GET.get('output_type','')
        if(outputType != ''):
            return send_to_file(outputType, 'proteins', table, queryset, request )
    else:
        table = None
    return render(request, 'db/listIndex.html', {'table': table, 'search':search, 'heading': 'Proteins' })
    
def proteinDetail(request, lincs_id):
    try:
        protein = Protein.objects.get(lincs_id=lincs_id) # todo: cell here
        if(protein.is_restricted and not request.user.is_authenticated()):
            return HttpResponse('Log in required.', status=401)
        details = {'object': get_detail(protein, ['protein',''])}
        
        # datasets table
        dataset_ids = find_datasets_for_protein(protein.id)
        if(len(dataset_ids)>0):
            logger.info(str(('dataset ids for sm',dataset_ids)))
            where = []
            if(not request.user.is_authenticated()): 
                where.append("(not is_restricted or is_restricted is NULL)")
            queryset = DataSet.objects.filter(pk__in=list(dataset_ids)).extra(where=where,
                       order_by=('facility_id',))        
            details['datasets'] = DataSetTable(queryset)

        # add in the LIFE System link: TODO: put this into the fieldinformation
        extralink = {   'title': 'LINCS Information Framework Page' ,
                        'name': 'LIFE Protein Information',
                        'link': 'http://baoquery.ccs.miami.edu/life/hms/summary?input=HMSL'+ str(protein.lincs_id) + '&mode=protein',
                        'value': protein.lincs_id }
        details['extralink'] = extralink
                
        return render(request, 'db/proteinDetail.html', details)
 
    except Protein.DoesNotExist:
        raise Http404

# TODO REFACTOR, DRY... 
def smallMoleculeIndex(request):
    search = request.GET.get('search','')
    logger.info(str(("is_authenticated:", request.user.is_authenticated(), 'search: ', search)))

    if(search != ''):
        criteria = "search_vector @@ to_tsquery(%s)"
        if(get_integer(search) != None):
            criteria = '(' + criteria + ' OR facility_id='+str(get_integer(search)) + ')' # TODO: seems messy here
            logger.info(str(('criteria',criteria)))
        where = [criteria]
        #if(not request.user.is_authenticated()): 
        #    where.append("(not is_restricted or is_restricted is NULL)")
        
        # postgres fulltext search with rank and snippets
        logger.info(str(("SmallMoleculeTable.snippet_def:",SmallMoleculeTable.snippet_def)))
        queryset = SmallMolecule.objects.extra(
            select={
                'snippet': "ts_headline(" + SmallMoleculeTable.snippet_def + ", to_tsquery(%s))",
                'rank': "ts_rank_cd(search_vector, to_tsquery(%s), 32)",
                },
            where=where,
            params=[search+":*"],
            select_params=[search+":*",search+":*"],
            order_by=('-rank',)
            )        
    else:
        where = []
        #if(not request.user.is_authenticated()): where.append("(not is_restricted or is_restricted is NULL)")
        queryset = SmallMolecule.objects.extra(
            where=where,
            order_by=('facility_id','salt_id'))        
    table = SmallMoleculeTable(queryset)

    outputType = request.GET.get('output_type','')
    logger.error(str(("outputType:", outputType)))
    if(outputType != ''):
        return send_to_file(outputType, 'small_molecule', table, queryset, request )
    
    RequestConfig(request, paginate={"per_page": 25}).configure(table)
    return render(request, 'db/listIndex.html', {'table': table, 'search':search, 'heading': 'Small molecules' })

def smallMoleculeDetail(request, facility_salt_id): # TODO: let urls.py grep the facility and the salt
    try:
        temp = facility_salt_id.split('-') # TODO: let urls.py grep the facility and the salt
        logger.info(str(('find sm detail for', temp)))
        facility_id = temp[0]
        salt_id = temp[1]
        sm = SmallMolecule.objects.get(facility_id=facility_id, salt_id=salt_id) 
        #if(sm.is_restricted and not request.user.is_authenticated()):
        #    return HttpResponse('Log in required.', status=401)
        smb = None
        if(len(temp)>2):
            smb = SmallMoleculeBatch.objects.get(smallmolecule=sm,facility_batch_id=temp[2]) 
        
    
        details = {'object': get_detail(sm, ['smallmolecule',''])}
        #TODO: set is_restricted if the user is not logged in only
        details['is_restricted'] = sm.is_restricted
        
        attachedFiles = get_attached_files(sm.facility_id,sm.salt_id)
        if(len(attachedFiles)>0):
            details['attached_files'] = AttachedFileTable(attachedFiles)
            
        # batch table
        if(smb == None):
            batches = SmallMoleculeBatch.objects.filter(smallmolecule=sm)
            if(len(batches)>0):
                details['batchTable']=SmallMoleculeBatchTable(batches)
        else:
            details['smallmolecule_batch']= get_detail(smb,['smallmoleculebatch',''])
            attachedFiles = get_attached_files(sm.facility_id,sm.salt_id,smb.facility_batch_id)
            if(len(attachedFiles)>0):
                details['attached_files_batch'] = AttachedFileTable(attachedFiles)        # attached file table        
        #attachedFiles = AttachedFile.objects.get(facility_id_for=facility_id, salt_id_for=salt_id)
        
        # datasets table
        dataset_ids = find_datasets_for_smallmolecule(sm.id)
        if(len(dataset_ids)>0):
            logger.info(str(('dataset ids for sm',dataset_ids)))
            where = []
            if(not request.user.is_authenticated()): 
                where.append("(not is_restricted or is_restricted is NULL)")
            queryset = DataSet.objects.filter(pk__in=list(dataset_ids)).extra(where=where,
                       order_by=('facility_id',))        
            details['datasets'] = DataSetTable(queryset)
        
        # nominal target dataset results information
        try:
            dataset = DataSet.objects.get(dataset_type='Nominal Targets')
            # NOTE: "col2" is "Is Nominal" (because of "Display Order"), also note: this column is numeric for now
            # TODO: column aliases should be set in the datacolumns worksheet (in a fieldinformation object, eventually)
            ntable = DataSetManager(dataset).get_table(whereClause=["smallmolecule_id=%d " % sm.id],
                                                       metaWhereClause = ["col2 = '1'"], 
                                                       column_exclusion_overrides=['facility_salt_batch','col2']) # exclude "is_nominal"
            logger.info(str(('ntable',ntable.data, len(ntable.data))))
            if(len(ntable.data)>0): details['nominal_targets_table']=ntable
            otable = DataSetManager(dataset).get_table(whereClause=["smallmolecule_id=%d " % sm.id], 
                                                       metaWhereClause=["col2 != '1'"], 
                                                       column_exclusion_overrides=['facility_salt_batch','col0','col2']) # exclude "effective conc", "is_nominal"
            logger.info(str(('otable',ntable.data, len(otable.data))))
            if(len(otable.data)>0): details['other_targets_table']=otable
        except DataSet.DoesNotExist:
            logger.warn('Nominal Targets dataset does not exist')
        
        image_location = COMPOUND_IMAGE_LOCATION + '/HMSL%d-%d.png' % (sm.facility_id,sm.salt_id)
        if(not sm.is_restricted or ( sm.is_restricted and request.user.is_authenticated())):
            if(can_access_image(request,image_location, sm.is_restricted)): details['image_location'] = image_location
            ambit_image_location = AMBIT_COMPOUND_IMAGE_LOCATION + '/HMSL%d-%d.png' % (sm.facility_id,sm.salt_id)
            if(can_access_image(request,ambit_image_location, sm.is_restricted)): details['ambit_image_location'] = ambit_image_location
        
        # add in the LIFE System link: TODO: put this into the fieldinformation
        extralink = {   'title': 'LINCS Information Framework Structure Page' ,
                        'name': 'LIFE Compound Information',
                        'link': 'http://baoquery.ccs.miami.edu/life/hms/summary?input=HMSL'+ str(sm.facility_id) + '&mode=compound',
                        'value': sm.facility_id }
        details['extralink'] = extralink
        
        return render(request,'db/smallMoleculeDetail.html', details)

    except SmallMolecule.DoesNotExist:
        raise Http404

def libraryIndex(request):
    search = request.GET.get('search','')
    queryset = LibrarySearchManager().search(search, is_authenticated=request.user.is_authenticated());

    if(len(queryset)>0):
        table = LibraryTable(queryset)
        RequestConfig(request, paginate={"per_page": 25}).configure(table)
        outputType = request.GET.get('output_type','')
        if(outputType != ''):
            return send_to_file(outputType, 'libraries', table, queryset, request )
    else:
        table = None
    return render(request, 'db/listIndex.html', {'table': table, 'search':search, 'heading': 'Libraries' })

def libraryDetail(request, short_name):
    search = request.GET.get('search','')
    try:
        library = Library.objects.get(short_name=short_name)
        if(library.is_restricted and not request.user.is_authenticated()):
            return HttpResponse('Unauthorized', status=401)
        response_dict = {'object': get_detail(library, ['library',''])}
        queryset = LibraryMappingSearchManager().search(query_string=search, is_authenticated=request.user.is_authenticated,library_id=library.id);
        if(len(queryset)>0): 
            table = LibraryMappingTable(queryset)
            RequestConfig(request, paginate={"per_page": 25}).configure(table)
            response_dict['table']=table
            
            outputType = request.GET.get('output_type','')
            logger.error(str(("outputType:", outputType)))
            if(outputType != ''):
                return send_to_file(outputType, 'library_'+library.short_name , table, queryset, request )
        
        return render(request,'db/libraryDetail.html', response_dict)
    except Library.DoesNotExist:
        raise Http404

def datasetIndex(request): #, type='screen'):
    search = request.GET.get('search','')
    logger.info(str(("is_authenticated:", request.user.is_authenticated(), 'search: ', search)))
    where = []
    if(search != ''):
        criteria = "search_vector @@ to_tsquery(%s)"
        if(get_integer(search) != None):
            criteria = '(' + criteria + ' OR facility_id='+str(get_integer(search)) + ')' # TODO: seems messy here
        where.append(criteria)
        if(not request.user.is_authenticated()): 
            where.append("(not is_restricted or is_restricted is NULL)")
            
        # postgres fulltext search with rank and snippets
        queryset = DataSet.objects.extra(
            select={
                'snippet': "ts_headline(" + DataSetTable.snippet_def + ", to_tsquery(%s) )",
                'rank': "ts_rank_cd(search_vector, to_tsquery(%s), 32)",
                },
            where=where,
            params=[search+":*"],
            select_params=[search,search],
            order_by=('-rank',)
            )        
    else:
        if(not request.user.is_authenticated()): 
            where.append("(not is_restricted or is_restricted is NULL)")
        queryset = DataSet.objects.extra(
            where=where,
            order_by=('facility_id',))        
    table = DataSetTable(queryset)
    
    outputType = request.GET.get('output_type','')
    if(outputType != ''):
        return send_to_file(outputType, 'datasetIndex', table, queryset, request )
        
    RequestConfig(request, paginate={"per_page": 25}).configure(table)
    heading = 'Datasets'
    return render(request, 'db/listIndex.html', {'table': table, 'search':search, 'type': type, 'heading': heading })

# Follows is a messy way to differentiate each tab for the dataset detail page (each tab calls it's respective method)
def getDatasetType(facility_id):
    facility_id = int(facility_id)
    if(facility_id < 30000 and facility_id >=  10000 ):
        return 'screen'
    elif(facility_id < 400000 and facility_id >= 300000 ):
        return 'study'
    else:
        raise Exception('unknown facility id range: ' + str(facility_id))
class Http401(Exception):
    pass

def datasetDetailMain(request, facility_id):
    try:
        details = datasetDetail(request,facility_id, 'main')
        return render(request,'db/datasetDetailMain.html', details )
    except Http401, e:
        return HttpResponse('Unauthorized', status=401)
    
def datasetDetailCells(request, facility_id):
    try:
        details = datasetDetail(request,facility_id, 'cells')
        return render(request,'db/datasetDetailCells.html', details)
    except Http401, e:
        return HttpResponse('Unauthorized', status=401)
    
def datasetDetailProteins(request, facility_id):
    try:
        details = datasetDetail(request,facility_id,'proteins')
        return render(request,'db/datasetDetailProteins.html', details)
    except Http401, e:
        return HttpResponse('Unauthorized', status=401)
    
def datasetDetailResults(request, facility_id):
    try:
        details = None

        outputType = request.GET.get('output_type','')
        if(outputType != ''):
            dataset = DataSet.objects.get(facility_id=facility_id)
            if(dataset.is_restricted and not request.user.is_authenticated()):
                raise Http401
            manager = DataSetManager(dataset)
            search = request.GET.get('search','')
            cursor = manager.get_cursor(search=search)
            datacolumns = DataColumn.objects.filter(dataset=dataset).order_by('display_order')
            return send_to_file1(outputType, 'dataset_'+str(facility_id), datacolumns, cursor, request )
        
        details = datasetDetail(request,facility_id, 'results')

        return render(request,'db/datasetDetailResults.html', details)
    except Http401, e:
        return HttpResponse('Unauthorized', status=401)

def datasetDetail(request, facility_id, sub_page):
    try:
        dataset = DataSet.objects.get(facility_id=facility_id)
        if(dataset.is_restricted and not request.user.is_authenticated()):
            raise Http401
    except DataSet.DoesNotExist:
        raise Http404

    manager = DataSetManager(dataset)

    
    details =  {'object': get_detail(manager.dataset, ['dataset','']),
                'facilityId': facility_id,
                'type':getDatasetType(facility_id),
                'has_cells':manager.has_cells(),
                'has_proteins':manager.has_proteins()}
    
    if(sub_page == 'results'):
        search = request.GET.get('search','')
        table = manager.get_table(search=search,metaWhereClause=[],parameters=[]) # TODO: not sure why have to set metaWhereClause=[] to erase former where clause (it is persistent somewhere?) - sde4
        RequestConfig(request, paginate={"per_page": 25}).configure(table)
        details['result_table'] = table
        details['search'] = search
        
    if(sub_page == 'cells'):
        if(manager.has_cells()):
            cellTable = CellTable(manager.cell_queryset)
            RequestConfig(request, paginate={"per_page": 25}).configure(cellTable)
            details['cellTable'] = cellTable
    if(sub_page == 'proteins'):
        if(manager.has_proteins()):
            proteinTable = ProteinTable(manager.protein_queryset)
            RequestConfig(request, paginate={"per_page": 25}).configure(proteinTable)
            details['proteinTable'] = proteinTable

    image_location = DATASET_IMAGE_LOCATION + '/%s.png' % str(facility_id)
    if(can_access_image(request,image_location)): details['image_location'] = image_location
    
    return details

class SnippetColumn(tables.Column):
    def render(self, value):
        return mark_safe(value)

class TypeColumn(tables.Column):
    def render(self, value):
        if value == "cell_detail": return "Cell"
        elif value == "sm_detail": return "Small Molecule"
        elif value == "dataset_detail": return "Screen"
        elif value == "protein_detail": return "Protein"
        else: raise Exception("Unknown type: "+value)

from math import log, pow

class PagedTable(tables.Table):
    
    def __init__(self,*args,**kwargs):
        kwargs['template']="db/custom_tables2_template.html"
        super(PagedTable,self).__init__(*args,**kwargs)

    def previous_ten_page_number(self):
        if(self.page):
            temp = self.page.number-10
            if(temp<1): temp=1
            return temp

    def next_ten_page_number(self):
        if(self.page):
            temp = self.page.number+10
            jump_exp = int(log(self.paginator.num_pages,10))
            if(jump_exp > 1): temp = self.page.number + int(pow(10,(jump_exp-1)))
            logger.info(str(('self.page.next_page_number()', self.page.next_page_number(),self.paginator.num_pages, temp)))
            if( temp > self.paginator.num_pages ): 
                temp=self.paginator.num_pages
            return temp
        
    def page_start(self):
        if(self.page):
            return self.paginator.per_page * (self.page.number-1)
        
    def page_end(self):
        if(self.page):
            temp = self.page_start()+self.paginator.per_page
            logger.info(str(('page_end:' , temp, self.paginator.count )))
            if(temp > self.paginator.count): return self.paginator.count
            return temp


class DataSetTable(PagedTable):
    id = tables.Column(visible=False)
    facility_id = tables.LinkColumn("dataset_detail", args=[A('facility_id')])
    protocol = tables.Column(visible=False) 
    references = tables.Column(visible=False)
    rank = tables.Column()
    snippet = SnippetColumn()
#    snippet_def = ("coalesce(facility_id,'') || ' ' || coalesce(title,'') || ' ' || coalesce(summary,'') || ' ' || coalesce(lead_screener_firstname,'') || ' ' || coalesce(lead_screener_lastname,'')|| ' ' || coalesce(lead_screener_email,'') || ' ' || "  +           
#                   "coalesce(lab_head_firstname,'') || ' ' || coalesce(lab_head_lastname,'')|| ' ' || coalesce(lab_head_email,'')")
    snippet_def = (" || ' ' || ".join(map( lambda x: "coalesce("+x.field+",'') ", FieldInformation.manager.get_search_fields(DataSet))))
    class Meta:
        model = DataSet
        orderable = True
        attrs = {'class': 'paleblue'}
        #exclude = ('id','lead_screener_email','lead_screener_firstname','lead_screener_lastname','lab_head_firstname','lab_head_lastname','lab_head_email','protocol_references','is_restricted','rank','snippet') 

    def __init__(self, table):
        super(DataSetTable, self).__init__(table)
        
        set_table_column_info(self, ['dataset',''])  

def set_field_information_to_table_column(fieldname,table_names,column):
    try:
        fi = FieldInformation.manager.get_column_fieldinformation_by_priority(fieldname,table_names)
        column.attrs['th']={'title':fi.get_column_detail()}
        column.verbose_name = fi.get_verbose_name()
    except (ObjectDoesNotExist) as e:
        raise Exception(str(('no fieldinformation found for field:', fieldname,e)))
    
# OMERO Image: TODO: only include this if the dataset has images
OMERO_IMAGE_TEMPLATE = '''
   <a href="#" onclick='window.open("https://lincs-omero.hms.harvard.edu/webclient/img_detail/{{ record.%s }}", "Image","height=700,width=800")' ><img src='https://lincs-omero.hms.harvard.edu/webgateway/render_thumbnail/{{ record.%s }}/32/' alt='image if available' ></a>
'''
class TestColumn(tables.Column):
    def render(self, value):
        return 'xxx'
#        return value.upper()
        
class DataSetResultTable(PagedTable):
    """
    Override of the tables.Table - columns are defined manually to conform to the DataSetManager query fields; 
    fields are added as Table "base_columns" in the __init__ method.
    # TODO: the cursor is converted to a list of dicts, all in memory; implement pagination
    # TODO: Augment each column/verbose_name with column info for each of the dataset fields, 
    just like set_table_column_info does with the fieldinformation class 
    """
    defined_base_columns = []
    id = tables.Column(visible=False)
    defined_base_columns.append('id')
    
    facility_salt_batch = tables.LinkColumn('sm_detail', args=[A('facility_salt_batch')])
    facility_salt_batch.attrs['td'] = {'nowrap': 'nowrap'}
    defined_base_columns.append('facility_salt_batch')
    set_field_information_to_table_column('facility_salt_batch', ['smallmoleculebatch'], facility_salt_batch)
    
    sm_name = tables.LinkColumn('sm_detail', args=[A('facility_salt_batch')])
    defined_base_columns.append('sm_name')
    set_field_information_to_table_column('name', ['smallmolecule'], sm_name)

    cell_name = tables.LinkColumn('cell_detail',args=[A('cell_facility_id')], visible=False, verbose_name='Cell Name') 
    defined_base_columns.append('cell_name')
    set_field_information_to_table_column('name', ['cell'], cell_name)
    
    cell_facility_id = tables.LinkColumn('cell_detail',args=[A('cell_facility_id')], visible=False, verbose_name='Cell Facility ID') 
    defined_base_columns.append('cell_facility_id')
    set_field_information_to_table_column('facility_id', ['cell'], cell_facility_id)
    
    protein_name = tables.LinkColumn('protein_detail',args=[A('protein_lincs_id')], visible=False, verbose_name='Protein Name') 
    defined_base_columns.append('protein_name')
    set_field_information_to_table_column('name', ['protein'], protein_name)
    
    protein_lincs_id = tables.LinkColumn('protein_detail',args=[A('protein_lincs_id')], visible=False, verbose_name='Protein LINCS ID') 
    defined_base_columns.append('protein_lincs_id')
    set_field_information_to_table_column('lincs_id', ['protein'], protein_lincs_id)
    
    plate = tables.Column()
    defined_base_columns.append('plate')
    set_field_information_to_table_column('plate', ['datarecord'], plate)
    
    well = tables.Column()
    defined_base_columns.append('well')
    set_field_information_to_table_column('well', ['datarecord'], well)
    
    control_type = tables.Column()
    defined_base_columns.append('control_type')
    set_field_information_to_table_column('control_type', ['datarecord'], control_type)
        
    class Meta:
        orderable = True
        attrs = {'class': 'paleblue'}
    
    def __init__(self, queryset, ordered_datacolumns,  
                 show_cells=False, show_proteins=False, 
                 column_exclusion_overrides=None, *args, **kwargs):
        # Follows is to deal with a bug - columns from one table appear to be injecting into other tables!!
        # This indicates that we are doing something wrong here by defining columns dynamically on the class "base_columns" attribute
        # So, to fix, we should redefine all of the base_columns every time here.  
        # For now, what is done is the "defined_base_columns" are preserved, then others are added.
        for name in self.base_columns.keys():
            if name not in self.defined_base_columns:
                logger.debug(str(('deleting column from the table', name,self.defined_base_columns)))
                del self.base_columns[name]
        
        temp = ['facility_salt_batch','sm_name']
        if(show_cells): 
            temp.append('cell_name')
            temp.append('cell_facility_id')
        if(show_proteins): 
            temp.append('protein_name')
            temp.append('protein_lincs_id')
        temp.extend(['col'+str(i) for (i,x) in enumerate(ordered_datacolumns)])
        temp.extend(['plate','well','control_type'])
        ordered_names = temp
        
        #logger.debug(str(('columns_to_names', columns_to_names, 'orderedNames', ordered_names)))
        #for name,verbose_name in columns_to_names.items():
        for i,dc in enumerate(ordered_datacolumns):    
            #logger.debug(str(('create column:',name,verbose_name)))
            col = 'col%d'%i
            logger.debug(str(('create column', col, dc.id, dc.data_type)))
            if(dc.data_type.lower() != OMERO_IMAGE_COLUMN_TYPE):
                self.base_columns[col] = tables.Column(verbose_name=dc.name)
            else:
                #logger.debug(str(('omero_image column template', TEMPLATE % ('omero_image_id','omero_image_id'))))
                self.base_columns[col] = tables.TemplateColumn(OMERO_IMAGE_TEMPLATE % (col,col), verbose_name=dc.name)

                
        # Note: since every instance reuses the base_columns, each time the visibility must be set.
        # Todo: these colums should be controlled by the column_exclusion_overrides
        if(show_cells):
            self.base_columns['cell_name'].visible = True
            self.base_columns['cell_facility_id'].visible = True
        else:
            self.base_columns['cell_name'].visible = False
            self.base_columns['cell_facility_id'].visible = False
        if(show_proteins):
            self.base_columns['protein_name'].visible = True
            self.base_columns['protein_lincs_id'].visible = True
        else:
            self.base_columns['protein_name'].visible = False
            self.base_columns['protein_lincs_id'].visible = False
        logger.debug(str(('base columns:', self.base_columns)))
        # Field information section: TODO: for the datasetcolumns, use the database information for these.
        # set_table_column_info(self, ['smallmolecule','cell','protein',''])  

        # TODO: why does this work with the super call last?  Keep an eye on forums for creating dynamic columns with tables2
        # for instance: https://github.com/bradleyayers/django-tables2/issues/70
        super(DataSetResultTable, self).__init__(queryset, *args, **kwargs)
        if(self.exclude): self.exclude = tuple(list(self.exclude).extend(column_exclusion_overrides))
        else: self.exclude = tuple(column_exclusion_overrides)
        self.sequence = ordered_names


# TODO: this class has grown - needs refactoring to allow ability to filter in a less clumsy way
# (who are we kidding, this is raw sql, after all).
class DataSetManager():
    
    def __init__(self,dataset,is_authenticated=False):
        self.dataset = dataset
        self.dataset_id = dataset.id
        self.cell_queryset = self.cells_for_dataset(self.dataset_id)  # TODO: use ORM
        self.protein_queryset = self.proteins_for_dataset(self.dataset_id)
                
    class DatasetForm(ModelForm):
        class Meta:
            model = DataSet           
            order = ('facility_id', '...')
            exclude = ('id', 'molfile') 

    def has_cells(self):
        return len(self.cell_queryset) > 0
    
    def has_proteins(self):
        return len(self.protein_queryset) > 0
    
    def get_cursor(self, whereClause=[],metaWhereClause=[],column_exclusion_overrides=[],parameters=[],search=''): 
        if(search != ''):
            searchParam = '%'+search+'%'
            searchClause = "facility_salt_batch like %s or sm_name like %s or sm_alternative_names like %s "
            searchParams = [searchParam,searchParam,searchParam]
            if(self.has_cells()): 
                searchClause += " or cell_facility_id::TEXT like %s or cell_name like %s "
                searchParams += [searchParam,searchParam]
            if(self.has_proteins()): 
                searchClause += " or protein_name like %s or protein_lincs_id::TEXT like %s"
                searchParams += [searchParam,searchParam]
                
            logger.info(str(('proteins', self.protein_queryset)))
            metaWhereClause.append(searchClause)
            parameters += searchParams
            
        logger.info(str(('search',search,'metaWhereClause',metaWhereClause,'parameters',parameters)))
        
        self.dataset_info = self._get_query_info(whereClause,metaWhereClause) # TODO: column_exclusion_overrides
        cursor = connection.cursor()
        cursor.execute(self.dataset_info.query_sql,parameters)
        return cursor

    def get_table(self, whereClause=[],metaWhereClause=[],column_exclusion_overrides=[],parameters=[],search=''): 
        if(search != ''):
            searchParam = '%'+search+'%'
            searchClause = "facility_salt_batch like %s or lower(sm_name) like lower(%s) or lower(sm_alternative_names) like lower(%s) "
            searchParams = [searchParam,searchParam,searchParam]
            if(self.has_cells()): 
                searchClause += " or cell_facility_id::TEXT like %s or lower(cell_name) like lower(%s) "
                searchParams += [searchParam,searchParam]
            if(self.has_proteins()): 
                searchClause += " or protein_lincs_id::TEXT like %s or lower(protein_name) like lower(%s) "
                searchParams += [searchParam,searchParam]
                
            logger.info(str(('proteins', self.protein_queryset)))
            metaWhereClause.append(searchClause)
            parameters += searchParams
            
        logger.info(str(('search',search,'metaWhereClause',metaWhereClause,'parameters',parameters)))
        self.dataset_info = self._get_query_info(whereClause,metaWhereClause)
        #sql_for_count = 'SELECT count(distinct id) from db_datarecord where dataset_id ='+ str(self.dataset_id)
        queryset = PagedRawQuerySet(self.dataset_info.query_sql,self.dataset_info.count_query_sql, connection, 
                                    parameters=parameters,order_by=['datarecord_id'], verbose_name_plural='records')
        if(not self.has_plate_wells_defined(self.dataset_id)): column_exclusion_overrides.extend(['plate','well'])
        if(not self.has_control_type_defined(self.dataset_id)): column_exclusion_overrides.append('control_type')
        _table = DataSetResultTable(queryset,
                                  self.dataset_info.datacolumns, 
                                  self.has_cells(), 
                                  self.has_proteins(),
                                  column_exclusion_overrides) # TODO: again, all these flags are confusing
        setattr(_table,'verbose_name_plural','records')
        setattr(_table,'verbose_name','record')
        return _table

    class DatasetInfo:
        # TODO: should be a fieldinformation here
        # An ordered list of DataColumn entities for this Dataset
        datacolumns = []
        query_sql = ''
        count_query_sql = ''
        
    

    def _get_query_info(self, whereClause=[],metaWhereClause=[]):
        """
        generate a django tables2 table
        TODO: move the logic out of the view: so that it can be shared with the tastypie api (or make this rely on tastypie)
        params:
        whereClause: use this to filter datarecords in the inner query
        metaWhereClause: use this to filter over the entire resultset: any column (as the entire query is made into a subquery)
        """
        logger.debug(str(('_get_query_info', whereClause,metaWhereClause)))
    
        #datacolumns = self.get_dataset_columns(self.dataset.id)
        # TODO: should be a fieldinformation here
        datacolumns = DataColumn.objects.filter(dataset=self.dataset).order_by('display_order')
        # Create a query on the fly that pivots the values from the datapoint table, making one column for each datacolumn type
        # use the datacolumns to make a query on the fly (for the DataSetManager), and make a DataSetResultSearchTable on the fly.
        #dataColumnCursor = connection.cursor()
        #dataColumnCursor.execute("SELECT id, name, data_type, precision from db_datacolumn where dataset_id = %s order by id asc", [dataset_id])
        logger.info(str(('dataset columns:', datacolumns)))
    
        # Need to construct something like this:
        # SELECT distinct (datarecord_id), smallmolecule_id, sm.facility_id || '-' || sm.salt_id as facility_id,
        #        (SELECT int_value as col1 from db_datapoint dp1 where dp1.datacolumn_id=2 and dp1.datarecord_id = dp.datarecord_id) as col1, 
        #        (SELECT int_value as col2 from db_datapoint dp2 where dp2.datarecord_id=dp.datarecord_id and dp2.datacolumn_id=3) as col2 
        #        from db_datapoint dp join db_datarecord dr on(datarecord_id=dr.id) join db_smallmoleculebatch smb on(smb.id=dr.smallmolecule_batch_id) join db_smallmolecule sm on(sm.id=smb.smallmolecule_id) 
        #        where dp.dataset_id = 1 order by datarecord_id;
        
#        queryString =   "SELECT distinct (dr_id) as datarecord_id,"
        queryString =   "SELECT dr_id as datarecord_id,"
        queryString +=  " trim( both '-' from ( sm_facility_id || '-' || salt_id  || '-' || coalesce(smb_facility_batch_id::TEXT,''))) as facility_salt_batch " # Note: because we have a composite key for determining unique sm structures, we need to do this
        queryString +=  ' ,sm_name, sm_alternative_names, plate, well, control_type '
        show_cells = self.has_cells()
        show_proteins = self.has_proteins()
        if(show_cells): queryString += ", cell_id, cell_name, cell_facility_id " 
        if(show_proteins): queryString += ", protein_id,  protein_name,  protein_lincs_id " 

        for i,dc in enumerate(datacolumns):
            alias = "dp"+str(i)
            columnName = "col" + str(i)
            column_to_select = None
            if(dc.data_type == 'Numeric' or dc.data_type == 'omero_image'):
                if dc.precision == 0 or dc.data_type == 'omero_image':
                    column_to_select = "int_value"
                else:
                    column_to_select = "round( float_value::numeric, 2 )" # TODO: specify the precision in the fieldinformation for this column
            else:
                column_to_select = "text_value"
            queryString +=  (",(SELECT " + column_to_select + " FROM db_datapoint " + alias + 
                                " where " + alias + ".datacolumn_id="+str(dc.id) + " and " + alias + ".datarecord_id=dr_id) as " + columnName )
        queryString += " FROM  ( SELECT dr.id as dr_id, "
        queryString += " sm.id as smallmolecule_id, sm.facility_id as sm_facility_id, sm.salt_id, smb.facility_batch_id as smb_facility_batch_id, sm.name as sm_name, sm.alternative_names as sm_alternative_names " 
        queryString += " ,plate, well, control_type " 
        if(show_cells):     queryString += " ,cell_id, cell.name as cell_name, cell.facility_id as cell_facility_id " 
        if(show_proteins):  queryString += " ,protein.name as protein_name, protein.lincs_id as protein_lincs_id, protein.id as protein_id "
        fromClause = " FROM db_datarecord dr " 
        fromClause += " LEFT JOIN db_smallmolecule sm on(dr.smallmolecule_id = sm.id) "
        fromClause += " LEFT JOIN db_smallmoleculebatch smb on(smb.smallmolecule_id=sm.id and smb.facility_batch_id=dr.batch_id) "
        if(show_cells):     fromClause += " LEFT JOIN db_cell cell on(cell.id=dr.cell_id ) "
        if(show_proteins):  fromClause += " LEFT JOIN db_protein protein on (protein.id=dr.protein_id) "
        fromClause += " WHERE dr.dataset_id = " + str(self.dataset.id)
        # Ok to show these results even if the linked entity is restricted
        #        queryString += " and ( not sm.is_restricted or sm.is_restricted is NULL) "
        #        if(show_cells): queryString += " and (not cell.is_restricted o`r cell.is_restricted is NULL) "
        #        if(show_proteins): queryString += " and (not protein.is_restricted or protein.is_restricted is NULL) "
        queryString += fromClause
        countQueryString = "SELECT count(*) " + fromClause
        
        inner_alias = 'x'
        queryString += " order by dr.id ) as " + inner_alias #LIMIT 5000 ) as x """
        
        logger.info(str(('whereClause',whereClause)))      
        queryString += ' WHERE 1=1 '
        if(len(whereClause)>0):
            queryString = (" AND "+inner_alias+".").join([queryString]+whereClause) # extra filters
            countQueryString = " AND dr.".join([countQueryString]+whereClause) # extra filters
        
        if(len(metaWhereClause)>0):
            fromClause = " FROM ( " + queryString + ") a  where " + (" AND ".join(metaWhereClause))
            queryString = "SELECT * " + fromClause
            # all bets are off if using the metawhereclause, unfortunately, since it can filter on the inner, dynamic cols
            countQueryString = "SELECT count(*) " + fromClause
            #countQueryString = " AND ".join([countQueryString]+metaWhereClause)
        if(logger.isEnabledFor(logging.DEBUG)): 
            logger.debug(str(('--querystrings---',queryString, countQueryString)))
        dataset_info = self.DatasetInfo()
        dataset_info.query_sql = queryString
        dataset_info.count_query_sql = countQueryString
        dataset_info.datacolumns = datacolumns
        return dataset_info
   

    #---------------Supporting classes and functions--------------------------------
    def get_dataset_columns(self, dataset_id):
        # Create a query on the fly that pivots the values from the datapoint table, making one column for each datacolumn type
        # use the datacolumns to make a query on the fly (for the DataSetManager), and make a DataSetResultSearchTable on the fly.
        dataColumnCursor = connection.cursor()
        dataColumnCursor.execute("SELECT id, name, data_type, precision FROM db_datacolumn WHERE dataset_id = %s order by id asc", [dataset_id])
        return dataColumnCursor.fetchall()
    
    def get_dataset_column_names(self,dataset_id):
        column_names = []
        for datacolumn_id, name, datatype, precision in self.get_dataset_columns(dataset_id):
            column_names.append(name)
        return column_names
         
    def cells_for_dataset(self, dataset_id):
        cursor = connection.cursor()
        sql = 'SELECT cell.* FROM db_cell cell WHERE cell.id in (SELECT distinct(cell_id) FROM db_datarecord dr WHERE dr.dataset_id=%s) order by cell.name'
        # TODO: like this: SELECT * FROM TABLE, (SELECT COLUMN FROM TABLE) as dummytable WHERE dummytable.COLUMN = TABLE.COLUMN;
        cursor.execute(sql, [dataset_id])
        return dictfetchall(cursor)
        
    def proteins_for_dataset(self,dataset_id):
        cursor = connection.cursor()
        sql = 'SELECT protein.* FROM db_protein protein WHERE protein.id in (SELECT distinct(protein_id) FROM db_datarecord dr WHERE dr.dataset_id=%s) order by protein.name'
        cursor.execute(sql, [dataset_id])
        return dictfetchall(cursor)
    
#    def has_omero_images(self, dataset_id):
#        res = len(DataSet.objects.get(id=dataset_id).datacolumn_set.filter(data_type='omero_image'))
#        #res = len(DataColumn.objects.all().filter(dataset_id=dataset_id, data_type=))
#        logger.info(str(('len(DataRecord.objects.all().filter(dataset_id=dataset_id).filter(omero_image_id__isnull=False))',len(DataRecord.objects.all().filter(dataset_id=dataset_id).filter(omero_image_id__isnull=False)))))
#        return res
    
    def has_plate_wells_defined(self, dataset_id):
        res= len(DataRecord.objects.all().filter(dataset_id=dataset_id).filter(plate__isnull=False).filter(well__isnull=False))>0
        return res

    def has_control_type_defined(self, dataset_id):
        res= len(DataRecord.objects.all().filter(dataset_id=dataset_id).filter(control_type__isnull=False))>0
        return res


def find_datasets_for_protein(protein_id):
    datasets = [x.id for x in DataSet.objects.filter(datarecord__protein__id=protein_id).distinct()]
    logger.info(str(('datasets',datasets)))
    return datasets

def find_datasets_for_cell(cell_id):
    datasets = [x.id for x in DataSet.objects.filter(datarecord__cell__id=cell_id).distinct()]
    logger.info(str(('datasets',datasets)))
    return datasets

def find_datasets_for_smallmolecule(smallmolecule_id):
    datasets = [x.id for x in DataSet.objects.filter(datarecord__smallmolecule__id=smallmolecule_id).distinct()]
    logger.info(str(('datasets',datasets)))
    return datasets
    #    cursor = connection.cursor()
    #    sql = ( 'SELECT distinct(dataset_id) from db_datarecord dr' +  
    #            ' join db_smallmoleculebatch smb on(dr.smallmolecule_batch_id=smb.id) ' + 
    #            ' WHERE smb.smallmolecule_id=%s' )
    #    cursor.execute(sql, [smallmolecule_id])
    #    dataset_ids = [];
    #    for val in cursor.fetchall():
    #        logger.info(str(('val',val)))
    #        dataset_ids.append(val[0])
    #        
    #    return dataset_ids
            
class LibraryMappingTable(PagedTable):
    facility_salt_batch = tables.LinkColumn("sm_detail", args=[A('facility_salt_batch')]) 
    sm_name = tables.Column()
    is_control = tables.Column() 
    well = tables.Column()
    plate = tables.Column()
    display_concentration = tables.Column(order_by='concentration')
    #concentration = tables.Column()
    #concentration_unit = tables.Column()
        
    snippet_def = (" || ' ' || ".join(map( lambda x: "coalesce("+x.field+",'') ", FieldInformation.manager.get_search_fields(SmallMolecule)))) # TODO: specialized search for librarymapping, if needed
    
    class Meta:
        #model = LibraryMapping
        orderable = True
        attrs = {'class': 'paleblue'}
        
    def __init__(self, table, show_plate_well=False,*args, **kwargs):
        super(LibraryMappingTable, self).__init__(table)
        sequence_override = ['facility_salt_batch']
        
        set_table_column_info(self, ['smallmolecule','smallmoleculebatch','librarymapping',''],sequence_override)  
                
class LibraryMappingSearchManager(models.Model):
    """
    Used for librarymapping display
    """
    def search(self, query_string='', is_authenticated=False, library_id=None):
        if(library_id == None): 
            raise Exception('Must define a library id to use the LibraryMappingSearchManager')

        query_string = query_string.strip()
        sql = "SELECT " + facility_salt_batch_id + " as facility_salt_batch , sm.name as sm_name, lm.concentration ||' '||lm.concentration_unit as display_concentration, lm.* "
        sql += " FROM db_library l "
        sql += " join db_librarymapping lm on(lm.library_id=l.id) " 
        sql += " LEFT JOIN db_smallmoleculebatch smb on (smb.id=lm.smallmolecule_batch_id) "
        sql += " LEFT JOIN db_smallmolecule sm on(smb.smallmolecule_id=sm.id) " 
        
        where = 'WHERE 1=1 '
        if(query_string != '' ):
            # TODO: how to include the smb snippet (once it's created)
            if(get_integer(query_string) != None):
                where = ' WHERE sm.facility_id='+str(get_integer(query_string)) 
            else: 
                where = ", to_tsquery(%s) as query  WHERE sm.search_vector @@ query "
            # TODO: search by facility-salt-batch
        where += ' and library_id='+ str(library_id)
        if(not is_authenticated):
            where += ' and ( not sm.is_restricted or sm.is_restricted is NULL)' # TODO: NOTE, not including: ' and not l.is_restricted'; library restriction will only apply to viewing the library explicitly (the meta data, and selection of compounds)
            
        sql += where
        sql += " order by "
        if(library_id != None):
            sql += "plate, well, smb.facility_batch_id, "
        sql += " sm.facility_id, sm.salt_id "
        
        logger.info(str(('sql',sql)))
        # TODO: the way we are separating query_string out here is a kludge
        cursor = connection.cursor()
        if(query_string != ''):
            cursor.execute(sql, [query_string + ':*'])
        else:
            cursor.execute(sql)
        v = dictfetchall(cursor)
        return v
    
class SmallMoleculeBatchTable(PagedTable):
    
    facility_salt_batch = tables.LinkColumn("sm_detail", args=[A('facility_salt_batch')])
    facility_salt_batch.attrs['td'] = {'nowrap': 'nowrap'}
    
    class Meta:
        model = SmallMoleculeBatch
        orderable = True
        attrs = {'class': 'paleblue'}

    def __init__(self, table, show_plate_well=False,*args, **kwargs):
        super(SmallMoleculeBatchTable, self).__init__(table)
        sequence_override = ['facility_salt_batch']
        set_table_column_info(self, ['smallmolecule','smallmoleculebatch',''],sequence_override)  

class SmallMoleculeTable(PagedTable):
    #facility_id = tables.Column(visible=False)
    facility_salt = tables.LinkColumn("sm_detail", args=[A('facility_salt')], order_by=['facility_id','salt_id']) 
    facility_salt.attrs['td'] = {'nowrap': 'nowrap'}
    rank = tables.Column()
    snippet = tables.Column()

    snippet_def = (" || ' ' || ".join(map( lambda x: "coalesce("+x.field+",'') ", FieldInformation.manager.get_search_fields(SmallMolecule)))) 

    class Meta:
        model = SmallMolecule #[SmallMolecule, SmallMoleculeBatch]
        orderable = True
        attrs = {'class': 'paleblue'}
    def __init__(self, table, show_plate_well=False,*args, **kwargs):
        super(SmallMoleculeTable, self).__init__(table)
        sequence_override = ['facility_salt']
        set_table_column_info(self, ['smallmolecule','smallmoleculebatch',''],sequence_override)  

class AttachedFileTable(PagedTable):
    filename=tables.LinkColumn("download_attached_file", args=[A('id')])
    #snippet_def = (" || ' ' || ".join(map( lambda x: "coalesce("+x.field+",'') ", FieldInformation.manager.get_search_fields(SmallMolecule)))) # TODO: specialized search for librarymapping, if needed
    
    class Meta:
        model = AttachedFile
        orderable = True
        attrs = {'class': 'paleblue'}
        
    def __init__(self, table,*args, **kwargs):
        super(AttachedFileTable, self).__init__(table)
        sequence_override = []
        set_table_column_info(self, ['attachedfile',''],sequence_override)  
            
class SmallMoleculeForm(ModelForm):
    class Meta:
        model = SmallMolecule           
        order = ('facility_id', '...')
        exclude = ('id', 'molfile') 

class CellTable(PagedTable):
    facility_id = tables.LinkColumn("cell_detail", args=[A('facility_id')])
    rank = tables.Column()
    snippet = SnippetColumn()
    id = tables.Column(verbose_name='CLO Id')
    
    # TODO: define the snippet dynamically, using all the text fields from the model
    # TODO: add the facility_id
#    snippet_def = ("coalesce(name,'') || ' ' || coalesce(id,'') || ' ' || coalesce(alternate_name,'') || ' ' || " +  
#                   "coalesce(alternate_id,'') || ' ' || coalesce(center_name,'') || ' ' || coalesce(center_specific_id,'') || ' ' || " +  
#                   "coalesce(assay,'') || ' ' || coalesce(provider_name,'') || ' ' || coalesce(provider_catalog_id,'') || ' ' || coalesce(batch_id,'') || ' ' || " + 
#                   "coalesce(organism,'') || ' ' || coalesce(organ,'') || ' ' || coalesce(tissue,'') || ' ' || coalesce(cell_type,'') || ' ' ||  " +
#                   "coalesce(cell_type_detail,'') || ' ' || coalesce(disease,'') || ' ' || coalesce(disease_detail,'') || ' ' ||  " +
#                   "coalesce(growth_properties,'') || ' ' || coalesce(genetic_modification,'') || ' ' || coalesce(related_projects,'') || ' ' || " + 
#                   "coalesce(recommended_culture_conditions)")
    snippet_def = (" || ' ' || ".join(map( lambda x: "coalesce("+x.field+",'') ", FieldInformation.manager.get_search_fields(Cell))))
    class Meta:
        model = Cell
        orderable = True
        attrs = {'class': 'paleblue'}
        #sequence = ('facility_id', '...')
        #exclude = ('id','recommended_culture_conditions', 'verification_reference_profile', 'mutations_explicit', 'mutations_reference')
    def __init__(self, table,*args,**kwargs):
        super(CellTable, self).__init__(table,*args,**kwargs)
        sequence_override = ['facility_id']    
        set_table_column_info(self, ['cell',''], sequence_override)  
                        
class ProteinTable(PagedTable):
    lincs_id = tables.LinkColumn("protein_detail", args=[A('lincs_id')])
    rank = tables.Column()
    snippet = SnippetColumn()
    snippet_def = (" || ' ' || ".join(map( lambda x: "coalesce("+x.field+",'') ", FieldInformation.manager.get_search_fields(Protein))))
    class Meta:
        model = Protein
        orderable = True
        attrs = {'class': 'paleblue'}
        #sequence = ('lincs_id', '...')
        #exclude = ('id')
    
    def __init__(self, table):
        super(ProteinTable, self).__init__(table)
        sequence_override = ['lincs_id']    
        set_table_column_info(self, ['protein',''],sequence_override)  
        
class LibrarySearchManager(models.Manager):
    
    def search(self, query_string, is_authenticated=False):
        query_string = query_string.strip()
        cursor = connection.cursor()
        sql = ( "SELECT a.*, b.*, l.* FROM " + 
                "( SELECT count(smallmolecule_batch_id) as sm_count, library.id " +
                " FROM db_library library LEFT JOIN db_librarymapping on (library_id=library.id) group by library.id ) b join db_library l on(b.id=l.id), "
                "( SELECT count(well) as well_count , max(plate)-min(plate)+ 1 as plate_count, library.id " + 
                "     FROM db_library library LEFT JOIN db_librarymapping on(library_id=library.id) ")
        where = ' WHERE 1=1 '
        if(not is_authenticated):
            where += 'and (not library.is_restricted or library.is_restricted is NULL) '
        if(query_string != '' ):
            sql += ", to_tsquery(%s) as query  " 
            where += "and library.search_vector @@ query "
        sql += where
        sql += " group by library.id) a join db_library l2 on(a.id=l2.id) WHERE l2.id=l.id order by l.short_name"
        
        logger.info(str(('sql',sql)))
        # TODO: the way we are separating query_string out here is a kludge
        if(query_string != ''):
            cursor.execute(sql, [query_string + ':*'])
        else:
            cursor.execute(sql)
        v = dictfetchall(cursor)
        #print 'dict: ', v, ', query: ', query_string
        return v
    
class LibraryTable(PagedTable):
    id = tables.Column(visible=False)
    short_name = tables.LinkColumn("library_detail", args=[A('short_name')])
    well_count = tables.Column()
    plate_count = tables.Column()
    sm_count = tables.Column()
    rank = tables.Column()
    snippet = SnippetColumn()
    
    snippet_def = (" || ' ' || ".join(map( lambda x: "coalesce("+x.field+",'') ", FieldInformation.manager.get_search_fields(Library))))
    class Meta:
        orderable = True
        model = Library
        attrs = {'class': 'paleblue'}
        #exclude = {'rank','snippet','is_restricted'}
    def __init__(self, table):
        super(LibraryTable, self).__init__(table)
        set_table_column_info(self, ['library',''],[])  
    
class LibraryForm(ModelForm):
    class Meta:
        model = Library        
            
class SiteSearchManager(models.Manager):
    
    def search(self, queryString, is_authenticated=False):
        cursor = connection.cursor()
        # TODO: build this dynamically, like the rest of the search
        # Notes: MaxFragments=10 turns on fragment based headlines (context for search matches), with MaxWords=20
        # ts_rank_cd(search_vector, query, 32): Normalization option 32 (rank/(rank+1)) can be applied to scale all 
        # ranks into the range zero to one, but of course this is just a cosmetic change; it will not affect the ordering of the search results.
        sql =   ("SELECT id, facility_id::text, ts_headline(" + CellTable.snippet_def + """, query1, 'MaxFragments=10, MinWords=1, MaxWords=20, FragmentDelimiter=" | "') as snippet, """ + 
                " ts_rank_cd(search_vector, query1, 32) AS rank, 'cell_detail' as type FROM db_cell, to_tsquery(%s) as query1 WHERE search_vector @@ query1 ") 
        if(not is_authenticated): 
            sql += " AND (not is_restricted or is_restricted is NULL)"
        sql +=  (" UNION " +
                " SELECT id, " + facility_salt_id + " as facility_id , ts_headline(" + SmallMoleculeTable.snippet_def + """, query2, 'MaxFragments=10, MinWords=1, MaxWords=20, FragmentDelimiter=" | "') as snippet, """ +
                " ts_rank_cd(search_vector, query2, 32) AS rank, 'sm_detail' as type FROM db_smallmolecule sm, to_tsquery(%s) as query2 WHERE search_vector @@ query2 ")
        if(not is_authenticated): 
            sql += " AND (not is_restricted or is_restricted is NULL)"
        sql +=  (" UNION " +
                " SELECT id, facility_id::text, ts_headline(" + DataSetTable.snippet_def + """, query3, 'MaxFragments=10, MinWords=1, MaxWords=20, FragmentDelimiter=" | "') as snippet, """ +
                " ts_rank_cd(search_vector, query3, 32) AS rank, 'dataset_detail' as type FROM db_dataset, to_tsquery(%s) as query3 WHERE search_vector @@ query3 " )
        if(not is_authenticated): 
            sql += " AND (not is_restricted or is_restricted is NULL)"
        sql +=  (" UNION " +
                " SELECT id, lincs_id::text as facility_id, ts_headline(" + ProteinTable.snippet_def + """, query4, 'MaxFragments=10, MinWords=1, MaxWords=20, FragmentDelimiter=" | "') as snippet, """ +
                " ts_rank_cd(search_vector, query4, 32) AS rank, 'protein_detail' as type FROM db_protein, to_tsquery(%s) as query4 WHERE search_vector @@ query4 ")
        if(not is_authenticated): 
            sql += " AND (not is_restricted or is_restricted is NULL)"
        sql += " ORDER by rank DESC;"
        cursor.execute(
                       sql , [queryString + ":*", queryString + ":*", queryString + ":*", queryString + ":*"])
        return dictfetchall(cursor)

class SiteSearchTable(PagedTable):
    id = tables.Column(visible=False)
    #Note: using the expediency here: the "type" column holds the subdirectory for that to make the link for type, so "sm", "cell", etc., becomes "/db/sm", "/db/cell", etc.
    facility_id = tables.LinkColumn(A('type'), args=[A('facility_id')])  
    type = TypeColumn()
    rank = tables.Column()
    snippet = SnippetColumn()
    class Meta:
        orderable = True
        attrs = {'class': 'paleblue'}
        exclude = {'rank'}

def get_integer(stringValue):
    try:
        return int(float(stringValue))
    except:
        logger.debug(str(('stringValue: ',stringValue,'is not an integer')))
    return None    

def can_access_image(request, image_filename, is_restricted=False):
    if(not is_restricted):
        url = request.build_absolute_uri(settings.STATIC_URL + image_filename)
        logger.info(str(('try to open url',url))) 
        try:
            response = urllib2.urlopen(url)
            response.read()
            #response.close() # TODO - is this needed?!
            logger.debug(str(('found image at', url)))
            return True
        except Exception,e:
            logger.info(str(('no image found at', url, e)))
        return False
    else:
        _path = os.path.join(settings.STATIC_AUTHENTICATED_FILE_DIR,image_filename)
        v = os.path.exists(_path)
        if(not v): logger.info(str(('could not find path', _path)))
        return v

def get_attached_files(facility_id, salt_id=None, batch_id=None):
    return AttachedFile.objects.filter(facility_id_for=facility_id, salt_id_for=salt_id, batch_id_for=batch_id)

def set_table_column_info(table,table_names, sequence_override=[]):
    # TODO: set_table_column info could pick the columns to include from the fieldinformation as well
    """
    Field information section
    param: table: a django-tables2 table
    param: table_names: a list of table names, by order of priority, include '' empty string for a general search.
    """ 
    fields = OrderedDict()
    exclude_list = [x for x in table.exclude]
    for fieldname,column in table.base_columns.iteritems():
        try:
            fi = FieldInformation.manager.get_column_fieldinformation_by_priority(fieldname,table_names)
            if(not fi.show_in_list):
                if(fieldname not in exclude_list):
                    exclude_list.append(fieldname)
            else:
                column.attrs['th']={'title':fi.get_column_detail()}
                column.verbose_name = fi.get_verbose_name()
                fields[fieldname] = fi
        except (ObjectDoesNotExist) as e:
            logger.warn(str(('no fieldinformation found for field:', fieldname)))
            if(fieldname not in exclude_list):
                exclude_list.append(fieldname)
            #column.attrs['th']={'title': fieldname}  
        
    fields = OrderedDict(sorted(fields.items(), key=lambda x: x[1].order))
    logger.debug(str(('fields',fields)))
    sequence = filter(lambda x: x not in sequence_override, [x for x in fields.keys()])
    sequence_override.extend(sequence)
    table.exclude = tuple(exclude_list)
    table.sequence = sequence_override
    logger.info(str(('excl',table.exclude)))
    logger.info(str(('seq',table.sequence)))
        
def dictfetchall(cursor): #TODO modify this to stream results properly
    "Returns all rows from a cursor as a dict"
    desc = cursor.description
    return [
        dict(zip([col[0] for col in desc], row)) for row in cursor.fetchall()
    ]

from django.contrib.auth.decorators import login_required
#@login_required
def restricted_image(request, filepath):
    if(not request.user.is_authenticated()):
        logger.warn(str(('access to restricted file for user is denied', request.user, filepath)))
        return HttpResponse('Log in required.', status=401)
    
    logger.info(str(('send requested file:', settings.STATIC_AUTHENTICATED_FILE_DIR, filepath, request.user.is_authenticated())))
    _path = os.path.join(settings.STATIC_AUTHENTICATED_FILE_DIR,filepath)
    _file = file(_path)
    logger.info(str(('download image',_path,_file)))
    wrapper = FileWrapper(_file)
    response = HttpResponse(wrapper,content_type='image/png') # todo: determine the type on the fly. (if ommitted, the browser sometimes doesn't know what to do with the image bytes)
    response['Content-Length'] = os.path.getsize(_path)
    return response

def download_attached_file(request, file_id):
    """                                                                         
    Send a file through Django without loading the whole file into              
    memory at once. The FileWrapper will turn the file object into an           
    iterator for chunks of 8KB.                                                 
    """
    try:
        af = AttachedFile.objects.get(id=file_id)
        logger.info(str(('send the attached file:', af, request.user.is_authenticated())))
        if(af.is_restricted and not request.user.is_authenticated()):
            logger.warn(str(('access to restricted file for user is denied', request.user, af)))
            return HttpResponse('Log in required.', status=401)

        _path = os.path.join(settings.STATIC_AUTHENTICATED_FILE_DIR,af.filename)
        if(af.relative_path):
            _path = os.path.join(settings.STATIC_AUTHENTICATED_FILE_DIR,af.relative_path)
        _file = file(_path)
        logger.info(str(('download_attached_file',_path,_file)))
        wrapper = FileWrapper(_file)
        response = HttpResponse(wrapper, content_type='text/plain') # use the same type for all files
        response['Content-Disposition'] = 'attachment; filename=%s' % unicode(af.filename)
        response['Content-Length'] = os.path.getsize(_path)
        return response
    except Exception,e:
        logger.error(str(('could not find attached file object for id', file_id, e)))
        raise e

# todo, not used    
#def download_attached_file_simple(request, path):
#    # TODO Authorization
#    logger.info(str(('download_attached_file',path)))
#    if(not request.user.is_authenticated()):
#        pass
#    return HttpResponseRedirect(settings.STATIC_ROOT+path)
        
# works, can't ensure authorization however
#def download_file(request, path):
#    logger.info(str(('download_attached_file',path,request.user)))
#    if(not request.user.is_authenticated()):
#        pass
#    return HttpResponseRedirect("/_static/"+path)

#x-sendfile option
# http://blog.zacharyvoase.com/2009/09/08/sendfile/
# This would be best placed in your settings file.
#def get_absolute_filename(filename='', safe=True):
#    if not filename:
#        return path.join(settings.STATIC_ROOT1, 'index')
#    if safe and '..' in filename.split(path.sep):
#        return get_absolute_filename(filename='')
#    return path.join(settings.STATIC_ROOT1, filename)
#
#from django.contrib.auth.decorators import login_required
#@login_required
#def retrieve_file(request, path=''):
#    logger.info(str(('get file', smart_str(path,'utf-8', errors='ignore'))))
#    abs_filename = get_absolute_filename(path)
#    response = HttpResponse() # 200 OK
#    del response['content-type'] # We'll let the web server guess this.
#    response['X-Sendfile'] = abs_filename
#    logger.info(str(('get file', abs_filename)))
#    return response
        
# TODO: currently, send_to_file1 is used specifically to export the large datasets; but would like for everything to use this method
def send_to_file1(outputType, name, ordered_datacolumns, cursor, request):
    if(outputType == 'csv'):
        return export_as_csv1(name,ordered_datacolumns , request, cursor)
    elif(outputType == 'xls'):
        return export_as_xls1(name, ordered_datacolumns, request, cursor)
    
def send_to_file(outputType, name, table, queryset, request):
    # ordered list (field,verbose_name)
    columns = map(lambda (x,y): (x, y.verbose_name), filter(lambda (x,y): x != 'rank' and x!= 'snippet' and y.visible, table.base_columns.items()))
    columnsOrdered = []
    for col in table._sequence:
        for (field,verbose_name) in columns:
            if(field==col):
                columnsOrdered.append((field,verbose_name))
                break
            
    #print 'return as ', outputType, ", columns: ", columns 

    if(outputType == 'csv'):
        return export_as_csv(name,columnsOrdered , request, queryset)
    elif(outputType == 'xls'):
        return export_as_xls(name, columnsOrdered, request, queryset)
    
def export_as_xls(name,columnNames, request, queryset):
    """
    Generic xls export admin action.
    """
    response = HttpResponse(mimetype='application/Excel')
    response['Content-Disposition'] = 'attachment; filename=%s.xls' % unicode(name).replace('.', '_')
    
    wbk = xlwt.Workbook()
    sheet = wbk.add_sheet('sheet 1')    # Write a first row with header information
    for i, (field,verbose_name) in enumerate(columnNames):
        sheet.write(0, i, verbose_name)        
        
    # Write data rows
    debug_interval=1000
    row = 0
    for obj in queryset:
        if isinstance(obj, dict):
            vals = [obj[field] for (field,verbose_name) in columnNames]
        else:
            vals = [getattr(obj, field) for (field,verbose_name) in columnNames]
        
        for i,column in enumerate(vals):
            sheet.write(row+1, i, column )
        if(row % debug_interval == 0):
            logger.info("row: " + str(row))
        row += 1
    wbk.save(response)
    return response

def export_as_csv(name,columnNames, request, queryset):
    """
    Generic csv export admin action.
    """
    response = HttpResponse(mimetype='text/csv')
    response['Content-Disposition'] = 'attachment; filename=%s.csv' % unicode(name).replace('.', '_')
    writer = csv.writer(response)
    # Write a first row with header information
    writer.writerow([verbose_name for (field,verbose_name) in columnNames])
    # Write data rows
    debug_interval=1000
    row = 0
    for obj in queryset:
        if isinstance(obj, dict):
            writer.writerow([smart_str(obj[field], 'utf-8', errors='ignore') for (field,verbose_name) in columnNames])
        else:
            writer.writerow([smart_str(getattr(obj, field), 'utf-8', errors='ignore') for (field,verbose_name) in columnNames])
        if(row % debug_interval == 0):
            logger.info("row: " + str(row))
        row += 1
    return response

def get_cols_to_write(cursor, fieldinformation_tables=[''], ordered_datacolumns=None):
    header_row = {}
    for i,col in enumerate(cursor.description):
        if(ordered_datacolumns != None and col.name.find('col')==0):
            #cols_to_write.append(i)
            j = int(re.match(r'col(\d+)',col.name).group(1))
            dc = ordered_datacolumns[j]
            header_row[i] = dc.name
        else:
            try:
                fi = FieldInformation.manager.get_column_fieldinformation_by_priority(col.name,fieldinformation_tables)
                if(fi.show_in_detail):
                    #cols_to_write.append(i)
                    header_row[i] = fi.get_verbose_name()
            except (ObjectDoesNotExist) as e:
                logger.warn(str(('no fieldinformation found for field:', col.name)))
         
    return OrderedDict(sorted(header_row.items(),key=lambda x: x[0]))
     


# TODO: is a cursor a queryset? if so then refactor all methods to use this
def export_as_xls1(name,ordered_datacolumns, request, cursor):
    """
    Generic xls export admin action.
    """
    response = HttpResponse(mimetype='application/Excel')
    response['Content-Disposition'] = 'attachment; filename=%s.xls' % unicode(name).replace('.', '_')

    cols_to_names = get_cols_to_write(cursor, ['dataset','smallmolecule','datarecord','smallmoleculebatch','protein','cell',''], ordered_datacolumns)   
    
    wbk = xlwt.Workbook()
    sheet = wbk.add_sheet('sheet 1')    # Write a first row with header information
    for i,name in enumerate(cols_to_names.values()):
        sheet.write(0, i, name)   
            
    debug_interval=1000
    row = 0
    obj=cursor.fetchone()
    keys = cols_to_names.keys()
    logger.info(str(('keys',keys)))
    while obj:
        for i,key in enumerate(keys):
            sheet.write(row+1,i,obj[key])
        if(row % debug_interval == 0):
            logger.info("row: " + str(row))
        row += 1
        obj=cursor.fetchone()
    wbk.save(response)
    return response

def export_as_csv1(name,ordered_datacolumns, request, cursor):
    """
    Generic csv export admin action.
    """
    response = HttpResponse(mimetype='text/csv')
    response['Content-Disposition'] = 'attachment; filename=%s.csv' % unicode(name).replace('.', '_')

    cols_to_names = get_cols_to_write(cursor, ['dataset','smallmolecule','datarecord','smallmoleculebatch','protein','cell',''], ordered_datacolumns)   

    writer = csv.writer(response)
    # Write a first row with header information
    writer.writerow(cols_to_names.values())
    # Write data rows
    debug_interval=1000
    row = 0
    obj=cursor.fetchone()
    keys = cols_to_names.keys()
    logger.info(str(('keys',keys,obj)))
    while obj:
        writer.writerow([smart_str(obj[int(key)], 'utf-8', errors='ignore') for key in keys])
        if(row % debug_interval == 0):
            logger.info("row: " + str(row))
        row += 1
        obj=cursor.fetchone()
    return response
