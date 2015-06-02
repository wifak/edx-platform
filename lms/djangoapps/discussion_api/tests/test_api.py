"""
Tests for Discussion API internal interface
"""
from datetime import datetime, timedelta
import itertools
from urlparse import urlparse, urlunparse
from urllib import urlencode

import ddt
import httpretty
import mock
from pytz import UTC

from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse
from django.http import Http404
from django.test.client import RequestFactory

from opaque_keys.edx.locator import CourseLocator

from courseware.tests.factories import BetaTesterFactory, StaffFactory
from discussion_api.api import (
    create_comment,
    create_thread,
    get_comment_list,
    get_course_topics,
    get_thread_list,
)
from discussion_api.tests.utils import (
    CommentsServiceMockMixin,
    make_minimal_cs_comment,
    make_minimal_cs_thread,
)
from django_comment_common.models import (
    FORUM_ROLE_ADMINISTRATOR,
    FORUM_ROLE_COMMUNITY_TA,
    FORUM_ROLE_MODERATOR,
    FORUM_ROLE_STUDENT,
    Role,
)
from openedx.core.djangoapps.course_groups.models import CourseUserGroupPartitionGroup
from openedx.core.djangoapps.course_groups.tests.helpers import CohortFactory
from student.tests.factories import CourseEnrollmentFactory, UserFactory
from util.testing import UrlResetMixin
from xmodule.modulestore.django import modulestore
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory, ItemFactory
from xmodule.partitions.partitions import Group, UserPartition
from xmodule.tabs import DiscussionTab


def _remove_discussion_tab(course, user_id):
    """
    Remove the discussion tab for the course.

    user_id is passed to the modulestore as the editor of the module.
    """
    course.tabs = [tab for tab in course.tabs if not isinstance(tab, DiscussionTab)]
    modulestore().update_item(course, user_id)


