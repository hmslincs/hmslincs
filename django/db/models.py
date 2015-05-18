from collections import OrderedDict
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
from django.db import models
from django.utils import timezone
import logging
import re
import types
from django.forms.models import model_to_dict

logger = logging.getLogger(__name__)

# *temporary* shorthand, to make the following declarations more visually
# digestible
_CHAR       = models.CharField
_INTEGER    = models.IntegerField
_TEXT       = models.TextField

_FACILITY_ID_LENGTH = 15
_SALT_ID_LENGTH = 10
_BATCH_ID_LENGTH = 5

# the only purpose for the two temporary shorthand definitions
# below is to make clear how we are translating the SQL NULL and
# NOT NULL qualifiers to Django's representation (in fact, for
# both the null and blank keywords, the default value is False, so
# the **_NOTNULLSTR qualifier below is always unnecessary, and all
# the **_NULLOKSTR qualifiers could be replaced with the
# blank=True spec); incidentally, the setting we're using for
# _NULLOKSTR is the one recommended in the Django docs to
# correspond to NULL-qualified string-type fields in SQL schemas
# (e.g. CHAR and TEXT); note that for such _NULLOKSTR-qualified
# fields, Django will automatically translate an absence of data
# as an empty string, and *not* as an SQL NULL value.
_NOTNULLSTR = dict(null=False, blank=False)
_NULLOKSTR  = dict(null=True, blank=False)
# to follow the opposite convention, uncomment the following

# definition
# _NULLOKSTR  = dict(null=False, blank=True)

class FieldInformationLookupException(Exception):
    ''' Signals missing field information
    '''
    pass

class FieldsManager(models.Manager):
    
    fieldinformation_map = {}

    # this is how you override a Manager's base QuerySet
    def get_query_set(self):
        return super(FieldsManager, self).get_query_set()
    def get_field_hash(self, table_or_queryset_name ):
        
        logger.info(str(('getting', table_or_queryset_name)))
        fieldmetas = self.get_table_fields(table_or_queryset_name);
        # TODO: note that fi.field is the fieldname and is unique for this scope.
        #  (rework as in iccbl-lims)
        table_fields = dict(zip([x.field for x in fieldmetas],  fieldmetas ))    
        
        fieldmetas = self.get_query_set().filter(queryset=table_or_queryset_name)
        queryset_fields = dict(zip([x.field for x in fieldmetas],  fieldmetas ))    
        table_fields.update(queryset_fields)
        
        return table_fields
    
    def get_table_fields(self,table):
        """
        return the FieldInformation objects for the table, or None if not defined
        """
        return self.get_query_set().filter(table=table)
    
    def get_column_fieldinformation_by_priority(
            self,field_or_alias,tables_by_priority):
        """
        searches for the FieldInformation using the tables in the 
        "tables_by_priority", in the order given.
        raises a FieldInformationLookupException if not found in any of them.
        @param tables_by_priority: a sequence of table names.  
            If an empty string is given, then a search through all fields having
            no table name.  
        """
        if isinstance(tables_by_priority, basestring): 
            tables_by_priority = (tables_by_priority,)

        for i,table in enumerate(tables_by_priority):
            val = None
            if(table == ''):
                val = self.get_column_fieldinformation(field_or_alias)
            else:
                val = self.get_column_fieldinformation(field_or_alias, table)
            if val:
                return val
            else:
                if( i+1 == len(tables_by_priority)): 
                    raise FieldInformationLookupException(
                        str(('Fieldinformation not found', 
                             field_or_alias,tables_by_priority )))
                
    def get_column_fieldinformation(self,field_or_alias,table_or_queryset=None):
        '''
        Cache and return the FieldInformation object for the column, or None if
        not defined
        '''
        
        table_hash = None
        if table_or_queryset and table_or_queryset in self.fieldinformation_map:
            table_hash = self.fieldinformation_map[table_or_queryset]
        elif '' in self.fieldinformation_map:
            table_hash = self.fieldinformation_map['']
        
        if not table_hash:
            table_hash = {}
            self.fieldinformation_map[table_or_queryset] = table_hash
        
        if not field_or_alias in table_hash or not table_hash[field_or_alias]:
            logger.info(str(('finding', table_or_queryset,  field_or_alias)))
            val = self.get_column_fieldinformation_uncached(
                field_or_alias, table_or_queryset)
            table_hash[field_or_alias] = val
        
        return table_hash[field_or_alias]

    def get_column_fieldinformation_uncached(
            self,field_or_alias,table_or_queryset=None):
        """
        @return the FieldInformation object for the column, or None if a 
            FieldInformation entry is not found for the table_or_queryset
        """
        fi = None
        if(table_or_queryset == None):
            try:
                return self.get_query_set().get(
                    alias=field_or_alias, table=None, queryset=None);
            except (ObjectDoesNotExist,MultipleObjectsReturned) as e:
                logger.debug(str((
                    'No field information for the alias: ',field_or_alias,e)))
            try:
                return self.get_query_set().get(
                    field=field_or_alias, table=None, queryset=None)
            except (ObjectDoesNotExist,MultipleObjectsReturned) as e:
                return None
        else:
            try:
                fi = self.get_query_set().get(
                    queryset=table_or_queryset, field=field_or_alias)
                return fi
            except (ObjectDoesNotExist,MultipleObjectsReturned) as e:
                logger.debug(str((
                    'No field information for the queryset,field: ',
                    table_or_queryset,field_or_alias, e)))
            try:
                fi = self.get_query_set().get(
                    queryset=table_or_queryset, alias=field_or_alias)
                return fi
            except (ObjectDoesNotExist,MultipleObjectsReturned) as e:
                logger.debug(str((
                    'No field information for the queryset,alias: ',
                    table_or_queryset,field_or_alias, e)))
            
            try:
                return self.get_query_set().get(
                    table=table_or_queryset, field=field_or_alias)
            except (ObjectDoesNotExist,MultipleObjectsReturned) as e:
                logger.debug(str((
                    'No field information for the table,field: ',
                    table_or_queryset,field_or_alias, e)))
            try:
                return self.get_query_set().get(
                    table=table_or_queryset, alias=field_or_alias)
            except (ObjectDoesNotExist,MultipleObjectsReturned) as e:
                return None
    
    def get_snippet_def(self,model_class): 
        db_table_name = model_class._meta.db_table   
        return (" || ' ' || ".join(map(
            lambda x: "coalesce(%s.%s,'') " % (db_table_name,x.field), 
            self.get_search_fields(model_class))))        
    
    def get_search_fields(self,model_class):
        """
        For the full text search, return the text searchable fields.
        """
        # Only text or char fields considered, must add numeric fields manually
        fields = map(lambda x: x.column, 
            filter(lambda x: isinstance(x, models.CharField) 
                or isinstance(x, models.TextField), tuple(model_class._meta.fields)))
        final_fields = []
        for fi in self.get_table_fields(model_class._meta.module_name):
            if(fi.use_for_search_index and fi.field in fields):  final_fields.append(fi)
        logger.debug(str(('get_search_fields for ',model_class,'returns',final_fields)))
        return final_fields

