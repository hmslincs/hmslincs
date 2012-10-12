#from django.template import Context, loader
#from django.http import HttpResponse
from django.shortcuts import render_to_response
from django.shortcuts import render
from django.db import models
from django.db import connection
from django.forms.models import model_to_dict
from django.forms import ModelForm
from django.http import Http404
from django.utils.safestring import mark_safe
from django.http import HttpResponse

import csv
import xlwt
import logging
#from django.template import RequestContext
import django_tables2 as tables
from django_tables2 import RequestConfig
from django_tables2.utils import A  # alias for Accessor

from db.models import SmallMolecule, SmallMoleculeBatch, Cell, Protein, DataSet, Library
# --------------- View Functions -----------------------------------------------

logger = logging.getLogger(__name__)

facility_salt_id = " sm.facility_id || '-' || sm.salt_id " # Note: because we have a composite key for determining unique sm structures, we need to do this


def get_integer(stringValue):
    try:
        return int(float(stringValue))
    except:
        logger.debug(str(('stringValue: ',stringValue,'is not an integer')))
    return None    

def main(request):
    search = request.GET.get('search','')
    if(search != ''):
        queryset = SiteSearchManager().search(search);
        table = SiteSearchTable(queryset)
        RequestConfig(request, paginate={"per_page": 25}).configure(table)
        return render(request, 'db/index.html', {'table': table, 'search':search })
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
            where.append("not is_restricted")
        # postgres fulltext search with rank and snippets
        queryset = Cell.objects.extra(    # TODO: evaluate using django query language, not extra clause
            select={
                'snippet': "ts_headline(" + CellTable.snippet_def + ", plainto_tsquery(%s))",
                'rank': "ts_rank_cd(search_vector, plainto_tsquery(%s), 32)",
                },
            where=where,
            params=[search],
            select_params=[search,search],
            order_by=('-rank',)
            )        
    else:
        where = []
        if(not request.user.is_authenticated()): where.append("not is_restricted")
        queryset = Cell.objects.extra(
            where=where,
            order_by=('facility_id',))        
    table = CellTable(queryset)

    outputType = request.GET.get('output_type','')
    if(outputType != ''):
        return send_to_file(outputType, 'cells', table, queryset, request )
    
    RequestConfig(request, paginate={"per_page": 25}).configure(table)
    return render(request, 'db/listIndex.html', {'table': table, 'search':search })
    
def cellDetail(request, facility_id):
    try:
        cell = Cell.objects.get(facility_id=facility_id) # todo: cell here
        if(cell.is_restricted and not request.user.is_authenticated()):
            return HttpResponse('Log in required.', status=401)
    except Cell.DoesNotExist:
        raise Http404
    return render(request, 'db/cellDetail.html', {'object': CellForm(data=model_to_dict(cell))})

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
            where.append("not is_restricted")
        # postgres fulltext search with rank and snippets
        queryset = Protein.objects.extra(
            select={
                'snippet': "ts_headline(" + ProteinTable.snippet_def + ", plainto_tsquery(%s))",
                'rank': "ts_rank_cd(search_vector, plainto_tsquery(%s), 32)",
                },
            where=where,
            params=[search],
            select_params=[search,search],
            order_by=('-rank',)
            )        
    else:
        where = []
        if(not request.user.is_authenticated()): where.append("not is_restricted")
        queryset = Protein.objects.extra(
            where=where,
            order_by=('lincs_id',))        
    table = ProteinTable(queryset)

    outputType = request.GET.get('output_type','')
    if(outputType != ''):
        return send_to_file(outputType, 'proteins', table, queryset, request )
    
    RequestConfig(request, paginate={"per_page": 25}).configure(table)
    return render(request, 'db/listIndex.html', {'table': table, 'search':search })
    
def proteinDetail(request, lincs_id):
    try:
        protein = Protein.objects.get(lincs_id=lincs_id) # todo: cell here
        if(protein.is_restricted and not request.user.is_authenticated()):
            return HttpResponse('Log in required.', status=401)
    except Protein.DoesNotExist:
        raise Http404
    return render(request, 'db/proteinDetail.html', {'object': ProteinForm(data=model_to_dict(protein))})

