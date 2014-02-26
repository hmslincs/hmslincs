from niepel_2014_utils import *
import os
from collections import namedtuple
from django.conf import settings
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
    'STATIC_URL': settings.STATIC_URL,
    'BASE_URL': BASE_URL,
}

render_template('breast_cancer_signaling/index.html', data,
                html_path, 'index.html')
data_filename = 'all_data.csv'
data_src_path = os.path.join(source_path, data_filename)
data_dest_path = os.path.join(html_path, data_filename)
shutil.copy(data_src_path, data_dest_path)
