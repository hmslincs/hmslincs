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
    # move <area> hrefs to ids
    for elt in tree.xpath('//area'):
        elt.attrib['id'] = elt.attrib['href']
        del elt.attrib['href']
    # fix up <map> attribs
    map_elt = tree.xpath('//map')[0]
    map_elt.attrib['id'] = 'pathway-map'
    del map_elt.attrib['name']
    # fix up <img> attribs
    img_elt = tree.xpath('//img')[0]
    img_elt.attrib['usemap'] = '#pathway-map'
    img_elt.attrib['id'] = 'pathway-img'
    img_elt.attrib['src'] = '%s/pathway/%s' % (django.conf.settings.STATIC_URL,
                                               img_elt.attrib['src'])
    # turn the tree back into html source
    formatter = functools.partial(lxml.etree.tostring,
                                  pretty_print=True, method='html')
    pathway_source = ''.join(map(formatter, tree[0].getchildren()))

    signatures = map(signature.template_context, *zip(*signature_data.items()))
    for target, compounds in signature_data.items():
        signature.signature_images(target, compounds, out_dir_image)
    ctx = {
        'signatures': signatures,
        'pathway_source': pathway_source,
        'STATIC_URL': django.conf.settings.STATIC_URL,
        }

    out_file = open(op.join(out_dir_html, 'index.html'), 'w')
    out_file.write(render_to_string('pathway/index.html', ctx))
    out_file.close()
