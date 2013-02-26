import datetime
from django.db import models
from django.core.exceptions import ObjectDoesNotExist,MultipleObjectsReturned
from collections import OrderedDict
import types
import re
import logging

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

class FieldsManager(models.Manager):
    
    fieldinformation_map = {}

    # this is how you override a Manager's base QuerySet
    def get_query_set(self):
        return super(FieldsManager, self).get_query_set()
    
    def get_table_fields(self,table):
        """
        return the FieldInformation objects for the table, or None if not defined
        """
        return self.get_query_set().filter(table=table)
    
    def get_column_fieldinformation_by_priority(self,field_or_alias,tables_by_priority):
        """
        searches for the FieldInformation using the tables in the tables_by_priority, in the order given.
        raises an ObjectDoesNotExist exception if not found in any of them.
        :param tables_by_priority: a sequence of table names.  If an empty table name is given, then
        a search through all fields is used.  This search can result in MultipleObjectsReturned exception.
        """
        for i,table in enumerate(tables_by_priority):
            try:
                if(table == ''):
                    return self.get_column_fieldinformation(field_or_alias)
                return self.get_column_fieldinformation(field_or_alias, table)
            except (ObjectDoesNotExist,MultipleObjectsReturned) as e:
                if( i+1 == len(tables_by_priority)): raise e
                
    def get_column_fieldinformation(self,field_or_alias,table_or_queryset=None):
        """
        return the FieldInformation object for the column, or None if not defined
        """
        
        fi = None
        if(table_or_queryset == None):
            try:
                return self.get_query_set().get(alias=field_or_alias, table=None, queryset=None); # TODO can use get?
            except (ObjectDoesNotExist,MultipleObjectsReturned) as e:
                logger.debug(str(('No field information for the alias: ',field_or_alias,e)))
            try:
                return self.get_query_set().get(field=field_or_alias, table=None, queryset=None); # TODO can use get?
            except (ObjectDoesNotExist,MultipleObjectsReturned) as e:
                logger.debug(str(('No field information for the field: ',field_or_alias,e)))
                raise e
        else:
            try:
                fi = self.get_query_set().get(queryset=table_or_queryset, field=field_or_alias)
                return fi
            except (ObjectDoesNotExist,MultipleObjectsReturned) as e:
                logger.debug(str(('No field information for the queryset,field: ',table_or_queryset,field_or_alias, e)))
            try:
                fi = self.get_query_set().get(queryset=table_or_queryset, alias=field_or_alias)
                return fi
            except (ObjectDoesNotExist,MultipleObjectsReturned) as e:
                logger.debug(str(('No field information for the queryset,alias: ',table_or_queryset,field_or_alias, e)))
            
            try:
                return self.get_query_set().get(table=table_or_queryset, field=field_or_alias)
            except (ObjectDoesNotExist,MultipleObjectsReturned) as e:
                logger.debug(str(('No field information for the table,field: ',table_or_queryset,field_or_alias, e)))
            try:
                return self.get_query_set().get(table=table_or_queryset, alias=field_or_alias)
            except (ObjectDoesNotExist,MultipleObjectsReturned) as e:
                logger.debug(str(('No field information for the table,alias: ',table_or_queryset,field_or_alias, e)))
                raise e
        
    #TODO: link this in to the reindex process!
    def get_search_fields(self,model):
        table = model._meta.module_name
        # Only text or char fields considered, must add numeric fields manually
        fields = map(lambda x: x.name, filter(lambda x: isinstance(x, models.CharField) or isinstance(x, models.TextField), tuple(model._meta.fields)))
        final_fields = []
        for fi in self.get_table_fields(table):
            if(fi.use_for_search_index and fi.field in fields):  final_fields.append(fi)
        logger.debug(str(('get_search_fields for ',model,'returns',final_fields)))
        return final_fields

PUBCHEM_TYPE_IDENTITY = 'identity'
PUBCHEM_TYPE_SUBSTRUCTURE = 'substructure'
PUBCHEM_TYPES = ((PUBCHEM_TYPE_IDENTITY, PUBCHEM_TYPE_IDENTITY),
                 (PUBCHEM_TYPE_SUBSTRUCTURE, PUBCHEM_TYPE_SUBSTRUCTURE),)

