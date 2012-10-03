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

from db.models import SmallMolecule, Cell, Protein, DataSet, Library
# --------------- View Functions -----------------------------------------------

logger = logging.getLogger(__name__)

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
    if(search != ''):
        logger.error("s: %s" % search)
# basic postgres fulltext search        
#        queryset = Cell.objects.extra(
#            where=['search_vector @@ plainto_tsquery(%s)'], 
#            params=[search])
 
# postgres fulltext search with rank and snippets
        queryset = Cell.objects.extra(
            select={
                'snippet': "ts_headline(" + CellTable.snippet_def + ", plainto_tsquery(%s))",
                'rank': "ts_rank_cd(search_vector, plainto_tsquery(%s), 32)",
                },
            where=["search_vector @@ plainto_tsquery(%s)"],
            params=[search],
            select_params=[search,search],
            order_by=('-rank',)
            )        
        logger.info("found: %s" % CellTable.snippet_def)
    else:
        queryset = Cell.objects.all().order_by('facility_id')
    table = CellTable(queryset)

    outputType = request.GET.get('output_type','')
    if(outputType != ''):
        return send_to_file(outputType, 'cells', table, queryset, request )
    
    RequestConfig(request, paginate={"per_page": 25}).configure(table)
    return render(request, 'db/listIndex.html', {'table': table, 'search':search })
    
def cellDetail(request, facility_id):
    try:
        cell = Cell.objects.get(facility_id=facility_id) # todo: cell here
    except Cell.DoesNotExist:
        raise Http404
    return render(request, 'db/cellDetail.html', {'object': CellForm(data=model_to_dict(cell))})

# TODO REFACTOR, DRY... 
def proteinIndex(request):
    logger.info("user: " , request.user, ", is authenticated: ", request.user.is_authenticated())
    search = request.GET.get('search','')
    if(search != ''):
        logger.info("s: %s" % search)
        queryset = Protein.objects.extra(
            select={
                'snippet': "ts_headline(" + ProteinTable.snippet_def + ", plainto_tsquery(%s))",
                'rank': "ts_rank_cd(search_vector, plainto_tsquery(%s), 32)",
                },
            where=["search_vector @@ plainto_tsquery(%s)"],
            params=[search],
            select_params=[search,search],
            order_by=('-rank',)
            )        
        logger.info("found: %s" % ProteinTable.snippet_def)
    else:
        queryset = Protein.objects.all().order_by('lincs_id')
    table = ProteinTable(queryset)

    outputType = request.GET.get('output_type','')
    if(outputType != ''):
        return send_to_file(outputType, 'proteins', table, queryset, request )
    
    RequestConfig(request, paginate={"per_page": 25}).configure(table)
    return render(request, 'db/listIndex.html', {'table': table, 'search':search })
    
def proteinDetail(request, lincs_id):
    try:
        protein = Protein.objects.get(lincs_id=lincs_id) # todo: cell here
    except Protein.DoesNotExist:
        raise Http404
    return render(request, 'db/proteinDetail.html', {'object': ProteinForm(data=model_to_dict(protein))})

def smallMoleculeIndex(request):
    search = request.GET.get('search','')
    queryset = SmallMoleculeSearchManager().search(search);
    table = SmallMoleculeTable(queryset)

    outputType = request.GET.get('output_type','')
    if(outputType != ''):
        return send_to_file(outputType, 'small_molecule', table, queryset, request )
    
    RequestConfig(request, paginate={"per_page": 25}).configure(table)
    return render(request, 'db/listIndex.html', {'table': table, 'search':search })
 
def smallMoleculeDetail(request, sm_id):
    try:
        sm = SmallMolecule.objects.get(pk=sm_id) # TODO: create a sm detail link from facilty-salt-batch id
    except SmallMolecule.DoesNotExist:
        raise Http404
    return render(request,'db/smallMoleculeDetail.html', {'object': SmallMoleculeForm(data=model_to_dict(sm))})

def libraryIndex(request):
    search = request.GET.get('search','')
    queryset = LibrarySearchManager().search(search);
    table = LibraryTable(queryset)

    outputType = request.GET.get('output_type','')
    if(outputType != ''):
        return send_to_file(outputType, 'libraries', table, queryset, request )
    
    RequestConfig(request, paginate={"per_page": 25}).configure(table)
    return render(request, 'db/listIndex.html', {'table': table, 'search':search })

def libraryDetail(request, short_name):
    try:
        library = Library.objects.get(short_name=short_name)
        queryset = SmallMoleculeSearchManager().search(library_id=library.id);
        table = SmallMoleculeTable(queryset)
    except Library.DoesNotExist:
        raise Http404
    return render(request,'db/libraryDetail.html', {'object': LibraryForm(data=model_to_dict(library)),
                                                         'table': table})

def studyIndex(request):
    return screenIndex(request, '3')

