'''
Main view class for the DB project
'''

from collections import OrderedDict
import csv
from datetime import timedelta
import inspect
import json
import logging
from math import log, pow
import os
import re
import sys
import StringIO
import xlwt
import zipfile
  

from django.conf import settings
import django.contrib.staticfiles as dcs
from django.contrib.staticfiles.templatetags.staticfiles import static
from django.core.servers.basehttp import FileWrapper
from django.core.urlresolvers import reverse
from django.db import connection, models
from django.db.models import Q
from django import forms
from django.forms import ModelForm
from django.forms.models import model_to_dict
from django.http import Http404, HttpResponseRedirect, HttpResponse
from django.shortcuts import render
from django_tables2 import RequestConfig
from django_tables2.utils import A # alias for Accessor
import django_tables2 as tables
from django.utils import timezone
from django.utils.encoding import smart_str
from django.utils.safestring import mark_safe, SafeString

from hms.pubchem import pubchem_database_cache_service
from dump_obj import dumpObj
from PagedRawQuerySet import PagedRawQuerySet
from db.models import PubchemRequest, SmallMolecule, SmallMoleculeBatch, Cell, \
    Protein, DataSet, Library, FieldInformation, AttachedFile, DataRecord, \
    DataColumn, get_detail, Antibody, OtherReagent, CellBatch, QCEvent,\
    QCAttachedFile


logger = logging.getLogger(__name__)

APPNAME = 'db',
COMPOUND_IMAGE_LOCATION = "compound-images-by-facility-salt-id"  
AMBIT_COMPOUND_IMAGE_LOCATION = "ambit-study-compound-images-by-facility-salt-id"  
DATASET_IMAGE_LOCATION = "dataset-images-by-facility-id" 

OMERO_IMAGE_COLUMN_TYPE = 'omero_image'
DAYS_TO_CACHE = 1
DAYS_TO_CACHE_PUBCHEM_ERRORS = 1
#SECONDS_TO_WAIT = 300

# Query snippets to create the composite keys for Small Molecules
facility_salt_id = " sm.facility_id || '-' || sm.salt_id " 
facility_salt_batch_id = facility_salt_id + " || '-' || smb.facility_batch_id " 
# need this one for datasets, since they may be linked either to sm or smb - sde4
facility_salt_batch_id_2 = ( 
    " trim( both '-' from ( %s || '-' || coalesce(smb.facility_batch_id::TEXT,'')))" 
    % facility_salt_id ) 

def dump(obj):
    dumpObj(obj)


# Cache the set of dataset types
dataset_types = [(str(x['dataset_type']), str(x['dataset_type'])) for 
        x in DataSet.objects.values('dataset_type').distinct()]
dataset_types.insert(0,('',''))


# --------------- View Functions -----------------------------------------------

def main(request):
    search = request.GET.get('search','')
    logger.debug(str(('main search: ', search)))
    if(search != ''):
        queryset = SiteSearchManager().search(
            search, is_authenticated=request.user.is_authenticated());

        table = SiteSearchTable(queryset)
        if(len(table.data)>0):
            RequestConfig(request, paginate={"per_page": 25}).configure(table)
        else:
            table = None
        return render(request, 'db/index.html', 
            {'table': table, 'search':search, 'dataset_types': json.dumps(dataset_types) })
    else:
        return render(request, 'db/index.html', 
            {'dataset_types': json.dumps(dataset_types) })

def cellIndex(request):
    search = request.GET.get('search','')
    logger.debug(str(("is_authenticated:", 
        request.user.is_authenticated(), 'search: ', search)))
    search = re.sub(r'[\'"]','',search)
 
    if(search != ''):
        queryset = CellSearchManager().search(search, 
            is_authenticated=request.user.is_authenticated())
        queryset.query.add_ordering('facility_id')
    else:
        where = []
        if(not request.user.is_authenticated()): 
            where.append("( not db_cell.is_restricted or db_cell.is_restricted is NULL)")
        queryset = Cell.objects.extra(
            where=where,
            order_by=('facility_id',))        
 
    # PROCESS THE EXTRA FORM    
    field_hash=FieldInformation.manager.get_field_hash('cell')
    
    # 1. Override fields: note do this _before_ grabbing all the (bound) fields
    # for the display matrix below
    form_field_overrides = {}
    fieldinformation = \
        FieldInformation.manager.get_column_fieldinformation_by_priority('dataset_types', '')
    field_hash['dataset_types'] = fieldinformation
    form_field_overrides['dataset_types'] = forms.ChoiceField(
        required=False, choices=dataset_types, 
        label=field_hash['dataset_types'].get_verbose_name(), 
        help_text=field_hash['dataset_types'].get_column_detail())

    # now bind the form to the request, make a copy of the request, so that we 
    # can set values back to the client form
    form = FieldsMetaForm(
        field_information_array=field_hash.values(), 
        form_field_overrides=form_field_overrides, data=request.GET.copy())
    # add a "search" field to make it compatible with the full text search
    form.fields['search'] = forms.CharField(required=False);
    form.fields['extra_form_shown'] = forms.BooleanField(required=False);
    
    visible_field_overrides = []
    search_label = ''
    if form.is_valid():
        if form.cleaned_data and form.cleaned_data['extra_form_shown']:
            form.shown = True
        key = 'dataset_types'
        show_field = form.cleaned_data.get(key +'_shown', False)
        field_data = form.cleaned_data.get(key)
        if show_field or field_data:
            queryset = CellSearchManager().join_query_to_dataset_type(
                queryset, dataset_type=field_data)
            if field_data:
                search_label += \
                    "Filtered for " + fieldinformation.get_verbose_name() + ": " + field_data
            visible_field_overrides.append(key)
            form.data[key+'_shown'] = True
    else:
        logger.info(str(('invalid form', form.errors)))

    table = CellTable(queryset, visible_field_overrides=visible_field_overrides)

    RequestConfig(request, paginate={"per_page": 25}).configure(table)
    outputType = request.GET.get('output_type','')
    if(outputType != ''):
        return send_to_file(outputType, 'cells', table, queryset, 'cell' )
    return render_list_index(request, table,search,'Cell','Cells',
        **{ 'extra_form': form, 'search_label': search_label })

def cellDetail(request, facility_batch, batch_id=None):
    try:
        _batch_id = None
        if not batch_id:
            temp = facility_batch.split('-') 
            logger.info(str(('find cell for', temp)))
            _facility_id = temp[0]
            if len(temp) > 1:
                _batch_id = temp[1]
        else:
            _facility_id = facility_batch
            _batch_id = batch_id        
        
        cell = Cell.objects.get(facility_id=_facility_id) 
        if(cell.is_restricted and not request.user.is_authenticated()):
            return HttpResponse('Log in required.', status=401)
        details = {'object': get_detail(cell, ['cell',''])}
        
        #Testing...
        details['facility_id'] = cell.facility_id
        #
        
        
        logger.info(str(('batch_id', _batch_id)))
        cell_batch = None
        if(_batch_id):
            cell_batch = CellBatch.objects.get(
                cell=cell,batch_id=_batch_id) 
        # batch table
        if(cell_batch == None):
            batches = CellBatch.objects.filter(cell=cell)
            logger.info(str(('batches', len(batches))))
            
            if len(batches)>1:
                details['batchTable']=CellBatchTable(batches)
            elif len(batches)==1:
                cell_batch = batches[0]
        if cell_batch:
            details['cell_batch']= get_detail(
                cell_batch,['cellbatch',''])
            attachedFiles = get_attached_files(
                cell.facility_id,batch_id=cell_batch.batch_id)
            if(len(attachedFiles)>0):
                details['attached_files_batch'] = AttachedFileTable(attachedFiles)        
        
        dataset_ids = find_datasets_for_cell(cell.id)
        if(len(dataset_ids)>0):
            logger.debug(str(('dataset ids for cell',dataset_ids)))
            where = []
            if(not request.user.is_authenticated()): 
                where.append("(not is_restricted or is_restricted is NULL)")
            queryset = DataSet.objects.filter(pk__in=list(dataset_ids)).extra(
                    where=where,
                    order_by=('facility_id',))        
            details['datasets'] = DataSetTable(queryset)

        # add in the LIFE System link: TODO: put this into the fieldinformation
        _LINK = 'http://life.ccs.miami.edu/life/summary?mode=CellLine&input={cl_center_specific_id}&source=HMS'
        extralink = {   'title': 'LINCS Information Framework Structure Page' ,
                        'name': 'LIFE Cell Information',
                        'link': _LINK.format(cl_center_specific_id=cell.facility_id),
                        'value': cell.facility_id }
        details['extralink'] = extralink

        
        return render(request, 'db/cellDetail.html', details)
    except Cell.DoesNotExist:
        raise Http404

 
def proteinIndex(request):
    search = request.GET.get('search','')
    search = re.sub(r'[\'"]','',search)
    
    if(search != ''):
        queryset = ProteinSearchManager().search(
            search, is_authenticated = request.user.is_authenticated())
        queryset.query.add_ordering('lincs_id')
        
    else:
        where = []
        if(not request.user.is_authenticated()): 
            where.append("(not db_protein.is_restricted or db_protein.is_restricted is NULL)")
        queryset = Protein.objects.extra(
            where=where,
            order_by=('lincs_id',))

    # PROCESS THE EXTRA FORM    
    field_hash=FieldInformation.manager.get_field_hash('protein')
    
    # 1. Override fields: 
    # Note - do this _before_ grabbing all the (bound) fields for the display matrix below
    form_field_overrides = {}
    fieldinformation = \
        FieldInformation.manager.get_column_fieldinformation_by_priority('dataset_types', '')
    field_hash['dataset_types'] = fieldinformation
    form_field_overrides['dataset_types'] = forms.ChoiceField(
        required=False, choices=dataset_types, 
        label=field_hash['dataset_types'].get_verbose_name(), 
        help_text=field_hash['dataset_types'].get_column_detail())

    # now bind the form to the request, make a copy of the request, 
    # so that we can set values back to the client form
    form = FieldsMetaForm(
        field_information_array=field_hash.values(), 
        form_field_overrides=form_field_overrides, data=request.GET.copy())
    # add a "search" field to make it compatible with the full text search
    form.fields['search'] = forms.CharField(required=False);
    form.fields['extra_form_shown'] = forms.BooleanField(required=False);
    
    visible_field_overrides = []
    search_label = ""
    if form.is_valid():
        if form.cleaned_data and form.cleaned_data['extra_form_shown']:
            form.shown = True
        key = 'dataset_types'
        show_field = form.cleaned_data.get(key +'_shown', False)
        field_data = form.cleaned_data.get(key)
        if show_field or field_data:
            queryset = ProteinSearchManager().join_query_to_dataset_type(
                queryset, dataset_type=field_data)
            if field_data:
                search_label += \
                    "Filtered for " + fieldinformation.get_verbose_name() + ": " + field_data
            visible_field_overrides.append(key)
            form.data[key+'_shown'] = True
    else:
        logger.info(str(('invalid form', form.errors)))

    table = ProteinTable(queryset, visible_field_overrides=visible_field_overrides)
    outputType = request.GET.get('output_type','')
    if(outputType != ''):
        return send_to_file(outputType, 'proteins', table, queryset, 'protein' )
    RequestConfig(request, paginate={"per_page": 25}).configure(table)
    return render_list_index(
        request, table,search,'Protein','Proteins',
        **{ 'extra_form': form, 'search_label': search_label })
    
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
                        'link': 'http://life.ccs.miami.edu/life/summary?mode=Protein&input={pp_center_specific_id}&source=HMS'
                                .format(pp_center_specific_id=protein.lincs_id), # Note, protein.lincs_id will be changed to protein.facility_id
                        'value': protein.lincs_id }
        details['extralink'] = extralink
                
        return render(request, 'db/proteinDetail.html', details)
 
    except Protein.DoesNotExist:
        raise Http404
 
def antibodyIndex(request):
    search = request.GET.get('search','')
    search = re.sub(r'[\'"]','',search)
    
    if(search != ''):
        queryset = AntibodySearchManager().search(
            search, is_authenticated = request.user.is_authenticated())
        queryset.query.add_ordering('facility_id')
    else:
        where = []
        if(not request.user.is_authenticated()): 
            where.append("(not is_restricted or is_restricted is NULL)")
        queryset = Antibody.objects.extra(
            where=where,
            order_by=('facility_id',))
    
    table = AntibodyTable(queryset)
    outputType = request.GET.get('output_type','')
    if(outputType != ''):
        return send_to_file(outputType, 'antibodies', table, queryset, 'antibody' )
    RequestConfig(request, paginate={"per_page": 25}).configure(table)
    return render_list_index(request, table,search,'Antibody','Antibodies')
    
def antibodyDetail(request, facility_id):
    try:
        antibody = Antibody.objects.get(facility_id=facility_id) # todo: cell here
        if(antibody.is_restricted and not request.user.is_authenticated()):
            return HttpResponse('Log in required.', status=401)
        details = {'object': get_detail(antibody, ['antibody',''])}
        
        # datasets table
        dataset_ids = find_datasets_for_antibody(antibody.id)
        if(len(dataset_ids)>0):
            logger.debug(str(('dataset ids for antibodies',dataset_ids)))
            where = []
            if(not request.user.is_authenticated()): 
                where.append("(not is_restricted or is_restricted is NULL)")
            queryset = DataSet.objects.filter(pk__in=list(dataset_ids)).extra(where=where,
                       order_by=('facility_id',))        
            details['datasets'] = DataSetTable(queryset)

        # add in the LIFE System link: TODO: put this into the fieldinformation
        extralink = {   'title': 'LINCS Information Framework Page' ,
                        'name': 'LIFE Antibody Information',
                        'link': 'http://life.ccs.miami.edu/life/summary?mode=Antibody&input={ar_center_specific_id}&source=HMS'
                                .format(ar_center_specific_id=antibody.facility_id), 
                        'value': antibody.facility_id }
        details['extralink'] = extralink
                
        return render(request, 'db/antibodyDetail.html', details)
 
    except Antibody.DoesNotExist:
        raise Http404
 
def otherReagentIndex(request):
    search = request.GET.get('search','')
    search = re.sub(r'[\'"]','',search)
    
    if(search != ''):
        queryset = OtherReagentSearchManager().search(
            search, is_authenticated = request.user.is_authenticated())
        queryset.query.add_ordering('facility_id')
    else:
        where = []
        if(not request.user.is_authenticated()): 
            where.append("(not is_restricted or is_restricted is NULL)")
        queryset = OtherReagent.objects.extra(
            where=where,
            order_by=('facility_id',))
    
    table = OtherReagentTable(queryset)
    outputType = request.GET.get('output_type','')
    if(outputType != ''):
        return send_to_file(outputType, 'other_reagents', table, queryset, 'otherreagent' )
    RequestConfig(request, paginate={"per_page": 25}).configure(table)
    return render_list_index(request, table,search,'Other Reagent','Other Reagents')
    
def otherReagentDetail(request, facility_id):
    try:
        reagent = OtherReagent.objects.get(facility_id=facility_id) # todo: cell here
        if(reagent.is_restricted and not request.user.is_authenticated()):
            return HttpResponse('Log in required.', status=401)
        details = {'object': get_detail(reagent, ['otherreagent',''])}
        
        # datasets table
        dataset_ids = find_datasets_for_otherreagent(reagent.id)
        if(len(dataset_ids)>0):
            logger.debug(str(('dataset ids for other reagents',dataset_ids)))
            where = []
            if(not request.user.is_authenticated()): 
                where.append("(not is_restricted or is_restricted is NULL)")
            queryset = DataSet.objects.filter(
                    pk__in=list(dataset_ids)).extra(where=where,
                    order_by=('facility_id',))        
            details['datasets'] = DataSetTable(queryset)

        return render(request, 'db/otherReagentDetail.html', details)
 
    except OtherReagent.DoesNotExist:
        raise Http404

