from PagedRawQuerySet import PagedRawQuerySet
from collections import OrderedDict
from datetime import timedelta
from db.models import PubchemRequest, SmallMolecule, SmallMoleculeBatch, Cell, \
    Protein, DataSet, Library, FieldInformation, AttachedFile, DataRecord, \
    DataColumn, LibraryMapping, get_detail, find_miami_lincs_mapping
from django import forms
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.staticfiles.finders import FileSystemFinder
from django.core.exceptions import ObjectDoesNotExist
from django.core.servers.basehttp import FileWrapper
from django.core.urlresolvers import reverse
from django.db import connection, models
from django.forms import ModelForm
from django.http import Http404, HttpResponseRedirect, HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.encoding import smart_str
from django.utils.safestring import mark_safe
from django_tables2 import RequestConfig
from django_tables2.utils import A # alias for Accessor
from dump_obj import dumpObj
from hms.pubchem import pubchem_database_cache_service
from math import log, pow
import csv
import django_tables2 as tables
import json
import logging
import os
import re
import sys
import xlwt


logger = logging.getLogger(__name__)
APPNAME = 'db',
COMPOUND_IMAGE_LOCATION = "compound-images-by-facility-salt-id"  
AMBIT_COMPOUND_IMAGE_LOCATION = "ambit-study-compound-images-by-facility-salt-id"  
DATASET_IMAGE_LOCATION = "dataset-images-by-facility-id" 
facility_salt_id = " sm.facility_id || '-' || sm.salt_id " # Note: because we have a composite key for determining unique sm structures, we need to do this
facility_salt_batch_id = facility_salt_id + " || '-' || smb.facility_batch_id " # Note: because we have a composite key for determining unique sm structures, we need to do this
facility_salt_batch_id_2 = " trim( both '-' from (" + facility_salt_id + " || '-' || coalesce(smb.facility_batch_id::TEXT,'')))" # need this one for datasets, since they may be linked either to sm or smb - sde4
OMERO_IMAGE_COLUMN_TYPE = 'omero_image'
DAYS_TO_CACHE = 1
DAYS_TO_CACHE_PUBCHEM_ERRORS = 1
#SECONDS_TO_WAIT = 300

filesystemfinder = FileSystemFinder()

def dump(obj):
    dumpObj(obj)

# --------------- View Functions -----------------------------------------------

def main(request):
    search = request.GET.get('search','')
    logger.debug(str(('main search: ', search)))
    if(search != ''):
        queryset = SiteSearchManager().search(search, is_authenticated=request.user.is_authenticated());
        table = SiteSearchTable(queryset)
        if(len(table.data)>0):
            RequestConfig(request, paginate={"per_page": 25}).configure(table)
        else:
            table = None
        return render(request, 'db/index.html', {'table': table, 'search':search })
    else:
        return render(request, 'db/index.html')

def cellIndex(request):
    search = request.GET.get('search','')
    logger.debug(str(("is_authenticated:", request.user.is_authenticated(), 'search: ', search)))
    if(search != ''):
        searchProcessed = format_search(search)
        criteria = "search_vector @@ to_tsquery(%s)"
        where = [criteria]
        if(not request.user.is_authenticated()): 
            where.append("( not is_restricted or is_restricted is NULL )")
        # postgres fulltext search with rank and snippets
        queryset = Cell.objects.extra(
            select={
                'snippet': "ts_headline(" + CellTable.snippet_def + ", to_tsquery(%s))",
                'rank': "ts_rank_cd(search_vector, to_tsquery(%s), 32)",
                },
            where=where,
            params=[searchProcessed],
            select_params=[searchProcessed,searchProcessed],
            order_by=('-rank',)
            )        
    else:
        where = []
        if(not request.user.is_authenticated()): where.append("( not is_restricted or is_restricted is NULL)")
        queryset = Cell.objects.extra(
            where=where,
            order_by=('facility_id',))        
 
    table = CellTable(queryset, template="db/custom_tables2_template.html")
    RequestConfig(request, paginate={"per_page": 25}).configure(table)
    outputType = request.GET.get('output_type','')
    if(outputType != ''):
        return send_to_file(outputType, 'cells', table, queryset )
    return render_list_index(request, table,search,'Cell','Cells')

def cellDetail(request, facility_id):
    try:
        cell = Cell.objects.get(facility_id=facility_id) # todo: cell here
        if(cell.is_restricted and not request.user.is_authenticated()):
            return HttpResponse('Log in required.', status=401)
        details = {'object': get_detail(cell, ['cell',''])}
        dataset_ids = find_datasets_for_cell(cell.id)
        if(len(dataset_ids)>0):
            logger.debug(str(('dataset ids for sm',dataset_ids)))
            where = []
            if(not request.user.is_authenticated()): 
                where.append("(not is_restricted or is_restricted is NULL)")
            queryset = DataSet.objects.filter(pk__in=list(dataset_ids)).extra(where=where,
                       order_by=('facility_id',))        
            details['datasets'] = DataSetTable(queryset)

        # add in the LIFE System link: TODO: put this into the fieldinformation
        extralink = {   'title': 'LINCS Information Framework Structure Page' ,
                        'name': 'LIFE Compound Information',
                        'link': 'http://baoquery.ccs.miami.edu/life/summary?mode=CellLine&input=' + str(find_miami_lincs_mapping(cell.facility_id)),
                        'value': cell.facility_id }
        details['extralink'] = extralink

        
        return render(request, 'db/cellDetail.html', details)
    except Cell.DoesNotExist:
        raise Http404

 
