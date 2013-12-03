import sys
import os
import os.path as op
import codecs
import errno
import shutil
import stat
import argparse
import pandas as pd
import openpyxl
import django.conf
from django.template.loader import render_to_string
import shell_utils as su


# Read RESOURCE_PATH from environ, or default to something that works for me.
RESOURCE_PATH = os.environ.get(
    'RESOURCE_PATH',
    '/home/jmuhlich/Volumes/sysbio on research.files.med.harvard.edu/'
    'SORGER PROJECTS/Publications/2013/Submissions/'
    'SampattavanichAndKramer_et_al-FOXO3a/websites'
    )

PLATEMAP_FILENAME = op.join(RESOURCE_PATH, 'Platemap.xlsx')
CELL_IMAGE_PATH = op.join(RESOURCE_PATH,
                          'PNG_individual_timeSeries_short_noTickLabel')
CELL_IMAGE_PREFIX = 'Individual_nolabel_'
POPUP_IMAGE_PATH = op.join(RESOURCE_PATH, 'PNG_individual_wellAveraged')

LIGAND_RENAMES = {
    'None': '',
    'IGF': 'IGF1',
    }

INHIBITOR_RENAMES = {
    'None': '',
    }

FLOAT_COLUMNS = ['ligand_conc', 'inhibitor_conc']

LIGAND_ORDER = ['IGF1', 'HRG', 'HGF', 'EGF', 'FGF', 'BTC', 'EPR']
INHIBITOR_ORDER = ['MEKi', 'AKTi', 'MEKi + AKTi']

CONCENTRATION_COLOR_BEGIN = 0xF8
CONCENTRATION_COLOR_END = 0xD0


def main(argv):

    argparser = argparse.ArgumentParser(
        description='Build sampattavanich_2014 app resources.')
    argparser.add_argument('-n', '--no-media', action='store_true',
                           default=False,
                           help="Don't copy media files)")
    args = argparser.parse_args()

    cur_dir = op.abspath(op.dirname(__file__))
    html_dir = op.abspath(op.join(
        cur_dir, '..', 'temp', 'docroot', 'explore', 'sampattavanich-2014'))
    html_filename = op.join(html_dir, 'index.html')
    cell_img_out_dir = op.join(html_dir, 'img', 'cell')
    popup_img_out_dir = op.join(html_dir, 'img', 'popup')

    platemap = build_platemap(PLATEMAP_FILENAME)
    ligand_concs = [c for c in sorted(platemap.ligand_conc.unique()) if c > 0]

    table = []
    for row, ligand_conc in enumerate(ligand_concs):
        intensity = (CONCENTRATION_COLOR_BEGIN +
                     (CONCENTRATION_COLOR_END - CONCENTRATION_COLOR_BEGIN) /
                     len(ligand_concs) * row)
        color = '#' + ('%02x' % intensity * 3)
        table_row = {'ligand_conc': ligand_conc,
                     'color': color,
                     'cells': []}
        for col, ligand in enumerate(LIGAND_ORDER):
            location = ((platemap.ligand_conc == ligand_conc) &
                        (platemap.ligand == ligand) &
                        (platemap.inhibitor == ''))
            table_row['cells'].append(platemap[location].iloc[0])
        table.append(table_row)
    # FIXME We should really just build a pivoted dataframe in the right way so
    # that we can just iterate over it cleanly. This duplication is not good.
    table_inhibitors = []
    for row, inhibitor in enumerate(INHIBITOR_ORDER):
        color = '#' + ('%02x' % CONCENTRATION_COLOR_END * 3)
        table_row = {'ligand_conc': ligand_concs[-1],
                     'color': color,
                     'inhibitors': inhibitor.split(' + '),
                     'cells': []}
        for col, ligand in enumerate(LIGAND_ORDER):
            location = ((platemap.inhibitor == inhibitor) &
                        (platemap.ligand == ligand))
            table_row['cells'].append(platemap[location].iloc[0])
        table_inhibitors.append(table_row)
            
    data = {'ligands': LIGAND_ORDER,
            'table': table,
            'table_inhibitors': table_inhibitors,
            'num_ligand_concs': len(ligand_concs),
            'num_inhibitors': len(INHIBITOR_ORDER),
            'STATIC_URL': django.conf.settings.STATIC_URL,
            }
    content = render_to_string('sampattavanich_2014/index.html', data)
    with codecs.open(html_filename, 'w', 'utf-8') as out_file:
        out_file.write(content)

    if not args.no_media:
        su.mkdirp(cell_img_out_dir)
        for src_filename in os.listdir(CELL_IMAGE_PATH):
            if not src_filename.endswith('.png'):
                continue
            src_path = op.join(CELL_IMAGE_PATH, src_filename)
            dest_filename = src_filename.partition(CELL_IMAGE_PREFIX)[2]
            dest_path = op.join(cell_img_out_dir, dest_filename)
            shutil.copy(src_path, dest_path)
            os.chmod(dest_path, 0644)
        su.mkdirp(popup_img_out_dir)
        for src_filename in os.listdir(POPUP_IMAGE_PATH):
            if not src_filename.endswith('.png'):
                continue
            src_path = op.join(POPUP_IMAGE_PATH, src_filename)
            dest_filename = src_filename
            dest_path = op.join(popup_img_out_dir, dest_filename)
            shutil.copy(src_path, dest_path)
            os.chmod(dest_path, 0644)

    return 0