def saltIndex(request):
    queryset = SmallMolecule.objects.extra(where=["facility_id::int < 1000 "]);
    return smallMoleculeIndex(request, queryset=queryset, 
        overrides={'title': 'Salt', 'titles':'Salts', 'table': SaltTable, 
            'table_name': 'SaltTable' })

def smallMoleculeIndex(request, queryset=None, overrides=None):
    search = request.GET.get('search','')
    search = re.sub(r'[\'"]','',search) # remove quotes from search string
    if not queryset:
        queryset = SmallMolecule.objects.extra(
            where=["facility_id::int >= 1000 "]);
    if(search != ''):
        queryset = SmallMoleculeSearchManager().search(
            queryset, search, is_authenticated=request.user.is_authenticated())
        queryset.query.add_ordering('facility_id','salt_id')
    else:
        where = []
        queryset = queryset.extra(
            where=where,
            order_by=('facility_id','salt_id')) 

    # PROCESS THE EXTRA FORM : for field level filtering    
    field_hash=FieldInformation.manager.get_field_hash('smallmolecule')

    # 1. Override fields: 
    # Note: do this _before_ grabbing all the (bound) fields for the display
    form_field_overrides = {}
    fieldinformation = FieldInformation.manager. \
        get_column_fieldinformation_by_priority('dataset_types', '')
    field_hash['dataset_types'] = fieldinformation
    form_field_overrides['dataset_types'] = forms.ChoiceField(
        required=False, choices=dataset_types, 
        label=field_hash['dataset_types'].get_verbose_name(), 
        help_text=field_hash['dataset_types'].get_column_detail())
    
    # now bind the form to the request, make a copy of the request, 
    # so that we can set values back to the client form
    form = FieldsMetaForm(field_information_array=field_hash.values(), 
        form_field_overrides=form_field_overrides, data=request.GET.copy())
    # add a "search" field to make it compatible with the full text search
    form.fields['search'] = forms.CharField(required=False);
    form.fields['extra_form_shown'] = forms.BooleanField(required=False);
    
    visible_field_overrides = []
    search_label = ""
    if form.is_valid():
        if form.cleaned_data and form.cleaned_data['extra_form_shown']:
            form.shown = True
        key = 'dataset_types'
        show_field = form.cleaned_data.get(key +'_shown', False)
        field_data = form.cleaned_data.get(key)
        if show_field or field_data:
            queryset = SmallMoleculeSearchManager().join_query_to_dataset_type(
                queryset, dataset_type=field_data)
            if field_data:
                search_label += "Filtered for " + \
                    fieldinformation.get_verbose_name() + ": " + field_data
            visible_field_overrides.append(key)
            form.data[key+'_shown'] = True
            form.shown = True
    else:
        logger.info(str(('invalid form', form.errors)))

    # trick to get these colums to sort with NULLS LAST in Postgres:
    # since a True sorts higher than a False, see above for usage (for Postgres)
    select={'lincs_id_null':'lincs_id is null',
            'pubchem_cid_null':'pubchem_cid is null' }
    # add column for image IDS; not showing restricted images in the list view
    #     if request.user.is_authenticated():
    #         select['unrestricted_image_facility_salt'] = \
    #             "facility_id || '-' || salt_id"
    #     else:
    select['unrestricted_image_facility_salt'] = \
        "case when is_restricted then '' else facility_id || '-' || salt_id end"
    queryset = queryset.extra(select=select)
    
    if overrides and 'table' in overrides:
        tablename = overrides['table_name']
        table = overrides['table'](
            queryset, visible_field_overrides=visible_field_overrides)
    else:
        tablename = 'smallmolecule'
        table = SmallMoleculeTable(
            queryset, visible_field_overrides=visible_field_overrides)
    
    outputType = request.GET.get('output_type','')
    if outputType:
        if(outputType == ".zip"):
            return export_sm_images(queryset, request.user.is_authenticated())
        
        return send_to_file(outputType, 'small_molecule', table, queryset,
                    tablename, is_authenticated=request.user.is_authenticated())
    
    if(len(queryset) == 1 ):
        return redirect_to_small_molecule_detail(queryset[0])
        
    title = 'Small molecule'
    titles = 'Small molecules'
    if overrides:
        title = overrides.get('title', title)
        titles = overrides.get('titles', titles)
    return render_list_index(request, table,search,title, titles,
                **{ 'extra_form': form, 'search_label': search_label,
                    'smallmolecule_images': True } )

def smallMoleculeIndexList(request, facility_ids=''):
    logger.debug(str(('search for small molecules: ', facility_ids)))
    temp = facility_ids.split(',')
    queryset = SmallMolecule.objects.filter(facility_id__in=temp).distinct()
    if(len(queryset) == 1 ):
        return redirect_to_small_molecule_detail(queryset[0])
    table = SmallMoleculeTable(queryset)
    return render_list_index(request, table, '','Small molecule',
                             'Small molecules', structure_search=True)
    
        
def smallMoleculeMolfile(request, facility_salt_id):
    try:
        # TODO: let urls.py grep the facility and the salt
        temp = facility_salt_id.split('-') 
        logger.debug(str(('find sm detail for', temp)))
        facility_id = temp[0]
        salt_id = temp[1]
        sm = SmallMolecule.objects.get(facility_id=facility_id, salt_id=salt_id) 
        if(sm.is_restricted and not request.user.is_authenticated()): 
            return HttpResponse('Unauthorized', status=401)
        response = HttpResponse(mimetype='text/csv')
        response['Content-Disposition'] = \
            'attachment; filename=%s.sdf' % facility_salt_id 
        response.write(sm.molfile)
        return response
        
    except SmallMolecule.DoesNotExist:
        raise Http404
 
def saltDetail(request, salt_id):
    logger.info(str(('find the salt', salt_id)))
    return smallMoleculeDetail(request, "%s-101" % salt_id )   
    
# TODO: let urls.py grep the facility and the salt    
def smallMoleculeDetail(request, facility_salt_id): 
    logger.info(str(('find the small molecule', facility_salt_id)))

    try:
        # TODO: let urls.py grep the facility and the salt
        temp = facility_salt_id.split('-') 
        logger.info(str(('find sm detail for', temp)))
        facility_id = temp[0]
        salt_id = temp[1]
        sm = SmallMolecule.objects.get(facility_id=facility_id, salt_id=salt_id) 
        smb = None
        if(len(temp)>2):
            smb = SmallMoleculeBatch.objects.get(
                smallmolecule=sm,facility_batch_id=temp[2]) 

        # extra_properties is a hack related to the restricted information:
        # it informs the system to grab these "hidden" properties
        # TODO: this demands an architectural solution: the django ORM is not set 
        # up for per-field restriction.  Best strategy may be to compose a proxy object 
        # from restricted and unrestricted models
        extra_properties = []
        if(not sm.is_restricted or request.user.is_authenticated()):
            extra_properties=['_inchi', '_inchi_key', '_smiles', 
                '_molecular_formula', '_molecular_mass']
        details = {'object': get_detail(
            sm, ['smallmolecule',''],extra_properties=extra_properties )}
        details['facility_salt_id'] = sm.facility_id + '-' + sm.salt_id
        
        # change the facility ID if it is a salt, for the purpose of display
        if int(sm.facility_id) < 1000:
            details['object']['facility_salt']['value'] = sm.facility_id
            del details['object']['salt_id']
        
        #TODO: set is_restricted if the user is not logged in only
        details['is_restricted'] = sm.is_restricted
        
        if(not sm.is_restricted or request.user.is_authenticated()):
            attachedFiles = get_attached_files(sm.facility_id,sm.salt_id)
            if(len(attachedFiles)>0):
                details['attached_files'] = AttachedFileTable(attachedFiles)
            
        # batch table
        if not smb:
            batches = SmallMoleculeBatch.objects.filter(smallmolecule=sm)
            details['batchTable']=SmallMoleculeBatchTable(batches)
        else:
            details['smallmolecule_batch']= get_detail(
                smb,['smallmoleculebatch',''])
            details['facility_salt_batch'] = '%s-%s-%s' % (sm.facility_id,sm.salt_id,smb.facility_batch_id) 
            # 20150413 - proposed "QC Outcome" field on batch info removed per group discussion
            qcEvents = QCEvent.objects.filter(
                facility_id_for=sm.facility_id,
                salt_id_for=sm.salt_id,
                batch_id_for=smb.facility_batch_id).order_by('-date')
            if qcEvents:
                details['qcTable'] = QCEventTable(qcEvents)
            
            logger.info(str(('smb', details['smallmolecule_batch'])))
            
            if(not sm.is_restricted or request.user.is_authenticated()):
                attachedFiles = get_attached_files(
                    sm.facility_id,sm.salt_id,smb.facility_batch_id)
                if(len(attachedFiles)>0):
                    details['attached_files_batch'] = AttachedFileTable(attachedFiles)        
        
        # datasets table
        dataset_ids = find_datasets_for_smallmolecule(sm.id)
        if(len(dataset_ids)>0):
            logger.debug(str(('dataset ids for sm',dataset_ids)))
            where = []
            if(not request.user.is_authenticated()): 
                where.append("(not is_restricted or is_restricted is NULL)")
            queryset = DataSet.objects.filter(pk__in=list(dataset_ids)).extra(
                where=where, order_by=('facility_id',))        
            details['datasets'] = DataSetTable(queryset)
        
        # nominal target dataset results information
        try:
            dataset = DataSet.objects.get(dataset_type='Nominal Targets')
            # NOTE: "col2" is "Is Nominal" (because of "Display Order"), 
            # also note: this column is numeric for now
            # TODO: column aliases should be set in the datacolumns worksheet 
            # (in a fieldinformation object, eventually)
            ntable = DataSetManager(dataset).get_table(
                whereClause=["smallmolecule_id=%d " % sm.id],
                metaWhereClause = ["col2 = '1'"], 
                column_exclusion_overrides=['facility_salt_batch','col2'])
            logger.debug(str(('ntable',ntable.data, len(ntable.data))))
            
            if(len(ntable.data)>0): details['nominal_targets_table']=ntable
            
            otable = DataSetManager(dataset).get_table(
                whereClause=["smallmolecule_id=%d " % sm.id], 
                metaWhereClause=["col2 != '1'"], 
                column_exclusion_overrides=['facility_salt_batch','col0','col2'])
            logger.debug(str(('otable',ntable.data, len(otable.data))))
            if(len(otable.data)>0): details['other_targets_table']=otable
        except DataSet.DoesNotExist:
            logger.warn('Nominal Targets dataset does not exist')
        
        image_location = ( COMPOUND_IMAGE_LOCATION + '/HMSL%s-%s.png' 
            % (sm.facility_id,sm.salt_id) )
        if(not sm.is_restricted 
            or ( sm.is_restricted and request.user.is_authenticated())):
            if(can_access_image(image_location, sm.is_restricted)): 
                details['image_location'] = image_location
            ambit_image_location = (AMBIT_COMPOUND_IMAGE_LOCATION + 
                '/HMSL%s-%s.png' % (sm.facility_id,sm.salt_id) )
            if(can_access_image(ambit_image_location, sm.is_restricted)): 
                details['ambit_image_location'] = ambit_image_location
        
        # add in the LIFE System link: TODO: put this into the fieldinformation
        extralink = {   'title': 'LINCS Information Framework Structure Page' ,
                        'name': 'LIFE Compound Information',
                        'link': 'http://life.ccs.miami.edu/life/summary?mode=SmallMolecule&input={sm_lincs_id}&source=LINCS'
                            .format(sm_lincs_id=sm.lincs_id),
                        'value': sm.lincs_id }
        details['extralink'] = extralink
        
        return render(request,'db/smallMoleculeDetail.html', details)

    except SmallMolecule.DoesNotExist:
        raise Http404

def libraryIndex(request):
    search = request.GET.get('search','')
    search = re.sub(r'[\'"]','',search)
    queryset = LibrarySearchManager().search(
        search, is_authenticated=request.user.is_authenticated());
    table = LibraryTable(queryset)
    outputType = request.GET.get('output_type','')
    if(outputType != ''):
        return send_to_file(outputType, 'libraries', table, queryset, 'library' )
    return render_list_index(request, table,search,'Library','Libraries')

def libraryDetail(request, short_name):
    search = request.GET.get('search','')
    try:
        library = Library.objects.get(short_name=short_name)
        if(library.is_restricted and not request.user.is_authenticated()):
            return HttpResponse('Unauthorized', status=401)
        response_dict = {'object': get_detail(library, ['library',''])}
        queryset = LibraryMappingSearchManager().search(
            query_string=search, is_authenticated=request.user.is_authenticated,
            library_id=library.id);
        if(len(queryset)>0): 
            table = LibraryMappingTable(queryset)
            RequestConfig(request, paginate={"per_page": 25}).configure(table)
            response_dict['table']=table
            
            outputType = request.GET.get('output_type','')
            logger.error(str(("outputType:", outputType)))
            if(outputType != ''):
                return send_to_file(outputType, 'library_'+library.short_name ,
                    table, queryset, 'library' )
        
        return render(request,'db/libraryDetail.html', response_dict)
    except Library.DoesNotExist:
        raise Http404

def datasetIndex(request): #, type='screen'):
    search = request.GET.get('search','')
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
            order_by=('-rank','facility_id',)
            )        
    else:
        if(not request.user.is_authenticated()): 
            where.append("(not is_restricted or is_restricted is NULL)")
        queryset = DataSet.objects.extra(
            where=where,
            order_by=('facility_id',))   
        

    # PROCESS THE EXTRA FORM    
    field_hash=FieldInformation.manager.get_field_hash('dataset')

    # 1. Override fields: note do this _before_ grabbing all the (bound) fields
    # for the display matrix below
    form_field_overrides = {}
    form_field_overrides['dataset_type'] = forms.ChoiceField(
        required=False, choices=dataset_types, 
        label=field_hash['dataset_type'].get_verbose_name(), 
        help_text=field_hash['dataset_type'].get_column_detail())
    
    # 2. initialize.  this binds the form fields
    # now bind the form to the request, make a copy of the request, so that we 
    # can set values back to the client form
    form = FieldsMetaForm(
        field_information_array=field_hash.values(), 
        form_field_overrides=form_field_overrides, data=request.GET.copy())
    # add a "search" field to make it compatible with the full text search
    form.fields['search'] = forms.CharField(required=False);
    form.fields['extra_form_shown'] = forms.BooleanField(required=False);
    
    visible_field_overrides = []
    search_label = ""
    if form.is_valid():
        logger.info(str(('processing form', form.cleaned_data)))
        if form.cleaned_data and form.cleaned_data['extra_form_shown']:
            form.shown = True
        key = 'dataset_type'
        show_field = form.cleaned_data.get(key +'_shown', False)
        field_data = form.cleaned_data.get(key, None)
        if field_data:
            search_label += \
                "Filtered for %s: %s" % ( 
                    field_hash['dataset_type'].get_verbose_name(),field_data )
            queryset = queryset.filter(dataset_type=str(field_data))
            
        if show_field or field_data:
            form.data[key+'_shown'] = True
            visible_field_overrides.append(key)
    else:
        logger.info(str(('invalid form', form.errors)))
        
             
    table = DataSetTable(queryset)
    
    outputType = request.GET.get('output_type','')
    if(outputType != ''):
        return send_to_file(
            outputType, 'datasetIndex', table, queryset, 'dataset' )
    requestArgs = { 
        'usage_message': 
            ( 'To find <a href="datasets">datasets</a> from ' 
              '<a href="http://lincs.hms.harvard.edu/about/publications/">'
              'LINCS publications</a>, type the relevant PMID'
              ' in the datasets search box below.' ),
          'extra_form': form, 'search_label': search_label }
    return render_list_index(
        request, table,search,'Dataset','Datasets', **requestArgs)

