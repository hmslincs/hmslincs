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
DIR=/groups/lincs/

if [[ $# -lt 1 ]]
then 
  echo "Usage: $0 <required: [test | local | dev | stage | prod] > [optional: local data dir] [optional: virtual env dir]"
  exit $WRONG_ARGS
fi

SERVER=$1
DATADIR=$2
VIRTUALENV=$3

if [[ "$SERVER" == "PROD" ]] || [[ "$SERVER" == "prod" ]] 
then
  DATADIR=${DATADIR:-${DIR}/data/prod}
  DB=lincs
  DB_USER=lincsweb
  LINCS_PGSQL_USER=lincsweb
  PGHOST=pgsql.orchestra
  export LINCS_PGSQL_USER=$DB_USER
  export LINCS_PGSQL_DB=$DB
  export LINCS_PGSQL_SERVER=$PGHOST
  export LINCS_PGSQL_PASSWORD=`cat ~/.pgpass |grep "\W$DB_USER\W" | awk -F ':' '{print $5}'`
  VIRTUALENV=/www/dev.lincs.hms.harvard.edu/support/virtualenv/bin/activate
  
  echo 'backing up db... '
  DATE=`date +%Y%m%d%H%M%S`
  set -x
  pg_dump -Fc --no-owner -U $DB_USER -h $PGHOST -f ${DIR}/data/db_dumps/${DB}.${DATE}.pre_build.pg_dump $DB
  check_errs $? "pg_dump fails"
  set +x
  echo 'backup done'
  
  
elif [[ "$SERVER" == "DEVTEST" ]] || [[ "$SERVER" == "devtest" ]] 
then
  DATADIR="${DATADIR:-sampledata}"
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
  DATADIR=${DATADIR:-${DIR}/data/dev}
  DB=devlincs
  DB_USER=devlincsweb
  PGHOST=dev.pgsql.orchestra
  export LINCS_PGSQL_USER=$DB_USER
  export LINCS_PGSQL_DB=$DB
  export LINCS_PGSQL_SERVER=$PGHOST
  export LINCS_PGSQL_PASSWORD=`cat ~/.pgpass |grep $DB_USER| awk -F ':' '{print $5}'`
  VIRTUALENV=/www/dev.lincs.hms.harvard.edu/support/virtualenv/bin/activate
elif [[ "$SERVER" == "DEV2" ]] || [[ "$SERVER" == "dev2" ]] 
then
  DATADIR=${DATADIR:-${DIR}/data/dev}
  DB=devoshernatprod
  DB_USER=devoshernatprodweb
  PGHOST=dev.pgsql.orchestra
  export LINCS_PGSQL_USER=$DB_USER
  export LINCS_PGSQL_DB=$DB
  export LINCS_PGSQL_SERVER=$PGHOST
  export LINCS_PGSQL_PASSWORD=`cat ~/.pgpass |grep $DB_USER| awk -F ':' '{print $5}'`
  VIRTUALENV=/www/dev.oshernatprod.hms.harvard.edu/support/virtualenv/bin/activate
elif [[ "$SERVER" == "DEV2TEST" ]] || [[ "$SERVER" == "dev2test" ]] 
then
  DATADIR="${DATADIR:-sampledata}"
  DB=devoshernatprod
  DB_USER=devoshernatprodweb
  PGHOST=dev.pgsql.orchestra
  export LINCS_PGSQL_USER=$DB_USER
  export LINCS_PGSQL_DB=$DB
  export LINCS_PGSQL_SERVER=$PGHOST
  export LINCS_PGSQL_PASSWORD=`cat ~/.pgpass |grep $DB_USER| awk -F ':' '{print $5}'`
  VIRTUALENV=/www/dev.oshernatprod.hms.harvard.edu/support/virtualenv/bin/activate
elif [[ "$SERVER" == "LOCAL" ]] || [[ "$SERVER" == "local" ]] 
then
  DATADIR=${DATADIR:-/home/sde4/sean/docs/work/LINCS/data/dev}
  DB=django
  DB_USER=django
  PGHOST=localhost
  VIRTUALENV=${3:-../hmslincs-env/bin/activate}
elif [[ "$SERVER" == "TEST" ]] || [[ "$SERVER" == "test" ]] 
then
  DATADIR="${DATADIR:-sampledata}"
  DB=django
  DB_USER=django
  PGHOST=localhost
  VIRTUALENV=${3:-../hmslincs-env/bin/activate}
else
  echo "Unknown option: \"$SERVER\""
  exit 1
fi


./generate_drop_all.sh $DB_USER $DB $PGHOST | psql -U$DB_USER  $DB -h $PGHOST 
check_errs $? "dropdb fails"

source $VIRTUALENV

django/manage.py syncdb 
check_errs $? "syncdb fails"

# ============ import the field definition information =========================

echo 'import dwg field definition tables ...'
python src/import_fieldinformation.py -f django/db/fieldinformation.csv
check_errs $? "import fieldinformation fails"

if [[ "$SERVER" == "TEST" ]] || [[ "$SERVER" == "test" ]] \
	|| [[ "$SERVER" == "DEVTEST" ]] || [[ "$SERVER" == "devtest" ]] \
	|| [[ "$SERVER" == "DEV2TEST" ]] || [[ "$SERVER" == "dev2test" ]]
then
  echo "===== perform the test import =====" 
  #============ Here is where the test data imports go =========================
  
  echo 'import cell tables ...'
  python src/import_cell.py -f sampledata/sample_cells.xlsx
  check_errs $? "import cell fails"
  
  echo 'import cell batch tables ...'
  python src/import_cell_batch.py -f sampledata/sample_cell_line_batch.xlsx
  check_errs $? "import cell fails"
  
  echo 'import small molecule tables...'
  python src/import_smallmolecule.py -f  sampledata/HMS-LINCS_complete.sdf
  check_errs $? "import sdf fails"

  echo 'import salt table...'
  python src/import_smallmolecule.py -f  sampledata/HMS-LINCS_salts.sdf
  check_errs $? "import sdf fails"

  echo 'import small molecule batch tables...'
  python src/import_smallmolecule_batch.py -f sampledata/small_molecule_batch-HMS_LINCS-1.xls
  check_errs $? "import smallmolecule batch fails"
  
  echo 'import small molecule batch qc reports...'
  python src/import_qc_events_batch.py -f sampledata/qc_events_batch.xlsx -fd $DATADIR
  check_errs $? "import_qc_events_batch fails"
  
  echo 'import library mapping tables...'
  python src/import_libraries.py -f sampledata/libraries.xls
  check_errs $? "import library fails"
	    
  echo 'import kinase tables...'
  python src/import_protein.py -f sampledata/HMS-LINCS_ProteinMetadata_forLoading.xls
  check_errs $? 'import kinases fails'
    
  echo 'import antibody tables...'
  python src/import_antibody.py -f sampledata/sample_antibodies.xlsx
  check_errs $? 'import antibodies fails'

  echo 'import antibody batches...'
  python src/import_antibody_batch.py -f sampledata/sample_antibody_batches.xlsx
  check_errs $? 'import antibody batches fails'

  echo 'import other reagent tables...'
  python src/import_other_reagent.py -f sampledata/HMS-LINCS_other_reagents.xls
  check_errs $? 'import other reagents fails'
  
  echo 'import test_dataset...'
  python src/import_dataset2.py -f sampledata/test_dataset.xls 
  check_errs $? "import dataset fails"
  
  echo 'import test_dataset2...'
  python src/import_dataset2.py -f sampledata/test_dataset2.xls 
  check_errs $? "import dataset 2 fails"
  
  echo 'import targets_test_dataset.xls...'
  python src/import_dataset2.py -f sampledata/Study20000_NominalTargets_forLoading.xls 
  check_errs $? "import dataset fails"
  
  echo 'import studies...'
  python ./src/import_dataset2.py -f sampledata/Screen20020_HMSL10008_kinomescan.xlsx
  check_errs $? "import study dataset fails"
  
  # remove the attached file example, not needed with the qc event entity handling this
  # echo 'import attached files...'
  # python ./src/import_attachedfiles.py -f sampledata/HPLC_HMSL10001.101.01.pdf -rp upload_files -fi 10001 -si 101 -bi 1 -ft 'QC-NMR' -fd 2012-10-11
  # check_errs $? "import attached file fails"

  # remove the attached file example, not needed with the qc event entity handling this
  # try attaching the same file to a cell batch, to test
  # python ./src/import_attachedfiles.py -f sampledata/sample_attached_file_for_cell.txt -rp upload_files -fi 50001 -bi 1 -ft 'QC-NMR' -fd 2012-10-11
  # check_errs $? "import attached file fails"

else
  
  #============ Here is where the "real" imports go ============================

  echo 'import cell tables ...'
  python src/import_cell.py -f $DATADIR/LINCS_Cells_forLoading.xls
  check_errs $? "import cell fails"
  
  echo 'import cell batch tables ...'
  python src/import_cell_batch.py -f $DATADIR/cell_line_batch.xlsx
  check_errs $? "import cell fails"
  
  echo 'import small molecule tables...'
  python src/import_smallmolecule.py -f $DATADIR/HMS-LINCS_complete.sdf
  check_errs $? "import sdf fails"

  echo 'import salt table...'
  python src/import_smallmolecule.py -f  $DATADIR/HMS-LINCS_salts.sdf
  check_errs $? "import sdf fails"

  echo 'import small molecule batch tables...'
  python src/import_smallmolecule_batch.py -f $DATADIR/small_molecule_batch-HMS_LINCS-1.xls
  check_errs $? "import smallmolecule batch fails"
  
  echo 'import small molecule batch qc reports...'
  python src/import_qc_events_batch.py -f $DATADIR/qc_events_batch.xlsx -fd $DATADIR
  check_errs $? "import_qc_events_batch fails"
  
  echo 'import library mapping tables...'
  python src/import_libraries.py -f $DATADIR/libraries.xls
  check_errs $? "import library fails"
  
  echo 'import kinase tables...'
  python src/import_protein.py -f $DATADIR/HMS-LINCS_ProteinMetadata_forLoading.xls
  check_errs $? 'import kinases fails'
  
  echo 'import other reagent tables...'
  python src/import_other_reagent.py -f $DATADIR/HMS-LINCS_other_reagents.xls
  check_errs $? 'import other reagents fails'
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Study20000_NominalTargets_forLoading.xls 
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20001_moerke_2color.xls 
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20002_moerke_3color.xls 
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20003_tang_MitoApop2.xls 
  check_errs $? "import dataset fails"

  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20004_tang_ProMitosis.xls 
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20020_HMSL10008_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20021_HMSL10017_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20022_HMSL10029_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20023_HMSL10046_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20024_HMSL10049_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20025_HMSL10050_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20026_HMSL10068_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20027_HMSL10006_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20028_HMSL10009_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20029_HMSL10010_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20030_HMSL10012_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20031_HMSL10013_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20032_HMSL10014_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20033_HMSL10027_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20034_HMSL10028_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20035_HMSL10034_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20036_HMSL10038_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20037_HMSL10055_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20038_HMSL10059_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20039_HMSL10060_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20040_HMSL10061_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20041_HMSL10065_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20042_HMSL10066_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20043_HMSL10067_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20044_HMSL10071_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20045_HMSL10078_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20046_HMSL10092_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20047_HMSL10096_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20048_HMSL10100_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20049_HMSL10002_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20050_HMSL10003_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20051_HMSL10015_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20052_HMSL10016_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20053_HMSL10018_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20054_HMSL10025_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20055_HMSL10026_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20056_HMSL10039_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20057_HMSL10041_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20058_HMSL10043_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20059_HMSL10045_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20060_HMSL10047_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20061_HMSL10070_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20062_HMSL10075_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20063_HMSL10076_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20064_HMSL10079_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20065_HMSL10080_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20066_HMSL10082_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20067_HMSL10083_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20068_HMSL10084_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20069_HMSL10085_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20070_HMSL10086_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20071_HMSL10087_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20072_HMSL10088_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20073_HMSL10089_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20074_HMSL10090_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20075_HMSL10091_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20076_HMSL10093_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20077_HMSL10094_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20078_HMSL10095_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20079_HMSL10064_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20080_HMSL10101_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20081_HMSL10208_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20082_HMSL10140_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20083_HMSL10035_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20084_HMSL10146_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20085_HMSL10172_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20086_HMSL10223_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinativ/Screen20087_HMSL10008_kinativ.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinativ/Screen20088_HMSL10029_kinativ.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinativ/Screen20089_HMSL10046_kinativ.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinativ/Screen20090_HMSL10049_kinativ.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinativ/Screen20091_HMSL10050_kinativ.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinativ/Screen20092_HMSL10068_kinativ.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinativ/Screen20093_HMSL10017_kinativ.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinativ/Screen20094_HMSL10079_kinativ.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinativ/Screen20095_HMSL10080_kinativ.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20096_HMSL10232_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinativ/Screen20097_HMSL10086_kinativ.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinativ/Screen20098_HMSL10087_kinativ.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinativ/Screen20099_HMSL10091_kinativ.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinativ/Screen20100_HMSL10092_kinativ.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinativ/Screen20101_HMSL10093_kinativ.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinativ/Screen20102_HMSL10094_kinativ.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinativ/Screen20103_HMSL10106_kinativ.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinativ/Screen20104_HMSL10200_kinativ.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinativ/Screen20105_HMSL10201_kinativ.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinativ/Screen20106_HMSL10070_kinativ.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20107_HMSL10051_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20108_HMSL10019_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20109_HMSL10024_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20110_HMSL10040_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20111_HMSL10162_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20112_HMSL10209_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20113_HMSL10213_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20114_HMSL10058_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20115_HMSL10106_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20116_HMSL10189_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20117_HMSL10229_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20118_HMSL10102_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20119_HMSL10214_kinomescan.xls
  check_errs $? "import dataset fails"
  
  # removed, per CES request, 2013-06-07 - sde
  # reinstated since paper published, 2013-09-09 - djw
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20120_Fallahi-Sichani.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20121_Yale_A549.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20122_Yale_U87.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20123_Yale_U937.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20124_HMSL10001_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20125_HMSL10073_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20126_HMSL10285_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20127_HMSL10286_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20128_HMSL10287_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20129_HMSL10289_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20130_HMSL10337_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20131_HMSL10284_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20132_HMSL10340_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20133_HMSL10341_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20134_HMSL10342_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20135_HMSL10158_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20136_Fallahi-Sichani_images.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20137_Niepel-Hafner.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20138_Niepel-Hafner.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20139_Niepel-Hafner.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20140_Niepel-Hafner.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20146_HMSL10028_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20147_HMSL10037_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20148_HMSL10040_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20149_HMSL10041_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20150_HMSL10042_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20151_HMSL10044_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20152_HMSL10047_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20153_HMSL10048_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20154_HMSL10049_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20155_HMSL10051_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20156_HMSL10056_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20157_HMSL10066_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20158_HMSL10067_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20159_HMSL10069_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20160_HMSL10097_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20161_HMSL10098_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20162_HMSL10099_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20163_HMSL10114_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20164_HMSL10120_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20165_HMSL10123_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20166_HMSL10125_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20167_HMSL10126_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20168_HMSL10127_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20169_HMSL10128_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20170_HMSL10130_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20171_HMSL10132_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20172_HMSL10133_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20173_HMSL10138_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20174_HMSL10141_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20175_HMSL10151_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20176_HMSL10157_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20177_HMSL10167_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20178_HMSL10168_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20179_HMSL10175_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20180_HMSL10177_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20181_HMSL10181_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20182_HMSL10182_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20183_HMSL10187_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20184_HMSL10189_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20185_HMSL10192_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20186_HMSL10198_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20187_HMSL10220_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20188_HMSL10226_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20189_HMSL10230_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20190_HMSL10255_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20191_HMSL10004_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20192_HMSL10008_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20193_HMSL10011_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20194_HMSL10013_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20195_HMSL10018_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20196_HMSL10020_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20197_HMSL10021_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20198_HMSL10023_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20199_HMSL10024_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20200_HMSL10027_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20201_HMSL10206_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20202_HMSL10104_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20203_HMSL10355_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinativ/Screen20204_HMSL10075_kinativ.xls
  check_errs $? "import dataset fails"
  
  # echo 'import screen results...'
  # python src/import_dataset2.py -f $DATADIR/kinativ/Screen20205_HMSL10077_kinativ.xls
  # check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinativ/Screen20206_HMSL10129_kinativ.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinativ/Screen20207_HMSL10188_kinativ.xls
  check_errs $? "import dataset fails"
  
  # echo 'import screen results...'
  # python src/import_dataset2.py -f $DATADIR/kinativ/Screen20208_HMSL10229_kinativ.xls
  # check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinativ/Screen20209_HMSL10337_kinativ.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinativ/Screen20210_HMSL10351_kinativ.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20211_HMSL10356_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20215_TransCenter_SensitivityMeasures.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20216_TransCenter_DoseResponse.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20217_ViabilityApoptosis.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20218_RPPA.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20219_PhosphoStateProteinLevels.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20220_HMSL10053_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20221_HMSL10105_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20222_HMSL10129_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20223_HMSL10171_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20224_HMSL10183_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20225_HMSL10212_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20227_HMSL10354_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20228_HMSL10364_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20229_PLSR_wpMEK-ERK.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20230_PLSR_wopMEK-ERK.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20231_VIP.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20232_Roux.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20233_Jones_SF1.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20234_Jones_SF3-1.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20235_Jones_SF3-2.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20237_LJP_processedData1.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20238_LJP_processedData2.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20239_LJP_processedData3.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20240_LJP_meanData1.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20241_LJP_meanData2.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20242_LJP_meanData3.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20243_LJP_aggregatedData.xls
  check_errs $? "import dataset fails"
  
  # 2015-04-20: removed all attached compound QC files since original reports from vendors will no longer be used and future reports will be attached in the QC Testing Events section of each batch
  
# if restricted:
#  python src/import_attachedfiles.py -f attach_test_1.txt -fi 10001 -ft "text"  -fd '2012-12-10' -si 101 -bi 1 --restricted
  
fi

# the PGUSER=$DB_USER prefix ensures that the script will run even when (Unix)
# USER running the script does not have access $DB on $PGHOST
PGUSER=$DB_USER python src/create_indexes.py | psql -U$DB_USER  $DB -h $PGHOST -v ON_ERROR_STOP=1
#check_errs $? "create indexes fails"

if [[ "$SERVER" == "PROD" ]] || [[ "$SERVER" == "prod" ]] 
then
  echo 'backing up db... '
  DATE=`date +%Y%m%d%H%M%S`
  set -x
  pg_dump -Fc --no-owner -U $DB_USER -h $PGHOST -f ${DIR}/data/db_dumps/${DB}.${DATE}.post_build.pg_dump $DB
  check_errs $? "pg_dump fails"
  set +x
  echo 'backup done'
fi
