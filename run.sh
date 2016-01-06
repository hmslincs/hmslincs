#!/bin/bash
# run a python script in the django environment
# can be used for cron jobs
# NOTE: to run from cron, cd to this directory before executing command.

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
DIR=/groups/lincs/

if [[ $# -lt 2 ]]
then 
  echo "Usage: $0 <required: [test | local | dev | stage | prod] [python_script] > <optional: python script arguments> "
  echo "Set the \"VENV\" environment variable to activate a specific virtualenv"
  exit $WRONG_ARGS
fi

SERVER=$1
shift

if [[ "$SERVER" == "PROD" ]] || [[ "$SERVER" == "prod" ]] 
then
  DATADIR=${DIR}/data/prod2
  DB=lincs
  DB_USER=lincsweb
  LINCS_PGSQL_USER=lincsweb
  PGHOST=pgsql.orchestra
  export LINCS_PGSQL_USER=$DB_USER
  export LINCS_PGSQL_DB=$DB
  export LINCS_PGSQL_SERVER=$PGHOST
  export LINCS_PGSQL_PASSWORD=`cat ~/.pgpass |grep "\W$DB_USER\W" | awk -F ':' '{print $5}'`
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
elif [[ "$SERVER" == "DEV2" ]] || [[ "$SERVER" == "dev2" ]] 
then
  DATADIR=${DIR}/data/dev2
  DB=devoshernatprod
  DB_USER=devoshernatprodweb
  PGHOST=dev.pgsql.orchestra
  export LINCS_PGSQL_USER=$DB_USER
  export LINCS_PGSQL_DB=$DB
  export LINCS_PGSQL_SERVER=$PGHOST
  export LINCS_PGSQL_PASSWORD=`cat ~/.pgpass |grep $DB_USER| awk -F ':' '{print $5}'`
elif [[ "$SERVER" == "LOCAL" ]] || [[ "$SERVER" == "local" ]] 
then
  DATADIR=/home/sde4/sean/docs/work/LINCS/data/dev2
  DB=django
  DB_USER=django
  PGHOST=localhost
elif [[ "$SERVER" == "TEST" ]] || [[ "$SERVER" == "test" ]] 
then
  # NOT NEEDED FOR TEST DATA : DATADIR=${2:-/home/sde4/workspace/hmslincs/}
  DB=django
  DB_USER=django
  PGHOST=localhost
else
  echo "Unknown option: \"$SERVER\""
  exit 1
fi

if [[ -z "${VIRTUAL_ENV}" ]] 
then
  if [[ -z "${VENV}" ]]
  then
    VENV="$(dirname $0)/../virtualenv/"
  fi
  if [[ ! -e $VENV ]]
  then
    echo "ERROR: virtualenv at \"${VENV}\" does not exist"
    exit 1
  fi
  echo "using virtualenv at \"${VENV}\" "
  source $VENV/bin/activate
  check_errs $? "failed to activate virtualenv: $VENV"
else
  echo "Using already active virtual environment: \"${VIRTUAL_ENV}\" "
fi

export DJANGO_SETTINGS_MODULE=hmslincs_server.settings
export PYTHONPATH=./django:./src
#echo "python path for execute: $PYTHONPATH, command $@"

python $@
