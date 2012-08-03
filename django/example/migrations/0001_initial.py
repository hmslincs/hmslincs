# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'SmallMolecule'
        db.create_table('example_smallmolecule', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('facility_id', self.gf('django.db.models.fields.CharField')(unique=True, max_length=15)),
            ('pub_date', self.gf('django.db.models.fields.DateTimeField')()),
        ))
        db.send_create_signal('example', ['SmallMolecule'])


    def backwards(self, orm):
        # Deleting model 'SmallMolecule'
        db.delete_table('example_smallmolecule')


    models = {
        'example.smallmolecule': {
            'Meta': {'object_name': 'SmallMolecule'},
            'facility_id': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '15'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'pub_date': ('django.db.models.fields.DateTimeField', [], {})
        }
    }

    complete_apps = ['example']