def proteinIndex(request):
    search = request.GET.get('search','')
    logger.debug(str(("is_authenticated:", request.user.is_authenticated(), 'search: ', search)))
    if(search != ''):
        searchProcessed = format_search(search)
        # NOTE: - change plaintext search to use "to_tsquery" as opposed to
        # "plainto_tsquery".  The "plain" version does not recognized the ":*"
        # syntax (override of the weighting syntax to do a greedy search)
        #        criteria = "search_vector @@ plainto_tsquery(%s)"
        criteria = "search_vector @@ to_tsquery(%s)"
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
            params=[searchProcessed],
            select_params=[searchProcessed,searchProcessed],
            order_by=('-rank',)
            )        
    else:
        where = []
        if(not request.user.is_authenticated()): where.append("(not is_restricted or is_restricted is NULL)")
        queryset = Protein.objects.extra(
            where=where,
            order_by=('lincs_id',))
    
    table = ProteinTable(queryset)
    RequestConfig(request, paginate={"per_page": 25}).configure(table)
    outputType = request.GET.get('output_type','')
    if(outputType != ''):
        return send_to_file(outputType, 'proteins', table, queryset )
    return render_list_index(request, table,search,'Protein','Proteins')
    
def proteinDetail(request, lincs_id):
    try:
        protein = Protein.objects.get(lincs_id=lincs_id) # todo: cell here
        if(protein.is_restricted and not request.user.is_authenticated()):
            return HttpResponse('Log in required.', status=401)
        details = {'object': get_detail(protein, ['protein',''])}
        
        # datasets table
        dataset_ids = find_datasets_for_protein(protein.id)
        if(len(dataset_ids)>0):
            logger.debug(str(('dataset ids for sm',dataset_ids)))
            where = []
            if(not request.user.is_authenticated()): 
                where.append("(not is_restricted or is_restricted is NULL)")
            queryset = DataSet.objects.filter(pk__in=list(dataset_ids)).extra(where=where,
                       order_by=('facility_id',))        
            details['datasets'] = DataSetTable(queryset)

        # add in the LIFE System link: TODO: put this into the fieldinformation
        extralink = {   'title': 'LINCS Information Framework Page' ,
                        'name': 'LIFE Protein Information',
                        'link': 'http://baoquery.ccs.miami.edu/life/summary?mode=Protein&input=' + str(find_miami_lincs_mapping(protein.lincs_id)),
                        'value': protein.lincs_id }
        details['extralink'] = extralink
                
        return render(request, 'db/proteinDetail.html', details)
 
    except Protein.DoesNotExist:
        raise Http404

