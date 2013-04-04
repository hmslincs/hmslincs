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
  export LINCS_PGSQL_PASSWORD=`cat ~/.pgpass |grep "\W$DB_USER\W" | awk -F ':' '{print $5}'`
  VIRTUALENV=/www/dev.lincs.hms.harvard.edu/support/virtualenv/bin/activate
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
	python src/import_protein.py -f sampledata/HMS-LINCS_ProteinMetadata_forLoading.xls
	check_errs $? 'import kinases fails'
	
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
	python src/import_protein.py -f $DATADIR/HMS-LINCS_ProteinMetadata_forLoading.xls
	check_errs $? 'import kinases fails'
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/Study20000_NominalTargets_forLoading.xlsx 
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/Screen20001_moerke_2color.xlsx 
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/Screen20002_moerke_3color.xlsx 
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/Screen20003_tang_MitoApop2.xlsx 
	check_errs $? "import dataset fails"

	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/Screen20004_tang_ProMitosis.xlsx 
	check_errs $? "import dataset fails"
	
	#echo 'import screen results...'
	#python src/import_dataset.py -f $DATADIR/Screen20005_tang_MitoApop2.xlsx 
	#check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/Screen20006_CMT_GrowthInhibition-3dose.xlsx 
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/Screen20007_CMT_GrowthInhibition-3dose.xlsx 
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/Screen20008_CMT_9dose-1.xlsx 
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/Screen20009_CMT_9dose-2.xlsx 
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/Screen20010_CMT_9dose-3.xlsx 
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/Screen20011_CMT_9dose-4.xlsx 
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/Screen20012_CMT_9dose-5.xlsx 
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/Screen20013_CMT_9dose-6.xlsx 
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/Screen20014_CMT_9dose-7.xlsx 
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/Screen20015_CMT_9dose-8.xlsx 
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/Screen20016_CMT_9dose-9.xlsx 
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/Screen20017_CMT_9dose-10.xlsx 
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20020_HMSL10008_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20021_HMSL10017_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20022_HMSL10029_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20023_HMSL10046_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20024_HMSL10049_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20025_HMSL10050_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20026_HMSL10068_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20027_HMSL10006_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20028_HMSL10009_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20029_HMSL10010_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20030_HMSL10012_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20031_HMSL10013_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20032_HMSL10014_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20033_HMSL10027_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20034_HMSL10028_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20035_HMSL10034_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20036_HMSL10038_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20037_HMSL10055_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20038_HMSL10059_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20039_HMSL10060_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20040_HMSL10061_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20041_HMSL10065_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20042_HMSL10066_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20043_HMSL10067_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20044_HMSL10071_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20045_HMSL10078_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20046_HMSL10092_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20047_HMSL10096_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20048_HMSL10100_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20049_HMSL10002_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20050_HMSL10003_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20051_HMSL10015_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20052_HMSL10016_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20053_HMSL10018_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20054_HMSL10025_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20055_HMSL10026_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20056_HMSL10039_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20057_HMSL10041_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20058_HMSL10043_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20059_HMSL10045_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20060_HMSL10047_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20061_HMSL10070_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20062_HMSL10075_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20063_HMSL10076_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20064_HMSL10079_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20065_HMSL10080_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20066_HMSL10082_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20067_HMSL10083_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20068_HMSL10084_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20069_HMSL10085_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20070_HMSL10086_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20071_HMSL10087_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20072_HMSL10088_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20073_HMSL10089_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20074_HMSL10090_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20075_HMSL10091_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20076_HMSL10093_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20077_HMSL10094_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20078_HMSL10095_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20079_HMSL10064_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20080_HMSL10101_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20081_HMSL10208_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20082_HMSL10140_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20083_HMSL10035_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20084_HMSL10146_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20085_HMSL10172_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20086_HMSL10223_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinativ/Screen20087_HMSL10008_kinativ.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinativ/Screen20088_HMSL10029_kinativ.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinativ/Screen20089_HMSL10046_kinativ.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinativ/Screen20090_HMSL10049_kinativ.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinativ/Screen20091_HMSL10050_kinativ.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinativ/Screen20092_HMSL10068_kinativ.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinativ/Screen20093_HMSL10017_kinativ.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinativ/Screen20094_HMSL10079_kinativ.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinativ/Screen20095_HMSL10080_kinativ.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20096_HMSL10232_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinativ/Screen20097_HMSL10086_kinativ.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinativ/Screen20098_HMSL10087_kinativ.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinativ/Screen20099_HMSL10091_kinativ.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinativ/Screen20100_HMSL10092_kinativ.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinativ/Screen20101_HMSL10093_kinativ.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinativ/Screen20102_HMSL10094_kinativ.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinativ/Screen20103_HMSL10106_kinativ.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinativ/Screen20104_HMSL10200_kinativ.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinativ/Screen20105_HMSL10201_kinativ.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinativ/Screen20106_HMSL10070_kinativ.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20107_HMSL10051_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20108_HMSL10019_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20109_HMSL10024_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20110_HMSL10040_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20111_HMSL10162_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20112_HMSL10209_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20113_HMSL10213_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20114_HMSL10058_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20115_HMSL10106_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20116_HMSL10189_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20117_HMSL10229_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20118_HMSL10102_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import screen results...'
	python src/import_dataset.py -f $DATADIR/kinomescan/Screen20119_HMSL10214_kinomescan.xlsx
	check_errs $? "import dataset fails"
	
	echo 'import attached file...'
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10001.101.01.pdf -fi 10001 -ft "QC-NMR"  -fd '2012-12-21' -si 101 -bi 1 --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10001.101.01.pdf -fi 10001 -ft "QC-HPLC"  -fd '2012-12-21' -si 101 -bi 1 --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'
	python src/import_attachedfiles.py -f $DATADIR/qc/NMR_HMSL10004.101.01.pdf -fi 10004 -ft "QC-NMR"  -fd '2012-12-21' -si 101 -bi 1 --restricted
	check_errs $? "import attached file fails"
	
	echo 'import attached file...'
	python src/import_attachedfiles.py -f $DATADIR/qc/HPLC_HMSL10004.101.01.pdf -fi 10004 -ft "QC-HPLC"  -fd '2012-12-21' -si 101 -bi 1 --restricted
	check_errs $? "import attached file fails"
	
# if restricted:
#	python src/import_attachedfiles.py -f attach_test_1.txt -fi 10001 -ft "text"  -fd '2012-12-10' -si 101 -bi 1 --restricted
	
fi

# the PGUSER=$DB_USER prefix ensures that the script will run even when (Unix)
# USER running the script does not have access $DB on $PGHOST
PGUSER=$DB_USER python src/create_indexes.py | psql -U$DB_USER  $DB -h $PGHOST -v ON_ERROR_STOP=1
#check_errs $? "create indexes fails"

