#!/bin/bash
# note: if using virtualenv, set that up before running this script

dropdb -U django django

createdb -Udjango -T django_init django

django/manage.py syncdb

#python src/import_cells.py sampledata/LINCS_Cells_20120727.xls 'HMS-LINCS cell line metadata' Cell 1
python src/populate_cell.py sampledata/LINCS_Cells_20120727.xls 'HMS-LINCS cell line metadata'

#python src/import_sdf.py sampledata/HMS_LINCS-1.sdf 
python src/populate_smallmolecule.py sampledata/HMS_LINCS-1.sdf

python src/import_screen_result.py -f sampledata/moerke_2color_IA-LM.xls 
python src/import_screen_result.py -f sampledata/tang_MitoApop2_5637.xls

psql -Udjango -f django/example/create_indexes.sql 
