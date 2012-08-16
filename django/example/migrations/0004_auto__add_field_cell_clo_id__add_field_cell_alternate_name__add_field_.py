# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding field 'Cell.clo_id'
        db.add_column('example_cell', 'clo_id',
                      self.gf('django.db.models.fields.CharField')(default='', unique=True, max_length=128),
                      keep_default=False)

        # Adding field 'Cell.alternate_name'
        db.add_column('example_cell', 'alternate_name',
                      self.gf('django.db.models.fields.CharField')(default='', max_length=256),
                      keep_default=False)

        # Adding field 'Cell.alternate_id'
        db.add_column('example_cell', 'alternate_id',
                      self.gf('django.db.models.fields.CharField')(default='', max_length=256),
                      keep_default=False)

        # Adding field 'Cell.center_name'
        db.add_column('example_cell', 'center_name',
                      self.gf('django.db.models.fields.CharField')(default='', max_length=256),
                      keep_default=False)

        # Adding field 'Cell.center_specific_id'
        db.add_column('example_cell', 'center_specific_id',
                      self.gf('django.db.models.fields.CharField')(default='', max_length=256),
                      keep_default=False)

        # Adding unique constraint on 'Cell', fields ['name']
        db.create_unique('example_cell', ['name'])


    def backwards(self, orm):
        # Removing unique constraint on 'Cell', fields ['name']
        db.delete_unique('example_cell', ['name'])

        # Deleting field 'Cell.clo_id'
        db.delete_column('example_cell', 'clo_id')

        # Deleting field 'Cell.alternate_name'
        db.delete_column('example_cell', 'alternate_name')

        # Deleting field 'Cell.alternate_id'
        db.delete_column('example_cell', 'alternate_id')

        # Deleting field 'Cell.center_name'
        db.delete_column('example_cell', 'center_name')

        # Deleting field 'Cell.center_specific_id'
        db.delete_column('example_cell', 'center_specific_id')


    models = {
        'example.cell': {
            'Meta': {'object_name': 'Cell'},
            'alternate_id': ('django.db.models.fields.CharField', [], {'max_length': '256'}),
            'alternate_name': ('django.db.models.fields.CharField', [], {'max_length': '256'}),
            'center_name': ('django.db.models.fields.CharField', [], {'max_length': '256'}),
            'center_specific_id': ('django.db.models.fields.CharField', [], {'max_length': '256'}),
            'clo_id': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '128'}),
            'facility_id': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '15'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '256'}),
            'pub_date': ('django.db.models.fields.DateTimeField', [], {})
        },
        'example.smallmolecule': {
            'Meta': {'object_name': 'SmallMolecule'},
            'facility_id': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '15'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'pub_date': ('django.db.models.fields.DateTimeField', [], {})
        }
    }

    complete_apps = ['example']