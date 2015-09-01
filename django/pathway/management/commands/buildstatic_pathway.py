from django.template import Template, Context
from django.template.loader import render_to_string
from django.core.management.base import BaseCommand, CommandError
from django.contrib.flatpages.models import FlatPage
from django.contrib.sites.models import Site

import django.conf
import os
import os.path as op
import lxml.etree
import functools
import math
import PIL.Image
from optparse import make_option
import shutil
from unipath import Path
import pathway.signature as signature


# mapping from target names in signature.LATEST to names in the diagram
target_name_fixups = {
    u'JNK1': 'JNK',
    u'JNK2': 'JNK',
    u'JNK3': 'JNK',
    u'AKT1': 'AKT',
    u'AKT2': 'AKT',
    u'AKT3': 'AKT',
    u'MNK2': 'MNK',
    u'CHK': 'CHK1-2',
    u'PI3K-ALPHA': 'PI3K',
    u'PI3K-BETA': 'PI3K',
    u'PI3K-DELTA': 'PI3K',
    u'PI3K-GAMMA': 'PI3K',
    u'BCR-ABL': 'C-ABL',
    u'ABL(T315I)': 'C-ABL',
    u'GSK3A': 'GSK3',
    u'GSK3B': 'GSK3',
    u'BRAF(V600E)': 'RAF',
    u'B-RAF': 'RAF',
    u'C-RAF': 'RAF',
    u'P38-ALPHA': 'P38',
    u'P38-BETA': 'P38',
    u'RSK2': 'P90RSK',
    u'JAK1': 'JAK',
    u'JAK2': 'JAK',
    u'JAK3': 'JAK',
    u'PKC-B': 'PKC',
    u'CHK1': 'CHK1-2',
    u'GSK-3': 'GSK3',
    u'IKK-BETA': 'IKK',
    u'MEK': 'MEK1-2',
    u'MEK1': 'MEK1-2',
    u'MEK2': 'MEK1-2',
    u'CDK1': 'CDK',
    u'CDK2': 'CDK',
    u'CDK4': 'CDK',
    u'CDK5': 'CDK',
    u'CDK7': 'CDK',
    u'CDK9': 'CDK',
    u'AURKA': 'AURORA',
    u'AURKB': 'AURORA',
    u'AURKC': 'AURORA',
    u'HSP90 ALPHA': 'HSP90',
    u'HSP90 BETA': 'HSP90',
    u'ERK1': 'ERK1-2',
    u'ERK2': 'ERK1-2',
    u'AMPK-ALPHA1': 'AMPK',
    u'MTORC1': 'MTOR',
    u'MTORC2': 'MTOR',
    u'P38 MAPK': 'P38',
    u'FGFR3': 'FGFR',
    u'ALK2': 'ALK',
    u'ALK5': 'ALK',
    u'PLK1': 'PLK',
    u'PLK3': 'PLK',
    u'BCL2': 'BCL-2',
    # didn't map PARP-2 to PARP since compound lists for both are currently identical
    }

target_display_names = {
    'AURORA': 'Aurora',
    'BCL-2': 'Bcl-2',
    'C-ABL': 'c-Abl',
    'C-KIT': 'c-Kit',
    'C-MET': 'c-Met',
    'CDC25': 'Cdc25',
    'CHK1-2': 'CHK1/2',
    'ERK1-2': 'ERK1/2',
    'MEK1-2': 'MEK1/2',
    'MTOR': 'mTOR',
    'P38': 'p38',
    'P53': 'p53',
    'P90RSK': 'p90RSK',
    'RAF': 'Raf',
    'SRC': 'Src',
    'WEE1': 'Wee1',
    }

