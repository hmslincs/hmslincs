#from django.template import Context, loader
#from django.http import HttpResponse
from django.shortcuts import render_to_response
from django.shortcuts import render
from django.db import models
from django.forms.models import model_to_dict
from django.forms import ModelForm

from example.models import SmallMolecule, Cell, Screen, DataColumn, DataPoint, DataRecord
from django.http import Http404
import django_tables2 as tables
from django_tables2 import RequestConfig
#from django.template import RequestContext
from django_tables2.utils import A  # alias for Accessor
from django.db import connection

class SmallMoleculeTable(tables.Table):
    facility_id = tables.LinkColumn("sm_detail", args=[A('pk')])
    rank = tables.Column()
    snippet = tables.Column()
    # TODO: define the snippet dynamically, using all the text fields from the model
    # TODO: add the facility_id
    snippet_def = ("coalesce(sm_name,'') || ' ' || coalesce(sm_provider,'')")
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
    facility_id = tables.LinkColumn("cell_detail", args=[A('pk')])
    rank = tables.Column()
    snippet = tables.Column()
    cl_id = tables.Column(verbose_name='CLO Id')
    # TODO: define the snippet dynamically, using all the text fields from the model
    # TODO: add the facility_id
    snippet_def = ("coalesce(cl_name,'') || ' ' || coalesce(cl_id,'') || ' ' || coalesce(cl_alternate_name,'') || ' ' || " +  
                   "coalesce(cl_alternate_id,'') || ' ' || coalesce(cl_center_name,'') || ' ' || coalesce(cl_center_specific_id,'') || ' ' || " +  
                   "coalesce(assay,'') || ' ' || coalesce(cl_provider_name,'') || ' ' || coalesce(cl_provider_catalog_id,'') || ' ' || coalesce(cl_batch_id,'') || ' ' || " + 
                   "coalesce(cl_organism,'') || ' ' || coalesce(cl_organ,'') || ' ' || coalesce(cl_tissue,'') || ' ' || coalesce(cl_cell_type,'') || ' ' ||  " +
                   "coalesce(cl_cell_type_detail,'') || ' ' || coalesce(cl_disease,'') || ' ' || coalesce(cl_disease_detail,'') || ' ' ||  " +
                   "coalesce(cl_growth_properties,'') || ' ' || coalesce(cl_genetic_modification,'') || ' ' || coalesce(cl_related_projects,'') || ' ' || " + 
                   "coalesce(cl_recommended_culture_conditions)")
    class Meta:
        model = Cell
        orderable = True
        attrs = {'class': 'paleblue'}
        sequence = ('facility_id', '...')
        exclude = ('id','cl_recommended_culture_conditions', 'cl_verification_reference_profile', 'cl_mutations_explicit', 'cl_mutations_reference')
        
class CellForm(ModelForm):
    class Meta:
        model = Cell        

class SiteSearchManager(models.Manager):
    
    def search(self, queryString):
        cursor = connection.cursor()
        # TODO: build this dynamically, like the rest of the search
        cursor.execute(
            "SELECT id, facility_id, ts_headline(" + CellTable.snippet_def + ", query1 ) as snippet, " +
            " ts_rank_cd(search_vector, query1, 32) AS rank, 'cell_detail' as type FROM example_cell, to_tsquery(%s) as query1 WHERE search_vector @@ query1 " +
            " UNION " +
            " SELECT id, facility_id, ts_headline(" + SmallMoleculeTable.snippet_def + ", query2 ) as snippet, " +
            " ts_rank_cd(search_vector, query2, 32) AS rank, 'sm_detail' as type FROM example_smallmolecule, to_tsquery(%s) as query2 WHERE search_vector @@ query2 " +
            " UNION " +
            " SELECT id, facility_id, ts_headline(" + ScreenTable.snippet_def + ", query3 ) as snippet, " +
            " ts_rank_cd(search_vector, query3, 32) AS rank, 'screen_detail' as type FROM example_screen, to_tsquery(%s) as query3 WHERE search_vector @@ query3 " +
            " ORDER by rank DESC;", [queryString + ":*", queryString + ":*", queryString + ":*"])
        return dictfetchall(cursor)

class SiteSearchTable(tables.Table):
    id = tables.Column(visible=False)
    #Note: using the expediency here: the "type" column holds the subdirectory for that to make the link for type, so "sm", "cell", etc., becomes "/example/sm", "/example/cell", etc.
    facility_id = tables.LinkColumn(A('type'), args=[A('id')])  
    type = tables.Column()
    rank = tables.Column()
    snippet = tables.Column()
    class Meta:
        orderable = True
        attrs = {'class': 'paleblue'}

