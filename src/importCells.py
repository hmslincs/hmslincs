"""
populate the database Cell Data
"""

import os.path as op
from django.utils import timezone
import script_path as sp
from example.models import Cell
import xls2py as xl
import argparse


class ArbitraryGrouping(object):
    
    def populate(self,inputFile):
            
        Cell.objects.all().delete()
        wb = xl.Workbook(inputFile)
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
            sm = Cell(facility_id=facilityId, pub_date=timezone.now())
            sm.save()


parser = argparse.ArgumentParser(description='Import Cell file')
parser.add_argument('-f', action='store', dest='inputFile',
                    metavar='FILE', required=True,
                    help='input file path')
    
if __name__ == "__main__":
    args = parser.parse_args()
    if(args.inputFile is None):
        parser.print_help();
        parser.exit(0, "\nMust define the FILE param.\n")
    ArbitraryGrouping().populate(args.inputFile)
    