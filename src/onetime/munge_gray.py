import sys
import os
import os.path as op
import csv
import re
import itertools as it
import collections as co

_workdir = op.join(os.environ['HOME'], 'Work')
sys.path.insert(1, op.join(_workdir,
                           *('Sites hmslincs src'.split())))

import misc_utils as mu
import partition as pa
import noclobberdict as ncd

# ---------------------------------------------------------------------------

import setparams as _sg
_params = dict(
    VERBOSE = False,
    DATASRC = op.join(_workdir, 'attachments', 'MF',
                      'JWGray_BCCL_drug_resp_encoded_v2-2.txt'),
    C9 = 'c9.tsv',
    FIELDDELIMITER = '\t',
    COLHEADERSROW = 1,
    COLSUBHEADERSROW = 2,
    FIRSTDATAROW = 4,
    ROWHEADERSCOL = 0,
    FIRSTDATACOL = 1,
    MAXVALMARKER = 'MAX',
    NMAXVALCUTOFF = 3,
    MAXVALSFILE = 'scratch/maxvals.tsv',
)
_sg.setparams(_params)
del _sg, _params

# ---------------------------------------------------------------------------

def isna(v, _nare=re.compile('^\s*NA$')):
    return bool(_nare.search(v))

def isvalid(v):
    return not (isna(v) or v == MAXVALMARKER)

def tofloat(v, _nare=re.compile('^\s*NA$')):
    try:
        return float(v)
    except ValueError, e:
        if not _nare.search(v):
            raise ValueError('%s (%s)' % (str(e), v))
        return None


def read_maxvals(path):
    with open(path) as fh:
        ret = dict((row[0].strip(), row[1])
                   for row in csv.reader(fh, delimiter='\t'))
    return ret


def score_cols(rows):
    ncols = len(rows[0])
    scores = [0] * ncols

    for row in rows:
        assert len(row) == ncols
        for k, (s, v) in enumerate(zip(scores, row)):
            if isvalid(v):
                scores[k] += 1

    return scores


def score_rows(rows):
    nrows = len(rows)
    scores = [0] * nrows
    ncols = len(rows[0])
    for k, row in enumerate(rows):
        assert len(row) == ncols
        # print '%02d: %s' % (k, row)
        for i, v in enumerate(row):
            if not isvalid(v):
                # print v, i
                scores[k] = i
                break
        else:
            scores[k] = ncols
        # print scores[k]
        # exit(0)

    return scores


def sort_by_score(seq, scores):
    return [p[1] for p in
            sorted(zip(scores, seq), key=lambda p: -p[0])]


def print_scored(metric, headers, scores, top=5):

    t0 = '%%-%ds' % max((len(h) for h in headers))
    print (t0 + ' %s') % ('', metric)

    t = t0 + ' %d'
    for h, sc in sorted(zip(headers, scores),
                        key=lambda p: (-p[1], p[0]))[:top]:
        print t % (h, sc)
    print

def _maybe_unlink(fn):
    try:
        if not fn: return
        fn = str(fn)
        if not op.exists(fn): return
        os.unlink(fn)
    except:
        import traceback as tb
        sep = '=' * 70
        print sep
        print 'while unlinking %s:' % fn
        tb.print_exc()
        print sep


class OutFH(file):
    def __init__(self, path, mode='w'):
        assert mode == 'w'
        super(OutFH, self).__init__(path, 'w')

    def open(cls, path):
        return cls(path)

    def __exit__(self, exc_type, exc_value, traceback):
        name = self.name
        in_exc = bool(exc_type)
        super(OutFH, self).__exit__(exc_type, exc_value, traceback)
        if in_exc:
            _maybe_unlink(name)


def print_table(table, rowheaders, colheaders, metric, outh=None):
    assert len(table) == len(rowheaders)
    ncols = len(colheaders)

    def _print_table(outh):
        print >> outh, '\t%s' % '\t'.join(colheaders)
        for rh, row in zip(rowheaders, table):
            print >> outh, '%s\t%s' % (rh, '\t'.join(row))

    if outh is None:
        outf = '%s.tsv' % metric
        # with open(outf, 'w') as outh:
        with OutFH(outf) as outh:
            _print_table(outh)
    else:
        _print_table(outh)


def main():

    allrows = tuple(csv.reader(open(DATASRC), delimiter=FIELDDELIMITER))
    allcols = zip(*allrows)

    colheaders = tuple(allrows[COLHEADERSROW][FIRSTDATACOL:])
    colsubheaders = tuple(allrows[COLSUBHEADERSROW][FIRSTDATACOL:])

    rowheaders = tuple(allcols[ROWHEADERSCOL][FIRSTDATAROW:])

    alldrugs = mu.unique(colheaders)
    drugs = tuple((dr for dr in alldrugs
                   if not dr.startswith('private_company_drug_')))

    drugset = set(drugs)

    metrics = 'lc50 tgi gi50'.split()
    assert set(colsubheaders) == set(metrics)

    nmetrics = len(metrics)

    assert len(colheaders) == len(alldrugs) * nmetrics

    cell_lines = rowheaders

    alldata = [list(col[FIRSTDATAROW:]) for col in allcols[FIRSTDATACOL:]]

    col_lookup = dict()
    for drug, subheader, data in zip(colheaders, colsubheaders, alldata):
        if drug not in drugset:
            continue
        d = col_lookup.setdefault(subheader, ncd.NoClobberDict())
        d[drug] = data

    nrows = len(allrows[FIRSTDATAROW:])
    assert nrows == len(cell_lines)

    maxvals = read_maxvals(MAXVALSFILE)

    for metric, drug in it.product(metrics, drugs):

        col = col_lookup[metric][drug]
        mv = maxvals[drug]
        for j, v in enumerate(col):
            assert isna(v) or float(v) <= float(mv)
            if v == mv:
                col[j] = MAXVALMARKER


    for metric, lkp in col_lookup.items():
        table0 = zip(*(lkp[dr] for dr in drugs))

        drug_scores = score_cols(table0)

        cols = zip(*table0)
        sorted_cols = sort_by_score(cols, drug_scores)

        table1 = zip(*sorted_cols)
        cell_line_scores = score_rows(table1)

        table2 = sort_by_score(table1, cell_line_scores)

        sorted_cell_lines = sort_by_score(cell_lines, cell_line_scores)
        sorted_drugs = sort_by_score(drugs, drug_scores)

        print_table(table2, sorted_cell_lines, sorted_drugs, metric)

main()
