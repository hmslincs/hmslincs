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
_INTEGER    = models.IntegerField
_TEXT       = models.TextField

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
            logger.debug(str(('finding', table_or_queryset,  field_or_alias)))
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


class PubchemRequest(models.Model):
    sm_facility_ids = _TEXT(**_NULLOKSTR)
    smiles  = _TEXT( **_NULLOKSTR )
    molfile = _TEXT( **_NULLOKSTR )
    type    = _TEXT( null=False)
    pubchem_error_message = _TEXT( **_NULLOKSTR )
    error_message = _TEXT( **_NULLOKSTR )
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
    
    table                   = _TEXT(**_NULLOKSTR)
    field                   = _TEXT(**_NULLOKSTR)
    alias                   = _TEXT(**_NULLOKSTR)
    queryset                = _TEXT(**_NULLOKSTR)
    show_in_detail          = models.BooleanField(default=False, null=False) # Note: default=False are not set at the db level, only at the Db-api level
    show_in_list            = models.BooleanField(default=False, null=False) # Note: default=False are not set at the db level, only at the Db-api level
    show_as_extra_field     = models.BooleanField(default=False, null=False) # Note: default=False are not set at the db level, only at the Db-api level
    list_order              = _INTEGER(null=False)
    detail_order            = _INTEGER(null=False)
    is_lincs_field          = models.BooleanField(default=False, null=False) # Note: default=False are not set at the db level, only at the Db-api level
    use_for_search_index    = models.BooleanField(default=False) # Note: default=False are not set at the db level, only at the Db-api level
    dwg_version             = _TEXT(**_NULLOKSTR)
    unique_id               = _TEXT(null=False,unique=True)
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
        return unicode(str((self.table, self.field, self.unique_id, 
            self.dwg_field_name, self.hms_field_name,self.detail_order)))
    
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
        return camel_case_dwg(field_name)

def camel_case_dwg(value):
    if not value: 
        return ''
    value = value.strip()
    array = re.split(r'[^a-zA-Z0-9]+',value)
    # convert to title case, if name made of multiple words
    value = ''.join(['ID' if x.lower()=='id' else x.title() for x in array])
    value = value[0].lower() + value[1:];
    return value

class QCEvent(models.Model):
    
    facility_id_for = models.TextField(null=False)
    salt_id_for = models.TextField(null=True)
    batch_id_for =models.TextField(null=True)
    outcome = models.TextField(null=False)
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

class Reagent(models.Model):

    facility_id = models.TextField(null=False)
    lincs_id = models.TextField(null=True)
    name = models.TextField(null=False)
    # Note: salt id is part of the composite key for the SmallMoleculeReagent
    salt_id = _TEXT(**_NOTNULLSTR)
    is_restricted = models.BooleanField(default=False) 
    alternative_names = models.TextField(null=True)
    alternative_id = models.TextField(null=True)
    
    date_data_received = models.DateField(null=True,blank=True)
    date_loaded = models.DateField(null=True,blank=True)
    date_publicly_available = models.DateField(null=True,blank=True)
    date_updated = models.DateField(null=True,blank=True)

    class Meta:
        unique_together = ('facility_id', 'salt_id')    
    
    @property
    def facility_salt(self):
        "Returns the 'facilty_id-salt_id'"
        return '%s-%s' % (self.facility_id, self.salt_id)

    @property
    def unrestricted_facility_salt(self):
        "Returns the 'facilty_id-salt_id', only if unrestricted"
        if self.is_restricted:
            return ''
        else: 
            return '%s-%s' % (self.facility_id, self.salt_id)
    
    @classmethod
    def get_snippet_def(cls):
        return FieldInformation.manager.get_snippet_def(cls)

    def __unicode__(self):
        return u'%s' % self.facility_id

