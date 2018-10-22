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
import django_tables2.columns.linkcolumn
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
    Protein, DataSet, DatasetProperty, Library, FieldInformation, AttachedFile,\
    DataRecord, DataColumn, get_detail, Antibody, OtherReagent, CellBatch, \
    PrimaryCell, PrimaryCellBatch, QCEvent, \
    QCAttachedFile, AntibodyBatch, Reagent, ReagentBatch, get_listing,\
    ProteinBatch, OtherReagentBatch, DiffCell, DiffCellBatch,\
    Ipsc, IpscBatch, EsCell, EsCellBatch, Unclassified, UnclassifiedBatch
from django_tables2.utils import AttributeDict
from tempfile import SpooledTemporaryFile
from db.api import DataSetResource2, _get_raw_time_string


logger = logging.getLogger(__name__)

APPNAME = 'db',
COMPOUND_IMAGE_LOCATION = "compound-images-by-facility-salt-id"  
AMBIT_COMPOUND_IMAGE_LOCATION = "ambit-study-compound-images-by-facility-salt-id"  
DATASET_IMAGE_LOCATION = "dataset-images-by-facility-id" 
RRID_LINK_TEMPLATE = 'http://antibodyregistry.org/search.php?q={value}'

OMERO_IMAGE_COLUMN_TYPE = 'omero_image'
DAYS_TO_CACHE = 1
DAYS_TO_CACHE_PUBCHEM_ERRORS = 1

