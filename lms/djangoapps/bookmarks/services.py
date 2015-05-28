"""
Bookmarks service.
"""
import logging

from django.core.exceptions import ObjectDoesNotExist

from xmodule.modulestore.django import modulestore
from xmodule.modulestore.exceptions import ItemNotFoundError

from request_cache.middleware import RequestCache

from . import DEFAULT_FIELDS, OPTIONAL_FIELDS, api

log = logging.getLogger(__name__)

CACHE_KEY_TEMPLATE = u"bookmarks.list.{}.{}"


class BookmarksService(object):
    """
    A service that provides access to the bookmarks API.
    """

    def __init__(self, user, **kwargs):
        super(BookmarksService, self).__init__(**kwargs)
        self._user = user

    def _clear_bookmarks_cache(self, course_key):
        """
        Clear the user's bookmarks cache for a particular course.

        Arguments:
            course_key (CourseKey): course_key of the course whose bookmarks cache should be cleared.
        """
        course_key = modulestore().fill_in_run(course_key)
        if course_key.run is None:
            return

        cache_key = CACHE_KEY_TEMPLATE.format(self._user.id, course_key)
        RequestCache.get_request_cache().data.pop(cache_key, None)

    def bookmarks(self, course_key):
        """
        Return a list of bookmarks for the course for the current user.

        Arguments:
            course_key: CourseKey of the course for which to retrieve the user's bookmarks for.

        Returns:
            list of dict:
        """
        bookmarks = api.get_bookmarks(self._user, course_key=course_key, fields=DEFAULT_FIELDS + OPTIONAL_FIELDS)

        if course_key.run is not None:
            cache_key = CACHE_KEY_TEMPLATE.format(self._user.id, course_key)
            RequestCache.get_request_cache().data[cache_key] = bookmarks

        return bookmarks

    def is_bookmarked(self, usage_key):
        """
        Return whether the block has been bookmarked by the user.

        This method fetches and caches all the bookmarks of the user
        with course_key the same as usage_key.course_key. So multiple
        calls to this method during a request will not result in repeated
        queries to the database. The cache is cleared at the end of the
        request and when set_bookmarked or unset_bookmarked are called.

        Arguments:
            usage_key: UsageKey of the block.

        Returns:
            Bool
        """
        course_key = modulestore().fill_in_run(usage_key.course_key)
        if course_key.run is None:
            return False
        cache_key = CACHE_KEY_TEMPLATE.format(self._user.id, course_key)
        request_cache = RequestCache.get_request_cache()

        if not cache_key in request_cache.data:
            self.bookmarks(course_key)

        for bookmark in request_cache.data.get(cache_key, []):
            if bookmark['usage_id'] == unicode(usage_key):
                return True

        return False

    def set_bookmarked(self, usage_key):
        """
        Adds a bookmark for the block.

        Arguments:
            usage_key: UsageKey of the block.

        Returns:
            Bool indicating whether the bookmark was added.
        """
        self._clear_bookmarks_cache(usage_key.course_key)

        try:
            api.create_bookmark(user=self._user, usage_key=usage_key)
        except ItemNotFoundError:
            log.error(u'Block with usage_id: %s not found.', usage_key)
            return False

        return True

    def unset_bookmarked(self, usage_key):
        """
        Removes the bookmark for the block.

        Arguments:
            usage_key: UsageKey of the block.

        Returns:
            Bool indicating whether the bookmark was removed.
        """
        self._clear_bookmarks_cache(usage_key.course_key)

        try:
            api.delete_bookmark(self._user, usage_key=usage_key)
        except ObjectDoesNotExist:
            log.error(u'Bookmark with usage_id: %s does not exist.', usage_key)
            return False

        return True