def smallMoleculeIndex(request):
    search = request.GET.get('search','')
    queryset = SmallMoleculeSearchManager().search(search, is_authenticated=request.user.is_authenticated());
    table = SmallMoleculeTable(queryset)

    outputType = request.GET.get('output_type','')
    if(outputType != ''):
        return send_to_file(outputType, 'small_molecule', table, queryset, request )
    
    RequestConfig(request, paginate={"per_page": 25}).configure(table)
    return render(request, 'db/listIndex.html', {'table': table, 'search':search })
 
def smallMoleculeDetail(request, facility_salt_id):
    try:
        temp = facility_salt_id.split('-')
        logger.info(str(('find sm detail for', temp)))
        facility_id = temp[0]
        salt_id = temp[1]
        sm = SmallMolecule.objects.get(facility_id=facility_id, salt_id=salt_id) # TODO: create a sm detail link from facility-salt
        if(sm.is_restricted and not request.user.is_authenticated()):
            return HttpResponse('Log in required.', status=401)
    except SmallMolecule.DoesNotExist:
        raise Http404
    return render(request,'db/smallMoleculeDetail.html', {'object': SmallMoleculeForm(data=model_to_dict(sm))})

def libraryIndex(request):
    search = request.GET.get('search','')
    queryset = LibrarySearchManager().search(search, is_authenticated=request.user.is_authenticated());
    table = LibraryTable(queryset)

    outputType = request.GET.get('output_type','')
    if(outputType != ''):
        return send_to_file(outputType, 'libraries', table, queryset, request )
    
    RequestConfig(request, paginate={"per_page": 25}).configure(table)
    return render(request, 'db/listIndex.html', {'table': table, 'search':search })

def libraryDetail(request, short_name):
    try:
        library = Library.objects.get(short_name=short_name)
        if(library.is_restricted and not request.user.is_authenticated()):
            return HttpResponse('Unauthorized', status=401)
        queryset = SmallMoleculeSearchManager().search(library_id=library.id);
        table = SmallMoleculeTable(queryset)
    except Library.DoesNotExist:
        raise Http404
    return render(request,'db/libraryDetail.html', {'object': LibraryForm(data=model_to_dict(library)),
                                                         'table': table})

def studyIndex(request):
    return screenIndex(request, 'study' )

def screenIndex(request, type='screen'):
    search = request.GET.get('search','')
    logger.info(str(("is_authenticated:", request.user.is_authenticated(), 'search: ', search)))
    where = []
    if(type == 'screen'):
        where.append(" facility_id between 10000 and 20000 ")
    elif(type == 'study'):
        where.append(" facility_id between 300000 and 400000 ")
    if(search != ''):
        criteria = "search_vector @@ plainto_tsquery(%s)"
        if(get_integer(search) != None):
            criteria = '(' + criteria + ' OR facility_id='+str(get_integer(search)) + ')' # TODO: seems messy here
        where.append(criteria)
        if(not request.user.is_authenticated()): 
            where.append("not is_restricted")
            
        # postgres fulltext search with rank and snippets
        queryset = DataSet.objects.extra(
            select={
                'snippet': "ts_headline(" + DataSetTable.snippet_def + ", plainto_tsquery(%s) )",
                'rank': "ts_rank_cd(search_vector, plainto_tsquery(%s), 32)",
                },
            where=where,
            params=[search],
            select_params=[search,search],
            order_by=('-rank',)
            )        
        #logger.info( 'queryset: ' queryset
    else:
        if(not request.user.is_authenticated()): 
            where.append("not is_restricted")
        queryset = DataSet.objects.extra(
            where=where,
            order_by=('facility_id',))        
    table = DataSetTable(queryset)
    
    outputType = request.GET.get('output_type','')
    if(outputType != ''):
        return send_to_file(outputType, 'screenIndex', table, queryset, request )
        
    RequestConfig(request, paginate={"per_page": 25}).configure(table)
    
    return render(request, 'db/listIndex.html', {'table': table, 'search':search, 'type': type })