# TODO REFACTOR, DRY... 
def smallMoleculeIndex(request):
    search = request.GET.get('search','')
    logger.debug(str(("is_authenticated:", request.user.is_authenticated(), 'search: ', search))) #, 'items_per_page', items_per_page)))

    if(search != ''):
        searchProcessed = format_search(search)
        criteria = "search_vector @@ to_tsquery(%s)"
        where = [criteria]
        
        # postgres fulltext search with rank and snippets
        logger.debug(str(("SmallMoleculeTable.snippet_def:",SmallMoleculeTable.snippet_def)))
        queryset = SmallMolecule.objects.extra(
            select={
                'snippet': "ts_headline(" + SmallMoleculeTable.snippet_def + ", to_tsquery(%s))",
                'rank': "ts_rank_cd(search_vector, to_tsquery(%s), 32)",
                },
            where=where,
            params=[searchProcessed],
            select_params=[searchProcessed,searchProcessed],
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
    if outputType:
        return send_to_file(outputType, 'small_molecule', table, queryset )
    
        if(len(queryset) == 1 ):
            return redirect_to_small_molecule_detail(queryset[0])
    return render_list_index(request, table,search,'Small molecule','Small molecules') #, **kwargs )    
    
def smallMoleculeMolfile(request, facility_salt_id):
    try:
        temp = facility_salt_id.split('-') # TODO: let urls.py grep the facility and the salt
        logger.debug(str(('find sm detail for', temp)))
        facility_id = temp[0]
        salt_id = temp[1]
        sm = SmallMolecule.objects.get(facility_id=facility_id, salt_id=salt_id) 
        response = HttpResponse(mimetype='text/csv')
        response['Content-Disposition'] = 'attachment; filename=%s.sdf' % facility_salt_id 
        response.write(sm.molfile)
        return response
        
    except SmallMolecule.DoesNotExist:
        raise Http404
    
    
def smallMoleculeDetail(request, facility_salt_id): # TODO: let urls.py grep the facility and the salt
    try:
        temp = facility_salt_id.split('-') # TODO: let urls.py grep the facility and the salt
        logger.debug(str(('find sm detail for', temp)))
        facility_id = temp[0]
        salt_id = temp[1]
        sm = SmallMolecule.objects.get(facility_id=facility_id, salt_id=salt_id) 
        smb = None
        if(len(temp)>2):
            smb = SmallMoleculeBatch.objects.get(smallmolecule=sm,facility_batch_id=temp[2]) 
        
    
        details = {'object': get_detail(sm, ['smallmolecule',''])}
        details['facility_salt_id'] = sm.facility_id + '-' + sm.salt_id
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
        
        # datasets table
        dataset_ids = find_datasets_for_smallmolecule(sm.id)
        if(len(dataset_ids)>0):
            logger.debug(str(('dataset ids for sm',dataset_ids)))
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
            logger.debug(str(('ntable',ntable.data, len(ntable.data))))
            if(len(ntable.data)>0): details['nominal_targets_table']=ntable
            otable = DataSetManager(dataset).get_table(whereClause=["smallmolecule_id=%d " % sm.id], 
                                                       metaWhereClause=["col2 != '1'"], 
                                                       column_exclusion_overrides=['facility_salt_batch','col0','col2']) # exclude "effective conc", "is_nominal"
            logger.debug(str(('otable',ntable.data, len(otable.data))))
            if(len(otable.data)>0): details['other_targets_table']=otable
        except DataSet.DoesNotExist:
            logger.warn('Nominal Targets dataset does not exist')
        
        image_location = COMPOUND_IMAGE_LOCATION + '/HMSL%s-%s.png' % (sm.facility_id,sm.salt_id)
        if(not sm.is_restricted or ( sm.is_restricted and request.user.is_authenticated())):
            if(can_access_image(request,image_location, sm.is_restricted)): details['image_location'] = image_location
            ambit_image_location = AMBIT_COMPOUND_IMAGE_LOCATION + '/HMSL%s-%s.png' % (sm.facility_id,sm.salt_id)
            if(can_access_image(request,ambit_image_location, sm.is_restricted)): details['ambit_image_location'] = ambit_image_location
        
        # add in the LIFE System link: TODO: put this into the fieldinformation
        extralink = {   'title': 'LINCS Information Framework Structure Page' ,
                        'name': 'LIFE Compound Information',
                        'link': 'http://baoquery.ccs.miami.edu/life/summary?mode=SmallMolecule&input=' + str(find_miami_lincs_mapping(sm.facility_id + "-" + sm.salt_id)),
                        'value': sm.facility_id }
        details['extralink'] = extralink
        
        return render(request,'db/smallMoleculeDetail.html', details)

    except SmallMolecule.DoesNotExist:
        raise Http404

def libraryIndex(request):
    search = request.GET.get('search','')
    queryset = LibrarySearchManager().search(search, is_authenticated=request.user.is_authenticated());
    table = LibraryTable(queryset)
    outputType = request.GET.get('output_type','')
    if(outputType != ''):
        return send_to_file(outputType, 'libraries', table, queryset )
    return render_list_index(request, table,search,'Library','Libraries')

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
                return send_to_file(outputType, 'library_'+library.short_name , table, queryset )
        
        return render(request,'db/libraryDetail.html', response_dict)
    except Library.DoesNotExist:
        raise Http404

def datasetIndex(request): #, type='screen'):
    search = request.GET.get('search','')
    logger.debug(str(("is_authenticated:", request.user.is_authenticated(), 'search: ', search)))
    where = []
    if(search != ''):
        searchProcessed = format_search(search)
        criteria = "search_vector @@ to_tsquery(%s)"
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
            params=[searchProcessed],
            select_params=[searchProcessed,searchProcessed],
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
        return send_to_file(outputType, 'datasetIndex', table, queryset )
        
    return render_list_index(request, table,search,'Dataset','Datasets')

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
        details.setdefault('heading', 'Cells Studied')
        return render(request,'db/datasetDetailRelated.html', details)
    except Http401, e:
        return HttpResponse('Unauthorized', status=401)
    
def datasetDetailProteins(request, facility_id):
    try:
        details = datasetDetail(request,facility_id,'proteins')
        details.setdefault('heading', 'Proteins Studied')
        return render(request,'db/datasetDetailRelated.html', details)
    except Http401, e:
        return HttpResponse('Unauthorized', status=401)
    
def datasetDetailSmallMolecules(request, facility_id):
    try:
        details = datasetDetail(request,facility_id,'small_molecules')
        details.setdefault('heading', 'Small Molecules Studied')
        return render(request,'db/datasetDetailRelated.html', details)
    except Http401, e:
        return HttpResponse('Unauthorized', status=401)
    
def datasetDetailDataColumns(request, facility_id):
    try:
        details = datasetDetail(request,facility_id,'datacolumns')
        details.setdefault('heading', 'Data Columns')
        return render(request,'db/datasetDetailRelated.html', details)
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
            return send_to_file1(outputType, 'dataset_'+str(facility_id), datacolumns, cursor )
        
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
                'has_small_molecules':manager.has_small_molecules(),
                'has_cells':manager.has_cells(),
                'has_proteins':manager.has_proteins()}

    items_per_page = 25
    form = PaginationForm(request.GET)
    details['items_per_page_form'] = form
    if(form.is_valid()):
        if(form.cleaned_data['items_per_page']): # TODO: is there another way to determine if the form has been used yet?
            items_per_page = int(form.cleaned_data['items_per_page'])
    
    if (sub_page == 'results'):
        search = request.GET.get('search','')
        table = manager.get_table(search=search) 
        if(len(table.data)>0):
            details['table'] = table
            RequestConfig(request, paginate={"per_page": items_per_page}).configure(table)
        details['search'] = search
        
    elif (sub_page == 'cells'):
        if(manager.has_cells()):
            table = CellTable(manager.cell_queryset)
            setattr(table.data,'verbose_name_plural','Cells')
            setattr(table.data,'verbose_name','Cells')
            details['table'] = table
            RequestConfig(request, paginate={"per_page": items_per_page}).configure(table)
    elif (sub_page == 'proteins'):
        if(manager.has_proteins()):
            table = ProteinTable(manager.protein_queryset)
            setattr(table.data,'verbose_name_plural','Proteins')
            setattr(table.data,'verbose_name','Protein')
            details['table'] = table
            RequestConfig(request, paginate={"per_page": items_per_page}).configure(table)
    elif (sub_page == 'small_molecules'):
        if(manager.has_small_molecules()):
            table = SmallMoleculeTable(manager.small_molecule_queryset)
            setattr(table.data,'verbose_name_plural','Small Molecules')
            setattr(table.data,'verbose_name','Small Molecule')
            details['table'] = table
            RequestConfig(request, paginate={"per_page": items_per_page}).configure(table)
    elif (sub_page == 'datacolumns'):
        table = DataColumnTable(DataColumn.objects.all().filter(dataset_id=dataset.id).order_by('display_order'))
        setattr(table.data,'verbose_name_plural','Data Columns')
        setattr(table.data,'verbose_name','Data Column')
        details['table'] = table
        RequestConfig(request, paginate={"per_page": items_per_page}).configure(table)
    elif sub_page != 'main':
        raise Exception(str(('Unknown sub_page for datasedetail', sub_page)))
    
    image_location = DATASET_IMAGE_LOCATION + '/%s.png' % str(facility_id)
    if(can_access_image(request,image_location)): details['image_location'] = image_location
    
    return details

def format_search(search_raw):
    """
    Formats the search term for use with postgres to_tsquery function.
    non-word characters (anything but letter, digit or underscore) is replaced with an AND condition
    """
    if(search_raw != ''):
        return " & ".join([x+":*" for x in re.split(r'\W+', search_raw)])
    return search_raw

# Pubchem search methods


