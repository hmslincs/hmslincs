# -*- coding: utf-8 -*-

import sys
import os
import re
import codecs
import argparse
import itertools
import unipath
import csv
import wand.image
import django.conf
from django.template.loader import render_to_string
from django.core.management.base import BaseCommand, CommandError
from django.contrib.flatpages.models import FlatPage
from django.contrib.sites.models import Site
from optparse import make_option


table = [{'name': u'Modulation of DISC activity (k)',
          'schematic_page': 1,
          'treatment_map': [('TRAIL', '', 1), ('Mapatumumab', '', 52),
                            ('Apomab', '', 90), ('Mapatumumab', 'anti-Fc', 68),
                            ('Apomab', 'anti-Fc', 103),
                            ('TRAIL', 'FLIP-L overexpression', 124),
                            ('TRAIL', 'FLIP-S overexpression', 131)],
          'treatments': [], 'num_columns': 0, 'num_dose_columns': 0,
          'num_padding_columns': 0},
         {'name': u'Modulation of activation timing (τ)',
          'schematic_page': 3,
          'treatment_map': [('TRAIL', 'Bortezomib', 27),
                            ('Mapatumumab', 'Bortezomib', 84),
                            ('Mapatumumab', 'Bortezomib + anti-Fc', 87),
                            ('Apomab', 'Bortezomib', 116),
                            ('Apomab', 'Bortezomib + anti-Fc', 120),
                            ('TRAIL', 'Bortezomib + FLIP-L overexpression', 138),
                            ('TRAIL', 'Bortezomib + FLIP-S overexpression', 141)],
          'treatments': [], 'num_columns': 0, 'num_dose_columns': 0,
          'num_padding_columns': 0},
         {'name': u'Modulation of the cellular apoptotic threshold (θ)',
          'schematic_page': 2,
          'treatment_map': [('TRAIL', 'ABT-263', 40),
                            ('TRAIL', 'Bcl-2 overexpression', 144),
                            ('TRAIL', 'ABT-263 + Bcl-2 overexpression', 158),
                            ('TRAIL', 'Bcl-XL overexpression', 149),
                            ('TRAIL', 'ABT-263 + Bcl-XL overexpression', 160)],
          'treatments': [], 'num_columns': 0, 'num_dose_columns': 0,
          'num_padding_columns': 0}]
data_filenames = ['Aggregate_SingleCell_results.tsv', 'All_SingleCell_data.zip',
                  'Results_other_lines.zip', 'scripts.zip']
empty_treatment = dict.fromkeys(['name', 'unit', 'doses'])

popup_target_width = 939 * 2
schematic_target_width = 230 * 2


class Command(BaseCommand):
    help = 'Builds the static assets and html chunks'
    option_list = BaseCommand.option_list + (
       make_option('-n', '--no-images', action='store_true', default=False,
                   help='Skip building images'),
       make_option('-d', '--no-data', action='store_true', default=False,
                   help='Skip building data download files'),
       make_option('-r', '--resource-path',
                   default=('/home/jmuhlich/Dropbox (HMS-LSP)/'
                            'Roux Hafner TRAIL_DISC_paper/website/'),
                   help=('Path to resource files (contains "figures" and '
                         '"data" directories)'))
       )

    def handle(self, *args, **options):

        url = '/explore/trail-threshold-variability/'
        content = build_static(options)

        page, created = FlatPage.objects.get_or_create(url=url)
        page.title = ('Fractional killing arises from cell-to-cell '
                      'variability in overcoming a caspase activity threshold')
        page.content = content
        page.template_name = 'trail_threshold_variability/base.html'
        page.sites.clear()
        page.sites.add(Site.objects.get_current())
        page.save()