class Http401(Exception):
    pass

def datasetDetailMain(request, facility_id):
    try:
        details = datasetDetail(request,facility_id, 'main')
        return render(request,'db/datasetDetailMain.html', details )
    except Http401, e:
        return HttpResponse('Unauthorized', status=401)
    
def datasetDetailCells(request, facility_id):
    outputType = request.GET.get('output_type','')
    if(outputType != ''):
        try:
            dataset = DataSet.objects.get(facility_id=facility_id)
            if(dataset.is_restricted and not request.user.is_authenticated()):
                raise Http401
            manager = DataSetManager(dataset)
            return send_to_file(
                outputType, 'cells_for_'+ str(facility_id), 
                CellTable(manager.cell_queryset), manager.cell_queryset, 'cell' )
        except DataSet.DoesNotExist:
            raise Http404
    try:
        details = datasetDetail(request,facility_id, 'cells')
        details.setdefault('heading', 'Cells Studied')
        return render(request,'db/datasetDetailRelated.html', details)
    except Http401, e:
        return HttpResponse('Unauthorized', status=401)
    
def datasetDetailProteins(request, facility_id):
    outputType = request.GET.get('output_type','')
    if(outputType != ''):
        try:
            dataset = DataSet.objects.get(facility_id=facility_id)
            if(dataset.is_restricted and not request.user.is_authenticated()):
                raise Http401
            manager = DataSetManager(dataset)
            return send_to_file(
                outputType, 'proteins_for_'+ str(facility_id), 
                ProteinTable(manager.protein_queryset), 
                manager.protein_queryset, 'protein' )
        except DataSet.DoesNotExist:
            raise Http404
    try:
        details = datasetDetail(request,facility_id,'proteins')
        details.setdefault('heading', 'Proteins Studied')
        return render(request,'db/datasetDetailRelated.html', details)
    except Http401, e:
        return HttpResponse('Unauthorized', status=401)  
      
def datasetDetailAntibodies(request, facility_id):
    outputType = request.GET.get('output_type','')
    if(outputType != ''):
        try:
            dataset = DataSet.objects.get(facility_id=facility_id)
            if(dataset.is_restricted and not request.user.is_authenticated()):
                raise Http401
            manager = DataSetManager(dataset)
            return send_to_file(
                outputType, 'antibodies_for_'+ str(facility_id), 
                AntibodyTable(manager.antibody_queryset), 
                manager.antibody_queryset, 'antibody' )
        except DataSet.DoesNotExist:
            raise Http404
    try:
        details = datasetDetail(request,facility_id,'antibodies')
        details.setdefault('heading', 'Antibodies Studied')
        return render(request,'db/datasetDetailRelated.html', details)
    except Http401, e:
        return HttpResponse('Unauthorized', status=401)
          
def datasetDetailOtherReagents(request, facility_id):
    outputType = request.GET.get('output_type','')
    if(outputType != ''):
        try:
            dataset = DataSet.objects.get(facility_id=facility_id)
            if(dataset.is_restricted and not request.user.is_authenticated()):
                raise Http401
            manager = DataSetManager(dataset)
            return send_to_file(
                outputType, 'other_reagents_for_'+ str(facility_id), 
                OtherReagentTable(manager.otherreagent_queryset), 
                manager.otherreagent_queryset, 'otherreagent' )
        except DataSet.DoesNotExist:
            raise Http404
    try:
        details = datasetDetail(request,facility_id,'otherreagents')
        details.setdefault('heading', 'Other Reagents Studied')
        return render(request,'db/datasetDetailRelated.html', details)
    except Http401, e:
        return HttpResponse('Unauthorized', status=401)
    
def datasetDetailSmallMolecules(request, facility_id):
    outputType = request.GET.get('output_type','')
    if(outputType != ''):
        try:
            dataset = DataSet.objects.get(facility_id=facility_id)
            if(dataset.is_restricted and not request.user.is_authenticated()):
                raise Http401
            manager = DataSetManager(dataset)
            
            if outputType == '.zip':
                filename = 'sm_images_for_dataset_' + str(dataset.facility_id)
                return export_sm_images(manager.small_molecule_queryset, 
                                        request.user.is_authenticated(),
                                        output_filename=filename)
            else:
                return send_to_file(
                    outputType, 'small_molecules_for_'+ str(facility_id), 
                    SmallMoleculeTable(manager.small_molecule_queryset), 
                    manager.small_molecule_queryset, 'smallmolecule' )
        except DataSet.DoesNotExist:
            raise Http404
    try:
        details = datasetDetail(request,facility_id,'small_molecules')
        details.setdefault('heading', 'Small Molecules Studied')
        details['smallmolecule_images'] = True
        return render(request,'db/datasetDetailRelated.html', details)
    except Http401, e:
        return HttpResponse('Unauthorized', status=401)
    
def datasetDetailDataColumns(request, facility_id):
    outputType = request.GET.get('output_type','')
    if(outputType != ''):
        try:
            dataset = DataSet.objects.get(facility_id=facility_id)
            if(dataset.is_restricted and not request.user.is_authenticated()):
                raise Http401
            queryset = DataColumn.objects.all().filter(
                dataset_id=dataset.id).order_by('display_order')
            
            # Because the datacolumn queryset contains references to full objects, 
            # and xlrt doesn't know what to do with them,
            # we have to convert all objects to values 
            # also, we're stuffing in some added information that isn't shown in 
            # the table view (cell id, protein id) 
            # TODO: based on discussion (2013-09), cell and protein should not 
            # be linked to the column in this way; since they 
            # are output values in this case, and so we should create a special
            # 'link-to-entity' datacolumn type
            array_of_dicts = []
            has_cells = False;
            has_proteins = False;
            for dc in queryset:
                row = model_to_dict(dc)
                if dc.cell: 
                    row['cell'] = dc.cell.name;
                    row['cell_facility_id'] = dc.cell.facility_id
                    has_cells=True
                else: row['cell_facility_id'] = None
                if dc.protein: 
                    row['protein'] = dc.protein.name;
                    row['protein_lincs_id'] = dc.protein.lincs_id
                    has_proteins = True
                else:
                    row['protein_lincs_id'] = None
                array_of_dicts.append(row)
                logger.info(str(('row', row)))
            
            extra_columns = []
            if has_cells:                     
                extra_columns.append(('cell_facility_id', 'cell_facility_id'))
            if has_proteins:
                extra_columns.append(('protein_lincs_id', 'protein_lincs_id'))
            return send_to_file(
                outputType, 'datacolumns_for_'+ str(facility_id),
                DataColumnTable(queryset), array_of_dicts, 'dataset', 
                extra_columns=extra_columns )
        except DataSet.DoesNotExist:
            raise Http404
    try:
        details = datasetDetail(request,facility_id,'datacolumns')
        details.setdefault('heading', 'Data Columns')
        return render(request,'db/datasetDetailRelated.html', details)
    except Http401, e:
        return HttpResponse('Unauthorized', status=401)

def datasetDetailResults_minimal(request, facility_id):
    return datasetDetailResults(request, facility_id, template='db/datasetDetailResults_minimal.html')
    
def datasetDetailResults(request, facility_id, template='db/datasetDetailResults.html'):
    try:
        details = None

        outputType = request.GET.get('output_type','')
        if(outputType != ''):
            dataset = DataSet.objects.get(facility_id=facility_id)
            if(dataset.is_restricted and not request.user.is_authenticated()):
                raise Http401
            manager = DataSetManager(dataset)
            form = manager.get_result_set_data_form(request)
            cursor = manager.get_cursor(whereClause=form.get_where_clause())
            datacolumns = \
                DataColumn.objects.filter(dataset=dataset).order_by('display_order')
            return send_to_file1(
                outputType, 'dataset_'+str(facility_id), 'dataset', 
                datacolumns, cursor, 'dataset' )
        
        details = datasetDetail(request,facility_id, 'results')
        
        details['pop_out_link'] = request.get_full_path().replace('results','results_minimal')

        return render(request,template, details)
    except Http401, _:
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
                'has_small_molecules':manager.has_small_molecules(),
                'has_cells':manager.has_cells(),
                'has_proteins':manager.has_proteins(),
                'has_antibodies':manager.has_antibodies(),
                'has_otherreagents':manager.has_otherreagents()}

    items_per_page = 25
    form = PaginationForm(request.GET)
    details['items_per_page_form'] = form
    if(form.is_valid()):
        if(form.cleaned_data['items_per_page']): 
            items_per_page = int(form.cleaned_data['items_per_page'])
    
    if (sub_page == 'results'):

        form = manager.get_result_set_data_form(request)
        table = manager.get_table(whereClause=form.get_where_clause()) 
        details['search_form'] = form
        if(len(table.data)>0):
            details['table'] = table
            RequestConfig(
                request, paginate={"per_page": items_per_page}).configure(table)

        
    elif (sub_page == 'cells'):
        if(manager.has_cells()):
            table = CellTable(manager.cell_queryset)
            setattr(table.data,'verbose_name_plural','Cells')
            setattr(table.data,'verbose_name','Cells')
            details['table'] = table
            RequestConfig(
                request, paginate={"per_page": items_per_page}).configure(table)
    elif (sub_page == 'proteins'):
        if(manager.has_proteins()):
            table = ProteinTable(manager.protein_queryset)
            setattr(table.data,'verbose_name_plural','Proteins')
            setattr(table.data,'verbose_name','Protein')
            details['table'] = table
            RequestConfig(
                request, paginate={"per_page": items_per_page}).configure(table)
    elif (sub_page == 'antibodies'):
        if(manager.has_antibodies()):
            table = AntibodyTable(manager.antibody_queryset)
            setattr(table.data,'verbose_name_plural','Antibodies')
            setattr(table.data,'verbose_name','Antibody')
            details['table'] = table
            RequestConfig(
                request, paginate={"per_page": items_per_page}).configure(table)
    elif (sub_page == 'otherreagents'):
        if(manager.has_otherreagents()):
            table = OtherReagentTable(manager.otherreagent_queryset)
            setattr(table.data,'verbose_name_plural','Other Reagents')
            setattr(table.data,'verbose_name','Other Reagent')
            details['table'] = table
            RequestConfig(
                request, paginate={"per_page": items_per_page}).configure(table)
    elif (sub_page == 'small_molecules'):
        if(manager.has_small_molecules()):
            table = SmallMoleculeTable(manager.small_molecule_queryset)
            setattr(table.data,'verbose_name_plural','Small Molecules')
            setattr(table.data,'verbose_name','Small Molecule')
            details['table'] = table
            RequestConfig(
                request, paginate={"per_page": items_per_page}).configure(table)
    elif (sub_page == 'datacolumns'):
        table = DataColumnTable(DataColumn.objects.all().filter(
            dataset_id=dataset.id).order_by('display_order'))
        setattr(table.data,'verbose_name_plural','Data Columns')
        setattr(table.data,'verbose_name','Data Column')
        details['table'] = table
        RequestConfig(
            request, paginate={"per_page": items_per_page}).configure(table)
    elif sub_page != 'main':
        raise Exception(str(('Unknown sub_page for datasedetail', sub_page)))
    
    image_location = DATASET_IMAGE_LOCATION + '/%s.png' % str(facility_id)
    if(can_access_image(image_location)): 
        details['image_location'] = image_location
    
    return details

def format_search(search_raw):
    """
    Formats the search term for use with postgres to_tsquery function.
    non-word characters (anything but letter, digit or underscore) is replaced 
    with an AND condition
    """
    # TODO: temp fix for issue #188 - update all ID's to the "HMSL###" form
    search_raw = re.sub('HMSL','', search_raw)
    if(search_raw != ''):
        return " & ".join([x+":*" for x in re.split(r'\W+', search_raw) if x])
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
                    
                    request_id = \
                        pubchem_database_cache_service.submit_search(**kwargs)
                    
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

        return render(
            request, 'db/structureSearch_jquery.html',
            { 'structure_search_form':form, 
              'message':'Enter either a SMILES or a MOLFILE' })


def get_cached_structure_search(request, search_request_id):
    """
    check whether the structure search specfied by the id has been fullfilled.
    - if so, redirect the output to the list small molecules page and fill with 
    the query for the Facility_ids found
    - if not, return a waiting response
    """
    logger.debug(str(('check cached request',search_request_id)))
    request = PubchemRequest.objects.get(pk=int(search_request_id));
    if request:
        kwargs = { 
            'smiles':request.smiles,
            'molfile':request.molfile, 
            'type':request.type }            
        if request.date_time_fullfilled:
            if request.pubchem_error_message:
                if ((timezone.now()-request.date_time_fullfilled) > 
                        timedelta(days=DAYS_TO_CACHE_PUBCHEM_ERRORS) ):
                    logger.info(str((
                        'pubchem errored cached request is older than',
                        DAYS_TO_CACHE_PUBCHEM_ERRORS,'days',request)))
                    request.delete();
                    # TODO: for now, not restarting.  if the user tries again, 
                    # it will be restarted because the cache was just cleared
                return_dict = {'pubchem_error': request.pubchem_error_message }
                logger.info(str(('return err: ', return_dict)))
                json_return = json.dumps(return_dict)
                return HttpResponse(json_return, mimetype="application/x-javascript")
            elif request.error_message:
                # NOTE: delete non-pubchem request errors, 
                # since presumably these are due to software errors
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
                    logger.info(str((
                        'pubchem search result does not intersect with any compounds',kwargs)))
                    return_dict = {'empty': request.id }
                    json_return = json.dumps(return_dict)
                    return HttpResponse(json_return, mimetype="application/x-javascript")
        else:  # request not fullfilled yet
                logger.debug(str(('request not fullfilled yet', search_request_id)))
                return_dict = {'pubchemRequestId': request.id }
                json_return = json.dumps(return_dict)
                return HttpResponse(json_return, mimetype="application/x-javascript")
    else:
        return_dict = {
            'error': 'No cached request was located for the id, please resubmit your query.' }
        logger.info(str(('return err: ', return_dict)))
        json_return = json.dumps(return_dict)
        return HttpResponse(json_return, mimetype="application/x-javascript")
    
    # TODO: necessary to close the connection?            
    connection.close()
    logger.info(str(('pubchem search completed')))

def redirect_to_small_molecule_detail(smallmolecule):
    facility_salt_id = smallmolecule.facility_id + "-" + smallmolecule.salt_id
    return HttpResponseRedirect(reverse(
        'db.views.smallMoleculeDetail',kwargs={'facility_salt_id':facility_salt_id}))


def render_list_index(request, table, search, name, name_plural, **requestArgs):
    items_per_page = 25
    form = PaginationForm(request.GET)
    if(form.is_valid()):
        if(form.cleaned_data['items_per_page']): 
            items_per_page = int(form.cleaned_data['items_per_page'])

    
    if( not requestArgs):
        requestArgs = dict()
    requestArgs.setdefault('search',search)
    requestArgs.setdefault('heading', name_plural)
    
    requestArgs.setdefault('table',table)
    table.data.length = len(table.data)
    if(len(table.data)>0):
        RequestConfig(
            request, paginate={"per_page": items_per_page}).configure(table)
        setattr(table.data,'verbose_name_plural',name_plural)
        setattr(table.data,'verbose_name',name)
        requestArgs.setdefault('items_per_page_form',form )
        logger.debug(str(('requestArgs', requestArgs)))
    result = render(request, 'db/listIndex.html', requestArgs)
    return result