class ReagentBatch(models.Model):        

    reagent = models.ForeignKey('Reagent', null=False)
    batch_id = models.TextField(null=False)
    provider_name = models.TextField(null=True)
    provider_catalog_id = models.TextField(null=True)
    provider_batch_id = models.TextField(null=True)
    
    center_specific_code = models.TextField(null=True)

    date_data_received = models.DateField(null=True,blank=True)
    date_loaded = models.DateField(null=True,blank=True)
    date_publicly_available = models.DateField(null=True,blank=True)
    date_updated = models.DateField(null=True,blank=True)

    @property
    def facility_batch(self):
        "Returns the 'facilty_id-batch_id'"
        return '%s-%s' % (self.reagent.facility_id, self.batch_id)

    @property
    def facility_salt_batch(self):
        "Returns the 'facilty_id-salt_id'"
        return '%s-%s' % (self.reagent.facility_salt, self.batch_id)

    @classmethod
    def get_snippet_def(cls):
        return FieldInformation.manager.get_snippet_def(cls)

    class Meta:
        unique_together = ('reagent', 'batch_id')
        # TODO: verify that the center_specific_code will not be repeated
        # unique_together = ('reagent', 'center_specific_code')

    def __unicode__(self):
        return u'%s:%s' %(self.reagent, self.batch_id)
    
class SmallMolecule(Reagent):
    
    nominal_target          = models.ForeignKey('Protein', null=True)
    molfile                 = _TEXT(**_NULLOKSTR)
    pubchem_cid             = _TEXT(**_NULLOKSTR)
    chembl_id               = _TEXT(**_NULLOKSTR)
    chebi_id                = _TEXT(**_NULLOKSTR)
    _inchi                   = _TEXT(db_column='inchi', **_NULLOKSTR)
    _inchi_key               = _TEXT(db_column='inchi_key', **_NULLOKSTR)
    _smiles                  = _TEXT( db_column='smiles', **_NULLOKSTR)
    software                = _TEXT(**_NULLOKSTR)
    # Following fields not listed for the canonical information in the DWG, but per HMS policy will be - sde4
    _molecular_mass          = models.DecimalField(db_column='molecular_mass', max_digits=8, decimal_places=2, null=True) # Note: FloatField results in a (postgres) double precision datatype - 8 bytes; approx 15 digits of decimal precision
    _molecular_formula       = _TEXT(db_column='molecular_formula', **_NULLOKSTR)
      
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
    
    @property
    def primary_name(self):
        "Returns the 'primary name'"
        return self.name.split(';')[0]
    
    @classmethod
    def get_snippet_def(cls):
        return FieldInformation.manager.get_snippet_def(cls)

class SmallMoleculeBatch(ReagentBatch):

    chemical_synthesis_reference = _TEXT(**_NULLOKSTR)
    purity                  = _TEXT(**_NULLOKSTR)
    purity_method           = _TEXT(**_NULLOKSTR)
    aqueous_solubility      = models.DecimalField(max_digits=4, decimal_places=2, null=True)
    aqueous_solubility_unit = models.TextField(null=True)
    inchi                   = _TEXT(**_NULLOKSTR)
    inchi_key               = _TEXT(**_NULLOKSTR)
    smiles                  = _TEXT(**_NULLOKSTR)

class Cell(Reagent):
    
    precursor = models.ForeignKey('Cell',related_name='descendants', null=True)
    center_specific_id = models.TextField(null=False)
    mgh_id = models.TextField(null=True)
    assay = models.TextField(null=True)
    organism = models.TextField(null=True)
    organ = models.TextField(null=True)
    tissue = models.TextField(null=True)
    cell_type = models.TextField(null=True)
    cell_type_detail = models.TextField(null=True)
    disease = models.TextField(null=True)
    disease_detail = models.TextField(null=True)
    growth_properties = models.TextField(null=True)
    genetic_modification = models.TextField(null=True)
    related_projects = models.TextField(null=True)
    recommended_culture_conditions = models.TextField(null=True)
    verification_reference_profile = models.TextField(null=True)
    mutations_known = models.TextField(null=True)
    mutations_citations = models.TextField(null=True)
    reference_source = models.TextField(null=True)
    reference_source_url = models.TextField(null=True)
    donor_sex = models.TextField(null=True)
    donor_age_years = models.IntegerField(null=True)
    donor_ethnicity = models.TextField(null=True)
    donor_health_status = models.TextField(null=True)
    molecular_features = models.TextField(null=True)
    production_details = models.TextField(null=True)
    relevant_citations = models.TextField(null=True)
    usage_note = models.TextField(null=True)

    @classmethod
    def get_snippet_def(cls):
        return FieldInformation.manager.get_snippet_def(cls)

    @property
    def precursor_cell_name(self):
        if self.precursor:
            return self.precursor.name
        else:
            return None