PUBCHEM_TYPE_IDENTITY = 'identity'
PUBCHEM_TYPE_SUBSTRUCTURE = 'substructure'
PUBCHEM_TYPES = ((PUBCHEM_TYPE_IDENTITY, PUBCHEM_TYPE_IDENTITY),
                 (PUBCHEM_TYPE_SUBSTRUCTURE, PUBCHEM_TYPE_SUBSTRUCTURE),)

class PubchemRequest(models.Model):
    sm_facility_ids = _TEXT(**_NULLOKSTR)
    smiles  = _TEXT( **_NULLOKSTR )
    molfile = _TEXT( **_NULLOKSTR )
    type    = _TEXT( null=False)
    pubchem_error_message = _TEXT( **_NULLOKSTR )
    error_message = _TEXT( **_NULLOKSTR )
#    type    = models.CharField(null=True, max_length=12,
#                               choices=PUBCHEM_TYPES,
#                               default=PUBCHEM_TYPE_IDENTITY)
    date_time_fullfilled = models.DateTimeField(null=True) 
    date_time_processing = models.DateTimeField(null=True) 
    date_time_requested = models.DateTimeField(null=False, default=timezone.now ) 
    # note, don't actually call the datetime.date.today function, since in this case it serves as a function pointer
    class Meta:
        unique_together = (('smiles', 'molfile','type'))    

    
    def __unicode__(self):
        return unicode((self.id, self.sm_facility_ids, self.smiles, 
                        'has_molfile' if self.molfile else 'no molfile',
                        self.error_message, self.pubchem_error_message, 
                        self.date_time_requested, self.date_time_fullfilled ))
    

# proposed class to capture all of the DWG information - and to map fields to these database tables
class FieldInformation(models.Model):
    manager                 = FieldsManager()
    objects                 = models.Manager() # default manager
    
    table                   = _CHAR(max_length=35, **_NULLOKSTR)
    field                   = _CHAR(max_length=35, **_NULLOKSTR)
    alias                   = _CHAR(max_length=35, **_NULLOKSTR)
    queryset                = _CHAR(max_length=35, **_NULLOKSTR)
    show_in_detail          = models.BooleanField(default=False, null=False) # Note: default=False are not set at the db level, only at the Db-api level
    show_in_list            = models.BooleanField(default=False, null=False) # Note: default=False are not set at the db level, only at the Db-api level
    show_as_extra_field     = models.BooleanField(default=False, null=False) # Note: default=False are not set at the db level, only at the Db-api level
    order                   = _INTEGER(null=False)
    is_lincs_field          = models.BooleanField(default=False, null=False) # Note: default=False are not set at the db level, only at the Db-api level
    use_for_search_index    = models.BooleanField(default=False) # Note: default=False are not set at the db level, only at the Db-api level
    dwg_version             = _CHAR(max_length=35,**_NULLOKSTR)
    unique_id               = _CHAR(max_length=35,null=False,unique=True)
    dwg_field_name              = _TEXT(**_NULLOKSTR) # LINCS name for display
    hms_field_name              = _TEXT(**_NULLOKSTR) # override the LINCS name for display
    related_to              = _TEXT(**_NULLOKSTR)
    description             = _TEXT(**_NULLOKSTR)
    importance              = _TEXT(**_NULLOKSTR)
    comments                = _TEXT(**_NULLOKSTR)
    ontologies              = _TEXT(**_NULLOKSTR)
    ontology_reference      = _TEXT(**_NULLOKSTR)
    additional_notes        = _TEXT(**_NULLOKSTR)
    is_unrestricted         = models.BooleanField(default=False, null=False)
    class Meta:
        unique_together = (('table', 'field','queryset'),('field','alias'))    
    def __unicode__(self):
        return unicode(str((self.table, self.field, self.unique_id, self.dwg_field_name, self.hms_field_name)))
    
    def get_field_name(self):
        if(self.hms_field_name != None):
            return self.hms_field_name
        else:
            return self.dwg_field_name

    def get_column_detail(self):
        """
        descriptive long name for the field: unique_id-field_name-description
        """
        s = ''
        if(self.dwg_field_name): 
            if(self.unique_id): s += self.unique_id
            if(len(s)>0): s += '-'
            s += self.dwg_field_name
        if(self.description):
            if(len(s)>0): s += ':'
            s+= self.description
        else:
            if(len(s)>0): s += ':'
            s+= self.get_verbose_name()
        return s
    
    def get_verbose_name(self):
        logger.debug(str(('create a verbose name for:', self)))
        
        field_name = re.sub(r'^[^_]{2}_','',self.get_field_name())
        field_name = field_name.replace('_',' ')
        field_name = field_name.strip()
        if(field_name != ''):
            #field_name = field_name.capitalize()
            #logger.info(str(('field_name:',field_name)))
            #field_name=field_name.replace('id','ID')
            #logger.info(str(('field_name:',field_name)))
            return field_name
        else:
            logger.error(str(('There is an issue with the field name: ',self.dwg_field_name,self.hms_field_name)))
            return self.field
    
    def get_dwg_name_hms_name(self):
        field_name = self.dwg_field_name        
        if not field_name or len(field_name)==0 : field_name = self.hms_field_name
        if not field_name or len(field_name)==0 :
            logger.error(str(('There is an issue with the field name: ',self.dwg_field_name,self.hms_field_name)))
            return self.field
        return field_name
    
    def get_camel_case_dwg_name(self):
        logger.debug(str(('create a camelCase name for:', self)))
        field_name = self.get_dwg_name_hms_name()
        field_name = field_name.strip().title()
        # TODO: convert a trailing "Id" to "ID"
        field_name = ''.join(['ID' if x.lower()=='id' else x for x in re.split(r'[_\s]+',field_name)])
        
        #field_name = re.sub(r'[_\s]+','',field_name)
        field_name = field_name[0].lower() + field_name[1:];
        #        logger.info(str(('created camel case name', field_name, 'for', self)))
        return field_name

