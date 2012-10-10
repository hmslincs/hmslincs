from __future__ import division
import sys
import collections as co
import random as rn
import csv
import re
import pprint as pp

import readtable as rt
import transpose as tr
import minmax as mm
import misc_utils as mu
import signature as si
import superdict as sd

# # ---------------------------------------------------------------------------

ISCLINICAL_CUTOFF = 2/3
ISSELECTIVE_CUTOFF = 2/3
ISPRIMARY_CUTOFF = 1/2

# import setparams as _sg
# _params = dict(
#     VERBOSE = False,
#     DATASRC = op.join(_workdir, 'attachments', 'MF',
#                       'JWGray_BCCL_drug_resp_encoded_v2-2.txt'),
#     C9 = 'c9.tsv',
#     FIELDDELIMITER = '\t',
#     COLHEADERSROW = 1,
#     COLSUBHEADERSROW = 2,
#     FIRSTDATAROW = 4,
#     ROWHEADERSCOL = 0,
#     FIRSTDATACOL = 1,
#     MAXVALMARKER = 'MAX',
#     NMAXVALCUTOFF = 3,
#     MAXVALSFILE = 'scratch/maxvals.tsv',
# )
# _sg.setparams(_params)
# del _sg, _params

# # ---------------------------------------------------------------------------

def convert_conc_string(v):
    return None if v == 'NA' else float(v)

def convert_conc_row(row):
    return tuple(convert_conc_string(v.strip()) for v in row)

def lims(col):
    vals = tuple(x for x in col if x is not None)
    return mm.minmax(vals) if len(vals) else (None, None)

def possible_lims():
    concs = '/Users/berriz/Work/attachments/MF/JWGray_drug_conc_v1.csv'
    with open(concs) as fh:
        allrows = tuple(csv.reader(fh))
    record = co.namedtuple('Record', allrows[0])
    table = (record(*(row[:3] +
                      list(convert_conc_row(row[3:-1])) +
                      row[-1:]))
             for row in allrows[1:])
    possible_lims = dict()
    for row in mu.unique(tuple((row.drug, row.c1, row.c9, row.units)
                               for row in table)):
        possible_lims.setdefault(row[0], []).append(tuple(row[1:3]))

    return possible_lims

def getlims():
    gi50 = '/Users/berriz/Work/scratch/gi50.tsv'
    header, namedrows = rt.readtable(gi50, headerrow=0)
    rows = tuple(convert_conc_row(nr[1:]) for nr in namedrows)
    cols = zip(*rows)
    errors = []
    def resolve(rng, candidates):
        assert rng[0] <= rng[1]

        found = []
        garbage = []
        puramierda = []

        for pl in candidates:
            if pl[0] <= rng[0] and rng[1] <= pl[1]:
                found.append(pl)
            elif pl[0] == rng[0] or rng[1] == pl[1]:
                garbage.append(pl)
            elif pl[0] < rng[0] or rng[1] < pl[1]:
                puramierda.append(pl)

        lfound = len(found)
        if lfound == 1:
            return found[0]

        if lfound == 0:
            lgarbage = len(garbage)
            if lgarbage == 1:
                errors.append('found garbage for %s %s' % (drug, rng))
                toshow = garbage
                ret = garbage[0]
            else:
                if lgarbage > 1 or len(puramierda):
                    errors.append('found PURA MIERDA for %s %s' % (drug, rng))
                    toshow = garbage + puramierda
                else:
                    errors.append('no dice for %s %s' % (drug, rng))
                    toshow = candidates
                ret = None
        elif lfound > 1:
            found2 = []
            for pl in found:
                if ((pl[0] == rng[0] <= rng[1]) or
                    (rng[0] <= rng[1] == pl[1])):
                    found2.append(pl)

            if len(found2) == 1:
                ret = found2[0]
            else:
                (_, imin) = mm.minmax((t[1]-t[0] for t in found), warg=True)[0]
                ret = found[imin]

            errors.append('too many dice for %s %s:' % (drug, rng))
            toshow = found

        for t in toshow:
            errors.append('  %s' % (t,))
        errors.append('')

        return ret

    d2l = dict()
    pls = possible_lims()
    for drug, col in zip(header[1:], cols):
        rng = lims(col)
        d2l[drug] = resolve(rng, pls[drug])

    if errors:
        print
        for e in errors:
            print e

    return d2l

def gettargets():
    tgts = '/Users/berriz/Work/attachments/MF/LBNL_Gray_drug_targets_encoded_10Feb.txt'
    _, rows = rt.readtable(tgts, headerrow=0)
    comma_split_re = re.compile(r'\s*,\s*')
    d2t = dict()
    for drug, info in rows:
        d2t.setdefault(drug, []).extend(comma_split_re.split(info))
    return d2t

def main(argv):
    d2l = getlims()
    d2t = gettargets()
    excerpt = '/Users/berriz/Work/scratch/excerpt.tsv'
    header, rows = rt.readtable(excerpt, headerrow=0)
    sigclass = co.namedtuple('sigclass', header[1:], rename=True)
    flds = set(si.SignatureData._fields)
    t2s = dict()
    rn.seed(0)
    for row in sorted(rows):
        drug, vv = row[0], row[1:]
        if drug not in d2t:
            continue
        rangetested = d2l[drug]
        signature = tuple(convert_conc_row(vv))
        isclinical = rn.random() < ISCLINICAL_CUTOFF
        isselective = rn.random() < ISSELECTIVE_CUTOFF
        isprimary = rn.random() < ISPRIMARY_CUTOFF

        data = si.SignatureData(**(sd.superdict(locals()).subdict(flds)))
        for t in d2t[drug]:
            t2s.setdefault(t, []).append(data)

    for vv in t2s.values():
        drugs = set(v.drug for v in vv)
        assert len(drugs) == len(vv)

    print '    LATEST =',
    pp.pprint(t2s)


if __name__ == '__main__':
    main(sys.argv[1:])
