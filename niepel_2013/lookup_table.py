from __future__ import print_function, division
from niepel_2013 import *
import jinja2
import wand.image, wand.color
import math
import os
import re

# 870px wide, 2x resolution
DESIRED_WIDTH_PX = 870 * 2

lookup_path = resource_path('SignalingPage', 'LookupTablesPage')

template_env = jinja2.Environment(
    loader=jinja2.PackageLoader('niepel_2013', 'templates'))
table_template = template_env.get_template('lookup_table.html')

panel_path = os.path.join(lookup_path, 'subfigures')

html_path = create_output_path('lookup_table')

akt_pdf_filename = os.path.join(lookup_path, 'lookup table pAKT.pdf')
erk_pdf_filename = os.path.join(lookup_path, 'lookup table pERK.pdf')

img_tmp = wand.image.Image(filename=akt_pdf_filename)
# Use img_tmp height because the source image is rotated 90 degrees.
height_inches = img_tmp.height / img_tmp.resolution[1]
resolution = int(math.floor(DESIRED_WIDTH_PX / height_inches))
img_tmp.close()

img_akt = wand.image.Image(filename=akt_pdf_filename, resolution=resolution)
img_akt.rotate(-90)
with wand.image.Image(width=img_akt.width, height=img_akt.height,
                      background=wand.color.Color('white')) as img_out:
    img_out.composite(image=img_akt, left=0, top=0)
    img_out.save(filename=os.path.join(html_path, 'img', 'table_akt.png'))

img_erk = wand.image.Image(filename=erk_pdf_filename, resolution=resolution)
img_erk.rotate(-90)
with wand.image.Image(width=img_erk.width, height=img_erk.height,
                      background=wand.color.Color('white')) as img_out:
    img_out.composite(image=img_erk, left=0, top=0)
    img_out.save(filename=os.path.join(html_path, 'img', 'table_erk.png'))

# Constants determined empirically by inspecting the output images (and tweaking
# a bit after looking at the output html). All values in CSS px.
origin_x = 76
origin_y = 96.5
cell_w = 18.07
cell_h = 26.5

# FIXME make ligand.py stash this list somewhere we can read it in (pickle?)
ligands = ['EGF', 'EPR', 'BTC', 'HRG', 'INS', 'IGF-1', 'IGF-2', 'PDGF-BB',
           'HGF', 'SCF', 'FGF-1', 'FGF-2', 'NGF-beta', 'EFNA1', 'VEGF165']
# FIXME same thing here for cell_line.py
cell_lines = ['184B5', 'BT-20', 'BT-549', 'HCC1187', 'HCC1395', 'HCC1806',
              'HCC1937', 'HCC38', 'HCC70', 'Hs 578T', 'MCF 10A', 'MCF 10F',
              'MCF-12A', 'MDA-MB-157', 'MDA-MB-231', 'MDA-MB-436', 'MDA-MB-453',
              'MDA-MB-468', 'AU-565', 'BT-474', 'HCC1419', 'HCC1569', 'HCC1954',
              'HCC202', 'MDA-MB-361', 'SK-BR-3', 'UACC-812', 'UACC-893',
              'ZR-75-30', 'BT-483', 'CAMA-1', 'HCC1428', 'HCC1500', 'MCF7',
              'MDA-MB-134-VI', 'MDA-MB-175-VII', 'MDA-MB-415', 'T47D',
              'ZR-75-1']

cells = []
for row, ligand in enumerate(ligands):
    for column, cell_line in enumerate(cell_lines):
        cell = {
            'name': '%s_%s' % (ligand, cell_line),
            'ligand': ligand,
            'cell_line': cell_line,
            'left': origin_x + column * cell_w,
            'top': origin_y + row * cell_h,
            'width': cell_w,
            'height': cell_h,
            }
        cells.append(cell)
        

data = {
    'tables': [
        {
            'name': 'akt',
            'image_path': 'img/table_akt.png',
            'image': img_akt,
            'cells': cells,
            },
        ]
    }
render_template(table_template, data, html_path, 'index.html')

for cell in cells:
    image_filename = cell['name'] + '.png'
    # We are only copying one image, but we can reuse copy_images with a little
    # creativity in crafting the first arg.
    copy_images([('', 'subfigures')], image_filename,
                lookup_path, ('lookup_table', 'img'), permissive=True)