class PrimaryCell(Reagent):

    organism = models.TextField(null=True)
    organ = models.TextField(null=True)
    tissue = models.TextField(null=True)
    cell_type = models.TextField(null=True)
    cell_type_detail = models.TextField(null=True)
    donor_sex = models.TextField(null=True)
    gonosome_code = models.TextField(null=True)
    donor_age_years = models.IntegerField(null=True)
    donor_ethnicity = models.TextField(null=True)
    donor_health_status = models.TextField(null=True)
    disease = models.TextField(null=True)
    disease_detail = models.TextField(null=True)
    disease_site_onset = models.TextField(null=True)
    disease_age_onset_years = models.IntegerField(null=True)
    donor_age_death_years = models.IntegerField(null=True)
    donor_disease_duration_years = models.IntegerField(null=True)
    mutations_known = models.TextField(null=True)
    mutations_citations = models.TextField(null=True)
    molecular_features = models.TextField(null=True)
    genetic_modification = models.TextField(null=True)
    cell_markers = models.TextField(null=True)
    growth_properties = models.TextField(null=True)
    recommended_culture_conditions = models.TextField(null=True)
    related_projects = models.TextField(null=True)
    verification_reference_profile = models.TextField(null=True)
    production_details = models.TextField(null=True)
    relevant_citations = models.TextField(null=True)
    usage_note = models.TextField(null=True)

    @classmethod
    def get_snippet_def(cls):
        return FieldInformation.manager.get_snippet_def(cls)

class CellBatch(ReagentBatch):

    quality_verification = models.TextField(null=True)
    transient_modification = models.TextField(null=True)
    source_information = models.TextField(null=True)
    date_received = models.TextField(null=True)

    # TODO: test this for batch - update indexer
    @classmethod
    def get_snippet_def(cls):
        return FieldInformation.manager.get_snippet_def(cls)
    
class PrimaryCellBatch(ReagentBatch):

    quality_verification = models.TextField(null=True)
    transient_modification = models.TextField(null=True)
    source_information = models.TextField(null=True)
    culture_conditions = models.TextField(null=True)
    passage_number = models.IntegerField(null=True)
    date_received = models.TextField(null=True)

    # TODO: test this for batch - update indexer
    @classmethod
    def get_snippet_def(cls):
        return FieldInformation.manager.get_snippet_def(cls)
    
class Protein(Reagent):
    
    uniprot_id          = _TEXT(**_NULLOKSTR) # Note: UNIPROT ID's are 6 chars long, but we have a record with two in it, see issue #74
    alternate_name_2    = _TEXT(**_NULLOKSTR)
    provider            = _TEXT(**_NULLOKSTR)
    provider_catalog_id = _TEXT(**_NULLOKSTR)
    batch_id            = _TEXT(**_NULLOKSTR)
    amino_acid_sequence = _TEXT(**_NULLOKSTR)
    gene_symbol         = _TEXT(**_NULLOKSTR)
    gene_id             = _TEXT(**_NULLOKSTR)
    protein_source      = _TEXT(**_NULLOKSTR)
    protein_form        = _TEXT(**_NULLOKSTR) 
    protein_domain        = _TEXT(**_NULLOKSTR) 
    phosphlorylation    = _TEXT(**_NULLOKSTR) 
    mutation            = _TEXT(**_NULLOKSTR) 
    protein_purity      = _TEXT(**_NULLOKSTR)
    protein_complex     = _TEXT(**_NULLOKSTR)
    isoform             = _TEXT(**_NULLOKSTR) #TODO: Shall this be boolean?
    protein_type        = _TEXT(**_NULLOKSTR) #TODO: controlled vocabulary
    source_organism     = _TEXT(**_NULLOKSTR) #TODO: controlled vocabulary
    reference           = _TEXT(**_NULLOKSTR)

    @classmethod
    def get_snippet_def(cls):
        return FieldInformation.manager.get_snippet_def(cls)

class ProteinBatch(ReagentBatch):
    
    production_organism = models.TextField()