# Follows is a messy way to differentiate each tab for the screen detail page (each tab calls it's respective method)
def getDatasetType(facility_id):
    facility_id = int(facility_id)
    if(facility_id < 20000 and facility_id >=  10000 ):
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

    dataset_id = dataset.id
    
    cell_queryset = cells_for_dataset(dataset_id)
    cellTable = CellTable(cell_queryset)
    show_cells=len(cell_queryset)>0  # TODO pass in show_cells!

    protein_queryset = proteins_for_dataset(dataset_id)
    proteinTable = ProteinTable(protein_queryset)
    show_proteins=len(protein_queryset)>0 # TODO pass in show_proteins!

    # TODO: are the screen results gonna be searchable? (no, not for now, but if so, we would look at the search string here)
    # search = request.GET.get('search','')
    
    
    table = get_dataset_result_table(dataset_id, is_authenticated=request.user.is_authenticated(), **{'show_cells':show_cells, 'show_proteins':show_proteins})

    RequestConfig(request, paginate={"per_page": 25}).configure(table)
    RequestConfig(request, paginate={"per_page": 25}).configure(cellTable)
    RequestConfig(request, paginate={"per_page": 25}).configure(proteinTable)
    return {'object': DataSetForm(data=model_to_dict(dataset)),
           'table': table,
           'cellTable': cellTable,
           'proteinTable': proteinTable,
           'facilityId': facility_id,
           'type':getDatasetType(facility_id)}


def get_dataset_result_table(dataset_id, is_authenticated=False, **kwargs):
    """
    generate a django tables2 table
    TODO: move the logic out of the view: so that it can be shared with the tastypie api (or make this rely on tastypie)
    """
    if(not 'show_cells' in kwargs):
        cell_queryset = cells_for_dataset(dataset_id)
        show_cells=len(cell_queryset)>0  # TODO pass in show_cells!
    else:
        show_cells = kwargs['show_cells']
    
    if(not 'show_proteins' in kwargs):
        protein_queryset = proteins_for_dataset(dataset_id)
        show_proteins=len(protein_queryset)>0 # TODO pass in show_proteins!
    else:
        show_proteins = kwargs['show_proteins']
    #return get_dataset_result_queryset1(dataset_id,show_cells,show_proteins,is_authenticated)['table']

#def get_dataset_result_table(dataset_id, show_cells, show_proteins,is_authenticated=False):
#    return get_dataset_result_queryset1(dataset_id, show_cells, show_proteins,is_authenticated)['table']