@mock.patch.dict("django.conf.settings.FEATURES", {"DISABLE_START_DATES": False})
class GetCourseTopicsTest(UrlResetMixin, ModuleStoreTestCase):
    """Test for get_course_topics"""

    @mock.patch.dict("django.conf.settings.FEATURES", {"ENABLE_DISCUSSION_SERVICE": True})
    def setUp(self):
        super(GetCourseTopicsTest, self).setUp()
        self.maxDiff = None  # pylint: disable=invalid-name
        self.partition = UserPartition(
            0,
            "partition",
            "Test Partition",
            [Group(0, "Cohort A"), Group(1, "Cohort B")],
            scheme_id="cohort"
        )
        self.course = CourseFactory.create(
            org="x",
            course="y",
            run="z",
            start=datetime.now(UTC),
            discussion_topics={"Test Topic": {"id": "non-courseware-topic-id"}},
            user_partitions=[self.partition],
            cohort_config={"cohorted": True},
            days_early_for_beta=3
        )
        self.user = UserFactory.create()
        self.request = RequestFactory().get("/dummy")
        self.request.user = self.user
        CourseEnrollmentFactory.create(user=self.user, course_id=self.course.id)

    def make_discussion_module(self, topic_id, category, subcategory, **kwargs):
        """Build a discussion module in self.course"""
        ItemFactory.create(
            parent_location=self.course.location,
            category="discussion",
            discussion_id=topic_id,
            discussion_category=category,
            discussion_target=subcategory,
            **kwargs
        )

    def get_thread_list_url(self, topic_id_list):
        """
        Returns the URL for the thread_list_url field, given a list of topic_ids
        """
        path = reverse("thread-list")
        query_list = [("course_id", unicode(self.course.id))] + [("topic_id", topic_id) for topic_id in topic_id_list]
        return self.request.build_absolute_uri(urlunparse(("", "", path, "", urlencode(query_list), "")))

    def get_course_topics(self):
        """
        Get course topics for self.course, using the given user or self.user if
        not provided, and generating absolute URIs with a test scheme/host.
        """
        return get_course_topics(self.request, self.course.id)

    def make_expected_tree(self, topic_id_list, name, children=None):
        """
        Build an expected result tree given a topic id, display name, children
        """
        children = children or []
        node = {
            "name": name,
            "children": children,
            "thread_list_url": self.get_thread_list_url(topic_id_list)
        }
        if children:
            node["id"] = None
        else:
            node["id"] = topic_id_list[0]

        return node

    def test_nonexistent_course(self):
        with self.assertRaises(Http404):
            get_course_topics(self.request, CourseLocator.from_string("non/existent/course"))

    def test_not_enrolled(self):
        unenrolled_user = UserFactory.create()
        self.request.user = unenrolled_user
        with self.assertRaises(Http404):
            self.get_course_topics()

    def test_discussions_disabled(self):
        _remove_discussion_tab(self.course, self.user.id)
        with self.assertRaises(Http404):
            self.get_course_topics()

    def test_without_courseware(self):
        actual = self.get_course_topics()
        expected = {
            "courseware_topics": [],
            "non_courseware_topics": [
                self.make_expected_tree(["non-courseware-topic-id"], "Test Topic")
            ],
        }
        self.assertEqual(actual, expected)

    def test_with_courseware(self):
        self.make_discussion_module("courseware-topic-id", "Foo", "Bar")
        actual = self.get_course_topics()
        expected = {
            "courseware_topics": [
                self.make_expected_tree(
                    ["courseware-topic-id"],
                    "Foo",
                    [self.make_expected_tree(["courseware-topic-id"], "Bar")]
                ),
            ],
            "non_courseware_topics": [
                self.make_expected_tree(["non-courseware-topic-id"], "Test Topic")
            ],
        }
        self.assertEqual(actual, expected)

    def test_many(self):
        self.course.discussion_topics = {
            "A": {"id": "non-courseware-1"},
            "B": {"id": "non-courseware-2"},
        }
        modulestore().update_item(self.course, self.user.id)
        self.make_discussion_module("courseware-1", "A", "1")
        self.make_discussion_module("courseware-2", "A", "2")
        self.make_discussion_module("courseware-3", "B", "1")
        self.make_discussion_module("courseware-4", "B", "2")
        self.make_discussion_module("courseware-5", "C", "1")
        actual = self.get_course_topics()
        expected = {
            "courseware_topics": [
                self.make_expected_tree(
                    ["courseware-1", "courseware-2"],
                    "A",
                    [
                        self.make_expected_tree(["courseware-1"], "1"),
                        self.make_expected_tree(["courseware-2"], "2"),
                    ]
                ),
                self.make_expected_tree(
                    ["courseware-3", "courseware-4"],
                    "B",
                    [
                        self.make_expected_tree(["courseware-3"], "1"),
                        self.make_expected_tree(["courseware-4"], "2"),
                    ]
                ),
                self.make_expected_tree(
                    ["courseware-5"],
                    "C",
                    [self.make_expected_tree(["courseware-5"], "1")]
                ),
            ],
            "non_courseware_topics": [
                self.make_expected_tree(["non-courseware-1"], "A"),
                self.make_expected_tree(["non-courseware-2"], "B"),
            ],
        }
        self.assertEqual(actual, expected)

    def test_sort_key(self):
        self.course.discussion_topics = {
            "W": {"id": "non-courseware-1", "sort_key": "Z"},
            "X": {"id": "non-courseware-2"},
            "Y": {"id": "non-courseware-3", "sort_key": "Y"},
            "Z": {"id": "non-courseware-4", "sort_key": "W"},
        }
        modulestore().update_item(self.course, self.user.id)
        self.make_discussion_module("courseware-1", "First", "A", sort_key="D")
        self.make_discussion_module("courseware-2", "First", "B", sort_key="B")
        self.make_discussion_module("courseware-3", "First", "C", sort_key="E")
        self.make_discussion_module("courseware-4", "Second", "A", sort_key="F")
        self.make_discussion_module("courseware-5", "Second", "B", sort_key="G")
        self.make_discussion_module("courseware-6", "Second", "C")
        self.make_discussion_module("courseware-7", "Second", "D", sort_key="A")
        actual = self.get_course_topics()
        expected = {
            "courseware_topics": [
                self.make_expected_tree(
                    ["courseware-1", "courseware-2", "courseware-3"],
                    "First",
                    [
                        self.make_expected_tree(["courseware-2"], "B"),
                        self.make_expected_tree(["courseware-1"], "A"),
                        self.make_expected_tree(["courseware-3"], "C"),
                    ]
                ),
                self.make_expected_tree(
                    ["courseware-4", "courseware-5", "courseware-6", "courseware-7"],
                    "Second",
                    [
                        self.make_expected_tree(["courseware-7"], "D"),
                        self.make_expected_tree(["courseware-6"], "C"),
                        self.make_expected_tree(["courseware-4"], "A"),
                        self.make_expected_tree(["courseware-5"], "B"),
                    ]
                ),
            ],
            "non_courseware_topics": [
                self.make_expected_tree(["non-courseware-4"], "Z"),
                self.make_expected_tree(["non-courseware-2"], "X"),
                self.make_expected_tree(["non-courseware-3"], "Y"),
                self.make_expected_tree(["non-courseware-1"], "W"),
            ],
        }
        self.assertEqual(actual, expected)

    def test_access_control(self):
        """
        Test that only topics that a user has access to are returned. The
        ways in which a user may not have access are:

        * Module is visible to staff only
        * Module has a start date in the future
        * Module is accessible only to a group the user is not in

        Also, there is a case that ensures that a category with no accessible
        subcategories does not appear in the result.
        """
        beta_tester = BetaTesterFactory.create(course_key=self.course.id)
        CourseEnrollmentFactory.create(user=beta_tester, course_id=self.course.id)
        staff = StaffFactory.create(course_key=self.course.id)
        for user, group_idx in [(self.user, 0), (beta_tester, 1)]:
            cohort = CohortFactory.create(
                course_id=self.course.id,
                name=self.partition.groups[group_idx].name,
                users=[user]
            )
            CourseUserGroupPartitionGroup.objects.create(
                course_user_group=cohort,
                partition_id=self.partition.id,
                group_id=self.partition.groups[group_idx].id
            )

        self.make_discussion_module("courseware-1", "First", "Everybody")
        self.make_discussion_module(
            "courseware-2",
            "First",
            "Cohort A",
            group_access={self.partition.id: [self.partition.groups[0].id]}
        )
        self.make_discussion_module(
            "courseware-3",
            "First",
            "Cohort B",
            group_access={self.partition.id: [self.partition.groups[1].id]}
        )
        self.make_discussion_module("courseware-4", "Second", "Staff Only", visible_to_staff_only=True)
        self.make_discussion_module(
            "courseware-5",
            "Second",
            "Future Start Date",
            start=datetime.now(UTC) + timedelta(days=1)
        )

        student_actual = self.get_course_topics()
        student_expected = {
            "courseware_topics": [
                self.make_expected_tree(
                    ["courseware-1", "courseware-2"],
                    "First",
                    [
                        self.make_expected_tree(["courseware-2"], "Cohort A"),
                        self.make_expected_tree(["courseware-1"], "Everybody"),
                    ]
                ),
            ],
            "non_courseware_topics": [
                self.make_expected_tree(["non-courseware-topic-id"], "Test Topic"),
            ],
        }
        self.assertEqual(student_actual, student_expected)
        self.request.user = beta_tester
        beta_actual = self.get_course_topics()
        beta_expected = {
            "courseware_topics": [
                self.make_expected_tree(
                    ["courseware-1", "courseware-3"],
                    "First",
                    [
                        self.make_expected_tree(["courseware-3"], "Cohort B"),
                        self.make_expected_tree(["courseware-1"], "Everybody"),
                    ]
                ),
                self.make_expected_tree(
                    ["courseware-5"],
                    "Second",
                    [self.make_expected_tree(["courseware-5"], "Future Start Date")]
                ),
            ],
            "non_courseware_topics": [
                self.make_expected_tree(["non-courseware-topic-id"], "Test Topic"),
            ],
        }
        self.assertEqual(beta_actual, beta_expected)

        self.request.user = staff
        staff_actual = self.get_course_topics()
        staff_expected = {
            "courseware_topics": [
                self.make_expected_tree(
                    ["courseware-1", "courseware-2", "courseware-3"],
                    "First",
                    [
                        self.make_expected_tree(["courseware-2"], "Cohort A"),
                        self.make_expected_tree(["courseware-3"], "Cohort B"),
                        self.make_expected_tree(["courseware-1"], "Everybody"),
                    ]
                ),
                self.make_expected_tree(
                    ["courseware-4", "courseware-5"],
                    "Second",
                    [
                        self.make_expected_tree(["courseware-5"], "Future Start Date"),
                        self.make_expected_tree(["courseware-4"], "Staff Only"),
                    ]
                ),
            ],
            "non_courseware_topics": [
                self.make_expected_tree(["non-courseware-topic-id"], "Test Topic"),
            ],
        }
        self.assertEqual(staff_actual, staff_expected)