class SmallMoleculeReportForm(forms.Form):
    
    def __init__(self, dataset_types, *args, **kwargs):
        super(SmallMoleculeReportForm, self).__init__(*args, **kwargs)
        self.fields['show dataset types'] = forms.BooleanField(required=False)
        self.fields['dataset types'] = \
            forms.ChoiceField(required=False, choices=dataset_types)
    
class ResultSetDataForm(forms.Form):
    def __init__(self, entity_id_name_map={}, *args, **kwargs):
        super(ResultSetDataForm, self).__init__(*args, **kwargs)
        self.entity_id_name_map = entity_id_name_map    
        for key, item in entity_id_name_map.items():
            list_of_id_name_tuple = item['choices']
            self.fields[key] = \
                forms.MultipleChoiceField(required=False, choices=list_of_id_name_tuple)
#        super(ResultSetDataForm, self).__init__(*args, **kwargs)    
    
    def get_where_clause(self):
        whereClause = []
        if self.is_valid():
            whereClause=[]
            for key in self.entity_id_name_map.keys():
                id_field = self.entity_id_name_map[key]['id_field']
                if key in self.fields:
                    vals = self.cleaned_data[key]
                    if(vals and len(vals) > 0):
                        logger.info(str(('vals', vals)))
                        whereClause.append(
                            id_field + " in (" + ','.join([str(val) for val in vals]) + ')')
        return whereClause
    
class PaginationForm(forms.Form):
    items_per_page = \
        forms.ChoiceField(
            widget=forms.Select(attrs={'onchange': 'this.form.submit();'}), 
            choices=(
                ('25','25'),('50','50'),('100','100'),('250','250'),
                ('1000','1000')),
            required=False, label='per page')
    sort = forms.CharField(widget=forms.HiddenInput(), required=False);
    search = forms.CharField(widget=forms.HiddenInput(), required=False);
    
class StructureSearchForm(forms.Form):
    smiles = forms.CharField(
        widget=forms.Textarea(attrs={'cols': 50, 'rows': 4}), required=False);
    sdf  = forms.FileField(required=False, label='Molfile (sd file)')
    type = \
        forms.ChoiceField(
            widget=forms.Select(), 
            choices=(
                ('identity','Identity'),('similarity','Similarity'),
                ('substructure','Substructure'),),
            required=True, label='Search Type',
            initial='identity')
    
class TypeColumn(tables.Column):
    def render(self, value):
        if value == "cell_detail": return "Cell"
        elif value == "sm_detail": return "Small Molecule"
        elif value == "dataset_detail": return "Dataset"
        elif value == "protein_detail": return "Protein"
        else: raise Exception("Unknown type: "+value)

class DivWrappedColumn(tables.Column):
    '''
    This special column wraps each cell in a <DIV> element, which allows each 
    cell to be styled independantly.  We use this to make the fixed width cells 
    wrap properly.
    '''
    def __init__(self, classname=None, *args, **kwargs):
        self.classname=classname
        super(DivWrappedColumn, self).__init__(*args, **kwargs)
    
    def render(self, value):
        return mark_safe(
            "<div class='%s' >%s</div>" % (
                self.classname, smart_str(value, 'utf-8', errors='ignore')))

class ImageColumn(tables.Column):

    def __init__(self, loc=None, image_class=None, *args, **kwargs):
        self.loc=loc
        self.image_class=image_class
        super(ImageColumn, self).__init__(*args, **kwargs)
    
    def render(self, value):
        if value:
            location = static('%s/HMSL%s.png'% (self.loc, smart_str(value)))
            return mark_safe(
                '<img class="%s" src="%s" />' % (self.image_class, location) )
        else:
            return ''

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
    title = DivWrappedColumn(classname='fixed_width_column_300', visible=False)
    protocol = tables.Column(visible=False) 
    references = tables.Column(visible=False)
    rank = tables.Column()
    snippet = DivWrappedColumn(verbose_name='matched text', classname='snippet')
    snippet_def = (" || ' ' || ".join(map(
        lambda x: "coalesce(db_dataset."+x.field+",'') ", 
        FieldInformation.manager.get_search_fields(DataSet))))
    class Meta:
        model = DataSet
        orderable = True
        attrs = {'class': 'paleblue'}

    def __init__(self, table):
        super(DataSetTable, self).__init__(table)
        
        set_table_column_info(self, ['dataset',''])  

def set_field_information_to_table_column(fieldname,table_names,column):
    try:
        fi = FieldInformation.manager.get_column_fieldinformation_by_priority(
            fieldname,table_names)
        column.attrs['th']={'title':fi.get_column_detail()}
        column.verbose_name = SafeString(fi.get_verbose_name())
    except (Exception) as e:
        raise Exception(str(('no fieldinformation found for field:', fieldname, table_names,e)))
    
OMERO_IMAGE_TEMPLATE = '''
   <a href="#" onclick='window.open("https://lincs-omero.hms.harvard.edu/webclient/img_detail/{{ record.%s }}", "Image","height=700,width=800")' ><img src='https://lincs-omero.hms.harvard.edu/webgateway/render_thumbnail/{{ record.%s }}/32/' alt='image if available' ></a>
'''
        
class DataSetResultTable(PagedTable):
    """
    Override of the tables.Table - columns are defined manually to conform to 
    the DataSetManager query fields; 
    fields are added as Table "base_columns" in the __init__ method.
    TODO: 
    the cursor is converted to a list of dicts, all in memory; implement pagination
    """
    defined_base_columns = []
    id = tables.Column(visible=False)
    defined_base_columns.append('id')
    
    facility_salt_batch = \
        tables.LinkColumn('sm_detail', args=[A('facility_salt_batch')],visible=False)
    facility_salt_batch.attrs['td'] = {'nowrap': 'nowrap'}
    defined_base_columns.append('facility_salt_batch')
    set_field_information_to_table_column(
        'facility_salt_batch', ['smallmoleculebatch'], facility_salt_batch)
    
    sm_name = tables.LinkColumn('sm_detail', args=[A('facility_salt_batch')],
                                visible=False)
    defined_base_columns.append('sm_name')
    set_field_information_to_table_column('name', ['smallmolecule'], sm_name)

    cell_name = \
        tables.LinkColumn('cell_detail',args=[A('cell_facility_batch')], 
                          visible=False,verbose_name='Cell Name') 
    defined_base_columns.append('cell_name')
    set_field_information_to_table_column('name', ['cell'], cell_name)
    
    cell_facility_batch = \
        tables.LinkColumn('cell_detail',args=[A('cell_facility_batch')], 
                          visible=False,verbose_name='Cell Facility ID') 
    defined_base_columns.append('cell_facility_batch')
    set_field_information_to_table_column(
        'facility_id', ['cell'], cell_facility_batch)
    
    protein_name = \
        tables.LinkColumn('protein_detail',args=[A('protein_lincs_id')], 
                          visible=False, verbose_name='Protein Name') 
    defined_base_columns.append('protein_name')
    set_field_information_to_table_column('name', ['protein'], protein_name)
    
    protein_lincs_id = \
        tables.LinkColumn('protein_detail',args=[A('protein_lincs_id')], 
                          visible=False, verbose_name='Protein LINCS ID') 
    defined_base_columns.append('protein_lincs_id')
    set_field_information_to_table_column('lincs_id', ['protein'], protein_lincs_id)
    
    antibody_name = \
        tables.LinkColumn('antibody_detail',args=[A('antibody_facility_id')], 
                          visible=False, verbose_name='Antibody Name') 
    defined_base_columns.append('antibody_name')
    set_field_information_to_table_column('name', ['antibody'], antibody_name)
    
    antibody_facility_id = \
        tables.LinkColumn('antibody_detail',args=[A('antibody_facility_id')], 
                          visible=False, verbose_name='Antibody Facility ID') 
    defined_base_columns.append('antibody_facility_id')
    set_field_information_to_table_column(
        'facility_id', ['antibody'], antibody_facility_id)
    
    otherreagent_name = \
        tables.LinkColumn('otherreagent_detail',
                          args=[A('otherreagent_facility_id')], visible=False, 
                          verbose_name='Other Reagent Name') 
    defined_base_columns.append('otherreagent_name')
    set_field_information_to_table_column(
        'name', ['otherreagent'], otherreagent_name)
    
    otherreagent_facility_id = \
        tables.LinkColumn('otherreagent_detail',
                          args=[A('otherreagent_facility_id')], visible=False, 
                          verbose_name='Other Reagent Facility ID') 
    defined_base_columns.append('otherreagent_facility_id')
    set_field_information_to_table_column(
        'facility_id', ['otherreagent'], otherreagent_facility_id)
    
    plate = tables.Column()
    defined_base_columns.append('plate')
    set_field_information_to_table_column('plate', ['datarecord'], plate)
    
    well = tables.Column()
    defined_base_columns.append('well')
    set_field_information_to_table_column('well', ['datarecord'], well)
    
    control_type = tables.Column()
    defined_base_columns.append('control_type')
    set_field_information_to_table_column(
        'control_type', ['datarecord'], control_type)
        
    class Meta:
        orderable = True
        attrs = {'class': 'paleblue'}
    
    def __init__(self, queryset, ordered_datacolumns, show_small_mols=False, 
                 show_cells=False, show_proteins=False, 
                 show_antibodies=False, show_otherreagents=False, 
                 column_exclusion_overrides=None, *args, **kwargs):
        # Follows is to deal with a bug - columns from one table appear to be 
        # injecting into other tables!!
        # This indicates that we are doing something wrong here by defining 
        # columns dynamically on the class "base_columns" attribute
        # So, to fix, we should redefine all of the base_columns every time here.  
        # For now, what is done is the "defined_base_columns" are preserved, 
        # then others are added.
        for name in self.base_columns.keys():
            if name not in self.defined_base_columns:
                logger.debug(str((
                    'deleting column from the table', name,self.defined_base_columns)))
                del self.base_columns[name]

        temp = []
        if(show_small_mols):
            temp.extend(['facility_salt_batch','sm_name'])
        if(show_cells): 
            temp.append('cell_name')
            temp.append('cell_facility_batch')
        if(show_proteins): 
            temp.append('protein_name')
            temp.append('protein_lincs_id')
        if(show_antibodies): 
            temp.append('antibody_name')
            temp.append('antibody_facility_id')
        if(show_otherreagents): 
            temp.append('otherreagent_name')
            temp.append('otherreagent_facility_id')
        temp.extend(['col'+str(i) for (i,__) in enumerate(ordered_datacolumns)])
        temp.extend(['plate','well','control_type'])
        ordered_names = temp
        
        #for name,verbose_name in columns_to_names.items():
        for i,dc in enumerate(ordered_datacolumns):    
            #logger.debug(str(('create column:',name,verbose_name)))
            col = 'col%d'%i
            display_name = \
                (SafeString(dc.display_name), dc.name)[
                    dc.display_name == None or len(dc.display_name)==0]
            logger.debug(str((
                'create column', col, dc.id, dc.data_type, display_name, dc.name)))
            if(dc.data_type.lower() != OMERO_IMAGE_COLUMN_TYPE):
                self.base_columns[col] = tables.Column(verbose_name=display_name)
            else:
                self.base_columns[col] = \
                    tables.TemplateColumn(OMERO_IMAGE_TEMPLATE % (col,col), 
                                          verbose_name=display_name)
            if dc.description: 
                self.base_columns[col].attrs['th'] = { 'title':dc.description }

                
        # Note: since every instance reuses the base_columns, 
        # each time the visibility must be set.
        # Todo: these colums should be controlled by the column_exclusion_overrides
        if(show_small_mols):
            self.base_columns['sm_name'].visible = True
            self.base_columns['facility_salt_batch'].visible = True
        else:
            self.base_columns['sm_name'].visible = False
            self.base_columns['facility_salt_batch'].visible = False
        if(show_cells):
            self.base_columns['cell_name'].visible = True
            self.base_columns['cell_facility_batch'].visible = True
        else:
            self.base_columns['cell_name'].visible = False
            self.base_columns['cell_facility_batch'].visible = False
        if(show_proteins):
            self.base_columns['protein_name'].visible = True
            self.base_columns['protein_lincs_id'].visible = True
        else:
            self.base_columns['protein_name'].visible = False
            self.base_columns['protein_lincs_id'].visible = False
        if(show_antibodies):
            self.base_columns['antibody_name'].visible = True
            self.base_columns['antibody_facility_id'].visible = True
        else:
            self.base_columns['antibody_name'].visible = False
            self.base_columns['antibody_facility_id'].visible = False
        if(show_otherreagents):
            self.base_columns['otherreagent_name'].visible = True
            self.base_columns['otherreagent_facility_id'].visible = True
        else:
            self.base_columns['otherreagent_name'].visible = False
            self.base_columns['otherreagent_facility_id'].visible = False
        logger.debug(str(('base columns:', self.base_columns)))
        # Field information section: 
        # TODO: for the datasetcolumns, use the database information for these.
        # set_table_column_info(self, ['smallmolecule','cell','protein',''])  

        # TODO: why does this work with the super call last?  
        # Keep an eye on forums for creating dynamic columns with tables2
        # for instance: https://github.com/bradleyayers/django-tables2/issues/70
        super(DataSetResultTable, self).__init__(queryset, *args, **kwargs)
        if(self.exclude): 
            self.exclude = tuple(list(self.exclude).extend(column_exclusion_overrides))
        else: self.exclude = tuple(column_exclusion_overrides)
        self.sequence = ordered_names


