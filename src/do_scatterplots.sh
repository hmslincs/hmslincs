#!/usr/bin/env zsh

# Requires GNU versions of sort, cut, and mkdir; if these GNU
# utilities are not in PATH, or if they're available under different
# names, specify them via inline assignments to the SORT, CUT, and/or
# MKDIR variables, as shown in the example below:
#
# SORT=<GNU sort> CUT=<GNU cut> MKDIR=<GNU mkdir> OUTPUTDIR=tmp/trash \
#    CLOBBEROK=1 src/do_scatterplots.sh

# set -x
set -e

DEBUG=${DEBUG:-false}

if [[ -n $VIRTUAL_ENV ]]; then
  source "$VIRTUAL_ENV/bin/activate"
fi

SRCDIR=$( dirname $0 )
EXECDIR=$( dirname $SRCDIR )
JSPATH=$EXECDIR/django/responses/static/responses/js/pointmap.js

cd $EXECDIR || false

SORT=${SORT:-sort}
JOIN=${JOIN:-$SRCDIR/join.py}
CUT=${CUT:-cut}
MKDIR=${MKDIR:-mkdir}

DATADIR0=data/scatterplots
DATADIR1=${DATADIR1:-/tmp/$$}

OUTPUTDIR=${OUTPUTDIR:-django/responses/static/responses/img}
$MKDIR -p $OUTPUTDIR

export LANG=
export LC_ALL=C 

alias SORTT="$SORT -t$'\t'"
alias CUTT="$CUT -d$'\t' -f"

BLANK=${BLANK:-''}
alias JOINT="$JOIN -t$'\t' -e '$BLANK' -o auto -a 2"

pickcols () {
  cols="1,$1"
  shift
  in=${1:--}
  shift
  if (( $# > 0 )) {
     JOINT -a 1 \
       <( CUTT $cols $in | SORTT -k1 ) \
       <( pickcols "$@" )
  } else {
    CUTT $cols $in | SORTT -k1
  }
}

addsubtype () {
  in=${1:--}
  JOINT <( CUTT 1,2 $DATADIR0/cell_line_subtype.tsv ) $in
}

addlevel () {
  in=${1:--}
  JOINT <( CUTT 1,2 $DATADIR0/lapatinib_gi50.tsv ) $in
}

pflane () {
  perl -F"\t" -lane 'BEGIN { $, = "\t" }
if ( $. == 1 ) {
  $ncols = @F = split /\t/, $_, -1;
}
else {
  $missing = $ncols - @F;
  push @F, ("") x $missing if $missing;
}
' -e $@
}

addnan () {
  pflane '
BEGIN { $blank = q,'$BLANK', }
splice @F, 1, 0, ( $. == 1 ? $blank : "nan" );
print @F'
}

adddisplayname () {
  in=${1:--}
  JOINT \
    <( CUTT 1-3 $DATADIR0/cell_line_display_name.tsv ) <( SORTT -k1,1 $in )
}

cull () {
  pflane '
BEGIN { $blank = q,'$BLANK', }
next if $. > 1 && ( ( grep { $F[$_] eq $blank } 0..3 ) or
                    $seen{ $F[0] }++ );
splice @F, 0, 1;
print @F'
}

make_w_level () {
  pickcols "$@" | addsubtype | addlevel | adddisplayname | cull
}

make_w_nan () {
  pickcols "$@" | addsubtype | addnan   | adddisplayname | cull
}

FMTTBL=$( whence fmttbl || : )
if $DEBUG && [[ -n $FMTTBL ]] {
  show () {
    head | CUTT 1-8 | $FMTTBL
    echo
  }
} else {
  show () cat > /dev/null
}

BASAL=$DATADIR0/elisa_basal.tsv
MFC=$DATADIR0/elisa_meanfoldchange.tsv
FC=$DATADIR0/elisa_foldchange.tsv

mkdir -p $DATADIR1

make_w_nan   3,5,10,12,13 $BASAL          | tee $DATADIR1/picks_for_basal.tsv         | show
make_w_nan   3,7,13,23,33,39,43,53 $MFC   | tee $DATADIR1/picks_for_responses.tsv     | show
make_w_level 5,12 $BASAL                  | tee $DATADIR1/picks_for_basal_w_color.tsv | show
make_w_level 23,43 $MFC 65-67,125-127 $FC | tee $DATADIR1/picks_for_slider.tsv        | show

SCRIPT=$( basename $0 )
echo "$SCRIPT: making $OUTPUTDIR/**/*.png files... "

$DEBUG && echo $DATADIR1

rm -f $( $DEBUG && echo -v ) $OUTPUTDIR{,/{slider,basal_graded}}/*.png(N)

[[ -n $VIRTUAL_ENV ]] && source $VIRTUAL_ENV/bin/activate


truncate -s 0 $JSPATH
echo \
'// WARNING: THIS FILE IS AUTOMATICALLY CREATED -- MANUAL EDITS WILL BE OVERWRITTEN
// Adapted from snippet at http://stackoverflow.com/questions/881515#5947280

(function( hmslincs ) {
    // data for scatterplot popups

    hmslincs.POINTMAP = {' >> $JSPATH

python src/do_scatterplots.py $DATADIR1/picks_for_basal.tsv >> $JSPATH
python src/do_scatterplots.py $DATADIR1/picks_for_responses.tsv >> $JSPATH
IDPREFIX='slider/' WITHLIMITS=1 OUTPUTDIR=$OUTPUTDIR/slider \
  python src/do_scatterplots.py $DATADIR1/picks_for_slider.tsv >> $JSPATH
IDPREFIX='basal_graded/' OUTPUTDIR=$OUTPUTDIR/basal_graded \
  python src/do_scatterplots.py $DATADIR1/picks_for_basal_w_color.tsv >> $JSPATH

echo '    }
}( window.hmslincs = window.hmslincs || {} ));' >> $JSPATH

echo "$SCRIPT: done"