#def get_dataset_result_queryset1(dataset_id, show_cells, show_proteins, is_authenticated=False):
        
    datacolumns = get_dataset_columns(dataset_id)
    # Create a query on the fly that pivots the values from the datapoint table, making one column for each datacolumn type
    # use the datacolumns to make a query on the fly (for the DataSetResultSearchManager), and make a DataSetResultSearchTable on the fly.
    #dataColumnCursor = connection.cursor()
    #dataColumnCursor.execute("SELECT id, name, data_type, precision from db_datacolumn where dataset_id = %s order by id asc", [dataset_id])
    logger.info(str(('dataset columns:', datacolumns)))

    # Need to construct something like this:
    # select distinct (datarecord_id), smallmolecule_id, sm.facility_id || '-' || sm.salt_id as facility_id,
    #        (select int_value as col1 from db_datapoint dp1 where dp1.datacolumn_id=2 and dp1.datarecord_id = dp0.datarecord_id) as col1, 
    #        (select int_value as col2 from db_datapoint dp2 where dp2.datarecord_id=dp0.datarecord_id and dp2.datacolumn_id=3) as col2 
    #        from db_datapoint dp0 join db_datarecord dr on(datarecord_id=dr.id) join db_smallmoleculebatch smb on(smb.id=dr.smallmolecule_batch_id) join db_smallmolecule sm on(sm.id=smb.smallmolecule_id) 
    #        where dp0.dataset_id = 1 order by datarecord_id;
    
    queryString = "select distinct (datarecord_id) as datarecord_id, sm.id as smallmolecule_id ,"
    queryString += " 'HMSL' || sm.facility_id || '-' || sm.salt_id || '-' || smb.facility_batch_id as facility_id, "
    queryString += facility_salt_id +' as facility_salt_id' # Note: because we have a composite key for determining unique sm structures, we need to do this

    if(show_cells): queryString += ", cell_id, cell.name as cell_name, cell.facility_id as cell_facility_id " 
    if(show_proteins): queryString += ", protein_id, protein.name as protein_name, protein.lincs_id as protein_lincs_id " 
    i = 0
    names = {}
    orderedNames = ['facility_id']
    for datacolumn_id, name, datatype, precision in datacolumns:
        i += 1
        alias = "dp"+str(i)
        columnName = "col" + str(i)
        names[columnName] = name
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
    queryString += " from db_datapoint dp0 join db_datarecord dr on(datarecord_id=dr.id) join db_smallmoleculebatch smb on(smb.id=dr.smallmolecule_batch_id) "
    queryString += " join db_smallmolecule sm on(smb.smallmolecule_id = sm.id) "
    if(show_cells): 
        queryString += " join db_cell cell on(cell.id=dr.cell_id) "
        orderedNames.insert(1,'cell_name')
    if(show_proteins): 
        queryString += " join db_protein protein on(protein.id=dr.protein_id) "
        orderedNames.insert(1,'protein_name')
    queryString += " where dp0.dataset_id = " + str(dataset_id)
    if(not is_authenticated): 
        queryString += " and not sm.is_restricted "
        if(show_proteins):
            queryString += " and not protein.is_restricted "
        if(show_cells):
            queryString += " and not cell.is_restricted " 
    queryString += " order by datarecord_id"
    orderedNames.append('...') # is this necessary?
    
    logger.info(str(('orderedNames',orderedNames)))
    logger.info(str(('names',names)))
    queryset = DataSetResultSearchManager().search(queryString);
    table = DataSetResultTable(queryset, names, orderedNames, show_cells, show_proteins)

    return table # todo, redo this, once the tastypie integration is figured out

#---------------Supporting classes and functions--------------------------------
def get_dataset_columns(dataset_id):
    # Create a query on the fly that pivots the values from the datapoint table, making one column for each datacolumn type
    # use the datacolumns to make a query on the fly (for the DataSetResultSearchManager), and make a DataSetResultSearchTable on the fly.
    dataColumnCursor = connection.cursor()
    dataColumnCursor.execute("SELECT id, name, data_type, precision from db_datacolumn where dataset_id = %s order by id asc", [dataset_id])
    return dataColumnCursor.fetchall()

def get_dataset_column_names(dataset_id):
    column_names = []
    for datacolumn_id, name, datatype, precision in get_dataset_columns(dataset_id):
        column_names.append(name)
    return column_names
    
def cells_for_dataset(dataset_id):
    cursor = connection.cursor()
    sql = 'select cell.* from db_cell cell where cell.id in (select distinct(cell_id) from db_datarecord dr where dr.dataset_id=%s) order by cell.name'
    cursor.execute(sql, [dataset_id])
    return dictfetchall(cursor)

def proteins_for_dataset(dataset_id):
    cursor = connection.cursor()
    sql = 'select protein.* from db_protein protein where protein.id in (select distinct(protein_id) from db_datarecord dr where dr.dataset_id=%s) order by protein.name'
    cursor.execute(sql, [dataset_id])
    return dictfetchall(cursor)

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
        

def get_text_fields(model):
    # Only text or char fields considered, must add numeric fields manually
    return filter(lambda x: isinstance(x, models.CharField) or isinstance(x, models.TextField), tuple(model._meta.fields))

