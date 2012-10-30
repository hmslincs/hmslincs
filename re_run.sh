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

DATADIR=
VIRTUALENV=
DIR=/groups/pharmacoresponse/

if [[ $# -lt 1 ]]
then 
  echo "Usage: $0 <required: [test | local | dev | stage | prod] > [optional: local data dir] [optional: virtual env dir]"
  exit $WRONG_ARGS
fi

SERVER=$1

if [[ "$SERVER" == "PROD" ]] || [[ "$SERVER" == "prod" ]] 
then
  DATADIR=${DIR}/data/prod
  DB=lincs
  DB_USER=lincsweb
  LINCS_PGSQL_USER=lincsweb
  PGHOST=pgsql.orchestra
  export LINCS_PGSQL_USER=$DB_USER
  export LINCS_PGSQL_DB=$DB
  export LINCS_PGSQL_SERVER=$PGHOST
  export LINCS_PGSQL_PASSWORD=`cat ~/.pgpass |grep $DB_USER| awk -F ':' '{print $5}'`
  VIRTUALENV=/www/dev.lincs.hms.harvard.edu/support/virtualenv/bin/activate
elif [[ "$SERVER" == "DEVTEST" ]] || [[ "$SERVER" == "devtest" ]] 
then
  # not needed for test data DATADIR=${DIR}/data/dev2
  DB=devlincs
  DB_USER=devlincsweb
  PGHOST=dev.pgsql.orchestra
  export LINCS_PGSQL_USER=$DB_USER
  export LINCS_PGSQL_DB=$DB
  export LINCS_PGSQL_SERVER=$PGHOST
  export LINCS_PGSQL_PASSWORD=`cat ~/.pgpass |grep $DB_USER| awk -F ':' '{print $5}'`
  VIRTUALENV=/www/dev.lincs.hms.harvard.edu/support/virtualenv/bin/activate
elif [[ "$SERVER" == "DEV" ]] || [[ "$SERVER" == "dev" ]] 
then
  DATADIR=${DIR}/data/dev2
  DB=devlincs
  DB_USER=devlincsweb
  PGHOST=dev.pgsql.orchestra
  export LINCS_PGSQL_USER=$DB_USER
  export LINCS_PGSQL_DB=$DB
  export LINCS_PGSQL_SERVER=$PGHOST
  export LINCS_PGSQL_PASSWORD=`cat ~/.pgpass |grep $DB_USER| awk -F ':' '{print $5}'`
  VIRTUALENV=/www/dev.lincs.hms.harvard.edu/support/virtualenv/bin/activate
elif [[ "$SERVER" == "LOCAL" ]] || [[ "$SERVER" == "local" ]] 
then
  DATADIR=${2:-/home/sde4/sean/docs/work/LINCS/data/dev2}
  DB=django
  DB_USER=django
  PGHOST=localhost
  VIRTUALENV=${3:-/home/sde4/workspace/hmslincs/myvirtualenv/bin/activate}
elif [[ "$SERVER" == "TEST" ]] || [[ "$SERVER" == "test" ]] 
then
  # NOT NEEDED FOR TEST DATA : DATADIR=${2:-/home/sde4/workspace/hmslincs/}
  DB=django
  DB_USER=django
  PGHOST=localhost
  VIRTUALENV=${3:-/home/sde4/workspace/hmslincs/myvirtualenv/bin/activate}
else
  echo "Unknown option: \"$SERVER\""
  exit 1
fi


#/home/sde4/sql/drop-all.pl devlincs
./generate_drop_all.sh $DB_USER $DB $PGHOST | psql -U$DB_USER  $DB -h $PGHOST 
check_errs $? "dropdb fails"

source $VIRTUALENV

django/manage.py syncdb
check_errs $? "syncdb fails"

# ============ import the field definition information =========================

echo 'import dwg field definition tables ...'
python src/import_fieldinformation.py -f sampledata/fieldinformation.xlsx
check_errs $? "import fieldinformation fails"

if [[ "$SERVER" == "TEST" ]] || [[ "$SERVER" == "test" ]] || [[ "$SERVER" == "DEVTEST" ]] || [[ "$SERVER" == "devtest" ]] 
then
 
  #============ Here is where the test data imports go =========================
  
	echo 'import cell tables ...'
	python src/import_cell.py -f sampledata/LINCS_Cells_forLoading.xls
	check_errs $? "import cell fails"
	
	echo 'import small molecule tables...'
	python src/import_smallmolecule.py -f  sampledata/HMS-LINCS_complete.sdf
	check_errs $? "import sdf fails"

	echo 'import small molecule batch tables...'
	python src/import_smallmolecule_batch.py -f sampledata/small_molecule_batch-HMS_LINCS-1.xls
	check_errs $? "import smallmolecule batch fails"
	
	echo 'import library mapping tables...'
	python src/import_libraries.py -f sampledata/libraries.xls
	check_errs $? "import library fails"
	
	echo 'import kinase tables...'
	python src/import_protein.py -f sampledata/HMS-LINCS_KinaseMetadata_forLoading.xls
	check_errs $? 'import kinases fails'
	
	echo 'import screen results...'
	python src/import_dataset.py -f sampledata/test_dataset.xls 
	check_errs $? "import dataset fails"
	
	echo 'import studies...'
	python ./src/import_dataset.py -f sampledata/Study300002_HMSL10008_sorafenib_ambit.xls
	check_errs $? "import study dataset fails"
	
	echo 'import attached files...'
	python ./src/import_attachedfiles.py -f /home/sde4/docs/work/LINCS/data/dev/qc/LCMS_HMSL10014.101.01.pdf -rp upload_files -fi 10014 -si 101 -bi 1 -ft 'QC-NMR' -fd 2012-10-11
	check_errs $? "import attached file fails"

else
	
	#============ Here is where the "real" imports go ============================

	echo 'import cell tables ...'
	python src/import_cell.py -f $DATADIR/LINCS_Cells_forLoading.xls
	check_errs $? "import cell fails"
	
	echo 'import small molecule tables...'
	python src/import_smallmolecule.py -f $DATADIR/HMS-LINCS_complete.sdf
	check_errs $? "import sdf fails"

	echo 'import small molecule batch tables...'
	python src/import_smallmolecule_batch.py -f $DATADIR/small_molecule_batch-HMS_LINCS-1.xls
	check_errs $? "import smallmolecule batch fails"
	
	echo 'import library mapping tables...'
	python src/import_libraries.py -f $DATADIR/libraries.xls
	check_errs $? "import library fails"
	
	echo 'import kinase tables...'
	python src/import_protein.py -f $DATADIR/HMS-LINCS_KinaseMetadata_forLoading.xls
	check_errs $? 'import kinases fails'

fi

python src/create_indexes.py | psql -U$DB_USER  $DB -h $PGHOST  -v ON_ERROR_STOP=1
#check_errs $? "create indexes fails"
