from __future__ import print_function, division
from niepel_2014_utils import *
import wand.image, wand.color
import math
import os
import re
import argparse
from django.conf import settings

# Table image - 870px wide, 2x resolution.
TABLE_WIDTH = 870
DESIRED_WIDTH_PX = TABLE_WIDTH * 2

# Size of individual plots in the popups.
PLOT_DIMENSIONS = (350, 257)

lookup_path = resource_path('SignalingPage', 'LookupTablesPage')

panel_path = os.path.join(lookup_path, 'subfigures')

img_path_elements = ('matrix', 'img')
html_path = os.path.dirname(create_output_path(*img_path_elements))

akt_pdf_filename = os.path.join(lookup_path, 'lookup table pAKT.pdf')
erk_pdf_filename = os.path.join(lookup_path, 'lookup table pERK.pdf')

parser = argparse.ArgumentParser(
    description='Build niepel_2014 cell line page resources')
parser.add_argument('-n', '--no-images', action='store_true', default=False,
                    help='Skip building images')
args = parser.parse_args()

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
if not args.no_images:
    with wand.image.Image(width=img_akt.width, height=img_akt.height,
                          background=wand.color.Color('white')) as img_out:
        img_out.composite(image=img_akt, left=0, top=0)
        img_out.save(filename=os.path.join(html_path, 'img', 'table_akt.png'))
PASS_nl()

print_partial(os.path.basename(erk_pdf_filename))
img_erk = wand.image.Image(filename=erk_pdf_filename, resolution=resolution)
img_erk.rotate(-90)
if not args.no_images:
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
    'breadcrumbs': [
        {'url': BASE_URL, 'text': 'Start'},
        {'url': '', 'text': 'Response matrix'},
    ],
    'ligand_links': ligand_links,
    'cell_line_links': cell_line_links,
    'cells': cells,
    'tables': [
        {
            'name': 'akt',
            'image_path': 'img/table_akt.png',
            'image_width': img_akt.width / 2,
            'image_height': img_akt.height / 2,
            },
        {
            'name': 'erk',
            'image_path': 'img/table_erk.png',
            'image_width': img_erk.width / 2,
            'image_height': img_erk.height / 2,
            },
        ],
    'plot_dimensions': PLOT_DIMENSIONS,
    'STATIC_URL': settings.STATIC_URL,
    'BASE_URL': BASE_URL,
}

render_template('breast_cancer_signaling/lookup_table.html', data,
                html_path, 'index.html')

if not args.no_images:
    print()
    image_sizes = {'': PLOT_DIMENSIONS}
    for i, cell in enumerate(cells):
        msg = 'rendering image %d/%d %s...' % (i+1, len(cells), cell['name'])
        # FIXME The string padding (50) should be calculated dynamically.
        print_partial('\r' + msg.ljust(50))
        image_filename = cell['name'] + '.png'
        # We are only copying one image, but we can reuse copy_images with a
        # little creativity in crafting the first arg.
        copy_images([('', 'subfigures')], image_filename,
                    lookup_path, img_path_elements, permissive=True,
                    new_sizes=image_sizes, new_format='jpg',
                    format_options={'quality': 85, 'optimize': True})
    print_partial("done")
    PASS_nl()
