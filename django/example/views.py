#from django.template import Context, loader
#from django.http import HttpResponse
from django.shortcuts import render_to_response
from django.shortcuts import render

from example.models import SmallMolecule
from django.http import Http404
import django_tables2 as tables
from django_tables2 import RequestConfig
#from django.template import RequestContext

class SmallMoleculeTable(tables.Table):
    class Meta:
        model = SmallMolecule
        orderable = True
        attrs = {'class': 'paleblue'}
    
    
def index(request):
#  sms = SmallMolecule.objects.all().order_by('-pub_date')
#  output  = ', '.join([sm.facility_id for sm in sms])
#  return HttpResponse(output)

    sms = SmallMolecule.objects.all() #.order_by('-pub_date')
    table = SmallMoleculeTable(sms,order_by=('<any column name from Performance>',))
    RequestConfig(request).configure(table)
# pagination works without this setup:    
#    table.paginate(page=request.GET.get('page', 1), per_page=25)
    #t = loader.get_template('example/index.html')
    #c = Context({
    #    'small_molecule_list': sms,
    #})
    #return HttpResponse(t.render(c))
#   return render_to_response('example/index.html', {'table': table }, context_instance=RequestContext(request))
    return render(request, 'example/index.html', {'table': table })

def detail(request, sm_id):
    try:
        sm = SmallMolecule.objects.get(pk=sm_id)
    except SmallMolecule.DoesNotExist:
        raise Http404
    return render_to_response('example/detail.html', {'small_molecule': sm})