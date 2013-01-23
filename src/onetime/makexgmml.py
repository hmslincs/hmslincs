from __future__ import division
import os
import os.path as op
import re
import collections as co

# Running this script (no arguments required)
#
# 1. generates a set of xgmml files (one for each file in the
#    DATADIR directory);
# 2. generates a cytoscape script;
# 3. prints the command line to feed to the Command Window of
#    Cytoscape's Command Tool plugin to run the script (from 2)
#    and thereby generate the png files specified by the xgmml
#    files (from 1);
#
# E.g.:
#
# % python src/onetime/makexgmml.py
# commandtool run file="/Users/berriz/Work/Sites/hmslincs/src/onetime/makepng"
#

# ---------------------------------------------------------------------------
SRCDIR = op.dirname(op.abspath(__file__))
BASEDIR = op.normpath(op.join(SRCDIR, '..', '..'))
DATADIR = op.join(BASEDIR, *'data networks data'.split())
XMLDIR = op.join(BASEDIR, *'data networks xgmml'.split())
IMGDIR = op.join(BASEDIR, *'django networks static networks img'.split())

NODES = co.OrderedDict((
                        ('center', co.OrderedDict((
                                      ('ce', (0.00, 0.00)),
                                    ))),
                        ('dummy', co.OrderedDict((
                                      ('nw', (-340.00, -340.00)),
                                      ('ne', (340.00, -340.00)),
                                      ('se', (340.00, 340.00)),
                                      ('sw', (-340.00, 340.00)),
                                    ))),
                        # the y-coord of ERK and AKT is the midpoint of the
                        # y-coords of FGF2 and SCF (or equivalently, of EFNA1
                        # and IGF1), to maximize the angle the edges from
                        # these nodes and the ERK and AKT nodes; this deviation
                        # a more symmetric arrangement (with both ERK and AKT
                        # nodes at y=0) is necessitated by the fact that the
                        # number of nodes in the 'middle' subset is odd.
                        ('inner', co.OrderedDict((
                                      ('ERK', (-60.00, -17.38)),
                                      ('AKT', (60.00, -17.38)),
                                    ))),
                        ('middle', co.OrderedDict((
                                      ('EPR', (0.00, -170.00)),
                                      ('HRG', (69.15, -155.30)),
                                      ('VEGF', (126.33, -113.75)),
                                      ('EFNA1', (161.68, -52.53)),
                                      ('IGF1', (169.07, 17.77)),
                                      ('IGF2', (147.22, 85.00)),
                                      ('INS', (99.92, 137.53)),
                                      ('HGF', (35.34, 166.29)),
                                      ('NGF', (-35.34, 166.29)),
                                      ('PDGF', (-99.92, 137.53)),
                                      ('FGF1', (-147.22, 85.00)),
                                      ('FGF2', (-169.07, 17.77)),
                                      ('SCF', (-161.68, -52.53)),
                                      ('EGF', (-126.33, -113.75)),
                                      ('BTC', (-69.15, -155.30)),
                                    ))),
                        ('outer', co.OrderedDict((
                                      ('ERBB3', (0.00, -270.00)),
                                      ('ERBB4', (83.43, -256.79)),
                                      ('VEGFR1', (158.70, -218.43)),
                                      ('VEGFR2', (218.43, -158.70)),
                                      ('VEGFR3', (256.79, -83.43)),
                                      ('EPHA2', (270.00, 0.00)),
                                      ('IGF1R', (256.79, 83.43)),
                                      ('IGF2R', (218.43, 158.70)),
                                      ('INSR', (158.70, 218.43)),
                                      ('MET', (83.43, 256.79)),
                                      ('TRKA', (0.00, 270.00)),
                                      ('PDGFRA', (-83.43, 256.79)),
                                      ('PDGFRB', (-158.70, 218.43)),
                                      ('FGFR1', (-218.43, 158.70)),
                                      ('FGFR2', (-256.79, 83.43)),
                                      ('FGFR3', (-270.00, 0.00)),
                                      ('FGFR4', (-256.79, -83.43)),
                                      ('CKIT', (-218.43, -158.70)),
                                      ('EGFR', (-158.70, -218.43)),
                                      ('ERBB2', (-83.43, -256.79)),
                                    ))),
                       ))