target_protein_ids = {
    'AKT': (('200482', 'AKT1'), ('200483', 'AKT2'), ('200484', 'AKT3')),
    'ALK': (('200562', 'ALK2'), ('200563', 'ALK3'), ('200564', 'ALK5')),
    'AMPK': (('200486', 'AMPK-alpha1'), ('200487', 'AMPK-alpha2')),
    'ATM': '200488',
    'AURORA': (('200489', 'AURKA'), ('200490', 'AURKB'), ('200491', 'AURKC')),
    'BCL-2': '200493',
    'C-ABL': (('200495', 'c-Abl'), ('200566', 'Bcr-Abl')),
    'C-KIT': '200501',
    'C-MET': '200502',
    'CDK': (('200498', 'CDK1'), ('200575', 'CDK2'), ('200576', 'CDK4'), ('200577', 'CDK5'), ('200578', 'CDK6'), ('200579', 'CDK7'), ('200580', 'CDK9')),
    'CHK1-2': (('200499', 'CHK1'), ('200500', 'CHK2')),
    'CSF1R': '200504',
    'DDR1': '200505',
    'DNA-PK': '200506',
    'EGFR': '200507',
    'EPHB3': '200508',
    'ERBB2': '200509',
    'ERK1-2': (('200510', 'ERK1'), ('200511', 'ERK2')),
    'ERK5': '200512',
    'FAK': '200513',
    'FGFR': (('200514', 'FGFR1'), ('200591', 'FGFR3')),
    'FLT3': '200515',
    'GSK3': (('200516', 'GSK3A'), ('200517', 'GSK3B')),
    'HSP90': (('200594', 'HSP90 alpha'), ('200595', 'HSP90 beta')),
    'IGF1R': '200519',
    'IKK': (('200520', 'IKK-alpha'), ('200521', 'IKK-beta'), ('200522', 'IKK-epsilon')),
    'JAK': (('200523', 'JAK1'), ('200524', 'JAK2'), ('200525', 'JAK3')),
    'JNK': (('200526', 'JNK1'), ('200527', 'JNK2'), ('200528', 'JNK3')),
    'MDM2': '200529',
    'MEK1-2': (('200530', 'MEK1'), ('200531', 'MEK2')),
    'MEK5': '200532',
    'MNK': (('200535', 'MNK1'), ('200536', 'MNK2')),
    'MTOR': '200537',
    'P38': (('200539', 'p38-alpha'), ('200540', 'p38-beta'), ('200541', 'p38-delta'), ('200542', 'p38-gamma')),
    'P53': '200543',
    'P90RSK': '200545',
    'PARP': (('200546', 'PARP'), ('200609', 'PARP-2')),
    'PDK1': '200547',
    'PI3K': (('200634', 'PI3K-alpha'), ('200635', 'PI3K-beta'), ('200636', 'PI3K-delta'), ('200637', 'PI3K-gamma'),),
    'PKC': '200549',
    'PLK': (('200551', 'PLK1'), ('200614', 'PLK2'), ('200615', 'PLK3')),
    'RAF': (('200494', 'B-Raf'), ('200503', 'C-Raf')),
    'SRC': '200555',
    'WEE1': '200558',
    }


class Command(BaseCommand):
    help = 'Builds the static assets and html chunks'
    option_list = BaseCommand.option_list + (
        make_option('-n', '--no-signatures', action='store_true',
                    default=False, help='Skip building signature images'),
        )

    def handle(self, *args, **options):
        #from django.core.files.storage import default_storage
        #from django.core.files.base import ContentFile
        #path = default_storage.save('foo.txt', ContentFile('new content'))
        #self.stdout.write("the path to foo.txt is: %s\n" % path)

        url = '/explore/pathway/'
        content = generate_images_and_index(options)

        page, created = FlatPage.objects.get_or_create(url=url)
        page.title = 'Kinase inhibitor pathways'
        page.content = content
        page.template_name = 'pathway/base.html'
        page.sites.clear()
        page.sites.add(Site.objects.get_current())
        page.save()


