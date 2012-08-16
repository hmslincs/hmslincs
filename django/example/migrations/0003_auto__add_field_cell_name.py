# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding field 'Cell.name'
        db.add_column('example_cell', 'name',
                      self.gf('django.db.models.fields.CharField')(default='test_name_value', max_length=256),
                      keep_default=False)


    def backwards(self, orm):
        # Deleting field 'Cell.name'
        db.delete_column('example_cell', 'name')


    models = {
        'example.cell': {
            'Meta': {'object_name': 'Cell'},
            'facility_id': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '15'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '256'}),
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