# TODO: this class has grown - 
# needs refactoring to allow ability to filter in a less clumsy way
# (who are we kidding, this is raw sql, after all!).
class DataSetManager():
    
    def __init__(self,dataset,is_authenticated=False):
        self.dataset = dataset
        self.dataset_id = dataset.id
        
        # grab these now and cache them
        ds_query = DataRecord.objects.all().filter(dataset_id=dataset.id)
        self.cell_queryset = self.cells_for_dataset(self.dataset_id) 
        self.has_cells_for_datarecords = \
            ds_query.filter(cell__isnull=False).exists()
        self.protein_queryset = self.proteins_for_dataset(self.dataset_id)
        self.has_proteins_for_datarecords = \
            ds_query.filter(protein__isnull=False).exists()
        self.antibody_queryset = self.antibodies_for_dataset(self.dataset_id)
        self.has_antibodies_for_datarecords = \
            ds_query.filter(antibody__isnull=False).exists()
        self.otherreagent_queryset = \
            self.otherreagents_for_dataset(self.dataset_id)
        self.has_otherreagents_for_datarecords = \
            ds_query.filter(otherreagent__isnull=False).exists()
        self.small_molecule_queryset = \
            self.small_molecules_for_dataset(self.dataset_id)
        self.has_small_molecules_for_datarecords = \
            ds_query.filter(smallmolecule__isnull=False).exists()
            
    class DatasetForm(ModelForm):
        class Meta:
            model = DataSet           
            order = ('facility_id', '...')
            exclude = ('id', 'molfile') 

    # Note that the "has_[entity]" methods are different from the 
    # has_[entity]_for_dataset" methods, because the first take into account the 
    # [entities] that were attached to the Datacolum or the Datarecord, and the
    # second accounts for those attached through the Datarecord only.
    def has_cells(self):
        return self.has_cells_for_datarecords \
            or self.dataset.datacolumn_set.all()\
                .filter(cell__isnull=False).exists()
    
    def get_cells(self):
        return self.cell_queryset
    
    def has_proteins(self):
        return self.has_proteins_for_datarecords \
            or self.dataset.datacolumn_set.all()\
                .filter(protein__isnull=False).exists()

    def get_proteins(self):
        return self.protein_queryset
    
    def has_antibodies(self):
        return self.has_antibodies_for_datarecords
    
    def get_antibodies(self):
        return self.antibody_queryset
    
    def has_otherreagents(self):
        return self.has_otherreagents_for_datarecords

    def get_otherreagents(self):
        return self.otherreagent_queryset
    
    def has_small_molecules(self):
        return self.has_small_molecules_for_datarecords
    
    def get_small_molecules(self):
        return self.small_molecule_queryset
    
    def get_result_set_data_form(self, request):
        # TODO: data drive this
        entity_id_name_map = {}
        if self.has_cells():
            entity_id_name_map['cells'] = { 
                'id_field': 'cell_id', 
                'choices': 
                    [(str(item['id']), '{name}:{facility_id}'.format(**item)) 
                        for item in self.get_cells()] }
        if self.has_proteins():
            entity_id_name_map['proteins'] = { 
                'id_field': 'protein_id', 
                'choices': 
                    [(str(item['id']), '{name}:{lincs_id}'.format(**item)) 
                        for item in self.get_proteins()]}
        if self.has_small_molecules():
            entity_id_name_map['small molecules'] = { 
                'id_field': 'smallmolecule_id', 
                'choices': 
                    [(str(item['id']), '{name}:{facility_id}'.format(**item)) 
                        for item in self.get_small_molecules()]}
        if self.has_antibodies():
            entity_id_name_map['antibodies'] = { 
                'id_field': 'antibody_id', 
                'choices': 
                    [(str(item['id']), '{name}:{facility_id}'.format(**item) ) 
                        for item in self.get_antibodies()]}
        if self.has_otherreagents():
            entity_id_name_map['other reagents'] = { 
                'id_field': 'otherreagent_id', 
                'choices': 
                    [(str(item['id']), '{name}:{facility_id}'.format(**item))
                        for item in self.get_otherreagents()]}
        form = ResultSetDataForm(entity_id_name_map=entity_id_name_map, data=request.GET)
        return form
        
        
    #TODO: get_cursor and get_table violate DRY...
    def get_cursor(self, whereClause=None,metaWhereClause=None,
                   column_exclusion_overrides=None,parameters=None,search=''): 
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
            searchClause = \
                ("facility_salt_batch like %s"
                 " or lower(sm_name) like lower(%s)"
                 " or lower(sm_alternative_names) like lower(%s) ")
            searchParams = [searchParam,searchParam,searchParam]
            if(self.has_cells()): 
                searchClause += (" or cell_facility_batch like %s"
                                 " or lower(cell_name) like lower(%s) ")
                searchParams += [searchParam,searchParam]
            if(self.has_proteins()): 
                searchClause += (" or protein_lincs_id::TEXT like %s"
                                 " or lower(protein_name) like lower(%s) ")
                searchParams += [searchParam,searchParam]
                
            if(self.has_antibodies()): 
                searchClause += (" or antibody_facility_id::TEXT like %s"
                                 " or lower(antibody_name) like lower(%s) ")
                searchParams += [searchParam,searchParam]
                
            if(self.has_otherreagents()): 
                searchClause += (" or otherreagent_facility_id::TEXT like %s"
                                 " or lower(otherreagent_name) like lower(%s) ")
                searchParams += [searchParam,searchParam]
                
            metaWhereClause.append(searchClause)
            parameters += searchParams
            
        logger.debug(str((
            'search',search,'metaWhereClause',metaWhereClause,'parameters',parameters)))
        
        self.dataset_info = \
            self._get_query_info(whereClause,metaWhereClause,parameters)
        cursor = connection.cursor()
        logger.info(str((
            'execute sql', self.dataset_info.query_sql, self.dataset_info.parameters)))
        cursor.execute(self.dataset_info.query_sql,self.dataset_info.parameters)
        return cursor

    #TODO: get_cursor and get_table violate DRY...
    def get_table(self, whereClause=None,metaWhereClause=None,
                  column_exclusion_overrides=None,parameters=None,search=''): 
        if not whereClause:
            whereClause = []
        if not metaWhereClause:
            metaWhereClause = []
        if not parameters:
            parameters = []
        if not column_exclusion_overrides:
            column_exclusion_overrides = []
            
        self.dataset_info = \
            self._get_query_info(whereClause,metaWhereClause, parameters)
        logger.debug(str((
            'search',search,'metaWhereClause',metaWhereClause,
            'parameters',self.dataset_info.parameters)))
        queryset = PagedRawQuerySet(
            self.dataset_info.query_sql, self.dataset_info.count_query_sql, 
            connection,parameters=self.dataset_info.parameters, 
            order_by=['datarecord_id'], verbose_name_plural='records')
        if(not self.has_plate_wells_defined()): 
            column_exclusion_overrides.extend(['plate','well'])
        if(not self.has_control_type_defined()): 
            column_exclusion_overrides.append('control_type')

        # TODO: again, all these flags are confusing
        _table = DataSetResultTable(queryset,
                                  self.dataset_info.datacolumns, 
                                  self.has_small_molecules_for_datarecords,
                                  self.has_cells_for_datarecords, 
                                  self.has_proteins_for_datarecords,
                                  self.has_antibodies_for_datarecords,
                                  self.has_otherreagents_for_datarecords,
                                  column_exclusion_overrides) 
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
        
    

    def _get_query_info(self, whereClause=None,metaWhereClause=None, 
                        parameters=None):
        """
        generate a django tables2 table
        TODO: move the logic out of the view: so that it can be shared with the 
        tastypie api (or make this rely on tastypie)
        params:
        whereClause: use this to filter datarecords in the inner query
        metaWhereClause: use this to filter over the entire resultset: 
        any column (as the entire query is made into a subquery)
        """
        if not whereClause:
            whereClause = []
        if not metaWhereClause:
            metaWhereClause = []
        if not parameters:
            parameters = []
        
        logger.debug(str((
            '_get_query_info', whereClause,metaWhereClause, parameters)))
    
        #datacolumns = self.get_dataset_columns(self.dataset.id)
        # TODO: should be a fieldinformation here
        datacolumns = \
            DataColumn.objects.filter(dataset=self.dataset).order_by('display_order')
        # Create a query on the fly that pivots the values from the datapoint 
        # table, making one column for each datacolumn type
        # use the datacolumns to make a query on the fly (for the DataSetManager), 
        # and make a DataSetResultSearchTable on the fly.
    
        # Need to construct something like this:
        # SELECT distinct (datarecord_id), smallmolecule_id, 
        #        sm.facility_id || '-' || sm.salt_id as facility_id,
        #        (SELECT int_value as col1 from db_datapoint dp1 where dp1.datacolumn_id=2 and dp1.datarecord_id = dp.datarecord_id) as col1, 
        #        (SELECT int_value as col2 from db_datapoint dp2 where dp2.datarecord_id=dp.datarecord_id and dp2.datacolumn_id=3) as col2 
        #        from db_datapoint dp join db_datarecord dr on(datarecord_id=dr.id)
        #        join db_smallmoleculebatch smb on(smb.id=dr.smallmolecule_batch_id) 
        #        join db_smallmolecule sm on(sm.id=smb.smallmolecule_id) 
        #        where dp.dataset_id = 1 order by datarecord_id;
        
        queryString = \
            ("SELECT dr_id as datarecord_id,"
             # we need to do this because we have a composite key for sm structures
             " trim( both '-' from ( "
             " sm_facility_id || '-' || salt_id  || '-' || "
             " coalesce(smb_facility_batch_id::TEXT,''))) as facility_salt_batch " 
             ' ,sm_name, sm_alternative_names, plate, well, control_type ' )
        show_cells = self.has_cells()
        show_proteins = self.has_proteins()
        show_antibodies = self.has_antibodies()
        show_otherreagents = self.has_otherreagents()
        if(show_cells): 
            queryString += \
            (", trim( both '-' from ( "
                " cell_facility_id || '-' || coalesce(cell_batch_id::TEXT,''))) as cell_facility_batch ,"
                " cell_name, cell_id " )
        if(show_proteins): 
            queryString += ", protein_id,  protein_name,  protein_lincs_id " 
        if(show_antibodies): 
            queryString += ", antibody_id,antibody_name,  antibody_facility_id " 
        if(show_otherreagents): 
            queryString += ",otherreagent_id,otherreagent_name,otherreagent_facility_id " 

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
            queryString += \
                (",(SELECT " + column_to_select + " FROM db_datapoint " + alias + 
                 " where " + alias + ".datacolumn_id="+str(dc.id) + 
                 " and " + alias + ".datarecord_id=dr_id) as " + columnName )
        queryString += \
            (" FROM  ( SELECT dr.id as dr_id, "
             " sm.id as smallmolecule_id, sm.facility_id as sm_facility_id,"
             " sm.salt_id, smb.facility_batch_id as smb_facility_batch_id, "
             " sm.name as sm_name, sm.alternative_names as sm_alternative_names " 
             " ,plate, well, control_type " )
        if(show_cells):     
            queryString += \
                (" ,cell.id as cell_id, cb.batch_id as cell_batch_id, cell.name as cell_name,"
                " cell.facility_id as cell_facility_id ") 
        if(show_proteins):  
            queryString += \
                (",protein.name as protein_name"
                 ",protein.lincs_id as protein_lincs_id"
                 ",protein.id as protein_id ")
        if(show_antibodies):  
            queryString += \
                (" ,antibody.name as antibody_name"
                 ", antibody.facility_id as antibody_facility_id"
                 ", antibody.id as antibody_id ")
        if(show_otherreagents):  
            queryString += \
                (",otherreagent.name as otherreagent_name"
                 ",otherreagent.facility_id as otherreagent_facility_id"
                 ", otherreagent.id as otherreagent_id ")
        fromClause = " FROM db_datarecord dr " 
        fromClause += \
            " LEFT JOIN db_smallmolecule sm on(dr.smallmolecule_id = sm.id) "
        fromClause += \
            (" LEFT JOIN db_smallmoleculebatch smb on(smb.smallmolecule_id=sm.id"
             " and smb.facility_batch_id=dr.sm_batch_id) ")
        if(show_cells):     
            fromClause += " LEFT JOIN db_cell cell on(cell.id=dr.cell_id ) "
            fromClause += \
                (" LEFT JOIN db_cellbatch cb on(cb.cell_id=cell.id"
                 " and cb.batch_id=dr.cell_batch_id) ")
        if(show_proteins):  
            fromClause += " LEFT JOIN db_protein protein on (protein.id=dr.protein_id) "
        if(show_antibodies):  
            fromClause += " LEFT JOIN db_antibody antibody on (antibody.id=dr.antibody_id) "
        if(show_otherreagents):  
            fromClause += \
                " LEFT JOIN db_otherreagent otherreagent on (otherreagent.id=dr.otherreagent_id) "
        fromClause += " WHERE dr.dataset_id = " + str(self.dataset.id)
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
            # all bets are off if using the metawhereclause, unfortunately, 
            # since it can filter on the inner, dynamic cols
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
        # Create a query on the fly that pivots the values from the datapoint 
        # table, making one column for each datacolumn type
        # use the datacolumns to make a query on the fly (for the DataSetManager), 
        # and make a DataSetResultSearchTable on the fly.
        dataColumnCursor = connection.cursor()
        dataColumnCursor.execute(
            ("SELECT id, name, data_type, precision FROM db_datacolumn "
             "WHERE dataset_id = %s order by id asc", [dataset_id]))
        return dataColumnCursor.fetchall()
    
    def get_dataset_column_names(self,dataset_id):
        column_names = []
        for datacolumn_id, name, datatype, precision in self.get_dataset_columns(dataset_id):
            column_names.append(name)
        return column_names
         
    def cells_for_dataset(self, dataset_id):
        cursor = connection.cursor()
        sql = ( ' SELECT cell.* '
                ' FROM db_cell cell '
                ' WHERE cell.id in (SELECT distinct(cell_id) '
                ' FROM db_datarecord dr WHERE dr.dataset_id=%s) '
                ' OR cell.id in '
                '     (SELECT distinct(cell_id) FROM db_datacolumn dc WHERE dc.dataset_id=%s) '
                ' order by cell.name' )
        # TODO: like this: 
        # SELECT * FROM TABLE, (SELECT COLUMN FROM TABLE) 
        #        as dummytable WHERE dummytable.COLUMN = TABLE.COLUMN;
        cursor.execute(sql, [dataset_id, dataset_id])
        return dictfetchall(cursor)
             
# Note: this usage of the django ORM is not performant 
# - is there and indexing problem; or can we mimick the sql version above?   
#    def cells_for_dataset(self,dataset_id):
#        queryset = Cell.objects.filter(datarecord__dataset__id=dataset_id).distinct() 
#        # Note: restriction not needed as this will only show in the limited 
#        # view of the small molecule table
#        logger.info(str(('cells for dataset',dataset_id,len(queryset))))
#        return queryset
   
    def antibodies_for_dataset(self,dataset_id):
        cursor = connection.cursor()
        sql = ( ' SELECT antibody.* '
                ' FROM db_antibody antibody '
                ' WHERE antibody.id in '
                '    (SELECT distinct(antibody_id) FROM db_datarecord dr WHERE dr.dataset_id=%s) '
                ' order by antibody.name' )

        cursor.execute(sql, [dataset_id])
        return dictfetchall(cursor)
            
    def otherreagents_for_dataset(self,dataset_id):
        cursor = connection.cursor()
        sql = ( ' SELECT otherreagent.* '
                ' FROM db_otherreagent otherreagent '
                ' WHERE otherreagent.id in '
                '     (SELECT distinct(otherreagent_id) FROM db_datarecord dr WHERE dr.dataset_id=%s) '
                ' order by otherreagent.name' )

        cursor.execute(sql, [dataset_id])
        return dictfetchall(cursor)

    def proteins_for_dataset(self,dataset_id):
        cursor = connection.cursor()
        sql = ( ' SELECT protein.* '
                ' FROM db_protein protein '
                ' WHERE protein.id in '
                '    (SELECT distinct(protein_id) FROM db_datarecord dr WHERE dr.dataset_id=%s) '
                ' OR protein.id in '
                '    (SELECT distinct(protein_id) FROM db_datacolumn dc where dc.dataset_id=%s)'
                ' order by protein.name' )

        cursor.execute(sql, [dataset_id, dataset_id])
        return dictfetchall(cursor)

# Note: this usage of the django ORM is a bit more performant than the cell 
# version above; still, going to stick with the non-ORM version for now    
#    def proteins_for_dataset(self,dataset_id):
#        queryset = Protein.objects.filter(datarecord__dataset__id=dataset_id).distinct() 
#        # Note: restriction not needed as this will only show in the limited 
#        # view of the small molecule table
#        logger.info(str(('proteins for dataset',dataset_id,len(queryset))))
#        return queryset

    def small_molecules_for_dataset(self,dataset_id):
        cursor = connection.cursor()
        sql = ( ' SELECT *,' + facility_salt_id + ' as facility_salt, '
                ' (lincs_id is null) as lincs_id_null, pubchem_cid is null as pubchem_cid_null, '
                " (case when sm.is_restricted then '' else sm.facility_id || '-' || sm.salt_id end) "
                "    as unrestricted_image_facility_salt "
                ' FROM db_smallmolecule sm '
                ' WHERE sm.id in '
                '    (SELECT distinct(smallmolecule_id) FROM db_datarecord dr WHERE dr.dataset_id=%s) '
                ' order by sm.facility_id' )
        cursor.execute(sql, [dataset_id])
        
        sm_dict = dictfetchall(cursor)
        # post-process the dictionary to remove restricted field information
        for row_dict in sm_dict:
            for col,value in row_dict.items():
                if col in ['inchi','inchi_key','smiles','molecular_mass','molecular_formula']:
                    del row_dict[col]
                    if row_dict['is_restricted']:
                        row_dict['get_'+col] = 'restricted'
                    else:
                        row_dict['get_'+col] = value
        return sm_dict
            