def structure_search(request):
    """
    This method returns JSON output, it is meant to be called by an AJAX process
    in the compound structure search page.
    """
    
    logger.info(str(('structure search os pid:', os.getpid())))
    if(request.method == 'POST'):
        form = StructureSearchForm(request.POST, request.FILES)
        
        if(form.is_valid()):
            if(form.cleaned_data['smiles'] or request.FILES.has_key('sdf')):
                try:
                    kwargs = { 'type':form.cleaned_data['type'] }
                    smiles = form.cleaned_data['smiles']
                    kwargs['smiles'] = smiles;
                    molfile = ''
                    if (request.FILES.has_key('sdf')):
                        molfile =  request.FILES['sdf'].read()
                        kwargs['molfile'] = molfile
                    
                    request_id = pubchem_database_cache_service.submit_search(**kwargs)
                    
                    #TODO: debug mode could kick of the search processes as so:
                    # pubchem_database_cache_service.service_database_cache()
                    
                    return get_cached_structure_search(request, request_id)
                except Exception, e:
                    exc_type, exc_obj, exc_tb = sys.exc_info()
                    fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]      
                    logger.error(str((exc_type, fname, exc_tb.tb_lineno)))
                    logger.error(str(('in structure search', e)))
                    raise e
    else: # not submitted yet
        form = StructureSearchForm()

        return render(request, 'db/structureSearch_jquery.html', { 'structure_search_form':form, 'message':'Enter either a SMILES or a MOLFILE' })


def get_cached_structure_search(request, search_request_id):
    """
    check whether the structure search specfied by the id has been fullfilled.
    - if so, redirect the output to the list small molecules page and fill with the query for the Facility_ids found
    - if not, return a waiting response
    """
    logger.debug(str(('check cached request',search_request_id)))
    request = PubchemRequest.objects.get(pk=int(search_request_id));
    if request:
        kwargs = { 'smiles':request.smiles,'molfile':request.molfile, 'type':request.type }            
        if request.date_time_fullfilled:
            if request.pubchem_error_message:
                if (timezone.now()-request.date_time_fullfilled) > timedelta(days=DAYS_TO_CACHE_PUBCHEM_ERRORS):
                    logger.info(str(('pubchem errored cached request is older than',DAYS_TO_CACHE_PUBCHEM_ERRORS,'days',request)))
                    request.delete();
                    # TODO: for now, not restarting.  if the user tries again, it will be restarted because the cache was just cleared
                return_dict = {'pubchem_error': request.pubchem_error_message }
                logger.info(str(('return err: ', return_dict)))
                json_return = json.dumps(return_dict)
                return HttpResponse(json_return, mimetype="application/x-javascript")
            elif request.error_message:
                # NOTE: delete non-pubchem request errors, since presumably these are due to software errors
                return_dict = {'error': request.error_message }
                request.delete();
                logger.info(str(('return err: ', return_dict)))
                json_return = json.dumps(return_dict)
                return HttpResponse(json_return, mimetype="application/x-javascript")
            else: #then the request has been fullfilled
                if request.sm_facility_ids :
                    return_dict = { 'facility_ids': request.sm_facility_ids}
                    json_return = json.dumps(return_dict)
                    return HttpResponse(json_return, mimetype="application/x-javascript")
                else:
                    logger.info(str(('pubchem search result does not intersect with any compounds',kwargs)))
                    return_dict = {'empty': request.id }
                    json_return = json.dumps(return_dict)
                    return HttpResponse(json_return, mimetype="application/x-javascript")
        else:  # request not fullfilled yet
                logger.debug(str(('request not fullfilled yet', search_request_id)))
                return_dict = {'pubchemRequestId': request.id }
                json_return = json.dumps(return_dict)
                return HttpResponse(json_return, mimetype="application/x-javascript")
    else:
        return_dict = {'error': 'No cached request was located for the id, please resubmit your query.' }
        logger.info(str(('return err: ', return_dict)))
        json_return = json.dumps(return_dict)
        return HttpResponse(json_return, mimetype="application/x-javascript")
    
    # TODO: necessary to close the connection?            
    connection.close()
    logger.info(str(('pubchem search completed')))

def redirect_to_small_molecule_detail(smallmolecule):
    facility_salt_id = smallmolecule.facility_id + "-" + smallmolecule.salt_id
    return HttpResponseRedirect(reverse('db.views.smallMoleculeDetail',kwargs={'facility_salt_id':facility_salt_id}))

def smallMoleculeIndexList(request, facility_ids=''):
    logger.debug(str(('search for small molecules: ', facility_ids)))
    temp = facility_ids.split(',')
    queryset = SmallMolecule.objects.filter(facility_id__in=temp).distinct()
    if(len(queryset) == 1 ):
        return redirect_to_small_molecule_detail(queryset[0])
    table = SmallMoleculeTable(queryset)
    return render_list_index(request, table, '','Small molecule','Small molecules')
    
    
def render_list_index(request, table, search, name, name_plural, **requestArgs):
    items_per_page = 25
    form = PaginationForm(request.GET)
    if(form.is_valid()):
        if(form.cleaned_data['items_per_page']): # TODO: is there another way to determine if the form has been used yet?
            items_per_page = int(form.cleaned_data['items_per_page'])

    
    if( not requestArgs):
        requestArgs = dict()
    requestArgs.setdefault('search',search)
    requestArgs.setdefault('heading', name_plural)

    if(len(table.data)>0):
        RequestConfig(request, paginate={"per_page": items_per_page}).configure(table)
        setattr(table.data,'verbose_name_plural',name_plural)
        setattr(table.data,'verbose_name',name)
        requestArgs.setdefault('table',table)
        requestArgs.setdefault('items_per_page_form',form )
        logger.debug(str(('requestArgs', requestArgs)))
    return render(request, 'db/listIndex.html', requestArgs)
    

class PaginationForm(forms.Form):
    items_per_page = forms.ChoiceField(widget=forms.Select(attrs={'onchange': 'this.form.submit();'}), 
                                       choices=(('25','25'),('50','50'),('100','100'),('250','250'),('1000','1000')),
                                       required=False, label='per page')
    sort = forms.CharField(widget=forms.HiddenInput(), required=False);
    search = forms.CharField(widget=forms.HiddenInput(), required=False);
    