@ddt.ddt
class GetThreadListTest(CommentsServiceMockMixin, UrlResetMixin, ModuleStoreTestCase):
    """Test for get_thread_list"""
    @mock.patch.dict("django.conf.settings.FEATURES", {"ENABLE_DISCUSSION_SERVICE": True})
    def setUp(self):
        super(GetThreadListTest, self).setUp()
        httpretty.reset()
        httpretty.enable()
        self.addCleanup(httpretty.disable)
        self.maxDiff = None  # pylint: disable=invalid-name
        self.user = UserFactory.create()
        self.register_get_user_response(self.user)
        self.request = RequestFactory().get("/test_path")
        self.request.user = self.user
        self.course = CourseFactory.create()
        CourseEnrollmentFactory.create(user=self.user, course_id=self.course.id)
        self.author = UserFactory.create()
        self.cohort = CohortFactory.create(course_id=self.course.id)

    def get_thread_list(self, threads, page=1, page_size=1, num_pages=1, course=None, topic_id_list=None):
        """
        Register the appropriate comments service response, then call
        get_thread_list and return the result.
        """
        course = course or self.course
        self.register_get_threads_response(threads, page, num_pages)
        ret = get_thread_list(self.request, course.id, page, page_size, topic_id_list)
        return ret

    def test_nonexistent_course(self):
        with self.assertRaises(Http404):
            get_thread_list(self.request, CourseLocator.from_string("non/existent/course"), 1, 1)

    def test_not_enrolled(self):
        self.request.user = UserFactory.create()
        with self.assertRaises(Http404):
            self.get_thread_list([])

    def test_discussions_disabled(self):
        _remove_discussion_tab(self.course, self.user.id)
        with self.assertRaises(Http404):
            self.get_thread_list([])

    def test_empty(self):
        self.assertEqual(
            self.get_thread_list([]),
            {
                "results": [],
                "next": None,
                "previous": None,
            }
        )

    def test_get_threads_by_topic_id(self):
        self.get_thread_list([])
        self.assertEqual(urlparse(httpretty.last_request().path).path, "/api/v1/threads")

    def test_basic_query_params(self):
        self.get_thread_list([], page=6, page_size=14)
        self.assert_last_query_params({
            "course_id": [unicode(self.course.id)],
            "sort_key": ["date"],
            "sort_order": ["desc"],
            "page": ["6"],
            "per_page": ["14"],
            "recursive": ["False"],
        })

    def test_thread_content(self):
        source_threads = [
            {
                "id": "test_thread_id_0",
                "course_id": unicode(self.course.id),
                "commentable_id": "topic_x",
                "group_id": None,
                "user_id": str(self.author.id),
                "username": self.author.username,
                "anonymous": False,
                "anonymous_to_peers": False,
                "created_at": "2015-04-28T00:00:00Z",
                "updated_at": "2015-04-28T11:11:11Z",
                "thread_type": "discussion",
                "title": "Test Title",
                "body": "Test body",
                "pinned": False,
                "closed": False,
                "abuse_flaggers": [],
                "votes": {"up_count": 4},
                "comments_count": 5,
                "unread_comments_count": 3,
            },
            {
                "id": "test_thread_id_1",
                "course_id": unicode(self.course.id),
                "commentable_id": "topic_y",
                "group_id": self.cohort.id,
                "user_id": str(self.author.id),
                "username": self.author.username,
                "anonymous": False,
                "anonymous_to_peers": False,
                "created_at": "2015-04-28T22:22:22Z",
                "updated_at": "2015-04-28T00:33:33Z",
                "thread_type": "question",
                "title": "Another Test Title",
                "body": "More content",
                "pinned": False,
                "closed": True,
                "abuse_flaggers": [],
                "votes": {"up_count": 9},
                "comments_count": 18,
                "unread_comments_count": 0,
            },
        ]
        expected_threads = [
            {
                "id": "test_thread_id_0",
                "course_id": unicode(self.course.id),
                "topic_id": "topic_x",
                "group_id": None,
                "group_name": None,
                "author": self.author.username,
                "author_label": None,
                "created_at": "2015-04-28T00:00:00Z",
                "updated_at": "2015-04-28T11:11:11Z",
                "type": "discussion",
                "title": "Test Title",
                "raw_body": "Test body",
                "pinned": False,
                "closed": False,
                "following": False,
                "abuse_flagged": False,
                "voted": False,
                "vote_count": 4,
                "comment_count": 5,
                "unread_comment_count": 3,
                "comment_list_url": "http://testserver/api/discussion/v1/comments/?thread_id=test_thread_id_0",
                "endorsed_comment_list_url": None,
                "non_endorsed_comment_list_url": None,
            },
            {
                "id": "test_thread_id_1",
                "course_id": unicode(self.course.id),
                "topic_id": "topic_y",
                "group_id": self.cohort.id,
                "group_name": self.cohort.name,
                "author": self.author.username,
                "author_label": None,
                "created_at": "2015-04-28T22:22:22Z",
                "updated_at": "2015-04-28T00:33:33Z",
                "type": "question",
                "title": "Another Test Title",
                "raw_body": "More content",
                "pinned": False,
                "closed": True,
                "following": False,
                "abuse_flagged": False,
                "voted": False,
                "vote_count": 9,
                "comment_count": 18,
                "unread_comment_count": 0,
                "comment_list_url": None,
                "endorsed_comment_list_url": (
                    "http://testserver/api/discussion/v1/comments/?thread_id=test_thread_id_1&endorsed=True"
                ),
                "non_endorsed_comment_list_url": (
                    "http://testserver/api/discussion/v1/comments/?thread_id=test_thread_id_1&endorsed=False"
                ),
            },
        ]
        self.assertEqual(
            self.get_thread_list(source_threads),
            {
                "results": expected_threads,
                "next": None,
                "previous": None,
            }
        )

    @ddt.data(
        *itertools.product(
            [
                FORUM_ROLE_ADMINISTRATOR,
                FORUM_ROLE_MODERATOR,
                FORUM_ROLE_COMMUNITY_TA,
                FORUM_ROLE_STUDENT,
            ],
            [True, False]
        )
    )
    @ddt.unpack
    def test_request_group(self, role_name, course_is_cohorted):
        cohort_course = CourseFactory.create(cohort_config={"cohorted": course_is_cohorted})
        CourseEnrollmentFactory.create(user=self.user, course_id=cohort_course.id)
        CohortFactory.create(course_id=cohort_course.id, users=[self.user])
        role = Role.objects.create(name=role_name, course_id=cohort_course.id)
        role.users = [self.user]
        self.get_thread_list([], course=cohort_course)
        actual_has_group = "group_id" in httpretty.last_request().querystring
        expected_has_group = (course_is_cohorted and role_name == FORUM_ROLE_STUDENT)
        self.assertEqual(actual_has_group, expected_has_group)

    def test_pagination(self):
        # N.B. Empty thread list is not realistic but convenient for this test
        self.assertEqual(
            self.get_thread_list([], page=1, num_pages=3),
            {
                "results": [],
                "next": "http://testserver/test_path?page=2",
                "previous": None,
            }
        )
        self.assertEqual(
            self.get_thread_list([], page=2, num_pages=3),
            {
                "results": [],
                "next": "http://testserver/test_path?page=3",
                "previous": "http://testserver/test_path?page=1",
            }
        )
        self.assertEqual(
            self.get_thread_list([], page=3, num_pages=3),
            {
                "results": [],
                "next": None,
                "previous": "http://testserver/test_path?page=2",
            }
        )

        # Test page past the last one
        self.register_get_threads_response([], page=3, num_pages=3)
        with self.assertRaises(Http404):
            get_thread_list(self.request, self.course.id, page=4, page_size=10)