class SmallMoleculeSearchManager(models.Manager):
    
    def search(self, query_string='', is_authenticated=False, library_id=None):
        query_string = query_string.strip()
        cursor = connection.cursor()
        sql = ( "select l.short_name as library_name, l.id as library_id," + facility_salt_id + " as facility_salt_id , sm.*, smb.id as smb_id, smb.* " +
            " from db_smallmolecule sm " +
            " left join db_smallmoleculebatch smb on(smb.smallmolecule_id=sm.id)" 
            " left join db_librarymapping lm on(smb.id=lm.smallmolecule_batch_id) " + 
            " left join db_library l on(lm.library_id=l.id) ")
        where = ''
        if(query_string != '' ):
            # TODO: how to include the smb snippet (once it's created)
            where = " sm.search_vector @@ query "
            if(get_integer(query_string) != None):
                where = '(' + where + ' OR sm.facility_id='+str(get_integer(query_string)) + ')' # TODO: seems messy here
            # TODO: search by facility-salt-batch
            where = ", to_tsquery(%s) as query  where " + where
        if(library_id != None):
            if(where != ''):
                where += ' and '
            else:
                where = ' where '
            where += 'library_id='+ str(library_id)
        if(not is_authenticated):
            if(where != ''):
                where += ' and '
            else:
                where = ' where '
            where += 'not sm.is_restricted' # TODO: NOTE, not including: ' and not l.is_restricted'; library restriction will only apply to viewing the library explicitly (the meta data, and selection of compounds)
            
        sql += where
        sql += " order by sm.facility_id, sm.salt_id, smb.facility_batch_id "
        
        # TODO: the way we are separating query_string out here is a kludge
        if(query_string != ''):
            cursor.execute(sql, [query_string + ':*'])
        else:
            cursor.execute(sql)
        v = dictfetchall(cursor)
        return v
    
class SmallMoleculeTable(tables.Table):
    facility_id = tables.LinkColumn("sm_detail", args=[A('facility_salt_id')]) # TODO: create a molecule link for facility/salt/batch ids
    rank = tables.Column()
    snippet = tables.Column()
    library_name = tables.LinkColumn('library_detail', args=[A('library_id')])
    
    facility_batch_id = tables.Column()
    
    provider = tables.Column()
    provider_catalog_id = tables.Column()
    provider_sample_id = tables.Column()
    
    # TODO:
    # chemical_synthesis_reference = tables.Column()
    # purity = tables.Column()
    # purity_method = tables.Column()
    
    
    snippet_def = (" || ' ' || ".join(map( lambda x: "coalesce("+x.name+",'') ", get_text_fields(SmallMolecule))))
    
    class Meta:
        model = SmallMolecule #[SmallMolecule, SmallMoleculeBatch]
        orderable = True
        attrs = {'class': 'paleblue'}
        sequence = ('facility_id', 'salt_id', 'facility_batch_id', 'name','library_name','...','smiles','inchi')
        exclude = ('id', 'smallmolecule_id','smallmolecule_batch_id','molfile','rank','snippet','is_restricted','lincs_id') 

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
    snippet_def = (" || ' ' || ".join(map( lambda x: "coalesce("+x.name+",'') ", get_text_fields(Cell))))
    class Meta:
        model = Cell
        orderable = True
        attrs = {'class': 'paleblue'}
        sequence = ('facility_id', '...')
        exclude = ('id','recommended_culture_conditions', 'verification_reference_profile', 'mutations_explicit', 'mutations_reference')
        
class CellForm(ModelForm):
    class Meta:
        model = Cell  
        
class ProteinTable(tables.Table):
    lincs_id = tables.LinkColumn("protein_detail", args=[A('lincs_id')])
    rank = tables.Column()
    snippet = SnippetColumn()
    snippet_def = (" || ' ' || ".join(map( lambda x: "coalesce("+x.name+",'') ", get_text_fields(Protein))))
    class Meta:
        model = Protein
        orderable = True
        attrs = {'class': 'paleblue'}
        sequence = ('lincs_id', '...')
        exclude = ('id')
        
class ProteinForm(ModelForm):
    class Meta:
        model = Protein        
        
