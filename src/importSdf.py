"""
populate the database Small Molecule Data
"""

import os.path as op
from django.utils import timezone
import script_path as sp
from example.models import SmallMolecule
import argparse


class ArbitraryGrouping(object):
    
    def populate(self,inputFile,clearData):
            
        if(clearData):
            SmallMolecule.objects.all().delete()
        
        print("processing: %s " % inputFile)
        names = ["(R)- Roscovitine","ALW-II-38-3","ALW-II-49-7","AT-7519","AV-951","AZD7762","AZD8055","BAY-439006","CP466722","Flavopiridol"]
        alternate_names = ["(R)- Roscovitine, CYC202, Seliciclib" , "ALW-II-38-3" , "ALW-II-49-7" , "AT-7519" , "AV-951, Tivozanib" , "AZD7762" , "AZD8055" , "BAY-439006, Sorafenib" , "CP466722" , "Flavopiridol, Alvocidib, HMR-1275, L868275"]

        for i in range(200):
            facilityId = 'HMLSL' + str(1000 + i)
            sm = SmallMolecule( facility_id=facilityId,
                                name=names[i%10]+str(i),
                                alternate_names=alternate_names[i%10]+str(i),
                                salt_id = 100+i,
                                smiles='xxx'+str(i),
                                pub_date=timezone.now())
            sm.save()

parser = argparse.ArgumentParser(description='Import SDF file')
parser.add_argument('-f', action='store', dest='inputFile',
                    metavar='FILE', required=True,
                    help='input file path')
parser.add_argument('--delete_existing', action='store_true',dest='deleteExisting')
    
if __name__ == "__main__":
    args = parser.parse_args()
    if(args.inputFile is None):
        parser.print_help();
        parser.exit(0, "\nMust define the FILE param.\n")
    ArbitraryGrouping().populate(args.inputFile, args.deleteExisting)
    