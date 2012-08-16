#from django.template import Context, loader
#from django.http import HttpResponse
from django.shortcuts import render_to_response
from django.shortcuts import render
from django.db import models
from django.forms.models import model_to_dict
from django.forms import ModelForm

from example.models import SmallMolecule
from example.models import Cell
from django.http import Http404
import django_tables2 as tables
from django_tables2 import RequestConfig
#from django.template import RequestContext
from django_tables2.utils import A  # alias for Accessor

class SmallMoleculeTable(tables.Table):
    facility_id = tables.LinkColumn("sm_detail", args=[A('pk')])
    rank = tables.Column()
    snippet = tables.Column()
    class Meta:
        model = SmallMolecule
        orderable = True
        attrs = {'class': 'paleblue'}

class SmallMoleculeForm(ModelForm):
    class Meta:
        model = SmallMolecule        

class CellTable(tables.Table):
    facility_id = tables.LinkColumn("cell_detail", args=[A('pk')])
    rank = tables.Column()
    snippet = tables.Column()
    class Meta:
        model = Cell
        orderable = True
        attrs = {'class': 'paleblue'}
        
class CellForm(ModelForm):
    class Meta:
        model = Cell        

class SiteSearchManager(models.Manager):
    
    def dictfetchall(self,cursor):
        "Returns all rows from a cursor as a dict"
        desc = cursor.description
        return [
            dict(zip([col[0] for col in desc], row))
            for row in cursor.fetchall()
        ]
    
    def search(self, queryString):
        from django.db import connection
        cursor = connection.cursor()
        cursor.execute("""
            SELECT id, facility_id, ts_headline(facility_id || ' ' || name || ' ' || alternate_name || ' ' || alternate_id, query1 ) as snippet, ts_rank_cd(search_vector, query1, 32) AS rank, 'cell_detail' as type FROM example_cell, to_tsquery(%s) as query1 WHERE search_vector @@ query1
            UNION
            SELECT id, facility_id, ts_headline(facility_id || ' ' || name || ' ' || alternate_names, query2 ) as snippet, ts_rank_cd(search_vector, query2, 32) AS rank, 'sm_detail' as type FROM example_smallmolecule, to_tsquery(%s) as query2 WHERE search_vector @@ query2
            ORDER by rank DESC;""", [queryString + ":*", queryString + ":*"])
        return self.dictfetchall(cursor)

class SiteSearchTable(tables.Table):
    id = tables.Column(visible=False)
    facility_id = tables.LinkColumn(A('type'), args=[A('id')])
    type = tables.Column(visible=False)
    rank = tables.Column()
    snippet = tables.Column()
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
                'snippet': "ts_headline(facility_id || ' ' || name || ' ' || alternate_name || ' ' || alternate_id, plainto_tsquery(%s))",
                'rank': "ts_rank_cd(search_vector, plainto_tsquery(%s), 32)",
                },
            where=["search_vector @@ plainto_tsquery(%s)"],
            params=[search],
            select_params=[search,search],
            order_by=('-rank',)
            )        
        print("found: %s" % queryset)
    else:
        queryset = Cell.objects.all().order_by('facility_id')
    table = CellTable(queryset)
    RequestConfig(request, paginate={"per_page": 25}).configure(table)
    return render(request, 'example/listIndex.html', {'table': table, 'search':search })
    
def smallMoleculeIndex(request):
    search = request.GET.get('search','')
    if(search != ''):
        print("s: %s" % search)
        queryset = SmallMolecule.objects.extra(
            select={
                'snippet': "ts_headline(facility_id || ' ' || name || ' ' || alternate_names, plainto_tsquery(%s))",
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

def cellDetail(request, cell_id):
    try:
        cell = Cell.objects.get(pk=cell_id) # todo: cell here
    except Cell.DoesNotExist:
        raise Http404
    return render(request, 'example/cellDetail.html', {'object': CellForm(data=model_to_dict(cell))})