class PubchemRequest(models.Model):
    cids    = _TEXT(**_NULLOKSTR)
    smiles  = _TEXT( **_NULLOKSTR )
    molfile = _TEXT( **_NULLOKSTR )
    type    = _TEXT( null=False)
    pubchem_error_message = _TEXT( **_NULLOKSTR )
    error_message = _TEXT( **_NULLOKSTR )
#    type    = models.CharField(null=True, max_length=12,
#                               choices=PUBCHEM_TYPES,
#                               default=PUBCHEM_TYPE_IDENTITY)
    date_time_fullfilled = models.DateTimeField(null=True) 
    date_time_requested = models.DateTimeField(null=False, default=datetime.date.today ) 
    # note, don't actually call the datetime.date.today function, since in this case it serves as a function pointer
    class Meta:
        unique_together = (('smiles', 'molfile','type'))    

    
    def __unicode__(self):
        return unicode((self.id, self.cids, self.smiles, 'has_molfile' if self.molfile else 'no molfile', self.date_time_requested, self.date_time_fullfilled ))
    

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
    inchi                   = _TEXT(**_NULLOKSTR)
    inchi_key               = _TEXT(**_NULLOKSTR)
    smiles                  = _TEXT(**_NULLOKSTR)
    software                = _TEXT(**_NULLOKSTR)
    # Following fields not listed for the canonical information in the DWG, but per HMS policy will be - sde4
    molecular_mass          = models.DecimalField(max_digits=8, decimal_places=2, null=True) # Note: FloatField results in a (postgres) double precision datatype - 8 bytes; approx 15 digits of decimal precision
    molecular_formula       = _TEXT(**_NULLOKSTR)
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
    
    def _get_facility_salt(self):
        "Returns the 'facilty_id-salt_id'"
        return '%s-%s' % (self.facility_id, self.salt_id)
    
    facility_salt = property(_get_facility_salt) 
    
    def _get_primary_name(self):
        "Returns the 'primary name'"
        return self.name.split(';')[0]
    
    primary_name = property(_get_primary_name)   


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
    # ----------------------------------------------------------------------------------------------------------------------
    #                                                                          EXAMPLE VALUES:
    # ----------------------------------------------------------------------------------------------------------------------
    facility_id                    = _CHAR(max_length=_FACILITY_ID_LENGTH, unique=True, **_NOTNULLSTR)
    name                           = _CHAR(max_length=35, unique=True, **_NOTNULLSTR)    # 5637
    cl_id                          = _CHAR(max_length=35, **_NULLOKSTR)     # CLO_0003703
    alternate_name                 = _CHAR(max_length=35, **_NULLOKSTR)     # CaSki
    alternate_id                   = _CHAR(max_length=50, **_NULLOKSTR)     # COSMIC:687452
    center_name                    = _CHAR(max_length=20, **_NOTNULLSTR)    # HMS
    center_specific_id             = _CHAR(max_length=15, **_NOTNULLSTR)    # HMSL50001
    mgh_id                         = _CHAR(max_length=15, **_NULLOKSTR)     # 6
    assay                          = _TEXT(**_NULLOKSTR)                    # Mitchison Mitosis-apoptosis Img; Mitchison 
                                                                            # Prolif-Mitosis Img; Mitchison 2-3 color apo
                                                                            # pt Img
    provider_name                  = _CHAR(max_length=35, **_NOTNULLSTR)    # ATCC
    provider_catalog_id            = _CHAR(max_length=35, **_NOTNULLSTR)    # HTB-9
    batch_id                       = _CHAR(max_length=35, **_NULLOKSTR)     #
    organism                       = _CHAR(max_length=35, **_NOTNULLSTR)    # Homo sapiens
    organ                          = _CHAR(max_length=35, **_NOTNULLSTR)    # urinary bladder
    tissue                         = _CHAR(max_length=35, **_NULLOKSTR)     #
    cell_type                      = _CHAR(max_length=35, **_NULLOKSTR)     # epithelial
    cell_type_detail               = _CHAR(max_length=35, **_NULLOKSTR)     # epithelial immortalized with hTERT
    disease                        = _TEXT(**_NOTNULLSTR)                   # transitional cell carcinoma
    disease_detail                 = _TEXT(**_NULLOKSTR)                    #
    growth_properties              = _TEXT(**_NOTNULLSTR)                   # adherent
    genetic_modification           = _CHAR(max_length=35, **_NULLOKSTR)     # none
    related_projects               = _CHAR(max_length=35, **_NULLOKSTR)     #
    recommended_culture_conditions = _TEXT(**_NULLOKSTR)                    # From MGH/CMT as specified by cell provider:
                                                                               # RPMI 1640 medium with 2 mM L-glutamine adju
                                                                               # sted to contain 1.5 g/L sodium bicarbonate,
                                                                               #  4.5 g/L glucose, 10 mM HEPES, and 1.0 mM s
                                                                               # odium pyruvate, 90%; fetal bovine serum, 10
                                                                               # %. Protocol: Remove medium, and rinse with 
                                                                               # 0.25% trypsin, 0.03% EDTA solution. Remove 
                                                                               # the solution and add an additional 1 to 2 m
                                                                               # l of trypsin-EDTA solution. Allow the flask
                                                                               #  to sit at room temperature (or at 37C) unt
                                                                               # il the cells detach. Add fresh culture medi
                                                                               # um, aspirate and dispense into new culture 
                                                                               # flasks.\012Subcultivation ratio: A subculti
                                                                               # vation ratio of 1:4 to 1:8 is recommended
                                                                               # \012\012
    verification_profile           = _CHAR(max_length=35, **_NULLOKSTR)     #
    verification_reference_profile = _TEXT(**_NULLOKSTR)                    # DNA Profile (STR, source: ATCC):\012Ameloge
                                                                               # nin: X,Y \012CSF1PO: 11 \012D13S317: 11 \01
                                                                               # 2D16S539: 9 \012D5S818: 11,12 \012D7S820: 1
                                                                               # 0,11 \012THO1: 7,9 \012TPOX: 8,9 \012vWA: 1
                                                                               # 6,18
    mutations_reference            = _TEXT(**_NULLOKSTR)                    # http://www.sanger.ac.uk/perl/genetics/CGP/c
                                                                               # ore_line_viewer?action=sample&id=687452
    mutations_explicit             = _TEXT(**_NULLOKSTR)                    # Mutation data source: Sanger, Catalogue Of 
                                                                               # Somatic Mutations In Cancer: Gene: RB1, \012
                                                                               # AA mutation: p.Y325* (Substitution - Nonsen
                                                                               # se), \012CDS mutation: c.975T>A (Substituti
                                                                               # on); \012\012Gene: TP53, \012AA mutation: p
                                                                               # .R280T (Substitution - Missense), \012CDS m
                                                                               # utation: c.839G>C (Substitution)
    organism_gender                = _CHAR(max_length=35, **_NULLOKSTR)     # male
    date_data_received      = models.DateField(null=True,blank=True)
    date_loaded             = models.DateField(null=True,blank=True)
    date_publicly_available = models.DateField(null=True,blank=True)
    is_restricted                     = models.BooleanField()

    # ----------------------------------------------------------------------------------------------------------------------
    def __unicode__(self):
        return unicode(self.facility_id)

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
    protein_form        = _TEXT(**_NULLOKSTR) #TODO: controlled vocabulary
    protein_purity      = _TEXT(**_NULLOKSTR)
    protein_complex     = _TEXT(**_NULLOKSTR)
    isoform             = _CHAR(max_length=5, **_NULLOKSTR) #TODO: Shall this be boolean?
    protein_type        = _CHAR(max_length=35, **_NULLOKSTR) #TODO: controlled vocabulary
    source_organism     = _CHAR(max_length=35, **_NULLOKSTR) #TODO: controlled vocabulary
    reference           = _TEXT(**_NULLOKSTR)
    date_data_received      = models.DateField(null=True,blank=True)
    date_loaded             = models.DateField(null=True,blank=True)
    date_publicly_available = models.DateField(null=True,blank=True)
    is_restricted       = models.BooleanField()

    def __unicode__(self):
        return unicode(self.lincs_id)

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
    is_restricted           = models.BooleanField()
    dataset_type            = _TEXT(**_NULLOKSTR)
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
    data_type               = _TEXT(**_NOTNULLSTR)
    precision               = _INTEGER(null=True)
    description             = _TEXT(**_NULLOKSTR)
    replicate               = _INTEGER(null=True)
    time_point              = _TEXT(**_NULLOKSTR)
    readout_type            = _TEXT(**_NULLOKSTR)
    comments                = _TEXT(**_NULLOKSTR)
    display_order           = _INTEGER(null=True) # an example of why fieldinformation may need to be combined with datacolumn

    def __unicode__(self):
        return unicode(str((self.dataset,self.name,self.data_type)))

