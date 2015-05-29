"""
Models for Bookmarks.
"""
import copy
import logging

from django.contrib.auth.models import User
from django.db import models

from jsonfield.fields import JSONField
from model_utils.models import TimeStampedModel

from xmodule.modulestore.django import modulestore
from xmodule.modulestore.exceptions import ItemNotFoundError, NoPathToItem
from xmodule.modulestore.search import path_to_location
from xmodule_django.models import CourseKeyField, LocationKeyField

log = logging.getLogger(__name__)


class Bookmark(TimeStampedModel):
    """
    Bookmarks model.
    """
    user = models.ForeignKey(User, db_index=True)
    course_key = CourseKeyField(max_length=255, db_index=True)
    usage_key = LocationKeyField(max_length=255, db_index=True)
    path = JSONField(help_text='Path in course tree to the block')

    xblock_cache = models.ForeignKey('bookmarks.XBlockCache', null=True)

    class Meta:
        """
        Bookmark metadata.
        """
        unique_together = ('user', 'usage_key')

    @classmethod
    def create(cls, data):
        """
        Create a Bookmark object.

        Arguments:
            data (dict): The data to create the object with.

        Returns:
            A Bookmark object.

        Raises:
            ItemNotFoundError: If no block exists for the usage_key.
        """
        data = copy.deepcopy(data)

        usage_key = data.pop('usage_key')
        usage_key = usage_key.replace(course_key=modulestore().fill_in_run(usage_key.course_key))

        block = modulestore().get_item(usage_key)

        xblock_cache = XBlockCache.create({
            'usage_key': usage_key,
            'display_name': block.display_name,
        })

        data['course_key'] = usage_key.course_key
        data['xblock_cache'] = xblock_cache

        if xblock_cache.paths and len(xblock_cache.paths) == 1:
            # If there is only one path to the block, use it.
            data['path'] = xblock_cache.paths[0]
        else:
            # In case of multiple paths, in the future get_path_data()
            # can be updated to look at which path the user has access to.
            data['path'] = Bookmark.get_path_data(usage_key)

        user = data.pop('user')

        bookmark, __ = cls.objects.get_or_create(usage_key=usage_key, user=user, defaults=data)
        return bookmark

    @property
    def display_name(self):
        """
        Return the display_name from self.xblock_cache.

        Returns:
            String.
        """
        return self.xblock_cache.display_name

    @property
    def updated_path(self):
        """
        Return the latest path to this block after checking self.xblock_cache.

        Returns:
            List of dicts.
        """
        if self.modified < self.xblock_cache.modified:

            if self.xblock_cache.paths and len(self.xblock_cache.paths) == 1:
                self.path = self.xblock_cache.paths[0]
            else:
                self.path = Bookmark.get_path_data(self.usage_key)

            self.save()  # Always save so that self.modified is updated.

        return self.path

    @staticmethod
    def get_path_data(usage_key):
        """
        Returns data for the path to the block in the course graph.

        Note: In case of multiple paths to the block from the course
        root, this function returns a path arbitrarily but consistently,
        depending on the modulestore. In the future, we may want to
        extend it to check which of the paths, the user has access to
        and return its data.

        Arguments:
            block (XBlock): The block whose path is required.

        Returns:
            list of dicts of the form {'usage_id': <usage_id>, 'display_name': <display_name>}.
        """
        try:
            path = path_to_location(modulestore(), usage_key, full_path=True)
        except ItemNotFoundError:
            log.error(u'Block with usage_key: %s not found.', usage_key)
            return []
        except NoPathToItem:
            log.error(u'No path to block with usage_key: %s.', usage_key)
            return []

        path_data = []
        for ancestor_usage_key in path:
            if ancestor_usage_key != usage_key and ancestor_usage_key.block_type != 'course':
                try:
                    block = modulestore().get_item(ancestor_usage_key)
                except ItemNotFoundError:
                    return []  # No valid path can be found.

                path_data.append({
                    'display_name': block.display_name,
                    'usage_id': unicode(block.location)
                })

        return path_data


class XBlockCache(TimeStampedModel):

    course_key = CourseKeyField(max_length=255, db_index=True)
    usage_key = LocationKeyField(max_length=255, db_index=True, unique=True)

    display_name = models.CharField(max_length=255, default='')
    paths = JSONField(null=True, blank=True)

    @classmethod
    def create(cls, data):
        """
        Create an XBlockCache object.

        Arguments:
            data (dict): The data to create the object with.

        Returns:
            An XBlockCache object.
        """
        data = copy.deepcopy(data)

        usage_key = data.pop('usage_key')
        usage_key = usage_key.replace(course_key=modulestore().fill_in_run(usage_key.course_key))

        data['course_key'] = usage_key.course_key

        xblock_cache, created = cls.objects.get_or_create(usage_key=usage_key, defaults=data)

        if not created:
            new_display_name = data.get('display_name', xblock_cache.display_name)
            if xblock_cache.display_name != new_display_name:
                xblock_cache.display_name = new_display_name
                xblock_cache.save()

        return xblock_cache