class QCEvent(models.Model):
    
    facility_id_for = models.CharField(max_length=_FACILITY_ID_LENGTH, null=False)
    salt_id_for = models.CharField(max_length=_SALT_ID_LENGTH, null=True)
    batch_id_for =models.CharField(max_length=_BATCH_ID_LENGTH, null=True)
    outcome = models.CharField(max_length=36, null=False)
    date = models.DateField(null=False)
    comment = models.TextField(null=True)
    
    class Meta:
        unique_together = (
            'date','facility_id_for','salt_id_for','batch_id_for')  
    def __unicode__(self):
        return unicode(str((self.facility_id_for,self.salt_id_for,
            self.batch_id_for,self.outcome)))  

class QCAttachedFile(models.Model):
    
    qc_event                = models.ForeignKey('QCEvent', null=False)
    filename                = models.TextField(null=False)
    description             = models.TextField(null=True)
    relative_path           = models.TextField(null=True)
    file_type               = models.TextField(null=True)
    file_date               = models.DateField(null=True,blank=True)
    is_restricted           = models.BooleanField(default=False) 
    
    class Meta:
        unique_together = ('qc_event','filename')
        
    def __unicode__(self):
        return unicode(
            str((self.filename,self.relative_path,self.is_restricted, 
                self.file_type,self.description,self.file_date)))
        
class SmallMolecule(models.Model):
    
    nominal_target          = models.ForeignKey('Protein', null=True)
    facility_id             = _CHAR(max_length=_FACILITY_ID_LENGTH, **_NOTNULLSTR)
    salt_id                 = _CHAR(max_length=_SALT_ID_LENGTH, **_NOTNULLSTR)
    lincs_id                = _CHAR(max_length=15, **_NULLOKSTR)
    name                    = _TEXT(**_NOTNULLSTR) 
    alternative_names       = _TEXT(**_NULLOKSTR) 
    #facility_batch_id       = _INTEGER(null=True)
    molfile                 = _TEXT(**_NULLOKSTR)
    pubchem_cid             = _CHAR(max_length=15, **_NULLOKSTR)
    chembl_id               = _CHAR(max_length=15, **_NULLOKSTR)
    chebi_id                = _CHAR(max_length=15, **_NULLOKSTR)
    _inchi                   = _TEXT(db_column='inchi', **_NULLOKSTR)
    _inchi_key               = _TEXT(db_column='inchi_key', **_NULLOKSTR)
    _smiles                  = _TEXT( db_column='smiles', **_NULLOKSTR)
    software                = _TEXT(**_NULLOKSTR)
    # Following fields not listed for the canonical information in the DWG, but per HMS policy will be - sde4
    _molecular_mass          = models.DecimalField(db_column='molecular_mass', max_digits=8, decimal_places=2, null=True) # Note: FloatField results in a (postgres) double precision datatype - 8 bytes; approx 15 digits of decimal precision
    _molecular_formula       = _TEXT(db_column='molecular_formula', **_NULLOKSTR)
    # concentration          = _CHAR(max_length=35, **_NULLOKSTR)
    #plate                   = _INTEGER(null=True)
    #row                     = _CHAR(max_length=1, **_NULLOKSTR)
    #column                  = _INTEGER(null=True)
    #well_type               = _CHAR(max_length=35, **_NULLOKSTR)
    is_restricted           = models.BooleanField(default=False) # Note: default=False are not set at the db level, only at the Db-api level

    class Meta:
        unique_together = ('facility_id', 'salt_id')    
    def __unicode__(self):
        return unicode(str((self.facility_id, self.salt_id)))
      
    def get_molecular_formula(self, is_authenticated=False):
        if(not self.is_restricted or is_authenticated):
            return self._molecular_formula
        else:
            return 'restricted'
        
    def get_molecular_mass(self, is_authenticated=False):
        if(not self.is_restricted or is_authenticated):
            return self._molecular_mass
        else:
            return 'restricted'
        
    def get_inchi(self, is_authenticated=False):
        if(not self.is_restricted or is_authenticated):
            return self._inchi
        else:
            return 'restricted'

    def get_inchi_key(self, is_authenticated=False):
        if(not self.is_restricted or is_authenticated):
            return self._inchi_key
        else:
            return 'restricted'
        
    def get_smiles(self, is_authenticated=False):
        if(not self.is_restricted or is_authenticated):
            return self._smiles
        else:
            return 'restricted'
    
    def _get_facility_salt(self):
        "Returns the 'facilty_id-salt_id'"
        return '%s-%s' % (self.facility_id, self.salt_id)
    
    facility_salt = property(_get_facility_salt) 
    
    def _get_primary_name(self):
        "Returns the 'primary name'"
        return self.name.split(';')[0]
    
    primary_name = property(_get_primary_name)   
    
    @classmethod
    def get_snippet_def(cls):
        return FieldInformation.manager.get_snippet_def(cls)

