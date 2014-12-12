#import os
from os import path, environ
from shutil import copy
import os
import os.path
import argparse
import logging
from django.core.exceptions import ObjectDoesNotExist
from django.conf import settings

import sys
_mydir = path.abspath(path.dirname(__file__))
_djangodir = path.normpath(path.join(_mydir, '../django'))
sys.path.insert(0, _djangodir)
import chdir as cd
with cd.chdir(_djangodir):
    environ.setdefault('DJANGO_SETTINGS_MODULE', 'hmslincs_server.settings')
del _mydir, _djangodir

import import_utils as util
from db.models import SmallMolecule, SmallMoleculeBatch, Cell, Protein, DataSet,\
    Library, AttachedFile, CellBatch

__version__ = "$Revision: 24d02504e664 $"
# $Source$

# ---------------------------------------------------------------------------

import setparams as _sg
_params = dict(
    VERBOSE = False,
    APPNAME = 'db',
)
_sg.setparams(_params)
del _sg, _params

# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)

def main(path,):
    """
    Record the attached file for the entity, and move the attached files to the right directory
    """
    logger.info("read the attached file")
    

parser = argparse.ArgumentParser(description='Copy attached files to the deployed directory, and add an attached file record to the database')
parser.add_argument('-f', action='store', dest='inputFile',
                    metavar='FILE', required=True,
                    help='attached file path')

parser.add_argument('-rp', action='store', dest='relativePath',
                    metavar='RELPATH', required=False,
                    help='if set, relative path of this file from the [STATIC_AUTHENTICATED_FILE_DIR:'+ settings.STATIC_AUTHENTICATED_FILE_DIR + '] directory')

parser.add_argument('-dp', action='store', dest='deployPath',
                    metavar='DEPLOYPATH', required=False,
                    help='if set, path to "deploy" (copy) to, otherwise, set to [STATIC_AUTHENTICATED_FILE_DIR:'+ settings.STATIC_AUTHENTICATED_FILE_DIR + '] directory')

parser.add_argument('-d', action='store', dest='description',
                    metavar='DESCRIPTION', required=False,
                    help='description for the end user')

parser.add_argument('-fi', action='store', dest='facilityId',
                    metavar='FACILITY_ID', required=True,
                    help='facility ID of the entity to attach this file to')

parser.add_argument('-si', action='store', dest='saltId',
                    metavar='SALT_ID', required=False,
                    help='Salt ID (must be used with facility id')

parser.add_argument('-bi', action='store', dest='batchId',
                    metavar='BATCH_ID', required=False,
                    help='Batch ID (must be used with facility/salt id')

parser.add_argument('-ft', action='store', dest='fileType',
                    metavar='FILE_TYPE', required=True,
                    help='designate a descriptive one word file type classification')

parser.add_argument('-fd', action='store', dest='fileDate',
                    metavar='FILE_DATE', required=True,
                    help='the date to record for the file')

parser.add_argument('-r', '--restricted', action='store_true', dest='isRestricted',
                    required=False,
                    help='set to restrict access to authorized users only')

parser.add_argument('-v', '--verbose', dest='verbose', action='count',
                help="Increase verbosity (specify multiple times for more)")    