class StructureSearchForm(forms.Form):
    smiles = forms.CharField(widget=forms.Textarea(attrs={'cols': 50, 'rows': 4}), required=False);
    sdf  = forms.FileField(required=False, label='Molfile (sd file)')
    type = forms.ChoiceField(widget=forms.Select(), 
                               choices=(('identity','Identity'),('similarity','Similarity'),('substructure','Substructure'),),
                               required=True, label='Search Type',
                               initial='identity')
    
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
            logger.debug(str(('self.page.next_page_number()', self.page.next_page_number(),self.paginator.num_pages, temp)))
            if( temp > self.paginator.num_pages ): 
                temp=self.paginator.num_pages
            return temp
        
    def page_start(self):
        if(self.page):
            return self.paginator.per_page * (self.page.number-1)
        
    def page_end(self):
        if(self.page):
            temp = self.page_start()+self.paginator.per_page
            logger.debug(str(('page_end:' , temp, self.paginator.count )))
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
    except (Exception) as e:
        raise Exception(str(('no fieldinformation found for field:', fieldname,e)))
    
# OMERO Image: TODO: only include this if the dataset has images
OMERO_IMAGE_TEMPLATE = '''
   <a href="#" onclick='window.open("https://lincs-omero.hms.harvard.edu/webclient/img_detail/{{ record.%s }}", "Image","height=700,width=800")' ><img src='https://lincs-omero.hms.harvard.edu/webgateway/render_thumbnail/{{ record.%s }}/32/' alt='image if available' ></a>
'''
        
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
            display_name = (dc.display_name, dc.name)[dc.display_name == None or len(dc.display_name)==0]
            logger.debug(str(('create column', col, dc.id, dc.data_type, display_name, dc.name)))
            if(dc.data_type.lower() != OMERO_IMAGE_COLUMN_TYPE):
                self.base_columns[col] = tables.Column(verbose_name=display_name)
            else:
                #logger.debug(str(('omero_image column template', TEMPLATE % ('omero_image_id','omero_image_id'))))
                self.base_columns[col] = tables.TemplateColumn(OMERO_IMAGE_TEMPLATE % (col,col), verbose_name=display_name)

                
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
        
        # grab these now and cache them
        self.cell_queryset = self.cells_for_dataset(self.dataset_id)  # TODO: use ORM
        self.protein_queryset = self.proteins_for_dataset(self.dataset_id)
        self.small_molecule_queryset = self.small_molecules_for_dataset(self.dataset_id)
                
    class DatasetForm(ModelForm):
        class Meta:
            model = DataSet           
            order = ('facility_id', '...')
            exclude = ('id', 'molfile') 

    def has_cells(self):
        return len(self.cell_queryset) > 0
    
    def has_proteins(self):
        return len(self.protein_queryset) > 0

    def has_small_molecules(self):
        return len(self.small_molecule_queryset) > 0
    
    #TODO: get_cursor and get_table violate DRY...
    def get_cursor(self, whereClause=None,metaWhereClause=None,column_exclusion_overrides=None,parameters=None,search=''): 
        if not whereClause:
            whereClause = []
        if not metaWhereClause:
            metaWhereClause = []
        if not parameters:
            parameters = []
        if not column_exclusion_overrides:
            column_exclusion_overrides = []
        if(search != ''):
            #TODO: NOTE: the dataset search does not use the full text search
            #TODO: dataset search to search the data fields as well?
            searchParam = '%'+search+'%'
            searchClause = "facility_salt_batch like %s or lower(sm_name) like lower(%s) or lower(sm_alternative_names) like lower(%s) "
            searchParams = [searchParam,searchParam,searchParam]
            if(self.has_cells()): 
                searchClause += " or cell_facility_id::TEXT like %s or lower(cell_name) like lower(%s) "
                searchParams += [searchParam,searchParam]
            if(self.has_proteins()): 
                searchClause += " or protein_lincs_id::TEXT like %s or lower(protein_name) like lower(%s) "
                searchParams += [searchParam,searchParam]
                
            metaWhereClause.append(searchClause)
            parameters += searchParams
            
        logger.debug(str(('search',search,'metaWhereClause',metaWhereClause,'parameters',parameters)))
        
        self.dataset_info = self._get_query_info(whereClause,metaWhereClause,parameters) # TODO: column_exclusion_overrides
        cursor = connection.cursor()
        logger.info(str(('execute sql', self.dataset_info.query_sql, self.dataset_info.parameters)))
        cursor.execute(self.dataset_info.query_sql,self.dataset_info.parameters)
        return cursor

    #TODO: get_cursor and get_table violate DRY...
    def get_table(self, whereClause=None,metaWhereClause=None,column_exclusion_overrides=None,parameters=None,search=''): 
        if not whereClause:
            whereClause = []
        if not metaWhereClause:
            metaWhereClause = []
        if not parameters:
            parameters = []
        if not column_exclusion_overrides:
            column_exclusion_overrides = []
        if(search != ''):
            #TODO: NOTE: the dataset search does not use the full text search
            #TODO: dataset search to search the data fields as well?
            searchParam = '%'+search+'%'
            searchClause = "facility_salt_batch like %s or lower(sm_name) like lower(%s) or lower(sm_alternative_names) like lower(%s) "
            searchParams = [searchParam,searchParam,searchParam]
            if(self.has_cells()): 
                searchClause += " or cell_facility_id::TEXT like %s or lower(cell_name) like lower(%s) "
                searchParams += [searchParam,searchParam]
            if(self.has_proteins()): 
                searchClause += " or protein_lincs_id::TEXT like %s or lower(protein_name) like lower(%s) "
                searchParams += [searchParam,searchParam]
                
            metaWhereClause.append(searchClause)
            parameters += searchParams
            
        self.dataset_info = self._get_query_info(whereClause,metaWhereClause, parameters)
        logger.debug(str(('search',search,'metaWhereClause',metaWhereClause,'parameters',self.dataset_info.parameters)))
        #sql_for_count = 'SELECT count(distinct id) from db_datarecord where dataset_id ='+ str(self.dataset_id)
        queryset = PagedRawQuerySet(self.dataset_info.query_sql,self.dataset_info.count_query_sql, connection, 
                                    parameters=self.dataset_info.parameters,order_by=['datarecord_id'], verbose_name_plural='records')
        if(not self.has_plate_wells_defined(self.dataset_id)): column_exclusion_overrides.extend(['plate','well'])
        if(not self.has_control_type_defined(self.dataset_id)): column_exclusion_overrides.append('control_type')
        _table = DataSetResultTable(queryset,
                                  self.dataset_info.datacolumns, 
                                  self.has_cells(), 
                                  self.has_proteins(),
                                  column_exclusion_overrides) # TODO: again, all these flags are confusing
        setattr(_table.data,'verbose_name_plural','records')
        setattr(_table.data,'verbose_name','record')
        return _table

    class DatasetInfo:
        # TODO: should be a fieldinformation here
        # An ordered list of DataColumn entities for this Dataset
        datacolumns = []
        query_sql = ''
        count_query_sql = ''
        parameters = []
        
    

    def _get_query_info(self, whereClause=None,metaWhereClause=None, parameters=None):
        """
        generate a django tables2 table
        TODO: move the logic out of the view: so that it can be shared with the tastypie api (or make this rely on tastypie)
        params:
        whereClause: use this to filter datarecords in the inner query
        metaWhereClause: use this to filter over the entire resultset: any column (as the entire query is made into a subquery)
        """
        if not whereClause:
            whereClause = []
        if not metaWhereClause:
            metaWhereClause = []
        if not parameters:
            parameters = []
        
        logger.debug(str(('_get_query_info', whereClause,metaWhereClause, parameters)))
    
        #datacolumns = self.get_dataset_columns(self.dataset.id)
        # TODO: should be a fieldinformation here
        datacolumns = DataColumn.objects.filter(dataset=self.dataset).order_by('display_order')
        # Create a query on the fly that pivots the values from the datapoint table, making one column for each datacolumn type
        # use the datacolumns to make a query on the fly (for the DataSetManager), and make a DataSetResultSearchTable on the fly.
        #dataColumnCursor = connection.cursor()
        #dataColumnCursor.execute("SELECT id, name, data_type, precision from db_datacolumn where dataset_id = %s order by id asc", [dataset_id])
        logger.debug(str(('dataset columns:', datacolumns)))
    
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
                    column_to_select = "round( float_value::numeric, %s )" 
                    parameters.append(str(dc.precision))
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
        
        logger.debug(str(('whereClause',whereClause)))      
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
            logger.debug(str(('--querystrings---',queryString, countQueryString, parameters)))
        dataset_info = self.DatasetInfo()
        dataset_info.query_sql = queryString
        dataset_info.count_query_sql = countQueryString
        dataset_info.datacolumns = datacolumns
        dataset_info.parameters = parameters
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
    
