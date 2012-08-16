# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding field 'SmallMolecule.name'
        db.add_column('example_smallmolecule', 'name',
                      self.gf('django.db.models.fields.CharField')(default='', max_length=256),
                      keep_default=False)

        # Adding field 'SmallMolecule.alternate_names'
        db.add_column('example_smallmolecule', 'alternate_names',
                      self.gf('django.db.models.fields.TextField')(default=''),
                      keep_default=False)

        # Adding field 'SmallMolecule.salt_id'
        db.add_column('example_smallmolecule', 'salt_id',
                      self.gf('django.db.models.fields.IntegerField')(default=0),
                      keep_default=False)

        # Adding field 'SmallMolecule.smiles'
        db.add_column('example_smallmolecule', 'smiles',
                      self.gf('django.db.models.fields.TextField')(default=''),
                      keep_default=False)


    def backwards(self, orm):
        # Deleting field 'SmallMolecule.name'
        db.delete_column('example_smallmolecule', 'name')

        # Deleting field 'SmallMolecule.alternate_names'
        db.delete_column('example_smallmolecule', 'alternate_names')

        # Deleting field 'SmallMolecule.salt_id'
        db.delete_column('example_smallmolecule', 'salt_id')

        # Deleting field 'SmallMolecule.smiles'
        db.delete_column('example_smallmolecule', 'smiles')


    models = {
        'example.cell': {
            'Meta': {'object_name': 'Cell'},
            'alternate_id': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '256'}),
            'alternate_name': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '256'}),
            'center_name': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '256'}),
            'center_specific_id': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '256'}),
            'clo_id': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '128'}),
            'facility_id': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '15'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '256'}),
            'pub_date': ('django.db.models.fields.DateTimeField', [], {})
        },
        'example.smallmolecule': {
            'Meta': {'object_name': 'SmallMolecule'},
            'alternate_names': ('django.db.models.fields.TextField', [], {}),
            'facility_id': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '15'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '256'}),
            'pub_date': ('django.db.models.fields.DateTimeField', [], {}),
            'salt_id': ('django.db.models.fields.IntegerField', [], {}),
            'smiles': ('django.db.models.fields.TextField', [], {})
        }
    }

    complete_apps = ['example']