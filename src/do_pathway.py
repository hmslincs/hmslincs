from django.template import Template, Context
from django.template.loader import render_to_string
import django.conf
import os.path as op
import lxml.etree
import functools
import signature


# mapping from target names in signature.LATEST to names in the diagram
target_name_fixups = {
    u'AKT1-2': ['AKT'],
    u'Aurora kinase': ['Aurora'],
    u'CDC25S': ['Cdc25'],
    u'CDK': ['CDK1'],
    u'CDK1/CCNB': ['CDK1'],
    u'EGFR/ERBB2': ['EGFR', 'ERBB2'],
    u'FLT-3': ['FLT3'],
    u'Hsp90': ['HSP90'],
    u'IKK2 (IkB kinase 2)': ['IKK'],
    u'JNK': ['JNK2', 'JNK3'],
    u'MEK': ['MEK1', 'MEK2'],
    u'PI3K gamma': ['PI3K'],
    u'Ras-Net (Elk-3)': ['Ras'],
    }

if __name__ == '__main__':

    cur_dir = op.abspath(op.dirname(__file__))
    data_dir = op.join(cur_dir, '..', 'nui-wip', 'pathway')
    static_dir = op.join(cur_dir, '..', 'django', 'pathway', 'static', 'pathway')
    out_dir_html = static_dir
    out_dir_image = op.join(static_dir, 'img')

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
    # turn <area> elts into positioned divs
    for area in map_.xpath('//area'):
        assert area.attrib['shape'] == 'poly'
        coords = map(int, area.attrib['coords'].split(','))
        coords_x = coords[::2]
        coords_y = coords[1::2]
        left = min(coords_x)
        top = min(coords_y)
        width = max(coords_x) - left
        height = max(coords_y) - top
        div = lxml.etree.Element('div')
        div.attrib['id'] = area.attrib['href']
        div.attrib['class'] = 'pathway-target'
        div.attrib['style'] = 'left: %dpx; top: %dpx; width: %dpx; height: %dpx;' % \
                              (left, top, width, height)
        img.addprevious(div)
    # delete the map since we no longer need it
    map_.getparent().remove(map_)
    # fix up <img> attribs
    del img.attrib['usemap']
    img.attrib['id'] = 'pathway-img'
    img.attrib['src'] = '%spathway/img/%s' % (django.conf.settings.STATIC_URL,
                                           img.attrib['src'])
    # turn the tree back into html source
    formatter = functools.partial(lxml.etree.tostring,
                                  pretty_print=True, method='html')
    pathway_source = ''.join(map(formatter, tree[0].getchildren()))

    signatures = map(signature.template_context, *zip(*signature_data.items()))
    ctx = {
        'signatures': signatures,
        'pathway_source': pathway_source,
        'STATIC_URL': django.conf.settings.STATIC_URL,
        }
    out_file = open(op.join(out_dir_html, 'index.html'), 'w')
    out_file.write(render_to_string('pathway/index.html', ctx))
    out_file.close()

    # generate the signature images
    for target, compounds in signature_data.items():
        signature.signature_images(target, compounds, out_dir_image)