def build_static(options):

    app_path = unipath.Path(__file__).absolute().ancestor(3)
    static_path = app_path.child('static', 'trail_threshold_variability')
    generated_path = static_path.child('g')
    generated_path.mkdir()

    resource_path = unipath.Path(options['resource_path'])

    img_src_path = resource_path.child('figures')
    popup_dest_path = generated_path.child('popup')
    schematic_dest_path = generated_path.child('schematic')

    data_src_path = resource_path.child('data')
    data_dest_path = generated_path.child('data')

    treatment_reverse_map = {}
    for s_idx, section in enumerate(table):
        tmap = section['treatment_map']
        treatments = section['treatments'] = [empty_treatment] * len(tmap)
        for t_idx, (t_main, t_other, dataset_number) in enumerate(tmap):
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
        t_main, t_other = table[s_idx]['treatment_map'][t_idx][0:2]
        unit = re.search(r'(?<=\()[^)]+', header_row[2]).group()
        # FIXME Factor out repeated reference to dose_img_paths[v['Dataset']].
        doses = [{'amount': v['Dose'],
                  'img_filename': dose_img_paths[v['Dataset']].name,
                  'img_path': dose_img_paths[v['Dataset']],
                  'id': as_css_identifier(dose_img_paths[v['Dataset']].stem)}
                 for v in values if v['Dataset'] in dose_img_paths]
        table[s_idx]['treatments'][t_idx] = {'name_main': t_main,
                                             'name_other': t_other,
                                             'unit': unit, 'doses': doses}
    max_dose_columns = max(len(treatment['doses']) for section in table
                           for treatment in section['treatments'])
    for section in table:
        n = max(len(treatment['doses']) for treatment in section['treatments'])
        section['num_columns'] = n + 1
        section['num_dose_columns'] = n
        section['num_padding_columns'] = max_dose_columns - n
    doses = [dose for section in table for treatment in section['treatments']
             for dose in treatment['doses']]

    # Sanity check: make sure there are no colliding dose ids. (Yes this code is
    # performance-naive but the list size is trivial.)
    dose_ids = [dose['id'] for dose in doses]
    assert len(dose_ids) == len(set(dose_ids))

    # Assemble data for template and render html.
    data = {'table': table,
            'STATIC_URL': django.conf.settings.STATIC_URL,
            }
    content = render_to_string('trail_threshold_variability/index.html', data)

    if not options['no_images']:
        # Resize and copy popup images.
        popup_dest_path.mkdir()
        for dose in doses:
            dest_path = popup_dest_path.child(dose['img_filename'])
            with wand.image.Image(filename=dose['img_path']) as img, \
                    open(dest_path, 'w') as f:
                scale = float(popup_target_width) / img.width
                target_size = [int(round(d * scale)) for d in img.size]
                img.resize(*target_size, blur=1.5)
                img.compression_quality = 20
                img.format = 'JPEG'
                img.save(file=f)
                dest_path.chmod(0o644)
        # Extract and copy schematic images.
        schematic_dest_path.mkdir()
        schematic_path = img_src_path.child('schematics', 'Trajectories_schematics.pdf')
        with wand.image.Image(filename=schematic_path, resolution=500) as img:
            for section in table:
                page_number = section['schematic_page']
                page = wand.image.Image(image=img.sequence[page_number])
                page.alpha_channel = False
                scale = float(schematic_target_width) / page.width
                target_size = [int(round(d * scale)) for d in page.size]
                page.resize(*target_size)
                page.compression_quality = 100
                page.format = 'JPEG'
                filename = '{}.jpg'.format(page_number)
                dest_path = schematic_dest_path.child(filename)
                page.save(filename=dest_path)
                dest_path.chmod(0o644)

    if not options['no_data']:
        # Copy data download files.
        data_dest_path.mkdir(parents=True)
        for filename in data_filenames:
            src_path = data_src_path.child(filename)
            dest_path = data_dest_path.child(filename)
            src_path.copy(dest_path)
            dest_path.chmod(0o644)

    return content


def as_css_identifier(s):
    """
    Sanitize a string for use as a CSS identifier (e.g. a class or id).

    Note that we don't remove leading hyphens, nor do we avoid introducing new
    ones. If they are a possibility with your data, you should apply a prefix to
    the values returned from this function to sidestep the issue entirely.
    """
    return re.sub(r'[^a-z0-9-]', '-', s, flags=re.IGNORECASE)
