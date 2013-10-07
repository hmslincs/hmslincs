from __future__ import print_function, division
from niepel_2013 import *
import jinja2
import wand.image
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
img_akt.save(filename=os.path.join(html_path, 'table_akt.png'))

# Constants determined empirically by inspecting the output images (and tweaking
# a bit after looking at the output html). All values in CSS px.
origin_x = 76
origin_y = 73
cell_w = 18.07
cell_h = 26.5

ligand_names = [
    
    ]

cells = []
for row in xrange(15):
    for column in xrange(39):
        cell = {
            'name': '%s_%s' % (row, column),
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
            'image_path': 'table_akt.png',
            'image': img_akt,
            'cells': cells,
            },
        ]
    }
render_template(table_template, data, html_path, 'index.html')
