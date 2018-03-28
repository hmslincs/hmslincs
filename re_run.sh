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

DIR=/n/groups/lincs/

if [[ $# -lt 1 ]]
then 
  echo "Usage: $0 <required: [test | local | dev | stage | prod] > [optional: local data dir]"
  echo "Set the \"VENV\" environment variable to activate a specific virtualenv"
  exit $WRONG_ARGS
fi

SERVER=$1
DATADIR=$2

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
elif [[ "$SERVER" == "LOCAL" ]] || [[ "$SERVER" == "local" ]] 
then
  DATADIR=${DATADIR:-/home/sde4/sean/docs/work/LINCS/data/dev}
  DB=django
  DB_USER=django
  PGHOST=localhost
elif [[ "$SERVER" == "TEST" ]] || [[ "$SERVER" == "test" ]] 
then
  DATADIR="${DATADIR:-sampledata}"
  DB=django
  DB_USER=django
  PGHOST=localhost
else
  echo "Unknown option: \"$SERVER\""
  exit 1
fi


./generate_drop_all.sh $DB_USER $DB $PGHOST | psql -U$DB_USER  $DB -h $PGHOST 
check_errs $? "dropdb fails"

if [[ -z "${VIRTUAL_ENV}" ]] 
then
  if [[ -z "${VENV}" ]]
  then
    VENV="$(dirname $0)/../virtualenv_o2/"
  fi
  if [[ ! -e $VENV ]]
  then
    echo "ERROR: virtualenv at \"${VENV}\" does not exist"
    exit 1
  fi
  echo "using virtualenv at \"${VENV}\" "
  module load gcc/6.2.0
  module load python/2.7.12
  source $VENV/bin/activate
  check_errs $? "failed to activate virtualenv: $VENV"
else
  echo "Using already active virtual environment: \"${VIRTUAL_ENV}\" "
fi

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
  
  echo 'import cell line tables ...'
  python src/import_cell.py -f sampledata/sample_cells.xlsx
  check_errs $? "import cell fails"
  
  echo 'import cell line batch tables ...'
  python src/import_cell_batch.py -f sampledata/sample_cell_line_batch.xlsx
  check_errs $? "import cell fails"
  
  echo 'import cell line precursor patches ...'
  python src/import_cell.py -f sampledata/sample_cells.xlsx --do_precursors
  check_errs $? "import cell precursors fails"

  echo 'import primary cell tables ...'
  python src/import_primary_cell.py -f sampledata/sample_primary_cells.xlsx
  check_errs $? "import primary cell fails"
  
  echo 'import primary cell line batch tables ...'
  python src/import_primary_cell_batch.py -f sampledata/sample_primary_cell_batch.xlsx
  check_errs $? "import cell fails"
  
  echo 'import primary cell precursor patches ...'
  python src/import_primary_cell.py -f sampledata/sample_primary_cells.xlsx --do_precursors
  check_errs $? "import primary cell precursors fails"
  
  echo 'import ipsc cell tables ...'
  python src/import_ipsc.py -f sampledata/sample_ipscs.xlsx
  check_errs $? "import ipscs fails"
  
  echo 'import ipsc cell batch tables ...'
  python src/import_ipsc_batch.py -f sampledata/sample_ipsc_batches.xlsx
  check_errs $? "import ipsc cell batches fails"
  
  # Note: if differentiated cells reference precursor IPSC batch cells, make
  # sure these are loaded before this.
  echo 'import differentiated cell tables ...'
  python src/import_differentiated_cell.py -f sampledata/sample_differentiated_cells.xlsx
  check_errs $? "import differentiated cell fails"
  
  echo 'import differentiated cell batch tables ...'
  python src/import_differentiated_cell_batch.py -f sampledata/sample_differentiated_cell_batches.xlsx
  check_errs $? "import differentiated cell batches fails"
  
  echo 'import small molecule tables...'
  python src/import_smallmolecule.py -f  sampledata/sample_small_molecules.sdf
  check_errs $? "import sdf fails"

  echo 'import salt table...'
  python src/import_smallmolecule.py -f  sampledata/sample_salts.sdf
  check_errs $? "import sdf fails"

  echo 'import small molecule batch tables...'
  python src/import_smallmolecule_batch.py -f sampledata/sample_small_molecule_batch.xls
  check_errs $? "import smallmolecule batch fails"
  
  echo 'import small molecule batch qc reports...'
  python src/import_qc_events_batch.py -f sampledata/sample_qc_events_batch.xlsx -fd $DATADIR
  check_errs $? "import_qc_events_batch fails"
  
  echo 'import library mapping tables...'
  python src/import_libraries.py -f sampledata/sample_libraries.xls
  check_errs $? "import library fails"
	    
  echo 'import kinase tables...'
  python src/import_protein.py -f sampledata/sample_proteins.xls
  check_errs $? 'import kinases fails'
    
  echo 'import antibody tables...'
  python src/import_antibody.py -f sampledata/sample_antibodies.xlsx
  check_errs $? 'import antibodies fails'

  echo 'import antibody batches...'
  python src/import_antibody_batch.py -f sampledata/sample_antibody_batches.xlsx
  check_errs $? 'import antibody batches fails'

  echo 'import other reagent tables...'
  python src/import_other_reagent.py -f sampledata/sample_other_reagents.xls
  check_errs $? 'import other reagents fails'
  
  echo 'import other reagent batches...'
  python src/import_other_reagent_batch.py -f sampledata/sample_other_reagent_batches.xlsx
  check_errs $? 'import other reagent batches fails'

  echo 'import unclassified perturbagen tables...'
  python src/import_unclassified_perturbagen.py -f sampledata/sample_unclassified_perturbagens.xlsx
  check_errs $? 'import unclassified perturbagens fails'
  
  echo 'import unclassified perturbagen batches...'
  python src/import_unclassified_perturbagen_batch.py -f sampledata/sample_unclassified_perturbagen_batches.xlsx
  check_errs $? 'import unclassified perturbagens batches fails'

  echo 'import test_dataset...'
  python src/import_dataset2.py -f sampledata/test_dataset.xls 
  check_errs $? "import dataset fails"
  
  echo 'import test_dataset2...'
  python src/import_dataset2.py -f sampledata/test_dataset2.xls 
  check_errs $? "import dataset 2 fails"
  
  echo 'import test_dataset_no_data...'
  python src/import_dataset2.py -f sampledata/test_dataset_no_data.xlsx 
  check_errs $? "import test_dataset_no_data fails"
  
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
  python src/import_cell.py -f $DATADIR/cells.xlsx
  check_errs $? "import cell fails"
  
  echo 'import cell batch tables ...'
  python src/import_cell_batch.py -f $DATADIR/cells_batch.xlsx
  check_errs $? "import cell fails"
  
  echo 'import cell line precursor patches ...'
  python src/import_cell.py -f $DATADIR/cells.xlsx --do_precursors
  check_errs $? "import cell precursors fails"
  
  echo 'import primary cell tables ...'
  python src/import_primary_cell.py -f $DATADIR/primary_cells.xlsx
  check_errs $? "import primary cell fails"
  
  echo 'import primary cell line batch tables ...'
  python src/import_primary_cell_batch.py -f $DATADIR/primary_cells_batch.xlsx
  check_errs $? "import cell fails"
  
  echo 'import primary cell precursor patches ...'
  python src/import_primary_cell.py -f $DATADIR/primary_cells.xlsx --do_precursors
  check_errs $? "import primary cell precursors fails"
  
  echo 'import ipsc cell tables ...'
  python src/import_ipsc.py -f $DATADIR/ipsc.xlsx
  check_errs $? "import ipscs fails"
  
  echo 'import ipsc cell batch tables ...'
  python src/import_ipsc_batch.py -f $DATADIR/ipsc_batch.xlsx
  check_errs $? "import ipsc cell batches fails"
  
  # Note: if differentiated cells reference precursor IPSC batch cells, make
  # sure these are loaded before this.
  echo 'import differentiated cell tables ...'
  python src/import_differentiated_cell.py -f $DATADIR/differentiated_cells.xlsx
  check_errs $? "import differentiated cell fails"
  
  echo 'import differentiated cell batch tables ...'
  python src/import_differentiated_cell_batch.py -f $DATADIR/differentiated_cells_batch.xlsx
  check_errs $? "import differentiated cell batches fails"
  
  echo 'import small molecule tables...'
  python src/import_smallmolecule.py -f $DATADIR/small_molecules.sdf
  check_errs $? "import sdf fails"

  echo 'import salt table...'
  python src/import_smallmolecule.py -f  $DATADIR/salts.sdf
  check_errs $? "import sdf fails"

  echo 'import small molecule batch tables...'
  python src/import_smallmolecule_batch.py -f $DATADIR/small_molecules_batch.xlsx
  check_errs $? "import smallmolecule batch fails"
  
  echo 'import small molecule batch qc reports...'
  python src/import_qc_events_batch.py -f $DATADIR/qc_events_batch.xlsx -fd $DATADIR
  check_errs $? "import_qc_events_batch fails"
  
  echo 'import library mapping tables...'
  python src/import_libraries.py -f $DATADIR/libraries.xlsx
  check_errs $? "import library fails"
  
  echo 'import kinase tables...'
  python src/import_protein.py -f $DATADIR/proteins.xlsx
  check_errs $? 'import kinases fails'
  
  echo 'import antibody tables...'
  python src/import_antibody.py -f $DATADIR/antibodies.xlsx
  check_errs $? 'import antibodies fails'
  
  echo 'import antibody batches...'
  python src/import_antibody_batch.py -f $DATADIR/antibodies_batch.xlsx
  check_errs $? 'import antibody batches fails'
  
  echo 'import other reagent tables...'
  python src/import_other_reagent.py -f $DATADIR/other_reagents.xlsx
  check_errs $? 'import other reagents fails'
  
  echo 'import other reagent batches...'
  python src/import_other_reagent_batch.py -f $DATADIR/other_reagents_batch.xlsx
  check_errs $? 'import other reagent batches fails'
  
  echo 'import unclassified perturbagen tables...'
  python src/import_unclassified_perturbagen.py -f $DATADIR/unclassified_perturbagens.xlsx
  check_errs $? 'import unclassified perturbagens fails'
  
  echo 'import unclassified perturbagen batches...'
  python src/import_unclassified_perturbagen_batch.py -f $DATADIR/unclassified_perturbagens_batch.xlsx
  check_errs $? 'import unclassified perturbagens batches fails'
  
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
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinativ/Screen20205_HMSL10077_kinativ.xls
  check_errs $? "import dataset fails"
  
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
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20212_HMSL10363_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinativ/Screen20213_HMSL10363_kinativ.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinativ/Screen20214_HMSL10129_kinativ.xls
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
  python src/import_dataset2.py -f $DATADIR/Screen20236_LinCycIF.xlsx
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
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20244_HCl1.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20245_LJP-8.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20246_LJP-9.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20247_LJP-10.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20248_LJP-11.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20249_LJP-12.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20250_LJP-13.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20251_LJP-14.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20252_LJP-15.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinativ/Screen20253_HMSL10084_kinativ.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinativ/Screen20254_HMSL10231_kinativ.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinativ/Screen20255_HMSL10356_kinativ.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20256_density_all.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20257_density_mean.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20258_density_fits.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20259_LJP_drugcombo_all.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20260_LJP_drugcombo_mean.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20261_HMSL10047_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20262_HMSL10147_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20263_HMSL10233_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20264_HMSL10445_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20265_DS1.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20266_DS2.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20267_DS3.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20268_HeiserDS1.xlsx
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20269_HeiserDS2.xlsx
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20270_HeiserDS3.xlsx
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20271_HeiserDS4.xlsx
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20272_BRAF7.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20273_BRAF8.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20274_BRAF9.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20275_BRAF10.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20276_BRAF11.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20277_BRAF12.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20278_AllCellCount-1.xlsx
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20279_AllCellCount-2.xlsx
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20280_AllCellCount-3.xlsx
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20281_MeanCellCount-1.xlsx
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20282_MeanCellCount-2.xlsx
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20283_MeanCellCount-3.xlsx
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20284_GRmetrics-1.xlsx
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20285_GRmetrics-2.xlsx
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20286_GRmetrics-3.xlsx
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20287.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20288.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20289.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20290.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20291.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20292.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20293.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20294.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20295.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20296.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20297.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20298.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20299.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20300.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20301.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20302.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20303_MCF10A_CycIF-1.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20304_MCF10A_CycIF-2.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20305_MCF10A_CycIF-3.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20306_MCF10A_CycIF-4.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20307_MCF10A_CycIF-5.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20308_MCF10A_CycIF-6.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20309_MCF10A-1.xlsx
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20310_MCF10A-2.xlsx
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20311_MCF10A-3.xlsx
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20312_MCF10A-4.xlsx
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20313_MCF10A-5.xlsx
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20314_MCF10A-6.xlsx
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20315_MCF10A-7.xlsx
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20316_MCF10A-8.xlsx
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20317_MCF10A-9.xlsx
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20318_MCF10A-10.xlsx
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20319_MCF10A-11.xlsx
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20320_MCF10A-12.xlsx
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20321_MCF10A-13.xlsx
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20322_MCF10A-14.xlsx
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/Screen20323_MCF10A-15.xlsx
  check_errs $? "import dataset fails"
   
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20326_HMSL10201_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20327_HMSL10423_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20328_HMSL10345_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20329_HMSL10394_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20330_HMSL10395_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20331_HMSL10419_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20332_HMSL10427_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20333_HMSL10442_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20334_HMSL10429_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20335_HMSL10477_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20336_HMSL10432_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20337_HMSL10522_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20338_HMSL10390_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20339_HMSL10071_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20340_HMSL10077_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20341_HMSL10240_kinomescan.xls
  check_errs $? "import dataset fails"
  
  echo 'import screen results...'
  python src/import_dataset2.py -f $DATADIR/kinomescan/Screen20342_HMSL10350_kinomescan.xls
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