def generate_images_and_index(options):

    app_dir = Path(__file__).absolute().ancestor(3)
    data_dir = app_dir.child('resources')
    static_dir = app_dir.child('static', 'pathway')
    out_dir_image = static_dir.child('g')
    out_dir_image.mkdir()
    pathway_image_filename = 'pathway.jpg'

    # tweak some target names
    signature_data = signature.LATEST.copy()
    for name, alias in target_name_fixups.items():
        if name in signature_data:
            original_signatures = signature_data[name]
            del signature_data[name]
            alias_signatures = signature_data.setdefault(alias, [])
            alias_signatures += original_signatures

    # load OmniGraffle-exported html
    pathway_source_file = open(op.join(data_dir, 'pathway.html'))
    pathway_source = pathway_source_file.read()
    tree = lxml.etree.HTML(pathway_source)
    map_ = tree.xpath('//map')[0]
    img = tree.xpath('//img')[0]
    # turn <area> elts into positioned divs and build a set of their ids
    pathway_targets = set()
    for area in map_.xpath('//area'):
        assert area.attrib['shape'] == 'poly'
        coords = map(lambda x: float(x)/2, area.attrib['coords'].split(','))
        coords_x = coords[::2]
        coords_y = coords[1::2]
        left = min(coords_x)
        top = min(coords_y)
        width = max(coords_x) - left
        height = max(coords_y) - top
        # grow the hotspots by 30% in each direction
        scale = 0.30
        left -= width * scale / 2
        top -= height * scale / 2
        width *= (1 + scale)
        height *= (1 + scale)
        div = lxml.etree.Element('div')
        target_name = area.attrib['href']
        div.attrib['id'] = target_name
        pathway_targets.add(target_name)
        div.attrib['class'] = 'pathway-hotspot'
        div.attrib['style'] = 'left: %dpx; top: %dpx; width: %dpx; height: %dpx;' % \
                              (left, top, width, height)
        img.addprevious(div)
    # delete the map since we no longer need it
    map_.getparent().remove(map_)

    # read omnigraffle jpg output metadata
    pathway_image_path = op.join(data_dir, pathway_image_filename)
    pathway_image = PIL.Image.open(pathway_image_path)
    # copy jpg to static dir, first removing destination (if they exist) to
    # prevent permissions issues
    out_dir_image.child(pathway_image_filename).remove()
    shutil.copy(pathway_image_path, out_dir_image)

    # fix up <img> attribs
    del img.attrib['usemap']
    img.attrib['id'] = 'pathway-img'
    img.attrib['src'] = '%spathway/g/%s' % (django.conf.settings.STATIC_URL,
                                              pathway_image_filename)
    img.attrib['width'] = str(pathway_image.size[0])
    img.attrib['height'] = str(pathway_image.size[1])
    # turn the tree back into html source
    formatter = functools.partial(lxml.etree.tostring,
                                  pretty_print=True, method='html')
    pathway_source = ''.join(map(formatter, tree[0].getchildren()))

    # clean up signature_data and build template context data structure
    old_signature_data = signature_data
    signature_data = {}
    signatures_ctx = []
    for target, compounds in old_signature_data.items():
        # filter signature_data down to targets that are actually in the map
        if target not in pathway_targets:
            continue
        # sort compounds by name
        compounds = sorted(set(compounds), key=lambda c: c.drug)
        # strip "HMSL" prefix from drug_ids
        compounds = [c._replace(drug_id=c.drug_id.replace('HMSL', ''))
                     for c in compounds]
        # update new signature_data
        signature_data[target] = compounds
        # update context data
        ctx = {
            'target_name': target,
            'target_display': target_display_names.get(target, target),
            'compounds': compounds,
            'show_scale': any(c.signature for c in compounds)
            }
        protein_id = target_protein_ids[target]
        if isinstance(protein_id, basestring):
            ctx['protein_id_single'] = protein_id
        else:
            ctx['protein_id_list'] = protein_id
        signatures_ctx.append(ctx)
    # build context data for cell lines and calculate midpoint
    cell_lines_ctx = list(enumerate(signature.cell_lines))
    cut_idx = int(math.ceil(len(cell_lines_ctx) / 2.0))

    ctx = {
        'signatures': signatures_ctx,
        # provide cell lines in two equal-sized lists for display on two rows
        'cell_lines': [cell_lines_ctx[:cut_idx],
                       cell_lines_ctx[cut_idx:]],
        'pathway_source': pathway_source,
        }

    page_content = render_to_string('pathway/index.html', ctx)

    # generate the signature images
    if not options['no_signatures']:
        for target, compounds in signature_data.items():
            signature.signature_images(target, compounds, out_dir_image)

    # generate images for the cell lines legend
    signature.cell_line_images(out_dir_image)

    return page_content