# TODO: this usage of the django ORM is not performant - is there and indexing problem; or can we mimick the sql version above?   
#    def cells_for_dataset(self,dataset_id):
#        queryset = Cell.objects.filter(datarecord__dataset__id=dataset_id).distinct() 
#        # Note: restriction not needed as this will only show in the limited view of the small molecule table
#        logger.info(str(('cells for dataset',dataset_id,len(queryset))))
#        return queryset
    
    def proteins_for_dataset(self,dataset_id):
        cursor = connection.cursor()
        sql = 'SELECT protein.* FROM db_protein protein WHERE protein.id in (SELECT distinct(protein_id) FROM db_datarecord dr WHERE dr.dataset_id=%s) order by protein.name'
        cursor.execute(sql, [dataset_id])
        return dictfetchall(cursor)
            

# TODO: this usage of the django ORM is a bit more performant than the cell version above; still, going to stick with the non-ORM version for now    
#    def proteins_for_dataset(self,dataset_id):
#        queryset = Protein.objects.filter(datarecord__dataset__id=dataset_id).distinct() 
#        # Note: restriction not needed as this will only show in the limited view of the small molecule table
#        logger.info(str(('proteins for dataset',dataset_id,len(queryset))))
#        return queryset

    def small_molecules_for_dataset(self,dataset_id):
        cursor = connection.cursor()
        sql = 'SELECT *,' + facility_salt_id + ' as facility_salt, (lincs_id is null) as lincs_id_null, pubchem_cid is null as pubchem_cid_null FROM db_smallmolecule sm WHERE sm.id in (SELECT distinct(smallmolecule_id) FROM db_datarecord dr WHERE dr.dataset_id=%s) order by sm.facility_id'
        cursor.execute(sql, [dataset_id])
        return dictfetchall(cursor)
            
# TODO: this usage of the django ORM is a bit more performant than the cell version above; still, going to stick with the non-ORM version for now    
#    def small_molecules_for_dataset(self, dataset_id):
#        queryset = SmallMolecule.objects.filter(datarecord__dataset__id=dataset_id).distinct() 
#        # Note: restriction not needed as this will only show in the limited view of the small molecule table
#        logger.info(str(('small molecules for dataset',dataset_id,len(queryset))))
#        return queryset
    
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
    #TODO: can we return a django model queryset instead of just the id's (and then post-filter?)
    datasets = [x.id for x in DataSet.objects.filter(datarecord__protein__id=protein_id).distinct()]
    logger.debug(str(('datasets',datasets)))
    return datasets

def find_datasets_for_cell(cell_id):
    datasets = [x.id for x in DataSet.objects.filter(datarecord__cell__id=cell_id).distinct()]
    logger.debug(str(('datasets',datasets)))
    return datasets