class ScreenTable(tables.Table):
    id = tables.Column(visible=False)
    facility_id = tables.LinkColumn("screen_detail", args=[A('pk')])
    protocol = tables.Column(visible=False) # TODO: add to the index, well, build the index automatically...
    references = tables.Column(visible=False)
    rank = tables.Column()
    snippet = tables.Column()
    snippet_def = ("coalesce(facility_id,'') || ' ' || coalesce(title,'') || ' ' || coalesce(summary,'') || ' ' || " +    
                   "coalesce(lead_screener_firstname,'') || ' ' || coalesce(lead_screener_lastname,'')|| ' ' || coalesce(lead_screener_email,'') || ' ' || "  +           
                   "coalesce(lab_head_firstname,'') || ' ' || coalesce(lab_head_lastname,'')|| ' ' || coalesce(lab_head_email,'')")
    class Meta:
        model = Screen
        orderable = True
        attrs = {'class': 'paleblue'}
        exclude = ('id') 

class ScreenForm(ModelForm):
    class Meta:
        model = Screen  
        
class ScreenResultSearchManager(models.Manager):
    
    def search(self, queryString ): # TODO: pass the parameters for the SQL as well
        cursor = connection.cursor()
        print "queryString: ", queryString
        cursor.execute(queryString)

        return dictfetchall(cursor)
  
TEMPLATE = '''
   <a href="#" onclick='window.open("https://lincs-omero.hms.harvard.edu/webclient/img_detail/{{ record.%s }}", "test","height=700,width=800")' >{{ record.%s }}</a>
'''
            
class ScreenResultTable(tables.Table):
    id = tables.Column(visible=False)
    facility_id = tables.LinkColumn('sm_detail', args=[A('small_molecule_key_id')]) 
    
    def __init__(self, queryset, names, omeroColumnNames, orderedNames, *args, **kwargs):
        super(ScreenResultTable, self).__init__(queryset, names, *args, **kwargs)
        # print "queryset: ", queryset , " , names: " , names, ", args: " , args
        for name,verbose_name in names.items():
            if name in omeroColumnNames:
                self.base_columns[name] = tables.TemplateColumn(TEMPLATE % (omeroColumnNames[name],name),verbose_name=verbose_name)
            else:
                self.base_columns[name] = tables.Column(verbose_name=verbose_name)
        self.sequence = orderedNames
        
    class Meta:
        orderable = True
        attrs = {'class': 'paleblue'}
    
def main(request):
    search = request.GET.get('search','')
    if(search != ''):
        print("s: %s" % search)
        queryset = SiteSearchManager().search(search);
        table = SiteSearchTable(queryset)
        RequestConfig(request, paginate={"per_page": 25}).configure(table)
        return render(request, 'example/index.html', {'table': table, 'search':search })
    else:
        return render(request, 'example/index.html')

def cellIndex(request):
    search = request.GET.get('search','')
    if(search != ''):
        print("s: %s" % search)
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
        print("found: %s" % CellTable.snippet_def)
    else:
        queryset = Cell.objects.all().order_by('facility_id')
    table = CellTable(queryset)
    RequestConfig(request, paginate={"per_page": 25}).configure(table)
    return render(request, 'example/listIndex.html', {'table': table, 'search':search })
    
def cellDetail(request, cell_id):
    try:
        cell = Cell.objects.get(pk=cell_id) # todo: cell here
    except Cell.DoesNotExist:
        raise Http404
    return render(request, 'example/cellDetail.html', {'object': CellForm(data=model_to_dict(cell))})

def smallMoleculeIndex(request):
    search = request.GET.get('search','')
    if(search != ''):
        print("s: %s" % search)
        queryset = SmallMolecule.objects.extra(
            select={
                'snippet': "ts_headline(" + SmallMoleculeTable.snippet_def + ", plainto_tsquery(%s))",
                'rank': "ts_rank_cd(search_vector, plainto_tsquery(%s), 32)",
                },
            where=["search_vector @@ plainto_tsquery(%s)"],
            params=[search],
            select_params=[search,search],
            order_by=('-rank',)
            )        
        print("found: %s" % queryset)
    else:
        queryset = SmallMolecule.objects.all().order_by('facility_id')
    table = SmallMoleculeTable(queryset)
    RequestConfig(request, paginate={"per_page": 25}).configure(table)
    return render(request, 'example/listIndex.html', {'table': table, 'search':search })
 