@ddt.ddt
class GetCommentListTest(CommentsServiceMockMixin, ModuleStoreTestCase):
    """Test for get_comment_list"""
    def setUp(self):
        super(GetCommentListTest, self).setUp()
        httpretty.reset()
        httpretty.enable()
        self.addCleanup(httpretty.disable)
        self.maxDiff = None  # pylint: disable=invalid-name
        self.user = UserFactory.create()
        self.register_get_user_response(self.user)
        self.request = RequestFactory().get("/test_path")
        self.request.user = self.user
        self.course = CourseFactory.create()
        CourseEnrollmentFactory.create(user=self.user, course_id=self.course.id)
        self.author = UserFactory.create()

    def make_minimal_cs_thread(self, overrides=None):
        """
        Create a thread with the given overrides, plus the course_id if not
        already in overrides.
        """
        overrides = overrides.copy() if overrides else {}
        overrides.setdefault("course_id", unicode(self.course.id))
        return make_minimal_cs_thread(overrides)

    def get_comment_list(self, thread, endorsed=None, page=1, page_size=1):
        """
        Register the appropriate comments service response, then call
        get_comment_list and return the result.
        """
        self.register_get_thread_response(thread)
        return get_comment_list(self.request, thread["id"], endorsed, page, page_size)

    def test_nonexistent_thread(self):
        thread_id = "nonexistent_thread"
        self.register_get_thread_error_response(thread_id, 404)
        with self.assertRaises(Http404):
            get_comment_list(self.request, thread_id, endorsed=False, page=1, page_size=1)

    def test_nonexistent_course(self):
        with self.assertRaises(Http404):
            self.get_comment_list(self.make_minimal_cs_thread({"course_id": "non/existent/course"}))

    def test_not_enrolled(self):
        self.request.user = UserFactory.create()
        with self.assertRaises(Http404):
            self.get_comment_list(self.make_minimal_cs_thread())

    def test_discussions_disabled(self):
        _remove_discussion_tab(self.course, self.user.id)
        with self.assertRaises(Http404):
            self.get_comment_list(self.make_minimal_cs_thread())

    @ddt.data(
        *itertools.product(
            [
                FORUM_ROLE_ADMINISTRATOR,
                FORUM_ROLE_MODERATOR,
                FORUM_ROLE_COMMUNITY_TA,
                FORUM_ROLE_STUDENT,
            ],
            [True, False],
            ["no_group", "match_group", "different_group"],
        )
    )
    @ddt.unpack
    def test_group_access(self, role_name, course_is_cohorted, thread_group_state):
        cohort_course = CourseFactory.create(cohort_config={"cohorted": course_is_cohorted})
        CourseEnrollmentFactory.create(user=self.user, course_id=cohort_course.id)
        cohort = CohortFactory.create(course_id=cohort_course.id, users=[self.user])
        role = Role.objects.create(name=role_name, course_id=cohort_course.id)
        role.users = [self.user]
        thread = self.make_minimal_cs_thread({
            "course_id": unicode(cohort_course.id),
            "group_id": (
                None if thread_group_state == "no_group" else
                cohort.id if thread_group_state == "match_group" else
                cohort.id + 1
            ),
        })
        expected_error = (
            role_name == FORUM_ROLE_STUDENT and
            course_is_cohorted and
            thread_group_state == "different_group"
        )
        try:
            self.get_comment_list(thread)
            self.assertFalse(expected_error)
        except Http404:
            self.assertTrue(expected_error)

    @ddt.data(True, False)
    def test_discussion_endorsed(self, endorsed_value):
        with self.assertRaises(ValidationError) as assertion:
            self.get_comment_list(
                self.make_minimal_cs_thread({"thread_type": "discussion"}),
                endorsed=endorsed_value
            )
        self.assertEqual(
            assertion.exception.message_dict,
            {"endorsed": ["This field may not be specified for discussion threads."]}
        )

    def test_question_without_endorsed(self):
        with self.assertRaises(ValidationError) as assertion:
            self.get_comment_list(
                self.make_minimal_cs_thread({"thread_type": "question"}),
                endorsed=None
            )
        self.assertEqual(
            assertion.exception.message_dict,
            {"endorsed": ["This field is required for question threads."]}
        )

    def test_empty(self):
        discussion_thread = self.make_minimal_cs_thread(
            {"thread_type": "discussion", "children": [], "resp_total": 0}
        )
        self.assertEqual(
            self.get_comment_list(discussion_thread),
            {"results": [], "next": None, "previous": None}
        )

        question_thread = self.make_minimal_cs_thread({
            "thread_type": "question",
            "endorsed_responses": [],
            "non_endorsed_responses": [],
            "non_endorsed_resp_total": 0
        })
        self.assertEqual(
            self.get_comment_list(question_thread, endorsed=False),
            {"results": [], "next": None, "previous": None}
        )
        self.assertEqual(
            self.get_comment_list(question_thread, endorsed=True),
            {"results": [], "next": None, "previous": None}
        )

    def test_basic_query_params(self):
        self.get_comment_list(
            self.make_minimal_cs_thread({
                "children": [make_minimal_cs_comment()],
                "resp_total": 71
            }),
            page=6,
            page_size=14
        )
        self.assert_query_params_equal(
            httpretty.httpretty.latest_requests[-2],
            {
                "recursive": ["True"],
                "user_id": [str(self.user.id)],
                "mark_as_read": ["True"],
                "resp_skip": ["70"],
                "resp_limit": ["14"],
            }
        )

    def test_discussion_content(self):
        source_comments = [
            {
                "id": "test_comment_1",
                "thread_id": "test_thread",
                "user_id": str(self.author.id),
                "username": self.author.username,
                "anonymous": False,
                "anonymous_to_peers": False,
                "created_at": "2015-05-11T00:00:00Z",
                "updated_at": "2015-05-11T11:11:11Z",
                "body": "Test body",
                "endorsed": False,
                "abuse_flaggers": [],
                "votes": {"up_count": 4},
                "children": [],
            },
            {
                "id": "test_comment_2",
                "thread_id": "test_thread",
                "user_id": str(self.author.id),
                "username": self.author.username,
                "anonymous": True,
                "anonymous_to_peers": False,
                "created_at": "2015-05-11T22:22:22Z",
                "updated_at": "2015-05-11T33:33:33Z",
                "body": "More content",
                "endorsed": False,
                "abuse_flaggers": [str(self.user.id)],
                "votes": {"up_count": 7},
                "children": [],
            }
        ]
        expected_comments = [
            {
                "id": "test_comment_1",
                "thread_id": "test_thread",
                "parent_id": None,
                "author": self.author.username,
                "author_label": None,
                "created_at": "2015-05-11T00:00:00Z",
                "updated_at": "2015-05-11T11:11:11Z",
                "raw_body": "Test body",
                "endorsed": False,
                "endorsed_by": None,
                "endorsed_by_label": None,
                "endorsed_at": None,
                "abuse_flagged": False,
                "voted": False,
                "vote_count": 4,
                "children": [],
            },
            {
                "id": "test_comment_2",
                "thread_id": "test_thread",
                "parent_id": None,
                "author": None,
                "author_label": None,
                "created_at": "2015-05-11T22:22:22Z",
                "updated_at": "2015-05-11T33:33:33Z",
                "raw_body": "More content",
                "endorsed": False,
                "endorsed_by": None,
                "endorsed_by_label": None,
                "endorsed_at": None,
                "abuse_flagged": True,
                "voted": False,
                "vote_count": 7,
                "children": [],
            },
        ]
        actual_comments = self.get_comment_list(
            self.make_minimal_cs_thread({"children": source_comments})
        )["results"]
        self.assertEqual(actual_comments, expected_comments)

    def test_question_content(self):
        thread = self.make_minimal_cs_thread({
            "thread_type": "question",
            "endorsed_responses": [make_minimal_cs_comment({"id": "endorsed_comment"})],
            "non_endorsed_responses": [make_minimal_cs_comment({"id": "non_endorsed_comment"})],
            "non_endorsed_resp_total": 1,
        })

        endorsed_actual = self.get_comment_list(thread, endorsed=True)
        self.assertEqual(endorsed_actual["results"][0]["id"], "endorsed_comment")

        non_endorsed_actual = self.get_comment_list(thread, endorsed=False)
        self.assertEqual(non_endorsed_actual["results"][0]["id"], "non_endorsed_comment")

    def test_endorsed_by_anonymity(self):
        """
        Ensure thread anonymity is properly considered in serializing
        endorsed_by.
        """
        thread = self.make_minimal_cs_thread({
            "anonymous": True,
            "children": [
                make_minimal_cs_comment({
                    "endorsement": {"user_id": str(self.author.id), "time": "2015-05-18T12:34:56Z"}
                })
            ]
        })
        actual_comments = self.get_comment_list(thread)["results"]
        self.assertIsNone(actual_comments[0]["endorsed_by"])

    @ddt.data(
        ("discussion", None, "children", "resp_total"),
        ("question", False, "non_endorsed_responses", "non_endorsed_resp_total"),
    )
    @ddt.unpack
    def test_cs_pagination(self, thread_type, endorsed_arg, response_field, response_total_field):
        """
        Test cases in which pagination is done by the comments service.

        thread_type is the type of thread (question or discussion).
        endorsed_arg is the value of the endorsed argument.
        repsonse_field is the field in which responses are returned for the
          given thread type.
        response_total_field is the field in which the total number of responses
          is returned for the given thread type.
        """
        # N.B. The mismatch between the number of children and the listed total
        # number of responses is unrealistic but convenient for this test
        thread = self.make_minimal_cs_thread({
            "thread_type": thread_type,
            response_field: [make_minimal_cs_comment()],
            response_total_field: 5,
        })

        # Only page
        actual = self.get_comment_list(thread, endorsed=endorsed_arg, page=1, page_size=5)
        self.assertIsNone(actual["next"])
        self.assertIsNone(actual["previous"])

        # First page of many
        actual = self.get_comment_list(thread, endorsed=endorsed_arg, page=1, page_size=2)
        self.assertEqual(actual["next"], "http://testserver/test_path?page=2")
        self.assertIsNone(actual["previous"])

        # Middle page of many
        actual = self.get_comment_list(thread, endorsed=endorsed_arg, page=2, page_size=2)
        self.assertEqual(actual["next"], "http://testserver/test_path?page=3")
        self.assertEqual(actual["previous"], "http://testserver/test_path?page=1")

        # Last page of many
        actual = self.get_comment_list(thread, endorsed=endorsed_arg, page=3, page_size=2)
        self.assertIsNone(actual["next"])
        self.assertEqual(actual["previous"], "http://testserver/test_path?page=2")

        # Page past the end
        thread = self.make_minimal_cs_thread({
            "thread_type": thread_type,
            response_field: [],
            response_total_field: 5
        })
        with self.assertRaises(Http404):
            self.get_comment_list(thread, endorsed=endorsed_arg, page=2, page_size=5)

    def test_question_endorsed_pagination(self):
        thread = self.make_minimal_cs_thread({
            "thread_type": "question",
            "endorsed_responses": [
                make_minimal_cs_comment({"id": "comment_{}".format(i)}) for i in range(10)
            ]
        })

        def assert_page_correct(page, page_size, expected_start, expected_stop, expected_next, expected_prev):
            """
            Check that requesting the given page/page_size returns the expected
            output
            """
            actual = self.get_comment_list(thread, endorsed=True, page=page, page_size=page_size)
            result_ids = [result["id"] for result in actual["results"]]
            self.assertEqual(
                result_ids,
                ["comment_{}".format(i) for i in range(expected_start, expected_stop)]
            )
            self.assertEqual(
                actual["next"],
                "http://testserver/test_path?page={}".format(expected_next) if expected_next else None
            )
            self.assertEqual(
                actual["previous"],
                "http://testserver/test_path?page={}".format(expected_prev) if expected_prev else None
            )

        # Only page
        assert_page_correct(
            page=1,
            page_size=10,
            expected_start=0,
            expected_stop=10,
            expected_next=None,
            expected_prev=None
        )

        # First page of many
        assert_page_correct(
            page=1,
            page_size=4,
            expected_start=0,
            expected_stop=4,
            expected_next=2,
            expected_prev=None
        )

        # Middle page of many
        assert_page_correct(
            page=2,
            page_size=4,
            expected_start=4,
            expected_stop=8,
            expected_next=3,
            expected_prev=1
        )

        # Last page of many
        assert_page_correct(
            page=3,
            page_size=4,
            expected_start=8,
            expected_stop=10,
            expected_next=None,
            expected_prev=2
        )

        # Page past the end
        with self.assertRaises(Http404):
            self.get_comment_list(thread, endorsed=True, page=2, page_size=10)


