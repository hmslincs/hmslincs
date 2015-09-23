from niepel_2014_utils import *
import os
from collections import namedtuple
from django.conf import settings
from django.template.loader import render_to_string
from django.contrib.flatpages.models import FlatPage
from django.contrib.sites.models import Site
import shutil

# Pattern to create a namedtuple-based class with optional args.
class FigArgs(namedtuple('FigArgs',
                         'category img_type names dimensions link fname_prefix')):
    def __new__(cls, category, img_type, names,
                dimensions, link=True, fname_prefix=''):
        return super(FigArgs, cls).__new__(cls, category, img_type, names,
                                           dimensions, link, fname_prefix)    

source_path = resource_path('SignalingPage')

html_path = create_output_path()

ligands = stash_get('ligands')
cell_lines = stash_get('cell_lines')
assert ligands, ("'ligands' not found in stash -- "
                 "please run niepel_2014_ligand.py")
assert cell_lines, ("'cell_lines' not found in stash -- "
                    "please run niepel_2014_cell_line.py")

ligand_names = [ligand['name'] for ligand in ligands]

cell_lines.sort(key=lambda c: c['name'])
cell_line_names = [c['name'] for c in cell_lines]

data = {
    'ligand_names': ligand_names,
    'cell_line_names': cell_line_names,
    'fig_args': {
        'cell_line_nodeedge': FigArgs('cell-line', 'nodeedge',
                                      ['MCF7', 'BT-20', 'MDA-MB-453'],
                                      (250, 235)),
        'subtype_nodeedge': FigArgs('cell-line', 'nodeedge',
                                    ['TNBC', 'HER2amp', 'HR+'], (250, 235),
                                    link=False, fname_prefix='NetMap_'),
        'cell_line_subtype': FigArgs('cell-line', 'subtype', ['MCF7'],
                                     (700, 237)),
        'cell_line_topmeasures': FigArgs('cell-line', 'topmeasures', ['MCF7'],
                                         (700, 385)),
        'cell_line_foldchange': FigArgs('cell-line', 'foldchange', ['MCF7'],
                                        (700, 237)),
        'ligand_timecourse': FigArgs('ligand', 'timecourse', ['EGF'],
                                     (700, 233)),
        'ligand_responsekinetics': FigArgs('ligand', 'responsekinetics',
                                           ['EGF'], (700, 245)),
        'ligand_doseresponse': FigArgs('ligand', 'doseresponse', ['EGF'],
                                       (700, 233)),
        'ligand_sensitivity': FigArgs('ligand', 'sensitivity', ['EGF'],
                                      (700, 292)),
        'ligand_pathwaybias': FigArgs('ligand', 'pathwaybias', ['EGF'],
                                      (700, 292)),
    },
    'BASE_URL': BASE_URL,
}

url = BASE_URL
content = render_to_string('breast_cancer_signaling/index.html', data)

page, created = FlatPage.objects.get_or_create(url=url)
page.title = ('Analysis of growth factor signaling in genetically '
              'diverse breast cancer lines')
page.content = content
page.template_name = 'breast_cancer_signaling/base.html'
page.sites.clear()
page.sites.add(Site.objects.get_current())
page.save()

data_filename = 'all_data.csv'
data_src_path = os.path.join(source_path, data_filename)
data_dest_path = os.path.join(html_path, data_filename)
shutil.copy(data_src_path, data_dest_path)