class LibrarySearchManager(models.Manager):
    
    def search(self, query_string, is_authenticated=False):
        query_string = query_string.strip()
        cursor = connection.cursor()
        sql = ( "select a.*, library.* from ( SELECT count(well) as well_count , max(plate)-min(plate)+ 1 as plate_count, library.id " + 
            " from db_library library left join db_librarymapping on(library_id=library.id) ")
        where = ' where 1=1 '
        if(not is_authenticated):
            where += 'and not library.is_restricted '
        if(query_string != '' ):
            sql += ", to_tsquery(%s) as query  where " 
            where = "and library.search_vector @@ query "
        sql += where
        sql += " group by library.id) a join db_library library on(a.id=library.id)"
        
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
    name = tables.LinkColumn("library_detail", args=[A('short_name')])
    well_count = tables.Column()
    plate_count = tables.Column()
    rank = tables.Column()
    snippet = SnippetColumn()
    
    snippet_def = (" || ' ' || ".join(map( lambda x: "coalesce("+x.name+",'') ", get_text_fields(Library))))
    class Meta:
        orderable = True
        model = Library
        attrs = {'class': 'paleblue'}
        exclude = {'rank','snippet'}

    
class LibraryForm(ModelForm):
    class Meta:
        model = Library        
            
class SiteSearchManager(models.Manager):
    
    def search(self, queryString):
        cursor = connection.cursor()
        # TODO: build this dynamically, like the rest of the search
        # Notes: MaxFragments=10 turns on fragment based headlines (context for search matches), with MaxWords=20
        # ts_rank_cd(search_vector, query, 32): Normalization option 32 (rank/(rank+1)) can be applied to scale all 
        # ranks into the range zero to one, but of course this is just a cosmetic change; it will not affect the ordering of the search results.
        cursor.execute(
            "SELECT id, facility_id::text, ts_headline(" + CellTable.snippet_def + """, query1, 'MaxFragments=10, MinWords=1, MaxWords=20, FragmentDelimiter=" | "') as snippet, """ +
            " ts_rank_cd(search_vector, query1, 32) AS rank, 'cell_detail' as type FROM db_cell, to_tsquery(%s) as query1 WHERE search_vector @@ query1 " +
            " UNION " +
            " SELECT id, " + facility_salt_id + " as facility_id , ts_headline(" + SmallMoleculeTable.snippet_def + """, query2, 'MaxFragments=10, MinWords=1, MaxWords=20, FragmentDelimiter=" | "') as snippet, """ +
            " ts_rank_cd(search_vector, query2, 32) AS rank, 'sm_detail' as type FROM db_smallmolecule, to_tsquery(%s) as query2 WHERE search_vector @@ query2 " +
            " UNION " +
            " SELECT id, facility_id::text, ts_headline(" + DataSetTable.snippet_def + """, query3, 'MaxFragments=10, MinWords=1, MaxWords=20, FragmentDelimiter=" | "') as snippet, """ +
            " ts_rank_cd(search_vector, query3, 32) AS rank, 'screen_detail' as type FROM db_dataset, to_tsquery(%s) as query3 WHERE search_vector @@ query3 " +
            " UNION " +
            " SELECT id, lincs_id::text as facility_id, ts_headline(" + ProteinTable.snippet_def + """, query4, 'MaxFragments=10, MinWords=1, MaxWords=20, FragmentDelimiter=" | "') as snippet, """ +
            " ts_rank_cd(search_vector, query4, 32) AS rank, 'protein_detail' as type FROM db_protein, to_tsquery(%s) as query4 WHERE search_vector @@ query4 " +
            " ORDER by rank DESC;", [queryString + ":*", queryString + ":*", queryString + ":*", queryString + ":*"])
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

class DataSetTable(tables.Table):
    id = tables.Column(visible=False)
    facility_id = tables.LinkColumn("screen_detail", args=[A('facility_id')])
    protocol = tables.Column(visible=False) 
    references = tables.Column(visible=False)
    rank = tables.Column()
    snippet = SnippetColumn()
#    snippet_def = ("coalesce(facility_id,'') || ' ' || coalesce(title,'') || ' ' || coalesce(summary,'') || ' ' || coalesce(lead_screener_firstname,'') || ' ' || coalesce(lead_screener_lastname,'')|| ' ' || coalesce(lead_screener_email,'') || ' ' || "  +           
#                   "coalesce(lab_head_firstname,'') || ' ' || coalesce(lab_head_lastname,'')|| ' ' || coalesce(lab_head_email,'')")
    snippet_def = (" || ' ' || ".join(map( lambda x: "coalesce("+x.name+",'') ", get_text_fields(DataSet))))
    class Meta:
        model = DataSet
        orderable = True
        attrs = {'class': 'paleblue'}
        exclude = ('id') 

    def __init__(self, table):
        super(DataSetTable, self).__init__(table)