EDGES = dict(inner=(('VEGF', 'ERK'),
                    ('VEGF', 'AKT'),
                    ('PDGF', 'ERK'),
                    ('PDGF', 'AKT'),
                    ('NGF', 'ERK'),
                    ('NGF', 'AKT'),
                    ('INS', 'ERK'),
                    ('INS', 'AKT'),
                    ('IGF2', 'ERK'),
                    ('IGF2', 'AKT'),
                    ('IGF1', 'ERK'),
                    ('IGF1', 'AKT'),
                    ('HRG', 'ERK'),
                    ('HRG', 'AKT'),
                    ('HGF', 'ERK'),
                    ('HGF', 'AKT'),
                    ('FGF2', 'ERK'),
                    ('FGF2', 'AKT'),
                    ('FGF1', 'ERK'),
                    ('FGF1', 'AKT'),
                    ('EPR', 'ERK'),
                    ('EPR', 'AKT'),
                    ('EGF', 'ERK'),
                    ('EGF', 'AKT'),
                    ('EFNA1', 'ERK'),
                    ('EFNA1', 'AKT'),
                    ('BTC', 'ERK'),
                    ('BTC', 'AKT'),
                    ('SCF', 'ERK'),
                    ('SCF', 'AKT')),
             outer=(('VEGFR3', 'VEGF'),
                    ('VEGFR2', 'VEGF'),
                    ('VEGFR1', 'VEGF'),
                    ('TRKA', 'NGF'),
                    ('PDGFRB', 'PDGF'),
                    ('PDGFRA', 'PDGF'),
                    ('MET', 'HGF'),
                    ('INSR', 'INS'),
                    ('IGF2R', 'IGF2'),
                    ('IGF1R', 'IGF1'),
                    ('IGF1R', 'IGF2'),
                    ('FGFR4', 'FGF1'),
                    ('FGFR4', 'FGF2'),
                    ('FGFR3', 'FGF1'),
                    ('FGFR3', 'FGF2'),
                    ('FGFR2', 'FGF2'),
                    ('FGFR2', 'FGF1'),
                    ('FGFR1', 'FGF2'),
                    ('FGFR1', 'FGF1'),
                    ('ERBB4', 'HRG'),
                    ('ERBB4', 'BTC'),
                    ('ERBB4', 'EPR'),
                    ('ERBB3', 'HRG'),
                    ('EPHA2', 'EFNA1'),
                    ('EGFR', 'EGF'),
                    ('EGFR', 'BTC'),
                    ('EGFR', 'EPR'),
                    ('CKIT', 'SCF'))
             )


NORMALIZE = {'IGF-1': 'IGF1',
             'IGF-2': 'IGF2',
             'PDGF-BB': 'PDGF',
             'FGF-1': 'FGF1',
             'FGF-2': 'FGF2',
             'NGF-beta': 'NGF',
             'VEGF165': 'VEGF'}

MINDIAM = 40
MINWIDTH = 1
MAXWIDTH = 9
MINFONT = 10
MAXFONT = 19
BLACK = '#000000'
WHITE = '#ffffff'
DARKGRAY = '#666666'
GRAYCUTOFF = 128

# "magic" constants
SCALEFUDGE = 44
#FONTFUDGE = 0.075
FONTFUDGE = 1.35
ZOOMFUDGE = 4.0

# ---------------------------------------------------------------------------

def cycommands(title, xgmmlfile, pngfile, _zoom=ZOOMFUDGE):
    return '''
network import file="%(xgmmlfile)s"
network view fit
network view export file="%(pngfile)s" zoom=%(_zoom)s
network destroy name="%(title)s"
'''.lstrip() % locals()

def prologue(title):
    return \
