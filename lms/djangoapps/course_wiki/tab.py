"""
These callables are used by django-wiki to check various permissions
a user has on an article.
"""

from django.conf import settings
from django.utils.translation import ugettext as _

from courseware.tabs import EnrolledCourseViewType


class WikiCourseViewType(EnrolledCourseViewType):
    """
    Defines the Wiki view type that is shown as a course tab.
    """

    name = "wiki"
    title = _('Wiki')
    view_name = "course_wiki"
    is_hideable = True

    @classmethod
    def is_enabled(cls, course, user=None):
        """
        Returns true if the wiki is enabled and the specified user is enrolled or has staff access.
        """
        if not settings.WIKI_ENABLED:
            return False
        if course.allow_public_wiki_access:
            return True
        return super(WikiCourseViewType, cls).is_enabled(course, user=user)