def smallMoleculeDetail(request, sm_id):
    try:
        sm = SmallMolecule.objects.get(pk=sm_id)
    except SmallMolecule.DoesNotExist:
        raise Http404
    return render(request,'example/smallMoleculeDetail.html', {'object': SmallMoleculeForm(data=model_to_dict(sm))})

def screenIndex(request):
    search = request.GET.get('search','')
    if(search != ''):
        print("s: %s" % search)
        queryset = Screen.objects.extra(
            select={
                'snippet': "ts_headline(" + ScreenTable.snippet_def + ", plainto_tsquery(%s))",
                'rank': "ts_rank_cd(search_vector, plainto_tsquery(%s), 32)",
                },
            where=["search_vector @@ plainto_tsquery(%s)"],
            params=[search],
            select_params=[search,search],
            order_by=('-rank',)
            )        
        print("found: %s" % queryset)
    else:
        queryset = Screen.objects.all().order_by('facility_id')
    table = ScreenTable(queryset)
    RequestConfig(request, paginate={"per_page": 25}).configure(table)
    return render(request, 'example/listIndex.html', {'table': table, 'search':search })
 
def screenDetail(request, screen_id):
    try:
        screen = Screen.objects.get(pk=screen_id)
    except Screen.DoesNotExist:
        raise Http404

    # TODO: are the screen results gonna be searchable?
    search = request.GET.get('search','')
    
    # Create a query on the fly that pivots the values from the datapoint table, making one column for each data_column type
    # use the datacolumns to make a query on the fly (for the ScreenResultSearchManager), and make a ScreenResultSearchTable on the fly.
    
    cursor = connection.cursor()
    cursor.execute("SELECT id, name, data_type, precision from example_datacolumn where screen_key_id = %s order by id asc", [screen_id])
    
    # Need to construct something like this:
    # select distinct (record_key_id), small_molecule_key_id,small_molecule_key_id, sm.facility_id || '-' || sm.sm_salt as facility_id,
    #        (select int_value as col1 from example_datapoint dp1 where dp1.data_column_key_id=2 and dp1.record_key_id = dp0.record_key_id) as col1, 
    #        (select int_value as col2 from example_datapoint dp2 where dp2.record_key_id=dp0.record_key_id and dp2.data_column_key_id=3) as col2 
    #        from example_datapoint dp0 join example_datarecord dr on(record_key_id=dr.id) join example_smallmolecule sm on(sm.id=dr.small_molecule_key_id) 
    #        where dp0.screen_key_id = 1 order by record_key_id;
    queryString = "select distinct (record_key_id), small_molecule_key_id, sm.facility_id || '-' || sm.sm_salt as facility_id " 
    i = 0
    names = {}
    orderedNames = ['facility_id']
    omeroColumnNames = {}
    for id, name, datatype, precision in cursor.fetchall():
        i += 1
        alias = "dp"+str(i)
        omeroAlias = alias + "_ow" # somewhat messy way to associate the omero_well_id with the datapoint
        columnName = "col" + str(i)
        names[columnName] = name
        orderedNames.append(columnName)
        omeroColumnName = columnName + "_ow"
        omeroColumnNames[columnName] = omeroColumnName
        column_to_select = None
        if(datatype == 'Numeric'):
            if precision == 0:
                column_to_select = "int_value"
            else:
                column_to_select = "float_value"
        else:
            column_to_select = "text_value"
        # TODO: use params
        queryString +=  (",(select " + column_to_select + " from example_datapoint " + alias + 
                            " where " + alias + ".data_column_key_id="+str(id) + " and " + alias + ".record_key_id=dp0.record_key_id) as " + columnName )
        # add in the omero_well_id column
        queryString +=  (",(select omero_well_id from example_datapoint " + omeroAlias + 
                            " where " + omeroAlias + ".data_column_key_id="+str(id) + " and " + omeroAlias + ".record_key_id=dp0.record_key_id) as " + omeroColumnName )
    queryString += " from example_datapoint dp0 join example_datarecord dr on(record_key_id=dr.id) join example_smallmolecule sm on(sm.id=dr.small_molecule_key_id) "
    queryString += " where dp0.screen_key_id = " + str(screen_id) + " order by record_key_id"
    orderedNames.append('...')
    queryset = ScreenResultSearchManager().search(queryString);
    table = ScreenResultTable(queryset, names, omeroColumnNames, orderedNames)
    
    return render(request,'example/screenDetail.html', {'object': ScreenForm(data=model_to_dict(screen)),
                                                        'table': table})

def dictfetchall(cursor):
    "Returns all rows from a cursor as a dict"
    desc = cursor.description
    return [
        dict(zip([col[0] for col in desc], row)) for row in cursor.fetchall()
    ]