class CreateThreadTest(CommentsServiceMockMixin, UrlResetMixin, ModuleStoreTestCase):
    """Tests for create_thread"""
    @mock.patch.dict("django.conf.settings.FEATURES", {"ENABLE_DISCUSSION_SERVICE": True})
    def setUp(self):
        super(CreateThreadTest, self).setUp()
        httpretty.reset()
        httpretty.enable()
        self.addCleanup(httpretty.disable)
        self.user = UserFactory.create()
        self.register_get_user_response(self.user)
        self.request = RequestFactory().get("/test_path")
        self.request.user = self.user
        self.course = CourseFactory.create()
        CourseEnrollmentFactory.create(user=self.user, course_id=self.course.id)
        self.minimal_data = {
            "course_id": unicode(self.course.id),
            "topic_id": "test_topic",
            "type": "discussion",
            "title": "Test Title",
            "raw_body": "Test body",
        }

    @mock.patch("eventtracking.tracker.emit")
    def test_basic(self, mock_emit):
        self.register_post_thread_response({
            "id": "test_id",
            "username": self.user.username,
            "created_at": "2015-05-19T00:00:00Z",
            "updated_at": "2015-05-19T00:00:00Z",
        })
        actual = create_thread(self.request, self.minimal_data)
        expected = {
            "id": "test_id",
            "course_id": unicode(self.course.id),
            "topic_id": "test_topic",
            "group_id": None,
            "group_name": None,
            "author": self.user.username,
            "author_label": None,
            "created_at": "2015-05-19T00:00:00Z",
            "updated_at": "2015-05-19T00:00:00Z",
            "type": "discussion",
            "title": "Test Title",
            "raw_body": "Test body",
            "pinned": False,
            "closed": False,
            "following": False,
            "abuse_flagged": False,
            "voted": False,
            "vote_count": 0,
            "comment_count": 0,
            "unread_comment_count": 0,
            "comment_list_url": "http://testserver/api/discussion/v1/comments/?thread_id=test_id",
            "endorsed_comment_list_url": None,
            "non_endorsed_comment_list_url": None,
        }
        self.assertEqual(actual, expected)
        self.assertEqual(
            httpretty.last_request().parsed_body,
            {
                "course_id": [unicode(self.course.id)],
                "commentable_id": ["test_topic"],
                "thread_type": ["discussion"],
                "title": ["Test Title"],
                "body": ["Test body"],
                "user_id": [str(self.user.id)],
            }
        )
        event_name, event_data = mock_emit.call_args[0]
        self.assertEqual(event_name, "edx.forum.thread.created")
        self.assertEqual(
            event_data,
            {
                "commentable_id": "test_topic",
                "group_id": None,
                "thread_type": "discussion",
                "title": "Test Title",
                "anonymous": False,
                "anonymous_to_peers": False,
                "options": {"followed": False},
                "id": "test_id",
                "truncated": False,
                "body": "Test body",
                "url": "",
                "user_forums_roles": [FORUM_ROLE_STUDENT],
                "user_course_roles": [],
            }
        )

    def test_following(self):
        self.register_post_thread_response({"id": "test_id"})
        self.register_subscription_response(self.user)
        data = self.minimal_data.copy()
        data["following"] = "True"
        result = create_thread(self.request, data)
        self.assertEqual(result["following"], True)
        cs_request = httpretty.last_request()
        self.assertEqual(
            urlparse(cs_request.path).path,
            "/api/v1/users/{}/subscriptions".format(self.user.id)
        )
        self.assertEqual(
            cs_request.parsed_body,
            {"source_type": ["thread"], "source_id": ["test_id"]}
        )

    def test_course_id_missing(self):
        with self.assertRaises(ValidationError) as assertion:
            create_thread(self.request, {})
        self.assertEqual(assertion.exception.message_dict, {"course_id": ["This field is required."]})

    def test_course_id_invalid(self):
        with self.assertRaises(ValidationError) as assertion:
            create_thread(self.request, {"course_id": "invalid!"})
        self.assertEqual(assertion.exception.message_dict, {"course_id": ["Invalid value."]})

    def test_nonexistent_course(self):
        with self.assertRaises(ValidationError) as assertion:
            create_thread(self.request, {"course_id": "non/existent/course"})
        self.assertEqual(assertion.exception.message_dict, {"course_id": ["Invalid value."]})

    def test_not_enrolled(self):
        self.request.user = UserFactory.create()
        with self.assertRaises(ValidationError) as assertion:
            create_thread(self.request, self.minimal_data)
        self.assertEqual(assertion.exception.message_dict, {"course_id": ["Invalid value."]})

    def test_discussions_disabled(self):
        _remove_discussion_tab(self.course, self.user.id)
        with self.assertRaises(ValidationError) as assertion:
            create_thread(self.request, self.minimal_data)
        self.assertEqual(assertion.exception.message_dict, {"course_id": ["Invalid value."]})

    def test_invalid_field(self):
        data = self.minimal_data.copy()
        data["type"] = "invalid_type"
        with self.assertRaises(ValidationError):
            create_thread(self.request, data)


