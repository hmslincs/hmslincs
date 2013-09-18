# the output of this module is the postgres sql that will create the full text indexes
import sys
import init_utils as iu

from db.models import Cell, DataSet, SmallMolecule, Library, Protein, FieldInformation,\
    Antibody, OtherReagent
from django.db import models

# ---------------------------------------------------------------------------

import setparams as _sg
_params = dict(
    VERBOSE = False,
    APPNAME = 'db',
)
_sg.setparams(_params)
del _sg, _params

# ---------------------------------------------------------------------------

def main():
    print '/** creating index definitions for Cell **/'
    createTableIndex('db_cell', Cell)
    print '/** creating index definitions for Small Molecule **/'
    createTableIndex('db_smallmolecule', SmallMolecule)
    print '/** creating index definitions for DataSet **/'
    createTableIndex('db_dataset', DataSet)
    print '/** creating index definitions for Library **/'
    createTableIndex('db_library', Library)
    print '/** creating index definitions for Protein **/'
    createTableIndex('db_protein', Protein)
    print '/** creating index definitions for Antibody **/'
    createTableIndex('db_antibody', Antibody)
    print '/** creating index definitions for OtherReagent **/'
    createTableIndex('db_otherreagent', OtherReagent)
    print "\n"

def ignore_errors(yn):
    print '\\%s ON_ERROR_STOP' % ('unset' if yn else 'set')

def createTableIndex(tableName, model):
    index = '%s_index' % tableName
    qualifier = 'cascade'
    kws = dict(locals())

    ignore_errors(True)
    print ('alter table %(tableName)s '
           'add column search_vector tsvector;' % kws)
    ignore_errors(False)

    createTableIndexTrigger(tableName, model)
    createTableIndexUpdate(tableName, model)
    print ('drop index if exists %(index)s %(qualifier)s;' % kws)
    print ('create index %(index)s on %(tableName)s '
           'using gin(search_vector);\n\n' % kws)


def textfields(model):
    return ['"%s"' % x.field for x in getTextTypeFields(model)]
    

def createTableIndexTrigger(tableName, model):
    trigger = 'tsvectorupdate'
    qualifier = 'cascade'
    fields = ', '.join(textfields(model))
    kws = dict(locals())

    print ('drop trigger if exists %(trigger)s on '
           '%(tableName)s %(qualifier)s;' % kws)

    print ('create trigger %(trigger)s '
           'BEFORE INSERT OR UPDATE ON %(tableName)s '
           'FOR EACH ROW EXECUTE PROCEDURE '
           "tsvector_update_trigger(search_vector, 'pg_catalog.english', "
           '%(fields)s);' % kws)


def createTableIndexUpdate(tableName, model):
    fields = " || ' ' || ".join(["coalesce(%s, '')" % f
                                 for f in textfields(model)])
    kws = dict(locals())

    print ('update %(tableName)s set search_vector = '
           "to_tsvector('pg_catalog.english', %(fields)s);" % kws)

    # 'update ' + tableName + \
    #     " set search_vector = to_tsvector('pg_catalog.english'," + \
    #     " || ' ' || ".join(map( lambda x: "coalesce("+x.field+",'') ",
    #                             getTextTypeFields(model))), ");" 

    
    
def getTextTypeFields(model):
    # Only text or char fields considered, must add numeric fields manually
    # return filter(lambda x: (isinstance(x, models.CharField) or
    #               isinstance(x, models.TextField), tuple(model._meta.fields)))
    return FieldInformation.manager.get_search_fields(model)

if __name__ == "__main__":
    main()
