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
import zipfile

from django.conf import settings
import django.contrib.staticfiles as dcs
from django.contrib.staticfiles.templatetags.staticfiles import static
from django.core.exceptions import ObjectDoesNotExist
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
from django.utils.html import escape
from openpyxl import Workbook
from openpyxl.writer.excel import save_virtual_workbook

from hms.pubchem import pubchem_database_cache_service
from dump_obj import dumpObj
from PagedRawQuerySet import PagedRawQuerySet
from db.models import PubchemRequest, SmallMolecule, SmallMoleculeBatch, Cell, \
    Protein, DataSet, Library, FieldInformation, AttachedFile, DataRecord, \
    DataColumn, get_detail, Antibody, OtherReagent, CellBatch, QCEvent, \
    QCAttachedFile, AntibodyBatch, Reagent, ReagentBatch, get_listing
from django_tables2.utils import AttributeDict
from tempfile import SpooledTemporaryFile


logger = logging.getLogger(__name__)

APPNAME = 'db',
COMPOUND_IMAGE_LOCATION = "compound-images-by-facility-salt-id"  
AMBIT_COMPOUND_IMAGE_LOCATION = "ambit-study-compound-images-by-facility-salt-id"  
DATASET_IMAGE_LOCATION = "dataset-images-by-facility-id" 

OMERO_IMAGE_COLUMN_TYPE = 'omero_image'
DAYS_TO_CACHE = 1
DAYS_TO_CACHE_PUBCHEM_ERRORS = 1


def dump(obj):
    dumpObj(obj)

# --------------- View Functions -----------------------------------------------

def main(request):
    search = request.GET.get('search','')
    logger.debug(str(('main search: ', search)))
    if(search != ''):
        queryset = SiteSearchManager2().search(
            search, is_authenticated=request.user.is_authenticated());

        table = SiteSearchTable(queryset)
        if(len(table.data)>0):
            RequestConfig(request, paginate={"per_page": 25}).configure(table)
        else:
            table = None
        return render(request, 'db/index.html', 
            {   'table': table, 
                'search':search, 
                'dataset_types': json.dumps(DataSet.get_dataset_types()) })
    else:
        return render(request, 'db/index.html', 
            {'dataset_types': json.dumps(DataSet.get_dataset_types()) })