def find_datasets_for_smallmolecule(smallmolecule_id):
    datasets = [x.id for x in DataSet.objects.filter(datarecord__smallmolecule__id=smallmolecule_id).distinct()]
    logger.debug(str(('datasets',datasets)))
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
            where = ", to_tsquery(%s) as query  WHERE sm.search_vector @@ query "
        where += ' and library_id='+ str(library_id)
        if(not is_authenticated):
            where += ' and ( not sm.is_restricted or sm.is_restricted is NULL)' # TODO: NOTE, not including: ' and not l.is_restricted'; library restriction will only apply to viewing the library explicitly (the meta data, and selection of compounds)
            
        sql += where
        sql += " order by "
        if(library_id != None):
            sql += "plate, well, smb.facility_batch_id, "
        sql += " sm.facility_id, sm.salt_id "
        
        logger.debug(str(('sql',sql)))
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
    facility_salt = tables.LinkColumn("sm_detail", args=[A('facility_salt')], order_by=['facility_id','salt_id']) 
    facility_salt.attrs['td'] = {'nowrap': 'nowrap'}
    rank = tables.Column()
    snippet = tables.Column()
    
    # django-tables2 trick to get these columns to sort with NULLS LAST in Postgres; 
    # note this requires the use of an "extra" clause in the query definition passed to this table (see the _init_ method below)
    lincs_id = tables.Column(order_by=('-lincs_id_null', 'lincs_id'))
    pubchem_cid = tables.Column(order_by=('-pubchem_cid_null', 'pubchem_cid'))

    snippet_def = (" || ' ' || ".join(map( lambda x: "coalesce("+x.field+",'') ", FieldInformation.manager.get_search_fields(SmallMolecule)))) 

    class Meta:
        model = SmallMolecule #[SmallMolecule, SmallMoleculeBatch]
        orderable = True
        attrs = {'class': 'paleblue'}
    def __init__(self, queryset, show_plate_well=False,*args, **kwargs):
        # trick to get these colums to sort with NULLS LAST in Postgres:
        # since a True sorts higher than a False, see above for usage (for Postgres)
        from django.db.models.query import QuerySet
        if(isinstance(queryset, QuerySet)): # test if we were passed a real queryset (as opposed to a dict)
            queryset = queryset.extra(select={'lincs_id_null':'lincs_id is null', 'pubchem_cid_null':'pubchem_cid is null'})
        super(SmallMoleculeTable, self).__init__(queryset)
        sequence_override = ['facility_salt']
        set_table_column_info(self, ['smallmolecule','smallmoleculebatch',''],sequence_override)  

class DataColumnTable(PagedTable):
    
    class Meta:
        model = DataColumn
        orderable = True
        attrs = {'class': 'paleblue'}
        
    def __init__(self, table,*args, **kwargs):
        super(DataColumnTable, self).__init__(table)
        sequence_override = []
        set_table_column_info(self, ['datacolumn',''],sequence_override)  

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
        
        logger.debug(str(('sql',sql)))
        # TODO: the way we are separating query_string out here is a kludge, i.e we should be using django ORM language?
        if(query_string != ''):
            searchProcessed = format_search(query_string)

            cursor.execute(sql, [searchProcessed])
        else:
            cursor.execute(sql)
        v = dictfetchall(cursor)
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
        queryStringProcessed = format_search(queryString)
        cursor = connection.cursor()
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
                       sql , [queryStringProcessed,queryStringProcessed,queryStringProcessed,queryStringProcessed])
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

def can_access_image(request, image_filename, is_restricted=False):
    if not is_restricted:
        matches = filesystemfinder.find(image_filename)
        return bool(matches)
    else:
        _path = os.path.join(settings.STATIC_AUTHENTICATED_FILE_DIR,image_filename)
        v = os.path.exists(_path)
        if(not v): logger.debug(str(('could not find path', _path)))
        return v

def get_attached_files(facility_id, salt_id=None, batch_id=None):
    return AttachedFile.objects.filter(facility_id_for=facility_id, salt_id_for=salt_id, batch_id_for=batch_id)

def set_table_column_info(table,table_names, sequence_override=None):
    # TODO: set_table_column info could pick the columns to include from the fieldinformation as well
    """
    Field information section
    param: table: a django-tables2 table
    param: table_names: a list of table names, by order of priority, include '' empty string for a general search.
    """ 
    if not sequence_override: 
        sequence_override = []
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
        except (Exception) as e:
            logger.debug(str(('no fieldinformation found for field:', fieldname)))
            if(fieldname not in exclude_list):
                exclude_list.append(fieldname)
            #column.attrs['th']={'title': fieldname}  
        
    fields = OrderedDict(sorted(fields.items(), key=lambda x: x[1].order))
    logger.debug(str(('fields',fields)))
    sequence = filter(lambda x: x not in sequence_override, [x for x in fields.keys()])
    sequence_override.extend(sequence)
    table.exclude = tuple(exclude_list)
    table.sequence = sequence_override
    logger.debug(str(('excl',table.exclude)))
    logger.debug(str(('seq',table.sequence)))
        
def dictfetchall(cursor): #TODO modify this to stream results properly
    "Returns all rows from a cursor as a dict"
    desc = cursor.description
    return [
        dict(zip([col[0] for col in desc], row)) for row in cursor.fetchall()
    ]

#@login_required
def restricted_image(request, filepath):
    if(not request.user.is_authenticated()):
        logger.warn(str(('access to restricted file for user is denied', request.user, filepath)))
        return HttpResponse('Log in required.', status=401)
    
    logger.debug(str(('send requested file:', settings.STATIC_AUTHENTICATED_FILE_DIR, filepath, request.user.is_authenticated())))
    _path = os.path.join(settings.STATIC_AUTHENTICATED_FILE_DIR,filepath)
    _file = file(_path)
    logger.debug(str(('download image',_path,_file)))
    wrapper = FileWrapper(_file)
    response = HttpResponse(wrapper,content_type='image/png') # todo: determine the type on the fly. (if ommitted, the browser sometimes doesn't know what to do with the image bytes)
    response['Content-Length'] = os.path.getsize(_path)
    return response

