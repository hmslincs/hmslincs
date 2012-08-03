#from django.template import Context, loader
#from django.http import HttpResponse
from django.shortcuts import render_to_response
from example.models import SmallMolecule
from django.http import Http404

def index(request):
#  sms = SmallMolecule.objects.all().order_by('-pub_date')
#  output  = ', '.join([sm.facility_id for sm in sms])
#  return HttpResponse(output)

    sms = SmallMolecule.objects.all().order_by('-pub_date')
    #t = loader.get_template('example/index.html')
    #c = Context({
    #    'small_molecule_list': sms,
    #})
    #return HttpResponse(t.render(c))
    return render_to_response('example/index.html', {'small_molecule_list': sms})


def detail(request, sm_id):
    try:
        sm = SmallMolecule.objects.get(pk=sm_id)
    except SmallMolecule.DoesNotExist:
        raise Http404
    return render_to_response('example/detail.html', {'small_molecule': sm})