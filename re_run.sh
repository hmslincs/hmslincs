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
  # not needed for test data DATADIR=${DIR}/data/dev
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
  DATADIR=${DIR}/data/dev
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
  DATADIR=${DIR}/data/dev
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
  DATADIR=${2:-/home/sde4/sean/docs/work/LINCS/data/dev}
  DB=django
  DB_USER=django
  PGHOST=localhost
  VIRTUALENV=${3:-../hmslincs-env/bin/activate}
elif [[ "$SERVER" == "TEST" ]] || [[ "$SERVER" == "test" ]] 
then
  # NOT NEEDED FOR TEST DATA : DATADIR=${2:-/home/sde4/workspace/hmslincs/}
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
python src/import_fieldinformation.py -f sampledata/fieldinformation.xlsx
check_errs $? "import fieldinformation fails"

if [[ "$SERVER" == "TEST" ]] || [[ "$SERVER" == "test" ]] || [[ "$SERVER" == "DEVTEST" ]] || [[ "$SERVER" == "devtest" ]] 
then
 
  #============ Here is where the test data imports go =========================
  
  echo 'import cell tables ...'
  python src/import_cell.py -f sampledata/LINCS_Cells_forLoading.xls
  check_errs $? "import cell fails"
  
  echo 'import cell batch tables ...'
  python src/import_cell_batch.py -f sampledata/cell_line_batch.xlsx
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
	
	echo 'import library mapping tables...'
	python src/import_libraries.py -f sampledata/libraries.xls
	check_errs $? "import library fails"
    
    echo 'import kinase tables...'
    python src/import_protein.py -f sampledata/HMS-LINCS_ProteinMetadata_forLoading.xls
    check_errs $? 'import kinases fails'
    
    echo 'import antibody tables...'
    python src/import_antibody.py -f sampledata/HMS-LINCS_antibodies.xls
    check_errs $? 'import antibodies fails'
    
    echo 'import other reagent tables...'
    python src/import_other_reagent.py -f sampledata/HMS-LINCS_other_reagents.xls
    check_errs $? 'import other reagents fails'
	
	echo 'import test_dataset...'
	python src/import_dataset.py -f sampledata/test_dataset.xls 
	check_errs $? "import dataset fails"
	
	echo 'import targets_test_dataset.xls...'
	python src/import_dataset.py -f sampledata/targets_test_dataset.xls 
	check_errs $? "import dataset fails"
	
	echo 'import studies...'
	python ./src/import_dataset.py -f sampledata/Screen20020_HMSL10008_kinomescan.xlsx
	check_errs $? "import study dataset fails"
	
	echo 'import attached files...'
  python ./src/import_attachedfiles.py -f sampledata/HPLC_HMSL10001.101.01.pdf -rp upload_files -fi 10001 -si 101 -bi 1 -ft 'QC-NMR' -fd 2012-10-11
  check_errs $? "import attached file fails"

  # try attaching the same file to a cell batch, to test
  python ./src/import_attachedfiles.py -f sampledata/sample_attached_file_for_cell.txt -rp upload_files -fi 50001 -bi 1 -ft 'QC-NMR' -fd 2012-10-11
  check_errs $? "import attached file fails"

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
	python src/import_dataset.py -f $DATADIR/Study20000_NominalTargets_forLoading.xls 
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/Screen20001_moerke_2color.xls 
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/Screen20002_moerke_3color.xls 
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/Screen20003_tang_MitoApop2.xls 
	check_errs $? "import dataset fails"

	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/Screen20004_tang_ProMitosis.xls 
	check_errs $? "import dataset fails"
	
	#echo 'import screen results...'
	#python src/import_dataset.py -f $DATADIR/Screen20005_tang_MitoApop2.xls 
	#check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/Screen20006_CMT_GrowthInhibition-3dose.xls 
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/Screen20007_CMT_GrowthInhibition-3dose.xls 
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/Screen20008_CMT_9dose-1.xls 
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/Screen20009_CMT_9dose-2.xls 
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/Screen20010_CMT_9dose-3.xls 
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/Screen20011_CMT_9dose-4.xls 
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/Screen20012_CMT_9dose-5.xls 
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/Screen20013_CMT_9dose-6.xls 
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/Screen20014_CMT_9dose-7.xls 
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/Screen20015_CMT_9dose-8.xls 
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/Screen20016_CMT_9dose-9.xls 
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/Screen20017_CMT_9dose-10.xls 
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20020_HMSL10008_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20021_HMSL10017_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20022_HMSL10029_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20023_HMSL10046_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20024_HMSL10049_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20025_HMSL10050_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20026_HMSL10068_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20027_HMSL10006_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20028_HMSL10009_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20029_HMSL10010_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20030_HMSL10012_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20031_HMSL10013_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20032_HMSL10014_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20033_HMSL10027_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20034_HMSL10028_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20035_HMSL10034_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20036_HMSL10038_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20037_HMSL10055_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20038_HMSL10059_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20039_HMSL10060_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20040_HMSL10061_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20041_HMSL10065_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20042_HMSL10066_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20043_HMSL10067_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20044_HMSL10071_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20045_HMSL10078_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20046_HMSL10092_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20047_HMSL10096_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20048_HMSL10100_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20049_HMSL10002_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20050_HMSL10003_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20051_HMSL10015_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20052_HMSL10016_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20053_HMSL10018_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20054_HMSL10025_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20055_HMSL10026_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20056_HMSL10039_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20057_HMSL10041_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20058_HMSL10043_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20059_HMSL10045_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20060_HMSL10047_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20061_HMSL10070_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20062_HMSL10075_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20063_HMSL10076_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20064_HMSL10079_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20065_HMSL10080_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20066_HMSL10082_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20067_HMSL10083_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20068_HMSL10084_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20069_HMSL10085_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20070_HMSL10086_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20071_HMSL10087_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20072_HMSL10088_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20073_HMSL10089_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20074_HMSL10090_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20075_HMSL10091_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20076_HMSL10093_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20077_HMSL10094_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20078_HMSL10095_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20079_HMSL10064_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20080_HMSL10101_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20081_HMSL10208_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20082_HMSL10140_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20083_HMSL10035_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20084_HMSL10146_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20085_HMSL10172_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20086_HMSL10223_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinativ/Screen20087_HMSL10008_kinativ.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinativ/Screen20088_HMSL10029_kinativ.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinativ/Screen20089_HMSL10046_kinativ.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinativ/Screen20090_HMSL10049_kinativ.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinativ/Screen20091_HMSL10050_kinativ.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinativ/Screen20092_HMSL10068_kinativ.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinativ/Screen20093_HMSL10017_kinativ.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinativ/Screen20094_HMSL10079_kinativ.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinativ/Screen20095_HMSL10080_kinativ.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20096_HMSL10232_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinativ/Screen20097_HMSL10086_kinativ.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinativ/Screen20098_HMSL10087_kinativ.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinativ/Screen20099_HMSL10091_kinativ.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinativ/Screen20100_HMSL10092_kinativ.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinativ/Screen20101_HMSL10093_kinativ.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinativ/Screen20102_HMSL10094_kinativ.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinativ/Screen20103_HMSL10106_kinativ.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinativ/Screen20104_HMSL10200_kinativ.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinativ/Screen20105_HMSL10201_kinativ.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinativ/Screen20106_HMSL10070_kinativ.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20107_HMSL10051_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20108_HMSL10019_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20109_HMSL10024_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20110_HMSL10040_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20111_HMSL10162_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20112_HMSL10209_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20113_HMSL10213_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20114_HMSL10058_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20115_HMSL10106_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20116_HMSL10189_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20117_HMSL10229_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20118_HMSL10102_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20119_HMSL10214_kinomescan.xls
	check_errs $? "import dataset fails"
	
	# removed, per CES request, 2013-06-07 - sde
	# reinstated since paper published, 2013-09-09 - djw
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/Screen20120_Fallahi-Sichani.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/Screen20121_Yale_A549.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/Screen20122_Yale_U87.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/Screen20123_Yale_U937.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20124_HMSL10001_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20125_HMSL10073_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20126_HMSL10285_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20127_HMSL10286_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20128_HMSL10287_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20129_HMSL10289_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20130_HMSL10337_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20131_HMSL10284_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20132_HMSL10340_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20133_HMSL10341_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20134_HMSL10342_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20135_HMSL10158_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/Screen20136_Fallahi-Sichani_images.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/Screen20137_Niepel-Hafner.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/Screen20138_Niepel-Hafner.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/Screen20139_Niepel-Hafner.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/Screen20140_Niepel-Hafner.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20146_HMSL10028_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20147_HMSL10037_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20148_HMSL10040_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20149_HMSL10041_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20150_HMSL10042_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20151_HMSL10044_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20152_HMSL10047_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20153_HMSL10048_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20154_HMSL10049_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20155_HMSL10051_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20156_HMSL10056_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20157_HMSL10066_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20158_HMSL10067_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20159_HMSL10069_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20160_HMSL10097_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20161_HMSL10098_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20162_HMSL10099_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20163_HMSL10114_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20164_HMSL10120_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20165_HMSL10123_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20166_HMSL10125_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20167_HMSL10126_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20168_HMSL10127_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20169_HMSL10128_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20170_HMSL10130_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20171_HMSL10132_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20172_HMSL10133_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20173_HMSL10138_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20174_HMSL10141_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20175_HMSL10151_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20176_HMSL10157_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20177_HMSL10167_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20178_HMSL10168_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20179_HMSL10175_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20180_HMSL10177_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20181_HMSL10181_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20182_HMSL10182_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20183_HMSL10187_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20184_HMSL10189_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20185_HMSL10192_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20186_HMSL10198_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20187_HMSL10220_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20188_HMSL10226_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20189_HMSL10230_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20190_HMSL10255_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20191_HMSL10004_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20192_HMSL10008_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20193_HMSL10011_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20194_HMSL10013_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20195_HMSL10018_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20196_HMSL10020_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20197_HMSL10021_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20198_HMSL10023_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20199_HMSL10024_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20200_HMSL10027_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20201_HMSL10206_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20202_HMSL10104_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20203_HMSL10355_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinativ/Screen20204_HMSL10075_kinativ.xls
	check_errs $? "import dataset fails"
	
	# echo 'import screen results...'
	# python src/import_dataset.py -f $DATADIR/kinativ/Screen20205_HMSL10077_kinativ.xls
	# check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinativ/Screen20206_HMSL10129_kinativ.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinativ/Screen20207_HMSL10188_kinativ.xls
	check_errs $? "import dataset fails"
	
	# echo 'import screen results...'
	# python src/import_dataset.py -f $DATADIR/kinativ/Screen20208_HMSL10229_kinativ.xls
	# check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinativ/Screen20209_HMSL10337_kinativ.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinativ/Screen20210_HMSL10351_kinativ.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20211_HMSL10356_kinomescan.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/Screen20215_TransCenter_SensitivityMeasures.xls
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/Screen20216_TransCenter_DoseResponse.xls
	check_errs $? "import dataset fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10001.101.01.pdf -fi 10001 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10001.101.01.pdf -fi 10001 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10004.101.01.pdf -fi 10004 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10004.101.01.pdf -fi 10004 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10005.101.01.pdf -fi 10005 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10005.101.01.pdf -fi 10005 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10006.101.01.pdf -fi 10006 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10006.101.01.pdf -fi 10006 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10010.101.01.pdf -fi 10010 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10010.101.01.pdf -fi 10010 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10011.101.01.pdf -fi 10011 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10011.101.01.pdf -fi 10011 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10012.101.01.pdf -fi 10012 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10012.101.01.pdf -fi 10012 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10013.101.01.pdf -fi 10013 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10013.101.01.pdf -fi 10013 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10014.101.01.pdf -fi 10014 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10014.101.01.pdf -fi 10014 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10015.101.01.pdf -fi 10015 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10015.101.01.pdf -fi 10015 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10016.101.01.pdf -fi 10016 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10016.101.01.pdf -fi 10016 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10018.101.01.pdf -fi 10018 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10018.101.01.pdf -fi 10018 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10020.101.01.pdf -fi 10020 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10020.101.01.pdf -fi 10020 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10021.101.01.pdf -fi 10021 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10021.101.01.pdf -fi 10021 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10023.103.01.pdf -fi 10023 -fd '2013-04-04' -si 103 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10023.103.01.pdf -fi 10023 -fd '2013-04-04' -si 103 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10024.101.01.pdf -fi 10024 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10024.101.01.pdf -fi 10024 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10024.101.01.pdf -fi 10024 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10029.101.01.pdf -fi 10029 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10029.101.01.pdf -fi 10029 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10032.101.01.pdf -fi 10032 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10032.101.01.pdf -fi 10032 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10034.101.01.pdf -fi 10034 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10034.101.01.pdf -fi 10034 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10035.101.01.pdf -fi 10035 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10035.101.01.pdf -fi 10035 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10036.101.01.pdf -fi 10036 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10036.101.01.pdf -fi 10036 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10037.101.01.pdf -fi 10037 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10037.101.01.pdf -fi 10037 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10038.101.01.pdf -fi 10038 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10038.101.01.pdf -fi 10038 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10039.101.01.pdf -fi 10039 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10039.101.01.pdf -fi 10039 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10040.101.01.pdf -fi 10040 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10041.101.01.pdf -fi 10041 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10041.101.01.pdf -fi 10041 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10042.101.01.pdf -fi 10042 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10042.101.01.pdf -fi 10042 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10043.101.01.pdf -fi 10043 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10043.101.01.pdf -fi 10043 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10043.101.01.pdf -fi 10043 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10046.101.01.pdf -fi 10046 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10046.101.01.pdf -fi 10046 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10048.101.01.pdf -fi 10048 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10048.101.01.pdf -fi 10048 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10050.101.01.pdf -fi 10050 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10050.101.01.pdf -fi 10050 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10051.104.01.pdf -fi 10051 -fd '2013-04-04' -si 104 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10051.104.01.pdf -fi 10051 -fd '2013-04-04' -si 104 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10051.104.01.pdf -fi 10051 -fd '2013-04-04' -si 104 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10052.101.01.pdf -fi 10052 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10053.101.01.pdf -fi 10053 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10053.101.01.pdf -fi 10053 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10053.101.01.pdf -fi 10053 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10054.101.01.pdf -fi 10054 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10054.101.01.pdf -fi 10054 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10054.101.01.pdf -fi 10054 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10055.101.01.pdf -fi 10055 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10055.101.01.pdf -fi 10055 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10056.101.01.pdf -fi 10056 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10056.101.01.pdf -fi 10056 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10056.101.01.pdf -fi 10056 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10057.102.01.pdf -fi 10057 -fd '2013-04-04' -si 102 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10057.102.01.pdf -fi 10057 -fd '2013-04-04' -si 102 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10059.101.01.pdf -fi 10059 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10059.101.01.pdf -fi 10059 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10059.101.01.pdf -fi 10059 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10060.101.01.pdf -fi 10060 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10060.101.01.pdf -fi 10060 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10061.101.01.pdf -fi 10061 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10061.101.01.pdf -fi 10061 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10062.101.01.pdf -fi 10062 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10062.101.01.pdf -fi 10062 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10062.101.01.pdf -fi 10062 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10064.101.01.pdf -fi 10064 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10064.101.01.pdf -fi 10064 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10064.101.01.pdf -fi 10064 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10066.101.01.pdf -fi 10066 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10066.101.01.pdf -fi 10066 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10066.101.01.pdf -fi 10066 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10068.101.01.pdf -fi 10068 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10068.101.01.pdf -fi 10068 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10069.101.01.pdf -fi 10069 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10069.101.01.pdf -fi 10069 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10070.101.01.pdf -fi 10070 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10070.101.01.pdf -fi 10070 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10071.101.01.pdf -fi 10071 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10071.101.01.pdf -fi 10071 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10072.101.01.pdf -fi 10072 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10072.101.01.pdf -fi 10072 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10073.101.01.pdf -fi 10073 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10073.101.01.pdf -fi 10073 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10074.101.01.pdf -fi 10074 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10074.101.01.pdf -fi 10074 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10074.101.01.pdf -fi 10074 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10078.101.01.pdf -fi 10078 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10078.101.01.pdf -fi 10078 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10082.101.01.pdf -fi 10082 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10082.101.01.pdf -fi 10082 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10083.101.01.pdf -fi 10083 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10083.101.01.pdf -fi 10083 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10086.101.01.pdf -fi 10086 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10086.101.01.pdf -fi 10086 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10088.101.01.pdf -fi 10088 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10088.101.01.pdf -fi 10088 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10089.101.01.pdf -fi 10089 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10089.101.01.pdf -fi 10089 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10090.101.01.pdf -fi 10090 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10090.101.01.pdf -fi 10090 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10091.101.01.pdf -fi 10091 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10091.101.01.pdf -fi 10091 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10092.101.01.pdf -fi 10092 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10092.101.01.pdf -fi 10092 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10093.101.01.pdf -fi 10093 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10093.101.01.pdf -fi 10093 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10094.101.01.pdf -fi 10094 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10094.101.01.pdf -fi 10094 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10095.101.01.pdf -fi 10095 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10095.101.01.pdf -fi 10095 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10096.101.01.pdf -fi 10096 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10096.101.01.pdf -fi 10096 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10096.101.01.pdf -fi 10096 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10097.101.01.pdf -fi 10097 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10097.101.01.pdf -fi 10097 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10098.101.01.pdf -fi 10098 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10098.101.01.pdf -fi 10098 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10101.101.01.pdf -fi 10101 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10101.101.01.pdf -fi 10101 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10101.101.01.pdf -fi 10101 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10109.101.01.pdf -fi 10109 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10109.101.01.pdf -fi 10109 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10110.101.01.pdf -fi 10110 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10110.101.01.pdf -fi 10110 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10111.101.01.pdf -fi 10111 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10111.101.01.pdf -fi 10111 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10112.101.01.pdf -fi 10112 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10112.101.01.pdf -fi 10112 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10113.101.01.pdf -fi 10113 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10113.101.01.pdf -fi 10113 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10114.102.01.pdf -fi 10114 -fd '2013-04-04' -si 102 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10114.102.01.pdf -fi 10114 -fd '2013-04-04' -si 102 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10115.102.01.pdf -fi 10115 -fd '2013-04-04' -si 102 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10115.102.01.pdf -fi 10115 -fd '2013-04-04' -si 102 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10116.101.01.pdf -fi 10116 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10116.101.01.pdf -fi 10116 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10117.101.01.pdf -fi 10117 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10117.101.01.pdf -fi 10117 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10117.101.01.pdf -fi 10117 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10118.101.01.pdf -fi 10118 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10118.101.01.pdf -fi 10118 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10119.101.01.pdf -fi 10119 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10119.101.01.pdf -fi 10119 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10120.102.01.pdf -fi 10120 -fd '2013-04-04' -si 102 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10120.102.01.pdf -fi 10120 -fd '2013-04-04' -si 102 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10121.101.01.pdf -fi 10121 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10121.101.01.pdf -fi 10121 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10122.101.01.pdf -fi 10122 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10122.101.01.pdf -fi 10122 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10123.101.01.pdf -fi 10123 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10123.101.01.pdf -fi 10123 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10124.101.01.pdf -fi 10124 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10124.101.01.pdf -fi 10124 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10125.101.01.pdf -fi 10125 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10125.101.01.pdf -fi 10125 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10126.101.01.pdf -fi 10126 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10126.101.01.pdf -fi 10126 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10127.101.01.pdf -fi 10127 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10127.101.01.pdf -fi 10127 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10128.101.01.pdf -fi 10128 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10128.101.01.pdf -fi 10128 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10129.101.01.pdf -fi 10129 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10129.101.01.pdf -fi 10129 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10130.101.01.pdf -fi 10130 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10130.101.01.pdf -fi 10130 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10130.101.01.pdf -fi 10130 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10131.101.01.pdf -fi 10131 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10131.101.01.pdf -fi 10131 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10131.101.01.pdf -fi 10131 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10132.101.01.pdf -fi 10132 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10132.101.01.pdf -fi 10132 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10133.101.01.pdf -fi 10133 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10133.101.01.pdf -fi 10133 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10134.101.01.pdf -fi 10134 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10134.101.01.pdf -fi 10134 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10134.101.01.pdf -fi 10134 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10135.101.01.pdf -fi 10135 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10135.101.01.pdf -fi 10135 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10135.101.01.pdf -fi 10135 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10136.101.01.pdf -fi 10136 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10136.101.01.pdf -fi 10136 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10136.101.01.pdf -fi 10136 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10137.101.01.pdf -fi 10137 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10137.101.01.pdf -fi 10137 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10138.105.01.pdf -fi 10138 -fd '2013-04-04' -si 105 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10138.105.01.pdf -fi 10138 -fd '2013-04-04' -si 105 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10138.105.01.pdf -fi 10138 -fd '2013-04-04' -si 105 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10139.101.01.pdf -fi 10139 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10139.101.01.pdf -fi 10139 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10139.101.01.pdf -fi 10139 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10140.101.01.pdf -fi 10140 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10140.101.01.pdf -fi 10140 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10140.101.01.pdf -fi 10140 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10141.101.01.pdf -fi 10141 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10141.101.01.pdf -fi 10141 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10142.101.01.pdf -fi 10142 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10142.101.01.pdf -fi 10142 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10142.101.01.pdf -fi 10142 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10143.101.01.pdf -fi 10143 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10143.101.01.pdf -fi 10143 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10144.101.01.pdf -fi 10144 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10144.101.01.pdf -fi 10144 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10145.102.01.pdf -fi 10145 -fd '2013-04-04' -si 102 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10145.102.01.pdf -fi 10145 -fd '2013-04-04' -si 102 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10145.102.01.pdf -fi 10145 -fd '2013-04-04' -si 102 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10146.101.01.pdf -fi 10146 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10146.101.01.pdf -fi 10146 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10146.101.01.pdf -fi 10146 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10147.101.01.pdf -fi 10147 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10147.101.01.pdf -fi 10147 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10147.101.01.pdf -fi 10147 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10148.101.01.pdf -fi 10148 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10148.101.01.pdf -fi 10148 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10148.101.01.pdf -fi 10148 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10149.102.01.pdf -fi 10149 -fd '2013-04-04' -si 102 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10149.102.01.pdf -fi 10149 -fd '2013-04-04' -si 102 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10149.102.01.pdf -fi 10149 -fd '2013-04-04' -si 102 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10150.101.01.pdf -fi 10150 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10150.101.01.pdf -fi 10150 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10150.101.01.pdf -fi 10150 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10151.101.01.pdf -fi 10151 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10151.101.01.pdf -fi 10151 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10151.101.01.pdf -fi 10151 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10152.101.01.pdf -fi 10152 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10152.101.01.pdf -fi 10152 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10152.101.01.pdf -fi 10152 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10153.101.01.pdf -fi 10153 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10153.101.01.pdf -fi 10153 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10153.101.01.pdf -fi 10153 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10154.101.01.pdf -fi 10154 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10154.101.01.pdf -fi 10154 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10155.101.01.pdf -fi 10155 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10155.101.01.pdf -fi 10155 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10156.101.01.pdf -fi 10156 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10156.101.01.pdf -fi 10156 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10157.101.01.pdf -fi 10157 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10157.101.01.pdf -fi 10157 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10158.101.01.pdf -fi 10158 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10158.101.01.pdf -fi 10158 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10159.101.01.pdf -fi 10159 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10159.101.01.pdf -fi 10159 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10160.101.01.pdf -fi 10160 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10160.101.01.pdf -fi 10160 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10161.101.01.pdf -fi 10161 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10161.101.01.pdf -fi 10161 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10162.101.01.pdf -fi 10162 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10162.101.01.pdf -fi 10162 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10163.101.01.pdf -fi 10163 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10163.101.01.pdf -fi 10163 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10164.101.01.pdf -fi 10164 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10164.101.01.pdf -fi 10164 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10165.101.01.pdf -fi 10165 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10165.101.01.pdf -fi 10165 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10166.101.01.pdf -fi 10166 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10166.101.01.pdf -fi 10166 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10166.101.01.pdf -fi 10166 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10167.101.01.pdf -fi 10167 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10167.101.01.pdf -fi 10167 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10168.101.01.pdf -fi 10168 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10168.101.01.pdf -fi 10168 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10169.101.01.pdf -fi 10169 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10169.101.01.pdf -fi 10169 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10170.101.01.pdf -fi 10170 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10170.101.01.pdf -fi 10170 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10171.101.01.pdf -fi 10171 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10171.101.01.pdf -fi 10171 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10172.101.01.pdf -fi 10172 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10172.101.01.pdf -fi 10172 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10173.101.01.pdf -fi 10173 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10173.101.01.pdf -fi 10173 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10174.101.01.pdf -fi 10174 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10174.101.01.pdf -fi 10174 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10175.106.01.pdf -fi 10175 -fd '2013-04-04' -si 106 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10175.106.01.pdf -fi 10175 -fd '2013-04-04' -si 106 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10176.101.01.pdf -fi 10176 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10176.101.01.pdf -fi 10176 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10177.101.01.pdf -fi 10177 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10177.101.01.pdf -fi 10177 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10178.101.01.pdf -fi 10178 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10178.101.01.pdf -fi 10178 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10179.101.01.pdf -fi 10179 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10179.101.01.pdf -fi 10179 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10180.101.01.pdf -fi 10180 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10180.101.01.pdf -fi 10180 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10181.101.01.pdf -fi 10181 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10181.101.01.pdf -fi 10181 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10182.101.01.pdf -fi 10182 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10182.101.01.pdf -fi 10182 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10183.101.01.pdf -fi 10183 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10183.101.01.pdf -fi 10183 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10184.101.01.pdf -fi 10184 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10184.101.01.pdf -fi 10184 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10185.101.01.pdf -fi 10185 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10185.101.01.pdf -fi 10185 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10186.102.01.pdf -fi 10186 -fd '2013-04-04' -si 102 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10186.102.01.pdf -fi 10186 -fd '2013-04-04' -si 102 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10187.101.01.pdf -fi 10187 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10187.101.01.pdf -fi 10187 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10188.101.01.pdf -fi 10188 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10188.101.01.pdf -fi 10188 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10189.101.01.pdf -fi 10189 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10189.101.01.pdf -fi 10189 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10190.101.01.pdf -fi 10190 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10190.101.01.pdf -fi 10190 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10191.101.01.pdf -fi 10191 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10191.101.01.pdf -fi 10191 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10192.101.01.pdf -fi 10192 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10192.101.01.pdf -fi 10192 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10193.101.01.pdf -fi 10193 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10193.101.01.pdf -fi 10193 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10194.106.01.pdf -fi 10194 -fd '2013-04-04' -si 106 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10194.106.01.pdf -fi 10194 -fd '2013-04-04' -si 106 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10195.101.01.pdf -fi 10195 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10195.101.01.pdf -fi 10195 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10196.101.01.pdf -fi 10196 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10196.101.01.pdf -fi 10196 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10197.102.01.pdf -fi 10197 -fd '2013-04-04' -si 102 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10197.102.01.pdf -fi 10197 -fd '2013-04-04' -si 102 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10198.101.01.pdf -fi 10198 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10198.101.01.pdf -fi 10198 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10199.101.01.pdf -fi 10199 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10199.101.01.pdf -fi 10199 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10200.101.01.pdf -fi 10200 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10200.101.01.pdf -fi 10200 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10201.101.01.pdf -fi 10201 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10201.101.01.pdf -fi 10201 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10201.101.01.pdf -fi 10201 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10202.101.01.pdf -fi 10202 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10202.101.01.pdf -fi 10202 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10203.101.01.pdf -fi 10203 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10203.101.01.pdf -fi 10203 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10204.101.01.pdf -fi 10204 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10204.101.01.pdf -fi 10204 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10204.101.01.pdf -fi 10204 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10205.101.01.pdf -fi 10205 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10205.101.01.pdf -fi 10205 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10206.101.01.pdf -fi 10206 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10206.101.01.pdf -fi 10206 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10207.101.01.pdf -fi 10207 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10207.101.01.pdf -fi 10207 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10208.101.01.pdf -fi 10208 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"

	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10208.101.01.pdf -fi 10208 -fd '2013-04-04' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10300.101.01.pdf -fi 10300 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10300.101.01.pdf -fi 10300 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10301.101.01.pdf -fi 10301 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10301.101.01.pdf -fi 10301 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10302.101.01.pdf -fi 10302 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10302.101.01.pdf -fi 10302 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10303.101.01.pdf -fi 10303 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10303.101.01.pdf -fi 10303 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10303.101.01.pdf -fi 10303 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10304.105.01.pdf -fi 10304 -fd '2014-10-10' -si 105 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10304.105.01.pdf -fi 10304 -fd '2014-10-10' -si 105 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10305.101.01.pdf -fi 10305 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10305.101.01.pdf -fi 10305 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10306.101.01.pdf -fi 10306 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10306.101.01.pdf -fi 10306 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10307.101.01.pdf -fi 10307 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10307.101.01.pdf -fi 10307 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10308.101.01.pdf -fi 10308 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10309.101.01.pdf -fi 10309 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10309.101.01.pdf -fi 10309 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10310.101.01.pdf -fi 10310 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10310.101.01.pdf -fi 10310 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10311.101.01.pdf -fi 10311 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10311.101.01.pdf -fi 10311 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10311.101.01.pdf -fi 10311 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10312.101.01.pdf -fi 10312 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10312.101.01.pdf -fi 10312 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10313.101.01.pdf -fi 10313 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10313.101.01.pdf -fi 10313 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10314.101.01.pdf -fi 10314 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10314.101.01.pdf -fi 10314 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10314.101.01.pdf -fi 10314 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10315.101.01.pdf -fi 10315 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10315.101.01.pdf -fi 10315 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10315.101.01.pdf -fi 10315 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10316.101.01.pdf -fi 10316 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10316.101.01.pdf -fi 10316 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10317.101.01.pdf -fi 10317 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10317.101.01.pdf -fi 10317 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10318.101.01.pdf -fi 10318 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10318.101.01.pdf -fi 10318 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10319.101.01.pdf -fi 10319 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10319.101.01.pdf -fi 10319 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10319.101.01.pdf -fi 10319 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10320.101.01.pdf -fi 10320 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10320.101.01.pdf -fi 10320 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10321.110.01.pdf -fi 10321 -fd '2014-10-10' -si 110 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10321.110.01.pdf -fi 10321 -fd '2014-10-10' -si 110 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10322.110.01.pdf -fi 10322 -fd '2014-10-10' -si 110 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10322.110.01.pdf -fi 10322 -fd '2014-10-10' -si 110 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10323.102.01.pdf -fi 10323 -fd '2014-10-10' -si 102 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10323.102.01.pdf -fi 10323 -fd '2014-10-10' -si 102 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10324.101.01.pdf -fi 10324 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10324.101.01.pdf -fi 10324 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10325.101.01.pdf -fi 10325 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10325.101.01.pdf -fi 10325 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10326.102.01.pdf -fi 10326 -fd '2014-10-10' -si 102 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10326.102.01.pdf -fi 10326 -fd '2014-10-10' -si 102 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10327.101.01.pdf -fi 10327 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10327.101.01.pdf -fi 10327 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10328.101.01.pdf -fi 10328 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10328.101.01.pdf -fi 10328 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10328.101.01.pdf -fi 10328 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10329.101.01.pdf -fi 10329 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10329.101.01.pdf -fi 10329 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10329.101.01.pdf -fi 10329 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10330.101.01.pdf -fi 10330 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10330.101.01.pdf -fi 10330 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10330.101.01.pdf -fi 10330 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10331.101.01.pdf -fi 10331 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10331.101.01.pdf -fi 10331 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10331.101.01.pdf -fi 10331 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10332.101.01.pdf -fi 10332 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10332.101.01.pdf -fi 10332 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10333.101.01.pdf -fi 10333 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10333.101.01.pdf -fi 10333 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10334.101.01.pdf -fi 10334 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10334.101.01.pdf -fi 10334 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10335.101.01.pdf -fi 10335 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10335.101.01.pdf -fi 10335 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10335.101.01.pdf -fi 10335 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10336.101.01.pdf -fi 10336 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10336.101.01.pdf -fi 10336 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10336.101.01.pdf -fi 10336 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10337.102.01.pdf -fi 10337 -fd '2014-10-10' -si 102 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10337.102.01.pdf -fi 10337 -fd '2014-10-10' -si 102 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10337.102.01.pdf -fi 10337 -fd '2014-10-10' -si 102 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10338.101.01.pdf -fi 10338 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-HPLC" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10338.101.01.pdf -fi 10338 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10339.101.01.pdf -fi 10339 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-NMR" --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'      
	python src/import_attachedfiles.py -f $DATADIR/qc/LCMS_HMSL10339.101.01.pdf -fi 10339 -fd '2014-10-10' -si 101 -bi 1 -ft "QC-LCMS" --restricted
	check_errs $? "import attached file fails"
	
# if restricted:
#	python src/import_attachedfiles.py -f attach_test_1.txt -fi 10001 -ft "text"  -fd '2012-12-10' -si 101 -bi 1 --restricted
	
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
