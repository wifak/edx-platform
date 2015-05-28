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
from xmodule.modulestore.exceptions import ItemNotFoundError
from xmodule_django.models import CourseKeyField, LocationKeyField

log = logging.getLogger(__name__)


def get_path_data(block):
    """
    Returns data for the path to the block in the course graph.

    Note: Right now, in case of multiple paths to the block from the
    root, this function returns a path arbitrarily but consistently.
    In the future, we may want to extend it to check which of the paths,
    the student has access to and return its data.

    Arguments:
        block (XBlock): The block whose path is required.

    Returns:
        list of dicts of the form {'usage_id': <usage_id>, 'display_name': <display_name>}.
    """
    parent = block.get_parent()
    parents_data = []

    while parent is not None and parent.location.block_type not in ['course']:
        parents_data.append({'display_name': parent.display_name, 'usage_id': unicode(parent.location)})
        parent = parent.get_parent()

    parents_data.reverse()
    return parents_data


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
            data['path'] = xblock_cache.paths[0]
        else:
            data['path'] = get_path_data(block)

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
                try:
                    block = modulestore().get_item(self.usage_key)
                except ItemNotFoundError:
                    log.error(u'Block with usage_id: %s not found.', self.usage_key)
                else:
                    self.path = get_path_data(block)

            self.save()  # Always save so that self.modified is updated.

        return self.path


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
            current_paths = xblock_cache.paths or []
            new_paths = current_paths + [path for path in data.get('paths', []) if path not in current_paths]

            if xblock_cache.display_name != new_display_name or xblock_cache.paths != new_paths:
                xblock_cache.display_name = new_display_name
                xblock_cache.paths = new_paths
                xblock_cache.save()

        return xblock_cache
