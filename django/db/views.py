import os.path as op
#from django.template import Context, loader
#from django.http import HttpResponse
from django.core.exceptions import ObjectDoesNotExist,MultipleObjectsReturned
#from django.shortcuts import render_to_response
from django.shortcuts import render
from django.db import models
from django.db import connection
#from django.forms.models import model_to_dict
from django.forms import ModelForm
#from django.forms import Field
from django.http import Http404,HttpResponseRedirect
from django.utils.safestring import mark_safe
from django.http import HttpResponse
from django.conf import settings

import urllib2
import csv
import xlwt
#from django.template import RequestContext
import django_tables2 as tables
from django_tables2 import RequestConfig
from django_tables2.utils import A  # alias for Accessor

from db.models import SmallMolecule, SmallMoleculeBatch, Cell, Protein, DataSet, Library, FieldInformation,AttachedFile,DataRecord
from db.models import get_detail
from collections import OrderedDict

import logging

#from db.CustomQuerySet import CustomQuerySet

logger = logging.getLogger(__name__)
APPNAME = 'db',
COMPOUND_IMAGE_LOCATION = "compound-images-by-facility-salt-id"  
DATASET_IMAGE_LOCATION = "screen-images-by-facility-id" 
facility_salt_id = " sm.facility_id || '-' || sm.salt_id " # Note: because we have a composite key for determining unique sm structures, we need to do this
facility_salt_batch_id = facility_salt_id + " || '-' || smb.facility_batch_id " # Note: because we have a composite key for determining unique sm structures, we need to do this

from dump_obj import dumpObj
def dump(obj):
    dumpObj(obj)


# --------------- View Functions -----------------------------------------------

