#!/bin/sh

# find the restricted sm images and move them to the authenticated images static file dir

SOURCE_DIR=../images
DEST_DIR=../authenticated_static_files

pwd=`pwd`
DB=""
DBUSER=""
DBHOST=""
if [[ "$pwd" =~ .*dev\.lincs.*support/hmslincs ]]; then
  DB="devlincs"
  DBUSER="devlincsweb"
  DBHOST="dev.pgsql.orchestra"
elif [[ "$pwd" =~ .*osher.*support/hmslincs ]]; then
  DB="devoshernatprod"
  DBUSER="devoshernatprodweb"
  DBHOST="dev.pgsql.orchestra"
elif [[ "$pwd" =~ /www/lincs.*support/hmslincs ]]; then
  DB="lincs"
  DBUSER="lincsweb"
  DBHOST="pgsql.orchestra"  
else
  echo "Must run from one of the recognized directories"
fi

echo "DB: $DB"


for x in `psql  $DB -h $DBHOST -c 'select facility_id from db_smallmolecule where is_restricted is true;'|awk '{print $1}'|grep -E ^[0-9]+ `;
#for x in `psql -Udevoshernatprodweb devoshernatprod -h dev.pgsql.orchestra -c 'select facility_id from db_smallmolecule where is_restricted is true;'|awk '{print $1}'|grep -E ^[0-9]+ `;
do 
	echo "facility id to restrict: $x"; 
	for y in `find $SOURCE_DIR -name "*$x*" `;
		do
		echo "file: $y"; 
		dir=`echo "$y"|awk -F '/' '{print $3}'`
		#dir1=`echo "$y"|perl -e "s#$SOURCE_DIR(.*)$y#\1#g"`
		echo "dir: $dir"
		#echo "dir1: $dir1"
		echo "mv $y $DEST_DIR/$dir/"
		if [[ ! -e $DEST_DIR/$dir ]] ;
		then
			echo "create directory: $DEST_DIR/$dir"
			mkdir $DEST_DIR/$dir
		fi
		mv $y $DEST_DIR/$dir/
	done
done