class Antibody(Reagent):

    clone_name              = _TEXT(**_NULLOKSTR)
    rrid                    = _TEXT(**_NULLOKSTR)
    type                    = _TEXT(**_NULLOKSTR)
    target_protein          = models.ForeignKey('Protein',null=True)
    non_protein_target_name = _TEXT(**_NULLOKSTR)
    target_organism         = _TEXT(**_NULLOKSTR) 
    immunogen               = _TEXT(**_NULLOKSTR) 
    immunogen_sequence      = _TEXT(**_NULLOKSTR) 
    species                 = _TEXT(**_NULLOKSTR)
    clonality               = _TEXT(**_NULLOKSTR) 
    isotype                 = _TEXT(**_NULLOKSTR)
    source_organism         = _TEXT(**_NULLOKSTR) 
    production_details      = _TEXT(**_NULLOKSTR)
    labeling                = _TEXT(**_NULLOKSTR) 
    labeling_details        = _TEXT(**_NULLOKSTR) 
    relevant_citations      = _TEXT(**_NULLOKSTR) 
    
    @property
    def target_protein_name(self):
        if self.target_protein:
            return self.target_protein.name
        else:
            return None

    @property
    def target_protein_uniprot_id(self):
        if self.target_protein:
            return self.target_protein.uniprot_id
        else:
            return None
    
    @property
    def target_protein_center_id(self):
        if self.target_protein:
            return self.target_protein.facility_id
        else:
            return None

    @property
    def target_protein_lincs_id(self):
        if self.target_protein:
            return self.target_protein.lincs_id
        else:
            return None
            
    @classmethod
    def get_snippet_def(cls):
        return FieldInformation.manager.get_snippet_def(cls)
        
class AntibodyBatch(ReagentBatch):

    antibody_purity         = _TEXT(**_NULLOKSTR) 

class OtherReagent(Reagent):

    alternate_id            = _TEXT(**_NULLOKSTR)
    role                    = _TEXT(**_NULLOKSTR)
    reference               = _TEXT(**_NULLOKSTR) 

    @classmethod
    def get_snippet_def(cls):
        return FieldInformation.manager.get_snippet_def(cls)

class OtherReagentBatch(ReagentBatch):
    
    def __unicode__(self):
        return ReagentBatch.__unicode__(self)
    
class DataSet(models.Model):
    facility_id             = _TEXT(unique=True, **_NOTNULLSTR)
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
    associated_publication     = _TEXT(**_NULLOKSTR)
    associated_project_summary = _TEXT(**_NULLOKSTR)
    small_molecules         = models.ManyToManyField('SmallMoleculeBatch')
    cells                   = models.ManyToManyField('CellBatch')
    primary_cells           = models.ManyToManyField('PrimaryCellBatch')
    antibodies              = models.ManyToManyField('AntibodyBatch')
    proteins                = models.ManyToManyField('ProteinBatch')
    other_reagents          = models.ManyToManyField('OtherReagentBatch')
    
    @property
    def lead_screener(self):
        "Returns the LS  full name."
        return '%s %s' % (self.lead_screener_firstname, self.lead_screener_lastname)
    
    @property
    def lab_head(self):
        "Returns the LH  full name."
        return '%s %s' % (self.lab_head_firstname, self.lab_head_lastname)

    @classmethod
    def get_snippet_def(cls):
        return FieldInformation.manager.get_snippet_def(cls)
    
    @staticmethod
    def get_dataset_types():
        dataset_types = DataSet.objects.values_list('dataset_type',flat=True).distinct()
        dataset_types = zip(dataset_types,dataset_types)
        dataset_types.insert(0,('',''))
        return dataset_types

    def __unicode__(self):
        return u'%s' % self.facility_id

class Library(models.Model):
    name                    = _TEXT(unique=True,**_NOTNULLSTR)
    short_name              = _TEXT(unique=True, **_NOTNULLSTR)
    type                    = models.TextField(null=True)
    date_first_plated       = models.DateField(null=True,blank=True)
    date_data_received      = models.DateField(null=True,blank=True)
    date_loaded             = models.DateField(null=True,blank=True)
    date_publicly_available = models.DateField(null=True,blank=True)
    date_updated            = models.DateField(null=True,blank=True)
    is_restricted           = models.BooleanField()

    def __unicode__(self):
        return unicode(self.short_name)
    
    