def screenIndex(request, facility_id_filter='1'):
    search = request.GET.get('search','')
    if(search != ''):
        logger.info("s: %s" % search)
        queryset = DataSet.objects.extra(
            select={
                'snippet': "ts_headline(" + DataSetTable.snippet_def + ", plainto_tsquery(%s) )",
                'rank': "ts_rank_cd(search_vector, plainto_tsquery(%s), 32)",
                },
            where=["search_vector @@ plainto_tsquery(%s)", "facility_id  like '%s%%'"], # TODO: purge 'HMSL'
            params=[search, facility_id_filter],
            select_params=[search,search],
            order_by=('-rank',)
            )        
        #logger.info( 'queryset: ' queryset
    else:
        queryset = DataSet.objects.all().order_by('facility_id').filter(facility_id__startswith=facility_id_filter)
    #print 'queryset size: ' + str(len(queryset))
    #if(facility_id_filter=='3'): table = DataSetTable(queryset,'study') # TODO: get rid of the magic value "3" for 300000 series == studies
    table = DataSetTable(queryset)
    
    outputType = request.GET.get('output_type','')
    if(outputType != ''):
        return send_to_file(outputType, 'screenIndex', table, queryset, request )
        
    RequestConfig(request, paginate={"per_page": 25}).configure(table)
    
    if(facility_id_filter=='3'): type='study'
    elif(facility_id_filter=='1'): type='screen'
    else:
        raise Exception('unknown facility_id_filter: ' + str(facility_id_filter))
    return render(request, 'db/listIndex.html', {'table': table, 'search':search, 'type': type })

# Follows is a messy way to differentiate each tab for the screen detail page (each tab calls it's respective method)
def getDatasetType(facility_id):
    if(facility_id.find('1') == 0):
        return 'screen'
    elif(facility_id.find('3') == 0):
        return 'study'
    else:
        raise Exception('unknown facility id range: ' + str(facility_id))
    
def screenDetailMain(request, facility_id):
    details = screenDetail(request,facility_id)
    details.setdefault('type',getDatasetType(facility_id))
    return render(request,'db/screenDetailMain.html', details )
def screenDetailCells(request, facility_id):
    details = screenDetail(request,facility_id)
    details.setdefault('type',getDatasetType(facility_id))
    return render(request,'db/screenDetailCells.html', details)
def screenDetailProteins(request, facility_id):
    details = screenDetail(request,facility_id)
    details.setdefault('type',getDatasetType(facility_id))
    return render(request,'db/screenDetailProteins.html', details)
def screenDetailResults(request, facility_id):
    details = screenDetail(request,facility_id)
    details.setdefault('type',getDatasetType(facility_id))
    return render(request,'db/screenDetailResults.html', details)
def screenDetail(request, facility_id):
    try:
        dataset = DataSet.objects.get(facility_id=facility_id)
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
    
    # Create a query on the fly that pivots the values from the datapoint table, making one column for each datacolumn type
    # use the datacolumns to make a query on the fly (for the DataSetResultSearchManager), and make a DataSetResultSearchTable on the fly.
    dataColumnCursor = connection.cursor()
    dataColumnCursor.execute("SELECT id, name, data_type, precision from db_datacolumn where dataset_id = %s order by id asc", [dataset_id])
    
    # Need to construct something like this:
    # select distinct (datarecord_id), small_molecule_id,small_molecule_id, sm.facility_id || '-' || sm.sm_salt as facility_id,
    #        (select int_value as col1 from db_datapoint dp1 where dp1.datacolumn_id=2 and dp1.datarecord_id = dp0.datarecord_id) as col1, 
    #        (select int_value as col2 from db_datapoint dp2 where dp2.datarecord_id=dp0.datarecord_id and dp2.datacolumn_id=3) as col2 
    #        from db_datapoint dp0 join db_datarecord dr on(datarecord_id=dr.id) join db_smallmolecule sm on(sm.id=dr.small_molecule_id) 
    #        where dp0.dataset_id = 1 order by datarecord_id;
    queryString = "select distinct (datarecord_id), small_molecule_id, sm.facility_id || '-' || sm.sm_salt as facility_id "
    if(show_cells): queryString += ", cell_id, cell.name as cell_name " 
    if(show_proteins): queryString += ", protein_id, protein.name as protein_name " 
    i = 0
    names = {}
    orderedNames = ['facility_id']
    for datacolumn_id, name, datatype, precision in dataColumnCursor.fetchall():
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
    queryString += " from db_datapoint dp0 join db_datarecord dr on(datarecord_id=dr.id) join db_smallmolecule sm on(sm.id=dr.small_molecule_id) "
    if(show_cells): 
        queryString += " join db_cell cell on(cell.id=dr.cell_id) "
        orderedNames.insert(1,'cell_name')
    if(show_proteins): 
        queryString += " join db_protein protein on(protein.id=dr.protein_id) "
        orderedNames.insert(1,'protein_name')
    queryString += " where dp0.dataset_id = " + str(dataset_id) + " order by datarecord_id"
    orderedNames.append('...')
    

    queryset = DataSetResultSearchManager().search(queryString);
    table = DataSetResultTable(queryset, names, orderedNames, show_cells, show_proteins)
    
    