class DataRecord(models.Model):
    dataset                 = models.ForeignKey('DataSet')
    smallmolecule           = models.ForeignKey('SmallMolecule', null=True)
    
    # TODO: need a schema that provides proper indexes
    batch_id                = _CHAR(max_length=_BATCH_ID_LENGTH, **_NULLOKSTR) # if given, denotes the batch associated with whichever entity is linked to this dataset through this recordd
    
    # NOTE: library_mapping: used in the case of control wells, if smallmolecule_batch is defined, then this must match the librarymapping to the smb
    library_mapping         = models.ForeignKey('LibraryMapping',null=True)  
    cell                    = models.ForeignKey('Cell', null=True)
    protein                 = models.ForeignKey('Protein', null=True)
    plate                   = _INTEGER(null=True)
    well                    = _CHAR(max_length=4, **_NULLOKSTR) # AA99
    control_type            = _CHAR(max_length=35, **_NULLOKSTR) # TODO: controlled vocabulary
    def __unicode__(self):
        return unicode(str((self.dataset,self.smallmolecule,self.cell,self.protein,self.batch_id,self.plate,self.well)))
    
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
    return get_fielddata(model_object, search_tables, False)

def get_detail(model_object, search_tables):
    """
    returns an ordered dict of field_name->{value:value,fieldinformation:}
    to be used to display the item in the UI Detail views
    """
    return get_fielddata(model_object, search_tables, True)

