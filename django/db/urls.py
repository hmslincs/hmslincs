from django.conf.urls import patterns, url, include
from tastypie.api import Api

from db.views import *
from db.api import SmallMoleculeResource
from db.api import CellResource
from db.api import PrimaryCellResource
from db.api import AntibodyResource
from db.api import OtherReagentResource
from db.api import DataSetResource2
from db.api import DataSetDataResource2
from db.api import ProteinResource
from db.api import LibraryResource
from django.contrib import admin

#smallmolecule_resource = SmallMoleculeResource()
v1_api = Api(api_name='v1')
v1_api.register(SmallMoleculeResource())
v1_api.register(CellResource())
v1_api.register(PrimaryCellResource())
v1_api.register(DataSetResource2())
v1_api.register(DataSetDataResource2())
v1_api.register(ProteinResource())
v1_api.register(LibraryResource())
v1_api.register(AntibodyResource())
v1_api.register(OtherReagentResource())

admin.autodiscover()

urlpatterns = patterns('',
    url(r'^admin/doc/', include('django.contrib.admindocs.urls')), 
    url(r'^admin/', include(admin.site.urls)),
    url(r'^$', 'db.views.main', name="home"),
    url(r'^sm/$','db.views.smallMoleculeIndex', name="listSmallMolecules" ),
    url(r'^sm/facility_ids/(?P<facility_ids>.*)$','db.views.smallMoleculeIndexList', name="small_molecule_listing" ),
    url(r'^sm/salt/$','db.views.saltIndex', name="salt_listing" ),
    url(r'^sm/salt/(?P<salt_id>\d+)/$','db.views.saltDetail', name="salt_detail" ),
    url(r'^sm/structuresearch/$','db.views.structure_search', name="structureSearch" ),
    url(r'^cached_structure_search/$','db.views.get_cached_structure_search', name="cached_structure_search_blank" ),
    url(r'^cached_structure_search/(?P<search_request_id>\d+)/$','db.views.get_cached_structure_search', name="cached_structure_search" ),
    url(r'^sm_molfile/(?P<facility_salt_id>[0-9\-]+)$','db.views.smallMoleculeMolfile', name="smallMoleculeMolfile" ),
    url(r'^sm/(?P<facility_salt_id>[0-9\-]+)/$', 'db.views.smallMoleculeDetail', name="sm_detail"),
    url(r'^cells/$','db.views.cellIndex', name="listCells"),
    url(r'^cells/(?P<facility_batch>[0-9\-]+)/$', 'db.views.cellDetail', name="cell_detail"),
    url(r'^cells/(?P<facility_batch>\d+)-(?P<batch_id>\d+)/$', 'db.views.cellDetail', name="cell_detail2"),    
    url(r'^primarycells/$','db.views.primaryCellIndex', name="listPrimaryCells"),
    url(r'^primarycells/(?P<facility_batch>[0-9\-]+)/$', 'db.views.primaryCellDetail', name="primary_cell_detail"),
    url(r'^primarycells/(?P<facility_batch>\d+)-(?P<batch_id>\d+)/$', 'db.views.primaryCellDetail', name="primary_cell_detail2"),    
    url(r'^antibodies/$','db.views.antibodyIndex', name="listAntibodies"),
    url(r'^antibodies/(?P<facility_batch>[\d-]+)/$', 
        'db.views.antibodyDetail', name="antibody_detail"),
    url(r'^antibodies/(?P<facility_batch>\d+)-(?P<batch_id>\d+)/$', 
        'db.views.antibodyDetail', name="antibody_detail2"),    
    url(r'^otherreagents/$','db.views.otherReagentIndex', name="listOtherReagents"),
    url(r'^otherreagents/(?P<facility_batch>[\d-]+)/$', 
        'db.views.otherReagentDetail', name="otherreagent_detail"),
    url(r'^otherreagents/(?P<facility_batch>\d+)-(?P<batch_id>\d+)/$', 
        'db.views.otherReagentDetail', name="otherreagent_detail2"),    
    url(r'^proteins/$','db.views.proteinIndex', name="listProteins"),
    url(r'^proteins/(?P<lincs_id>\d+)/$', 'db.views.proteinDetail', name="protein_detail"),
    url(r'^libraries/$','db.views.libraryIndex', name="listLibraries"),
    url(r'^libraries/(?P<short_name>[^/]+)/$', 'db.views.libraryDetail', name="library_detail"),
    url(r'^datasets/$','db.views.datasetIndex', name="listDatasets"),
    url(r'^datasets/(?P<facility_id>\d+)/$', 'db.views.datasetDetailMain', name="dataset_detail"),
    url(r'^datasets/(?P<facility_id>\d+)/main$', 'db.views.datasetDetailMain', name="dataset_detail_main"),
    url(r'^datasets/(?P<facility_id>\d+)/cells$', 'db.views.datasetDetailCells', name="dataset_detail_cells"),
    url(r'^datasets/(?P<facility_id>\d+)/primarycells$', 'db.views.datasetDetailPrimaryCells', name="dataset_detail_primary_cells"),
    url(r'^datasets/(?P<facility_id>\d+)/antibodies$', 'db.views.datasetDetailAntibodies', name="dataset_detail_antibodies"),
    url(r'^datasets/(?P<facility_id>\d+)/otherreagents$', 'db.views.datasetDetailOtherReagents', name="dataset_detail_otherreagents"),
    url(r'^datasets/(?P<facility_id>\d+)/proteins$', 'db.views.datasetDetailProteins', name="dataset_detail_proteins"),
    url(r'^datasets/(?P<facility_id>\d+)/smallmolecules$', 'db.views.datasetDetailSmallMolecules', name="dataset_detail_small_molecules"),
    url(r'^datasets/(?P<facility_id>\d+)/datapoints$', 'db.views.datasetDetailDataColumns', name="dataset_detail_datapoints"),
    url(r'^datasets/(?P<facility_id>\d+)/datacolumns$', 'db.views.datasetDetailDataColumns', name="dataset_detail_datacolumns"),
    url(r'^datasets/(?P<facility_id>\d+)/results$', 'db.views.datasetDetailResults', name="dataset_detail_results"),
    url(r'^datasets/(?P<facility_id>\d+)/results_minimal$', 'db.views.datasetDetailResults_minimal', name="dataset_detail_results_minimal"),
    # TODO: if we install x-sendfile on the apache server, we can serve these files with an x-sendfile redirect
    url(r'^downloadattached/(?P<id>\d+)/$', 'db.views.download_attached_file', name='download_attached_file'),
    url(r'^downloadqcattachedfile/(?P<id>\d+)/$', 'db.views.download_qc_attached_file', name='download_qc_attached_file'),
    # TODO: if we install x-sendfile on the apache server, we can serve these files with an x-sendfile redirect
     url(r'^restrictedimage/(?P<filepath>\S+)$', 'db.views.restricted_image', name="restricted_image"),
    
    # this method uses the x-sendfile header to apache to serve files, see views.py
    # url(r'^retrievefile/(?P<path>.*)/$', 'db.views.retrieve_file', name='retrieve_file'),

    (r'^api/', include(v1_api.urls)),
)