"""
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<graph label="%(title)s" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:cy="http://www.cytoscape.org" xmlns="http://www.cs.rpi.edu/XGMML"  directed="1">
  <att name="documentVersion" value="1.1"/>
  <att name="networkMetadata">
    <rdf:RDF>
      <rdf:Description rdf:about="http://www.cytoscape.org/">
        <dc:title>%(title)s</dc:title>
        <dc:type>Protein-Protein Interaction</dc:type>
        <dc:description>N/A</dc:description>
        <dc:identifier>N/A</dc:identifier>
        <dc:date>2013-01-12 16:27:56</dc:date>
        <dc:source>http://www.cytoscape.org/</dc:source>
        <dc:format>Cytoscape-XGMML</dc:format>
      </rdf:Description>
    </rdf:RDF>
  </att>

  <att type="string" name="backgroundColor" value="#ffffff"/>
  <att type="real" name="GRAPH_VIEW_ZOOM" value="1.0"/>
  <att type="real" name="GRAPH_VIEW_CENTER_X" value="396.60433197021484"/>
  <att type="real" name="GRAPH_VIEW_CENTER_Y" value="418.22540283203125"/>
  <att type="boolean" name="NODE_SIZE_LOCKED" value="true"/>
""".lstrip('\n') % locals()


def nodexml(sym, idx, x, y,
            label='',
            diam=40,
            fontsize=0,
            fontcolor='',
            fill=WHITE,
            width=1,
            outline=DARKGRAY,
            transparency=''):

    nodelabel = '' if label == '' else 'cy:nodeLabel="%s" ' % label

    font = ('cy:nodeLabelFont="SansSerif.bold-0-%d" '
            % fontsize if fontsize and nodelabel else '')

    if fontcolor:
        fontcolor = ('<att type="string" name="node.labelColor" value="%s"/>'
                     % fontcolor)

    diameter = ("%f" if diam < 1 else "%.2f") % diam

    return ('<node label="%(sym)s" id="%(idx)d">'
                '%(fontcolor)s'
                '<graphics type="ELLIPSE" '
                'h="%(diameter)s" w="%(diameter)s" '
                '%(nodelabel)s'
                '%(font)s'
                'x="%(x).2f" y="%(y).2f" '
                'fill="%(fill)s" '
                '%(transparency)s'
                'width="%(width)d" outline="%(outline)s"'
                '/>'
            '</node>'
            % locals())


def edgexml(label, sourceid, targetid, width, arrow, color, linetype):
    fill = ('fill="%s" ' % color) if color else ''
    arrowcolor = ('cy:targetArrowColor="%s" ' % color) if arrow else ''

    return ('<edge label="%(label)s" '
            'source="%(sourceid)d" target="%(targetid)d"><graphics '
            'width="%(width)d" '
            '%(fill)s'
            'cy:targetArrow="%(arrow)d" '
            '%(arrowcolor)s'
            'cy:edgeLineType="%(linetype)s"'
            '/></edge>' % locals())

def epilogue():
    return '</graph>'


