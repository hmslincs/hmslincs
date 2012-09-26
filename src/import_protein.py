import sys
import argparse
import xls2py as x2p
import re
from datetime import date

import init_utils as iu
import import_utils as util
from example.models import Protein

__version__ = "$Revision: 24d02504e664 $"
# $Source$

# ---------------------------------------------------------------------------

import setparams as _sg
_params = dict(
    VERBOSE = False,
    APPNAME = 'example',
)
_sg.setparams(_params)
del _sg, _params

# ---------------------------------------------------------------------------

def main(path):
    """
    Read in the Protein
    """
    sheet_name = 'HMS-LINCS Kinases'
    labels = { 'PP_Name':'name', 
              'PP_LINCS_ID':'lincs_id', 
              'PP_UniProt_ID':'uniprot_id', 
              'PP_Alternate_Name':'alternate_name',
              'PP_Provider':'provider',
              'PP_Provider_Catalog_ID':'provider_catalog_id',
              'PP_Batch_ID':'batch_id', 
              'PP_Amino_Acid_Sequence':'amino_acid_sequence',
              'PP_Gene_Symbol':'gene_symbol', 
              'PP_Gene_ID':'gene_id',
              'PP_Protein_Source':'protein_source',
              'PP_Protein_Form':'protein_form', 
              'PP_Protein_Purity':'protein_purity', 
              'PP_Protein_Complex':'protein_complex', 
              'PP_Isoform':'isoform', 
              'PP_Protein_Type':'protein_type', 
              'PP_Source_Organism':'source_organism', 
              'PP_Reference':'reference'}
    
    converters = { 'lincs_id': lambda x: x[x.index('HMSL')+4:] }    
    
    sheet = iu.readtable([path, sheet_name, 1]) # Note, skipping the header row by default
    cols = {}
    # first put the label row in (it contains the worksheet column, and its unique)
    print 'labels: ', sheet.labels
    for i,label in enumerate(sheet.labels):
        if label in labels:
            cols[i] = labels[label]
        else:
            print 'Note: column label not found:', label
            #raise
            
    rows = 0    
    i = 0
    
    print 'cols: ' , cols
    proteins = {}
    for row in sheet:
        r = util.make_row(row)
        dict = {}
        for i,value in enumerate(r):
            if i not in cols: continue
            if cols[i] in converters:
                value = converters[cols[i]](value)
            dict[cols[i]]= value
        try:
            protein = Protein(**dict)
            protein.save()
            rows += 1
        except Exception, e:
            print "Invalid Protein, name: ", r[0]
            raise
        
    print "Rows read: ", rows
    
    

parser = argparse.ArgumentParser(description='Import file')
parser.add_argument('-f', action='store', dest='inputFile',
                    metavar='FILE', required=True,
                    help='input file path')
    
if __name__ == "__main__":
    args = parser.parse_args()
    if(args.inputFile is None):
        parser.print_help();
        parser.exit(0, "\nMust define the FILE param.\n")
        
    print 'importing ', args.inputFile
    main(args.inputFile)