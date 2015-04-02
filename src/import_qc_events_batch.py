
import os.path
import sys
import argparse
import xls2py as x2p
import re
from datetime import date
import logging

import init_utils as iu
import import_utils as util
from db.models import SmallMolecule,SmallMoleculeBatch,QCEvent,QCAttachedFile
from django.db import transaction
from django.conf import settings

__version__ = "$Revision: 24d02504e664 $"
# $Source$

# ---------------------------------------------------------------------------

import setparams as _sg
import os
from shutil import copy
_params = dict(
    VERBOSE = False,
    APPNAME = 'db',
)
_sg.setparams(_params)
del _sg, _params

# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)

@transaction.commit_on_success
def main(import_file,file_directory,deploy_dir):
    """
    Read in the qc events for batches 
    - version 1 - for small molecule batches
    """
    sheet_name = 'Sheet1'
    start_row = 0
    sheet = iu.readtable([import_file, sheet_name, start_row]) # Note, skipping the header row by default

    properties = ('model_field','required','default','converter')
    column_definitions = { 
              'facility_id': ('facility_id_for',True,None, lambda x: util.convertdata(x,int)),
              'salt_id': ('salt_id_for',True,None, lambda x: util.convertdata(x,int)),
              'batch_id':('batch_id_for',True,None, lambda x: util.convertdata(x,int)),
              'date': ('date',True,None,util.date_converter),
              'outcome': ('outcome',True),
              'comment': 'comment',
              'file1': 'file1',
              'file1_type': 'file1_type',
              'file2': 'file2',
              'file2_type': 'file2_type',
              'file3': 'file3',
              'file3_type':'file3_type',
              }
    # convert the labels to fleshed out dict's, with strategies for optional, default and converter
    column_definitions = util.fill_in_column_definitions(properties,column_definitions)
    
    # create a dict mapping the column ordinal to the proper column definition dict
    cols = util.find_columns(column_definitions, sheet.labels)
    
    rows = 0    
    logger.debug(str(('cols: ' , cols)))
    for row in sheet:
        r = util.make_row(row)
        # store each row in a dict
        _dict = {}
        for i,value in enumerate(r):
            if i not in cols: continue
            properties = cols[i]

            logger.debug(str(('read col: ', i, ', ', properties)))
            required = properties['required']
            default = properties['default']
            converter = properties['converter']
            model_field = properties['model_field']

            logger.debug(str(('raw value', value)))
            if(converter != None):
                value = converter(value)
            if(value == None ):
                if( default != None ):
                    value = default
            if(value == None and  required == True):
                raise Exception('Field is required: %s, record: %d' % (properties['column_label'],rows))
            logger.debug(str(('model_field: ' , model_field, ', value: ', value)))
            _dict[model_field] = value

        logger.debug(str(('dict: ', _dict)))
        sm_lookup = {'facility_id':_dict['facility_id_for'],
                     'salt_id':_dict['salt_id_for'] }
        sm = None
        smb = None
        try:
            sm = SmallMolecule.objects.get(**sm_lookup)
        except (ObjectDoesNotExist,MultipleObjectsReturned) as e:
            logger.error(str(('Entity not found',sm_lookup,'row', rows+start_row, e)))
            raise
        try:
            smb = SmallMoleculeBatch.objects.get(
                smallmolecule=sm, 
                facility_batch_id=_dict['batch_id_for'])
        except (ObjectDoesNotExist,MultipleObjectsReturned) as e:
            logger.error(str(('Batch Entity not found',sm_lookup,
                _dict['facility_batch_id'],'row', rows+start_row, e)))
            raise
        
        files_to_attach = []
        for i in range(10):
            filenameProp = 'file%s'%i;
            filetypeProp = '%s_type'%filenameProp
            if _dict.get(filenameProp, None):
                if not _dict.get(filetypeProp,None):
                    raise Exception(str(('file_type is required',filetypeProp,
                        'row',rows+start_row)))
                fileprop = _dict[filenameProp]
                filepath = os.path.join(file_directory,fileprop)
                if not os.path.exists(filepath):
                    raise Exception(str(('file does not exist:',filepath,'row',
                        rows+start_row)))
                filename = os.path.basename(filepath)
                relative_path = fileprop[:fileprop.index(filename)]
                
                # Move the file
                dest_dir = deploy_dir
                if not dest_dir:
                    dest_dir = settings.STATIC_AUTHENTICATED_FILE_DIR
                if not os.path.isdir(dest_dir):
                    raise Exception(str(('no such deploy directory, please create it', dest_dir)))
                if relative_path:
                    dest_dir = os.path.join(dest_dir, relative_path)
                    if not os.path.exists(dest_dir):
                        os.makedirs(dest_dir)
                deployed_path = os.path.join(dest_dir, filename)
                    
                logger.debug(str(('deploy',filepath, deployed_path)))
                if os.path.exists(deployed_path):
                    os.remove(deployed_path)
                copy(filepath,deployed_path)
                if not os.path.isfile (deployed_path):
                    raise Exception(str(('could not deploy to', deployed_path)))
                else:
                    logger.debug(str(('successfully deployed to', deployed_path)))
                
                files_to_attach.append((filename,relative_path,_dict[filetypeProp]))
        
        initializer = None
        try:
            # create the qc record
            initializer = {key:_dict[key] for key in 
                ['facility_id_for','salt_id_for','batch_id_for','outcome','comment','date']}
            qc_event = QCEvent(**initializer)
            qc_event.save()
            logger.debug(str(('saved', qc_event)))
            
            # create attached file records
            for (filename,relative_path,file_type) in files_to_attach:
                initializer = {
                    'qc_event':qc_event,
                    'filename':filename,
                    'relative_path':relative_path,
                    'file_type':file_type }
                qc_attached_file = QCAttachedFile(**initializer)
                qc_attached_file.save()
                logger.debug(str(('created qc attached file', qc_attached_file)))
            
            rows += 1
            
        except Exception, e:
            logger.error(str(("Invalid initializer: ", initializer, 'row', 
                rows+start_row+2, e)))
            raise
        
    print "Rows read: ", rows
    
    

parser = argparse.ArgumentParser(description='Import file')
parser.add_argument('-f', action='store', dest='inputFile',
                    metavar='FILE', required=True,
                    help='input file path')

parser.add_argument('-dp', action='store', dest='deployPath',
                    metavar='DEPLOYPATH', required=False,
                    help=('if set, path to "deploy" (copy) to, otherwise, '
                        'set to [STATIC_AUTHENTICATED_FILE_DIR:')
                        + settings.STATIC_AUTHENTICATED_FILE_DIR + '] directory')


parser.add_argument('-fd', action='store', dest='attachedFilesDirectory',
                    metavar='FILES_DIRECTORY', required=True,
                    help='the directory containing the attached files')

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
    logging.basicConfig(level=log_level, 
        format='%(msecs)d:%(module)s:%(lineno)d:%(levelname)s: %(message)s')        

    print 'importing ', args.inputFile
    main(args.inputFile, args.attachedFilesDirectory, args.deployPath)
