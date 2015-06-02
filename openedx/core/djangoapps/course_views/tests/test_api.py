"""
Tests for the plugin API
"""

from django.test import TestCase

from openedx.core.lib.api.plugins import PluginError
from openedx.core.djangoapps.course_views.course_views import CourseViewTypeManager


class TestPluginApi(TestCase):
    """
    Unit tests for the plugin API
    """

    def test_get_plugin(self):
        """
        Verify that get_plugin works as expected.
        """
        course_view_type = CourseViewTypeManager.get_plugin("instructor")
        self.assertEqual(course_view_type.title, "Instructor")

        with self.assertRaises(PluginError):
            CourseViewTypeManager.get_plugin("no_such_type")
