"""
populate the database with dummy data
"""

import os.path as op
from django.utils import timezone
import script_path as sp
from example.models import SmallMolecule
import xls2py as xl
import argparse

DATADIR = op.join(sp.script_dir(), '..', 'sampledata')

class ArbitraryGrouping:
    
    def populate(self,inputFile):
            
        SmallMolecule.objects.all().delete()
        wb = xl.Workbook(op.join(DATADIR, inputFile))
        print("processing: %s ", inputFile)
        
        for sheet in wb:
            if sheet.name == 'HMS-LINCS cell line metadata':
                break
        else:
            raise Exception('')
        print("reading: %s", sheet.name)
        rows = iter(sheet)
        headers = [next(rows) for _ in (0, 1)]
        for row in rows:
            facilityId = str(list(row)[0])
            print("processing: " + facilityId)
            sm = SmallMolecule(facility_id=facilityId, pub_date=timezone.now())
            sm.save()


parser = argparse.ArgumentParser(description='Import Small Molecule file')
parser.add_argument('-f', action='store', dest='inputFile',
                    metavar='FILE', required=True,
                    help='input file path')
    
if __name__ == "__main__":
    args = parser.parse_args()
    if(args.inputFile is None):
        parser.print_help();
        parser.exit(0, "\nMust define the FILE param.\n")
    ArbitraryGrouping().populate(args.inputFile)
    