CONCENTRATION_GL = 'g/L'
CONCENTRATION_MGML = 'mg/mL'
CONCENTRATION_WEIGHT_VOLUME_CHOICES = ((CONCENTRATION_GL,CONCENTRATION_GL),
                                       (CONCENTRATION_MGML,CONCENTRATION_MGML))

class SmallMoleculeBatch(models.Model):
    smallmolecule           = models.ForeignKey('SmallMolecule')
    facility_batch_id       = _CHAR(max_length=_BATCH_ID_LENGTH, **_NOTNULLSTR)
    provider                = _TEXT(**_NULLOKSTR)
    provider_catalog_id     = _CHAR(max_length=64, **_NULLOKSTR)
    provider_sample_id      = _CHAR(max_length=35, **_NULLOKSTR)
    chemical_synthesis_reference = _TEXT(**_NULLOKSTR)
    purity                  = _TEXT(**_NULLOKSTR)
    purity_method           = _TEXT(**_NULLOKSTR)
    aqueous_solubility      = models.DecimalField(max_digits=4, decimal_places=2, null=True)
    aqueous_solubility_unit = models.CharField(null=True,
                                               max_length=2,
                                      choices=CONCENTRATION_WEIGHT_VOLUME_CHOICES,
                                      default=CONCENTRATION_MGML)
    date_data_received      = models.DateField(null=True,blank=True)
    date_loaded             = models.DateField(null=True,blank=True)
    date_publicly_available = models.DateField(null=True,blank=True)
    date_updated            = models.DateField(null=True,blank=True)
    ## following fields probably not used with batch, per HMS policy - sde4
    inchi                   = _TEXT(**_NULLOKSTR)
    inchi_key               = _TEXT(**_NULLOKSTR)
    smiles                  = _TEXT(**_NULLOKSTR)

    def __unicode__(self):
        return unicode(str((self.smallmolecule,self.facility_batch_id)))
    class Meta:
        unique_together = ('smallmolecule', 'facility_batch_id',)    

    def _get_facility_salt_batch(self):
        "Returns the 'facilty_id-salt_id'"
        return '%s-%s' % (self.smallmolecule.facility_salt, self.facility_batch_id)
    
    facility_salt_batch = property(_get_facility_salt_batch)    

class Cell(models.Model):
    facility_id = models.CharField(max_length=_FACILITY_ID_LENGTH, unique=True, null=False)
    name = models.CharField(max_length=35, unique=True, null=False)
    lincs_id = models.CharField(max_length=35, null=True)
    alternate_name = models.CharField(max_length=35, null=True)
    alternate_id = models.CharField(max_length=50, null=True)
    center_name = models.CharField(max_length=20, null=False)
    center_specific_id = models.CharField(max_length=15, null=False)
    mgh_id = models.CharField(max_length=15, null=True)
    assay = models.TextField(null=True)
    organism = models.CharField(max_length=35, null=True)
    organ = models.CharField(max_length=35, null=True)
    tissue = models.CharField(max_length=35, null=True)
    cell_type = models.CharField(max_length=35, null=True)
    cell_type_detail = models.CharField(max_length=35, null=True)
    disease = models.TextField(null=True)
    disease_detail = models.TextField(null=True)
    growth_properties = models.TextField(null=True)
    genetic_modification = models.CharField(max_length=35, null=True)
    related_projects = models.CharField(max_length=35, null=True)
    recommended_culture_conditions = models.TextField(null=True)
    verification_reference_profile = models.TextField(null=True)
    mutations_reference = models.TextField(null=True)
    mutations_explicit = models.TextField(null=True)
    
    reference_source = models.TextField(null=True)
    reference_source_id = models.CharField(max_length=64, null=True)
    donor_sex = models.CharField(max_length=16, null=True)
    donor_age_years = models.IntegerField(null=True)
    donor_ethnicity = models.CharField(max_length=128, null=True)
    donor_health_status = models.TextField(null=True)
    molecular_features = models.TextField(null=True)
    relevant_citations = models.TextField(null=True)

    date_data_received = models.DateField(null=True,blank=True)
    date_loaded = models.DateField(null=True,blank=True)
    date_publicly_available = models.DateField(null=True,blank=True)
    date_updated = models.DateField(null=True,blank=True)
    is_restricted = models.BooleanField()
    def __unicode__(self):
        return unicode(self.facility_id)

    @classmethod
    def get_snippet_def(cls):
        return FieldInformation.manager.get_snippet_def(cls)