#    return render(request,'db/screenDetailMain.html', {'object': ScreenForm(data=model_to_dict(screen)),
#                                                        'table': table,
#                                                        'cellTable': cellTable,
#                                                        'screenId': screen.id})
    RequestConfig(request, paginate={"per_page": 25}).configure(table)
    RequestConfig(request, paginate={"per_page": 25}).configure(cellTable)
    RequestConfig(request, paginate={"per_page": 25}).configure(proteinTable)
    return {'object': DataSetForm(data=model_to_dict(dataset)),
           'table': table,
           'cellTable': cellTable,
           'proteinTable': proteinTable,
           'facilityId': facility_id}
    
#---------------Supporting classes and functions--------------------------------

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
    
    def search(self, query_string='', library_id=None):
        query_string = query_string.strip()
        cursor = connection.cursor()
        sql = ( "select l.short_name as library_name, l.id as library_id, sm.* " +
            " from db_smallmolecule sm " + 
            " left join db_librarymapping lm on(sm.id=lm.small_molecule_id) " + 
            " join db_library l on(lm.library_id=l.id) ")
        where = ''
        if(query_string != '' ):
            where = ", to_tsquery(%s) as query  where sm.search_vector @@ query "
        if(library_id != None):
            if(where != ''):
                where += ', '
            else:
                where = ' where '
            where += 'library_id='+ str(library_id)
        sql += where
        sql += " order by sm.facility_id, sm.sm_salt, sm.facility_batch_id "
        
        # TODO: the way we are separating query_string out here is a kludge
        if(query_string != ''):
            cursor.execute(sql, [query_string + ':*'])
        else:
            cursor.execute(sql)
        v = dictfetchall(cursor)
        return v
    
class SmallMoleculeTable(tables.Table):
    facility_id = tables.LinkColumn("sm_detail", args=[A('id')]) # TODO: create a molecule link for facility/salt/batch ids
    rank = tables.Column()
    snippet = tables.Column()
    library_name = tables.LinkColumn('library_detail', args=[A('library_id')])
    snippet_def = (" || ' ' || ".join(map( lambda x: "coalesce("+x.name+",'') ", get_text_fields(SmallMolecule))))
    class Meta:
        model = SmallMolecule
        orderable = True
        attrs = {'class': 'paleblue'}
        sequence = ('facility_id', 'sm_salt', 'facility_batch_id', 'sm_name','...','sm_smiles','sm_inchi')
        exclude = ('id', 'molfile', 'plate', 'row', 'column', 'well_type') 

class SmallMoleculeForm(ModelForm):
    class Meta:
        model = SmallMolecule           
        order = ('facility_id', '...')
        exclude = ('id', 'molfile', 'plate', 'row', 'column', 'well_type') 

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
    
    def search(self, query_string):
        query_string = query_string.strip()
        cursor = connection.cursor()
        sql = ( "select a.*, library.* from ( SELECT count(well) as well_count , max(plate)-min(plate)+ 1 as plate_count, library.id " + 
            " from db_library library left join db_librarymapping on(library_id=library.id) ")
        if(query_string != '' ):
            sql += ", to_tsquery(%s) as query  where library.search_vector @@ query " 
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
            "SELECT id, facility_id, ts_headline(" + CellTable.snippet_def + """, query1, 'MaxFragments=10, MinWords=1, MaxWords=20, FragmentDelimiter=" | "') as snippet, """ +
            " ts_rank_cd(search_vector, query1, 32) AS rank, 'cell_detail' as type FROM db_cell, to_tsquery(%s) as query1 WHERE search_vector @@ query1 " +
            " UNION " +
            " SELECT id, facility_id, ts_headline(" + SmallMoleculeTable.snippet_def + """, query2, 'MaxFragments=10, MinWords=1, MaxWords=20, FragmentDelimiter=" | "') as snippet, """ +
            " ts_rank_cd(search_vector, query2, 32) AS rank, 'sm_detail' as type FROM db_smallmolecule, to_tsquery(%s) as query2 WHERE search_vector @@ query2 " +
            " UNION " +
            " SELECT id, facility_id, ts_headline(" + DataSetTable.snippet_def + """, query3, 'MaxFragments=10, MinWords=1, MaxWords=20, FragmentDelimiter=" | "') as snippet, """ +
            " ts_rank_cd(search_vector, query3, 32) AS rank, 'screen_detail' as type FROM db_dataset, to_tsquery(%s) as query3 WHERE search_vector @@ query3 " +
            " UNION " +
            " SELECT id, lincs_id as facility_id, ts_headline(" + ProteinTable.snippet_def + """, query4, 'MaxFragments=10, MinWords=1, MaxWords=20, FragmentDelimiter=" | "') as snippet, """ +
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
    facility_id = tables.LinkColumn('sm_detail', args=[A('small_molecule_id')]) 
    cell_name = tables.LinkColumn('cell_detail',args=[A('cell_id')], visible=False)
    protein_name = tables.LinkColumn('protein_detail',args=[A('protein_id')], visible=False)
    
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