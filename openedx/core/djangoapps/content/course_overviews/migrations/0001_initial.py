# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'CourseOverviewFields'
        db.create_table('course_overviews_courseoverviewfields', (
            ('id', self.gf('xmodule_django.models.CourseKeyField')(max_length=255, primary_key=True, db_index=True)),
            ('modulestore_type', self.gf('django.db.models.fields.CharField')(max_length=5)),
            ('user_partitions', self.gf('openedx.core.djangoapps.content.course_overviews.models.UserPartitionListCacheField')()),
            ('static_asset_path', self.gf('django.db.models.fields.TextField')()),
            ('ispublic', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('visible_to_staff_only', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('group_access', self.gf('openedx.core.djangoapps.content.course_overviews.models.GroupAccessDictCacheField')()),
            ('location', self.gf('xmodule_django.models.UsageKeyField')(max_length=255)),
            ('enrollment_start', self.gf('django.db.models.fields.DateField')()),
            ('enrollment_end', self.gf('django.db.models.fields.DateField')()),
            ('start', self.gf('django.db.models.fields.DateField')(default=datetime.datetime(2029, 12, 31, 0, 0))),
            ('end', self.gf('django.db.models.fields.DateField')()),
            ('advertised_start', self.gf('django.db.models.fields.TextField')()),
            ('pre_requisite_courses', self.gf('openedx.core.djangoapps.content.course_overviews.models.CourseIdListCacheField')()),
            ('end_of_course_survey_url', self.gf('django.db.models.fields.TextField')()),
            ('display_name', self.gf('django.db.models.fields.TextField')(default='Empty')),
            ('mobile_available', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('facebook_url', self.gf('django.db.models.fields.TextField')(default=None)),
            ('enrollment_domain', self.gf('django.db.models.fields.TextField')()),
            ('certificates_show_before_end', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('certificates_display_behavior', self.gf('django.db.models.fields.TextField')(default='end')),
            ('course_image', self.gf('django.db.models.fields.TextField')(default='images_course_image.jpg')),
            ('cert_name_short', self.gf('django.db.models.fields.TextField')(default='')),
            ('cert_name_long', self.gf('django.db.models.fields.TextField')(default='')),
            ('display_organization', self.gf('django.db.models.fields.TextField')()),
            ('display_coursenumber', self.gf('django.db.models.fields.TextField')()),
            ('invitation_only', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('catalog_visibility', self.gf('django.db.models.fields.TextField')(default='both')),
            ('social_sharing_url', self.gf('django.db.models.fields.TextField')(default=None)),
        ))
        db.send_create_signal('course_overviews', ['CourseOverviewFields'])

        # Adding model 'CourseOverviewDescriptor'
        db.create_table('course_overviews_courseoverviewdescriptor', (
            ('courseoverviewfields_ptr', self.gf('django.db.models.fields.related.OneToOneField')(to=orm['course_overviews.CourseOverviewFields'], unique=True, primary_key=True)),
        ))
        db.send_create_signal('course_overviews', ['CourseOverviewDescriptor'])


    def backwards(self, orm):
        # Deleting model 'CourseOverviewFields'
        db.delete_table('course_overviews_courseoverviewfields')

        # Deleting model 'CourseOverviewDescriptor'
        db.delete_table('course_overviews_courseoverviewdescriptor')


    models = {
        'course_overviews.courseoverviewdescriptor': {
            'Meta': {'object_name': 'CourseOverviewDescriptor', '_ormbases': ['course_overviews.CourseOverviewFields']},
            'courseoverviewfields_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': "orm['course_overviews.CourseOverviewFields']", 'unique': 'True', 'primary_key': 'True'})
        },
        'course_overviews.courseoverviewfields': {
            'Meta': {'object_name': 'CourseOverviewFields'},
            'advertised_start': ('django.db.models.fields.TextField', [], {}),
            'catalog_visibility': ('django.db.models.fields.TextField', [], {'default': "'both'"}),
            'cert_name_long': ('django.db.models.fields.TextField', [], {'default': "''"}),
            'cert_name_short': ('django.db.models.fields.TextField', [], {'default': "''"}),
            'certificates_display_behavior': ('django.db.models.fields.TextField', [], {'default': "'end'"}),
            'certificates_show_before_end': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'course_image': ('django.db.models.fields.TextField', [], {'default': "'images_course_image.jpg'"}),
            'display_coursenumber': ('django.db.models.fields.TextField', [], {}),
            'display_name': ('django.db.models.fields.TextField', [], {'default': "'Empty'"}),
            'display_organization': ('django.db.models.fields.TextField', [], {}),
            'end': ('django.db.models.fields.DateField', [], {}),
            'end_of_course_survey_url': ('django.db.models.fields.TextField', [], {}),
            'enrollment_domain': ('django.db.models.fields.TextField', [], {}),
            'enrollment_end': ('django.db.models.fields.DateField', [], {}),
            'enrollment_start': ('django.db.models.fields.DateField', [], {}),
            'facebook_url': ('django.db.models.fields.TextField', [], {'default': 'None'}),
            'group_access': ('openedx.core.djangoapps.content.course_overviews.models.GroupAccessDictCacheField', [], {}),
            'id': ('xmodule_django.models.CourseKeyField', [], {'max_length': '255', 'primary_key': 'True', 'db_index': 'True'}),
            'invitation_only': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ispublic': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'location': ('xmodule_django.models.UsageKeyField', [], {'max_length': '255'}),
            'mobile_available': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'modulestore_type': ('django.db.models.fields.CharField', [], {'max_length': '5'}),
            'pre_requisite_courses': ('openedx.core.djangoapps.content.course_overviews.models.CourseIdListCacheField', [], {}),
            'social_sharing_url': ('django.db.models.fields.TextField', [], {'default': 'None'}),
            'start': ('django.db.models.fields.DateField', [], {'default': 'datetime.datetime(2029, 12, 31, 0, 0)'}),
            'static_asset_path': ('django.db.models.fields.TextField', [], {}),
            'user_partitions': ('openedx.core.djangoapps.content.course_overviews.models.UserPartitionListCacheField', [], {}),
            'visible_to_staff_only': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        }
    }

    complete_apps = ['course_overviews']