class CellBatch(models.Model):
    cell = models.ForeignKey('Cell')
    batch_id = models.CharField(max_length=_BATCH_ID_LENGTH, null=False)
    provider_name = models.TextField(null=True)
    provider_catalog_id = models.CharField(max_length=64, null=True)
    verification_profile = models.TextField(null=True)
    
    date_data_received = models.DateField(null=True,blank=True)
    date_loaded = models.DateField(null=True,blank=True)
    date_publicly_available = models.DateField(null=True,blank=True)
    date_updated = models.DateField(null=True,blank=True)

    def __unicode__(self):
        return unicode(str((self.cell,self.batch_id)))
    class Meta:
        unique_together = ('cell', 'batch_id',)    


class Protein(models.Model):
    name                = _TEXT(**_NOTNULLSTR)
    lincs_id            = _CHAR(max_length=_FACILITY_ID_LENGTH, unique=True, **_NOTNULLSTR)
    uniprot_id          = _CHAR(max_length=13, **_NULLOKSTR) # Note: UNIPROT ID's are 6 chars long, but we have a record with two in it, see issue #74
    alternate_name      = _TEXT(**_NULLOKSTR)
    alternate_name_2    = _TEXT(**_NULLOKSTR)
    provider            = _TEXT(**_NULLOKSTR)
    provider_catalog_id = _TEXT(**_NULLOKSTR)
    batch_id            = _CHAR(max_length=10, **_NULLOKSTR)
    amino_acid_sequence = _TEXT(**_NULLOKSTR)
    gene_symbol         = _CHAR(max_length=35, **_NULLOKSTR)
    gene_id             = _CHAR(max_length=35, **_NULLOKSTR)
    protein_source      = _CHAR(max_length=65, **_NULLOKSTR)
    protein_form        = _TEXT(**_NULLOKSTR) 
    protein_domain        = _TEXT(**_NULLOKSTR) 
    phosphlorylation    = _TEXT(**_NULLOKSTR) 
    mutation            = _TEXT(**_NULLOKSTR) 
    protein_purity      = _TEXT(**_NULLOKSTR)
    protein_complex     = _TEXT(**_NULLOKSTR)
    isoform             = _CHAR(max_length=5, **_NULLOKSTR) #TODO: Shall this be boolean?
    protein_type        = _CHAR(max_length=35, **_NULLOKSTR) #TODO: controlled vocabulary
    source_organism     = _CHAR(max_length=35, **_NULLOKSTR) #TODO: controlled vocabulary
    reference           = _TEXT(**_NULLOKSTR)
    date_data_received      = models.DateField(null=True,blank=True)
    date_loaded             = models.DateField(null=True,blank=True)
    date_publicly_available = models.DateField(null=True,blank=True)
    date_updated            = models.DateField(null=True,blank=True)
    is_restricted       = models.BooleanField()

    def __unicode__(self):
        return unicode(self.lincs_id)

    @classmethod
    def get_snippet_def(cls):
        return FieldInformation.manager.get_snippet_def(cls)


class Antibody(models.Model):
    facility_id             = _CHAR(max_length=_FACILITY_ID_LENGTH, **_NOTNULLSTR)
    lincs_id                = _CHAR(max_length=15, **_NULLOKSTR)
    name                    = _TEXT(**_NOTNULLSTR)
    alternative_names       = _TEXT(**_NULLOKSTR) 
    target_protein_name     = _TEXT(**_NULLOKSTR) 
    target_protein_uniprot_id       = _CHAR(max_length=13, **_NULLOKSTR) # Note: UNIPROT ID's are 6 chars long, but we have a record with two in it, see issue #74
    target_gene_name      = _CHAR(max_length=35, **_NULLOKSTR)
    target_gene_id          = _CHAR(max_length=35, **_NULLOKSTR)
    target_organism         = _CHAR(max_length=35, **_NULLOKSTR) #TODO: controlled vocabulary
    immunogen               = _TEXT(**_NULLOKSTR) 
    immunogen_sequence      = _TEXT(**_NULLOKSTR) 
    antibody_clonality      = _TEXT(**_NULLOKSTR) 
    source_organism         = _CHAR(max_length=35, **_NULLOKSTR) #TODO: controlled vocabulary
    antibody_isotype        = _CHAR(max_length=35, **_NULLOKSTR)
    engineering             = _TEXT(**_NULLOKSTR) 
    antibody_purity         = _TEXT(**_NULLOKSTR) 
    antibody_labeling       = _TEXT(**_NULLOKSTR) 
    recommended_experiment_type     = _TEXT(**_NULLOKSTR) 
    relevant_reference      = _TEXT(**_NULLOKSTR) 
    specificity             = _TEXT(**_NULLOKSTR) 
    date_data_received      = models.DateField(null=True,blank=True)
    date_loaded             = models.DateField(null=True,blank=True)
    date_publicly_available = models.DateField(null=True,blank=True)
    date_updated            = models.DateField(null=True,blank=True)
    is_restricted           = models.BooleanField(default=False) # Note: default=False are not set at the db level, only at the Db-api level

    @classmethod
    def get_snippet_def(cls):
        return FieldInformation.manager.get_snippet_def(cls)
    
class AntibodyBatch(models.Model):
    antibody           = models.ForeignKey('Antibody')
    facility_batch_id       = _CHAR(max_length=_BATCH_ID_LENGTH, **_NOTNULLSTR)
    provider                = _TEXT(**_NULLOKSTR)
    provider_catalog_id     = _CHAR(max_length=64, **_NULLOKSTR)
    
