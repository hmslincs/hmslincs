from __future__ import print_function, division
from niepel_2013 import *
import jinja2
import wand.image
import math
import os
import re
import codecs

def render_template(dirname, filename, data):
    out_filename = os.path.join(dirname, filename)
    content = lookup_template.render(data)
    with codecs.open(out_filename, 'w', 'utf-8') as out_file:
        out_file.write(content)

# 870px wide, 2x resolution
DESIRED_WIDTH_PX = 870 * 2

lookup_path = site_path('SignalingPage', 'LookupTablesPage')

template_env = jinja2.Environment(
    loader=jinja2.PackageLoader('niepel_2013', 'templates'))
ligand_template = template_env.get_template('lookup_table.html')

panel_path = os.path.join(lookup_path, 'subfigures')

html_path = site_path('html', 'lookup_table')
try:
    os.makedirs(html_path)
except OSError as e:
    # pass only if error is EEXIST
    if e.errno != 17:
        raise

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
