#!/bin/bash

if [[ $# -lt 2 ]]
then
  echo "generate_drop_all.sh <user> <db>"
  exit 1;
fi

USER=$1
DB=$2
HOST=$3
TABLE_PREFIX="db_" # django model prefixes the table names with the app name, "db" in this case
echo "begin;" 
psql -U$USER $DB -h $HOST -c \\d |grep table |grep $TABLE_PREFIX |nawk '{print "drop table " $3 " cascade;" }'
#psql -U$USER $DB -c \\d |grep sequence |grep example |nawk '{print "drop sequence " $3 " cascade;" }'
echo "commit;"
