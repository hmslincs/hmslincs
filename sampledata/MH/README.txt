The files

  sampledata/MH/picks_for_basal.tsv
  sampledata/MH/picks_for_responses.tsv
  sampledata/MH/picks_for_slider.tsv

are, basically, subsets of the data in the files

  sampledata/MH/data_Basal levels_raw.tsv
  sampledata/MH/data_HTM (all GF), mean_foldchange.tsv
  sampledata/MH/data_HTM (GF)_foldchange.tsv

respectively, consisting of only those columns required to generate
the scatterplots selected by MH for the NUI.  These are:

  Basal levels
  ·         ErbB2 vs pErbB2
  ·         AKT vs pAKT
  ·         pErbB2 vs pAKT
  ·         pErbB2 vs pErbB3
  ·         ErbB3 vs pErbB3

  Ligand response:
  ·         pERK [FGF-1] vs pERK [FGF-2]
  ·         pAKT [EGF] vs pERK [EGF]
  ·         pERK [EGF] vs pERK [BTC]
  ·         pERK [EGF] vs pERK [HRG]
  ·         pAKT [IGF-1] vs pERK [IGF-1]
  ·         pAKT [IGF-1] vs pERK [FGF-1]

  slider: use the time points for
  ·         pAKT [IGF-1] vs pERK [FGF-1]

The files

  sampledata/MH/picks_for_basal.tsv
  sampledata/MH/picks_for_responses.tsv
  sampledata/MH/picks_for_slider.tsv

were generated with the following incantations

 % gjoin -t$'\t' \
     sampledata/MH/kluge.tsv \
     <( cut -f 1,3,5,6,29,31,32 'sampledata/MH/data_Basal levels_raw.tsv' ) \
   > sampledata/MH/picks_for_basal.tsv
 % gjoin -t$'\t' \
     sampledata/MH/kluge.tsv \
     <( cut -f 1,2,4,5,7,12,13,17,22 'sampledata/MH/data_HTM (all GF), mean_foldchange.tsv' ) \
   > sampledata/MH/picks_for_responses.tsv
 % gjoin -t$'\t' \
     sampledata/MH/kluge.tsv \
     <( cut -f 1,67,68,69,127,128,129 'sampledata/MH/data_HTM (GF)_foldchange.tsv' ) \
   > sampledata/MH/picks_for_slider.tsv

...where the file sampledata/MH/kluge.tsv was in turn generated with:

 % gjoin -o 0,1.2,2.2 -a1 -a2 -e '0.0' -t$'\t' \
     <( cut -f 1,2 'sampledata/MH/data_HTM (all GF), mean_raw(1).txt' ) \
     <( cut -f 1,3 'sampledata/MH/data_HTM (GF)_foldchange.tsv' ) \
   > sampledata/MH/kluge.tsv

NOTE that the last gjoin command results in some output lines where
the second column (GI50(AG1478)) is 0.0, which is incorrect, but is
meant as a placeholder:

  % nl sampledata/MH/kluge.tsv | grep -e GI50 -e '0.0'
       1	.	GI50(AG1478)	Subtype
       2	184B5	0.0	TNBC
      13	HCC1500	0.0	HR+
      14	HCC1569	0.0	HER2amp
      21	Hs 578T	0.0	TNBC
      22	MCF 10A	0.0	TNBC
      23	MCF 10F	0.0	TNBC
      24	MCF-12A	0.0	TNBC
      31	MDA-MB-415	0.0	HR+
      39	ZR-75-30	0.0	HER2amp

To generate the pre-cooked scatterplots, run

  % python src/do_scatterplots.py sampledata/MH/picks_for_basal.tsv
  % python src/do_scatterplots.py sampledata/MH/picks_for_responses.tsv
  % python src/do_scatterplots.py sampledata/MH/picks_for_slider.tsv
