#!/bin/sh

# find the restricted sm images and move them to the authenticated images
# static file dir

# NOTE: all variables below whose initialization has the form
#
# VAR=${VAR:-defaultvalue}
#
# can be overridden in the command line by prefixing it with a suitable inline
# assignment.  In particular, to undo the script's default operation, run it
# with the UNDO=true prefix.

set -e

DEBUG=${DEBUG:-false}
if $DEBUG; then
  set -x
  VERBOSE=-v
else
  VERBOSE=
fi

# If UNDO is true, the script undoes the actions of its default operation
UNDO=${UNDO:-false}

# When CLEAN is true, the undo operation will also remove all subdirectories
# under the destination directory; meaningful only if UNDO is true
$UNDO && CLEAN=${CLEAN:-false}

PROG=$( basename $0 )
function _error {
  echo "$PROG: $1" >&2
  exit 1
}

# 'readlink -f' is used below to canonicalize paths; NOTE: GNU readlink is
# required for this
READLINK=${READLINK:-readlink}

# SCRIPTDIR is used to:
# 1) determine the location of the source and destination directories;
# 2) determine the DB connection parameters, unless they have already been
#    passed to the script through the environment
SCRIPTDIR=$( dirname $( $READLINK -f $0 ) )
BASEDIR=$( $READLINK -f $SCRIPTDIR/.. )

SOURCEDIR=$BASEDIR/../docroot/_static
DESTDIR=$BASEDIR/authenticated_static_files

function _move_from {
  origin=${1%/}
  filepath=$2
  tgt=$(dirname ${filepath#$origin/})
  mkdir $VERBOSE -p $tgt
  mv -f $VERBOSE -t $tgt $filepath
}

function move_restricted {
  if [[ $SCRIPTDIR =~ .*dev\.lincs.*support/hmslincs ]]; then
    DB=${DB:-devlincs}
    DBUSER=${DBUSER:-devlincsweb}
    DBHOST=${DBHOST:-dev.pgsql.orchestra}
  elif [[ $SCRIPTDIR =~ .*osher.*support/hmslincs ]]; then
    DB=${DB:-devoshernatprod}
    DBUSER=${DBUSER:-devoshernatprodweb}
    DBHOST=${DBHOST:-dev.pgsql.orchestra}
  elif [[ $SCRIPTDIR =~ /www/lincs.*support/hmslincs ]]; then
    DB=${DB:-lincs}
    DBUSER=${DBUSER:-lincsweb}
    DBHOST=${DBHOST:-pgsql.orchestra}
  fi

  if [[ -z $DB ]] || [[ -z $DBUSER ]] || [[ -z $DBHOST ]]; then
    _error "Cannot determine db connection parameters.  Exiting..."
  elif $DEBUG; then
    echo "Will connect with 'psql $DB -h $DBHOST -U $DBUSER'"
  fi

  SQL='SELECT facility_id FROM db_smallmolecule WHERE is_restricted IS TRUE;'

  cd $DESTDIR
  count=0
  for fac_id in $( psql $DB -h $DBHOST -U $DBUSER -Atc "$SQL" ); do 
    if $DEBUG; then echo "facility id to restrict: $fac_id"; fi
    for fpath in $( find $SOURCEDIR -name "*$fac_id*" ); do
      _move_from $SOURCEDIR $fpath
      count=$(( count + 1 ))
    done
  done
  if $DEBUG; then echo "$count files moved"; fi
}

function _undo {
  cd $SOURCEDIR
  count=0
  for fpath in $( find $DESTDIR -type f ); do
    _move_from $DESTDIR $fpath
    count=$(( count + 1 ))
  done
  if $DEBUG; then echo "$count files moved"; fi

  $CLEAN && find $DESTDIR -mindepth 1 -type d -exec rm -rf {} +
}

if $UNDO; then
  _undo
else
  move_restricted
fi
