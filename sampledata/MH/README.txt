Author: Gabriel F. Berriz <gabriel_berriz@hms.harvard.edu>
Date:   Wed Oct 24 16:40:54 2012 -0400

To populate the directory

  django/responses/static/responses/img

run the following:

  src/do_scatterplots.sh

For the specifics of the build, see the src/do_scatterplots.sh source.

The rest of this README gives some additional details that are not
deducible from the src/do_scatterplots.sh source.

As part of the build, src/do_scatterplots.sh generates a set of input
files containing only the subset of MH's data required to generate the
scatterplots selected by MH for the NUI.  These scatterplots are:

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

  slider: use the mean ligand response and time points for
  ·         pAKT [IGF-1] vs pERK [FGF-1]

Note that the file sampledata/MH/col_1_3.tsv currently includes some
nan values in the "GI50(AG1478)" column; they are meant as temporary
placeholders until we get the correct values from MH:

  % nl sampledata/MH/col_1_3.tsv | grep -e GI50 -e nan
       1	.	GI50(AG1478)	Subtype
       2	184B5	nan	TNBC
      13	HCC1500	nan	HR+
      14	HCC1569	nan	HER2amp
      21	Hs 578T	nan	TNBC
      22	MCF 10A	nan	TNBC
      23	MCF 10F	nan	TNBC
      24	MCF-12A	nan	TNBC
      31	MDA-MB-415	nan	HR+
      39	ZR-75-30	nan	HER2amp
