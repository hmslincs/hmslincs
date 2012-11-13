#!/usr/bin/env zsh

# NOTE: this script is probably not portable enough to run
# "out-of-the-box"; I'm committing it to git as documentation.

# set -x
set -e

EXECDIR=$( dirname $( dirname $0 ) )

cd $EXECDIR || false

# requires GNU join
JOIN=${JOIN:-join}
CUT=${CUT:-cut}
SORT=${SORT:-sort}

DATADIR0=data/scatterplots
DATADIR1=${DATADIR1:-/tmp/$$}

OUTPUTDIR=${OUTPUTDIR:-django/responses/static/responses/img}

alias gcutt="$CUT -d$'\t' -f"
alias gsortt="$SORT -t$'\t'"
alias gjoint="$JOIN -t$'\t'"

BLANK='';

pickcols () {
  cols="1,$1"
  shift
  in=${1:--}
  shift
  if (( $# > 0 )) {
     gjoint -a 1 -a 2 -e "$BLANK" -o auto \
       <( gcutt $cols $in | gsortt -k1 ) \
       <( pickcols "$@" )
  } else {
    gcutt $cols $in | gsortt -k1
  }
}

addsubtype () {
  in=${1:--}
  gjoint -a 2 -e "$BLANK" -o auto \
    <( gcutt 1,2 $DATADIR0/cell_line_subtype.tsv ) $in
}

addlevel () {
  in=${1:--}
  gjoint -a 2 -e "$BLANK" -o auto \
    <( gcutt 1,2 $DATADIR0/lapatinib_gi50.tsv ) $in
}

addnan () {
  pflane '
BEGIN { $blank = q,'$BLANK', }
splice @F, 1, 0, ( $. == 1 ? $blank : "nan" );
print @F'
}

adddisplayname () {
  in=${1:--}
  gjoint -a 2 -e "$BLANK" -o auto \
    <( gcutt 1-3 $DATADIR0/cell_line_display_name.tsv ) $in
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

FMTTBL=$( whence fmttbl )
if [[ -n $DEBUG ]] && [[ -n $FMTTBL ]] {
  show () {
    head | gcutt 1-8 | $FMTTBL
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

echo -n "making $OUTPUTDIR/**/*.png files... "

[[ -n $DEBUG ]] && echo $DATADIR1

rm -f ${DEBUG:+-v} $OUTPUTDIR/**/*.png(N)

[[ -n $VIRTUAL_ENV ]] && source $VIRTUAL_ENV/bin/activate

python src/do_scatterplots.py $DATADIR1/picks_for_basal.tsv
python src/do_scatterplots.py $DATADIR1/picks_for_responses.tsv
WITHLIMITS=1 OUTPUTDIR=$OUTPUTDIR/slider \
  python src/do_scatterplots.py $DATADIR1/picks_for_slider.tsv
python src/do_scatterplots.py $DATADIR1/picks_for_basal_w_color.tsv

echo done