class OtherReagent(models.Model):
    facility_id             = _CHAR(max_length=_FACILITY_ID_LENGTH, **_NOTNULLSTR)
    lincs_id                = _CHAR(max_length=15, **_NULLOKSTR)
    alternate_id            = _CHAR(max_length=15, **_NULLOKSTR)
    name                    = _TEXT(**_NOTNULLSTR)
    alternative_names       = _TEXT(**_NULLOKSTR) 
    role                    = _CHAR(max_length=35, **_NULLOKSTR)
    reference               = _TEXT(**_NULLOKSTR) 
    date_data_received      = models.DateField(null=True,blank=True)
    date_loaded             = models.DateField(null=True,blank=True)
    date_publicly_available = models.DateField(null=True,blank=True)
    date_updated            = models.DateField(null=True,blank=True)
    is_restricted           = models.BooleanField(default=False) # Note: default=False are not set at the db level, only at the Db-api level

    @classmethod
    def get_snippet_def(cls):
        return FieldInformation.manager.get_snippet_def(cls)

class OtherReagentBatch(models.Model):
    other_reagent           = models.ForeignKey('OtherReagent')
    facility_batch_id       = _CHAR(max_length=_BATCH_ID_LENGTH, **_NOTNULLSTR)
    provider                = _TEXT(**_NULLOKSTR)
    provider_catalog_id     = _CHAR(max_length=64, **_NULLOKSTR)
    
class DataSet(models.Model):
    #cells                   = models.ManyToManyField(Cell, verbose_name="Cells screened")
    facility_id             = _CHAR(max_length=_FACILITY_ID_LENGTH, unique=True, **_NOTNULLSTR)
    title                   = _TEXT(unique=True, **_NOTNULLSTR)
    lead_screener_firstname = _TEXT(**_NULLOKSTR)
    lead_screener_lastname  = _TEXT(**_NULLOKSTR)
    lead_screener_email     = _TEXT(**_NULLOKSTR)
    lab_head_firstname      = _TEXT(**_NULLOKSTR)
    lab_head_lastname       = _TEXT(**_NULLOKSTR)
    lab_head_email          = _TEXT(**_NULLOKSTR)
    summary                 = _TEXT(**_NOTNULLSTR)
    protocol                = _TEXT(**_NULLOKSTR)
    protocol_references     = _TEXT(**_NULLOKSTR)
    date_data_received      = models.DateField(null=True,blank=True)
    date_loaded             = models.DateField(null=True,blank=True)
    date_publicly_available = models.DateField(null=True,blank=True)
    date_updated            = models.DateField(null=True,blank=True)
    is_restricted           = models.BooleanField()
    dataset_type            = _TEXT(**_NULLOKSTR)
    bioassay                = _TEXT(**_NULLOKSTR)
    dataset_keywords        = _TEXT(**_NULLOKSTR)
    usage_message           = _TEXT(**_NULLOKSTR)
    
    def _get_lead_screener(self):
        "Returns the LS  full name."
        return '%s %s' % (self.lead_screener_firstname, self.lead_screener_lastname)
    
    lead_screener = property(_get_lead_screener)    
    
    def _get_lab_head(self):
        "Returns the LH  full name."
        return '%s %s' % (self.lab_head_firstname, self.lab_head_lastname)
    
    lab_head = property(_get_lab_head)

    def __unicode__(self):
        return unicode(self.facility_id)

    @classmethod
    def get_snippet_def(cls):
        return FieldInformation.manager.get_snippet_def(cls)
    
    @staticmethod
    def get_dataset_types():
        dataset_types = DataSet.objects.values_list('dataset_type',flat=True).distinct()
        dataset_types = zip(dataset_types,dataset_types)
        dataset_types.insert(0,('',''))
        return dataset_types

        

LIBRARY_TYPE_PLATED = 'plated'
LIBRARY_TYPE_NON_PLATED = 'non-plated'
LIBRARY_TYPE_VIAL  = 'vial'
LIBRARY_TYPES = ((LIBRARY_TYPE_PLATED, LIBRARY_TYPE_PLATED),
                 (LIBRARY_TYPE_NON_PLATED, LIBRARY_TYPE_NON_PLATED),
                 (LIBRARY_TYPE_VIAL, LIBRARY_TYPE_VIAL),)
class Library(models.Model):
    name                    = _TEXT(unique=True,**_NOTNULLSTR)
    short_name              = _CHAR(max_length=35,unique=True, **_NOTNULLSTR)
    type                    = models.CharField(null=True, max_length=24,
                                      choices=LIBRARY_TYPES,
                                      default=LIBRARY_TYPE_NON_PLATED)
    date_first_plated       = models.DateField(null=True,blank=True)
    date_data_received      = models.DateField(null=True,blank=True)
    date_loaded             = models.DateField(null=True,blank=True)
    date_publicly_available = models.DateField(null=True,blank=True)
    date_updated            = models.DateField(null=True,blank=True)
    is_restricted           = models.BooleanField()

    def __unicode__(self):
        return unicode(self.short_name)
    
CONCENTRATION_NM = 'nM'
CONCENTRATION_UM = 'uM'
CONCENTRATION_MM = 'mM'    
CONCENTRATION_CHOICES = ((CONCENTRATION_NM,CONCENTRATION_NM),
                         (CONCENTRATION_UM,CONCENTRATION_UM),
                         (CONCENTRATION_MM,CONCENTRATION_MM))

# LibraryMapping is equivalent to a "Well"; it details how the SmallMolecule is mapped in the Library
class LibraryMapping(models.Model):
    library                 = models.ForeignKey('Library',null=True)
    smallmolecule_batch     = models.ForeignKey('SmallMoleculeBatch',null=True)
    is_control              = models.BooleanField()
    plate                   = _INTEGER(null=True)
    well                    = _CHAR(max_length=4, **_NULLOKSTR) # AA99
    concentration           = models.DecimalField(max_digits=4, decimal_places=2, null=True)
    concentration_unit      = models.CharField(null=True, max_length=2,
                                      choices=CONCENTRATION_CHOICES,
                                      default=CONCENTRATION_UM)
    
    def _get_display_concentration(self):
        return "%d %s" %(self.concentration,self.concentration_unit)

    display_concentration = property(_get_display_concentration)
    
    def __unicode__(self):
        return unicode(str((self.library,self.smallmolecule_batch)))
    #class Meta:
    #    unique_together = ('library', 'smallmolecule_batch',)    
    
