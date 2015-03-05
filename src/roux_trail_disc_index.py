# -*- coding: utf-8 -*-

import sys
import os
import re
import codecs
import argparse
import itertools
import unipath
import csv
import django.conf
from django.template.loader import render_to_string



# Read RESOURCE_PATH from environ, or default to something that works for me.
resource_path_s = os.environ.get(
    'RESOURCE_PATH',
    '/home/jmuhlich/Dropbox (HMS-LSP)/Roux Hafner TRAIL_DISC_paper/website/')
resource_path = unipath.Path(resource_path_s)
hmslincs_path = unipath.Path(__file__).ancestor(2)

docroot_path = hmslincs_path.child(
    'temp', 'docroot', 'explore', 'roux-trail-disc')
img_src_path = resource_path.child('figures')

base_url = '/explore/roux-trail-disc/'

table = [{'name': u'Modulation of DISC activity (κ)',
          'treatment_map': [('TRAIL', 1), ('Mapatumumab', 52),
                            ('Apomab', 90), ('Mapatumumab+anti-Fc', 68),
                            ('Apomab+anti-Fc', 103),
                            ('TRAIL+FLIP-L overexpression', 124),
                            ('TRAIL+FLIP-S overexpression', 131)],
          'treatments': []},
         {'name': u'Modulation of activation timing (τ)',
          'treatment_map': [('Bortezomib+TRAIL', 27),
                            ('Bortezomib+Mapatumumab', 84),
                            ('Bortezomib+Mapatumumab+anti-Fc', 87),
                            ('Bortezomib+Apomab', 116),
                            ('Bortezomib+Apomab+anti-Fc', 120),
                            ('Bortezomib+TRAIL+FLIP-L overexpression', 138),
                            ('Bortezomib+TRAIL+FLIP-S overexpression', 141)],
          'treatments': []},
         {'name': u'Modulation of the cellular apoptotic threshold (θ)',
          'treatment_map': [('TRAIL+ABT-263', 40),
                            ('TRAIL+Bcl-2 overexpression', 144),
                            ('TRAIL+Bcl-2 overexpression+ABT-263', 158),
                            ('TRAIL+Bcl-XL overexpression', 149),
                            ('TRAIL+Bcl-XL overexpression+ABT-263', 160)],
          'treatments': []}]
empty_treatment = dict.fromkeys(['name', 'unit', 'doses'])

def main(argv):

    argparser = argparse.ArgumentParser(
        description='Build roux_trail_disc app resources.')
    args = argparser.parse_args()

    img_dest_path = docroot_path.child('img')

    treatment_reverse_map = {}
    for s_idx, section in enumerate(table):
        tmap = section['treatment_map']
        treatments = section['treatments'] = [empty_treatment] * len(tmap)
        for t_idx, (treatment_name, dataset_number) in enumerate(tmap):
            treatment_reverse_map[dataset_number] = s_idx, t_idx

    dose_img_paths = {}
    for p in img_src_path.child('doses').listdir():
        match = re.match('(\d{3}).*\.jpg$', p.name)
        if match:
            dataset_idx = match.group(1).lstrip('0')
            # Sanity check: should never see two images for the same dataset.
            assert dataset_idx not in dose_img_paths
            dose_img_paths[dataset_idx] = p

    data_file = open(resource_path.child('datasets_results_internal.tsv'))
    groups = itertools.groupby(
        csv.reader(data_file, delimiter='\t'),
        lambda x: re.match(r'\d', x[0]) is None)
    groups = (list(g) for k, g in groups)
    for headers, values in itertools.izip(groups, groups):
        treatment_row, header_row = headers
        s_idx, t_idx = treatment_reverse_map[int(values[0][0])]
        values = [dict(zip(header_row, v)) for v in values]
        values = [v for v in values if v['Dataset'] in dose_img_paths]
        name = table[s_idx]['treatment_map'][t_idx][0]
        unit = re.search(r'(?<=\()[^)]+', header_row[2]).group()
        # FIXME Factor out repeated reference to dose_img_paths[v['Dataset']].
        doses = [{'amount': v['Dose'],
                  'img_filename': dose_img_paths[v['Dataset']].name,
                  'img_path': dose_img_paths[v['Dataset']],
                  'id': as_css_identifier(dose_img_paths[v['Dataset']].stem)}
                 for v in values if v['Dataset'] in dose_img_paths]
        table[s_idx]['treatments'][t_idx] = {'name': name, 'unit': unit,
                                             'doses': doses}
    # Build up separate flat list of doses for convenience in the template.
    doses = [dose for section in table for treatment in section['treatments']
             for dose in treatment['doses']]
    # Sanity check: make sure there are no colliding dose ids. (Yes this code is
    # performance-naive but the list size is trivial.)
    dose_ids = [dose['id'] for dose in doses]
    assert len(dose_ids) == len(set(dose_ids))

    data = {'table': table,
            'doses': doses,
            'STATIC_URL': django.conf.settings.STATIC_URL,
            'BASE_URL': base_url,
            }
    docroot_path.mkdir(parents=True)
    render_template('roux_trail_disc/index.html', data,
                    docroot_path, 'index.html')

    popup_dest_path = img_dest_path.child('popup')
    popup_dest_path.mkdir(parents=True)
    for dose in doses:
        dest_path = popup_dest_path.child(dose['img_filename'])
        dose['img_path'].copy(dest_path)
        dest_path.chmod(0o644)

    globals().update(locals()) # XXX temp debug aid
    return 0


def as_css_identifier(s):
    """
    Sanitize a string for use as a CSS identifier (e.g. a class or id).

    Note that we don't remove leading hyphens, nor do we avoid introducing new
    ones. If they are a possibility with your data, you should apply a prefix to
    the values returned from this function to sidestep the issue entirely.
    """
    return re.sub(r'[^a-z0-9-]', '-', s, flags=re.IGNORECASE)


def render_template(template_name, data, dirname, basename):
    "Render a template with data to a file specified by dirname and basename."
    out_filename = unipath.Path(dirname, basename)
    content = render_to_string(template_name, data)
    with codecs.open(out_filename, 'w', 'utf-8') as out_file:
        out_file.write(content)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