"""Build plate-map dataframe."""
def build_platemap(filename):

    wb = openpyxl.load_workbook(filename)
    ws = wb.worksheets[0]

    # Extract row metadata.
    row_meta = dataframe_for_range(ws, 'D9:D16')
    row_meta.columns = pd.Index(['ligand'])
    row_meta['ligand'].replace(LIGAND_RENAMES, inplace=True)
    row_meta.insert(0, 'plate_row', range(1, len(row_meta)+1))

    # Extract column metadata.
    col_meta = dataframe_for_range(ws, 'G4:R6').T
    col_meta.columns = pd.Index(['ligand_conc', 'inhibitor',
                                 'inhibitor_conc'])
    col_meta['inhibitor'].replace(INHIBITOR_RENAMES, inplace=True)
    for name in FLOAT_COLUMNS:
        col_meta[name] = col_meta[name].astype(float)
    col_meta.insert(0, 'plate_col', range(1, len(col_meta)+1))

    # Add same-valued dummy columns so merge() will generate a full cartesian
    # product, then delete that column in the resulting dataframe.
    row_meta.insert(0, 'dummy', [0] * len(row_meta))
    col_meta.insert(0, 'dummy', [0] * len(col_meta))
    platemap = pd.merge(row_meta, col_meta, on='dummy')
    del platemap['dummy']

    # Swap the columns around a bit to move the row and column numbers up front.
    new_column_order = platemap.columns[[0,2,1]].append(platemap.columns[3:])
    platemap = platemap[new_column_order]

    # Get rid of extreme left/right/bottom cells -- not part of the experiment.
    platemap = platemap[(platemap.plate_col >= 2) &
                        (platemap.plate_col <= 11) &
                        (platemap.plate_row <= 7)]

    # Replace plate_row and plate_col with a new column in r1c1 format.
    rc_values = platemap.apply(lambda r: 'r%(plate_row)dc%(plate_col)d' % r,
                               axis=1)
    platemap = platemap.drop(['plate_row', 'plate_col'], axis=1)
    platemap.insert(0, 'rc_address', rc_values)

    return platemap


"""Return a Pandas DataFrame from a given range in an openpyxl worksheet."""
def dataframe_for_range(worksheet, range):
    data = [[c.value for c in row] for row in worksheet.range(range)]
    return pd.DataFrame(data)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