def cellIndex(request):
    search = request.GET.get('search','')
    logger.debug(str(("is_authenticated:", 
        request.user.is_authenticated(), 'search: ', search)))
    search = re.sub(r'[\'"]','',search)
 
    if(search != ''):
        queryset = CellSearchManager().search(search, 
            is_authenticated=request.user.is_authenticated())      
    else:
        queryset = Cell.objects.order_by('facility_id')
        if not request.user.is_authenticated(): 
            queryset = queryset.exclude(is_restricted=True)
 
    # PROCESS THE EXTRA FORM    
    field_hash=FieldInformation.manager.get_field_hash('cell')
    
    # 1. Override fields: note do this _before_ grabbing all the (bound) fields
    # for the display matrix below
    form_field_overrides = {}
    fieldinformation = \
        FieldInformation.manager.get_column_fieldinformation_by_priority('dataset_types', '')
    field_hash['dataset_types'] = fieldinformation
    form_field_overrides['dataset_types'] = forms.ChoiceField(
        required=False, choices=DataSet.get_dataset_types(), 
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
        return send_to_file(outputType, 'cells', table, queryset, ['cell',''] )
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
        
        logger.info(str((details)))
        
        details['facility_id'] = cell.facility_id
        cell_batch = None
        if(_batch_id):
            cell_batch = CellBatch.objects.get( 
                reagent=cell, batch_id=_batch_id) 

        # batch table
        if not cell_batch:
            batches = CellBatch.objects.filter(reagent=cell, batch_id__gt=0)
            if batches.exists():
                details['batchTable']=CellBatchTable(batches)
        else:
            details['cell_batch']= get_detail(
                cell_batch,['cellbatch',''])
            details['facility_batch'] = '%s-%s' % (cell.facility_id,cell_batch.batch_id) 

            # 20150413 - proposed "QC Outcome" field on batch info removed per group discussion
            qcEvents = QCEvent.objects.filter(
                facility_id_for=cell.facility_id,
                batch_id_for=cell_batch.batch_id).order_by('-date')
            if qcEvents:
                details['qcTable'] = QCEventTable(qcEvents)
            
            if(not cell.is_restricted or request.user.is_authenticated()):
                attachedFiles = get_attached_files(
                    cell.facility_id,batch_id=cell_batch.batch_id)
                if(len(attachedFiles)>0):
                    details['attached_files_batch'] = AttachedFileTable(attachedFiles)        
                
        datasets = DataSet.objects.filter(cells__reagent=cell).distinct()
        if(datasets.exists()):
            where = []
            if(not request.user.is_authenticated()): 
                where.append("(not is_restricted or is_restricted is NULL)")
            queryset = datasets.extra(
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
    else:
        queryset = Protein.objects.order_by('lincs_id')
        if not request.user.is_authenticated(): 
            queryset = queryset.exclude(is_restricted=True)

    # PROCESS THE EXTRA FORM    
    field_hash=FieldInformation.manager.get_field_hash('protein')
    
    # 1. Override fields: 
    # Note - do this _before_ grabbing all the (bound) fields for the display matrix below
    form_field_overrides = {}
    fieldinformation = \
        FieldInformation.manager.get_column_fieldinformation_by_priority('dataset_types', '')
    field_hash['dataset_types'] = fieldinformation
    form_field_overrides['dataset_types'] = forms.ChoiceField(
        required=False, choices=DataSet.get_dataset_types(), 
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
        return send_to_file(outputType, 'proteins', table, queryset, ['protein',''] )
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
        
        datasets = DataSet.objects.filter(proteins__reagent=protein).distinct()
        if(datasets.exists()):
            where = []
            if(not request.user.is_authenticated()): 
                where.append("(not is_restricted or is_restricted is NULL)")
            queryset = datasets.extra( where=where, order_by=('facility_id',))        
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
    else:
        queryset = Antibody.objects.order_by('facility_id')
        if not request.user.is_authenticated(): 
            queryset = queryset.exclude(is_restricted=True)
    
    table = AntibodyTable(queryset)
    outputType = request.GET.get('output_type','')
    if(outputType != ''):
        return send_to_file(outputType, 'antibodies', table, queryset, ['antibody',''] )
    RequestConfig(request, paginate={"per_page": 25}).configure(table)
    return render_list_index(request, table,search,'Antibody','Antibodies')
   
def antibodyDetail(request, facility_batch, batch_id=None):
    try:
        _batch_id = None
        if not batch_id:
            temp = facility_batch.split('-') 
            logger.info('find antibody for %s' % temp)
            _facility_id = temp[0]
            if len(temp) > 1:
                _batch_id = temp[1]
        else:
            _facility_id = facility_batch
            _batch_id = batch_id        
        
        antibody = Antibody.objects.get(facility_id=_facility_id) 
        if(antibody.is_restricted and not request.user.is_authenticated()):
            return HttpResponse('Log in required.', status=401)
        details = {'object': get_detail(antibody, ['antibody',''])}
        
        if antibody.target_protein_name and antibody.target_protein_center_id:
            details['object']['target_protein_name']['link'] = (
                '/db/proteins/%s' % antibody.target_protein_center_id )
        if antibody.target_protein_center_id:
            details['object']['target_protein_center_id']['link'] = (
                '/db/proteins/%s' % antibody.target_protein_center_id )
        
        details['facility_id'] = antibody.facility_id
        antibody_batch = None
        if(_batch_id):
            antibody_batch = AntibodyBatch.objects.get(
                reagent=antibody,batch_id=_batch_id) 

        if not antibody_batch:
            batches = AntibodyBatch.objects.filter(reagent=antibody, batch_id__gt=0)
            if batches.exists():
                details['batchTable']=AntibodyBatchTable(batches)
        else:
            details['antibody_batch']= get_detail(
                antibody_batch,['antibodybatch',''])
            details['facility_batch'] = '%s-%s' % (antibody.facility_id,antibody_batch.batch_id) 

            qcEvents = QCEvent.objects.filter(
                facility_id_for=antibody.facility_id,
                batch_id_for=antibody_batch.batch_id).order_by('-date')
            if qcEvents:
                details['qcTable'] = QCEventTable(qcEvents)
            
            if(not antibody.is_restricted or request.user.is_authenticated()):
                attachedFiles = get_attached_files(
                    antibody.facility_id,batch_id=antibody_batch.batch_id)
                if(len(attachedFiles)>0):
                    details['attached_files_batch'] = AttachedFileTable(attachedFiles)        
                
        datasets = DataSet.objects.filter(antibodies__reagent=antibody).distinct()
        if(datasets.exists()):
            where = []
            if(not request.user.is_authenticated()): 
                where.append("(not is_restricted or is_restricted is NULL)")
            queryset = datasets.extra(
                    where=where,
                    order_by=('facility_id',))        
            details['datasets'] = DataSetTable(queryset)

        # add in the LIFE System link: TODO: put this into the fieldinformation
        extralink = {   
            'title': 'LINCS Information Framework Page' ,
            'name': 'LIFE Antibody Information',
            'link': ( 'http://life.ccs.miami.edu/life/summary?mode=Antibody'
                      '&input={ar_center_specific_id}&source=HMS' )
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
    else:
        queryset = OtherReagent.objects.order_by('facility_id')
        if not request.user.is_authenticated(): 
            queryset = queryset.exclude(is_restricted=True)
    
    table = OtherReagentTable(queryset)
    outputType = request.GET.get('output_type','')
    if(outputType != ''):
        return send_to_file(outputType, 'other_reagents', table, queryset, ['otherreagent',''] )
    RequestConfig(request, paginate={"per_page": 25}).configure(table)
    return render_list_index(request, table,search,'Other Reagent','Other Reagents')
    
def otherReagentDetail(request, facility_id):
    try:
        reagent = OtherReagent.objects.get(facility_id=facility_id) # todo: cell here
        if(reagent.is_restricted and not request.user.is_authenticated()):
            return HttpResponse('Log in required.', status=401)
        details = {'object': get_detail(reagent, ['otherreagent',''])}
        
        datasets = DataSet.objects.filter(other_reagents__reagent=reagent).distinct()
        if(datasets.exists()):
            where = []
            if(not request.user.is_authenticated()): 
                where.append("(not is_restricted or is_restricted is NULL)")
            queryset = datasets.extra(where=where,
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
        required=False, choices=DataSet.get_dataset_types(), 
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
                    [tablename,''], is_authenticated=request.user.is_authenticated())
    
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
                reagent=sm,batch_id=temp[2]) 

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
            batches = SmallMoleculeBatch.objects.filter(reagent=sm,batch_id__gt=0)
            if batches.exists():
                details['batchTable']=SmallMoleculeBatchTable(batches)
        else:
            details['smallmolecule_batch']= get_detail(
                smb,['smallmoleculebatch',''])
            details['facility_salt_batch'] = '%s-%s-%s' % (sm.facility_id,sm.salt_id,smb.batch_id) 
            # 20150413 - proposed "QC Outcome" field on batch info removed per group discussion
            qcEvents = QCEvent.objects.filter(
                facility_id_for=sm.facility_id,
                salt_id_for=sm.salt_id,
                batch_id_for=smb.batch_id).order_by('-date')
            if qcEvents:
                details['qcTable'] = QCEventTable(qcEvents)
            
            logger.info(str(('smb', details['smallmolecule_batch'])))
            
            if(not sm.is_restricted or request.user.is_authenticated()):
                attachedFiles = get_attached_files(
                    sm.facility_id,sm.salt_id,smb.batch_id)
                if(len(attachedFiles)>0):
                    details['attached_files_batch'] = AttachedFileTable(attachedFiles)        
        
        # datasets table
        datasets = DataSet.objects.filter(small_molecules__reagent=sm).distinct()
        if(datasets.exists()):
            where = []
            if(not request.user.is_authenticated()): 
                where.append("(not is_restricted or is_restricted is NULL)")
            queryset = datasets.extra(
                where=where, order_by=('facility_id',))        
            details['datasets'] = DataSetTable(queryset)
        
        # nominal target dataset results information
        try:
            dataset = DataSet.objects.get(dataset_type='Nominal Targets')
            metaWhereClause=[
                '''"smallMolecule" ~ '^%s' ''' % sm.facility_salt,
                '''"isNominal" = '1' '''] 
            ntable = DataSetManager2(dataset).get_table(
                metaWhereClause=metaWhereClause,
                column_exclusion_overrides=['isNominal'])
            logger.info(str(('ntable',ntable.data, len(ntable.data))))
            
            if ntable.data: 
                details['nominal_targets_table']=ntable
            
            metaWhereClause=[
                '''"smallMolecule" ~ '^%s' ''' % sm.facility_salt,
                '''"isNominal" != '1' '''] 
            otable = DataSetManager2(dataset).get_table(
                metaWhereClause=metaWhereClause,
                column_exclusion_overrides=[
                    'isNominal'])
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

    except ObjectDoesNotExist:
        raise Http404

def libraryIndex(request):
    search = request.GET.get('search','')
    search = re.sub(r'[\'"]','',search)
    queryset = LibrarySearchManager().search(
        search, is_authenticated=request.user.is_authenticated());
    table = LibraryTable(queryset)
    outputType = request.GET.get('output_type','')
    if(outputType != ''):
        return send_to_file(outputType, 'libraries', table, queryset, ['library',''] )
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
                    table, queryset, ['library','smallmolecule',
                        'smallmoleculebatch','librarymapping',''] )
        
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
                'snippet': "ts_headline(" + DataSet.get_snippet_def() + ", to_tsquery(%s) )",
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
        
    # PROCESS THE EXTRA FORM    
    field_hash=FieldInformation.manager.get_field_hash('dataset')

    # 1. Override fields: note do this _before_ grabbing all the (bound) fields
    # for the display matrix below
    form_field_overrides = {}
    form_field_overrides['dataset_type'] = forms.ChoiceField(
        required=False, choices=DataSet.get_dataset_types(), 
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
            outputType, 'datasetIndex', table, queryset, ['dataset',''] )
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
        details = datasetDetail2(request,facility_id, 'main')
        details['skip_blanks'] = True
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
            queryset = Cell.objects.filter(id__in=(
                dataset.cells.all().values_list('reagent_id',flat=True).distinct()))
            return send_to_file(
                outputType, 'cells_for_'+ str(facility_id), 
                CellTable(queryset), queryset, ['cell',''] )
        except DataSet.DoesNotExist:
            raise Http404
    try:
        details = datasetDetail2(request,facility_id, 'cells')
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
            queryset = Protein.objects.filter(id__in=(
                dataset.proteins.all().values_list('reagent_id',flat=True).distinct()))
            return send_to_file(
                outputType, 'proteins_for_'+ str(facility_id), 
                ProteinTable(queryset), 
                queryset, ['protein',''] )
        except DataSet.DoesNotExist:
            raise Http404
    try:
        details = datasetDetail2(request,facility_id,'proteins')
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
            queryset = Antibody.objects.filter(id__in=(
                dataset.antibodies.all().values_list('reagent_id',flat=True).distinct()))
            return send_to_file(
                outputType, 'antibodies_for_'+ str(facility_id), 
                AntibodyTable(queryset), 
                queryset, ['antibody',''] )
        except DataSet.DoesNotExist:
            raise Http404
    try:
        details = datasetDetail2(request,facility_id,'antibodies')
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
            queryset = OtherReagent.objects.filter(id__in=(
                dataset.other_reagents.all().values_list('reagent_id',flat=True).distinct()))
            return send_to_file(
                outputType, 'other_reagents_for_'+ str(facility_id), 
                OtherReagentTable(queryset), 
                queryset, ['otherreagent',''] )
        except DataSet.DoesNotExist:
            raise Http404
    try:
        details = datasetDetail2(request,facility_id,'otherreagents')
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
            queryset = SmallMolecule.objects.filter(id__in=(
                dataset.small_molecules.all()
                    .values_list('reagent_id',flat=True).distinct()))
            if outputType == '.zip':
                filename = 'sm_images_for_dataset_' + str(dataset.facility_id)
                return export_sm_images(queryset, 
                                        request.user.is_authenticated(),
                                        output_filename=filename)
            else:
                return send_to_file(
                    outputType, 'small_molecules_for_'+ str(facility_id), 
                    SmallMoleculeTable(queryset), 
                    queryset,['smallmolecule',''] )
        except DataSet.DoesNotExist:
            raise Http404
    try:
        details = datasetDetail2(request,facility_id,'small_molecules')
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
            
            return send_to_file(
                outputType, 'datacolumns_for_'+ str(facility_id),
                DataColumnTable(queryset), queryset, ['datacolumn',''] )
        except DataSet.DoesNotExist:
            raise Http404
    try:
        details = datasetDetail2(request,facility_id,'datacolumns')
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
            manager = DataSetManager2(dataset)
            form = manager.get_result_set_data_form(request)
            cursor = manager.get_cursor(facility_ids=form.get_search_facility_ids())
            datacolumns = \
                DataColumn.objects.filter(dataset=dataset).order_by('display_order')
            return send_to_file1(
                outputType, 'dataset_'+str(facility_id), 'dataset', 
                datacolumns, cursor, ['dataset',''] )
        
        details = datasetDetail2(request,facility_id, 'results')
        
        details['pop_out_link'] = request.get_full_path().replace('results','results_minimal')

        return render(request,template, details)
        
    except DataSet.DoesNotExist:
        raise Http404    
    except Http401:
        return HttpResponse('Unauthorized', status=401)


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
    else:
        form = PaginationForm()
    
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

    def get_search_facility_ids(self):
        facility_ids = []
        if self.is_valid():
            for key in self.entity_id_name_map.keys():
                if key in self.fields:
                    vals = self.cleaned_data[key]
                    if(vals and len(vals) > 0):
                        facility_ids.extend([str(val) for val in vals])
        return facility_ids
    
    
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
        elif value == "antibody_detail": return "Antibody"
        elif value == "otherreagent_detail": return "Other Reagent"
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
            return self.paginator.per_page * (self.page.number-1) + 1
        
    def page_end(self):
        if(self.page):
            temp = self.paginator.per_page * (self.page.number-1) + self.paginator.per_page
            logger.debug(str(('page_end:' , temp, self.paginator.count )))
            if(temp > self.paginator.count): return self.paginator.count
            return temp


class DataSetTable(PagedTable):
    id = tables.Column(visible=False)
    facility_id = tables.LinkColumn("dataset_detail", args=[A('facility_id')])
    title = DivWrappedColumn(classname='constrained_width_column_300', visible=False)
    protocol = tables.Column(visible=False) 
    references = tables.Column(visible=False)
    rank = tables.Column()
    snippet = DivWrappedColumn(verbose_name='matched text', classname='snippet')
    class Meta:
        model = DataSet
        orderable = True
        attrs = {'class': 'paleblue'}

    def __init__(self, table):
        super(DataSetTable, self).__init__(table)
        
        set_table_column_info(self, ['dataset',''])  

    
OMERO_IMAGE_TEMPLATE = '''
   <a href="#" onclick='window.open("https://lincs-omero.hms.harvard.edu/webclient/img_detail/{{ record.%s }}", "Image","height=700,width=800")' ><img src='https://lincs-omero.hms.harvard.edu/webgateway/render_thumbnail/{{ record.%s }}/32/' alt='image if available' ></a>
'''
            
class LibraryMappingTable(PagedTable):
    facility_salt_batch = tables.LinkColumn(
        "sm_detail", args=[A('facility_salt_batch')]) 
    sm_name = tables.Column()
    is_control = tables.Column() 
    well = tables.Column()
    plate = tables.Column()
    display_concentration = tables.Column(order_by='concentration')
        
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
        sql = ( "SELECT r.facility_id || '-' || r.salt_id || '-' || rb.batch_id as facility_salt_batch "
                ", r.name as sm_name, "
                " lm.concentration ||' '||lm.concentration_unit as display_concentration"
                ", lm.* "
                " FROM db_library l "
                " join db_librarymapping lm on(lm.library_id=l.id) " 
                " LEFT JOIN db_reagentbatch rb on (rb.id=lm.smallmolecule_batch_id) "
                " LEFT JOIN db_reagent r on(rb.reagent_id=r.id) " )
        
        where = 'WHERE 1=1 '
        if(query_string != '' ):
            where = ", to_tsquery(%s) as query  WHERE sm.search_vector @@ query "
        where += ' and library_id='+ str(library_id)

        if(not is_authenticated):
            where += ' and ( not r.is_restricted or r.is_restricted is NULL)' 
            # TODO: NOTE, not including: ' and not l.is_restricted'; 
            # library restriction will only apply to viewing the library explicitly
            # (the meta data, and selection of compounds)
            
        sql += where
        sql += " order by "
        if(library_id != None):
            sql += "plate, well, rb.batch_id, "
        sql += " r.facility_id, r.salt_id "
        
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
    facility_batch = BatchInfoLinkColumn("cell_detail", args=[A('facility_batch')])
    
    class Meta:
        model = CellBatch
        orderable = True
        attrs = {'class': 'paleblue'}

    def __init__(self, table, *args, **kwargs):
        super(CellBatchTable, self).__init__(table, *args, **kwargs)
        sequence_override = ['facility_batch']
        set_table_column_info(
            self, ['cell','cellbatch',''],sequence_override)  


class AntibodyBatchTable(PagedTable):
    facility_batch = BatchInfoLinkColumn("antibody_detail", args=[A('facility_batch')])
    
    class Meta:
        model = AntibodyBatch
        orderable = True
        attrs = {'class': 'paleblue'}

    def __init__(self, table, *args, **kwargs):
        super(AntibodyBatchTable, self).__init__(table, *args, **kwargs)
        sequence_override = ['facility_batch']
        set_table_column_info(
            self, ['antibody','antibodybatch',''],sequence_override)  


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
    dataset_types = DivWrappedColumn(classname='constrained_width_column', visible=False)
    alternative_names = DivWrappedColumn(classname='constrained_width_column')

    image = ImageColumn(
        verbose_name='image', accessor=A('unrestricted_facility_salt'), 
        image_class='compound_image_thumbnail', loc=COMPOUND_IMAGE_LOCATION)
    
    # django-tables2 trick to get these columns to sort with NULLS LAST in Postgres; 
    # note this requires the use of an "extra" clause in the query definition 
    # passed to this table (see the _init_ method below)
    lincs_id = tables.Column(order_by=('-lincs_id_null', 'lincs_id'))
    pubchem_cid = tables.Column(order_by=('-pubchem_cid_null', 'pubchem_cid'))

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
    description = DivWrappedColumn(classname='constrained_width_column', visible=True)
    
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
    disease = DivWrappedColumn(classname='constrained_width_column')
    dataset_types = DivWrappedColumn(classname='constrained_width_column', visible=False)
    
#    snippet_def = ("coalesce(name,'') || ' ' || coalesce(id,'') || ' ' || coalesce(alternate_name,'') || ' ' || " +  
#                   "coalesce(alternate_id,'') || ' ' || coalesce(center_name,'') || ' ' || coalesce(center_specific_id,'') || ' ' || " +  
#                   "coalesce(assay,'') || ' ' || coalesce(provider_name,'') || ' ' || coalesce(provider_catalog_id,'') || ' ' || coalesce(batch_id,'') || ' ' || " + 
#                   "coalesce(organism,'') || ' ' || coalesce(organ,'') || ' ' || coalesce(tissue,'') || ' ' || coalesce(cell_type,'') || ' ' ||  " +
#                   "coalesce(cell_type_detail,'') || ' ' || coalesce(disease,'') || ' ' || coalesce(disease_detail,'') || ' ' ||  " +
#                   "coalesce(growth_properties,'') || ' ' || coalesce(genetic_modification,'') || ' ' || coalesce(related_projects,'') || ' ' || " + 
#                   "coalesce(recommended_culture_conditions)")

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
    alternative_names = DivWrappedColumn(classname='constrained_width_column', visible=False)
    dataset_types = DivWrappedColumn(classname='constrained_width_column', visible=False)

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
    target_protein_name = tables.LinkColumn("protein_detail", args=[A('target_protein_center_id')])
    
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

class SearchManager(models.Manager):
    
    def search(self, base_query, tablename, searchString, id_fields, 
            snippet_def, ids=None ):
        '''
        @param ids extra pk id's for the base_query to 'OR in with the search
        '''
        ids = ids or []
        logger.info('searchString %s, id_fields: %s, snippet_def: %s, ids: %s'
            % (searchString, id_fields, snippet_def, ids))
        # format the search string to be compatible with the plain text search
        searchProcessed = format_search(searchString) 
        # because the "ID" fields contain a lot of non-words (by english dict),
        # we augment the plain text search with simple contains searches on 
        # these fields
        criteria =   ' ( ' + tablename + '.search_vector @@ to_tsquery(%s)'
        params = [searchProcessed]
        if id_fields: 
            criteria += ' or '
            criteria += ' or '.join(['lower('+ x + ') like %s ' for x in id_fields]) 
        for x in id_fields: 
            params.append( '%' + searchString.lower() + '%')

        # postgres fulltext search with rank and snippets
        extra_select = {
                'snippet': "ts_headline(" + snippet_def + ", to_tsquery(%s))",
                'rank':"ts_rank_cd("+tablename+".search_vector,to_tsquery(%s),32)",
                }
        if tablename in ['db_smallmolecule','db_cell','db_antibody','db_protein','db_otherreagent']:
            criteria += ' or db_reagent.search_vector @@ to_tsquery(%s)'
            extra_select['snippet'] += (
                ' || ts_headline(' + Reagent.get_snippet_def() 
                + ', to_tsquery(%s))' )
            params.append(searchProcessed)
            extra_ids = [ id for id in ReagentBatch.objects.filter(
                Q(provider_name__icontains=searchString) |
                Q(provider_catalog_id__icontains=searchString) |
                Q(provider_batch_id__icontains=searchString) ).\
                    values_list('reagent__id').distinct('reagent__id')]
            ids.extend(extra_ids)
            
            extra_ids = [ id for id in 
                Reagent.objects.filter(
                    Q(name__icontains=searchString) |
                    Q(lincs_id__icontains=searchString) |
                    Q(alternative_names__icontains=searchString) |
                    Q(facility_id__icontains=searchString))
                    .values_list('id') ]
            ids.extend(extra_ids)
        
        if ids:
            if tablename in ['db_smallmolecule','db_cell','db_antibody','db_protein','db_otherreagent']:
                criteria += ' or reagent_ptr_id = ANY(%s)'.format(tablename=tablename)
            else:
                criteria += ' or {tablename}.id = ANY(%s)'.format(tablename=tablename)
            params.append(ids)

        criteria += ' ) '
        # force join to the reagent table so that it is available in all orm use cases
        criteria += ' AND db_reagent.id=%s.reagent_ptr_id' % tablename
        where = [criteria]
                
        queryset = base_query.extra(
            tables=['db_reagent'],
            select=extra_select,
            where=where,
            params=params,
            select_params=[searchProcessed,searchProcessed,searchProcessed],
            order_by=('-rank',)
            )  
        
        logger.info('queryset: %s' % queryset.query)
        return queryset     


class CellSearchManager(SearchManager):

    def search(self, searchString, is_authenticated=False):
        base_query = Cell.objects.all()
        
        id_fields = []
        query =  super(CellSearchManager, self).search(
            base_query, 'db_cell', searchString, id_fields, 
            Cell.get_snippet_def())
        
        return query

    def join_query_to_dataset_type(self, queryset, dataset_type=None ):
        if dataset_type:
            ids = (DataSet.objects
                .filter(dataset_type=str(dataset_type))
                .values_list('cells__reagent__id', flat=True)
                .distinct('cells__reagent__id') )
            queryset = queryset.filter(id__in=ids)
        queryset = queryset.extra(select={
            'dataset_types' : (
                "(select array_to_string(array_agg(distinct (ds.dataset_type)),', ')"
                "     from db_dataset ds "
                " join {join_table} on(ds.id={join_table}.dataset_id) " 
                " join db_reagentbatch rb on(rb.id={join_table}.{specific_batch_id} ) "
                " where rb.reagent_id={specific_reagent_table}.reagent_ptr_id)" ) 
                    .format(join_table='db_dataset_cells',
                            specific_batch_id='cellbatch_id',
                            specific_reagent_table='db_cell')
            })
        return queryset


class ProteinSearchManager(SearchManager):

    def search(self, searchString, is_authenticated=False):

        id_fields = ['uniprot_id', 'alternate_name_2',
             'provider_catalog_id']
        return super(ProteinSearchManager, self).search(
            Protein.objects.all(), 'db_protein', searchString, id_fields, 
            Protein.get_snippet_def())        
    
    def join_query_to_dataset_type(self, queryset, dataset_type=None ):
        if dataset_type:
            ids = (DataSet.objects
                .filter(dataset_type=str(dataset_type))
                .values_list('proteins__reagent__id', flat=True)
                .distinct('proteins__reagent__id') )
            queryset = queryset.filter(id__in=ids)
        queryset = queryset.extra(select={
            'dataset_types' : (
                "(select array_to_string(array_agg(distinct (ds.dataset_type)),', ')"
                "     from db_dataset ds "
                " join {join_table} on(ds.id={join_table}.dataset_id) " 
                " join db_reagentbatch rb on(rb.id={join_table}.{specific_batch_id} ) "
                " where rb.reagent_id={specific_reagent_table}.reagent_ptr_id)" ) 
                    .format(join_table='db_dataset_proteins',
                            specific_batch_id='proteinbatch_id',
                            specific_reagent_table='db_protein')
            })
        return queryset


class SmallMoleculeSearchManager(SearchManager):

    def search(self, queryset, searchString, is_authenticated=False):
        # TODO: temp fix for issue #188 
        # - perm fix is to update all ID's to the "HMSLXXX" form
        searchString = re.sub('HMSL','', searchString)
        id_fields = []
        
        return super(SmallMoleculeSearchManager, self).search(
            queryset, 'db_smallmolecule', searchString, id_fields, 
            SmallMolecule.get_snippet_def() )        

    def join_query_to_dataset_type(self, queryset, dataset_type=None ):
        if dataset_type:
            ids = (DataSet.objects
                .filter(dataset_type=str(dataset_type))
                .values_list('small_molecules__reagent__id', flat=True)
                .distinct('small_molecules__reagent__id') )
            queryset = queryset.filter(id__in=ids)
        queryset = queryset.extra(select={
            'dataset_types' : (
                "(select array_to_string(array_agg(distinct (ds.dataset_type)),', ')"
                "     from db_dataset ds "
                " join {join_table} on(ds.id={join_table}.dataset_id) " 
                " join db_reagentbatch rb on(rb.id={join_table}.{specific_batch_id} ) "
                " where rb.reagent_id={specific_reagent_table}.reagent_ptr_id)" ) 
                    .format(join_table='db_dataset_small_molecules',
                            specific_batch_id='smallmoleculebatch_id',
                            specific_reagent_table='db_smallmolecule')
            })
        return queryset

class AntibodySearchManager(SearchManager):
    
    def search(self, searchString, is_authenticated=False):

        id_fields = []
        return super(AntibodySearchManager, self).search(
            Antibody.objects.all(), 'db_antibody', searchString, id_fields, 
            Antibody.get_snippet_def())        

    def join_query_to_dataset_type(self, queryset, dataset_type=None ):
        if dataset_type:
            ids = (DataSet.objects
                .filter(dataset_type=str(dataset_type))
                .values_list('antibodies__reagent__id', flat=True)
                .distinct('antibodies__reagent__id') )
            queryset = queryset.filter(id__in=ids)
        queryset = queryset.extra(select={
            'dataset_types' : (
                "(select array_to_string(array_agg(distinct (ds.dataset_type)),', ')"
                "     from db_dataset ds "
                " join {join_table} on(ds.id={join_table}.dataset_id) " 
                " join db_reagentbatch rb on(rb.id={join_table}.{specific_batch_id} ) "
                " where rb.reagent_id={specific_reagent_table}.reagent_ptr_id)" ) 
                    .format(join_table='db_dataset_antibodies',
                            specific_batch_id='antibodybatch_id',
                            specific_reagent_table='db_antibody')
            })
        return queryset

class OtherReagentSearchManager(SearchManager):
    
    def search(self, searchString, is_authenticated=False):

        id_fields = []
        return super(OtherReagentSearchManager, self).search(
            OtherReagent.objects.all(), 'db_otherreagent', searchString, id_fields, 
            OtherReagent.get_snippet_def())        

    def join_query_to_dataset_type(self, queryset, dataset_type=None ):
        if dataset_type:
            ids = (DataSet.objects
                .filter(dataset_type=str(dataset_type))
                .values_list('other_reagents__reagent__id', flat=True)
                .distinct('other_reagents__reagent__id') )
            queryset = queryset.filter(id__in=ids)
        queryset = queryset.extra(select={
            'dataset_types' : (
                "(select array_to_string(array_agg(distinct (ds.dataset_type)),', ')"
                "     from db_dataset ds "
                " join {join_table} on(ds.id={join_table}.dataset_id) " 
                " join db_reagentbatch rb on(rb.id={join_table}.{specific_batch_id} ) "
                " where rb.reagent_id={specific_reagent_table}.reagent_ptr_id)" ) 
                    .format(join_table='db_dataset_other_reagents',
                            specific_batch_id='otherreagentbatch_id',
                            specific_reagent_table='db_otherreagent')
            })
        return queryset


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
        verbose_name='alternate matched text', classname='constrained_width_column', 
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
    fields = OrderedDict(sorted(fields.items(), key=lambda x: x[1].list_order))
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
            'attachment; filename=%s' % file_obj.filename
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
    @param outputType '.csv','.xlsx'
    @param table a django-tables2 table
    @param name the filename to use, consisting of only word characters
    """
    assert not re.search(r'\W',name), '"name" parameter: "%s" must contain only word characters' % name

    logger.info(str(('send_to_file1', outputType, name, ordered_datacolumns)))
    col_key_name_map = get_cols_to_write(
        cursor, [table_name, ''],
        ordered_datacolumns)   
    
    name = name + '_' + _get_raw_time_string()

    if(outputType == '.csv'):
        return export_as_csv(name,col_key_name_map, cursor=cursor, 
                             is_authenticated=is_authenticated)
    elif(outputType in ['.xls','.xlsx']):
        return export_as_xlsx(name, col_key_name_map, cursor=cursor, 
                             is_authenticated=is_authenticated)
    else:
        raise Http404('Unknown output type: "%s", must be one of [".xlsx",".csv"]' % outputType )


def get_cols_to_write(cursor, fieldinformation_tables=None, 
                      ordered_datacolumns=None):
    """
    returns a dict of #column_number:verbose_name
    """
    if not fieldinformation_tables: 
        fieldinformation_tables=['']
    header_row = {}
    for i,col in enumerate(cursor.description):
        found = False
        if ordered_datacolumns:
            logger.info('find cursor col %r in ordered_datacolumns %s' 
                % (col.name, [x.name for x in ordered_datacolumns]))
            for dc in ordered_datacolumns:
                if ( dc.data_type in 
                    ['small_molecule', 'cell','protein','antibody','other_reagent']):
                    if dc.name == col.name:
                        found = True
                        header_row[i] = dc.display_name + ' HMS LINCS ID'
                    elif '%s_name'%dc.name == col.name:
                        found = True
                        header_row[i] = dc.display_name + ' Name'
                elif dc.name == col.name:
                    found = True
                    header_row[i] = dc.display_name
        if not found:
            logger.info('col: %r, not found in datacolumns, find in fieldinformation' % col.name)
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
    # also, for #386, trim leading spaces from strings for openpyxl
    # see https://bitbucket.org/openpyxl/openpyxl/issues/280
    return smart_str(val, 'utf-8', errors='ignore').strip() if val else ''
  
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
    @param cursor a django.db.connection.cursor; must define either cursor
        or queryset, not both
    @param queryset a django QuerySet or simple list; must define either cursor
        or queryset, not both
    @param name the filename to use, consisting of only word characters
    """
    assert not re.search(r'\W',name), '"name" parameter: "%s" must contain only word characters' % name
    assert not (bool(cursor) and bool(queryset)), 'must define either cursor or queryset, not both'
    
    response = HttpResponse(mimetype='text/csv')
    response['Content-Disposition'] = \
        'attachment; filename=%s.csv' % name

    if not (bool(cursor) or bool(queryset)):
        logger.info(str(('empty result for', name)))
        return response

    writer = csv.writer(response)
    # Write a first row with header information
    writer.writerow(col_key_name_map.values())

    debug_interval=1000
    row = 0
    
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

def export_as_xlsx(name,col_key_name_map, cursor=None, queryset=None, 
                  is_authenticated=False):
    """
    Generic xls export admin action.
    @param cursor a django.db.connection.cursor; must define either cursor
        or queryset, not both
    @param queryset a django QuerySet or simple list; must define either cursor
        or queryset, not both
    @param name the filename to use, consisting of only word characters
    """
    assert not re.search(r'\W',name), '"name" parameter: "%s" must contain only word characters' % name
    assert not (bool(cursor) and bool(queryset)), 'must define either cursor or queryset, not both'
    
    logger.info(str(('------is auth:',is_authenticated)) )

    if not (bool(cursor) or bool(queryset)):
        logger.info(str(('empty result for', name)))
        return response

    wb = Workbook(optimized_write=True)
    ws = wb.create_sheet()
    ws.append(col_key_name_map.values())
    debug_interval=1000
    row = 0
    
    if cursor:
        obj=cursor.fetchone()
        keys = col_key_name_map.keys()
        while obj:  # row in the dataset; a tuple to be indexed numerically
            ws.append([_write_val_safe(obj[key]) for key in keys])
            if(row % debug_interval == 0):
                logger.info("row: " + str(row))
            row += 1
            obj=cursor.fetchone()
    elif queryset:
        for obj in queryset:  
            if isinstance(obj, dict): # a ORM object as a dict
                vals = [_write_val_safe(obj[field]) 
                            for field in col_key_name_map.keys()]
            else: # a ORM object
                vals = [getattr(obj,field) for field in col_key_name_map.keys()]
            
            temp = []
            for column in vals:
                # if the columnn is a method, we are referencing the method 
                # wrapper for restricted columns
                if(inspect.ismethod(column)):
                    temp.append(_write_val_safe(
                        column(is_authenticated=is_authenticated)) )
                else:
                    temp.append(_write_val_safe(column))
            ws.append(temp)
            if(row % debug_interval == 0):
                logger.info("row: " + str(row))
            row += 1 
    logger.info('save temp file')
    with SpooledTemporaryFile() as f:
        wb.save(f)
        f.seek(0)
        logger.info('write file to response: %s ' % name)
        response = HttpResponse(
            f.read(), 
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename=%s.xlsx' % name
        return response
    
def send_to_file(outputType, name, table, queryset, lookup_tables, 
                 extra_columns = None, is_authenticated=False): 
    """
    Export the queryset to the file type pointed to by outputType.  
    Get the column header information from the django-tables2 table
    @param outputType '.csv','.xls'
    @param table a django-tables2 table
    @param name the filename to use, consisting of only word characters
    """
    assert not re.search(r'\W',name), '"name" parameter: "%s" must contain only word characters' % name
    
    extra_columns = extra_columns or []
    # ordered list (field,verbose_name)
    columns = map(lambda (x,y): (x, y.verbose_name), 
                  filter(lambda (x,y): x!='rank' and x!='snippet' and y.visible, 
                         table.base_columns.items()))
    col_fi_map = {}
    for field,verbose_name in columns:
        try:
            # _ is the marker for private fields - only accessible through logic
            # defined on the ORM object
            # i.e. if authorized
            if(field[0] == '_'):
                temp = field[1:]
                field = 'get_' + temp
                fi = FieldInformation.manager.\
                    get_column_fieldinformation_by_priority(
                        field,lookup_tables)
                logger.info(str(('found', field, fi)))
            else:
                fi = FieldInformation.manager.\
                    get_column_fieldinformation_by_priority(
                        field,lookup_tables)
            if(fi.show_in_detail):
                col_fi_map[field]=fi
        except (Exception) as e:
            logger.warn(str(('no fieldinformation found for field:', field, e)))        
    col_key_name_map = OrderedDict([(x[0],x[1].get_verbose_name()) 
        for x in sorted(col_fi_map.items(), key=lambda item:item[1].detail_order)])    

    name = name + '_' + _get_raw_time_string()
    
    # The type strings deliberately include a leading "." to make the URLs
    # trigger the analytics js code that tracks download events by extension.
    if(outputType == '.csv'):
        return export_as_csv(
            name,col_key_name_map, queryset=queryset, 
            is_authenticated=is_authenticated)
    elif(outputType in ['.xls','.xlsx']):
        return export_as_xlsx(
            name, col_key_name_map, queryset=queryset, 
            is_authenticated=is_authenticated)
    else:
        raise Http404('Unknown output type: "%s", must be one of [".xlsx",".csv"]' % outputType )

def datasetDetail2(request, facility_id, sub_page):
    try:
        dataset = DataSet.objects.get(facility_id=facility_id)
        if(dataset.is_restricted and not request.user.is_authenticated()):
            raise Http401
    except DataSet.DoesNotExist:
        raise Http404

    manager = DataSetManager2(dataset)

    details =  {'object': get_detail(manager.dataset, ['dataset','']),
                'facilityId': facility_id,
                'has_small_molecules':dataset.small_molecules.exists(),
                'has_cells':dataset.cells.exists(),
                'has_proteins':dataset.proteins.exists(),
                'has_antibodies':dataset.antibodies.exists(),
                'has_otherreagents':dataset.other_reagents.exists()}

    items_per_page = 25
    form = PaginationForm(request.GET)
    details['items_per_page_form'] = form
    if(form.is_valid()):
        if(form.cleaned_data['items_per_page']): 
            items_per_page = int(form.cleaned_data['items_per_page'])
    
    if (sub_page == 'results'):

        form = manager.get_result_set_data_form(request)
        table = manager.get_table(facility_ids=form.get_search_facility_ids()) 
        details['search_form'] = form
        if(len(table.data)>0):
            details['table'] = table
            RequestConfig(
                request, paginate={"per_page": items_per_page}).configure(table)

        
    elif (sub_page == 'cells'):
        if dataset.cells.exists():
            queryset = Cell.objects.filter(id__in=(
                dataset.cells.all().values_list('reagent_id',flat=True).distinct()))
            queryset = queryset.order_by('facility_id')
            table = CellTable(queryset)
            setattr(table.data,'verbose_name_plural','Cells')
            setattr(table.data,'verbose_name','Cells')
            details['table'] = table
            RequestConfig(
                request, paginate={"per_page": items_per_page}).configure(table)
    elif (sub_page == 'proteins'):
        if dataset.proteins.exists():
            queryset = Protein.objects.filter(id__in=(
                dataset.proteins.all().values_list('reagent_id',flat=True).distinct()))
            queryset = queryset.order_by('facility_id')
            table = ProteinTable(queryset)
            setattr(table.data,'verbose_name_plural','Proteins')
            setattr(table.data,'verbose_name','Protein')
            details['table'] = table
            RequestConfig(
                request, paginate={"per_page": items_per_page}).configure(table)
    elif (sub_page == 'antibodies'):
        if dataset.antibodies.exists():
            queryset = Antibody.objects.filter(id__in=(
                dataset.antibodies.all().values_list('reagent_id',flat=True).distinct()))
            queryset = queryset.order_by('facility_id')
            table = AntibodyTable(queryset)
            setattr(table.data,'verbose_name_plural','Antibodies')
            setattr(table.data,'verbose_name','Antibody')
            details['table'] = table
            RequestConfig(
                request, paginate={"per_page": items_per_page}).configure(table)
    elif (sub_page == 'otherreagents'):
        if dataset.other_reagents.exists():
            queryset = OtherReagent.objects.filter(id__in=(
                dataset.other_reagents.all().values_list('reagent_id',flat=True).distinct()))
            queryset = queryset.order_by('facility_id')
            table = OtherReagentTable(queryset)
            setattr(table.data,'verbose_name_plural','Other Reagents')
            setattr(table.data,'verbose_name','Other Reagent')
            details['table'] = table
            RequestConfig(
                request, paginate={"per_page": items_per_page}).configure(table)
    elif (sub_page == 'small_molecules'):
        if dataset.small_molecules.exists():
            queryset = SmallMolecule.objects.filter(id__in=(
                dataset.small_molecules.all().values_list('reagent_id',flat=True).distinct()))
            queryset = queryset.order_by('facility_id')
            table = SmallMoleculeTable(queryset)
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

class DataSetResultTable2(PagedTable):

    id = tables.Column(visible=False)
    plate = tables.Column()
    well = tables.Column()
    control_type = tables.Column()
        
    class Meta:
        orderable = True
        attrs = {'class': 'paleblue'}
    
    def __init__(self, queryset, ordered_datacolumns, 
            column_exclusion_overrides=None, *args, **kwargs):

        self.set_field_information_to_table_column('plate','plate', ['datarecord'])
        self.set_field_information_to_table_column('well', 'well', ['datarecord'])
        self.set_field_information_to_table_column('control_type', 
            'control_type', ['datarecord'])

        defined_base_columns = ['plate','well','control_type']
        for name in self.base_columns.keys():
            if name not in defined_base_columns:
                logger.debug('deleting column from the table %s, %s', 
                    name,defined_base_columns)
                del self.base_columns[name]

        ordered_names = []
        for dc in ordered_datacolumns:
            if dc.data_type in ['small_molecule', 'cell','protein','antibody','other_reagent']:
                ordered_names.append(dc.name + "_name")
            else:
                ordered_names.append(dc.name)

        ordered_names.extend(['plate','well','control_type'])
        
        for i,dc in enumerate(ordered_datacolumns):    
            col = dc.name
            key_col = col
            display_name = (
                (SafeString(dc.display_name), dc.name)[
                    dc.display_name == None or len(dc.display_name)==0] )
            if dc.data_type.lower() == OMERO_IMAGE_COLUMN_TYPE:
                self.base_columns[key_col] = tables.TemplateColumn(
                    OMERO_IMAGE_TEMPLATE % (col,col), verbose_name=display_name)
            elif dc.data_type.lower() == 'small_molecule':
                key_col = col+'_name'
                self.base_columns[key_col] = tables.LinkColumn('sm_detail',
                    args=[A(col)], verbose_name=display_name) 
            elif dc.data_type.lower() == 'cell':
                key_col = col+'_name'
                self.base_columns[key_col] = tables.LinkColumn('cell_detail',
                    args=[A(col)], verbose_name=display_name) 
            elif dc.data_type.lower() == 'protein':
                key_col = col+'_name'
                self.base_columns[key_col] = tables.LinkColumn('protein_detail',
                    args=[A(col)], verbose_name=display_name) 
            elif dc.data_type.lower() == 'antibody':
                key_col = col+'_name'
                self.base_columns[key_col] = tables.LinkColumn('antibody_detail',
                    args=[A(col)], verbose_name=display_name) 
            elif dc.data_type.lower() == 'other_reagent':
                key_col = col+'_name'
                self.base_columns[key_col] = tables.LinkColumn('otherreagent_detail',
                    args=[A(col)], verbose_name=display_name) 
            else:
                logger.info('create base col %r' % col)
                if dc.data_type.lower() == 'numeric':
                    self.base_columns[col] = tables.Column(verbose_name=display_name)
                elif dc.data_type.lower() == 'boolean':
                    self.base_columns[col] = tables.BooleanColumn(verbose_name=display_name)
                else:
                    self.base_columns[col] = DivWrappedColumn(
                        classname='constrained_width_column',verbose_name=display_name)
            if dc.description: 
                self.base_columns[key_col].attrs['th'] = { 'title':dc.description }

        super(DataSetResultTable2, self).__init__(queryset, *args, **kwargs)
        if(self.exclude): 
            self.exclude = tuple(list(self.exclude).extend(column_exclusion_overrides))
        else: 
            self.exclude = tuple(column_exclusion_overrides)
        logger.info('base columns: %s' % self.base_columns )
        self.sequence = ordered_names
        
    def set_field_information_to_table_column(self, column_name, fieldname, table_names):
        try:
            column = self.base_columns[column_name]
            fi = FieldInformation.manager.get_column_fieldinformation_by_priority(
                fieldname,table_names)
            column.attrs['th']={'title':fi.get_column_detail()}
            column.verbose_name = SafeString(fi.get_verbose_name())
        except (Exception) as e:
            raise Exception(str(('no fieldinformation found for field:', 
                fieldname, table_names,e)))


class DataSetManager2():
    
    def __init__(self,dataset,is_authenticated=False):
        self.dataset = dataset
        self.dataset_id = dataset.id
            
    class DatasetForm(ModelForm):
        class Meta:
            model = DataSet           
            order = ('facility_id', '...')
            exclude = ('id', 'molfile') 

    def get_result_set_data_form(self, request):
        
        entity_id_name_map = {}
        if self.dataset.cells.exists():
            entity_id_name_map['cells'] = { 
                'id_field': 'cell_id', 
                'choices': [ ( item.reagent.facility_id, 
                    '%s:%s'% ( item.reagent.name,item.reagent.facility_id ) ) 
                    for item in self.dataset.cells.all() ] }
        if self.dataset.proteins.exists():
            entity_id_name_map['proteins'] = { 
                'id_field': 'protein_id', 
                'choices': [ ( item.reagent.facility_id, 
                    '%s:%s'% ( item.reagent.name,item.reagent.facility_id ) ) 
                    for item in self.dataset.proteins.all() ] }
        if self.dataset.small_molecules.exists():
            entity_id_name_map['small molecules'] = { 
                'id_field': 'smallmolecule_id', 
                'choices': [ ( item.reagent.facility_id, 
                    '%s:%s'% ( item.reagent.name,item.reagent.facility_id ) ) 
                    for item in self.dataset.small_molecules.all() ] }
        if self.dataset.antibodies.exists():
            entity_id_name_map['antibodies'] = { 
                'id_field': 'antibody_id', 
                'choices': [ ( item.reagent.facility_id, 
                    '%s:%s' % ( item.reagent.name,item.reagent.facility_id) ) 
                    for item in self.dataset.antibodies.all() ] }
        if self.dataset.other_reagents.exists():
            entity_id_name_map['other reagents'] = { 
                'id_field': 'otherreagent_id', 
                'choices': [ ( item.reagent.facility_id, 
                    '%s:%s' % ( item.reagent.name,item.reagent.facility_id ) )
                    for item in self.dataset.other_reagents.all() ] }
            
        form = ResultSetDataForm(entity_id_name_map=entity_id_name_map, data=request.GET)
        
        return form
        
    def get_cursor(
        self, whereClause=None, metaWhereClause=None,
        column_exclusion_overrides=None, parameters=None, facility_ids=None): 
        
        if not whereClause:
            whereClause = []
        if not metaWhereClause:
            metaWhereClause = []
        if not parameters:
            parameters = []
        if not column_exclusion_overrides:
            column_exclusion_overrides = []
            
        logger.debug('metaWhereClause: %r, parameters: %s' 
            % ( metaWhereClause, parameters ) )
        
        self.dataset_info = self._get_query_info(
            whereClause, metaWhereClause, parameters, facility_ids)
        cursor = connection.cursor()
        logger.info('execute sql: %r, parameters: %s' 
            % ( self.dataset_info.query_sql, self.dataset_info.parameters) )
        cursor.execute(self.dataset_info.query_sql,self.dataset_info.parameters)
        return cursor

    def get_table(
        self, whereClause=None, metaWhereClause=None,
        column_exclusion_overrides=None, parameters=None, facility_ids=None): 
        
        if not whereClause:
            whereClause = []
        if not metaWhereClause:
            metaWhereClause = []
        if not parameters:
            parameters = []
        if not column_exclusion_overrides:
            column_exclusion_overrides = []
            
        self.dataset_info = self._get_query_info(
            whereClause, metaWhereClause, parameters, facility_ids)
        
        logger.debug('metaWhereClause: %r, parameters: %s' 
            % (metaWhereClause, self.dataset_info.parameters) )
        logger.info('queryset %r' % self.dataset_info.query_sql)

        queryset = PagedRawQuerySet(
            self.dataset_info.query_sql, self.dataset_info.count_query_sql, 
            connection,parameters=self.dataset_info.parameters, 
            order_by=['datarecord_id'], verbose_name_plural='records')
        if(not self.has_plate_wells_defined()): 
            column_exclusion_overrides.extend(['plate','well'])
        if(not self.has_control_type_defined()): 
            column_exclusion_overrides.append('control_type')

        logger.debug('dataset_info %s' % self.dataset_info )
        _table = DataSetResultTable2(queryset,self.dataset_info.datacolumns, 
            column_exclusion_overrides) 

        setattr(_table.data,'verbose_name_plural','records')
        setattr(_table.data,'verbose_name','record')
        return _table

    class DatasetInfo:
        datacolumns = []
        query_sql = ''
        count_query_sql = ''
        parameters = []
        
        def __repr__(self):
            return ( 'DatasetInfo< %s, %s, %s, %s >' 
                % (self.datacolumns,self.query_sql,self.count_query_sql,self.parameters))

    def _get_query_info(self, whereClause=None,metaWhereClause=None, 
                        parameters=None, facility_ids=None):
        """
        Create the dataset results sql query
        @param whereClause use this to filter datarecords in the inner query
        @param metaWhereClause: use this to filter over the entire resultset 
        """
        if not whereClause:
            whereClause = []
        if not metaWhereClause:
            metaWhereClause = []
        if not parameters:
            parameters = []
        
        logger.debug('whereClause: %r, metaWhereClause: %r, parameters: %s' 
            % (whereClause,metaWhereClause, parameters))
    
        datacolumns = ( 
            DataColumn.objects.filter(dataset=self.dataset)
                .order_by('display_order') )
        
        reagent_name_query_string = (
            ', (SELECT '
            'r.name '
            'FROM db_reagent r '
            'JOIN db_reagentbatch rb on rb.reagent_id=r.id '
            'JOIN db_datapoint {alias} on rb.id={alias}.reagent_batch_id '
            'WHERE {alias}.datarecord_id=dr_id '
            'AND {alias}.datacolumn_id={dc_id} ) as "{column_name}" '
            )
        col_query_string = (
            ", (SELECT "
            "{column_to_select} "
            "FROM db_datapoint as {alias} "
            "WHERE {alias}.datacolumn_id={dc_id} "
            'AND {alias}.datarecord_id=dr_id ) as "{column_name}" '
            )
        query_string = "SELECT dr_id as datarecord_id "
        reagent_key_columns = []
        for i,dc in enumerate(datacolumns):
            alias = "dp"+str(i)
            column_name = dc.name
            column_to_select = None
            if(dc.data_type == 'Numeric' or dc.data_type == 'omero_image'):
                if dc.precision == 0 or dc.data_type == 'omero_image':
                    column_to_select = "int_value"
                else:
                    column_to_select = "round( float_value::numeric, %s )" 
                    parameters.append(str(dc.precision))
                query_string += col_query_string.format( 
                    column_to_select=column_to_select, alias=alias,
                    column_name=column_name,dc_id=dc.id )
            elif dc.data_type in ['small_molecule','cell','protein','antibody','other_reagent']:
                column_to_select = "text_value"
                reagent_key_columns.append(column_name)
                query_string += col_query_string.format( 
                    column_to_select=column_to_select, alias=alias,
                    column_name=column_name,dc_id=dc.id )
                query_string += reagent_name_query_string.format(alias=alias,
                    column_name=column_name+'_name',dc_id=dc.id)
            else:
                column_to_select = "text_value"

                query_string += col_query_string.format( 
                    column_to_select=column_to_select, alias=alias,
                    column_name=column_name,dc_id=dc.id )
        query_string += ", plate, well, control_type "
        query_string += (" FROM  ( SELECT dr.id as dr_id "
                            " ,plate, well, control_type " )
        fromClause = " FROM db_datarecord dr " 
        fromClause += " WHERE dr.dataset_id = " + str(self.dataset.id)
        query_string += fromClause

        countQueryString = "SELECT count(*) " + fromClause
        
        inner_alias = 'x'
        query_string += " order by dr.id ) as " + inner_alias 
        logger.debug('whereClause: %s' % whereClause)      
        query_string += ' WHERE 1=1 '
        if facility_ids:
            reagent_clauses = []
            for col in reagent_key_columns:
                for id in facility_ids:
                    reagent_clauses.append(' "{key_col}" ~ %s '.format(key_col=col))
                    parameters.append(id)
            metaWhereClause.append(' OR '.join(reagent_clauses))
        if whereClause:
            query_string = (" AND "+inner_alias+".").join([query_string]+whereClause) # extra filters
            countQueryString = " AND dr.".join([countQueryString]+whereClause) # extra filters
        
        if metaWhereClause:
            fromClause = " FROM ( " + query_string + ") a  where " + (" AND ".join(metaWhereClause))
            query_string = "SELECT * " + fromClause
            countQueryString = "SELECT count(*) " + fromClause
       
        logger.debug('query_string: %r, countQueryString: %r, parameters: %s' 
            % (query_string, countQueryString, parameters) )
        dataset_info = self.DatasetInfo()
        dataset_info.query_sql = query_string
        dataset_info.count_query_sql = countQueryString
        dataset_info.datacolumns = datacolumns
        dataset_info.parameters = parameters
        return dataset_info
      
    def has_plate_wells_defined(self):
        return DataRecord.objects.all().filter(dataset_id=self.dataset_id)\
            .filter(plate__isnull=False).filter(well__isnull=False).exists()

    def has_control_type_defined(self):
        return DataRecord.objects.all().filter(dataset_id=self.dataset_id)\
            .filter(control_type__isnull=False).exists()


class SiteSearchManager2(models.Manager):

    def search(self, queryString, is_authenticated=False):
        
        logger.info('searching %r' % queryString)
            
        queryStringProcessed = format_search(queryString)
        cursor = connection.cursor()
        # Notes: MaxFragments=10 turns on fragment based headlines (context for
        # search matches), with MaxWords=20
        # ts_rank_cd(search_vector, query, 32): Normalization option 32 
        # (rank/(rank+1)) can be applied to scale all 
        # ranks into the range zero to one, but of course this is just a 
        # cosmetic change; will not affect the ordering of the search results.

        REAGENT_SEARCH_SQL = \
'''
SELECT
  id, {key_id}::text,
  ts_headline({snippet_def} || {reagent_snippet_def}, {query_number}, 'MaxFragments=10, MinWords=1, MaxWords=20, 
              FragmentDelimiter=" | "') as snippet,
  ( ts_rank_cd({table_name}.search_vector, {query_number}, 32) 
      + ts_rank_cd(db_reagent.search_vector, {query_number}, 32) ) AS rank,
  '{detail_type}' as type 
FROM  {table_name} join db_reagent on(reagent_ptr_id=db_reagent.id), to_tsquery(%s) as {query_number}
WHERE {table_name}.search_vector @@ {query_number} 
or db_reagent.search_vector @@ {query_number}
'''
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
        sql = REAGENT_SEARCH_SQL.format(
            key_id='facility_id',
            reagent_snippet_def=Reagent.get_snippet_def(),
            snippet_def=Cell.get_snippet_def(),
            detail_type='cell_detail',
            table_name='db_cell',
            query_number='query1')
        if(not is_authenticated): 
            sql += RESTRICTION_SQL
        sql += " UNION "
        sql += REAGENT_SEARCH_SQL.format(
            key_id= "facility_id || '-' || salt_id" ,
            reagent_snippet_def=Reagent.get_snippet_def(),
            snippet_def=SmallMolecule.get_snippet_def(),
            detail_type='sm_detail',
            table_name='db_smallmolecule',
            query_number='query2')
        if(not is_authenticated): 
            sql += RESTRICTION_SQL
        sql += " UNION "
        sql += SEARCH_SQL.format(
            key_id='facility_id',
            snippet_def=DataSet.get_snippet_def(),
            detail_type='dataset_detail',
            table_name='db_dataset',
            query_number='query3')
        if(not is_authenticated): 
            sql += RESTRICTION_SQL
        sql += " UNION "
        sql += REAGENT_SEARCH_SQL.format(
            key_id='lincs_id',
            reagent_snippet_def=Reagent.get_snippet_def(),
            snippet_def=Protein.get_snippet_def(),
            detail_type='protein_detail',
            table_name='db_protein',
            query_number='query4')
        if(not is_authenticated): 
            sql += RESTRICTION_SQL
        sql += " UNION "
        sql += REAGENT_SEARCH_SQL.format(
            key_id='facility_id',
            reagent_snippet_def=Reagent.get_snippet_def(),
            snippet_def=Antibody.get_snippet_def(),
            detail_type='antibody_detail',
            table_name='db_antibody',
            query_number='query5')
        if(not is_authenticated): 
            sql += RESTRICTION_SQL
        sql += " UNION "
        sql += REAGENT_SEARCH_SQL.format(
            key_id='facility_id',
            reagent_snippet_def=Reagent.get_snippet_def(),
            snippet_def=OtherReagent.get_snippet_def(),
            detail_type='otherreagent_detail',
            table_name='db_otherreagent',
            query_number='query6')
        if(not is_authenticated): 
            sql += RESTRICTION_SQL
        sql += " ORDER by type, rank DESC;"
        logger.info('search query: %r' % sql)
        cursor.execute(sql , 
                       [queryStringProcessed,queryStringProcessed,
                        queryStringProcessed,queryStringProcessed,
                        queryStringProcessed,queryStringProcessed])
        _data = dictfetchall(cursor)

        # perform (largely redundant) queries using the specific managers:
        # - to execute any specific search logic implemented in each manager
        # (e.g. batch fields)
        def add_specific_search_matches(specific_search_match_query,type):
            if len(specific_search_match_query) > 0:
                for obj in specific_search_match_query:
                    skip = False
                    for x in _data:
                        if x['facility_id'] == obj.facility_id: 
                            skip=True
                    if not skip:
                        _data.append(
                            {'id':obj.id,'facility_id':obj.facility_id, 
                             'snippet': obj.snippet,
                             'type':type, 'rank':1})
        
        smqs = SmallMoleculeSearchManager().search(
            SmallMolecule.objects.all(), queryString, 
            is_authenticated=is_authenticated);
        add_specific_search_matches(smqs,'sm_detail')
        cqs = CellSearchManager().search(
            queryString, is_authenticated=is_authenticated);
        add_specific_search_matches(cqs,'cell_detail')
        pqs = ProteinSearchManager().search(
            queryString, is_authenticated=is_authenticated)
        add_specific_search_matches(pqs,'protein_detail')
        aqs = AntibodySearchManager().search(
            queryString, is_authenticated=is_authenticated)
        add_specific_search_matches(aqs,'antibody_detail')
        oqs = OtherReagentSearchManager().search(
            queryString, is_authenticated=is_authenticated)
        add_specific_search_matches(oqs,'otherreagent_detail')

        return _data