# LibraryMapping is equivalent to a "Well"; it details how the SmallMolecule is mapped in the Library
class LibraryMapping(models.Model):
    library                 = models.ForeignKey('Library',null=True)
    smallmolecule_batch     = models.ForeignKey('SmallMoleculeBatch',null=True)
    is_control              = models.BooleanField()
    plate                   = _INTEGER(null=True)
    well                    = _TEXT(**_NULLOKSTR) # AA99
    concentration           = models.DecimalField(max_digits=4, decimal_places=2, null=True)
    concentration_unit      = models.TextField(null=True)
    
    @property
    def display_concentration(self):
        return "%d %s" %(self.concentration,self.concentration_unit)
    
    def __unicode__(self):
        return unicode(str((self.library,self.smallmolecule_batch)))
    
class DataColumn(models.Model):
    dataset                 = models.ForeignKey('DataSet')
    worksheet_column        = _TEXT(**_NULLOKSTR)
    name                    = _TEXT(**_NOTNULLSTR)
    display_name            = _TEXT(**_NOTNULLSTR)
    data_type               = _TEXT(**_NOTNULLSTR)
    precision               = _INTEGER(null=True)
    description             = _TEXT(**_NULLOKSTR)
    replicate               = _INTEGER(null=True)
    unit                    = _TEXT(**_NULLOKSTR)
    readout_type            = _TEXT(**_NULLOKSTR)
    comments                = _TEXT(**_NULLOKSTR)
    display_order           = _INTEGER(null=True)

    class Meta:
        unique_together = ('dataset', 'name',)    

    def __unicode__(self):
        return u'%s: worksheet_column: %s, %s, %s' % (
            self.dataset, self.worksheet_column, self.name, self.data_type)

class DataRecord(models.Model):
    dataset                 = models.ForeignKey('DataSet')
    library_mapping         = models.ForeignKey('LibraryMapping',null=True)  
    plate                   = _INTEGER(null=True)
    well                    = _TEXT(**_NULLOKSTR)
    control_type            = _TEXT(**_NULLOKSTR)
    
    def __unicode__(self):
        return u'%s: %r, plate: %r, well: %s' % (
            self.dataset, self.id, self.plate, self.well)
    
class DataPoint(models.Model):
    datacolumn              = models.ForeignKey('DataColumn')
    dataset                 = models.ForeignKey('DataSet') 
    datarecord              = models.ForeignKey('DataRecord') 
    int_value               = _INTEGER(null=True)
    float_value             = models.FloatField(null=True) 
    text_value              = _TEXT(**_NULLOKSTR)
    reagent_batch           = models.ForeignKey('ReagentBatch', null=True)

    def __unicode__(self):
        return u'%s: %s: %r, %r, %s, %s' % (
            self.datarecord, self.datacolumn, self.int_value, self.float_value, 
            self.text_value, self.reagent_batch)
    class Meta:
        unique_together = ('datacolumn', 'datarecord',)    

class AttachedFile(models.Model):
    filename                = _TEXT(unique=True,**_NOTNULLSTR)
    description             = _TEXT(**_NULLOKSTR)
    relative_path           = _TEXT(**_NULLOKSTR)
    facility_id_for         = _TEXT(**_NULLOKSTR)
    salt_id_for             = _TEXT(**_NULLOKSTR)
    batch_id_for            = _TEXT(**_NULLOKSTR)
    file_type               = _TEXT(**_NULLOKSTR)
    file_date               = models.DateField(null=True,blank=True)
    is_restricted           = models.BooleanField(default=False) # Note: default=False are not set at the db level, only at the Db-api level
    
    def __unicode__(self):
        return unicode(str((self.filename,self.relative_path,self.is_restricted, self.file_type,self.description,self.file_date)))
    
    @property
    def relative_path_to_file(self):
        "Returns the 'id string'"
        return '%s/%s' % (self.relative_path, self.filename)
     
del _TEXT, _INTEGER
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

def get_detail(
        model_object, search_tables, _filter=None, extra_properties=[],
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
    ui_dict = OrderedDict(sorted(ui_dict.items(), key=lambda x: x[1]['fieldinformation'].detail_order))
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
    