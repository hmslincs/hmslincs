# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Removing unique constraint on 'Cell', fields ['clo_id']
        db.delete_unique('example_cell', ['clo_id'])


    def backwards(self, orm):
        # Adding unique constraint on 'Cell', fields ['clo_id']
        db.create_unique('example_cell', ['clo_id'])


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
            'facility_id': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '15'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'pub_date': ('django.db.models.fields.DateTimeField', [], {})
        }
    }

    complete_apps = ['example']