# Note: though this usage of the django ORM is a bit more performant 
# than the cell version above; still, going to stick with the non-ORM version for now    
#    def small_molecules_for_dataset(self, dataset_id):
#        queryset = SmallMolecule.objects.filter(datarecord__dataset__id=dataset_id).distinct() 
#        # Note: restriction not needed as this will only show in the limited 
#        # view of the small molecule table
#        logger.info(str(('small molecules for dataset',dataset_id,len(queryset))))
#        return queryset
    
    def has_plate_wells_defined(self):
        return DataRecord.objects.all().filter(dataset_id=self.dataset_id)\
            .filter(plate__isnull=False).filter(well__isnull=False).exists()

    def has_control_type_defined(self):
        return DataRecord.objects.all().filter(dataset_id=self.dataset_id)\
            .filter(control_type__isnull=False).exists()

def find_datasets_for_protein(protein_id):
    datasets = [
        x.id for x in DataSet.objects.filter(
            datarecord__protein__id=protein_id).distinct()]
    logger.debug(str(('datasets',datasets)))
    return datasets

def find_datasets_for_antibody(antibody_id):
    datasets = [
        x.id for x in DataSet.objects.filter(
            datarecord__antibody__id=antibody_id).distinct()]
    logger.debug(str(('datasets',datasets)))
    return datasets

def find_datasets_for_otherreagent(otherreagent_id):
    datasets = [
        x.id for x in DataSet.objects.filter(
            datarecord__otherreagent__id=otherreagent_id).distinct()]
    logger.debug(str(('datasets',datasets)))
    return datasets

def find_datasets_for_cell(cell_id):
    datasets = [
        x.id for x in DataSet.objects.filter(
            datarecord__cell__id=cell_id).distinct()]
    logger.debug(str(('datasets',datasets)))
    return datasets

def find_datasets_for_smallmolecule(smallmolecule_id):
    datasets = [
        x.id for x in DataSet.objects.filter(
            datarecord__smallmolecule__id=smallmolecule_id).distinct()]
    logger.debug(str(('datasets',datasets)))
    return datasets
            
class LibraryMappingTable(PagedTable):
    facility_salt_batch = tables.LinkColumn(
        "sm_detail", args=[A('facility_salt_batch')]) 
    sm_name = tables.Column()
    is_control = tables.Column() 
    well = tables.Column()
    plate = tables.Column()
    display_concentration = tables.Column(order_by='concentration')
        
    snippet_def = (" || ' ' || ".join(
        map(lambda x: "coalesce(db_smallmolecule."+x.field+",'') ", 
            FieldInformation.manager.get_search_fields(SmallMolecule)))) 
    
    class Meta:
        #model = LibraryMapping
        orderable = True
        attrs = {'class': 'paleblue'}
        
    def __init__(self, table, show_plate_well=False,*args, **kwargs):
        super(LibraryMappingTable, self).__init__(table)
        sequence_override = ['facility_salt_batch']
        
        set_table_column_info(
            self, ['smallmolecule','smallmoleculebatch','librarymapping',''],
            sequence_override)  
                
class LibraryMappingSearchManager(models.Model):
    """
    Used for librarymapping display
    """
    def search(self, query_string='', is_authenticated=False, library_id=None):
        if(library_id == None): 
            raise Exception(
                'Must define a library id to use the LibraryMappingSearchManager')

        query_string = query_string.strip()
        sql = ( "SELECT " + facility_salt_batch_id + " as facility_salt_batch "
                ", sm.name as sm_name, "
                " lm.concentration ||' '||lm.concentration_unit as display_concentration"
                ", lm.* "
                " FROM db_library l "
                " join db_librarymapping lm on(lm.library_id=l.id) " 
                " LEFT JOIN db_smallmoleculebatch smb on (smb.id=lm.smallmolecule_batch_id) "
                " LEFT JOIN db_smallmolecule sm on(smb.smallmolecule_id=sm.id) " )
        
        where = 'WHERE 1=1 '
        if(query_string != '' ):
            where = ", to_tsquery(%s) as query  WHERE sm.search_vector @@ query "
        where += ' and library_id='+ str(library_id)

        if(not is_authenticated):
            where += ' and ( not sm.is_restricted or sm.is_restricted is NULL)' 
            # TODO: NOTE, not including: ' and not l.is_restricted'; 
            # library restriction will only apply to viewing the library explicitly
            # (the meta data, and selection of compounds)
            
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
    
class BatchInfoLinkColumn(tables.LinkColumn):
    
    def render_link(self, uri, text, attrs=None):
        
        return super(BatchInfoLinkColumn,self).render_link(uri + "#batchinfo",text,attrs)    
    
class SmallMoleculeBatchTable(PagedTable):
    
    facility_salt_batch = BatchInfoLinkColumn("sm_detail", args=[A('facility_salt_batch')])
    facility_salt_batch.attrs['td'] = {'nowrap': 'nowrap'}
    # qc_outcome = tables.Column()
    
    class Meta:
        model = SmallMoleculeBatch
        orderable = True
        attrs = {'class': 'paleblue'}

    def __init__(self, table, show_plate_well=False,*args, **kwargs):
        super(SmallMoleculeBatchTable, self).__init__(table)
        sequence_override = ['facility_salt_batch']
        set_table_column_info(
            self, ['smallmolecule','smallmoleculebatch',''],sequence_override)  


class CellBatchTable(PagedTable):
    batch_id = tables.LinkColumn("cell_detail2", args=[A('cell.facility_id'),A('batch_id')])
    
    class Meta:
        model = CellBatch
        orderable = True
        attrs = {'class': 'paleblue'}

    def __init__(self, table, *args, **kwargs):
        super(CellBatchTable, self).__init__(table, *args, **kwargs)
        sequence_override = ['batch_id']
        set_table_column_info(
            self, ['cell','cellbatch',''],sequence_override)  


class SaltTable(PagedTable):
    
    facility_id = tables.LinkColumn("salt_detail", args=[A('facility_id')])

    class Meta:
        model = SmallMolecule #[SmallMolecule, SmallMoleculeBatch]
        orderable = True
        attrs = {'class': 'paleblue'}
        
    def __init__(
            self, queryset, show_plate_well=False,visible_field_overrides=[], 
            *args, **kwargs):
        super(SaltTable, self).__init__(queryset, *args, **kwargs)
        
        sequence_override = ['facility_id']
        set_table_column_info(
            self, ['salt',''],sequence_override, 
            visible_field_overrides=visible_field_overrides)  
        logger.info('init done')

class SmallMoleculeTable(PagedTable):
    facility_salt = tables.LinkColumn("sm_detail", args=[A('facility_salt')], 
        order_by=['facility_id','salt_id']) 
    facility_salt.attrs['td'] = {'nowrap': 'nowrap'}
    rank = tables.Column()
    snippet = DivWrappedColumn(verbose_name='matched text', classname='snippet')
    dataset_types = DivWrappedColumn(classname='fixed_width_column', visible=False)
    alternative_names = DivWrappedColumn(classname='fixed_width_column')

    image = ImageColumn(
        verbose_name='image', accessor=A('unrestricted_image_facility_salt'), 
        image_class='compound_image_thumbnail', loc=COMPOUND_IMAGE_LOCATION)
    
    # django-tables2 trick to get these columns to sort with NULLS LAST in Postgres; 
    # note this requires the use of an "extra" clause in the query definition 
    # passed to this table (see the _init_ method below)
    lincs_id = tables.Column(order_by=('-lincs_id_null', 'lincs_id'))
    pubchem_cid = tables.Column(order_by=('-pubchem_cid_null', 'pubchem_cid'))

    snippet_def =  (" || ' ' || ".join(
        map(lambda x: "coalesce( " + x.field+",'') ", 
            FieldInformation.manager.get_search_fields(SmallMolecule)))) 
    snippet_def_localized =  (" || ' ' || ".join(
        map(lambda x: "coalesce( db_smallmolecule." + x.field+",'') ", 
            FieldInformation.manager.get_search_fields(SmallMolecule)))) 
        
    class Meta:
        model = SmallMolecule #[SmallMolecule, SmallMoleculeBatch]
        orderable = True
        attrs = {'class': 'paleblue'}
        
    def __init__(self, queryset, show_plate_well=False,
        visible_field_overrides=[], *args, **kwargs):
        super(SmallMoleculeTable, self).__init__(queryset, *args, **kwargs)
        
        sequence_override = ['facility_salt']
        set_table_column_info(
            self, ['smallmolecule','smallmoleculebatch',''],sequence_override, 
            visible_field_overrides=visible_field_overrides)  
        logger.info('init done')

class DataColumnTable(PagedTable):
    protein = tables.LinkColumn("protein_detail", args=[A('protein.lincs_id')])
    cell = tables.LinkColumn("cell_detail", args=[A('cell.facility_id')])
    description = DivWrappedColumn(classname='fixed_width_column', visible=True)
    
    class Meta:
        model = DataColumn
        orderable = True
        attrs = {'class': 'paleblue'}
        
    def __init__(self, table,*args, **kwargs):
        super(DataColumnTable, self).__init__(table)
        sequence_override = []
        set_table_column_info(self, ['datacolumn',''],sequence_override)  

class QCFileColumn(tables.Column):
    
    def __init__(self, *args, **kwargs):
        super(QCFileColumn, self).__init__(*args, **kwargs)    
    
    def render(self, value):
        if value and len(value.all()) > 0:
            links = []
            a = '<a href="%s" >%s</a>'
            for x in value.all():
                link = reverse('download_qc_attached_file',args=[x.id])
                links.append(a%(link,x.filename))
            return mark_safe(',<br/>'.join(links))
            
class QCEventTable(PagedTable):
    
    qcattachedfile_set = QCFileColumn() 
    
    class Meta:
        model = QCEvent
        orderable = True
        attrs = {'class': 'paleblue'}

    def __init__(self, table,*args, **kwargs):
        super(QCEventTable, self).__init__(table)
        sequence_override = []
        set_table_column_info(self, ['qcevent',''],sequence_override)  


class AttachedFileTable(PagedTable):
    filename=tables.LinkColumn("download_attached_file", args=[A('id')])
    
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
    snippet = DivWrappedColumn(verbose_name='matched text', classname='snippet')
    id = tables.Column(verbose_name='CLO Id')
    disease = DivWrappedColumn(classname='fixed_width_column')
    dataset_types = DivWrappedColumn(classname='fixed_width_column', visible=False)
    
#    snippet_def = ("coalesce(name,'') || ' ' || coalesce(id,'') || ' ' || coalesce(alternate_name,'') || ' ' || " +  
#                   "coalesce(alternate_id,'') || ' ' || coalesce(center_name,'') || ' ' || coalesce(center_specific_id,'') || ' ' || " +  
#                   "coalesce(assay,'') || ' ' || coalesce(provider_name,'') || ' ' || coalesce(provider_catalog_id,'') || ' ' || coalesce(batch_id,'') || ' ' || " + 
#                   "coalesce(organism,'') || ' ' || coalesce(organ,'') || ' ' || coalesce(tissue,'') || ' ' || coalesce(cell_type,'') || ' ' ||  " +
#                   "coalesce(cell_type_detail,'') || ' ' || coalesce(disease,'') || ' ' || coalesce(disease_detail,'') || ' ' ||  " +
#                   "coalesce(growth_properties,'') || ' ' || coalesce(genetic_modification,'') || ' ' || coalesce(related_projects,'') || ' ' || " + 
#                   "coalesce(recommended_culture_conditions)")
    snippet_def = (" || ' ' || ".join(
        map(lambda x: "coalesce(db_cell."+x.field+",'') ", 
            FieldInformation.manager.get_search_fields(Cell))))
    class Meta:
        model = Cell
        orderable = True
        attrs = {'class': 'paleblue'}
 
    def __init__(self, table,visible_field_overrides=[], *args,**kwargs):
        super(CellTable, self).__init__(table,*args,**kwargs)
        sequence_override = ['facility_id']    
        set_table_column_info(
            self, ['cell',''], sequence_override, 
            visible_field_overrides=visible_field_overrides)  
                        
class ProteinTable(PagedTable):
    lincs_id = tables.LinkColumn("protein_detail", args=[A('lincs_id')])
    rank = tables.Column()
    snippet = DivWrappedColumn(verbose_name='matched text', classname='snippet')
    snippet_def = (" || ' ' || ".join(
        map(lambda x: "coalesce(db_protein."+x.field+",'') ", 
            FieldInformation.manager.get_search_fields(Protein))))
    alternate_name = DivWrappedColumn(classname='fixed_width_column', visible=False)
    dataset_types = DivWrappedColumn(classname='fixed_width_column', visible=False)

    class Meta:
        model = Protein
        orderable = True
        attrs = {'class': 'paleblue'}
        #sequence = ('lincs_id', '...')
        #exclude = ('id')
    
    def __init__(self, queryset, visible_field_overrides=[], *args, **kwargs):
        super(ProteinTable, self).__init__(queryset, *args, **kwargs)
        sequence_override = ['lincs_id']    
        set_table_column_info(self, ['protein',''],sequence_override, 
            visible_field_overrides=visible_field_overrides)  
                        
class AntibodyTable(PagedTable):
    facility_id = tables.LinkColumn("antibody_detail", args=[A('facility_id')])
    rank = tables.Column()
    snippet = DivWrappedColumn(verbose_name='matched text', classname='snippet')
    snippet_def = (" || ' ' || ".join(
        map(lambda x: "coalesce(db_antibody."+x.field+",'') ", 
            FieldInformation.manager.get_search_fields(Antibody))))
    class Meta:
        model = Antibody
        orderable = True
        attrs = {'class': 'paleblue'}
    
    def __init__(self, table):
        super(AntibodyTable, self).__init__(table)
        sequence_override = ['facility_id']    
        set_table_column_info(self, ['antibody',''],sequence_override)  
                
class OtherReagentTable(PagedTable):
    facility_id = tables.LinkColumn("otherreagent_detail", args=[A('facility_id')])
    rank = tables.Column()
    snippet = DivWrappedColumn(verbose_name='matched text', classname='snippet')
    snippet_def = (" || ' ' || ".join(
        map(lambda x: "coalesce(db_otherreagent."+x.field+",'') ", 
            FieldInformation.manager.get_search_fields(OtherReagent))))
    class Meta:
        model = OtherReagent
        orderable = True
        attrs = {'class': 'paleblue'}
    
    def __init__(self, table):
        super(OtherReagentTable, self).__init__(table)
        sequence_override = ['facility_id']    
        set_table_column_info(self, ['otherreagent',''],sequence_override)  
                
class LibrarySearchManager(models.Manager):
    
    def search(self, query_string, is_authenticated=False):
        query_string = query_string.strip()
        cursor = connection.cursor()
        sql = ( "SELECT a.*, b.*, l.* FROM "
                "(SELECT count(smallmolecule_batch_id) as sm_count, library.id " 
                "     FROM db_library library "
                "     LEFT JOIN db_librarymapping on (library_id=library.id) "
                "     group by library.id ) b " 
                " join db_library l on(b.id=l.id), "
                "(SELECT count(well) as well_count , "
                "     max(plate)-min(plate)+ 1 as plate_count, library.id " 
                "     FROM db_library library "
                "     LEFT JOIN db_librarymapping on(library_id=library.id) ")
        where = ' WHERE 1=1 '
        if(not is_authenticated):
            where += 'and (not library.is_restricted or library.is_restricted is NULL) '
        if(query_string != '' ):
            sql += ", to_tsquery(%s) as query  " 
            where += "and library.search_vector @@ query "
        sql += where
        sql += (" group by library.id) a join db_library l2 on(a.id=l2.id) "
                " WHERE l2.id=l.id order by l.short_name")
        
        logger.debug(str(('sql',sql)))
        # TODO: the way we are separating query_string out here is a kludge, 
        # i.e we should be using django ORM language?
        if(query_string != ''):
            searchProcessed = format_search(query_string)

            cursor.execute(sql, [searchProcessed])
        else:
            cursor.execute(sql)
        v = dictfetchall(cursor)
        return v
    
