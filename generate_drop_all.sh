#!/bin/bash

if [[ $# -ne 2 ]]
then
  echo "generate_drop_all.sh <user> <db>"
  exit 1;
fi

USER=$1
DB=$2
echo "begin;" 
psql -U$USER $DB -c \\d |grep table |grep example |nawk '{print "drop table " $3 " cascade;" }'
psql -U$USER $DB -c \\d |grep sequence |grep example |nawk '{print "drop sequence " $3 " cascade;" }'
echo "commit;"
