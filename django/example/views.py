#from django.template import Context, loader
#from django.http import HttpResponse
from django.shortcuts import render_to_response
from django.shortcuts import render

from example.models import SmallMolecule
from django.http import Http404
import django_tables2 as tables
from django_tables2 import RequestConfig
#from django.template import RequestContext
from django_tables2.utils import A  # alias for Accessor

class SmallMoleculeTable(tables.Table):
    facility_id = tables.LinkColumn("sm_detail", args=[A('pk')])
    class Meta:
        model = SmallMolecule
        orderable = True
        attrs = {'class': 'paleblue'}
    
def main(request):
    return render(request, 'example/index.html')

def cellIndex(request):
    sms = SmallMolecule.objects.all() #.order_by('-pub_date')
    table = SmallMoleculeTable(sms)
    RequestConfig(request, paginate={"per_page": 25}).configure(table)
    return render(request, 'example/listIndex.html', {'table': table })
    
def smallMoleculeIndex(request):
    sms = SmallMolecule.objects.all() #.order_by('-pub_date')
    table = SmallMoleculeTable(sms)
    # table = SmallMoleculeTable(sms,order_by=('<any column name from Performance>',))
    RequestConfig(request, paginate={"per_page": 25}).configure(table)
    
#    table.paginate(page=request.GET.get('page', 1), per_page=25)
    #t = loader.get_template('example/index.html')
    #c = Context({
    #    'small_molecule_list': sms,
    #})
    #return HttpResponse(t.render(c))
#   return render_to_response('example/index.html', {'table': table }, context_instance=RequestContext(request))
    return render(request, 'example/listIndex.html', {'table': table })

def smallMoleculeDetail(request, sm_id):
    try:
        sm = SmallMolecule.objects.get(pk=sm_id)
    except SmallMolecule.DoesNotExist:
        raise Http404
    return render_to_response('example/smallMoleculeDetail.html', {'small_molecule': sm})

def cellDetail(request, cell_id):
    try:
        cell = SmallMolecule.objects.get(pk=cell_id) # todo: cell here
    except SmallMolecule.DoesNotExist:
        raise Http404
    return render_to_response('example/cellDetail.html', {'cell': cell})