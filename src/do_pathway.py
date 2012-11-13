from django.template import Template, Context
from django.template.loader import render_to_string
import django.conf
import os.path as op
import lxml.etree
import functools
import math
import PIL.Image
import argparse
import shutil
import signature


# mapping from target names in signature.LATEST to names in the diagram
target_name_fixups = {
    u'JNK1': 'JNK1-2-3',
    u'JNK2': 'JNK1-2-3',
    u'JNK3': 'JNK1-2-3',
    u'AKT1': 'AKT',
    u'AKT2': 'AKT',
    u'AKT3': 'AKT',
    u'MNK2': 'MNK1-2',
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
    u'P38-BETA': 'p38',
    u'RSK2': 'P90RSK',
    u'JAK1': 'JAK1-2-3',
    u'JAK2': 'JAK1-2-3',
    u'JAK3': 'JAK1-2-3',
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
    u'ALK': 'ALK2',
    u'ALK': 'ALK5',
    u'PLK1': 'PLK',
    u'PLK2': 'PLK',
    # didn't map PARP-2 to PARP since compound lists for both are currently identical
    }

if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='Build pathway app resources.')
    parser.add_argument('-n', '--no-signatures', action='store_true', default=False,
                        help='Skip building signature images')
    args = parser.parse_args()

    cur_dir = op.abspath(op.dirname(__file__))
    data_dir = op.join(cur_dir, '..', 'nui-wip', 'pathway')
    static_dir = op.join(cur_dir, '..', 'django', 'pathway', 'static', 'pathway')
    out_dir_html = static_dir
    out_dir_image = op.join(static_dir, 'img')
    pathway_image_filename = 'pathway.jpg'

    # tweak some target names
    signature_data = signature.LATEST.copy()
    for name, aliase in target_name_fixups.items():
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
    # copy jpg to static dir
    shutil.copy(pathway_image_path, out_dir_image)

    # fix up <img> attribs
    del img.attrib['usemap']
    img.attrib['id'] = 'pathway-img'
    img.attrib['src'] = '%spathway/img/%s' % (django.conf.settings.STATIC_URL,
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
        signatures_ctx.append({
                'target_name': target,
                'compounds': compounds,
                'show_scale': any(c.signature for c in compounds)
                })
    # build context data for cell lines and calculate midpoint
    cell_lines_ctx = list(enumerate(signature.cell_lines))
    cut_idx = int(math.ceil(len(cell_lines_ctx) / 2.0))

    ctx = {
        'signatures': signatures_ctx,
        # provide cell lines in two equal-sized lists for display on two rows
        'cell_lines': [cell_lines_ctx[:cut_idx],
                       cell_lines_ctx[cut_idx:]],
        'pathway_source': pathway_source,
        'STATIC_URL': django.conf.settings.STATIC_URL,
        }
    out_file = open(op.join(out_dir_html, 'index.html'), 'w')
    out_file.write(render_to_string('pathway/index.html', ctx))
    out_file.close()

    # generate the signature images
    if not args.no_signatures:
        for target, compounds in signature_data.items():
            signature.signature_images(target, compounds, out_dir_image)

    # generate images for the cell lines legend
    signature.cell_line_images(out_dir_image)