class DataColumn(models.Model):
    dataset                 = models.ForeignKey('DataSet')
    worksheet_column        = _TEXT(**_NOTNULLSTR)
    name                    = _TEXT(**_NOTNULLSTR)
    display_name                    = _TEXT(**_NOTNULLSTR)
    data_type               = _TEXT(**_NOTNULLSTR)
    precision               = _INTEGER(null=True)
    description             = _TEXT(**_NULLOKSTR)
    replicate               = _INTEGER(null=True)
    unit                    = _TEXT(**_NULLOKSTR)
    readout_type            = _TEXT(**_NULLOKSTR)
    comments                = _TEXT(**_NULLOKSTR)
    display_order           = _INTEGER(null=True) # an example of why fieldinformation may need to be combined with datacolumn

    #Note we also allow cells and proteins to be associated on a column granularity
    cell                    = models.ForeignKey('Cell', null=True)
    protein                 = models.ForeignKey('Protein', null=True)

    def __unicode__(self):
        return unicode(str((self.dataset,self.name,self.data_type, self.unit)))

class DataRecord(models.Model):
    dataset                 = models.ForeignKey('DataSet')
    smallmolecule           = models.ForeignKey('SmallMolecule', null=True)
    
    sm_batch_id             = _CHAR(max_length=_BATCH_ID_LENGTH, **_NULLOKSTR) 
    cell_batch_id           = _CHAR(max_length=_BATCH_ID_LENGTH, **_NULLOKSTR) 
    
    # NOTE: library_mapping: used in the case of control wells, if smallmolecule_batch is defined, then this must match the librarymapping to the smb
    library_mapping         = models.ForeignKey('LibraryMapping',null=True)  
    cell                    = models.ForeignKey('Cell', null=True)
    protein                 = models.ForeignKey('Protein', null=True)
    antibody                = models.ForeignKey('Antibody', null=True)
    otherreagent            = models.ForeignKey('OtherReagent', null=True)
    plate                   = _INTEGER(null=True)
    well                    = _CHAR(max_length=4, **_NULLOKSTR) # AA99
    control_type            = _CHAR(max_length=35, **_NULLOKSTR) # TODO: controlled vocabulary
    def __unicode__(self):
        return unicode(str((self.dataset,self.smallmolecule,self.cell,self.protein,self.plate,self.well)))
    
class DataPoint(models.Model):
    datacolumn              = models.ForeignKey('DataColumn')
    dataset                 = models.ForeignKey('DataSet') # TODO: are we using this? Note, Screen is being included here for convenience
    datarecord              = models.ForeignKey('DataRecord') 
    int_value               = _INTEGER(null=True)
    float_value             = models.FloatField(null=True) # Note: this results in a (postgres) double precision datatype - 8 bytes; approx 15 digits of decimal precision
    text_value              = _TEXT(**_NULLOKSTR)
    
    def __unicode__(self):
        return unicode(str((self.datarecord,self.datacolumn,self.int_value,self.float_value,self.text_value)))
    class Meta:
        unique_together = ('datacolumn', 'datarecord',)    

class AttachedFile(models.Model):
    filename                = _TEXT(unique=True,**_NOTNULLSTR)
    description             = _TEXT(**_NULLOKSTR)
    relative_path           = _TEXT(**_NULLOKSTR)
    facility_id_for         = _CHAR(max_length=_FACILITY_ID_LENGTH, **_NULLOKSTR)
    salt_id_for             = _CHAR(max_length=_SALT_ID_LENGTH, **_NULLOKSTR)
    batch_id_for            = _CHAR(max_length=_BATCH_ID_LENGTH, **_NULLOKSTR)
    file_type               = _TEXT(**_NULLOKSTR)
    file_date               = models.DateField(null=True,blank=True)
    is_restricted           = models.BooleanField(default=False) # Note: default=False are not set at the db level, only at the Db-api level
    
    def __unicode__(self):
        return unicode(str((self.filename,self.relative_path,self.is_restricted, self.file_type,self.description,self.file_date)))
    
    def _get_relative_path_to_file(self):
        "Returns the 'id string'"
        return '%s/%s' % (self.relative_path, self.filename)
    
    relative_path_to_file = property(_get_relative_path_to_file)
     
del _CHAR, _TEXT, _INTEGER
del _NULLOKSTR, _NOTNULLSTR

def get_properties(obj):
    """
    Custom method to grab all of the fields _and_ properties on model instances
    """
    
    attrs     = {}
    MethodWrapperType = type(object().__hash__)

    for slot in dir(obj):
        try:
            attr = getattr(obj, slot)

            if ( slot.find('_') == 0 or slot == '__dict__' or slot == '__class__' 
                 or slot == '__doc__' 
                 or  slot == '__module__' 
                 or (isinstance(attr, types.BuiltinMethodType) or 
                  isinstance(attr, MethodWrapperType))
                 or (isinstance(attr, types.MethodType) or
                  isinstance(attr, types.FunctionType))
                or isinstance(attr, types.TypeType)):
                continue
            else:
                attrs[slot] = attr
        except Exception, e:
            logger.debug(str(('can not introspect',e)))
    return attrs

def get_listing(model_object, search_tables):
    """
    returns an ordered dict of field_name->{value:value,fieldinformation:}
    to be used to display the item in the UI Listing views
    """
    return get_fielddata(model_object, search_tables, lambda x: x.show_in_list )