@ddt.ddt
class CreateCommentTest(CommentsServiceMockMixin, UrlResetMixin, ModuleStoreTestCase):
    """Tests for create_comment"""
    @mock.patch.dict("django.conf.settings.FEATURES", {"ENABLE_DISCUSSION_SERVICE": True})
    def setUp(self):
        super(CreateCommentTest, self).setUp()
        httpretty.reset()
        httpretty.enable()
        self.addCleanup(httpretty.disable)
        self.user = UserFactory.create()
        self.register_get_user_response(self.user)
        self.request = RequestFactory().get("/test_path")
        self.request.user = self.user
        self.course = CourseFactory.create()
        CourseEnrollmentFactory.create(user=self.user, course_id=self.course.id)
        self.register_get_thread_response(
            make_minimal_cs_thread({
                "id": "test_thread",
                "course_id": unicode(self.course.id),
                "commentable_id": "test_topic",
            })
        )
        self.minimal_data = {
            "thread_id": "test_thread",
            "raw_body": "Test body",
        }

    @ddt.data(None, "test_parent")
    @mock.patch("eventtracking.tracker.emit")
    def test_success(self, parent_id, mock_emit):
        if parent_id:
            self.register_get_comment_response({"id": parent_id, "thread_id": "test_thread"})
        self.register_post_comment_response(
            {
                "id": "test_comment",
                "thread_id": "test_thread",
                "username": self.user.username,
                "created_at": "2015-05-27T00:00:00Z",
                "updated_at": "2015-05-27T00:00:00Z",
            },
            thread_id=(None if parent_id else "test_thread"),
            parent_id=parent_id
        )
        data = self.minimal_data.copy()
        if parent_id:
            data["parent_id"] = parent_id
        actual = create_comment(self.request, data)
        expected = {
            "id": "test_comment",
            "thread_id": "test_thread",
            "parent_id": parent_id,
            "author": self.user.username,
            "author_label": None,
            "created_at": "2015-05-27T00:00:00Z",
            "updated_at": "2015-05-27T00:00:00Z",
            "raw_body": "Test body",
            "endorsed": False,
            "endorsed_by": None,
            "endorsed_by_label": None,
            "endorsed_at": None,
            "abuse_flagged": False,
            "voted": False,
            "vote_count": 0,
            "children": [],
        }
        self.assertEqual(actual, expected)
        expected_url = (
            "/api/v1/comments/{}".format(parent_id) if parent_id else
            "/api/v1/threads/test_thread/comments"
        )
        self.assertEqual(
            urlparse(httpretty.last_request().path).path,
            expected_url
        )
        self.assertEqual(
            httpretty.last_request().parsed_body,
            {
                "course_id": [unicode(self.course.id)],
                "body": ["Test body"],
                "user_id": [str(self.user.id)]
            }
        )
        expected_event_name = (
            "edx.forum.comment.created" if parent_id else
            "edx.forum.response.created"
        )
        expected_event_data = {
            "discussion": {"id": "test_thread"},
            "commentable_id": "test_topic",
            "options": {"followed": False},
            "id": "test_comment",
            "truncated": False,
            "body": "Test body",
            "url": "",
            "user_forums_roles": [FORUM_ROLE_STUDENT],
            "user_course_roles": [],
        }
        if parent_id:
            expected_event_data["response"] = {"id": parent_id}
        actual_event_name, actual_event_data = mock_emit.call_args[0]
        self.assertEqual(actual_event_name, expected_event_name)
        self.assertEqual(actual_event_data, expected_event_data)

    def test_thread_id_missing(self):
        with self.assertRaises(ValidationError) as assertion:
            create_comment(self.request, {})
        self.assertEqual(assertion.exception.message_dict, {"thread_id": ["This field is required."]})

    def test_thread_id_not_found(self):
        self.register_get_thread_error_response("test_thread", 404)
        with self.assertRaises(ValidationError) as assertion:
            create_comment(self.request, self.minimal_data)
        self.assertEqual(assertion.exception.message_dict, {"thread_id": ["Invalid value."]})

    def test_nonexistent_course(self):
        self.register_get_thread_response(
            make_minimal_cs_thread({"id": "test_thread", "course_id": "non/existent/course"})
        )
        with self.assertRaises(ValidationError) as assertion:
            create_comment(self.request, self.minimal_data)
        self.assertEqual(assertion.exception.message_dict, {"thread_id": ["Invalid value."]})

    def test_not_enrolled(self):
        self.request.user = UserFactory.create()
        with self.assertRaises(ValidationError) as assertion:
            create_comment(self.request, self.minimal_data)
        self.assertEqual(assertion.exception.message_dict, {"thread_id": ["Invalid value."]})

    def test_discussions_disabled(self):
        _remove_discussion_tab(self.course, self.user.id)
        with self.assertRaises(ValidationError) as assertion:
            create_comment(self.request, self.minimal_data)
        self.assertEqual(assertion.exception.message_dict, {"thread_id": ["Invalid value."]})

    def test_invalid_field(self):
        data = self.minimal_data.copy()
        del data["raw_body"]
        with self.assertRaises(ValidationError):
            create_comment(self.request, data)
