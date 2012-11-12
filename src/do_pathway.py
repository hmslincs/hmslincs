from django.template import Template, Context
from django.template.loader import render_to_string
import django.conf
import os.path as op
import lxml.etree
import functools
import math
import PIL.Image
import argparse
import signature


# mapping from target names in signature.LATEST to names in the diagram
target_name_fixups = {
    u'JNK1': ['JNK1-2-3'],
    u'JNK2': ['JNK1-2-3'],
    u'JNK3': ['JNK1-2-3'],
    u'AKT1': ['AKT'],
    u'AKT2': ['AKT'],
    u'AKT3': ['AKT'],
    u'MNK2': ['MNK1-2'],
    u'WEE1': ['Wee1'],
    u'CHK': ['CHK1-2'],
    u'PI3K-ALPHA': ['PI3K'],
    u'PI3K-BETA': ['PI3K'],
    u'PI3K-DELTA': ['PI3K'],
    u'PI3K-GAMMA': ['PI3K'],
    u'C-MET': ['c-Met'],
    u'BCR-ABL': ['c-Abl'],
    u'ABL(T315I)': ['c-Abl'],
    u'C-ABL': ['c-Abl'],
    u'GSK3A': ['GSK3'],
    u'GSK3B': ['GSK3'],
    u'BRAF(V600E)': ['Raf'],
    u'B-RAF': ['Raf'],
    u'C-RAF': ['Raf'],
    u'P38-ALPHA': ['p38'],
    u'P38-BETA': ['p38'],
    u'RSK2': ['P90RSK'],
    u'JAK1': ['JAK1-2-3'],
    u'JAK2': ['JAK1-2-3'],
    u'JAK3': ['JAK1-2-3'],
    u'PKC-B': ['PKC'],
    u'C-KIT': ['c-Kit'],
    u'CHK1': ['CHK1-2'],
    u'SRC': ['Src'],
    u'GSK-3': ['GSK3'],
    u'IKK-BETA': ['IKK'],
    u'MTOR': ['mTOR'],
    u'MEK': ['MEK1-2'],
    u'MEK1': ['MEK1-2'],
    u'MEK2': ['MEK1-2'],
    u'CDK1': ['CDK'],
    u'CDK2': ['CDK'],
    u'CDK4': ['CDK'],
    u'CDK5': ['CDK'],
    u'CDK7': ['CDK'],
    u'CDK9': ['CDK'],
    u'AURORA': ['Aurora'],
    u'AURKA': ['Aurora'],
    u'AURKB': ['Aurora'],
    u'AURKC': ['Aurora'],
    u'HSP90 ALPHA': ['HSP90'],
    u'HSP90 BETA': ['HSP90'],
    u'P53': ['p53'],
    u'ERK1': ['ERK1-2'],
    u'ERK2': ['ERK1-2'],
    u'AMPK-ALPHA1': ['AMPK'],
    u'MTORC1': ['mTOR'],
    u'MTORC2': ['mTOR'],
    u'P38 MAPK': ['p38'],

    # TODO: PLK
    # TODO: DNA-PK not in diagram
    # TODO: FGFR -> FGFR1? compounds seem to be pan-FGFR or possibly FGFR1-selective
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
    for name, aliases in target_name_fixups.items():
        if name in signature_data:
            original_signatures = signature_data[name]
            del signature_data[name]
            for alias in aliases:
                alias_signatures = signature_data.setdefault(alias, [])
                alias_signatures += original_signatures

    # load OmniGraffle-exported html
    pathway_source_file = open(op.join(data_dir, 'pathway.html'))
    pathway_source = pathway_source_file.read()
    tree = lxml.etree.HTML(pathway_source)
    map_ = tree.xpath('//map')[0]
    img = tree.xpath('//img')[0]
    # turn <area> elts into positioned divs and build a set of their ids
    target_names = set()
    for area in map_.xpath('//area'):
        assert area.attrib['shape'] == 'poly'
        coords = map(lambda x: float(x)/2, area.attrib['coords'].split(','))
        coords_x = coords[::2]
        coords_y = coords[1::2]
        left = min(coords_x)
        top = min(coords_y)
        width = max(coords_x) - left
        height = max(coords_y) - top
        div = lxml.etree.Element('div')
        target_name = area.attrib['href']
        div.attrib['id'] = target_name
        target_names.add(target_name)
        div.attrib['class'] = 'pathway-hotspot'
        div.attrib['style'] = 'left: %dpx; top: %dpx; width: %dpx; height: %dpx;' % \
                              (left, top, width, height)
        img.addprevious(div)
    # delete the map since we no longer need it
    map_.getparent().remove(map_)

    # convert omnigraffle png output to jpg
    pathway_image = PIL.Image.open(op.join(data_dir, 'pathway.png'))
    pathway_image.save(op.join(out_dir_image, pathway_image_filename))

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

    signatures = [{ 'target_name': k,
                    'compounds': v,
                    'show_scale': any(c.signature for c in v) }
                  for k, v in signature_data.items() if k in target_names]
    cell_lines = list(enumerate(signature.cell_lines))
    cut_idx = int(math.ceil(len(cell_lines) / 2.0))
    ctx = {
        'signatures': signatures,
        'cell_lines': [cell_lines[:cut_idx],
                       cell_lines[cut_idx:]],
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