def download_attached_file(request, id):
    """                                                                         
    Send a file through Django without loading the whole file into              
    memory at once. The FileWrapper will turn the file object into an           
    iterator for chunks of 8KB.                                                 
    """
    try:
        af = AttachedFile.objects.get(id=id)
        logger.debug(str(('send the attached file:', af, request.user.is_authenticated())))
        if(af.is_restricted and not request.user.is_authenticated()):
            logger.warn(str(('access to restricted file for user is denied', request.user, af)))
            return HttpResponse('Log in required.', status=401)

        _path = os.path.join(settings.STATIC_AUTHENTICATED_FILE_DIR,af.filename)
        if(af.relative_path):
            _path = os.path.join(settings.STATIC_AUTHENTICATED_FILE_DIR,af.relative_path)
        _file = file(_path)
        logger.debug(str(('download_attached_file',_path,_file)))
        wrapper = FileWrapper(_file)
        response = HttpResponse(wrapper, content_type='text/plain') # use the same type for all files
        response['Content-Disposition'] = 'attachment; filename=%s' % unicode(af.filename)
        response['Content-Length'] = os.path.getsize(_path)
        return response
    except Exception,e:
        logger.error(str(('could not find attached file object for id', id, e)))
        raise e

def send_to_file1(outputType, name, ordered_datacolumns, cursor):
    """
    Export the datasetdata cursor to the file type pointed to by outputType
    @param ordered_datacolumns the datacolumns for the datasetdata, in order, so that they can be indexed by column number
    @param outputType '.csv','.xls'
    @param table a django-tables2 table
    @param name name of the table - to be used for the output file name
     
    """   
    logger.info(str(('send_to_file1', outputType, name, ordered_datacolumns)))
    col_key_name_map = get_cols_to_write(cursor, 
                                         ['dataset','smallmolecule','datarecord','smallmoleculebatch','protein','cell',''],
                                         ordered_datacolumns)   
    if(outputType == '.csv'):
        return export_as_csv(name,col_key_name_map, cursor=cursor)
    elif(outputType == '.xls'):
        return export_as_xls(name, col_key_name_map, cursor=cursor)

def send_to_file(outputType, name, table, queryset): 
    """
    Export the queryset to the file type pointed to by outputType.  Get the column header information from the django-tables2 table
    @param outputType '.csv','.xls'
    @param table a django-tables2 table
    @param name name of the table - to be used for the output file name
     
    """   
    # ordered list (field,verbose_name)
    columns = map(lambda (x,y): (x, y.verbose_name), 
                  filter(lambda (x,y): x != 'rank' and x!= 'snippet' and y.visible, table.base_columns.items()))
    columnsOrdered = []
    for col in table._sequence:
        for (field,verbose_name) in columns:
            if(field==col):
                columnsOrdered.append((field,verbose_name))
                break
    # The type strings deliberately include a leading "." to make the URLs
    # trigger the analytics js code that tracks download events by extension.
    if(outputType == '.csv'):
        return export_as_csv(name,OrderedDict(columnsOrdered) , queryset=queryset)
    elif(outputType == '.xls'):
        return export_as_xls(name, OrderedDict(columnsOrdered), queryset=queryset)

def get_cols_to_write(cursor, fieldinformation_tables=None, ordered_datacolumns=None):
    """
    returns a dict of #column_number:verbose_name
    """
    if not fieldinformation_tables: 
        fieldinformation_tables=['']
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
            except (Exception) as e:
                logger.warn(str(('no fieldinformation found for field:', col.name)))
         
    return OrderedDict(sorted(header_row.items(),key=lambda x: x[0]))

def export_as_csv(name,col_key_name_map, cursor=None, queryset=None):
    """
    Generic csv export admin action.
    """
    response = HttpResponse(mimetype='text/csv')
    response['Content-Disposition'] = 'attachment; filename=%s.csv' % unicode(name).replace('.', '_')
    writer = csv.writer(response)
    # Write a first row with header information
    writer.writerow(col_key_name_map.values())

    debug_interval=1000
    row = 0
    assert (cursor or queryset) and not (cursor and queryset), 'must define either cursor or queryset'
    if cursor:
        obj=cursor.fetchone()
        keys = col_key_name_map.keys()
        logger.debug(str(('keys',keys,obj)))
        while obj:
            writer.writerow([smart_str(obj[int(key)], 'utf-8', errors='ignore') for key in keys])
            if(row % debug_interval == 0):
                logger.info("row: " + str(row))
            row += 1
            obj=cursor.fetchone()
    elif queryset:
        for obj in queryset:
            if isinstance(obj, dict):
                writer.writerow([smart_str(obj[field], 'utf-8', errors='ignore') for field in col_key_name_map.keys()])
            else:
                writer.writerow([smart_str(getattr(obj, field), 'utf-8', errors='ignore') for field in col_key_name_map.keys()])
            if(row % debug_interval == 0):
                logger.info("row: " + str(row))
            row += 1
    return response

def export_as_xls(name,col_key_name_map, cursor=None, queryset=None):
    """
    Generic xls export admin action.
    """
    response = HttpResponse(mimetype='application/Excel')
    response['Content-Disposition'] = 'attachment; filename=%s.xls' % unicode(name).replace('.', '_')

    wbk = xlwt.Workbook()
    sheet = wbk.add_sheet('sheet 1')    # Write a first row with header information
    for i,name in enumerate(col_key_name_map.values()):
        sheet.write(0, i, name)   
            
    debug_interval=1000
    row = 0
    assert (cursor or queryset) and not (cursor and queryset), 'must define either cursor or queryset'
    if cursor:
        obj=cursor.fetchone()
        keys = col_key_name_map.keys()
        logger.debug(str(('keys',keys)))
        while obj:  # row in the dataset; a tuple to be indexed numerically
            for i,key in enumerate(keys):
                sheet.write(row+1,i,obj[key])
            if(row % debug_interval == 0):
                logger.info("row: " + str(row))
            row += 1
            obj=cursor.fetchone()
    elif queryset:
        for obj in queryset:  
            if isinstance(obj, dict): # a ORM object as a dict
                vals = [obj[field] for field in col_key_name_map.keys()]
            else: # a ORM object
                vals = [getattr(obj, field) for field in col_key_name_map.keys()]
            
            for i,column in enumerate(vals):
                sheet.write(row+1, i, column )
            if(row % debug_interval == 0):
                logger.info("row: " + str(row))
            row += 1    
    
    wbk.save(response)
    return response

