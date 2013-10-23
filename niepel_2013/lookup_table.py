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

img_path_elements = ('explore', 'signaling_response_matrix', 'img')
html_path = os.path.dirname(create_output_path(*img_path_elements))

akt_pdf_filename = os.path.join(lookup_path, 'lookup table pAKT.pdf')
erk_pdf_filename = os.path.join(lookup_path, 'lookup table pERK.pdf')

print_partial('determine PDF resolution')
img_tmp = wand.image.Image(filename=akt_pdf_filename)
# Use img_tmp height because the source image is rotated 90 degrees.
height_inches = img_tmp.height / img_tmp.resolution[1]
resolution = int(math.floor(DESIRED_WIDTH_PX / height_inches))
img_tmp.close()
PASS_nl()

print_partial(os.path.basename(akt_pdf_filename))
img_akt = wand.image.Image(filename=akt_pdf_filename, resolution=resolution)
img_akt.rotate(-90)
with wand.image.Image(width=img_akt.width, height=img_akt.height,
                      background=wand.color.Color('white')) as img_out:
    img_out.composite(image=img_akt, left=0, top=0)
    img_out.save(filename=os.path.join(html_path, 'img', 'table_akt.png'))
PASS_nl()

print_partial(os.path.basename(erk_pdf_filename))
img_erk = wand.image.Image(filename=erk_pdf_filename, resolution=resolution)
img_erk.rotate(-90)
with wand.image.Image(width=img_erk.width, height=img_erk.height,
                      background=wand.color.Color('white')) as img_out:
    img_out.composite(image=img_erk, left=0, top=0)
    img_out.save(filename=os.path.join(html_path, 'img', 'table_erk.png'))
PASS_nl()

# Constants determined empirically by inspecting the output images (and tweaking
# a bit after looking at the output html). All values in CSS px.
origin_x = 76
origin_y = 96.5
cell_w = 18.07
cell_h = 26.5
offset_y = 16

ligands = stash_get('ligands')
assert ligands, "'ligands' not found in stash -- please run ligand.py"
ligand_names = [ligand['name'] for ligand in ligands]

cell_lines = stash_get('cell_lines')
assert cell_lines, "'cell_lines' not found in stash -- please run cell_line.py"
subtype_order_list = ['TNBC', 'HER2amp', 'HR+']
subtype_order = dict(zip(subtype_order_list, range(len(subtype_order_list))))
cell_lines.sort(key=lambda c: (subtype_order[c['class_consensus']], c['name']))
cell_line_names = [c['name'] for c in cell_lines]

cells = []
for row, ligand in enumerate(ligand_names):
    for column, cell_line in enumerate(cell_line_names):
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

ligand_links = []
for row, ligand in enumerate(ligand_names):
    link = {
        'name': ligand,
        'left': 0,
        'top': origin_y + row * cell_h,
        'width': origin_x,
        'height': cell_h,
        }
    ligand_links.append(link)

cell_line_links = []
for column, cell_line in enumerate(cell_line_names):
    link = {
        'name': cell_line,
        'left': origin_x + column * cell_w,
        'top': 0,
        'width': cell_w,
        'height': origin_y - offset_y,
        }
    cell_line_links.append(link)

data = {
    'ligand_links': ligand_links,
    'cell_line_links': cell_line_links,
    'cells': cells,
    'tables': [
        {
            'name': 'akt',
            'image_path': 'img/table_akt.png',
            'image': img_akt,
            },
        {
            'name': 'erk',
            'image_path': 'img/table_erk.png',
            'image': img_erk,
            },
        ],
    'STATIC_URL_2': '../../.etc/',
    'DOCROOT': '../../',
}

render_template(table_template, data, html_path, 'index.html')

for cell in cells:
    image_filename = cell['name'] + '.png'
    # We are only copying one image, but we can reuse copy_images with a little
    # creativity in crafting the first arg.
    copy_images([('', 'subfigures')], image_filename,
                lookup_path, img_path_elements, permissive=True)