class LibraryTable(PagedTable):
    id = tables.Column(visible=False)
    name = tables.LinkColumn("library_detail", args=[A('short_name')])
    short_name = tables.LinkColumn("library_detail", args=[A('short_name')])
    well_count = tables.Column()
    plate_count = tables.Column()
    sm_count = tables.Column()
    rank = tables.Column()
    snippet = DivWrappedColumn(verbose_name='matched text', classname='snippet')
    
    snippet_def = (" || ' ' || ".join(map(
        lambda x: "coalesce(db_library."+x.field+",'') ", 
        FieldInformation.manager.get_search_fields(Library))))
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
        # Notes: MaxFragments=10 turns on fragment based headlines (context for
        # search matches), with MaxWords=20
        # ts_rank_cd(search_vector, query, 32): Normalization option 32 
        # (rank/(rank+1)) can be applied to scale all 
        # ranks into the range zero to one, but of course this is just a 
        # cosmetic change; will not affect the ordering of the search results.

        SEARCH_SQL = \
'''
SELECT
  id, {key_id}::text,
  ts_headline({snippet_def}, {query_number}, 'MaxFragments=10, MinWords=1, MaxWords=20, 
              FragmentDelimiter=" | "') as snippet,
  ts_rank_cd(search_vector, {query_number}, 32) AS rank,
  '{detail_type}' as type 
FROM {table_name}, to_tsquery(%s) as {query_number}
WHERE search_vector @@ {query_number} 
'''
        RESTRICTION_SQL = " AND (not is_restricted or is_restricted is NULL)"
        sql = SEARCH_SQL.format(
            key_id='facility_id',
            snippet_def=CellTable.snippet_def,
            detail_type='cell_detail',
            table_name='db_cell',
            query_number='query1')
        if(not is_authenticated): 
            sql += RESTRICTION_SQL
        sql += " UNION "
        sql += SEARCH_SQL.format(
            key_id= "facility_id || '-' || salt_id" ,
            snippet_def=SmallMoleculeTable.snippet_def,
            detail_type='sm_detail',
            table_name='db_smallmolecule',
            query_number='query2')
        if(not is_authenticated): 
            sql += RESTRICTION_SQL
        sql += " UNION "
        sql += SEARCH_SQL.format(
            key_id='facility_id',
            snippet_def=DataSetTable.snippet_def,
            detail_type='dataset_detail',
            table_name='db_dataset',
            query_number='query3')
        if(not is_authenticated): 
            sql += RESTRICTION_SQL
        sql += " UNION "
        sql += SEARCH_SQL.format(
            key_id='lincs_id',
            snippet_def=ProteinTable.snippet_def,
            detail_type='protein_detail',
            table_name='db_protein',
            query_number='query4')
        if(not is_authenticated): 
            sql += RESTRICTION_SQL
        sql += " UNION "
        sql += SEARCH_SQL.format(
            key_id='facility_id',
            snippet_def=AntibodyTable.snippet_def,
            detail_type='antibody_detail',
            table_name='db_antibody',
            query_number='query5')
        if(not is_authenticated): 
            sql += RESTRICTION_SQL
        sql += " UNION "
        sql += SEARCH_SQL.format(
            key_id='facility_id',
            snippet_def=OtherReagentTable.snippet_def,
            detail_type='otherreagent_detail',
            table_name='db_otherreagent',
            query_number='query6')
        if(not is_authenticated): 
            sql += RESTRICTION_SQL
        sql += " ORDER by type, rank DESC;"
        cursor.execute(sql , 
                       [queryStringProcessed,queryStringProcessed,
                        queryStringProcessed,queryStringProcessed,
                        queryStringProcessed,queryStringProcessed])
        _data = dictfetchall(cursor)
        
        smqs = SmallMoleculeSearchManager().search(
                SmallMolecule.objects, 
                queryString, is_authenticated=is_authenticated);
        if len(smqs) > 0:
            for obj in smqs:
                skip = False
                facility_id = obj.facility_id + '-'+ obj.salt_id
                for x in _data:
                    if x['facility_id'] == facility_id: 
                        skip=True
                if not skip:
                    _data.append(
                        {'id':obj.id,'facility_id':facility_id, 
                         'snippet': ', '.join(
                             [x for x in [obj.name, obj.alternative_names, 
                                          obj.lincs_id ] if x and len(x) > 0]),
                         'type':'sm_detail', 'rank':1})
                    
        cqs = CellSearchManager().search(queryString, 
                                         is_authenticated=is_authenticated);
        if len(cqs) > 0:
            for obj in cqs:
                skip = False
                for x in _data:
                    if x['facility_id'] == obj.facility_id: skip = True
                if not skip:
                    _data.append(
                        {'id': obj.id, 'facility_id':obj.facility_id, 
                         'snippet': ', '.join(
                             [x for x in [obj.name, obj.alternate_name ] 
                                 if x and len(x) > 0]),
                         'type': 'cell_detail', 'rank': 1})
    
        pqs = ProteinSearchManager().search(queryString, 
                                            is_authenticated=is_authenticated)
        if len(pqs) > 0:
            for obj in pqs:
                skip = False
                for x in _data:
                    if x['facility_id'] == obj.lincs_id: skip = True
                if not skip:
                    _data.append(
                        {'id': obj.id, 'facility_id': obj.lincs_id, 
                         'snippet': ', '.join(
                             [x for x in [obj.name,obj.uniprot_id,
                                          obj.alternate_name] 
                                 if x and len(x) > 0]),
                         'type': 'protein_detail', 'rank': 1 })

        aqs = AntibodySearchManager().search(queryString, 
                                             is_authenticated=is_authenticated)
        if len(aqs) > 0:
            for obj in aqs:
                skip = False
                for x in _data:
                    if x['facility_id'] == obj.facility_id: skip = True
                if not skip:
                    _data.append(
                        {'id': obj.id, 'facility_id': obj.facility_id, 
                         'snippet': ', '.join(
                             [x for x in [obj.name, obj.alternative_names] 
                                 if x and len(x) > 0]),
                         'type': 'antibody_detail', 'rank': 1 })
                    
        oqs = OtherReagentSearchManager().search(
                queryString, is_authenticated=is_authenticated)
        if len(oqs) > 0:
            for obj in oqs:
                skip = False
                for x in _data:
                    if x['facility_id'] == obj.facility_id: skip = True
                if not skip:
                    _data.append(
                        {'id': obj.id, 'facility_id': obj.facility_id, 
                         'snippet': ', '.join(
                             [x for x in [obj.name, obj.alternative_names] 
                                 if x and len(x) > 0]),
                         'type': 'otherreagent_detail', 'rank': 1 })
        return _data
    
class SearchManager(models.Manager):
    
    def search(self, base_query, tablename, searchString, id_fields, 
            snippet_def, ids=[] ):
        '''
        @param ids extra pk id's for the base_query to 'OR in with the search
        '''
        
        # format the search string to be compatible with the plain text search
        searchProcessed = format_search(searchString) 
        # because the "ID" fields contain a lot of non-words (by english dict),
        # we augment the plain text search with simple contains searches on 
        # these fields
        criteria =   ' ( ' + tablename + '.search_vector @@ to_tsquery(%s)'
        params = [searchProcessed]
        criteria += ' or ' 
        criteria += ' or '.join(['lower('+ x + ') like %s ' for x in id_fields]) 
        criteria += ' ) '
        for x in id_fields: 
            params.append( '%' + searchString.lower() + '%')
        
        if ids:
            # warning: "ANY" is postgresql specific
            criteria += ' or {tablename}.id = ANY(%s)'.format(tablename=tablename)
            params.append(ids)

        where = [criteria]
                
        # postgres fulltext search with rank and snippets
        extra_select = {
                'snippet': "ts_headline(" + snippet_def + ", to_tsquery(%s))",
                'rank':"ts_rank_cd("+tablename+".search_vector,to_tsquery(%s),32)",
                }
        queryset = base_query.extra(
            select=extra_select,
            where=where,
            params=params,
            select_params=[searchProcessed,searchProcessed],
            )  
        queryset = queryset.order_by('-rank')

        return queryset     


class CellSearchManager(SearchManager):

    def search(self, searchString, is_authenticated=False):
        base_query = Cell.objects

        # Override to find the batch field matches
        cell_ids = [ id for id in CellBatch.objects.filter(
            Q(provider_name__icontains=searchString) |
            Q(provider_catalog_id__icontains=searchString)).\
                values_list('cell__id').distinct('cell__id')]
        
        id_fields = ['name', 'alternate_name', 'center_name']
        query =  super(CellSearchManager, self).search(
            base_query, 'db_cell', searchString, id_fields, 
            CellTable.snippet_def, ids=cell_ids)
        
        return query

    def join_query_to_dataset_type(self, queryset, dataset_type=None ):
        key = 'dataset_types'
        if dataset_type:
            # get the set of primary entity id's that satisfy the join to the
            # dataset type - do this as a separate query (filter() returns a 
            # clone) and then use the result to add just the id's back in to the
            # parent query
            ids = [x.id for x in Cell.objects\
                    .filter(datarecord__dataset__dataset_type=str(dataset_type))
                    .order_by('id').distinct('id')]
            queryset = queryset.filter(id__in=ids)
            
        datarecord_field = 'cell_id'
        source_table = 'db_cell'
        queryset = queryset.extra( 
            select={key:(
                "(select array_to_string(array_agg(distinct (ds.dataset_type)),', ')"
                "     as %s from db_dataset ds "
                " join db_datarecord dr on(ds.id=dr.dataset_id) " 
                " where dr.%s=%s.id)" ) % (key,datarecord_field, source_table)})
        return queryset


class ProteinSearchManager(SearchManager):

    def search(self, searchString, is_authenticated=False):

        id_fields = ['name', 'uniprot_id', 'alternate_name', 'alternate_name_2',
             'provider_catalog_id']
        return super(ProteinSearchManager, self).search(
            Protein.objects, 'db_protein', searchString, id_fields, 
            ProteinTable.snippet_def)        
    
    def join_query_to_dataset_type(self, queryset, dataset_type=None ):
        key = 'dataset_types'
        if dataset_type:
            # get the set to of primary entity id's that satisfy the join to the
            # dataset type - do this as a separate query (filter() returns a 
            # clone) and then use the result to add just the id's back in to the
            # parent query
            ids = [x.id for x in Protein.objects\
                    .filter(datarecord__dataset__dataset_type=str(dataset_type))
                    .order_by('id').distinct('id')]
            queryset = queryset.filter(id__in=ids)
            
        datarecord_field = 'protein_id'
        source_table = 'db_protein'
        queryset = queryset.extra( 
            select={key:(
                "(select array_to_string(array_agg(distinct (ds.dataset_type)),', ')"
                "     as %s from db_dataset ds "
                " join db_datarecord dr on(ds.id=dr.dataset_id) " 
                " where dr.%s=%s.id)" ) % (key,datarecord_field, source_table)})
        return queryset

class SmallMoleculeSearchManager(SearchManager):

    def search(self, queryset, searchString, is_authenticated=False):
        # TODO: temp fix for issue #188 
        # - perm fix is to update all ID's to the "HMSLXXX" form
        searchString = re.sub('HMSL','', searchString)
        id_fields = ['name', 'alternative_names', 'lincs_id']
        
        # Override to find the batch field matches
        sm_ids = [ id for id in SmallMoleculeBatch.objects.filter(
            Q(provider__icontains=searchString) |
            Q(provider_catalog_id__icontains=searchString) |
            Q(provider_sample_id__icontains=searchString) ).\
                values_list('smallmolecule__id').distinct('smallmolecule__id')]
        
        return super(SmallMoleculeSearchManager, self).search(
            queryset, 'db_smallmolecule', searchString, id_fields, 
            SmallMoleculeTable.snippet_def_localized, ids=sm_ids )        

    def join_query_to_dataset_type(self, queryset, dataset_type=None ):
        key = 'dataset_types'
        if dataset_type:
            # get the set to of primary entity id's that satisfy the join to the
            # dataset type - do this as a separate query (filter() returns a 
            # clone) and then use the result to add just the id's back in to the
            # parent query
            ids = [x.id for x in SmallMolecule.objects\
                    .filter(datarecord__dataset__dataset_type=str(dataset_type))
                    .order_by('id').distinct('id')]
            queryset = queryset.filter(id__in=ids)
            
        datarecord_field = 'smallmolecule_id'
        source_table = 'db_smallmolecule'
        queryset = queryset.extra( 
            select={key:(
                "(select array_to_string(array_agg(distinct (ds.dataset_type)),', ')"
                "     as %s from db_dataset ds "
                " join db_datarecord dr on(ds.id=dr.dataset_id) " 
                " where dr.%s=%s.id)" ) % (key,datarecord_field, source_table)})
        return queryset

class AntibodySearchManager(SearchManager):
    
    def search(self, searchString, is_authenticated=False):

        id_fields = ['name', 'alternative_names', 'lincs_id']
        return super(AntibodySearchManager, self).search(
            Antibody.objects, 'db_antibody', searchString, id_fields, 
            AntibodyTable.snippet_def)        


class OtherReagentSearchManager(SearchManager):
    
    def search(self, searchString, is_authenticated=False):

        id_fields = ['name', 'alternative_names', 'lincs_id']
        return super(OtherReagentSearchManager, self).search(
            OtherReagent.objects, 'db_otherreagent', searchString, id_fields, 
            OtherReagentTable.snippet_def)        


class SiteSearchTable(PagedTable):
    id = tables.Column(visible=False)
    # Note: using the expediency here: the "type" column holds the subdirectory 
    # for that to make the link for type, so "sm", "cell", etc., becomes 
    # "/db/sm", "/db/cell", etc.
    facility_id = tables.LinkColumn(A('type'), args=[A('facility_id')])  
    type = TypeColumn()
    rank = tables.Column()
    snippet = DivWrappedColumn(verbose_name='matched text', classname='snippet')
    snippet2 = DivWrappedColumn(
        verbose_name='alternate matched text', classname='fixed_width_column', 
        visible=False)
    class Meta:
        orderable = True
        attrs = {'class': 'paleblue'}
        exclude = {'rank'}

def can_access_image(image_filename, is_restricted=False):
    if not is_restricted:
        if settings.DEBUG:
            # In local development mode the staticfiles finders will work, since
            # django itself uses them to serve the static files. In this mode
            # collectstatic will probably never be run so we can't use the
            # storage manager approach used below.
            exists = bool(dcs.finders.find(image_filename))
        else:
            # In the production environment we are running under the web server
            # and may not have access to the static files source directories, so
            # we look the file up through the storage manager (i.e. check the
            # location that collectstatic writes to).
            exists = dcs.storage.staticfiles_storage.exists(image_filename)
    else:
        path = os.path.join(settings.STATIC_AUTHENTICATED_FILE_DIR,
                            image_filename)
        exists = os.access(path, os.R_OK)
    if not exists:
        logger.info(str(('could not find path', image_filename,
                         'restricted=%s' % is_restricted)))
    return exists

def get_attached_files(facility_id, salt_id=None, batch_id=None):
    return AttachedFile.objects.filter(
        facility_id_for=facility_id, salt_id_for=salt_id, batch_id_for=batch_id)