if True:
    import sys

    NodeParams = co.namedtuple('_nodeparams',
                               'label diam fontsize fill fontcolor')
    dummynode = NodeParams('', 1e-4, 0, WHITE, '')
    # centernode= NodeParams('', 200, 0, '#00ffff', '')
    fixednodes = dict(#ce=centernode,
                      ce=dummynode,
                      sw=dummynode,
                      nw=dummynode,
                      ne=dummynode,
                      se=dummynode)

    EdgeParams = co.namedtuple('_edgeparams',
                               'source target width arrow color linetype')

    fixededges = tuple(EdgeParams(src, tgt, 1, 0, '', 'DOT')
                       for src, tgt in EDGES['outer'])
    inneredges = set(EDGES['inner'])
    assert len(inneredges) == len(EDGES['inner'])

    allws = re.compile('^\s*$')

    def nodesizes(label='', basallevel=0,
                  _minfont=MINFONT, _maxfont=MAXFONT,
                  _fudgefactor=FONTFUDGE):
        basallevel = float(basallevel)
        assert 0 <= basallevel <= 1
        diam = MINDIAM + (basallevel * SCALEFUDGE)
        ll = len(label)
        # fontsize = (0 if ll == 0
        #             else min(int(_minfont + _fudgefactor * diam/ll),
        #                      _maxfont))
        fontsize = (0 if ll == 0
                    else max(min(int(_fudgefactor * diam/ll),
                                 _maxfont),
                             _minfont))
        return diam, fontsize

    def colors(phospholevel=0):
        phospholevel = float(phospholevel)
        assert 0 <= phospholevel <= 1
        r = round((1 - phospholevel) * 256)
        fill = '#%(n)02x%(n)02x%(n)02x' % {'n': min(r, 255)}
        fontcolor = BLACK if r > GRAYCUTOFF else WHITE
        return fill, fontcolor

    def edgesizes(response=None,
                  _minwidth=MINWIDTH,
                  _widthrng=MAXWIDTH-MINWIDTH+1):
        if response is None:
            return 1, 0
        response = float(response)
        assert 0 <= response <= 1
        return round(_minwidth + _widthrng * response), 6
        
    cerk = '#0000cc'
    cakt = '#ff0000'

    scriptfile = op.join(SRCDIR, 'makepng')

    # if True:
    #     import sys
    #     scriptfh = sys.stdout

    with open(scriptfile, 'w') as scriptfh:
        for d in os.listdir(DATADIR):
            nodeparams = dict(fixednodes)
            edgeparams = dict(erk=[], akt=[])

            with open(op.join(DATADIR, d)) as fh:
                for lineno, line in enumerate(fh):
                    if lineno == 0:
                        continue
                    if allws.match(line):
                        break

                    kinase, basallevel, phospholevel = line[:-1].split('\t')
                    diam, fontsize = nodesizes(kinase, basallevel)
                    fill, fontcolor = colors(phospholevel)
                    params = NodeParams(kinase, diam, fontsize, fill,
                                        fontcolor)
                    sym = kinase.upper()
                    assert sym not in nodeparams, sym
                    nodeparams[sym] = params

                for lineno, line in enumerate(fh):
                    if lineno == 0:
                        continue
                    if allws.match(line):
                        break
                    rec = line[:-1].split('\t')
                    srcnode = NORMALIZE.get(rec[0], rec[0])
                    sym = srcnode.upper()
                    assert sym not in nodeparams, sym
                    assert (sym, 'ERK') in inneredges
                    assert (sym, 'AKT') in inneredges

                    diam, fontsize = nodesizes(srcnode)
                    fill, fontcolor = colors()
                    nodeparams[sym] = NodeParams(srcnode, diam, fontsize,
                                                 fill, fontcolor)

                    werk, aerk = edgesizes(rec[1])
                    edgeparams['erk'].append(EdgeParams(sym, 'ERK', werk, aerk,
                                                        cerk, 'SOLID'))
                    wakt, aakt = edgesizes(rec[2])
                    edgeparams['akt'].append(EdgeParams(sym, 'AKT', wakt, aakt,
                                                        cakt, 'SOLID'))

            node2idx = dict()
            idx = 0

            edgeparams = edgeparams['erk'] + edgeparams['akt']
            edgeparams.extend(fixededges)

            title = d[:-4]
            xgmmlfile = op.join(XMLDIR, '%s.xgmml' % title)
            print >> scriptfh, cycommands(title, xgmmlfile,
                                          op.join(IMGDIR, '%s.png' % title))

            # if True:
            #     import sys
            #     out = sys.stdout

            with open(xgmmlfile, 'w') as out:

                print >> out, prologue(title)

                for grp, v in NODES.items():
                    for sym, (x, y) in v.items():
                        node2idx[sym] = idx
                        params = nodeparams[sym]
                        kwargs = params._asdict()
                        if grp == 'dummy':
                            kwargs['width'] = 0
                            kwargs['outline'] = '#ffffff'
                            kwargs['transparency'] = ('cy:nodeTransparency='
                                                      '"%s" '
                                                      % ('0.5' if sym == 'ce'
                                                         else '0'))
                        label = '%02d %s' % (-idx, sym)
                        print >> out, ('  %s'
                                       % nodexml(label, idx, x, y, **kwargs))
                                                       
                        idx -= 1

                for i, params in enumerate(edgeparams):
                    kwargs = params._asdict()
                    label = '%02d %s %s' % (i, params.source, params.target)
                    kwargs['sourceid'] = node2idx[kwargs.pop('source')]
                    kwargs['targetid'] = node2idx[kwargs.pop('target')]
                    print >> out, '  %s' % edgexml(label, **kwargs)

                print >> out, epilogue()

    print 'commandtool run file="%s"' % scriptfile