if __name__ == "__main__":
    args = parser.parse_args()
    if(args.inputFile is None):
        parser.print_help();
        parser.exit(0, "\nMust define the FILE param.\n")

    log_level = logging.WARNING # default
    if args.verbose == 1:
        log_level = logging.INFO
    elif args.verbose >= 2:
        log_level = logging.DEBUG
    # NOTE this doesn't work because the config is being set by the included settings.py, and you can only set the config once
    logging.basicConfig(level=log_level, format='%(msecs)d:%(module)s:%(lineno)d:%(levelname)s: %(message)s')        
    logger.setLevel(log_level)

    facilityId = util.int_converter(args.facilityId); # NOTE: TODO: we have made facility id a text field in the DB
    inputFile = args.inputFile
    relativePath = args.relativePath

    print 'importing ', inputFile
    if(not path.exists(inputFile)):
        raise Exception(str(('file does not exist',inputFile)))
    else:
        # deploy the file
        filename = path.basename(inputFile)
        deploy_dir = settings.STATIC_AUTHENTICATED_FILE_DIR
        if(args.deployPath):
            deploy_dir = args.deployPath
        if not path.isdir(deploy_dir):
            raise Exception(str(('no such deploy directory, please create it', deploy_dir)))
        deployed_path = path.join(deploy_dir, filename)
        if(relativePath):
            deployed_path = path.join(deploy_dir, relativePath)
            
        logger.info(str(('deploy to', deployed_path, os.path.join(deployed_path,filename))))
        if( path.exists(deployed_path)):
            os.remove(deployed_path)
        copy(inputFile,deployed_path)
#        os.system ("copy %s %s" % (inputFile, deployed_path ))
        if not path.isfile (deployed_path):
            raise Exception(str(('could not deploy to', deployed_path)))
        else:
            logger.info(str(('successfully deployed to', deployed_path)))
            
    filename = path.basename(inputFile)
    attachedFile = AttachedFile(filename=filename,facility_id_for=facilityId, relative_path=relativePath, is_restricted=args.isRestricted)
    # lookup the Entity
    
    if(facilityId <= 30000 ): # SM or Screen
        logger.info('look for the small molecule for:' + str(facilityId))
        saltId = util.int_converter(args.saltId)
        if(saltId is not None):
            logger.info('look for the small molecule for saltId ' + str(saltId))
            try:
                sm = SmallMolecule(facility_id=facilityId, salt_id=saltId)
                attachedFile.salt_id_for=saltId
                batchId = util.int_converter(args.batchId)
                if(batchId is not None):
                    logger.info('look for the batch Id: ' + str(batchId))
                    attachedFile.batch_id_for=batchId
                    try:
                        smb = SmallMoleculeBatch(smallmolecule=sm,facility_batch_id=batchId)
                    except ObjectDoesNotExist,e:
                        logger.error(str(('No such SmallMoleculeBatch found', facilityId, saltId, batchId, e)))
                        raise e
            except ObjectDoesNotExist,e:
                logger.error(str(('No such SmallMolecule found', facilityId, saltId, e)))
                raise e
                    
        else: # it's a screen/dataset
            try:
                ds = DataSet.objects.get(facility_id=facilityId)
            except ObjectDoesNotExist,e:
                logger.error(str(('No such Study DataSet found', facilityId, saltId, e)))
                raise e
    elif(facilityId <=60000): # Cell
        try:
            cell = Cell.objects.get(facility_id=facilityId)
            batchId = util.int_converter(args.batchId)
            if(batchId is not None):
                logger.info('look for the batch Id: ' + str(batchId))
                attachedFile.batch_id_for=batchId
                try:
                    cb = CellBatch(cell=cell,batch_id=batchId)
                except ObjectDoesNotExist,e:
                    logger.error(str(('No such Cell batch found', facilityId, batchId, e)))
                    raise e
        except ObjectDoesNotExist,e:
            logger.error(str(('No such Cell found', facilityId, saltId, e)))
            raise e
         
    elif(facilityId <=300000): # Protein 
        try:
            ds = DataSet.objects.get(facility_id=facilityId)
        except ObjectDoesNotExist,e:
            logger.error(str(('No such Study DataSet found', facilityId, saltId, e)))
            raise e
    elif(facilityId <=400000): # Study 
        try:
            ds = DataSet.objects.get(facility_id=facilityId)
        except ObjectDoesNotExist,e:
            logger.error(str(('No such Study DataSet found', facilityId, saltId, e)))
            raise e
    else:
        raise Exception(str(('unknown facility id', facilityId)))
        
    attachedFile.file_type = args.fileType
    attachedFile.description = args.description
    attachedFile.file_date = util.date_converter(args.fileDate)
    
    attachedFile.save()