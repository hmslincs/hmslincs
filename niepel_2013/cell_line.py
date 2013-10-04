from __future__ import print_function
from niepel_2013 import *
import openpyxl
import jinja2
import requests
import os
import re
import codecs
import shutil


def render_template(dirname, filename, data):
    out_filename = os.path.join(dirname, filename)
    content = cellline_template.render(data)
    with codecs.open(out_filename, 'w', 'utf-8') as out_file:
        out_file.write(content)

cellline_path = resource_path('SignalingPage', 'CellLinePage')

filename = os.path.join(cellline_path, 'CellLine_sutypes.xlsx')
workbook = openpyxl.load_workbook(filename)
sheet = workbook.worksheets[0]
column_names = ('hmsl_id', 'name', 'short_name', 'atcc_id_ignored',
                'vendor', 'class_neve', 'class_heiser', 'class_kao', 'notes',
                'class_consensus')

template_env = jinja2.Environment(
    loader=jinja2.PackageLoader('niepel_2013', 'templates'))
cellline_template = template_env.get_template('cell_line.html')

image_dirs = [
    ('foldchange', 'FoldChangeBoxPlot'),
    ('nodeedge', 'NodeEdgeFigures'),
    ('subtype', 'subtypeBoxPlot'),
    ('topmeasures', 'BasalTopMeasures'),
    ]

html_path = create_output_path('cell_line')

all_data = []
print(' ' * 15 + 'FC NE ST TM DB  status')

for row in sheet.rows[1:3]:

    data = dict(zip(column_names, (r.value for r in row)))
    print('%-15s' % data['name'], end='')

    plot_filename = data['name'] + '.png'
    all_ok = all([print_status_accessible(cellline_path, d_in, plot_filename)
                  for d_out, d_in in image_dirs])

    db_data = None
    db_url = 'http://lincs.hms.harvard.edu/db/api/v1/cell/%s/' % data['hmsl_id']
    db_response = requests.get(db_url)
    all_ok &= db_response.ok
    if db_response.ok:
        PASS()
        data['db'] = db_response.json()
        if data['db']['clAlternateID']:
            cosmic_match = re.search(r'COSMIC:\s*(\d+)', data['db']['clAlternateID'])
            if cosmic_match:
                data['db']['_cosmic_id'] = cosmic_match.group(1)
    else:
        FAIL()

    if all_ok:
        print(' OK')
        all_data.append(data)
    else:
        print()

name_data = {'all_names': [data['name'] for data in all_data]}
for data in all_data:
    data.update(name_data)
    html_filename = data['name'] + '.html'        
    render_template(html_path, html_filename, data)
    for d_out, d_in in image_dirs:
        image_path = create_output_path('cell_line', 'img', d_out)
        base_filename = data['name'] + '.png'
        source_filename = os.path.join(cellline_path, d_in, base_filename)
        dest_filename = os.path.join(image_path, base_filename)
        shutil.copy(source_filename, dest_filename)
