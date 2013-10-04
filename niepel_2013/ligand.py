from __future__ import print_function
from niepel_2013 import *
import openpyxl
import jinja2
import requests
import os
import re
import codecs
import shutil


ligand_path = resource_path('SignalingPage', 'LigandPage')

filename = os.path.join(ligand_path, 'Ligand_info.xlsx')
workbook = openpyxl.load_workbook(filename)
sheet = workbook.worksheets[0]
column_names = ('hmsl_id', 'family', 'full_name', 'name',
                'vendor_catalog_ignored', 'uniprot_id_ignored', 'concentration',
                'comment')

filename_affinities = os.path.join(ligand_path,
                                   'ligand receptor affinities summary.xlsx')
workbook_affinities = openpyxl.load_workbook(filename_affinities)
sheet_affinities = workbook_affinities.worksheets[0]

template_env = jinja2.Environment(
    loader=jinja2.PackageLoader('niepel_2013', 'templates'))
ligand_template = template_env.get_template('ligand.html')

image_dirs = [
    ('doseresponse', 'DoseResponsePlots'),
    ('pathwaybias', 'PathwayBiasPlots'),
    ('responsekinetics', 'ResponseKinetics'),
    ('sensitivity', 'SensitivityClass'),
    ('timecourse', 'TimeCoursePlots'),
    ]

html_path = create_output_path('ligand')

all_data = []
print(' ' * 15 + 'DR PB RK SE TC RA DB UP  status')

for row in sheet.rows[1:]:

    data = dict(zip(column_names, (r.value for r in row)))
    print('%-15s' % data['name'], end='')

    plot_filename = data['name'] + '.png'
    all_ok = all([print_status_accessible(ligand_path, d_in, plot_filename)
                  for d_out, d_in in image_dirs])

    for row_affinity in sheet_affinities.rows[1:]:
        if row_affinity[0].value == data['name']:
            affinity_raw = [cell.value for cell in row_affinity[1:9]]
            affinity_pairs = zip(affinity_raw[0::2], affinity_raw[1::2])
            affinity_dicts = [{'name': name, 'kd': kd}
                              for name, kd in affinity_pairs
                              if name and kd]
            affinity_reference = row_affinity[9].value
            data['affinity'] = {'receptors': affinity_dicts,
                                'reference': affinity_reference}
            break
    if 'affinity' in data:
        PASS()
    else:
        FAIL()
        all_ok = False

    db_data = None
    db_url = ('http://lincs.hms.harvard.edu/db/api/v1/protein/%s/' %
              data['hmsl_id'])
    db_response = requests.get(db_url)
    if db_response.ok:
        PASS()
        data['db'] = db_response.json()
    else:
        FAIL()
        all_ok = False

    if 'db' in data:
        uniprot_url = ('http://www.uniprot.org/uniprot/%s.txt' %
                       data['db']['ppUniprotID'])
        uniprot_response = requests.get(uniprot_url)
    # Avoid nested 'if', otherwise we'd need to duplicate the FAIL/all_ok code.
    # Ideally we would write a little more library code to support this idiom.
    if 'db' in data and uniprot_response.ok:
        PASS()
        mw_match = re.search('\nSQ .*?(\d+) MW;', uniprot_response.content)
        molecular_weight = int(mw_match.group(1)) / 1000
        data['molecular_weight'] = molecular_weight
    else:
        FAIL()
        all_ok = False

    if all_ok:
        print(' OK')
        all_data.append(data)
    else:
        print()

name_data = {'all_names': [data['name'] for data in all_data]}
for data in all_data:
    data.update(name_data)
    html_filename = data['name'] + '.html'        
    render_template(ligand_template, data, html_path, html_filename)
    image_filename = data['name'] + '.png'
    copy_images(image_dirs, image_filename, ligand_path, ('ligand', 'img'))