def get_fielddata(model_object, search_tables, is_detail=False):
    """
    returns an ordered dict of field_name->{value:value,fieldinformation:}
    to be used to display the item in the UI Detail views
    """
    #dump(self.dataset)
    #data=model_to_dict(self.dataset)
    property_dict = get_properties(model_object)
    ui_dict = { }
    for field,value in property_dict.iteritems():
        details = {}
        try:
            fi = FieldInformation.manager.get_column_fieldinformation_by_priority(field,search_tables)
            if((is_detail and fi.show_in_detail) or
               (not is_detail and fi.show_in_list)):
                details['fieldinformation'] = fi
                details['value'] = value
                ui_dict[field] = details
                #ui_dict[fi.get_verbose_name()] = value
            else:
                logger.debug(str(('field not shown in this view: is_detail',is_detail, field,value)))
        except (ObjectDoesNotExist,MultipleObjectsReturned) as e:
            logger.debug(str(('no field information defined for: ', field, value)))
    ui_dict = OrderedDict(sorted(ui_dict.items(), key=lambda x: x[1]['fieldinformation'].order))
    if(logger.isEnabledFor(logging.DEBUG)): logger.debug(str(('ui_dict',ui_dict)))
    return ui_dict
    #return self.DatasetForm(data)
   
def get_detail_bundle(obj,tables_to_search):
    """
    returns a bundle (dict of {verbose_name->value}) for the object, using fieldinformation to 
    determine fields to show, and to find the verbose names
    """
    detail = get_detail(obj, tables_to_search)
    data = {}
    for entry in detail.values():
        data[entry['fieldinformation'].get_verbose_name()]=entry['value']
    return data

def get_detail_schema(obj,tables_to_search):
    """
    returns a schema (a dictionary: {fieldinformation.verbose_name -> {field information}) 
    for the api
    """
    meta_field_info = get_listing(FieldInformation(),['fieldinformation'])
    
    detail = get_detail(obj, tables_to_search)
    fields = {}
    for entry in detail.values():
        fi = entry['fieldinformation']
        field_schema_info = {}
        for item in meta_field_info.items():
            meta_fi_attr = item[0]
            meta_fi = item[1]['fieldinformation']
            
            field_schema_info[meta_fi.get_verbose_name()] = getattr(fi,meta_fi_attr)
             
        fields[fi.get_verbose_name()]= field_schema_info
    return fields