def get_integer(stringValue):
    try:
        return int(float(stringValue))
    except:
        logger.debug(str(('stringValue: ',stringValue,'is not an integer')))
    return None    

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
        criteria = "search_vector @@ plainto_tsquery(%s)"
        if(get_integer(search) != None):
            criteria = '(' + criteria + ' OR facility_id='+str(get_integer(search)) + ')' # TODO: seems messy here
        where = [criteria]
        if(not request.user.is_authenticated()): 
            where.append("( not is_restricted or is_restricted is NULL )")
        # postgres fulltext search with rank and snippets
        queryset = Cell.objects.extra(    # TODO: evaluate using django query language, not extra clause
            select={
                'snippet': "ts_headline(" + CellTable.snippet_def + ", plainto_tsquery(%s))",
                'rank': "ts_rank_cd(search_vector, plainto_tsquery(%s), 32)",
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
    table = CellTable(queryset)

    outputType = request.GET.get('output_type','')
    if(outputType != ''):
        return send_to_file(outputType, 'cells', table, queryset, request )
    
    RequestConfig(request, paginate={"per_page": 25}).configure(table)
    return render(request, 'db/listIndex.html', {'table': table, 'search':search, 'heading': 'Cells' })
    
def cellDetail(request, facility_id):
    try:
        cell = Cell.objects.get(facility_id=facility_id) # todo: cell here
        if(cell.is_restricted and not request.user.is_authenticated()):
            return HttpResponse('Log in required.', status=401)
    except Cell.DoesNotExist:
        raise Http404
    return render(request, 'db/cellDetail.html', {'object': get_detail(cell, ['cell',''])})

# TODO REFACTOR, DRY... 
def proteinIndex(request):
    search = request.GET.get('search','')
    logger.info(str(("is_authenticated:", request.user.is_authenticated(), 'search: ', search)))
    if(search != ''):
        criteria = "search_vector @@ plainto_tsquery(%s)"
        if(get_integer(search) != None):
            criteria = '(' + criteria + ' OR lincs_id='+str(get_integer(search)) + ')' # TODO: seems messy here
        where = [criteria]
        if(not request.user.is_authenticated()): 
            where.append("(not is_restricted or is_restricted is NULL)")
        # postgres fulltext search with rank and snippets
        queryset = Protein.objects.extra(
            select={
                'snippet': "ts_headline(" + ProteinTable.snippet_def + ", plainto_tsquery(%s))",
                'rank': "ts_rank_cd(search_vector, plainto_tsquery(%s), 32)",
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
    table = ProteinTable(queryset)

    outputType = request.GET.get('output_type','')
    if(outputType != ''):
        return send_to_file(outputType, 'proteins', table, queryset, request )
    
    RequestConfig(request, paginate={"per_page": 25}).configure(table)
    return render(request, 'db/listIndex.html', {'table': table, 'search':search, 'heading': 'Proteins' })
    
def proteinDetail(request, lincs_id):
    try:
        protein = Protein.objects.get(lincs_id=lincs_id) # todo: cell here
        if(protein.is_restricted and not request.user.is_authenticated()):
            return HttpResponse('Log in required.', status=401)
    except Protein.DoesNotExist:
        raise Http404
    return render(request, 'db/proteinDetail.html', {'object': get_detail(protein, ['protein',''])})

# TODO REFACTOR, DRY... 
def smallMoleculeIndex(request):
    search = request.GET.get('search','')
    logger.info(str(("is_authenticated:", request.user.is_authenticated(), 'search: ', search)))
    if(search != ''):
        criteria = "search_vector @@ to_tsquery(%s)"
        if(get_integer(search) != None):
            criteria = '(' + criteria + ' OR facility_id='+str(get_integer(search)) + ')' # TODO: seems messy here
        where = [criteria]
        if(not request.user.is_authenticated()): 
            where.append("(not is_restricted or is_restricted is NULL)")
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
        if(not request.user.is_authenticated()): where.append("(not is_restricted or is_restricted is NULL)")
        queryset = SmallMolecule.objects.extra(
            where=where,
            order_by=('facility_id','salt_id'))        
    table = SmallMoleculeTable(queryset)

    outputType = request.GET.get('output_type','')
    if(outputType != ''):
        return send_to_file(outputType, 'small_molecule', table, queryset, request )
    
    RequestConfig(request, paginate={"per_page": 25}).configure(table)
    return render(request, 'db/listIndex.html', {'table': table, 'search':search, 'heading': 'Small molecules' })

#def smallMoleculeIndex(request):
#    search = request.GET.get('search','')
#    queryset = SmallMoleculeSearchManager().search(search, is_authenticated=request.user.is_authenticated());
#    table = SmallMoleculeTable(queryset)
#
#    outputType = request.GET.get('output_type','')
#    if(outputType != ''):
#        return send_to_file(outputType, 'small_molecule', table, queryset, request )
#    
#    RequestConfig(request, paginate={"per_page": 25}).configure(table)
#    return render(request, 'db/listIndex.html', {'table': table, 'search':search })

def can_access_image(request, image_filename):
    #dump(settings)
    url = request.build_absolute_uri(settings.STATIC_URL + image_filename)
    logger.info(str(('try to open url',url))) 
    try:
        response = urllib2.urlopen(url)
        response.read()
        #response.close() # TODO - is this needed?!
        return True
    except Exception,e:
        logger.info(str(('no image found at', url, e)))
    return False
       
def smallMoleculeDetail(request, facility_salt_id): # TODO: let urls.py grep the facility and the salt
    try:
        temp = facility_salt_id.split('-') # TODO: let urls.py grep the facility and the salt
        logger.info(str(('find sm detail for', temp)))
        facility_id = temp[0]
        salt_id = temp[1]
        sm = SmallMolecule.objects.get(facility_id=facility_id, salt_id=salt_id) 
        if(sm.is_restricted and not request.user.is_authenticated()):
            return HttpResponse('Log in required.', status=401)
        smb = None
        if(len(temp)>2):
            smb = SmallMoleculeBatch.objects.get(smallmolecule=sm,facility_batch_id=temp[2]) 
        
    
        details = {'object': get_detail(sm, ['smallmolecule',''])}
        
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
        
        
        image_location = COMPOUND_IMAGE_LOCATION + '/HMSL%d-%d.png' % (sm.facility_id,sm.salt_id)
        if(can_access_image(request,image_location)): details['image_location'] = image_location
        return render(request,'db/smallMoleculeDetail.html', details)

    except SmallMolecule.DoesNotExist:
        raise Http404


    
def get_attached_files(facility_id, salt_id=None, batch_id=None):
    return AttachedFile.objects.filter(facility_id_for=facility_id, salt_id_for=salt_id, batch_id_for=batch_id)

def libraryIndex(request):
    search = request.GET.get('search','')
    queryset = LibrarySearchManager().search(search, is_authenticated=request.user.is_authenticated());
    table = LibraryTable(queryset)

    outputType = request.GET.get('output_type','')
    if(outputType != ''):
        return send_to_file(outputType, 'libraries', table, queryset, request )
    
    RequestConfig(request, paginate={"per_page": 25}).configure(table)
    return render(request, 'db/listIndex.html', {'table': table, 'search':search, 'heading': 'Libraries' })

def libraryDetail(request, short_name):
    try:
        library = Library.objects.get(short_name=short_name)
        if(library.is_restricted and not request.user.is_authenticated()):
            return HttpResponse('Unauthorized', status=401)
        response_dict = {'object': get_detail(library, ['library',''])}
        queryset = LibraryMappingSearchManager().search(is_authenticated=request.user.is_authenticated,library_id=library.id);
        if(len(queryset)>0): 
            table = LibraryMappingTable(queryset)
            RequestConfig(request, paginate={"per_page": 25}).configure(table)
            response_dict['table']=table
        return render(request,'db/libraryDetail.html', response_dict)
    except Library.DoesNotExist:
        raise Http404



def studyIndex(request):
    return screenIndex(request, 'study' )

def screenIndex(request, type='screen'):
    search = request.GET.get('search','')
    logger.info(str(("is_authenticated:", request.user.is_authenticated(), 'search: ', search)))
    where = []
    if(type == 'screen'):
        where.append(" facility_id between 10000 and 30000 ")
    elif(type == 'study'):
        where.append(" facility_id between 300000 and 400000 ")
    if(search != ''):
        criteria = "search_vector @@ plainto_tsquery(%s)"
        if(get_integer(search) != None):
            criteria = '(' + criteria + ' OR facility_id='+str(get_integer(search)) + ')' # TODO: seems messy here
        where.append(criteria)
        if(not request.user.is_authenticated()): 
            where.append("(not is_restricted or is_restricted is NULL)")
            
        # postgres fulltext search with rank and snippets
        queryset = DataSet.objects.extra(
            select={
                'snippet': "ts_headline(" + DataSetTable.snippet_def + ", plainto_tsquery(%s) )",
                'rank': "ts_rank_cd(search_vector, plainto_tsquery(%s), 32)",
                },
            where=where,
            params=[search+":*"],
            select_params=[search,search],
            order_by=('-rank',)
            )        
        #logger.info( 'queryset: ' queryset
    else:
        if(not request.user.is_authenticated()): 
            where.append("(not is_restricted or is_restricted is NULL)")
        queryset = DataSet.objects.extra(
            where=where,
            order_by=('facility_id',))        
    table = DataSetTable(queryset)
    
    outputType = request.GET.get('output_type','')
    if(outputType != ''):
        return send_to_file(outputType, 'screenIndex', table, queryset, request )
        
    RequestConfig(request, paginate={"per_page": 25}).configure(table)

    heading = type[0].upper() + type[1:]
    if heading[-1] == 'y':
        heading = heading[:-1] + 'ies'
    else:
        heading = heading + 's'

    return render(request, 'db/listIndex.html', {'table': table, 'search':search, 'type': type, 'heading': heading })

# Follows is a messy way to differentiate each tab for the screen detail page (each tab calls it's respective method)
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

def screenDetailMain(request, facility_id):
    try:
        details = screenDetail(request,facility_id)
        return render(request,'db/screenDetailMain.html', details )
    except Http401, e:
        return HttpResponse('Unauthorized', status=401)
def screenDetailCells(request, facility_id):
    try:
        details = screenDetail(request,facility_id)
        return render(request,'db/screenDetailCells.html', details)
    except Http401, e:
        return HttpResponse('Unauthorized', status=401)
def screenDetailProteins(request, facility_id):
    try:
        details = screenDetail(request,facility_id)
        return render(request,'db/screenDetailProteins.html', details)
    except Http401, e:
        return HttpResponse('Unauthorized', status=401)
def screenDetailResults(request, facility_id):
    try:
        details = screenDetail(request,facility_id)

        outputType = request.GET.get('output_type','')
        if(outputType != ''):
            table = details['table']
            return send_to_file(outputType, 'dataset_'+str(facility_id), table, table.data, request )

        return render(request,'db/screenDetailResults.html', details)
    except Http401, e:
        return HttpResponse('Unauthorized', status=401)

def screenDetail(request, facility_id):
    try:
        dataset = DataSet.objects.get(facility_id=facility_id)
        if(dataset.is_restricted and not request.user.is_authenticated()):
            raise Http401
    except DataSet.DoesNotExist:
        raise Http404

    # TODO: remove this and use left join in manager
    manager = DataSetManager(dataset)

    cellTable = None
    if(manager.has_cells()):
        cellTable = CellTable(manager.cell_queryset)
        RequestConfig(request, paginate={"per_page": 25}).configure(cellTable)
    proteinTable = None
    if(manager.has_proteins()):
        proteinTable = ProteinTable(manager.protein_queryset)
        RequestConfig(request, paginate={"per_page": 25}).configure(proteinTable)

    # TODO: are the screen results gonna be searchable? (no, not for now, but if so, we would look at the search string here)
    # search = request.GET.get('search','')
    
    table = manager.get_table(request.user.is_authenticated())
    RequestConfig(request, paginate={"per_page": 25}).configure(table)
    
    details =  {'object': get_detail(manager.dataset, ['dataset','']),
                'table': table,
                'cellTable': cellTable,
                'proteinTable': proteinTable,
                'facilityId': facility_id,
                'type':getDatasetType(facility_id)}

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
        elif value == "screen_detail": return "Screen"
        elif value == "protein_detail": return "Protein"
        else: raise Exception("Unknown type: "+value)
        
        

class DataSetTable(tables.Table):
    id = tables.Column(visible=False)
    facility_id = tables.LinkColumn("screen_detail", args=[A('facility_id')])
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
    
        
class DataSetResultTable(tables.Table):
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
    defined_base_columns.append('facility_salt_batch')
    set_field_information_to_table_column('facility_salt_batch', ['smallmoleculebatch'], facility_salt_batch)
    
    cell_name = tables.LinkColumn('cell_detail',args=[A('cell_facility_id')], visible=False, verbose_name='Cell Name') 
    defined_base_columns.append('cell_name')
    set_field_information_to_table_column('name', ['cell'], cell_name)
    
    protein_name = tables.LinkColumn('protein_detail',args=[A('protein_lincs_id')], visible=False, verbose_name='Protein Name') 
    defined_base_columns.append('protein_name')
    set_field_information_to_table_column('name', ['protein'], protein_name)
    
    plate = tables.Column()
    defined_base_columns.append('plate')
    set_field_information_to_table_column('plate', ['datarecord'], plate)
    well = tables.Column()
    defined_base_columns.append('well')
    set_field_information_to_table_column('well', ['datarecord'], well)
    
    control_type = tables.Column()
    defined_base_columns.append('control_type')
    set_field_information_to_table_column('control_type', ['datarecord'], control_type)
    
    # OMERO Image: TODO: only include this if the dataset has images
    TEMPLATE = '''
       <a href="#" onclick='window.open("https://lincs-omero.hms.harvard.edu/webclient/img_detail/{{ record.%s }}", "test","height=700,width=800")' ><img src='https://lincs-omero.hms.harvard.edu/webgateway/render_thumbnail/{{ record.%s }}/32/' alt='image if available' ></a>
    '''
    logger.debug(str(('omero_image column template', TEMPLATE % ('omero_image_id','omero_image_id'))))
    omero_image_id = tables.TemplateColumn(TEMPLATE % ('omero_image_id','omero_image_id'))
    defined_base_columns.append('omero_image_id')
    set_field_information_to_table_column('omero_image_id', ['datarecord'], omero_image_id)
    
    class Meta:
        orderable = True
        attrs = {'class': 'paleblue'}
    
    def __init__(self, queryset, names_to_columns, ordered_names, show_cells, show_proteins, has_omero_images, *args, **kwargs):
        # Follows is to deal with a bug - columns from one table appear to be injecting into other tables!!
        # This indicates that we are doing something wrong here by defining columns dynamically on the class "base_columns" attribute
        # So, to fix, we should redefine all of the base_columns every time here.  
        # For now, what is done is the "defined_base_columns" are preserved, then others are added.
        for name in self.base_columns.keys():
            if name not in self.defined_base_columns:
                logger.warn(str(('deleting column from the table', name)))
                del self.base_columns[name]
        
        temp = ['facility_salt_batch','plate','well','control_type']
        if(show_cells): temp.append('cell_name')
        if(show_proteins): temp.append('protein_name')
        temp.extend(ordered_names)
        ordered_names = temp
        
        logger.debug(str(('names_to_columns', names_to_columns, 'orderedNames', ordered_names)))
        for name,verbose_name in names_to_columns.items():
            logger.debug(str(('create column:',name,verbose_name)))
            self.base_columns[name] = tables.Column(verbose_name=verbose_name)
        
        # Note: since every instance reuses the base_columns, each time the visibility must be set.
        if(show_cells):
            self.base_columns['cell_name'].visible = True
        else:
            self.base_columns['cell_name'].visible = False
        if(show_proteins):
            self.base_columns['protein_name'].visible = True
        else:
            self.base_columns['protein_name'].visible = False
        self.base_columns['omero_image_id'].visible=has_omero_images
        logger.debug(str(('base columns:', self.base_columns)))
        # Field information section: TODO: for the datasetcolumns, use the database information for these.
        # set_table_column_info(self, ['smallmolecule','cell','protein',''])  

        # TODO: why does this work with the super call last?  Keep an eye on forums for creating dynamic columns with tables2
        # for instance: https://github.com/bradleyayers/django-tables2/issues/70
        super(DataSetResultTable, self).__init__(queryset, *args, **kwargs)
        self.sequence = ordered_names


# NOTE: this class doesn't have to override models.Manager, since it won't be used on 
# a particular model.
class DataSetManager():

    #exclude_detail = ('lead_screener_firstname','lead_screener_lastname','lead_screener_email') 
    
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
    
    def get_table(self, is_authenticated=False):
        
        dataset_info = self._get_query_info(is_authenticated)
        cursor = connection.cursor()
        cursor.execute(dataset_info.query_sql)
        # TODO: all dictfetchall calls to be replaced with pageable cursor implementation
    
        queryset = dictfetchall(cursor)
        #queryset = manager.get_dataset_result_table(dataset_id, is_authenticated=request.user.is_authenticated(), **{'show_cells':show_cells, 'show_proteins':show_proteins})
        return DataSetResultTable(queryset, dataset_info.columns_to_names, dataset_info.ordered_names, self.has_cells(), self.has_proteins(),self.has_omero_images(self.dataset_id))
    
    class DatasetInfo:
        names_to_columns = {}
        ordered_names = []
        query_sql = ''
    
    def _get_query_info(self, is_authenticated=False):
        """
        generate a django tables2 table
        TODO: move the logic out of the view: so that it can be shared with the tastypie api (or make this rely on tastypie)
        """
    
        datacolumns = self.get_dataset_columns(self.dataset.id)
        # Create a query on the fly that pivots the values from the datapoint table, making one column for each datacolumn type
        # use the datacolumns to make a query on the fly (for the DataSetManager), and make a DataSetResultSearchTable on the fly.
        #dataColumnCursor = connection.cursor()
        #dataColumnCursor.execute("SELECT id, name, data_type, precision from db_datacolumn where dataset_id = %s order by id asc", [dataset_id])
        logger.debug(str(('dataset columns:', datacolumns)))
    
        # Need to construct something like this:
        # select distinct (datarecord_id), smallmolecule_id, sm.facility_id || '-' || sm.salt_id as facility_id,
        #        (select int_value as col1 from db_datapoint dp1 where dp1.datacolumn_id=2 and dp1.datarecord_id = dp0.datarecord_id) as col1, 
        #        (select int_value as col2 from db_datapoint dp2 where dp2.datarecord_id=dp0.datarecord_id and dp2.datacolumn_id=3) as col2 
        #        from db_datapoint dp0 join db_datarecord dr on(datarecord_id=dr.id) join db_smallmoleculebatch smb on(smb.id=dr.smallmolecule_batch_id) join db_smallmolecule sm on(sm.id=smb.smallmolecule_id) 
        #        where dp0.dataset_id = 1 order by datarecord_id;
        queryString =   "select distinct (datarecord_id) as datarecord_id, sm.id as smallmolecule_id ,"
        queryString +=  facility_salt_batch_id +' as facility_salt_batch' # Note: because we have a composite key for determining unique sm structures, we need to do this
        queryString +=  ', plate, well, control_type, omero_image_id '
        show_cells = self.has_cells()
        show_proteins = self.has_proteins()
        if(show_cells): queryString += ", cell_id, cell.name as cell_name, cell.facility_id as cell_facility_id " 
        if(show_proteins): queryString += ", protein_id, protein.name as protein_name, protein.lincs_id as protein_lincs_id " 
        i = 0
        columns_to_names = {}
        orderedNames = []
        for datacolumn_id, name, datatype, precision in datacolumns:
            i += 1
            alias = "dp"+str(i)
            columnName = "col" + str(i)
            columns_to_names[columnName] = name
            orderedNames.append(columnName)
            column_to_select = None
            if(datatype == 'Numeric'):
                if precision == 0:
                    column_to_select = "int_value"
                else:
                    column_to_select = "float_value"
            else:
                column_to_select = "text_value"
            # TODO: use params
            queryString +=  (",(select " + column_to_select + " from db_datapoint " + alias + 
                                " where " + alias + ".datacolumn_id="+str(datacolumn_id) + " and " + alias + ".datarecord_id=dp0.datarecord_id) as " + columnName )
        queryString += " from db_datapoint dp0 join db_datarecord dr on(datarecord_id=dr.id) "
        # LEAVE LM out, so can also serve un-mapped studies  queryString += " join db_librarymapping lm on(dr.librarymapping_id=lm.id) "
        queryString += " left join db_smallmoleculebatch smb on(smb.id=dr.smallmolecule_batch_id) "
        queryString += " left join db_smallmolecule sm on(smb.smallmolecule_id = sm.id) "
        if(self.has_cells()): 
            queryString += " left join db_cell cell on(cell.id=dr.cell_id) " # TODO: change to left join
            # orderedNames.insert(1,'cell_name')
        if(self.has_proteins()): 
            queryString += " left join db_protein protein on(protein.id=dr.protein_id) " # TODO: change to left join
            # orderedNames.insert(1,'protein_name')
        queryString += " where dp0.dataset_id = " + str(self.dataset.id)
        if(not is_authenticated): 
            queryString += " and ( not sm.is_restricted or sm.is_restricted is NULL)"
            if(show_proteins):
                queryString += " and (not protein.is_restricted or protein.is_restricted is NULL) "
            if(show_cells):
                queryString += " and (not cell.is_restricted or cell.is_restricted is NULL)" 
        queryString += " order by datarecord_id"
        queryString += " LIMIT 10000 " # TODO - figure out how to paginate
        # orderedNames.append('...') # is this necessary?
        
        logger.info(str(('orderedNames',orderedNames)))
        logger.info(str(('columns_to_names',columns_to_names)))
    
        if(logger.isEnabledFor(logging.DEBUG)): logger.debug( "queryString: "+ queryString)
        
        dataset_info = self.DatasetInfo()
        dataset_info.columns_to_names = columns_to_names
        dataset_info.ordered_names = orderedNames
        dataset_info.query_sql = queryString
        
        return dataset_info
   

    #---------------Supporting classes and functions--------------------------------
    def get_dataset_columns(self, dataset_id):
        # Create a query on the fly that pivots the values from the datapoint table, making one column for each datacolumn type
        # use the datacolumns to make a query on the fly (for the DataSetManager), and make a DataSetResultSearchTable on the fly.
        dataColumnCursor = connection.cursor()
        dataColumnCursor.execute("SELECT id, name, data_type, precision from db_datacolumn where dataset_id = %s order by id asc", [dataset_id])
        return dataColumnCursor.fetchall()
    
    def get_dataset_column_names(self,dataset_id):
        column_names = []
        for datacolumn_id, name, datatype, precision in self.get_dataset_columns(dataset_id):
            column_names.append(name)
        return column_names
         
    def cells_for_dataset(self, dataset_id):
        cursor = connection.cursor()
        sql = 'select cell.* from db_cell cell where cell.id in (select distinct(cell_id) from db_datarecord dr where dr.dataset_id=%s) order by cell.name'
        # TODO: like this: SELECT * FROM TABLE, (SELECT COLUMN FROM TABLE) as dummytable WHERE dummytable.COLUMN = TABLE.COLUMN;
        cursor.execute(sql, [dataset_id])
        return dictfetchall(cursor)
        
    def proteins_for_dataset(self,dataset_id):
        cursor = connection.cursor()
        sql = 'select protein.* from db_protein protein where protein.id in (select distinct(protein_id) from db_datarecord dr where dr.dataset_id=%s) order by protein.name'
        cursor.execute(sql, [dataset_id])
        return dictfetchall(cursor)
    
    def has_omero_images(self, dataset_id):
        res= len(DataRecord.objects.all().filter(dataset_id=dataset_id).filter(omero_image_id__isnull=False))>0
        logger.info(str(('len(DataRecord.objects.all().filter(dataset_id=dataset_id).filter(omero_image_id__isnull=False))',len(DataRecord.objects.all().filter(dataset_id=dataset_id).filter(omero_image_id__isnull=False)))))
        return res

# TODO: create a QuerySet that can paginate through an arbitrary sql (for the dataset results)
#from django.db.models.query import QuerySet
#class CustomQS(QuerySet):
#    def __init__(self,querySet,model=None,query=None,*args, **kwargs):
#        self.querySet=querySet
#        logger.info(str((args,kwargs)))
#        super(CustomQS,self).__init__(*args,**kwargs)
#        
#    def count(self):
#        logger.info(str(('count')))
#        return 100;
#    
#    def __len__(self):
#        logger.info('len')
#        return self.count()
#    
#    def __getitem__(self,key):
#        # key should be a slice or an int
#        # see django.db.models.query.QuerySet for guidance on implementation
#        logger.info(str(('__getitem__',key)))
#        return [key] # this should look like a row?
#    
#def screenTest(request, facility_id):
#    dataset_id = 1
#    #queryset = CustomQuerySet('select dr.*, ds.title as title from db_datarecord dr join db_dataset ds on(dr.dataset_id=ds.id) where dr.dataset_id = 1')
#    #queryset = Cell.objects.all();
#    queryset = CustomQS(DataRecord.objects.all())
#    table = ScreenTestTable(queryset)
#    table.paginate(page=request.GET.get('page', 1), per_page=25)
#    #RequestConfig(request, paginate={"per_page": 25}).configure(table)
#    return render(request, 'db/listIndex.html', {'table': table })
#
#
#class ScreenTestTable(tables.Table):
#    test = tables.Column()
#    
#    class Meta:
#        #model = DataRecord
#        orderable = True
#        attrs = {'class': 'paleblue'}
#
#    def __init__(self, table, *args, **kwargs):
#        super(ScreenTestTable, self).__init__(table)

def find_datasets_for_smallmolecule(smallmolecule_id):
    datasets = [x.id for x in DataSet.objects.filter(datarecord__smallmolecule_batch__smallmolecule__id=smallmolecule_id).distinct()]
    logger.info(str(('datasets',datasets)))
    return datasets
    #    cursor = connection.cursor()
    #    sql = ( 'select distinct(dataset_id) from db_datarecord dr' +  
    #            ' join db_smallmoleculebatch smb on(dr.smallmolecule_batch_id=smb.id) ' + 
    #            ' where smb.smallmolecule_id=%s' )
    #    cursor.execute(sql, [smallmolecule_id])
    #    dataset_ids = [];
    #    for val in cursor.fetchall():
    #        logger.info(str(('val',val)))
    #        dataset_ids.append(val[0])
    #        
    #    return dataset_ids
    
        
class LibraryMappingSearchManager(models.Model):
    """
    Used for librarymapping display
    """
    def search(self, query_string='', is_authenticated=False, library_id=None):
        if(library_id == None): 
            raise Exception('Must define a library id to use the LibraryMappingSearchManager')

        query_string = query_string.strip()
        cursor = connection.cursor()
        
#        sql = "select l.short_name, l.id as library_id," + facility_salt_batch_id + " as facility_salt , sm.*, smb.id as smb_id, smb.* " # TODO: remove the _id columns, not needed
#        sql += (" from db_smallmolecule sm " +
#            " left join db_smallmoleculebatch smb on(smb.smallmolecule_id=sm.id)" 
#            " left join db_librarymapping lm on(smb.id=lm.smallmolecule_batch_id) " + 
#            " left join db_library l on(lm.library_id=l.id) ")
        sql = "select " + facility_salt_batch_id + " as facility_salt_batch , sm.*, smb.*, lm.* "
        sql += " from db_library l "
        sql += " join db_librarymapping lm on(lm.library_id=l.id) " 
        sql += " left join db_smallmoleculebatch smb on (smb.id=lm.smallmolecule_batch_id) "
        sql += " left join db_smallmolecule sm on(smb.smallmolecule_id=sm.id) " 
        
#        sql += " from db_smallmolecule sm " 
#        sql += (" left join db_smallmoleculebatch smb on(smb.smallmolecule_id=sm.id) ") 
#        sql += (" left join db_librarymapping lm on(smb.id=lm.smallmolecule_batch_id) " + 
#                " left join db_library l on(lm.library_id=l.id) ")

        where = ' where 1=1 '
        if(query_string != '' ):
            # TODO: how to include the smb snippet (once it's created)
            where += " and sm.search_vector @@ query "
            if(get_integer(query_string) != None):
                where = '(' + where + ' OR sm.facility_id='+str(get_integer(query_string)) + ')' # TODO: seems messy here
            # TODO: search by facility-salt-batch
            where = ", to_tsquery(%s) as query  where " + where
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
        if(query_string != ''):
            cursor.execute(sql, [query_string + ':*'])
        else:
            cursor.execute(sql)
        v = dictfetchall(cursor)
        return v
    
class SmallMoleculeBatchTable(tables.Table):
    
    facility_salt_batch = tables.LinkColumn("sm_detail", args=[A('facility_salt_batch')])
    
    class Meta:
        model = SmallMoleculeBatch
        orderable = True
        attrs = {'class': 'paleblue'}

    def __init__(self, table, show_plate_well=False,*args, **kwargs):
        super(SmallMoleculeBatchTable, self).__init__(table)
        sequence_override = ['facility_salt_batch']
        set_table_column_info(self, ['smallmolecule','smallmoleculebatch',''],sequence_override)  

class SmallMoleculeTable(tables.Table):
    facility_salt = tables.LinkColumn("sm_detail", args=[A('facility_salt')]) 
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

class AttachedFileTable(tables.Table):
    filename=tables.LinkColumn("download_attached_file", args=[A('filename')])
    #snippet_def = (" || ' ' || ".join(map( lambda x: "coalesce("+x.field+",'') ", FieldInformation.manager.get_search_fields(SmallMolecule)))) # TODO: specialized search for librarymapping, if needed
    
    class Meta:
        model = AttachedFile
        orderable = True
        attrs = {'class': 'paleblue'}
        
    def __init__(self, table,*args, **kwargs):
        super(AttachedFileTable, self).__init__(table)
        sequence_override = []
        set_table_column_info(self, ['attachedfile',''],sequence_override)  
        
class LibraryMappingTable(tables.Table):
    facility_salt_batch = tables.LinkColumn("sm_detail", args=[A('facility_salt_batch')]) 
    is_control = tables.Column() 
    well = tables.Column()
    plate = tables.Column()
    concentration = tables.Column()
    concentration_unit = tables.Column()
        
    snippet_def = (" || ' ' || ".join(map( lambda x: "coalesce("+x.field+",'') ", FieldInformation.manager.get_search_fields(SmallMolecule)))) # TODO: specialized search for librarymapping, if needed
    
    class Meta:
        model = SmallMoleculeBatch
        orderable = True
        attrs = {'class': 'paleblue'}
        
    def __init__(self, table, show_plate_well=False,*args, **kwargs):
        super(LibraryMappingTable, self).__init__(table)
        sequence_override = ['facility_salt_batch']
        
        set_table_column_info(self, ['smallmolecule','smallmoleculebatch','librarymapping',''],sequence_override)  
            
class SmallMoleculeForm(ModelForm):
    class Meta:
        model = SmallMolecule           
        order = ('facility_id', '...')
        exclude = ('id', 'molfile') 

class CellTable(tables.Table):
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
    def __init__(self, table):
        super(CellTable, self).__init__(table)
        sequence_override = ['facility_id']    
        set_table_column_info(self, ['cell',''], sequence_override)  
                        
class ProteinTable(tables.Table):
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
        sql = ( "select a.*, library.* from ( SELECT count(well) as well_count , max(plate)-min(plate)+ 1 as plate_count, library.id " + 
            " from db_library library left join db_librarymapping on(library_id=library.id) ")
        where = ' where 1=1 '
        if(not is_authenticated):
            where += 'and (not library.is_restricted or library.is_restricted is NULL) '
        if(query_string != '' ):
            sql += ", to_tsquery(%s) as query  " 
            where += "and library.search_vector @@ query "
        sql += where
        sql += " group by library.id) a join db_library library on(a.id=library.id)"
        
        logger.info(str(('sql',sql)))
        # TODO: the way we are separating query_string out here is a kludge
        if(query_string != ''):
            cursor.execute(sql, [query_string + ':*'])
        else:
            cursor.execute(sql)
        v = dictfetchall(cursor)
        #print 'dict: ', v, ', query: ', query_string
        return v
    
class LibraryTable(tables.Table):
    id = tables.Column(visible=False)
    short_name = tables.LinkColumn("library_detail", args=[A('short_name')])
    well_count = tables.Column()
    plate_count = tables.Column()
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
                " ts_rank_cd(search_vector, query3, 32) AS rank, 'screen_detail' as type FROM db_dataset, to_tsquery(%s) as query3 WHERE search_vector @@ query3 " )
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

class SiteSearchTable(tables.Table):
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
    logger.info(str(('fields',fields)))
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

def download_attached_file(request, path):
    # TODO Authorization
    dump(request.user)
    logger.info(str(('download_attached_file',path,request.user)))
    if(request.user.is_authenticated()):
        pass
    return HttpResponseRedirect("/_static/"+path)
        
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
    for row,obj in enumerate(queryset):
        if isinstance(obj, dict):
            vals = [obj[field] for (field,verbose_name) in columnNames]
        else:
            vals = [getattr(obj, field) for (field,verbose_name) in columnNames]
        
        for i,column in enumerate(vals):
            sheet.write(row+1, i, column )
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
    for obj in queryset:
        if isinstance(obj, dict):
            writer.writerow([obj[field] for (field,verbose_name) in columnNames])
        else:
            writer.writerow([getattr(obj, field) for (field,verbose_name) in columnNames])
    return response