class DataSetForm(ModelForm):
    class Meta:
        model = DataSet  
        
class DataSetResultSearchManager(models.Manager):
    
    def search(self, queryString ): # TODO: pass the parameters for the SQL as well
        cursor = connection.cursor()
        logger.info( "queryString: "+ queryString)
        cursor.execute(queryString)

        return dictfetchall(cursor)
  
TEMPLATE = '''
   <a href="#" onclick='window.open("https://lincs-omero.hms.harvard.edu/webclient/img_detail/{{ record.%s }}", "test","height=700,width=800")' >{{ record.%s }}</a>
'''
            
class DataSetResultTable(tables.Table):
    id = tables.Column(visible=False)
    facility_id = tables.LinkColumn('sm_detail', args=[A('facility_salt_id')], verbose_name='Facility ID') #TODO: broken! must use facilty_id
    cell_name = tables.LinkColumn('cell_detail',args=[A('cell_facility_id')], visible=False, verbose_name='Cell Name') #TODO: broken! must use facility_id
    protein_name = tables.LinkColumn('protein_detail',args=[A('protein_lincs_id')], visible=False, verbose_name='Protein Name') #TODO: broken! must use facilty_id
    
    def __init__(self, queryset, names, orderedNames, show_cells, show_proteins, *args, **kwargs):
        super(DataSetResultTable, self).__init__(queryset, names, *args, **kwargs)
        # print "queryset: ", queryset , " , names: " , names, ", args: " , args
        for name,verbose_name in names.items():
        #    if name in omeroColumnNames:  #TODO: all the columns are currently in omeroColumnNames, figure out a way to not have them here if there's no omero well_id for that column
        #        self.base_columns[name] = tables.TemplateColumn(TEMPLATE % (omeroColumnNames[name],name), verbose_name=verbose_name)
        #    else:
            self.base_columns[name] = tables.Column(verbose_name=verbose_name)
        self.sequence = orderedNames
        if(show_cells):
            self.base_columns['cell_name'].visible = True
        if(show_proteins):
            self.base_columns['protein_name'].visible = True
        
    class Meta:
        orderable = True
        attrs = {'class': 'paleblue'}

def dictfetchall(cursor):
    "Returns all rows from a cursor as a dict"
    desc = cursor.description
    return [
        dict(zip([col[0] for col in desc], row)) for row in cursor.fetchall()
    ]

def send_to_file(outputType, name, table, queryset, request):
    columns = map(lambda (x,y): x, filter(lambda (x,y): x != 'rank' and x!= 'snippet' and y.visible, table.base_columns.items()))
    #print 'return as ', outputType, ", columns: ", columns 

    if(outputType == 'csv'):
        return export_as_csv(name,columns , request, queryset)
    elif(outputType == 'xls'):
        return export_as_xls(name, columns, request, queryset)
 
def export_as_xls(name,columnNames, request, queryset):
    """
    Generic xls export admin action.
    """
    response = HttpResponse(mimetype='application/Excel')
    response['Content-Disposition'] = 'attachment; filename=%s.xls' % unicode(name).replace('.', '_')
    
    wbk = xlwt.Workbook()
    sheet = wbk.add_sheet('sheet 1')    # Write a first row with header information
    for i, column in enumerate(columnNames):
        sheet.write(0, i, columnNames[i])
    # Write data rows
    for row,obj in enumerate(queryset):
        if isinstance(obj, dict):
            vals = [obj[field] for field in columnNames]
        else:
            vals = [getattr(obj, field) for field in columnNames]
        
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
    writer.writerow(columnNames)
    # Write data rows
    for obj in queryset:
        if isinstance(obj, dict):
            writer.writerow([obj[field] for field in columnNames])
        else:
            writer.writerow([getattr(obj, field) for field in columnNames])
    return response