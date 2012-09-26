#!/bin/bash

check_errs()
{
  # Function. Parameter 1 is the return code
  # Para. 2 is text to display on failure.
  if [ "${1}" -ne "0" ]; then
    echo "ERROR: ${1} : ${2}"
    exit ${1}
  fi
}


#/home/sde4/sql/drop-all.pl devlincs
./generate_drop_all.sh devlincsweb devlincs dev.pgsql.orchestra | psql -Udevlincsweb devlincs -h dev.pgsql.orchestra 
check_errs $? "dropdb fails"

source /www/dev.lincs.hms.harvard.edu/support/virtualenv/bin/activate

django/manage.py syncdb
check_errs $? "syncdb fails"

echo 'import cell table ...'
python src/populate_cell.py sampledata/LINCS_Cells_20120727.xls 'HMS-LINCS cell line metadata'
check_errs $? "populate cell fails"

echo 'import small molecule...'
python src/populate_smallmolecule.py sampledata/HMS_LINCS-1.sdf
check_errs $? "import sdf fails"

echo 'import screen results...'
python src/import_dataset.py -f sampledata/moerke_2color_IA-LM.xls 
check_errs $? "import dataset fails"
python src/import_dataset.py -f sampledata/tang_MitoApop2_5637.xls
check_errs $? "import dataset result fails"

python src/import_libraries.py -f sampledata/libraries.xls
check_errs $? "import library fails"

python src/create_indexes.py | psql -U devlincsweb devlincs -h dev.pgsql.orchestra -v ON_ERROR_STOP=1
#check_errs $? "create indexes fails"
