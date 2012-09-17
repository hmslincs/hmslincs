#!/bin/bash
# note: if using virtualenv, set that up before running this script

check_errs()
{
  # Function. Parameter 1 is the return code
  # Para. 2 is text to display on failure.
  if [ "${1}" -ne "0" ]; then
    echo "ERROR: ${1} : ${2}"
    exit ${1}
  fi
}


dropdb -U django django 
check_errs $? "dropdb fails"

createdb -Udjango -T django_init django
check_errs $? "createdb fails"

django/manage.py syncdb
check_errs $? "syncdb fails"

echo 'import cell table ...'
python src/populate_cell.py sampledata/LINCS_Cells_20120727.xls 'HMS-LINCS cell line metadata'
check_errs $? "populate cell fails"

echo 'import small molecule...'
python src/populate_smallmolecule.py sampledata/HMS_LINCS-1.sdf
check_errs $? "import sdf fails"

echo 'import screen results...'
python src/import_screen_result.py -f sampledata/moerke_2color_IA-LM.xls 
check_errs $? "import screen result fails"
python src/import_screen_result.py -f sampledata/tang_MitoApop2_5637.xls
check_errs $? "import screen result fails"

python src/create_indexes.py | psql -Udjango django  -v ON_ERROR_STOP=1
check_errs $? "create indexes fails"