FACILITY_BATCH_PATTERN = re.compile(r'^(HMSL)?(\d+)(-(\d+))?$',re.IGNORECASE)

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
        col_key_name_map = get_table_col_key_name_map(
            table,fieldinformation_tables=['cell',''],
            extra_columns=[
                'precursor_cell_name','precursor_cell_facility_batch_id'])
        return send_to_file(
            outputType, 'cells', queryset, col_key_name_map)
    return render_list_index(request, table,search,'Cell Line','Cell Lines',
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
        details['type_title'] = 'Cell Line'
        
        if cell.precursor:
            details['object']['precursor_cell_name']['value'] = \
                'HMSL%s-%s: %s' % (cell.precursor.reagent.facility_id, 
                    cell.precursor.batch_id, cell.precursor.reagent.name)
            details['object']['precursor_cell_name']['link'] = (
                '/db/cells/%s-%s#batchinfo' 
                % (cell.precursor.reagent.facility_id,cell.precursor.batch_id) )
        
        details['facility_id'] = cell.facility_id
        cell_batch = None
        if(_batch_id):
            cell_batch = CellBatch.objects.get( 
                reagent=cell, batch_id=_batch_id) 

        # batch table
        if not cell_batch:
            batches = ( CellBatch.objects
                .filter(reagent=cell, batch_id__gt=0)
                .order_by('batch_id') )
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

        return render(request, 'db/cellDetail.html', details)
    except Cell.DoesNotExist:
        raise Http404


def primaryCellIndex(request):
    search = request.GET.get('search','')
    logger.debug(str(("is_authenticated:", 
        request.user.is_authenticated(), 'search: ', search)))
    search = re.sub(r'[\'"]','',search)
 
    if(search != ''):
        queryset = PrimaryCellSearchManager().search(search, 
            is_authenticated=request.user.is_authenticated())      
    else:
        queryset = PrimaryCell.objects.order_by('facility_id')
        if not request.user.is_authenticated(): 
            queryset = queryset.exclude(is_restricted=True)
 
    # PROCESS THE EXTRA FORM    
    field_hash=FieldInformation.manager.get_field_hash('primarycell')
    
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
            queryset = PrimaryCellSearchManager().join_query_to_dataset_type(
                queryset, dataset_type=field_data)
            if field_data:
                search_label += \
                    "Filtered for " + fieldinformation.get_verbose_name() + ": " + field_data
            visible_field_overrides.append(key)
            form.data[key+'_shown'] = True
    else:
        logger.info(str(('invalid form', form.errors)))

    table = PrimaryCellTable(queryset, visible_field_overrides=visible_field_overrides)

    RequestConfig(request, paginate={"per_page": 25}).configure(table)
    outputType = request.GET.get('output_type','')
    if(outputType != ''):

        col_key_name_map = get_table_col_key_name_map(
            table,fieldinformation_tables=['primarycell',''],
            extra_columns=[
                'precursor_cell_name','precursor_cell_facility_batch_id'])
        return send_to_file(
            outputType, 'primary_cells', queryset, col_key_name_map)
        
    return render_list_index(request, table,search,'Primary Cell','Primary Cells',
        **{ 'extra_form': form, 'search_label': search_label })

def primaryCellDetail(request, facility_batch, batch_id=None):
    try:
        _batch_id = None
        if not batch_id:
            temp = facility_batch.split('-') 
            _facility_id = temp[0]
            if len(temp) > 1:
                _batch_id = temp[1]
        else:
            _facility_id = facility_batch
            _batch_id = batch_id        
        
        cell = PrimaryCell.objects.get(facility_id=_facility_id) 
        if(cell.is_restricted and not request.user.is_authenticated()):
            return HttpResponse('Log in required.', status=401)
        details = {'object': get_detail(cell, ['primarycell',''])}
        details['type_title'] = 'Primary Cell'
        
        if cell.precursor:
            details['object']['precursor_cell_name']['value'] = \
                'HMSL%s-%s: %s' % (cell.precursor.reagent.facility_id, 
                    cell.precursor.batch_id, cell.precursor.reagent.name)
            details['object']['precursor_cell_name']['link'] = (
                '/db/primarycells/%s-%s#batchinfo' 
                % (cell.precursor.reagent.facility_id,cell.precursor.batch_id) )

        details['facility_id'] = cell.facility_id
        
        cell_batch = None
        if(_batch_id):
            cell_batch = PrimaryCellBatch.objects.get( 
                reagent=cell, batch_id=_batch_id) 

        # batch table
        if not cell_batch:
            batches = ( PrimaryCellBatch.objects
                .filter(reagent=cell, batch_id__gt=0)
                .order_by('batch_id') )
            if batches.exists():
                details['batchTable']=PrimaryCellBatchTable(batches)
        else:
            details['cell_batch']= get_detail(
                cell_batch,['primarycellbatch',''])
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
                
        datasets = DataSet.objects.filter(primary_cells__reagent=cell).distinct()
        if(datasets.exists()):
            where = []
            if(not request.user.is_authenticated()): 
                where.append("(not is_restricted or is_restricted is NULL)")
            queryset = datasets.extra(
                    where=where,
                    order_by=('facility_id',))        
            details['datasets'] = DataSetTable(queryset)

        return render(request, 'db/cellDetail.html', details)
    except PrimaryCell.DoesNotExist:
        raise Http404

def ipscIndex(request):
    search = request.GET.get('search','')
    logger.debug(str(("is_authenticated:", 
        request.user.is_authenticated(), 'search: ', search)))
    search = re.sub(r'[\'"]','',search)
 
    if(search != ''):
        queryset = IpscSearchManager().search(search, 
            is_authenticated=request.user.is_authenticated())      
    else:
        queryset = Ipsc.objects.order_by('facility_id')
        if not request.user.is_authenticated(): 
            queryset = queryset.exclude(is_restricted=True)
 
    # PROCESS THE EXTRA FORM    
    field_hash=FieldInformation.manager.get_field_hash('ipsc')
    
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
            queryset = IpscSearchManager().join_query_to_dataset_type(
                queryset, dataset_type=field_data)
            if field_data:
                search_label += \
                    "Filtered for " + fieldinformation.get_verbose_name() + ": " + field_data
            visible_field_overrides.append(key)
            form.data[key+'_shown'] = True
    else:
        logger.info(str(('invalid form', form.errors)))

    table = IpscTable(queryset, visible_field_overrides=visible_field_overrides)

    RequestConfig(request, paginate={"per_page": 25}).configure(table)
    outputType = request.GET.get('output_type','')
    if(outputType != ''):

        col_key_name_map = get_table_col_key_name_map(
            table,fieldinformation_tables=['ipsc',''],
            extra_columns=[
                'precursor_cell_name','precursor_cell_facility_batch_id'])
        return send_to_file(
            outputType, 'ipscs', queryset, col_key_name_map)
        
    return render_list_index(request, table,search,'iPSC','iPSCs',
        **{ 'extra_form': form, 'search_label': search_label })

def ipscDetail(request, facility_batch, batch_id=None):
    try:
        _batch_id = None
        if not batch_id:
            temp = facility_batch.split('-') 
            _facility_id = temp[0]
            if len(temp) > 1:
                _batch_id = temp[1]
        else:
            _facility_id = facility_batch
            _batch_id = batch_id        
        
        cell = Ipsc.objects.get(facility_id=_facility_id) 
        if(cell.is_restricted and not request.user.is_authenticated()):
            return HttpResponse('Log in required.', status=401)
        details = {'object': get_detail(cell, ['ipsc',''])}
        details['type_title'] = 'iPSC'
        
        if cell.precursor:
            details['object']['precursor_cell_name']['value'] = \
                'HMSL%s-%s: %s' % (cell.precursor.reagent.facility_id, 
                    cell.precursor.batch_id, cell.precursor.reagent.name)
            details['object']['precursor_cell_name']['link'] = (
                '/db/primarycells/%s-%s#batchinfo' 
                % (cell.precursor.reagent.facility_id,cell.precursor.batch_id) )

        details['facility_id'] = cell.facility_id
        
        cell_batch = None
        if(_batch_id):
            cell_batch = IpscBatch.objects.get( 
                reagent=cell, batch_id=_batch_id) 

        # batch table
        if not cell_batch:
            batches = ( IpscBatch.objects
                .filter(reagent=cell, batch_id__gt=0)
                .order_by('batch_id') )
            if batches.exists():
                details['batchTable'] = IpscBatchTable(batches)
        else:
            details['cell_batch']= get_detail(
                cell_batch,['ipscbatch',''])
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
                
        datasets = DataSet.objects.filter(ipscs__reagent=cell).distinct()
        if(datasets.exists()):
            where = []
            if(not request.user.is_authenticated()): 
                where.append("(not is_restricted or is_restricted is NULL)")
            queryset = datasets.extra(
                    where=where,
                    order_by=('facility_id',))        
            details['datasets'] = DataSetTable(queryset)

        return render(request, 'db/cellDetail.html', details)
    except Ipsc.DoesNotExist:
        raise Http404
 
def esCellIndex(request):
    search = request.GET.get('search','')
    logger.debug(str(("is_authenticated:", 
        request.user.is_authenticated(), 'search: ', search)))
    search = re.sub(r'[\'"]','',search)
 
    if(search != ''):
        queryset = EsCellSearchManager().search(search, 
            is_authenticated=request.user.is_authenticated())      
    else:
        queryset = EsCell.objects.order_by('facility_id')
        if not request.user.is_authenticated(): 
            queryset = queryset.exclude(is_restricted=True)
 
    # PROCESS THE EXTRA FORM    
    field_hash=FieldInformation.manager.get_field_hash('escell')
    
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
            queryset = EsCellSearchManager().join_query_to_dataset_type(
                queryset, dataset_type=field_data)
            if field_data:
                search_label += \
                    "Filtered for " + fieldinformation.get_verbose_name() + ": " + field_data
            visible_field_overrides.append(key)
            form.data[key+'_shown'] = True
    else:
        logger.info(str(('invalid form', form.errors)))

    table = EsCellTable(queryset, visible_field_overrides=visible_field_overrides)

    RequestConfig(request, paginate={"per_page": 25}).configure(table)
    outputType = request.GET.get('output_type','')
    if(outputType != ''):

        col_key_name_map = get_table_col_key_name_map(
            table,fieldinformation_tables=['escell',''],
            extra_columns=[
                'precursor_cell_name','precursor_cell_facility_batch_id'])
        return send_to_file(
            outputType, 'es_cells', queryset, col_key_name_map)
        
    return render_list_index(request, table,search,'Embryonic Stem Cell','Embryonic Stem Cells',
        **{ 'extra_form': form, 'search_label': search_label })

def esCellDetail(request, facility_batch, batch_id=None):
    try:
        _batch_id = None
        if not batch_id:
            temp = facility_batch.split('-') 
            _facility_id = temp[0]
            if len(temp) > 1:
                _batch_id = temp[1]
        else:
            _facility_id = facility_batch
            _batch_id = batch_id        
        
        cell = EsCell.objects.get(facility_id=_facility_id) 
        if(cell.is_restricted and not request.user.is_authenticated()):
            return HttpResponse('Log in required.', status=401)
        details = {'object': get_detail(cell, ['escell',''])}
        details['type_title'] = 'Embryonic Stem Cell'
        
        if cell.precursor:
            details['object']['precursor_cell_name']['value'] = \
                'HMSL%s-%s: %s' % (cell.precursor.reagent.facility_id, 
                    cell.precursor.batch_id, cell.precursor.reagent.name)
            details['object']['precursor_cell_name']['link'] = (
                '/db/primarycells/%s-%s#batchinfo' 
                % (cell.precursor.reagent.facility_id,cell.precursor.batch_id) )

        details['facility_id'] = cell.facility_id
        
        cell_batch = None
        if(_batch_id):
            cell_batch = EsCellBatch.objects.get( 
                reagent=cell, batch_id=_batch_id) 

        # batch table
        if not cell_batch:
            batches = ( EsCellBatch.objects
                .filter(reagent=cell, batch_id__gt=0)
                .order_by('batch_id') )
            if batches.exists():
                details['batchTable'] = EsCellBatchTable(batches)
        else:
            details['cell_batch']= get_detail(
                cell_batch,['escellbatch',''])
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
                
        datasets = DataSet.objects.filter(es_cells__reagent=cell).distinct()
        if(datasets.exists()):
            where = []
            if(not request.user.is_authenticated()): 
                where.append("(not is_restricted or is_restricted is NULL)")
            queryset = datasets.extra(
                    where=where,
                    order_by=('facility_id',))        
            details['datasets'] = DataSetTable(queryset)

        return render(request, 'db/cellDetail.html', details)
    except EsCell.DoesNotExist:
        raise Http404
 
def diffCellIndex(request):
    search = request.GET.get('search','')
    logger.debug(str(("is_authenticated:", 
        request.user.is_authenticated(), 'search: ', search)))
    search = re.sub(r'[\'"]','',search)
 
    if(search != ''):
        queryset = DiffCellSearchManager().search(search, 
            is_authenticated=request.user.is_authenticated())      
    else:
        queryset = DiffCell.objects.order_by('facility_id')
        if not request.user.is_authenticated(): 
            queryset = queryset.exclude(is_restricted=True)
 
    # PROCESS THE EXTRA FORM    
    field_hash=FieldInformation.manager.get_field_hash('diffcell')
    
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
            queryset = DiffCellSearchManager().join_query_to_dataset_type(
                queryset, dataset_type=field_data)
            if field_data:
                search_label += \
                    "Filtered for " + fieldinformation.get_verbose_name() + ": " + field_data
            visible_field_overrides.append(key)
            form.data[key+'_shown'] = True
    else:
        logger.info(str(('invalid form', form.errors)))

    table = DiffCellTable(queryset, visible_field_overrides=visible_field_overrides)

    RequestConfig(request, paginate={"per_page": 25}).configure(table)
    outputType = request.GET.get('output_type','')
    if(outputType != ''):

        col_key_name_map = get_table_col_key_name_map(
            table,fieldinformation_tables=['diffcell',''],
            extra_columns=[
                'precursor_cell_name','precursor_cell_facility_batch_id'])
        return send_to_file(
            outputType, 'diff_cells', queryset, col_key_name_map)
        
    return render_list_index(request, table,search,'Differentiated Cell','Differentiated Cells',
        **{ 'extra_form': form, 'search_label': search_label })

def diffCellDetail(request, facility_batch, batch_id=None):
    try:
        _batch_id = None
        if not batch_id:
            temp = facility_batch.split('-') 
            _facility_id = temp[0]
            if len(temp) > 1:
                _batch_id = temp[1]
        else:
            _facility_id = facility_batch
            _batch_id = batch_id        
        
        cell = DiffCell.objects.get(facility_id=_facility_id) 
        if(cell.is_restricted and not request.user.is_authenticated()):
            return HttpResponse('Log in required.', status=401)
        details = {'object': get_detail(cell, ['diffcell',''])}
        details['type_title'] = 'Differentiated Cell'
        
        if cell.precursor:
            details['object']['precursor_cell_name']['value'] = \
                'HMSL%s-%s: %s' % (cell.precursor.reagent.facility_id, 
                    cell.precursor.batch_id, cell.precursor.reagent.name)
            details['object']['precursor_cell_name']['link'] = (
                '/db/ipscs/%s-%s#batchinfo' 
                % (cell.precursor.reagent.facility_id,cell.precursor.batch_id) )

        details['facility_id'] = cell.facility_id
        
        cell_batch = None
        if(_batch_id):
            cell_batch = DiffCellBatch.objects.get( 
                reagent=cell, batch_id=_batch_id) 

        # batch table
        if not cell_batch:
            batches = ( DiffCellBatch.objects
                .filter(reagent=cell, batch_id__gt=0)
                .order_by('batch_id') )
            if batches.exists():
                details['batchTable']=DiffCellBatchTable(batches)
        else:
            details['cell_batch']= get_detail(
                cell_batch,['diffcellbatch',''])
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
                
        datasets = DataSet.objects.filter(diff_cells__reagent=cell).distinct()
        if(datasets.exists()):
            where = []
            if(not request.user.is_authenticated()): 
                where.append("(not is_restricted or is_restricted is NULL)")
            queryset = datasets.extra(
                    where=where,
                    order_by=('facility_id',))        
            details['datasets'] = DataSetTable(queryset)

        return render(request, 'db/cellDetail.html', details)
    except DiffCell.DoesNotExist:
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
        col_key_name_map = get_table_col_key_name_map(
            table,fieldinformation_tables=['protein',''])
        return send_to_file(
            outputType, 'proteins', queryset, col_key_name_map)

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
        col_key_name_map = get_table_col_key_name_map(
            table,fieldinformation_tables=['antibody',''],
            extra_columns=[
                'target_protein_center_ids_ui',
                'other_human_target_protein_center_ids_ui'] )
        return send_to_file(
            outputType, 'antibodies', queryset, col_key_name_map)

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
        
        if antibody.target_proteins.exists():
            details['object']['target_protein_names']['links'] = (
                [(i,'/db/proteins/%s' % x.facility_id, x.name) 
                    for i,x in enumerate(
                        antibody.target_proteins.all().order_by('facility_id'))])
            details['object']['target_protein_center_ids']['links'] = (
                [(i,'/db/proteins/%s' % x.facility_id, x.facility_id) 
                    for i,x in enumerate(
                        antibody.target_proteins.all().order_by('facility_id'))])

        if antibody.other_human_target_proteins.exists():
            details['object']['other_human_target_protein_center_ids']['links'] = (
                [(i,'/db/proteins/%s' % x.facility_id, x.facility_id) 
                    for i,x in enumerate(
                        antibody.other_human_target_proteins.all()
                            .order_by('facility_id'))])

        if antibody.rrid is not None:
            details['object']['rrid']['link'] = \
                RRID_LINK_TEMPLATE.format(value=antibody.rrid) 

        details['facility_id'] = antibody.facility_id
        antibody_batch = None
        if(_batch_id):
            antibody_batch = AntibodyBatch.objects.get(
                reagent=antibody,batch_id=_batch_id) 

        if not antibody_batch:
            batches = ( AntibodyBatch.objects
                .filter(reagent=antibody, batch_id__gt=0)
                .order_by('batch_id') )
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

        return render(request, 'db/antibodyDetail.html', details)
    except Antibody.DoesNotExist:
        raise Http404
     
def unclassifiedIndex(request):
    search = request.GET.get('search','')
    search = re.sub(r'[\'"]','',search)
    
    if(search != ''):
        queryset = UnclassifiedSearchManager().search(
            search, is_authenticated = request.user.is_authenticated())
    else:
        queryset = Unclassified.objects.order_by('facility_id')
        if not request.user.is_authenticated(): 
            queryset = queryset.exclude(is_restricted=True)
    
    table = UnclassifiedTable(queryset)
    outputType = request.GET.get('output_type','')
    if(outputType != ''):
        col_key_name_map = get_table_col_key_name_map(
            table,fieldinformation_tables=['unclassified',''],)
        return send_to_file(
            outputType, 'unclassified_perturbagens', queryset, col_key_name_map)
        
    RequestConfig(request, paginate={"per_page": 25}).configure(table)
    return render_list_index(request, table,search,'Unclassified Perturbagen',
        'Unclassified Perturbagens')
    
def unclassifiedDetail(request, facility_batch, batch_id=None):
    try:
        _batch_id = None
        if not batch_id:
            temp = facility_batch.split('-') 
            logger.info('find unclassified perturbagen for %s' % temp)
            _facility_id = temp[0]
            if len(temp) > 1:
                _batch_id = temp[1]
        else:
            _facility_id = facility_batch
            _batch_id = batch_id        
        
        up = Unclassified.objects.get(facility_id=_facility_id) 
        if(up.is_restricted and not request.user.is_authenticated()):
            return HttpResponse('Log in required.', status=401)
        details = {'object': get_detail(up, ['unclassified',''])}
        
        details['facility_id'] = up.facility_id
        up_batch = None
        if(_batch_id):
            up_batch = UnclassifiedBatch.objects.get(
                reagent=up,batch_id=_batch_id) 

        if not up_batch:
            batches = ( UnclassifiedBatch.objects
                .filter(reagent=up, batch_id__gt=0)
                .order_by('batch_id') )
            if batches.exists():
                details['batchTable']=UnclassifiedBatchTable(batches)
        else:
            details['unclassified_batch']= get_detail(
                up_batch,['unclassifiedbatch',''])
            details['facility_batch'] = ( '%s-%s' 
                % (up.facility_id,up_batch.batch_id) ) 

            qcEvents = QCEvent.objects.filter(
                facility_id_for=up.facility_id,
                batch_id_for=up_batch.batch_id).order_by('-date')
            if qcEvents:
                details['qcTable'] = QCEventTable(qcEvents)
            
            if(not up.is_restricted or request.user.is_authenticated()):
                attachedFiles = get_attached_files(
                    up.facility_id,batch_id=up_batch.batch_id)
                if(len(attachedFiles)>0):
                    details['attached_files_batch'] = AttachedFileTable(attachedFiles)        
                
        datasets = DataSet.objects.filter(
            unclassified_perturbagens__reagent=up).distinct()
        if(datasets.exists()):
            where = []
            if(not request.user.is_authenticated()): 
                where.append("(not is_restricted or is_restricted is NULL)")
            queryset = datasets.extra(
                    where=where,
                    order_by=('facility_id',))        
            details['datasets'] = DataSetTable(queryset)

        return render(request, 'db/unclassifiedDetail.html', details)
    except Unclassified.DoesNotExist:
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
        col_key_name_map = get_table_col_key_name_map(
            table,fieldinformation_tables=['otherreagent',''],)
        return send_to_file(
            outputType, 'other_reagents', queryset, col_key_name_map)
        
    RequestConfig(request, paginate={"per_page": 25}).configure(table)
    return render_list_index(request, table,search,'Other Reagent','Other Reagents')
    
def otherReagentDetail(request, facility_batch, batch_id=None):
    try:
        _batch_id = None
        if not batch_id:
            temp = facility_batch.split('-') 
            logger.info('find other reagent for %s' % temp)
            _facility_id = temp[0]
            if len(temp) > 1:
                _batch_id = temp[1]
        else:
            _facility_id = facility_batch
            _batch_id = batch_id        
        
        other_reagent = OtherReagent.objects.get(facility_id=_facility_id) 
        if(other_reagent.is_restricted and not request.user.is_authenticated()):
            return HttpResponse('Log in required.', status=401)
        details = {'object': get_detail(other_reagent, ['otherreagent',''])}
        
        details['facility_id'] = other_reagent.facility_id
        other_reagent_batch = None
        if(_batch_id):
            other_reagent_batch = OtherReagentBatch.objects.get(
                reagent=other_reagent,batch_id=_batch_id) 

        if not other_reagent_batch:
            batches = ( OtherReagentBatch.objects
                .filter(reagent=other_reagent, batch_id__gt=0)
                .order_by('batch_id') )
            if batches.exists():
                details['batchTable']=OtherReagentBatchTable(batches)
        else:
            details['other_reagent_batch']= get_detail(
                other_reagent_batch,['otherreagentbatch',''])
            details['facility_batch'] = ( '%s-%s' 
                % (other_reagent.facility_id,other_reagent_batch.batch_id) ) 

            qcEvents = QCEvent.objects.filter(
                facility_id_for=other_reagent.facility_id,
                batch_id_for=other_reagent_batch.batch_id).order_by('-date')
            if qcEvents:
                details['qcTable'] = QCEventTable(qcEvents)
            
            if(not other_reagent.is_restricted or request.user.is_authenticated()):
                attachedFiles = get_attached_files(
                    other_reagent.facility_id,batch_id=other_reagent_batch.batch_id)
                if(len(attachedFiles)>0):
                    details['attached_files_batch'] = AttachedFileTable(attachedFiles)        
                
        datasets = DataSet.objects.filter(other_reagents__reagent=other_reagent).distinct()
        if(datasets.exists()):
            where = []
            if(not request.user.is_authenticated()): 
                where.append("(not is_restricted or is_restricted is NULL)")
            queryset = datasets.extra(
                    where=where,
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
    queryset = queryset.extra(
        select={'lincs_id_null':'lincs_id is null',
            'pubchem_cid_null':'pubchem_cid is null' })
    
    outputType = request.GET.get('output_type','')
    if not outputType and overrides and 'table' in overrides:
        tablename = overrides['table_name']
        table = overrides['table'](
            queryset, visible_field_overrides=visible_field_overrides)
    else:
        tablename = 'smallmolecule'
        table = SmallMoleculeTable(
            queryset, visible_field_overrides=visible_field_overrides)
    
    if outputType:
        if(outputType == ".zip"):
            return export_sm_images(queryset, request.user.is_authenticated())

        col_key_name_map = get_table_col_key_name_map(
            table,fieldinformation_tables=[tablename,''])
        return send_to_file(
            outputType, 'small_molecule', queryset, col_key_name_map,
            is_authenticated=request.user.is_authenticated())
        
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
            extra_properties=['_molecular_mass','_inchi', '_inchi_key', '_smiles', 
                '_relevant_citations']
        details = {'object': get_detail(
            sm, ['smallmolecule',''],extra_properties=extra_properties )}
        details['facility_salt_id'] = sm.facility_id + '-' + sm.salt_id
        
        # change the facility ID if it is a salt, for the purpose of display
        if int(sm.facility_id) < 1000:
            details['object']['facility_salt']['value'] = sm.facility_id
        
        #TODO: set is_restricted if the user is not logged in only
        details['is_restricted'] = sm.is_restricted
        
        if(not sm.is_restricted or request.user.is_authenticated()):
            attachedFiles = get_attached_files(sm.facility_id,sm.salt_id)
            if(len(attachedFiles)>0):
                details['attached_files'] = AttachedFileTable(attachedFiles)
            
        # batch table
        if not smb:
            batches = ( SmallMoleculeBatch.objects
                .filter(reagent=sm,batch_id__gt=0)
                .order_by('batch_id') )
            if batches.exists():
                details['batchTable']=SmallMoleculeBatchTable(batches)
        else:
            extra_properties = []
            if(not sm.is_restricted or request.user.is_authenticated()):
                extra_properties=['get_salt_id', 'get_molecular_weight','_molecular_formula',
                    '_chemical_synthesis_reference','_purity','_purity_method']
            details['smallmolecule_batch']= get_detail(
                smb,['smallmoleculebatch',''], extra_properties=extra_properties)
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
        
        # Target Affinity Spectrum data
        try:
            dataset = DataSet.objects.get(facility_id='20000')

            sql =  '''
                select
                classmin,
                array_to_string(array_agg(gene),', ') as genes
                from (
                select 
                dp2.int_value as classmin,
                dp1.text_value as gene
                from 
                (select dp.datarecord_id 
                    from db_datapoint dp
                    join db_datacolumn dc on(dp.datacolumn_id=dc.id) 
                    join db_dataset ds on (dp.dataset_id = ds.id) 
                    where ds.facility_id = '20000'
                    and dc.name = 'hmsid'
                    and dp.text_value = '%s'
                ) as dr
                join db_datapoint dp1 on (dp1.datarecord_id = dr.datarecord_id)
                join db_datacolumn dc1 on (dp1.datacolumn_id = dc1.id)
                join db_datapoint dp2 on (dp2.datarecord_id = dr.datarecord_id)
                join db_datacolumn dc2 on (dp2.datacolumn_id = dc2.id)
                where dc1.name = 'approvedSymbol'
                and dc2.name = 'classmin'
                order by classmin, gene ) a
                group by classmin;                
                '''            
            
            cursor = connection.cursor()
            cursor.execute(sql % sm.facility_salt)
            v = dictfetchall(cursor)

            class TargetTable(PagedTable):
                classmin = tables.Column(
                    verbose_name='Target Affinity Spectrum Value')
                genes = DivWrappedColumn(
                    verbose_name="HUGO Gene Name",
                    classname='wide_width_column')
                class Meta:
                    orderable = True
                    attrs = {'class': 'paleblue'}
            
            details['target_affinity_table']=TargetTable(v)
            
        except DataSet.DoesNotExist:
            logger.warn('Target Affinity dataset does not exist')
        
        image_location = ( COMPOUND_IMAGE_LOCATION + '/HMSL%s-%s.png' 
            % (sm.facility_id,sm.salt_id) )
        if(can_access_image(image_location, sm.is_restricted)): 
            if not sm.is_restricted:
                image_location = static(image_location)
            elif request.user.is_authenticated:
                image_location = reverse('restricted_image', 
                    kwargs={ 'filepath': image_location } )
            details['image_location'] = image_location
        
        if(not sm.is_restricted 
            or ( sm.is_restricted and request.user.is_authenticated())):

            ambit_image_location = (AMBIT_COMPOUND_IMAGE_LOCATION + 
                '/HMSL%s-%s.png' % (sm.facility_id,sm.salt_id) )
            if(can_access_image(ambit_image_location, sm.is_restricted)): 
                details['ambit_image_location'] = ambit_image_location
        
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
        col_key_name_map = get_table_col_key_name_map(
            table,fieldinformation_tables=['library',''])
        return send_to_file(
            outputType, 'libraries', queryset, col_key_name_map)
        
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
            if(outputType != ''):
                col_key_name_map = get_table_col_key_name_map(
                    table, fieldinformation_tables=[
                        'library','smallmolecule',
                        'smallmoleculebatch','librarymapping',''])
                return send_to_file(
                    outputType, 'library_'+library.short_name, queryset, 
                    col_key_name_map)
        
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
        col_key_name_map = get_table_col_key_name_map(
            table, fieldinformation_tables=['dataset',''])
        return send_to_file(
            outputType, 'datasetIndex', queryset, col_key_name_map)
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
            queryset = dataset.cells.all()
            # create a combination dict of canonical and batch
            def make_cell(batch):
                d = model_to_dict(batch)
                d.update(model_to_dict(batch.reagent.cell))
                d['facility_batch'] = batch.facility_batch
                return d
            queryset = [make_cell(batch) for batch in queryset]
            col_key_name_map = get_col_key_mapping(
                queryset[0].keys(),
                fieldinformation_tables=['cell','cellbatch',''],
                sequence_override=['facility_batch'])
            return send_to_file(
                outputType, 'cells_for_'+ str(facility_id), 
                queryset, col_key_name_map )
        except DataSet.DoesNotExist:
            raise Http404
    try:
        details = datasetDetail2(request,facility_id, 'cells')
        details.setdefault('heading', 'Cells Studied')
        return render(request,'db/datasetDetailRelated.html', details)
    except Http401, e:
        return HttpResponse('Unauthorized', status=401)
    
def datasetDetailPrimaryCells(request, facility_id):
    outputType = request.GET.get('output_type','')
    if(outputType != ''):
        try:
            dataset = DataSet.objects.get(facility_id=facility_id)
            if(dataset.is_restricted and not request.user.is_authenticated()):
                raise Http401
            queryset = dataset.primary_cells.all()
            # create a combination dict of canonical and batch
            def make_primary_cell(batch):
                d = model_to_dict(batch)
                d.update(model_to_dict(batch.reagent.primarycell))
                d['facility_batch'] = batch.facility_batch
                return d
            queryset = [make_primary_cell(batch) for batch in queryset]
            col_key_name_map = get_col_key_mapping(
                queryset[0].keys(),
                fieldinformation_tables=['primarycell','primarycellbatch',''],
                sequence_override=['facility_batch'])
            return send_to_file(
                outputType, 'primary_cells_for_'+ str(facility_id), 
                queryset, col_key_name_map )
        except DataSet.DoesNotExist:
            raise Http404
    try:
        details = datasetDetail2(request,facility_id, 'primary_cells')
        details.setdefault('heading', 'Primary Cells Studied')
        return render(request,'db/datasetDetailRelated.html', details)
    except Http401, e:
        return HttpResponse('Unauthorized', status=401)
    
def datasetDetailIpscs(request, facility_id):
    outputType = request.GET.get('output_type','')
    if(outputType != ''):
        try:
            dataset = DataSet.objects.get(facility_id=facility_id)
            if(dataset.is_restricted and not request.user.is_authenticated()):
                raise Http401
            queryset = dataset.ipscs.all()
            # create a combination dict of canonical and batch
            def make_ipsc(batch):
                d = model_to_dict(batch)
                d.update(model_to_dict(batch.reagent.ipsc))
                d['facility_batch'] = batch.facility_batch
                return d
            queryset = [make_ipsc(batch) for batch in queryset]
            col_key_name_map = get_col_key_mapping(
                queryset[0].keys(),
                fieldinformation_tables=['ipsc','ipscbatch',''],
                sequence_override=['facility_batch'])
            return send_to_file(
                outputType, 'ipscs_for_'+ str(facility_id), 
                queryset, col_key_name_map )
        except DataSet.DoesNotExist:
            raise Http404
    try:
        details = datasetDetail2(request,facility_id, 'ipscs')
        details.setdefault('heading', 'iPSCs Studied')
        return render(request,'db/datasetDetailRelated.html', details)
    except Http401, e:
        return HttpResponse('Unauthorized', status=401)
    
def datasetDetailEsCells(request, facility_id):
    outputType = request.GET.get('output_type','')
    if(outputType != ''):
        try:
            dataset = DataSet.objects.get(facility_id=facility_id)
            if(dataset.is_restricted and not request.user.is_authenticated()):
                raise Http401
            queryset = dataset.es_cells.all()
            # create a combination dict of canonical and batch
            def make_es_cell(batch):
                d = model_to_dict(batch)
                d.update(model_to_dict(batch.reagent.escell))
                d['facility_batch'] = batch.facility_batch
                return d
            queryset = [make_es_cell(batch) for batch in queryset]
            col_key_name_map = get_col_key_mapping(
                queryset[0].keys(),
                fieldinformation_tables=['escell','escellbatch',''],
                sequence_override=['facility_batch'])
            return send_to_file(
                outputType, 'es_cells_for_'+ str(facility_id), 
                queryset, col_key_name_map )
        except DataSet.DoesNotExist:
            raise Http404
    try:
        details = datasetDetail2(request,facility_id, 'es_cells')
        details.setdefault('heading', 'Embryonic Stem Cells Studied')
        return render(request,'db/datasetDetailRelated.html', details)
    except Http401, e:
        return HttpResponse('Unauthorized', status=401)
    
def datasetDetailDiffCells(request, facility_id):
    outputType = request.GET.get('output_type','')
    if(outputType != ''):
        try:
            dataset = DataSet.objects.get(facility_id=facility_id)
            if(dataset.is_restricted and not request.user.is_authenticated()):
                raise Http401
            queryset = dataset.diff_cells.all()
            # create a combination dict of canonical and batch
            def make_diff_cell(batch):
                d = model_to_dict(batch)
                d.update(model_to_dict(batch.reagent.diffcell))
                d['facility_batch'] = batch.facility_batch
                return d
            queryset = [make_diff_cell(batch) for batch in queryset]
            col_key_name_map = get_col_key_mapping(
                queryset[0].keys(),
                fieldinformation_tables=['diffcell','diffcellbatch',''],
                sequence_override=['facility_batch'])
            return send_to_file(
                outputType, 'diff_cells_for_'+ str(facility_id), 
                queryset, col_key_name_map )
        except DataSet.DoesNotExist:
            raise Http404
    try:
        details = datasetDetail2(request,facility_id, 'diff_cells')
        details.setdefault('heading', 'Differentiated Cells Studied')
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
            col_key_name_map = get_table_col_key_name_map(
                ProteinTable(queryset),fieldinformation_tables=['protein',''])
            return send_to_file(
                outputType, 'proteins_for_'+ str(facility_id), 
                queryset, col_key_name_map )
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
            queryset = dataset.antibodies.all()
            # create a combination dict of canonical and batch
            def make_antibody(batch):
                d = model_to_dict(batch)
                d.update(model_to_dict(batch.reagent.antibody))
                d['facility_batch'] = batch.facility_batch
                return d
            queryset = [make_antibody(batch) for batch in queryset]
            col_key_name_map = get_col_key_mapping(
                queryset[0].keys(),
                fieldinformation_tables=['antibody','antibodybatch',''],
                extra_columns=[
                    'target_protein_center_ids_ui',
                    'other_human_target_protein_center_ids_ui'],
                sequence_override=['facility_batch'])
            return send_to_file(
                outputType, 'antibodies_for_'+ str(facility_id), 
                queryset, col_key_name_map )
        except DataSet.DoesNotExist:
            raise Http404
    try:
        details = datasetDetail2(request,facility_id,'antibodies')
        details.setdefault('heading', 'Antibodies Studied')
        return render(request,'db/datasetDetailRelated.html', details)
    except Http401, e:
        return HttpResponse('Unauthorized', status=401)
          
def datasetDetailUnclassified(request, facility_id):
    outputType = request.GET.get('output_type','')
    if(outputType != ''):
        try:
            dataset = DataSet.objects.get(facility_id=facility_id)
            if(dataset.is_restricted and not request.user.is_authenticated()):
                raise Http401
            queryset = dataset.unclassified_perturbagens.all()
            # create a combination dict of canonical and batch
            def make_up(batch):
                d = model_to_dict(batch)
                d.update(model_to_dict(batch.reagent.unclassified))
                d['facility_batch'] = batch.facility_batch
                return d
            queryset = [make_up(batch) for batch in queryset]
            col_key_name_map = get_col_key_mapping(
                queryset[0].keys(),
                fieldinformation_tables=['unclassified','unclassifiedbatch',''],
                sequence_override=['facility_batch'])
            return send_to_file(
                outputType, 'unclassified_perturbagens_for_'+ str(facility_id), 
                queryset, col_key_name_map )
        except DataSet.DoesNotExist:
            raise Http404
    try:
        details = datasetDetail2(request,facility_id,'unclassified')
        details.setdefault('heading', 'Unclassified Perturbagens Studied')
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
            queryset = dataset.other_reagents.all()
            # create a combination dict of canonical and batch
            def make_other_reagent(batch):
                d = model_to_dict(batch)
                d.update(model_to_dict(batch.reagent.otherreagent))
                d['facility_batch'] = batch.facility_batch
                return d
            queryset = [make_other_reagent(batch) for batch in queryset]
            col_key_name_map = get_col_key_mapping(
                queryset[0].keys(),
                fieldinformation_tables=['otherreagent','otherreagentbatch',''],
                sequence_override=['facility_batch'])
            return send_to_file(
                outputType, 'other_reagents_for_'+ str(facility_id), 
                queryset, col_key_name_map )
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
            queryset = dataset.small_molecules.all().order_by('reagent__facility_id','batch_id')
            if outputType == '.zip':
                filename = 'sm_images_for_dataset_' + str(dataset.facility_id)
                queryset = SmallMolecule.objects.filter(id__in=(
                    dataset.small_molecules.all()
                        .values_list('reagent_id',flat=True).distinct()))
                return export_sm_images(queryset, 
                                        request.user.is_authenticated(),
                                        output_filename=filename)
            else:
                # create a combination dict of canonical and batch
                def make_sm(batch):
                    d = model_to_dict(batch)
                    d.update(model_to_dict(
                        SmallMolecule.objects.get(pk=batch.reagent.id)))
                    d['facility_salt_batch'] = batch.facility_salt_batch
                    d['facility_id'] = batch.reagent.facility_id
                    for key,val in d.items():
                        if key[0]=='_' and d['is_restricted'] is True:
                            if request.user.is_authenticated() is not True:
                                d[key] = 'restricted'
                    return d
                queryset = [make_sm(batch) for batch in queryset]
                col_key_name_map = get_col_key_mapping(
                    queryset[0].keys(),
                    fieldinformation_tables=[
                        'smallmolecule','smallmoleculebatch',''],
                    sequence_override=['facility_salt_batch','facility_id'])
                return send_to_file(
                    outputType, 'small_molecules_for_'+ str(facility_id), 
                    queryset, col_key_name_map )

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
            col_key_name_map = get_table_col_key_name_map(
                DataColumnTable(queryset),fieldinformation_tables=['datacolumn',''])
            return send_to_file(
                outputType, 'datacolumns_for_'+ str(facility_id),
                queryset, col_key_name_map)
        except DataSet.DoesNotExist:
            raise Http404
    try:
        details = datasetDetail2(request,facility_id,'datacolumns')
        details.setdefault('heading', 'Data Columns')
        return render(request,'db/datasetDetailRelated.html', details)
    except Http401, e:
        return HttpResponse('Unauthorized', status=401)

def datasetDetailMetadata(request, facility_id):
    outputType = request.GET.get('output_type','')
    if(outputType != ''):
        try:
            dataset = DataSet.objects.get(facility_id=facility_id)
            if(dataset.is_restricted and not request.user.is_authenticated()):
                raise Http401
            queryset = dataset.properties.all().order_by('ordinal')
            output_data = []
            for prop in queryset:
                output_data.append({
                    'name': prop.name,
                    'value': prop.value })    
            col_key_name_map = {
                'name': 'name',
                'value': 'value'}
            return send_to_file(
                outputType, 'experimental_metadata_data_for_'+ str(facility_id),
                output_data, col_key_name_map)
        except DataSet.DoesNotExist:
            raise Http404
    try:
        details = datasetDetail2(request,facility_id,'metadata')
        details.setdefault('heading', 'Experimental Metadata')
        return render(request,'db/datasetDetailPropertiesJson.html', details)
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
        if hasattr(settings, 'QUALTRICS_SURVEY_ID'):
            details['QUALTRICS_SURVEY_ID'] = settings.QUALTRICS_SURVEY_ID
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
        if value == "cell_detail": return "Cell Line"
        elif value == "primary_cell_detail": return "Primary Cell"
        elif value == "diff_cell_detail": return "Differentiated Cell"
        elif value == "ipsc_detail": return "iPSC"
        elif value == "es_cell_detail": return "Embryonic Stem Cell"
        elif value == "sm_detail": return "Small Molecule"
        elif value == "dataset_detail": return "Dataset"
        elif value == "protein_detail": return "Protein"
        elif value == "antibody_detail": return "Antibody"
        elif value == "otherreagent_detail": return "Other Reagent"
        elif value == "unclassified_detail": return "Unclassified Perturbagen"
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

class TargetProteinLinkColumn(tables.Column):

    def render(self, value):
        # value is a list of protein hmsl ids
        temp = []
        for id in value:
            p = Protein.objects.get(facility_id=id)
            temp.append('<a href="/db/proteins/%s">%s</a>' % (id,p.name))
        return mark_safe(
            "<div class='constrained_width_column' >%s</div>" 
                % '; '.join(temp))
    
class ImageColumn(tables.Column):

    def __init__(self, loc=None, image_class=None, *args, **kwargs):
        self.loc=loc
        self.image_class=image_class
        super(ImageColumn, self).__init__(*args, orderable=False, **kwargs)
    
    def render(self, value):
        if value:
            location = static('%s/HMSL%s.png'% (self.loc, smart_str(value)))
            return mark_safe(
                '<img class="%s" src="%s" />' % (self.image_class, location) )
        else:
            return ''

class LinkTemplateColumn(django_tables2.columns.linkcolumn.BaseLinkColumn):
    
    def __init__(self, link_template=None, attrs=None, *args, **kwargs):
        self.link_template = link_template
        django_tables2.columns.linkcolumn.BaseLinkColumn.__init__(
            self, attrs=attrs, *args, **kwargs)
        
    def render(self, value):
        
        return self.render_link(self.link_template.format(value=value), value)
                        
class PagedTable(tables.Table):
    
    def __init__(self,*args,**kwargs):
        kwargs['template']="db/custom_tables2_template.html"
        kwargs['default'] = ''
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
   <a href="#" onclick='window.open("https://lincs-omero.hms.harvard.edu/webclient/img_detail/{{ record.%s }}", "_blank","height=700,width=800" )' ><img src='https://lincs-omero.hms.harvard.edu/webgateway/render_thumbnail/{{ record.%s }}/32/' alt='image if available' ></a>
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
        
    def __init__(self, table, *args, **kwargs):
        super(LibraryMappingTable, self).__init__(table)
        set_table_column_info(
            self, ['smallmolecule','smallmoleculebatch','librarymapping',''],
            sequence_override=['facility_salt_batch'])  
                
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
    
class BatchOrCanonicalLinkColumn(django_tables2.columns.linkcolumn.BaseLinkColumn):
    
    def __init__(self, viewname, *args, **kwargs):
        self.viewname = viewname
        super(BatchOrCanonicalLinkColumn, self).__init__(*args, **kwargs)
    
    def render(self, value, record, bound_column):
        '''
        Manually construct the facility[[-salt]-batch_id] link
        - only show the batch_id for non-canonical records (batch_id not '0')
        - only show the salt_id for the link and not the link text
        '''
        
        text_values = [record.reagent.facility_id]
        ids = [record.reagent.facility_id]
        
        if isinstance(record, SmallMoleculeBatch):
            ids.append(record.reagent.salt_id)

        if record.batch_id == '0':
            id = '-'.join(ids)
            uri = reverse(self.viewname, args=(id,))
        else:
            text_values.append(record.batch_id)
            ids.append(record.batch_id)
            id = '-'.join(ids)
            uri = reverse(self.viewname, args=(id,)) + '#batchinfo'

        text = '-'.join(text_values)
        return self.render_link(uri, text=text)
            
class SmallMoleculeBatchTable(PagedTable):
    
    facility_salt_batch = BatchInfoLinkColumn("sm_detail", args=[A('facility_salt_batch')])
    facility_salt_batch.attrs['td'] = {'nowrap': 'nowrap'}
    # qc_outcome = tables.Column()
    
    class Meta:
        model = SmallMoleculeBatch
        orderable = True
        attrs = {'class': 'paleblue'}

    def __init__(self, table, *args, **kwargs):
        super(SmallMoleculeBatchTable, self).__init__(table)
        set_table_column_info(
            self, ['smallmolecule','smallmoleculebatch',''],
            sequence_override=['facility_salt_batch'])  

class CellBatchTable(PagedTable):
    facility_batch = BatchInfoLinkColumn("cell_detail", args=[A('facility_batch')])
    
    class Meta:
        model = CellBatch
        orderable = True
        attrs = {'class': 'paleblue'}

    def __init__(self, table, *args, **kwargs):
        super(CellBatchTable, self).__init__(table, *args, **kwargs)
        set_table_column_info(
            self, ['cell','cellbatch',''],
            sequence_override=['facility_batch'])  

class PrimaryCellBatchTable(PagedTable):
    facility_batch = BatchInfoLinkColumn("primary_cell_detail", args=[A('facility_batch')])
    
    class Meta:
        model = PrimaryCellBatch
        orderable = True
        attrs = {'class': 'paleblue'}

    def __init__(self, table, *args, **kwargs):
        super(PrimaryCellBatchTable, self).__init__(table, *args, **kwargs)
        set_table_column_info(
            self, ['primarycell','primarycellbatch',''],
            sequence_override=['facility_batch'])  

class IpscBatchTable(PagedTable):
    facility_batch = BatchInfoLinkColumn("ipsc_detail", args=[A('facility_batch')])
    
    class Meta:
        model = IpscBatch
        orderable = True
        attrs = {'class': 'paleblue'}

    def __init__(self, table, *args, **kwargs):
        super(IpscBatchTable, self).__init__(table, *args, **kwargs)
        set_table_column_info(
            self, ['ipsc','ipscbatch',''],
            sequence_override=['facility_batch'])  

class EsCellBatchTable(PagedTable):
    facility_batch = BatchInfoLinkColumn("es_cell_detail", args=[A('facility_batch')])
    
    class Meta:
        model = EsCellBatch
        orderable = True
        attrs = {'class': 'paleblue'}

    def __init__(self, table, *args, **kwargs):
        super(EsCellBatchTable, self).__init__(table, *args, **kwargs)
        set_table_column_info(
            self, ['escell','escellbatch',''],
            sequence_override=['facility_batch'])  

class DiffCellBatchTable(PagedTable):
    facility_batch = BatchInfoLinkColumn("diff_cell_detail", args=[A('facility_batch')])
    
    class Meta:
        model = DiffCellBatch
        orderable = True
        attrs = {'class': 'paleblue'}

    def __init__(self, table, *args, **kwargs):
        super(DiffCellBatchTable, self).__init__(table, *args, **kwargs)
        set_table_column_info(
            self, ['diffcell','diffcellbatch',''],
            sequence_override=['facility_batch'])  

class AntibodyBatchTable(PagedTable):
    facility_batch = BatchInfoLinkColumn("antibody_detail", args=[A('facility_batch')])
    
    class Meta:
        model = AntibodyBatch
        orderable = True
        attrs = {'class': 'paleblue'}

    def __init__(self, table, *args, **kwargs):
        super(AntibodyBatchTable, self).__init__(table, *args, **kwargs)
        set_table_column_info(
            self, ['antibody','antibodybatch',''],
            sequence_override=['facility_batch'])  

class OtherReagentBatchTable(PagedTable):
    facility_batch = BatchInfoLinkColumn("otherreagent_detail", args=[A('facility_batch')])
    
    class Meta:
        model = OtherReagentBatch
        orderable = True
        attrs = {'class': 'paleblue'}

    def __init__(self, table, *args, **kwargs):
        super(OtherReagentBatchTable, self).__init__(table, *args, **kwargs)
        set_table_column_info(
            self, ['otherreagent','otherreagentbatch',''],
            sequence_override=['facility_batch'])  

class UnclassifiedBatchTable(PagedTable):
    facility_batch = BatchInfoLinkColumn("unclassified_detail", args=[A('facility_batch')])
    
    class Meta:
        model = UnclassifiedBatch
        orderable = True
        attrs = {'class': 'paleblue'}

    def __init__(self, table, *args, **kwargs):
        super(UnclassifiedBatchTable, self).__init__(table, *args, **kwargs)
        set_table_column_info(
            self, ['unclassified','unclassifiedbatch',''],
            sequence_override=['facility_batch'])  

class SaltTable(PagedTable):
    
    facility_id = tables.LinkColumn("salt_detail", args=[A('facility_id')])

    class Meta:
        model = SmallMolecule #[SmallMolecule, SmallMoleculeBatch]
        orderable = True
        attrs = {'class': 'paleblue'}
        
    def __init__(
            self, queryset, visible_field_overrides=None, 
            *args, **kwargs):
        super(SaltTable, self).__init__(queryset, *args, **kwargs)
        set_table_column_info(
            self, ['salt',''],
            sequence_override=['facility_id'], 
            visible_field_overrides=visible_field_overrides)  

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
        
    def __init__(
            self, queryset, visible_field_overrides=None, *args, **kwargs):
        super(SmallMoleculeTable, self).__init__(queryset, *args, **kwargs)
        set_table_column_info(
            self, ['smallmolecule','smallmoleculebatch',''],
            sequence_override=['facility_salt'], 
            visible_field_overrides=visible_field_overrides)  

class DataColumnTable(PagedTable):
    description = DivWrappedColumn(classname='constrained_width_column', visible=True)
    comments = DivWrappedColumn(classname='comment_column', visible=False)
    
    class Meta:
        model = DataColumn
        orderable = True
        attrs = {'class': 'paleblue'}
        
    def __init__(self, table,*args, **kwargs):
        super(DataColumnTable, self).__init__(table)
        set_table_column_info(self, ['datacolumn',''])  

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
        set_table_column_info(self, ['qcevent',''])  

class AttachedFileTable(PagedTable):
    filename=tables.LinkColumn("download_attached_file", args=[A('id')])
    
    class Meta:
        model = AttachedFile
        orderable = True
        attrs = {'class': 'paleblue'}
        
    def __init__(self, table,*args, **kwargs):
        super(AttachedFileTable, self).__init__(table)
        set_table_column_info(self, ['attachedfile',''])  
            
class SmallMoleculeForm(ModelForm):
    class Meta:
        model = SmallMolecule           
        order = ('facility_id', '...')
        exclude = ('id', 'molfile') 

class CellBatchDatasetTable(PagedTable):
    facility_id = BatchOrCanonicalLinkColumn(
        "cell_detail", accessor=A('reagent.facility_id'))
    name = tables.Column(accessor=A('reagent.name'))
    lincs_id = tables.Column(accessor=A('reagent.lincs_id'))
    alternative_id = DivWrappedColumn(
        accessor=A('reagent.alternative_id'),
        classname='constrained_width_column')

    class Meta:
        model = CellBatch
        orderable = True
        attrs = {'class': 'paleblue'}
        exclude = ('provider_name','provider_catalog_id','provider_batch_id')
        
    def __init__(self, table, *args, **kwargs):
        super(CellBatchDatasetTable, self).__init__(table, *args, **kwargs)
        set_table_column_info(
            self, ['cell','cellbatch',''],
            sequence_override=['facility_id'],
            visible_field_overrides=['name'])  

class PrimaryCellBatchDatasetTable(PagedTable):
    facility_id = BatchOrCanonicalLinkColumn(
        "primary_cell_detail", accessor=A('reagent.facility_id'))
    name = tables.Column(accessor=A('reagent.name'))
    lincs_id = tables.Column(accessor=A('reagent.lincs_id'))
    alternative_id = DivWrappedColumn(
        accessor=A('reagent.alternative_id'),
        classname='constrained_width_column')

    class Meta:
        model = PrimaryCellBatch
        orderable = True
        attrs = {'class': 'paleblue'}
        exclude = ('provider_name','provider_catalog_id','provider_batch_id')
        
    def __init__(self, table, *args, **kwargs):
        super(PrimaryCellBatchDatasetTable, self).__init__(table, *args, **kwargs)
        set_table_column_info(
            self, ['primarycell','primarycellbatch',''],
            sequence_override=['facility_id'],
            visible_field_overrides=['name'])  

class DiffCellBatchDatasetTable(PagedTable):
    facility_id = BatchOrCanonicalLinkColumn(
        "diff_cell_detail", accessor=A('reagent.facility_id'))
    name = tables.Column(accessor=A('reagent.name'))
    lincs_id = tables.Column(accessor=A('reagent.lincs_id'))
    alternative_id = DivWrappedColumn(
        accessor=A('reagent.alternative_id'),
        classname='constrained_width_column')

    class Meta:
        model = DiffCellBatch
        orderable = True
        attrs = {'class': 'paleblue'}
        exclude = ('provider_name','provider_catalog_id','provider_batch_id')
        
    def __init__(self, table, *args, **kwargs):
        super(DiffCellBatchDatasetTable, self).__init__(table, *args, **kwargs)
        set_table_column_info(
            self, ['diffcell','diffcellbatch',''],
            sequence_override=['facility_id'],
            visible_field_overrides=['name'])  

class IpscBatchDatasetTable(PagedTable):
    facility_id = BatchOrCanonicalLinkColumn(
        "ipsc_detail", accessor=A('reagent.facility_id'))
    name = tables.Column(accessor=A('reagent.name'))
    lincs_id = tables.Column(accessor=A('reagent.lincs_id'))
    alternative_id = DivWrappedColumn(
        accessor=A('reagent.alternative_id'),
        classname='constrained_width_column')

    class Meta:
        model = IpscBatch
        orderable = True
        attrs = {'class': 'paleblue'}
        exclude = ('provider_name','provider_catalog_id','provider_batch_id')
        
    def __init__(self, table, *args, **kwargs):
        super(IpscBatchDatasetTable, self).__init__(table, *args, **kwargs)
        set_table_column_info(
            self, ['ipsc','ipscbatch',''],
            sequence_override=['facility_id'],
            visible_field_overrides=['name'])  

class EsCellBatchDatasetTable(PagedTable):
    facility_id = BatchOrCanonicalLinkColumn(
        "es_cell_detail", accessor=A('reagent.facility_id'))
    name = tables.Column(accessor=A('reagent.name'))
    lincs_id = tables.Column(accessor=A('reagent.lincs_id'))
    alternative_id = DivWrappedColumn(
        accessor=A('reagent.alternative_id'),
        classname='constrained_width_column')

    class Meta:
        model = EsCellBatch
        orderable = True
        attrs = {'class': 'paleblue'}
        exclude = ('provider_name','provider_catalog_id','provider_batch_id')
        
    def __init__(self, table, *args, **kwargs):
        super(EsCellBatchDatasetTable, self).__init__(table, *args, **kwargs)
        set_table_column_info(
            self, ['escell','escellbatch',''],
            sequence_override=['facility_id'],
            visible_field_overrides=['name'])  

class AntibodyBatchDatasetTable(PagedTable):
    facility_id = BatchOrCanonicalLinkColumn(
        "antibody_detail", accessor=A('reagent.facility_id'))
    name = DivWrappedColumn(
        accessor=A('reagent.name'),
        classname='constrained_width_column')
    alternative_names = DivWrappedColumn(
        accessor=A('reagent.alternative_names'),
        classname='constrained_width_column')
    clone_name = tables.Column(accessor=A('reagent.antibody.clone_name'))
    lincs_id = tables.Column(accessor=A('reagent.lincs_id'))
    alternative_id = DivWrappedColumn(
        accessor=A('reagent.alternative_id'),
        classname='constrained_width_column')
    target_protein_center_ids_ui = TargetProteinLinkColumn(
        accessor=A('reagent.antibody.target_protein_center_ids_ui'))
    rrid = LinkTemplateColumn(
        accessor=A('reagent.antibody.rrid'),
        link_template=RRID_LINK_TEMPLATE)

    class Meta:
        model = AntibodyBatch
        orderable = True
        attrs = {'class': 'paleblue'}
        exclude = ('provider_name','provider_catalog_id','provider_batch_id')
        
    def __init__(self, table, *args, **kwargs):
        super(AntibodyBatchDatasetTable, self).__init__(table, *args, **kwargs)
        set_table_column_info(
            self, ['antibody','antibodybatch',''],
            sequence_override=[
                'facility_id','name','alternative_names','clone_name',
                'lincs_id','rrid','target_protein_center_ids_ui'])  

class OtherReagentBatchDatasetTable(PagedTable):
    facility_id = BatchOrCanonicalLinkColumn(
        "otherreagent_detail", accessor=A('reagent.facility_id'))
    name = tables.Column(accessor=A('reagent.name'))
    lincs_id = tables.Column(accessor=A('reagent.lincs_id'))
    alternative_id = DivWrappedColumn(
        accessor=A('reagent.alternative_id'),
        classname='constrained_width_column')
    alternative_names = DivWrappedColumn(
        accessor=A('reagent.alternative_names'),
        classname='constrained_width_column')

    class Meta:
        model = OtherReagentBatch
        orderable = True
        attrs = {'class': 'paleblue'}
        exclude = ('provider_name','provider_catalog_id','provider_batch_id')
        
    def __init__(self, table, *args, **kwargs):
        super(OtherReagentBatchDatasetTable, self).__init__(table, *args, **kwargs)
        set_table_column_info(
            self, ['otherreagent','otherreagentbatch',''],
            sequence_override=['facility_id'],
            visible_field_overrides=['name'])  

class UnclassifiedBatchDatasetTable(PagedTable):
    facility_id = BatchOrCanonicalLinkColumn(
        "unclassified_detail", accessor=A('reagent.facility_id'))
    name = tables.Column(accessor=A('reagent.name'))
    lincs_id = tables.Column(accessor=A('reagent.lincs_id'))
    alternative_id = DivWrappedColumn(
        accessor=A('reagent.alternative_id'),
        classname='constrained_width_column')
    alternative_names = DivWrappedColumn(
        accessor=A('reagent.alternative_names'),
        classname='constrained_width_column')

    class Meta:
        model = OtherReagentBatch
        orderable = True
        attrs = {'class': 'paleblue'}
        exclude = ('provider_name','provider_catalog_id','provider_batch_id')
        
    def __init__(self, table, *args, **kwargs):
        super(UnclassifiedBatchDatasetTable, self).__init__(table, *args, **kwargs)
        set_table_column_info(
            self, ['unclassified','unclassifiedbatch',''],
            sequence_override=['facility_id'],
            visible_field_overrides=['name'])  

class SmallMoleculeBatchDatasetTable(PagedTable):
    facility_id = BatchOrCanonicalLinkColumn(
        "sm_detail", accessor=A('reagent.facility_id')) 
    name = tables.Column(accessor=A('reagent.name'))
    lincs_id = tables.Column(accessor=A('reagent.lincs_id'))
    alternative_names = DivWrappedColumn(
        accessor=A('reagent.alternative_names'),
        classname='constrained_width_column')
    image = ImageColumn(
        verbose_name='image', accessor=A('reagent.unrestricted_facility_salt'), 
        image_class='compound_image_thumbnail', loc=COMPOUND_IMAGE_LOCATION)
    pubchem_cid = tables.Column(accessor=A('reagent.smallmolecule.pubchem_cid'))
    
    class Meta:
        model = SmallMoleculeBatch
        orderable = True
        attrs = {'class': 'paleblue'}
        exclude = ('provider_name','provider_catalog_id','provider_batch_id')
        
    def __init__(self, table, *args, **kwargs):
        super(SmallMoleculeBatchDatasetTable, self).__init__(table, *args, **kwargs)
        set_table_column_info(
            self, ['smallmolecule','smallmoleculebatch',''],
            sequence_override=['facility_id'],
            visible_field_overrides=['name'])  
    
class CellTable(PagedTable):
    facility_id = tables.LinkColumn("cell_detail", args=[A('facility_id')])
    rank = tables.Column()
    snippet = DivWrappedColumn(verbose_name='matched text', classname='snippet')
    id = tables.Column(verbose_name='CLO Id')
    disease = DivWrappedColumn(classname='constrained_width_column')
    dataset_types = DivWrappedColumn(classname='constrained_width_column', visible=False)
    alternative_id = DivWrappedColumn(classname='constrained_width_column')
    precursor_cell_name = tables.Column(visible=False)
    precursor_cell_facility_batch_id = tables.Column(visible=False)
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
 
    def __init__(self, table,visible_field_overrides=None, *args,**kwargs):
        super(CellTable, self).__init__(table,*args,**kwargs)
        set_table_column_info(
            self, ['cell',''], sequence_override=['facility_id'], 
            visible_field_overrides=visible_field_overrides)  
                        
class PrimaryCellTable(PagedTable):
    facility_id = tables.LinkColumn("primary_cell_detail", args=[A('facility_id')])
    rank = tables.Column()
    snippet = DivWrappedColumn(verbose_name='matched text', classname='snippet')
    id = tables.Column(verbose_name='CLO Id')
    disease = DivWrappedColumn(classname='constrained_width_column')
    dataset_types = DivWrappedColumn(classname='constrained_width_column', visible=False)
    alternative_id = DivWrappedColumn(classname='constrained_width_column')
    precursor_cell_name = tables.Column(visible=False)
    precursor_cell_facility_batch_id = tables.Column(visible=False)
    
    class Meta:
        model = PrimaryCell
        orderable = True
        attrs = {'class': 'paleblue'}
 
    def __init__(self, table,visible_field_overrides=None, *args,**kwargs):
        super(PrimaryCellTable, self).__init__(table,*args,**kwargs)
        set_table_column_info(
            self, ['primarycell',''], 
            sequence_override=['facility_id'], 
            visible_field_overrides=visible_field_overrides)  
       
class IpscTable(PagedTable):       
    facility_id = tables.LinkColumn("ipsc_detail", args=[A('facility_id')])
    rank = tables.Column()
    snippet = DivWrappedColumn(verbose_name='matched text', classname='snippet')
    id = tables.Column(verbose_name='CLO Id')
    dataset_types = DivWrappedColumn(classname='constrained_width_column', visible=False)
    alternative_id = DivWrappedColumn(classname='constrained_width_column')
    precursor_cell_name = tables.Column(visible=False)
    precursor_cell_facility_batch_id = tables.Column(visible=False)
    
    class Meta:
        model = Ipsc
        orderable = True
        attrs = {'class': 'paleblue'}
 
    def __init__(self, table,visible_field_overrides=None, *args,**kwargs):
        super(IpscTable, self).__init__(table,*args,**kwargs)
        set_table_column_info(
            self, ['ipsc',''], 
            sequence_override=['facility_id'], 
            visible_field_overrides=visible_field_overrides)  
                        
class EsCellTable(PagedTable):       
    facility_id = tables.LinkColumn("es_cell_detail", args=[A('facility_id')])
    rank = tables.Column()
    snippet = DivWrappedColumn(verbose_name='matched text', classname='snippet')
    id = tables.Column(verbose_name='CLO Id')
    dataset_types = DivWrappedColumn(classname='constrained_width_column', visible=False)
    alternative_id = DivWrappedColumn(classname='constrained_width_column')
    precursor_cell_name = tables.Column(visible=False)
    precursor_cell_facility_batch_id = tables.Column(visible=False)
    
    class Meta:
        model = EsCell
        orderable = True
        attrs = {'class': 'paleblue'}
 
    def __init__(self, table,visible_field_overrides=None, *args,**kwargs):
        super(EsCellTable, self).__init__(table,*args,**kwargs)
        set_table_column_info(
            self, ['escell',''], 
            sequence_override=['facility_id'], 
            visible_field_overrides=visible_field_overrides)  
                        
class DiffCellTable(PagedTable):
    facility_id = tables.LinkColumn("diff_cell_detail", args=[A('facility_id')])
    rank = tables.Column()
    snippet = DivWrappedColumn(verbose_name='matched text', classname='snippet')
    id = tables.Column(verbose_name='CLO Id')
    dataset_types = DivWrappedColumn(classname='constrained_width_column', visible=False)
    alternative_id = DivWrappedColumn(classname='constrained_width_column')
    precursor_cell_name = tables.Column(visible=False)
    precursor_cell_facility_batch_id = tables.Column(visible=False)
    
    class Meta:
        model = DiffCell
        orderable = True
        attrs = {'class': 'paleblue'}
 
    def __init__(self, table,visible_field_overrides=None, *args,**kwargs):
        super(DiffCellTable, self).__init__(table,*args,**kwargs)
        set_table_column_info(
            self, ['diffcell',''], 
            sequence_override=['facility_id'], 
            visible_field_overrides=visible_field_overrides)  
                        
class ProteinTable(PagedTable):
    facility_id = tables.LinkColumn("protein_detail", args=[A('facility_id')])
    rank = tables.Column()
    snippet = DivWrappedColumn(verbose_name='matched text', classname='snippet')
    alternative_names = DivWrappedColumn(classname='constrained_width_column', visible=False)
    alternative_id = DivWrappedColumn(classname='constrained_width_column')
    dataset_types = DivWrappedColumn(classname='constrained_width_column', visible=False)

    class Meta:
        model = Protein
        orderable = True
        attrs = {'class': 'paleblue'}
    
    def __init__(self, queryset, visible_field_overrides=None, *args, **kwargs):
        super(ProteinTable, self).__init__(queryset, *args, **kwargs)
        set_table_column_info(self, ['protein',''],
            sequence_override=['lincs_id'], 
            visible_field_overrides=visible_field_overrides)  

class AntibodyTable(PagedTable):
    
    facility_id = tables.LinkColumn("antibody_detail", args=[A('facility_id')])
    rank = tables.Column()
    snippet = DivWrappedColumn(verbose_name='matched text', classname='snippet')
    target_protein_center_ids_ui = TargetProteinLinkColumn()
    other_human_target_protein_center_ids_ui = TargetProteinLinkColumn()
    name = DivWrappedColumn(classname='constrained_width_column')
    alternative_names = DivWrappedColumn(classname='constrained_width_column')
    alternative_id = DivWrappedColumn(classname='constrained_width_column')
    rrid = LinkTemplateColumn(link_template=RRID_LINK_TEMPLATE)
    
    class Meta:
        model = Antibody
        orderable = True
        attrs = {'class': 'paleblue'}
    
    def __init__(self, table):
        super(AntibodyTable, self).__init__(table)
        set_table_column_info(
            self, ['antibody',''], sequence_override=['facility_id'])  
                
class OtherReagentTable(PagedTable):
    facility_id = tables.LinkColumn("otherreagent_detail", args=[A('facility_id')])
    rank = tables.Column()
    snippet = DivWrappedColumn(verbose_name='matched text', classname='snippet')
    alternative_id = DivWrappedColumn(classname='constrained_width_column')
    alternative_names = DivWrappedColumn(classname='constrained_width_column')

    class Meta:
        model = OtherReagent
        orderable = True
        attrs = {'class': 'paleblue'}
    
    def __init__(self, table):
        super(OtherReagentTable, self).__init__(table)
        set_table_column_info(
            self, ['otherreagent',''],sequence_override=['facility_id'])  
                
class UnclassifiedTable(PagedTable):
    facility_id = tables.LinkColumn("unclassified_detail", args=[A('facility_id')])
    rank = tables.Column()
    snippet = DivWrappedColumn(verbose_name='matched text', classname='snippet')
    alternative_id = DivWrappedColumn(classname='constrained_width_column')
    alternative_names = DivWrappedColumn(classname='constrained_width_column')

    class Meta:
        model = Unclassified
        orderable = True
        attrs = {'class': 'paleblue'}
    
    def __init__(self, table):
        super(UnclassifiedTable, self).__init__(table)
        set_table_column_info(
            self, ['unclassified',''],sequence_override=['facility_id'])  
                
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
        set_table_column_info(self, ['library',''])  
    
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
        if tablename in ['db_smallmolecule','db_cell','db_primarycell',
            'db_diffcell','db_ipsc','db_escell', 'db_antibody','db_protein',
            'db_otherreagent','db_unclassified']:
            criteria += ' or db_reagent.search_vector @@ to_tsquery(%s)'
            extra_select['snippet'] += (
                ' || ts_headline(' + Reagent.get_snippet_def() 
                + ', to_tsquery(%s))' )
            params.append(searchProcessed)
            extra_ids = [ id for id in ReagentBatch.objects.filter(
                Q(batch_id__icontains=searchString) |
                Q(provider_name__icontains=searchString) |
                Q(provider_catalog_id__icontains=searchString) |
                Q(center_specific_code__icontains=searchString) |
                Q(provider_batch_id__icontains=searchString) ).\
                    values_list('reagent__id').distinct('reagent__id')]
            ids.extend(extra_ids)
            
            extra_ids = [ id for id in 
                Reagent.objects.filter(
                    Q(name__icontains=searchString) |
                    Q(lincs_id__icontains=searchString) |
                    Q(alternative_names__icontains=searchString) |
                    Q(salt_id__exact=searchString) |
                    Q(facility_id__icontains=searchString))
                    .values_list('id') ]
            ids.extend(extra_ids)

        match = FACILITY_BATCH_PATTERN.match(searchString)
        if match:
            query = ( ReagentBatch.objects.all()
                .filter(reagent__facility_id__exact=match.group(2)))
            if match.group(4):
                query = query.filter(batch_id=match.group(4))
            extra_ids = [ id for id in
                query.values_list('reagent__id', flat=True)
                    .distinct('reagent__id')]
            ids.extend(extra_ids)
                    
        if ids:
            if tablename in ['db_smallmolecule','db_cell','db_primarycell',
                'db_diffcell','db_ipsc','db_escell','db_antibody','db_protein',
                'db_otherreagent', 'db_unclassified']:
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
        
        # Note: using simple "contains" search for cellbatch specific fields
        ids = [id for id in
            CellBatch.objects.all().filter(
                Q(source_information__icontains=searchString) |
                Q(transient_modification__icontains=searchString ))
                .values_list('reagent__id', flat=True)
                .distinct('reagent__id')]
        
        # find by precursor (id, name)
        new_ids = [id for id in
            CellBatch.objects.all()
                .filter(reagent__cell__precursor__reagent__name__icontains=searchString) 
                .values_list('reagent__id', flat=True)
                .distinct('reagent__id')]
        match = FACILITY_BATCH_PATTERN.match(searchString)
        if match:
            query = ( CellBatch.objects.all()
                .filter(reagent__cell__precursor__reagent__facility_id__exact
                    =match.group(2))) 
            if match.group(4):
                query = query.filter(reagent__cell__precursor__batch_id__exact
                    =match.group(4))
            new_ids = [id for id in 
                query.values_list('reagent__id', flat=True)
                    .distinct('reagent__id')]
        ids.extend(new_ids)
        
        query =  super(CellSearchManager, self).search(
            base_query, 'db_cell', searchString, id_fields, 
            Cell.get_snippet_def(), ids=ids)
        
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


class PrimaryCellSearchManager(SearchManager):

    def search(self, searchString, is_authenticated=False):
        base_query = PrimaryCell.objects.all()
        
        id_fields = []
        # Note: using simple "contains" search for primarycellbatch specific fields
        ids = [id for id in
            PrimaryCellBatch.objects.all().filter(
                Q(source_information__icontains=searchString) |
                Q(transient_modification__icontains=searchString ) |
                Q(culture_conditions__icontains=searchString ) )
                .values_list('reagent__id', flat=True)
                .distinct('reagent__id')]

        # find by precursor (id, name)
        new_ids = [id for id in
            PrimaryCellBatch.objects.all()
                .filter(reagent__primarycell__precursor__reagent__name__icontains=searchString) 
                .values_list('reagent__id', flat=True)
                .distinct('reagent__id')]
        match = FACILITY_BATCH_PATTERN.match(searchString)
        if match:
            query = ( PrimaryCellBatch.objects.all()
                .filter(reagent__primarycell__precursor__reagent__facility_id__exact
                    =match.group(2))) 
            if match.group(4):
                query = query.filter(reagent__primarycell__precursor__batch_id__exact
                    =match.group(4))
            new_ids = [id for id in 
                query.values_list('reagent__id', flat=True)
                    .distinct('reagent__id')]
        ids.extend(new_ids)
        
        
        query =  super(PrimaryCellSearchManager, self).search(
            base_query, 'db_primarycell', searchString, id_fields, 
            PrimaryCell.get_snippet_def(), ids=ids)
        
        return query

    def join_query_to_dataset_type(self, queryset, dataset_type=None ):
        if dataset_type:
            ids = (DataSet.objects
                .filter(dataset_type=str(dataset_type))
                .values_list('primary_cells__reagent__id', flat=True)
                .distinct('primary_cells__reagent__id') )
            queryset = queryset.filter(id__in=ids)
        queryset = queryset.extra(select={
            'dataset_types' : (
                "(select array_to_string(array_agg(distinct (ds.dataset_type)),', ')"
                "     from db_dataset ds "
                " join {join_table} on(ds.id={join_table}.dataset_id) " 
                " join db_reagentbatch rb on(rb.id={join_table}.{specific_batch_id} ) "
                " where rb.reagent_id={specific_reagent_table}.reagent_ptr_id)" ) 
                    .format(join_table='db_dataset_primary_cells',
                            specific_batch_id='primarycellbatch_id',
                            specific_reagent_table='db_primarycell')
            })
        return queryset

class IpscSearchManager(SearchManager):
    
    def search(self, searchString, is_authenticated=False):
        base_query = Ipsc.objects.all()
        
        id_fields = []
        # Note: using simple "contains" search for ipscbatch specific fields
        ids = [id for id in
            IpscBatch.objects.all().filter(
                Q(source_information__icontains=searchString) |
                Q(transient_modification__icontains=searchString ) |
                Q(culture_conditions__icontains=searchString ) )
                .values_list('reagent__id', flat=True)
                .distinct('reagent__id')]

        # find by precursor (id, name)
        new_ids = [id for id in
            IpscBatch.objects.all()
                .filter(reagent__ipsc__precursor__reagent__name__icontains=searchString) 
                .values_list('reagent__id', flat=True)
                .distinct('reagent__id')]
        match = FACILITY_BATCH_PATTERN.match(searchString)
        if match:
            query = ( IpscBatch.objects.all()
                .filter(reagent__ipsc__precursor__reagent__facility_id__exact
                    =match.group(2))) 
            if match.group(4):
                query = query.filter(reagent__ipsc__precursor__batch_id__exact
                    =match.group(4))
            new_ids = [id for id in 
                query.values_list('reagent__id', flat=True)
                    .distinct('reagent__id')]
        ids.extend(new_ids)
        query =  super(IpscSearchManager, self).search(
            base_query, 'db_ipsc', searchString, id_fields, 
            Ipsc.get_snippet_def(), ids=ids)
        return query

    def join_query_to_dataset_type(self, queryset, dataset_type=None ):
        if dataset_type:
            ids = (DataSet.objects
                .filter(dataset_type=str(dataset_type))
                .values_list('ipscs__reagent__id', flat=True)
                .distinct('ipscs__reagent__id') )
            queryset = queryset.filter(id__in=ids)
        queryset = queryset.extra(select={
            'dataset_types' : (
                "(select array_to_string(array_agg(distinct (ds.dataset_type)),', ')"
                "     from db_dataset ds "
                " join {join_table} on(ds.id={join_table}.dataset_id) " 
                " join db_reagentbatch rb on(rb.id={join_table}.{specific_batch_id} ) "
                " where rb.reagent_id={specific_reagent_table}.reagent_ptr_id)" ) 
                    .format(join_table='db_dataset_ipscs',
                            specific_batch_id='ipscbatch_id',
                            specific_reagent_table='db_ipsc')
            })
        return queryset
    
class EsCellSearchManager(SearchManager):
    
    def search(self, searchString, is_authenticated=False):
        base_query = EsCell.objects.all()
        
        id_fields = []
        # Note: using simple "contains" search for EsCellBatch specific fields
        ids = [id for id in
            EsCellBatch.objects.all().filter(
                Q(source_information__icontains=searchString) |
                Q(transient_modification__icontains=searchString ) |
                Q(culture_conditions__icontains=searchString ) )
                .values_list('reagent__id', flat=True)
                .distinct('reagent__id')]

        # find by precursor (id, name)
        new_ids = [id for id in
            EsCellBatch.objects.all()
                .filter(reagent__escell__precursor__reagent__name__icontains=searchString) 
                .values_list('reagent__id', flat=True)
                .distinct('reagent__id')]
        match = FACILITY_BATCH_PATTERN.match(searchString)
        if match:
            query = ( EsCellBatch.objects.all()
                .filter(reagent__escell__precursor__reagent__facility_id__exact
                    =match.group(2))) 
            if match.group(4):
                query = query.filter(reagent__escell__precursor__batch_id__exact
                    =match.group(4))
            new_ids = [id for id in 
                query.values_list('reagent__id', flat=True)
                    .distinct('reagent__id')]
        ids.extend(new_ids)
        query =  super(EsCellSearchManager, self).search(
            base_query, 'db_escell', searchString, id_fields, 
            EsCell.get_snippet_def(), ids=ids)
        return query

    def join_query_to_dataset_type(self, queryset, dataset_type=None ):
        if dataset_type:
            ids = (DataSet.objects
                .filter(dataset_type=str(dataset_type))
                .values_list('es_cells__reagent__id', flat=True)
                .distinct('es_cells__reagent__id') )
            queryset = queryset.filter(id__in=ids)
        queryset = queryset.extra(select={
            'dataset_types' : (
                "(select array_to_string(array_agg(distinct (ds.dataset_type)),', ')"
                "     from db_dataset ds "
                " join {join_table} on(ds.id={join_table}.dataset_id) " 
                " join db_reagentbatch rb on(rb.id={join_table}.{specific_batch_id} ) "
                " where rb.reagent_id={specific_reagent_table}.reagent_ptr_id)" ) 
                    .format(join_table='db_dataset_es_cells',
                            specific_batch_id='escellbatch_id',
                            specific_reagent_table='db_escell')
            })
        return queryset
    
class DiffCellSearchManager(SearchManager):

    def search(self, searchString, is_authenticated=False):
        base_query = DiffCell.objects.all()
        
        id_fields = []
        # Note: using simple "contains" search for diffcellbatch specific fields
        ids = [id for id in
            DiffCellBatch.objects.all().filter(
                Q(source_information__icontains=searchString) |
                Q(transient_modification__icontains=searchString ) |
                Q(culture_conditions__icontains=searchString ) )
                .values_list('reagent__id', flat=True)
                .distinct('reagent__id')]

        # find by precursor (id, name)
        new_ids = [id for id in
            DiffCellBatch.objects.all()
                .filter(reagent__diffcell__precursor__reagent__name__icontains=searchString) 
                .values_list('reagent__id', flat=True)
                .distinct('reagent__id')]
        match = FACILITY_BATCH_PATTERN.match(searchString)
        if match:
            query = ( DiffCellBatch.objects.all()
                .filter(reagent__diffcell__precursor__reagent__facility_id__exact
                    =match.group(2))) 
            if match.group(4):
                query = query.filter(reagent__diffcell__precursor__batch_id__exact
                    =match.group(4))
            new_ids = [id for id in 
                query.values_list('reagent__id', flat=True)
                    .distinct('reagent__id')]
        ids.extend(new_ids)
        query =  super(DiffCellSearchManager, self).search(
            base_query, 'db_diffcell', searchString, id_fields, 
            DiffCell.get_snippet_def(), ids=ids)
        return query

    def join_query_to_dataset_type(self, queryset, dataset_type=None ):
        if dataset_type:
            ids = (DataSet.objects
                .filter(dataset_type=str(dataset_type))
                .values_list('diff_cells__reagent__id', flat=True)
                .distinct('diff_cells__reagent__id') )
            queryset = queryset.filter(id__in=ids)
        queryset = queryset.extra(select={
            'dataset_types' : (
                "(select array_to_string(array_agg(distinct (ds.dataset_type)),', ')"
                "     from db_dataset ds "
                " join {join_table} on(ds.id={join_table}.dataset_id) " 
                " join db_reagentbatch rb on(rb.id={join_table}.{specific_batch_id} ) "
                " where rb.reagent_id={specific_reagent_table}.reagent_ptr_id)" ) 
                    .format(join_table='db_dataset_diff_cells',
                            specific_batch_id='diffcellbatch_id',
                            specific_reagent_table='db_diffcell')
            })
        return queryset

class ProteinSearchManager(SearchManager):

    def search(self, searchString, is_authenticated=False):

        id_fields = ['uniprot_id', 'alternate_name_2',
             'provider_catalog_id']

        # Note: using simple "contains" search for proteinbatch specific fields
        ids = [id for id in
            ProteinBatch.objects.all().filter(
                Q(production_organism__icontains=searchString) )
                .values_list('reagent__id', flat=True)
                .distinct('reagent__id')]

        return super(ProteinSearchManager, self).search(
            Protein.objects.all(), 'db_protein', searchString, id_fields, 
            Protein.get_snippet_def(), ids=ids)        
    
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
        ids = []
        # Note: using simple "contains" search for proteinbatch specific fields
        if is_authenticated:
            ids = [id for id in
                SmallMoleculeBatch.objects.all().filter(
                    Q(_chemical_synthesis_reference__icontains=searchString) |
                    Q(_purity__icontains=searchString) |
                    Q(_purity_method__icontains=searchString) )
                    .values_list('reagent__id', flat=True)
                    .distinct('reagent__id')]

        return super(SmallMoleculeSearchManager, self).search(
            queryset, 'db_smallmolecule', searchString, id_fields, 
            SmallMolecule.get_snippet_def(), ids=ids )        

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

        # Note: using simple "contains" search for antibodybatch specific fields
        ids = [id for id in
            AntibodyBatch.objects.all().filter(
                Q(antibody_purity__icontains=searchString))
                .values_list('reagent__id', flat=True)
                .distinct('reagent__id')]

        # Find matching proteins linked through target fields
        proteinSearchQuery = ProteinSearchManager().search(searchString, is_authenticated)
        protein_ids = [x.id for x in proteinSearchQuery.all()]
        new_ids = [x.id for x in 
            Antibody.objects.all()
                .filter(
                    Q(target_proteins__in=protein_ids) |
                    Q(other_human_target_proteins__in=protein_ids))]
        ids.extend(new_ids)
        return super(AntibodySearchManager, self).search(
            Antibody.objects.all(), 'db_antibody', searchString, id_fields, 
            Antibody.get_snippet_def(), ids=ids)        

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

class UnclassifiedSearchManager(SearchManager):
    
    def search(self, searchString, is_authenticated=False):

        id_fields = []
        return super(UnclassifiedSearchManager, self).search(
            Unclassified.objects.all(), 'db_unclassified', searchString, id_fields, 
            Unclassified.get_snippet_def())        

    def join_query_to_dataset_type(self, queryset, dataset_type=None ):
        if dataset_type:
            ids = (DataSet.objects
                .filter(dataset_type=str(dataset_type))
                .values_list('unclassified_perturbagens__reagent__id', flat=True)
                .distinct('unclassified_perturbagens__reagent__id') )
            queryset = queryset.filter(id__in=ids)
        queryset = queryset.extra(select={
            'dataset_types' : (
                "(select array_to_string(array_agg(distinct (ds.dataset_type)),', ')"
                "     from db_dataset ds "
                " join {join_table} on(ds.id={join_table}.dataset_id) " 
                " join db_reagentbatch rb on(rb.id={join_table}.{specific_batch_id} ) "
                " where rb.reagent_id={specific_reagent_table}.reagent_ptr_id)" ) 
                    .format(join_table='db_dataset_unclassified_perturbagens',
                            specific_batch_id='unclassifiedbatch_id',
                            specific_reagent_table='db_unclassified')
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
                          visible_field_overrides=None):
    """
    Field information section
    @param table: a django-tables2 table
    @param sequence_override list of fields to show before all other fields
    @param table_names: a list of table names, by order of priority, 
            include '' empty string for a general search.
    """ 
    if sequence_override is None: 
        sequence_override = []
    if visible_field_overrides is None:
        visible_field_overrides = []
    visible_field_overrides = set(visible_field_overrides) | set(sequence_override)
    
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
    sequence_override.extend(
        [x for x in visible_field_overrides if x not in sequence_override])
    sequence_override.extend(sequence)
    table.sequence = sequence_override
    table.exclude = tuple(exclude_list)
    
        
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
    logger.info(str(('send_to_file1', outputType, name, ordered_datacolumns)))
    col_key_name_map = get_cursor_col_key_name_map(
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


def get_cursor_col_key_name_map(cursor, fieldinformation_tables=None, 
                                ordered_datacolumns=None):
    """
    returns an OrderedDict of column_number:verbose_name
    @param ordered_datacolumns for use in ordering
    """
    if not fieldinformation_tables: 
        fieldinformation_tables=['']
    header_row = {}
    for i,col in enumerate(cursor.description):
        found = False
        if ordered_datacolumns:
            logger.debug(
                'find cursor col %r in ordered_datacolumns %s' 
                    % (col.name, [x.name for x in ordered_datacolumns]))
            for dc in ordered_datacolumns:
                if ( dc.data_type in 
                    ['small_molecule', 'cell','primary_cell','protein',
                        'antibody','other_reagent','unclassified']):
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
            logger.info(
                'col: %r, not found in datacolumns, find in fieldinformation' 
                    % col.name)
            try:
                fi = FieldInformation.manager.\
                    get_column_fieldinformation_by_priority(
                        col.name,fieldinformation_tables)
                header_row[i] = fi.get_verbose_name()
            except (Exception) as e:
                logger.warn(
                    'no fieldinformation found for field: %r', col.name)
         
    return OrderedDict(sorted(header_row.items(),key=lambda x: x[0]))

def get_table_col_key_name_map(table, fieldinformation_tables=None,
                               extra_columns=None):
    if fieldinformation_tables is None: 
        fieldinformation_tables=['']
    if extra_columns is None:
        extra_columns=[]
    # ordered list (field,verbose_name)
    columns = map(
        lambda (x,y): (x, y.verbose_name), 
            filter(lambda (x,y): 
                (x!='rank' and x!='snippet' and (y.visible or x in extra_columns)), 
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
                        field,fieldinformation_tables)
            else:
                fi = FieldInformation.manager.\
                    get_column_fieldinformation_by_priority(
                        field,fieldinformation_tables)
            if(fi.show_in_detail or field in extra_columns):
                col_fi_map[field]=fi
        except (Exception) as e:
            logger.warn('no fieldinformation found for field: %r', field)        
    return OrderedDict(
        [(x[0],x[1].get_verbose_name()) 
            for x in sorted(
                col_fi_map.items(), key=lambda item:item[1].detail_order)])    

def get_col_key_mapping(cols, fieldinformation_tables=None, 
                        extra_columns=None, sequence_override=None):
    """
    returns an OrderedDict of key:verbose_name
    """
    if fieldinformation_tables is None: 
        fieldinformation_tables=['']
    if extra_columns is None:
        extra_columns=[]
    if sequence_override is None:
        sequence_override = []
        
    extra_columns = set(extra_columns) | set(sequence_override)
    header_row = {}
    fi_map = {}
    for col_name in cols:
        try:
            fi = FieldInformation.manager.\
                get_column_fieldinformation_by_priority(
                    col_name,fieldinformation_tables)
            if fi.show_in_list or fi.show_in_detail or col_name in extra_columns:
                header_row[col_name] = fi.get_verbose_name()
                fi_map[col_name] = fi
        except (Exception) as e:
            logger.info(
                'no fieldinformation found for field:  %r, tables: %r', 
                    col_name, fieldinformation_tables)
    def sort_key(item):
        key = item[0]
        if key in sequence_override:
            val = sequence_override.index(key)
        else:
            fi = fi_map[key]
            tablename = fi.table or fi.queryset
            order = 1000
            if tablename in fieldinformation_tables:
                index = fieldinformation_tables.index(tablename)
                order = index *100
            val = order + fi_map[key].detail_order
        return val
        
    return OrderedDict(sorted(header_row.items(),key=sort_key))


def _write_val_safe(val, is_authenticated=False):
    # for #185, remove 'None' values
    # also, for #386, trim leading spaces from strings for openpyxl
    # see https://bitbucket.org/openpyxl/openpyxl/issues/280
    return smart_str(val, 'utf-8', errors='ignore').strip() if val is not None else ''
  
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
    output_filename = '_'.join(re.split(r'\W+',output_filename))
    response['Content-Disposition'] = \
        'attachment; filename=%s.zip' % output_filename
    return response

def normalized_download_filename(name):
    return re.sub(r'\W+','_',name)

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
    assert not (bool(cursor) and bool(queryset)), 'must define either cursor or queryset, not both'
    
    response = HttpResponse(mimetype='text/csv')
    response['Content-Disposition'] = \
        'attachment; filename=%s.csv' % normalized_download_filename(name)

    if not (bool(cursor) or bool(queryset)):
        logger.info(str(('empty result for', name)))
        response = HttpResponse()
        response.status_code=204
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
                vals = [';'.join(x) if isinstance(x,(list,tuple)) else x for x in vals]
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
    @param name the filename to use
    """
    assert not (bool(cursor) and bool(queryset)), 'must define either cursor or queryset, not both'

    if not (bool(cursor) or bool(queryset)):
        logger.info(str(('empty result for', name)))
        response = HttpResponse()
        response.status_code=204
        return response

    name = normalized_download_filename(name)
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
                vals = [';'.join(x) if isinstance(x,(list,tuple)) else x for x in vals]
            
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
    with SpooledTemporaryFile(max_size=100*1024) as f:
        wb.save(f)
        f.seek(0)
        logger.info('write file to response: %s ' % name)
        response = HttpResponse(
            f.read(), 
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename=%s.xlsx' % name
        return response

def send_to_file(outputType, name, queryset, col_key_name_map,
                 is_authenticated=False): 
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
        raise Http404(
            'Unknown output type: "%s", must be one of [".xlsx",".csv"]' 
                % outputType )
    
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
                'has_primary_cells':dataset.primary_cells.exists(),
                'has_ipscs':dataset.ipscs.exists(),
                'has_es_cells':dataset.es_cells.exists(),
                'has_diff_cells':dataset.diff_cells.exists(),
                'has_proteins':dataset.proteins.exists(),
                'has_antibodies':dataset.antibodies.exists(),
                'has_otherreagents':dataset.other_reagents.exists(),
                'has_unclassified': dataset.unclassified_perturbagens.exists(),
                'has_datacolumns': dataset.datacolumn_set.exists(), 
                'has_metadata': dataset.properties.exists() }

    items_per_page = 25
    form = PaginationForm(request.GET)
    details['items_per_page_form'] = form
    if(form.is_valid()):
        if(form.cleaned_data['items_per_page']): 
            items_per_page = int(form.cleaned_data['items_per_page'])
    
    if (sub_page == 'results'):
        if dataset.datarecord_set.exists():
            form = manager.get_result_set_data_form(request)
            table = manager.get_table(facility_ids=form.get_search_facility_ids()) 
            details['search_form'] = form
            if(len(table.data)>0):
                details['table'] = table
                RequestConfig(
                    request, paginate={"per_page": items_per_page}).configure(table)
        if manager.dataset.dataset_data_url:
            logger.info('dataset_data_url: %r', manager.dataset.dataset_data_url)
            details['dataset_data_url'] = manager.dataset.dataset_data_url

    elif (sub_page == 'cells'):
        if dataset.cells.exists():
            queryset = dataset.cells.all()
            queryset = queryset.order_by('reagent__facility_id','batch_id')
            table = CellBatchDatasetTable(queryset)
            setattr(table.data,'verbose_name_plural','Cells')
            setattr(table.data,'verbose_name','Cells')
            details['table'] = table
            RequestConfig(
                request, paginate={"per_page": items_per_page}).configure(table)
    elif (sub_page == 'primary_cells'):
        if dataset.primary_cells.exists():
            queryset = dataset.primary_cells.all()
            queryset = queryset.order_by('reagent__facility_id','batch_id')
            table = PrimaryCellBatchDatasetTable(queryset)
            setattr(table.data,'verbose_name_plural','Primary Cells')
            setattr(table.data,'verbose_name','Primary Cells')
            details['table'] = table
            RequestConfig(
                request, paginate={"per_page": items_per_page}).configure(table)
    elif (sub_page == 'ipscs'):
        if dataset.ipscs.exists():
            queryset = dataset.ipscs.all()
            queryset = queryset.order_by('reagent__facility_id','batch_id')
            table = IpscBatchDatasetTable(queryset)
            setattr(table.data,'verbose_name_plural','iPSCs')
            setattr(table.data,'verbose_name','iPSC')
            details['table'] = table
            RequestConfig(
                request, paginate={"per_page": items_per_page}).configure(table)
    elif (sub_page == 'es_cells'):
        if dataset.es_cells.exists():
            queryset = dataset.es_cells.all()
            queryset = queryset.order_by('reagent__facility_id','batch_id')
            table = EsCellBatchDatasetTable(queryset)
            setattr(table.data,'verbose_name_plural','Embryonic Stem Cells')
            setattr(table.data,'verbose_name','Embryonic Stem Cell')
            details['table'] = table
            RequestConfig(
                request, paginate={"per_page": items_per_page}).configure(table)
    elif (sub_page == 'diff_cells'):
        if dataset.diff_cells.exists():
            queryset = dataset.diff_cells.all()
            queryset = queryset.order_by('reagent__facility_id','batch_id')
            table = DiffCellBatchDatasetTable(queryset)
            setattr(table.data,'verbose_name_plural','Differentiated Cells')
            setattr(table.data,'verbose_name','Differentiated Cell')
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
            queryset = dataset.antibodies.all()
            queryset = queryset.order_by('reagent__facility_id','batch_id')
            table = AntibodyBatchDatasetTable(queryset)
            setattr(table.data,'verbose_name_plural','Antibodies')
            setattr(table.data,'verbose_name','Antibody')
            details['table'] = table
            RequestConfig(
                request, paginate={"per_page": items_per_page}).configure(table)
    elif (sub_page == 'otherreagents'):
        if dataset.other_reagents.exists():
            queryset = dataset.other_reagents.all()
            queryset = queryset.order_by('reagent__facility_id','batch_id')
            table = OtherReagentBatchDatasetTable(queryset)
            setattr(table.data,'verbose_name_plural','Other Reagents')
            setattr(table.data,'verbose_name','Other Reagent')
            details['table'] = table
            RequestConfig(
                request, paginate={"per_page": items_per_page}).configure(table)
    elif (sub_page == 'unclassified'):
        if dataset.unclassified_perturbagens.exists():
            queryset = dataset.unclassified_perturbagens.all()
            queryset = queryset.order_by('reagent__facility_id','batch_id')
            table = UnclassifiedBatchDatasetTable(queryset)
            setattr(table.data,'verbose_name_plural','Unclassified Perturbagens')
            setattr(table.data,'verbose_name','Unclassified Perturbagen')
            details['table'] = table
            RequestConfig(
                request, paginate={"per_page": items_per_page}).configure(table)
    elif (sub_page == 'small_molecules'):
        if dataset.small_molecules.exists():
            queryset = dataset.small_molecules.all()
            queryset = queryset.order_by('reagent__facility_id')
            table = SmallMoleculeBatchDatasetTable(queryset)
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
    elif sub_page == 'metadata':
        # Use the API to generate a JSON compatible mapping of the properties
        property_map = DataSetResource2().build_metadata(dataset)
        prop_string = json.dumps(property_map, sort_keys=False, indent=2)
        # Do a minimalist conversion of the JSON structure to a indented list
        prop_string = re.sub(r'[{},"\[\]]','',prop_string)
        # Remove empty lines in the indented list
        prop_string = re.sub(r'^\s+\n','', prop_string, flags=re.MULTILINE )
        # Send the indented list directly to the template
        details['jsonProperties'] = prop_string
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
            if dc.data_type in ['small_molecule', 'cell','primary_cell',
                'diff_cell','ipsc','es_cell', 'protein','antibody','other_reagent',
                'unclassified']:
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
            elif dc.data_type.lower() == 'primary_cell':
                key_col = col+'_name'
                self.base_columns[key_col] = tables.LinkColumn('primary_cell_detail',
                    args=[A(col)], verbose_name=display_name) 
            elif dc.data_type.lower() == 'ipsc':
                key_col = col+'_name'
                self.base_columns[key_col] = tables.LinkColumn('ipsc_detail',
                    args=[A(col)], verbose_name=display_name) 
            elif dc.data_type.lower() == 'es_cell':
                key_col = col+'_name'
                self.base_columns[key_col] = tables.LinkColumn('es_cell_detail',
                    args=[A(col)], verbose_name=display_name) 
            elif dc.data_type.lower() == 'diff_cell':
                key_col = col+'_name'
                self.base_columns[key_col] = tables.LinkColumn('diff_cell_detail',
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
            elif dc.data_type.lower() == 'unclassified':
                key_col = col+'_name'
                self.base_columns[key_col] = tables.LinkColumn('unclassified_detail',
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
            items = sorted(set(item.reagent 
                for item in self.dataset.cells.all()),
                key=lambda x: x.facility_id)
            entity_id_name_map['cells'] = { 
                'id_field': 'cell_id', 
                'choices': [(reagent.facility_id, 
                    '%s:%s' % (reagent.facility_id,reagent.name))
                    for reagent in items  ] }
        if self.dataset.primary_cells.exists():
            items = sorted(set(item.reagent 
                for item in self.dataset.primary_cells.all()),
                key=lambda x: x.facility_id)
            entity_id_name_map['primary_cells'] = { 
                'id_field': 'primarycell_id', 
                'choices': [(reagent.facility_id, 
                    '%s:%s' % (reagent.facility_id,reagent.name))
                    for reagent in items  ] }
        if self.dataset.ipscs.exists():
            items = sorted(set(item.reagent 
                for item in self.dataset.ipscs.all()),
                key=lambda x: x.facility_id)
            entity_id_name_map['ipscs'] = { 
                'id_field': 'ipsc_id', 
                'choices': [(reagent.facility_id, 
                    '%s:%s' % (reagent.facility_id,reagent.name))
                    for reagent in items  ] }
        if self.dataset.es_cells.exists():
            items = sorted(set(item.reagent 
                for item in self.dataset.es_cells.all()),
                key=lambda x: x.facility_id)
            entity_id_name_map['es_cells'] = { 
                'id_field': 'escell_id', 
                'choices': [(reagent.facility_id, 
                    '%s:%s' % (reagent.facility_id,reagent.name))
                    for reagent in items  ] }
        if self.dataset.diff_cells.exists():
            items = sorted(set(item.reagent 
                for item in self.dataset.diff_cells.all()),
                key=lambda x: x.facility_id)
            entity_id_name_map['diff_cells'] = { 
                'id_field': 'diffcell_id', 
                'choices': [(reagent.facility_id, 
                    '%s:%s' % (reagent.facility_id,reagent.name))
                    for reagent in items  ] }
        if self.dataset.proteins.exists():
            items = sorted(set(item.reagent 
                for item in self.dataset.proteins.all()),
                key=lambda x: x.facility_id)
            entity_id_name_map['proteins'] = { 
                'id_field': 'protein_id', 
                'choices': [(reagent.facility_id, 
                    '%s:%s' % (reagent.facility_id,reagent.name))
                    for reagent in items  ] }
        if self.dataset.small_molecules.exists():
            items = sorted(set(item.reagent 
                for item in self.dataset.small_molecules.all()),
                key=lambda x: x.facility_id)
            entity_id_name_map['small molecules'] = { 
                'id_field': 'smallmolecule_id', 
                'choices': [(reagent.facility_id, 
                    '%s:%s' % (reagent.facility_id,reagent.name))
                    for reagent in items  ] }
        if self.dataset.antibodies.exists():
            items = sorted(set(item.reagent 
                for item in self.dataset.antibodies.all()),
                key=lambda x: x.facility_id)
            entity_id_name_map['antibodies'] = { 
                'id_field': 'antibody_id', 
                'choices': [(reagent.facility_id, 
                    '%s' % (reagent.facility_id))
                    for reagent in items  ] }
        if self.dataset.other_reagents.exists():
            items = sorted(set(item.reagent 
                for item in self.dataset.other_reagents.all()),
                key=lambda x: x.facility_id)
            entity_id_name_map['other reagents'] = { 
                'id_field': 'otherreagent_id', 
                'choices': [(reagent.facility_id, 
                    '%s:%s' % (reagent.facility_id,reagent.name))
                    for reagent in items  ] }
        if self.dataset.unclassified_perturbagens.exists():
            items = sorted(set(item.reagent 
                for item in self.dataset.unclassified_perturbagens.all()),
                key=lambda x: x.facility_id)
            entity_id_name_map['unclassified'] = { 
                'id_field': 'unclassified_id', 
                'choices': [(reagent.facility_id, 
                    '%s:%s' % (reagent.facility_id,reagent.name))
                    for reagent in items  ] }
            
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
            elif dc.data_type in ['small_molecule','cell','primary_cell',
                'diff_cell','ipsc','es_cell', 'protein','antibody','other_reagent',
                'unclassified']:
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
            key_id='facility_id',
            reagent_snippet_def=Reagent.get_snippet_def(),
            snippet_def=PrimaryCell.get_snippet_def(),
            detail_type='primary_cell_detail',
            table_name='db_primarycell',
            query_number='query2')
        if(not is_authenticated): 
            sql += RESTRICTION_SQL        
        sql += " UNION "
        sql += REAGENT_SEARCH_SQL.format(
            key_id='facility_id',
            reagent_snippet_def=Reagent.get_snippet_def(),
            snippet_def=Ipsc.get_snippet_def(),
            detail_type='ipsc_detail',
            table_name='db_ipsc',
            query_number='query3')
        if(not is_authenticated): 
            sql += RESTRICTION_SQL        
        sql += " UNION "
        sql += REAGENT_SEARCH_SQL.format(
            key_id='facility_id',
            reagent_snippet_def=Reagent.get_snippet_def(),
            snippet_def=EsCell.get_snippet_def(),
            detail_type='es_cell_detail',
            table_name='db_escell',
            query_number='query11')
        if(not is_authenticated): 
            sql += RESTRICTION_SQL        
        sql += " UNION "
        sql += REAGENT_SEARCH_SQL.format(
            key_id='facility_id',
            reagent_snippet_def=Reagent.get_snippet_def(),
            snippet_def=DiffCell.get_snippet_def(),
            detail_type='diff_cell_detail',
            table_name='db_diffcell',
            query_number='query4')
        if(not is_authenticated): 
            sql += RESTRICTION_SQL        
        sql += " UNION "
        sql += REAGENT_SEARCH_SQL.format(
            key_id= "facility_id || '-' || salt_id" ,
            reagent_snippet_def=Reagent.get_snippet_def(),
            snippet_def=SmallMolecule.get_snippet_def(),
            detail_type='sm_detail',
            table_name='db_smallmolecule',
            query_number='query5')
        if(not is_authenticated): 
            sql += RESTRICTION_SQL
        sql += " UNION "
        sql += SEARCH_SQL.format(
            key_id='facility_id',
            snippet_def=DataSet.get_snippet_def(),
            detail_type='dataset_detail',
            table_name='db_dataset',
            query_number='query6')
        if(not is_authenticated): 
            sql += RESTRICTION_SQL
        sql += " UNION "
        sql += REAGENT_SEARCH_SQL.format(
            key_id='facility_id',
            reagent_snippet_def=Reagent.get_snippet_def(),
            snippet_def=Protein.get_snippet_def(),
            detail_type='protein_detail',
            table_name='db_protein',
            query_number='query7')
        if(not is_authenticated): 
            sql += RESTRICTION_SQL
        sql += " UNION "
        sql += REAGENT_SEARCH_SQL.format(
            key_id='facility_id',
            reagent_snippet_def=Reagent.get_snippet_def(),
            snippet_def=Antibody.get_snippet_def(),
            detail_type='antibody_detail',
            table_name='db_antibody',
            query_number='query8')
        if(not is_authenticated): 
            sql += RESTRICTION_SQL
        sql += " UNION "
        sql += REAGENT_SEARCH_SQL.format(
            key_id='facility_id',
            reagent_snippet_def=Reagent.get_snippet_def(),
            snippet_def=OtherReagent.get_snippet_def(),
            detail_type='otherreagent_detail',
            table_name='db_otherreagent',
            query_number='query9')
        if(not is_authenticated): 
            sql += RESTRICTION_SQL
        sql += " UNION "
        sql += REAGENT_SEARCH_SQL.format(
            key_id='facility_id',
            reagent_snippet_def=Reagent.get_snippet_def(),
            snippet_def=Unclassified.get_snippet_def(),
            detail_type='unclassified_detail',
            table_name='db_unclassified',
            query_number='query10')
        if(not is_authenticated): 
            sql += RESTRICTION_SQL
        sql += " ORDER by type, rank DESC;"
        logger.info('search query: %r' % sql)
        cursor.execute(sql , 
                       [queryStringProcessed,queryStringProcessed,
                        queryStringProcessed,queryStringProcessed,
                        queryStringProcessed,queryStringProcessed,
                        queryStringProcessed,queryStringProcessed,
                        queryStringProcessed,queryStringProcessed,
                        queryStringProcessed])
        _data = dictfetchall(cursor)

        # perform (largely redundant) queries using the specific managers:
        # - to execute any specific search logic implemented in each manager
        # (e.g. batch fields)
        def add_specific_search_matches(specific_search_match_query,query_type):
            if len(specific_search_match_query) > 0:
                for obj in specific_search_match_query:
                    facility_id = obj.facility_id
                    if query_type == 'sm_detail':
                        facility_id = obj.facility_salt
                    skip = False
                    for x in _data:
                        if x['facility_id'] == facility_id: 
                            skip=True
                    if not skip:
                        _data.append(
                            {'id':obj.id,'facility_id':facility_id, 
                             'snippet': obj.snippet,
                             'type':query_type, 'rank':1})
        
        smqs = SmallMoleculeSearchManager().search(
            SmallMolecule.objects.all(), queryString, 
            is_authenticated=is_authenticated);
        add_specific_search_matches(smqs,'sm_detail')
        cqs = CellSearchManager().search(
            queryString, is_authenticated=is_authenticated);
        add_specific_search_matches(cqs,'cell_detail')
        pcqs = PrimaryCellSearchManager().search(
            queryString, is_authenticated=is_authenticated);
        add_specific_search_matches(pcqs,'primary_cell_detail')
        dcs = DiffCellSearchManager().search(
            queryString, is_authenticated=is_authenticated);
        add_specific_search_matches(dcs,'diff_cell_detail')
        ipscs = IpscSearchManager().search(
            queryString, is_authenticated=is_authenticated);
        add_specific_search_matches(ipscs,'ipsc_detail')
        escs = EsCellSearchManager().search(
            queryString, is_authenticated=is_authenticated);
        add_specific_search_matches(escs,'es_cell_detail')
        pqs = ProteinSearchManager().search(
            queryString, is_authenticated=is_authenticated)
        add_specific_search_matches(pqs,'protein_detail')
        aqs = AntibodySearchManager().search(
            queryString, is_authenticated=is_authenticated)
        add_specific_search_matches(aqs,'antibody_detail')
        oqs = OtherReagentSearchManager().search(
            queryString, is_authenticated=is_authenticated)
        add_specific_search_matches(oqs,'otherreagent_detail')
        ups = UnclassifiedSearchManager().search(
            queryString, is_authenticated=is_authenticated)
        add_specific_search_matches(ups,'unclassified_detail')

        return _data