class FieldsMetaForm(forms.Form):
    '''
    create a field for all of the fields passed in; override the default field 
    creation with anything passed in the overrides
    '''
    def __init__(self, field_information_array=[], form_field_overrides={}, 
                 *args, **kwargs):
        super(FieldsMetaForm, self).__init__(*args, **kwargs)

        self.fieldname_array = []
        for fi in [ fi for fi in field_information_array 
                    if fi.show_as_extra_field or 
                       fi.field in form_field_overrides]:
            # Note the fi.field string is unique to each table/report
            self.fields[fi.field +'_shown'] = forms.BooleanField(required=False)
            if fi.field in form_field_overrides:
                self.fields[fi.field] = form_field_overrides[fi.field]
            else:
                self.fields[fi.field] = forms.CharField(required=False)
            self.fieldname_array.append([fi.field + '_shown', fi.field])

        # 2. Grab the (bound) fields and put them in the display matrix 
        # (__getitem__ binds the fields):
        # have to do this _after_ creating and overriding fields
        # our form will wrap, as simply as possible; so here we just give an 
        # ordering to the fields with our fieldrows array
        # TODO: encapsulate this
        self.fieldrows = []
        for one,two in self.fieldname_array:
            self.fieldrows.append([self.__getitem__(one),self.__getitem__(two)])
        
      
def set_table_column_info(table,table_names, sequence_override=None,
                          visible_field_overrides=[]):
    """
    Field information section
    @param table: a django-tables2 table
    @param sequence_override list of fields to show before all other fields
    @param table_names: a list of table names, by order of priority, 
            include '' empty string for a general search.
    """ 
    # TODO: set_table_column info could pick the columns to include from the 
    # fieldinformation as well
    if not sequence_override: 
        sequence_override = []
    fields = OrderedDict()
    exclude_list = [x for x in table.exclude]
    for fieldname,column in table.base_columns.iteritems():
        try:
            fi = FieldInformation.manager.\
                get_column_fieldinformation_by_priority(fieldname,table_names)
            if not fi.show_in_list and not fi.field in visible_field_overrides:
                if(fieldname not in exclude_list):
                    exclude_list.append(fieldname)
            else:
                column.attrs['th']={'title':fi.get_column_detail()}
                column.verbose_name = SafeString(fi.get_verbose_name())
                column.visible = True
                fields[fieldname] = fi
        except (Exception) as e:
            logger.info(str(('no fieldinformation found for field:',fieldname)))
            if(fieldname not in exclude_list):
                exclude_list.append(fieldname)
    fields = OrderedDict(sorted(fields.items(), key=lambda x: x[1].order))
    sequence = filter(
        lambda x: x not in sequence_override and x not in visible_field_overrides, 
        [x for x in fields.keys()])
    sequence_override.extend(visible_field_overrides)
    sequence_override.extend(sequence)
    table.exclude = tuple(exclude_list)
    table.sequence = sequence_override
    
        
def dictfetchall(cursor): 
    """
    Returns all rows from a cursor as an array of dicts, using cursor columns 
    as keys
    """
    desc = cursor.description
    return [
        dict(zip([col[0] for col in desc], row)) for row in cursor.fetchall()
    ]

#@login_required
def restricted_image(request, filepath):
    if(not request.user.is_authenticated()):
        logger.warn(str(('access to restricted file for user is denied', 
                         request.user, filepath)))
        return HttpResponse('Log in required.', status=401)
    
    logger.debug(str(('send requested file:', 
                      settings.STATIC_AUTHENTICATED_FILE_DIR, filepath, 
                      request.user.is_authenticated())))
    _path = os.path.join(settings.STATIC_AUTHENTICATED_FILE_DIR,filepath)
    _file = file(_path)
    logger.debug(str(('download image',_path,_file)))
    wrapper = FileWrapper(_file)
    response = HttpResponse(wrapper,content_type='image/png') 
    response['Content-Length'] = os.path.getsize(_path)
    return response

def download_qc_attached_file(request, id):
    qf = None
    try:
        qf = QCAttachedFile.objects.get(id=id)
    except Exception,e:
        msg = str(('could not find qc attached file object for id', id, e))
        logger.warn(msg)
        raise Http404(msg)
    return _download_file(request,qf)

def download_attached_file(request, id):
    af = None
    try:
        af = AttachedFile.objects.get(id=id)
    except Exception,e:
        msg = str(('could not find attached file object for id', id, e))
        logger.warn(msg)
        raise Http404(msg)
    return _download_file(request,af)
        
def _download_file(request, file_obj):   
    """                                                                         
    Send a file through Django without loading the whole file into              
    memory at once. The FileWrapper will turn the file object into an           
    iterator for chunks of 8KB.                                                 
    """
    try:     
        if(file_obj.is_restricted and not request.user.is_authenticated()):
            logger.warn(str(('access to restricted file for user is denied',
                             request.user,file_obj)))
            return HttpResponse('Log in required.', status=401)
        
        _path = settings.STATIC_AUTHENTICATED_FILE_DIR
        if(file_obj.relative_path):
            _path = os.path.join(_path,file_obj.relative_path)
        _path = os.path.join(_path,file_obj.filename)
        _file = file(_path)
        logger.info(str(('download_attached_file',request.user.username,_path,file_obj)))
        wrapper = FileWrapper(_file)
        # use the same type for all files
        response = HttpResponse(wrapper, content_type='application/octet-stream') 
        response['Content-Disposition'] = \
            'attachment; filename=%s' % unicode(file_obj.filename)
        response['Content-Length'] = os.path.getsize(_path)
        return response
    except Exception,e:
        msg = str(('could not find attached file object for file_obj', file_obj, e))
        logger.warn(msg)
        raise Http404(msg)

def _get_raw_time_string():
  return timezone.now().strftime("%Y%m%d%H%M%S")

def send_to_file1(outputType, name, table_name, ordered_datacolumns, cursor, 
                  is_authenticated=False):
    """
    Export the datasetdata cursor to the file type pointed to by outputType
    @param ordered_datacolumns the datacolumns for the datasetdata, in order, 
           so that they can be indexed by column number
    @param outputType '.csv','.xls'
    @param table a django-tables2 table
    @param name name of the table - to be used for the output file name
     
    """   
    logger.info(str(('send_to_file1', outputType, name, ordered_datacolumns)))
    col_key_name_map = get_cols_to_write(
        cursor, [table_name, 'dataset','smallmolecule','datarecord',
                 'smallmoleculebatch','protein','antibody', 'otherreagent', 
                 'cell','datacolumn', ''],
        ordered_datacolumns)   
    
    name = name + '_' + _get_raw_time_string()

    if(outputType == '.csv'):
        return export_as_csv(name,col_key_name_map, cursor=cursor, 
                             is_authenticated=is_authenticated)
    elif(outputType == '.xls'):
        return export_as_xls(name, col_key_name_map, cursor=cursor, 
                             is_authenticated=is_authenticated)

def send_to_file(outputType, name, table, queryset, table_name, 
                 extra_columns = [], is_authenticated=False): 
    """
    Export the queryset to the file type pointed to by outputType.  
    Get the column header information from the django-tables2 table
    @param outputType '.csv','.xls'
    @param table a django-tables2 table
    @param name name of the table - to be used for the output file name
     
    """       
    # ordered list (field,verbose_name)
    columns = map(lambda (x,y): (x, y.verbose_name), 
                  filter(lambda (x,y): x!='rank' and x!='snippet' and y.visible, 
                         table.base_columns.items()))

    # TODO: the following two step process looks a the table def, then at 
    # fieldinformation, make this simpler by just looking at the fieldinf
    # grab the columns from the table definition
    columnsOrdered = []
    for col in table._sequence:
        for (field,verbose_name) in columns:
            if(field==col):
                columnsOrdered.append((field,verbose_name))
                break
    columnsOrdered.extend(extra_columns)
    # use field information to clean up and remove unneeded columns
    fieldinformation_tables = [ 
        table_name, 'dataset','smallmolecule','datarecord','smallmoleculebatch',
        'protein','antibody', 'otherreagent','cell','datacolumn', '']
    columnsOrdered_filtered = []
    for field,verbose_name in columnsOrdered:
        try:
            # _ is the marker for private fields - only accessible through logic
            # defined on the ORM object
            # i.e. if authorized
            if(field[0] == '_'):
                temp = field[1:]
                field = 'get_' + temp
                fi = FieldInformation.manager.\
                    get_column_fieldinformation_by_priority(
                        field,fieldinformation_tables)
                columnsOrdered_filtered.append((field,fi.get_verbose_name()))
                logger.info(str(('found', field, fi)))
            else:
                fi = FieldInformation.manager.\
                    get_column_fieldinformation_by_priority(
                        field,fieldinformation_tables)
            if(fi.show_in_detail):
                columnsOrdered_filtered.append((field,fi.get_verbose_name()))
        except (Exception) as e:
            logger.warn(str(('no fieldinformation found for field:', field, e)))        

    name = name + '_' + _get_raw_time_string()
    
    # The type strings deliberately include a leading "." to make the URLs
    # trigger the analytics js code that tracks download events by extension.
    if(outputType == '.csv'):
        return export_as_csv(
            name,OrderedDict(columnsOrdered_filtered), queryset=queryset, 
            is_authenticated=is_authenticated)
    elif(outputType == '.xls'):
        return export_as_xls(
            name, OrderedDict(columnsOrdered_filtered), queryset=queryset, 
            is_authenticated=is_authenticated)

def get_cols_to_write(cursor, fieldinformation_tables=None, 
                      ordered_datacolumns=None):
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
                fi = FieldInformation.manager.\
                    get_column_fieldinformation_by_priority(
                        col.name,fieldinformation_tables)
                header_row[i] = fi.get_verbose_name()
            except (Exception) as e:
                logger.warn(
                    str(('no fieldinformation found for field:', col.name)))
         
    return OrderedDict(sorted(header_row.items(),key=lambda x: x[0]))


def _write_val_safe(val, is_authenticated=False):
    # for #185, remove 'None' values
    return smart_str(val, 'utf-8', errors='ignore') if val else ''
  
def export_sm_images(queryset, is_authenticated=False, output_filename=None):
    '''
    Export all the small molecule images referenced in the queryset:
    - skip restricted images if not authenticated
    - skip and log an error if the image file cannot be found.
    @param queryset Smallmolecule objects to consider
    '''

    s = StringIO.StringIO()        
    filehandle = zipfile.ZipFile(s, "w")

    # wrapper to use dicts as objects
    class AttributeDict(dict): 
        __getattr__ = dict.__getitem__

    for smobj in queryset:
        if isinstance(smobj,dict):
            sm = AttributeDict(smobj)
        else:
            sm = smobj
        location = '%s/HMSL%s-%s.png' % (COMPOUND_IMAGE_LOCATION, 
                                         sm.facility_id, sm.salt_id)
        image_path = None
        if not sm.is_restricted:
            if settings.DEBUG:
                image_path = dcs.finders.find(location, all=False)
            else:
                ss = dcs.storage.staticfiles_storage
                if ss.exists(location):
                    image_path = ss.path(location)
            if not image_path: 
                logger.error(str(('image file for sm zip file does not exist',
                                  location )))

        if sm.is_restricted and is_authenticated:
            temp = os.path.join(settings.STATIC_AUTHENTICATED_FILE_DIR,location)
            if os.path.exists(temp):
                image_path = temp
            else: 
                logger.error(str(('image file for sm zip file does not exist',
                                  temp )))

        if image_path:
            filehandle.write(image_path, arcname=location, 
                             compress_type=zipfile.ZIP_DEFLATED)
    filehandle.close()  
    # Grab ZIP file from in-memory, make response with correct MIME-type
    response = HttpResponse(s.getvalue(),
                            mimetype="application/x-zip-compressed")  
    
    output_filename = output_filename or 'hms_lincs_molecule_images'
    response['Content-Disposition'] = \
        'attachment; filename=%s.zip' % output_filename
    return response

def export_as_csv(name,col_key_name_map, cursor=None, queryset=None, 
                  is_authenticated=False):
    """
    Generic csv export admin action.
    """
    response = HttpResponse(mimetype='text/csv')
    response['Content-Disposition'] = \
        'attachment; filename=%s.csv' % unicode(name).replace('.', '_')
    writer = csv.writer(response)
    # Write a first row with header information
    writer.writerow(col_key_name_map.values())

    debug_interval=1000
    row = 0
    assert (cursor or queryset) \
        and not (cursor and queryset), 'must define either cursor or queryset'
    if cursor:
        obj=cursor.fetchone()
        keys = col_key_name_map.keys()
        logger.debug(str(('keys',keys,obj)))
        while obj:
            writer.writerow([_write_val_safe(obj[int(key)]) for key in keys])
            if(row % debug_interval == 0):
                logger.info("row: " + str(row))
            row += 1
            obj=cursor.fetchone()
    elif queryset:
        for obj in queryset:
            if isinstance(obj, dict):
                writer.writerow(
                    [_write_val_safe(obj[field]) \
                        for field in col_key_name_map.keys()])
            else:# a ORM object
                vals = [getattr(obj,field) for field in col_key_name_map.keys()]
                vals_authenticated = []
                for i,column in enumerate(vals):
                    # if the method is a column, we are referencing the method 
                    # wrapper for restricted columns
                    if(inspect.ismethod(column)):
                        vals_authenticated.append(
                            _write_val_safe(
                                column(is_authenticated=is_authenticated)))
                    else:
                        vals_authenticated.append(_write_val_safe(column))
                writer.writerow(vals_authenticated)
            if(row % debug_interval == 0):
                logger.info("row: " + str(row))
            row += 1
    return response

def export_as_xls(name,col_key_name_map, cursor=None, queryset=None, 
                  is_authenticated=False):
    """
    Generic xls export admin action.
    """
    logger.info(str(('------is auth:',is_authenticated)) )
    response = HttpResponse(mimetype='applicatxlwt.Workbookion/Excel')
    response['Content-Disposition'] = \
        'attachment; filename=%s.xls' % unicode(name).replace('.', '_')

    wbk = xlwt.Workbook(encoding='utf8')
    sheet = wbk.add_sheet('sheet 1') # Write a first row with header information
    for i,name in enumerate(col_key_name_map.values()):
        sheet.write(0, i, name)   
            
    debug_interval=1000
    row = 0
    assert (cursor or queryset) \
        and not (cursor and queryset), 'must define either cursor or queryset'
    if cursor:
        obj=cursor.fetchone()
        keys = col_key_name_map.keys()
        logger.debug(str(('keys',keys)))
        while obj:  # row in the dataset; a tuple to be indexed numerically
            for i,key in enumerate(keys):
                sheet.write(row+1,i,_write_val_safe(obj[key]))
            if(row % debug_interval == 0):
                logger.info("row: " + str(row))
            row += 1
            obj=cursor.fetchone()
    elif queryset:
        for obj in queryset:  
            if isinstance(obj, dict): # a ORM object as a dict
                vals = [_write_val_safe(obj[field]) \
                            for field in col_key_name_map.keys()]
            else: # a ORM object
                vals = [getattr(obj,field) for field in col_key_name_map.keys()]
            
            for i,column in enumerate(vals):
                # if the columnn is a method, we are referencing the method 
                # wrapper for restricted columns
                if(inspect.ismethod(column)):
                    sheet.write(
                        row+1,i, _write_val_safe(
                            column(is_authenticated=is_authenticated)) )
                else:
                    sheet.write(row+1, i, _write_val_safe(column) )
            if(row % debug_interval == 0):
                logger.info("row: " + str(row))
            row += 1    
    
    wbk.save(response)
    return response