def get_detail(model_object, search_tables, _filter=None, extra_properties=[],
               _override_filter=None ):
    """
    returns an ordered dict of field_name->{value:value,fieldinformation:}
    to be used to display the item in the UI Detail views
    """
    if _override_filter:
        field_information_filter = lambda x: _override_filter(x)
    elif (_filter):
        field_information_filter = lambda x: x.show_in_detail and _filter(x)
    else:
        field_information_filter = lambda x: x.show_in_detail
    return get_fielddata(model_object, search_tables, field_information_filter=field_information_filter, extra_properties=extra_properties )

def get_fielddata(model_object, search_tables, field_information_filter=None, extra_properties=[]):
    """
    returns an ordered dict of field_name->{value:value,fieldinformation:fi}
    to be used to display the item in the UI Detail views
    extra_properties are non-standard getters that wouldn't normally be returned (restricted fields)
    """
    #dump(self.dataset)
    #data=model_to_dict(self.dataset)
    property_dict = get_properties(model_object)
    if len(extra_properties) > 0:
        for prop in extra_properties:
            property_dict[prop] = getattr(model_object, prop)
            logger.info(str(('got extra prop',prop,getattr(model_object, prop) )))
            
    logger.debug(str(('property_dict', property_dict)))
    ui_dict = { }
    for field,value in property_dict.iteritems():
        logger.debug(str(('get_field_info', field)))
        details = {}
        try:
            fi = FieldInformation.manager.get_column_fieldinformation_by_priority(field,search_tables)
            
            if fi and (field_information_filter and field_information_filter(fi)
                    or field_information_filter == None ): 
                details['fieldinformation'] = fi
                details['value'] = value
                ui_dict[field] = details
                #ui_dict[fi.get_verbose_name()] = value
            else:
                logger.debug(str(('field not shown in this view: ', field,value)))
        except (FieldInformationLookupException) as e:
            logger.debug(str(('no field information defined for: ', field, value)))
    ui_dict = OrderedDict(sorted(ui_dict.items(), key=lambda x: x[1]['fieldinformation'].order))
    if(logger.isEnabledFor(logging.DEBUG)): logger.debug(str(('ui_dict',ui_dict)))
    return ui_dict
    #return self.DatasetForm(data)
 

def get_detail_bundle(obj,tables_to_search, _filter=None, _override_filter=None):
    """
    returns a bundle (dict of {verbose_name->value}) for the object, using fieldinformation to 
    determine fields to show, and to find the verbose names
    """
    detail = get_detail(obj, tables_to_search, _filter, _override_filter=_override_filter)
    data = {}
    for entry in detail.values():
        data[entry['fieldinformation'].get_camel_case_dwg_name()]=entry['value']
    return data

def get_schema_fieldinformation(field, search_tables):
    """
    generate a dict of the fieldinformation that should be shown as a part of a listing of the information for a field
    """
    #TODO: research proper way to make a lazy instantiation
    _meta_field_info = get_listing(FieldInformation(),['fieldinformation'])
        
    fi = get_fieldinformation(field, search_tables)
    if not fi:
        return 'field not defined: "' + field + '"'
    field_schema_info = {}
    for item in _meta_field_info.items():
        meta_fi_attr = item[0]
        meta_fi = item[1]['fieldinformation']
        field_schema_info[meta_fi.get_camel_case_dwg_name()] = getattr(fi,meta_fi_attr)
    return field_schema_info

def get_fieldinformation(field, search_tables=[]):
    """
    convenience wrapper around FieldInformation.manager.get_column_fieldinformation_by_priority(field,search_tables)
    """
    return FieldInformation.manager.get_column_fieldinformation_by_priority(field,search_tables)

def get_detail_schema(obj,tables_to_search, field_information_filter=None):
    """
    returns a schema (a dictionary: {fieldinformation.camel_case_dwg_name -> {field information for each field in the model obj}) 
    for the api
    """
#    meta_field_info = get_fielddata(FieldInformation(),['fieldinformation'])
    #TODO: research proper way to make a lazy instantiation
    _meta_field_info = get_listing(FieldInformation(),['fieldinformation'])
        
    
    detail = get_fielddata(obj, tables_to_search)
    fields = {}
    for entry in detail.values():
        fi = entry['fieldinformation']
        if field_information_filter and not field_information_filter(fi):
            continue
        field_schema_info = {}
        for item in _meta_field_info.items():
            meta_fi_attr = item[0]
            meta_fi = item[1]['fieldinformation']
            
            field_schema_info[meta_fi.get_camel_case_dwg_name()] = getattr(fi,meta_fi_attr)
             
        fields[fi.get_camel_case_dwg_name()]= field_schema_info
    return fields

#from django.core.cache import cache
#def find_miami_lincs_mapping(sm_id):
#    miami_lincs_id_map = cache.get('miami_lincs_id_map')
#    if not miami_lincs_id_map:
#        filesystemfinder = FileSystemFinder()
#        matches = filesystemfinder.find("miami_lincs_mapping.csv")
#        logger.info(str(('read in file', matches)))
#        if matches:
#            if not isinstance(matches, basestring): matches = matches[0]
#            with open(matches) as _file:
#                reader = csv.reader(_file,delimiter=',')
#                miami_lincs_id_map = {}
#                for line in reader:
#                    miami_lincs_id_map[line[0]]=line[1]
#            cache.set('miami_lincs_id_map', miami_lincs_id_map)
#        else:
#            logger.error(str(('filesystem finder cannot locate the miami_incs_mapping.csv')))
#    if sm_id in miami_lincs_id_map:
#        return miami_lincs_id_map[sm_id]
#    else:
#        logger.warn(str(('miami_lincs_mapping.csv does not contain sm id', sm_id)))
    