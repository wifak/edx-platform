"""
Tests for Bookmarks models.
"""
import ddt

from opaque_keys.edx.locator import CourseLocator, BlockUsageLocator

from bookmarks.models import Bookmark, XBlockCache
from student.tests.factories import UserFactory

from xmodule.modulestore.tests.factories import CourseFactory, ItemFactory
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase


class BookmarkModelTest(ModuleStoreTestCase):
    """
    Test the Bookmark model.
    """
    def setUp(self):
        super(BookmarkModelTest, self).setUp()

        self.user = UserFactory.create(password='test')

        self.course = CourseFactory.create(display_name='An Introduction to API Testing')
        self.course_id = unicode(self.course.id)

        self.chapter = ItemFactory.create(
            parent_location=self.course.location, category='chapter', display_name='Week 1'
        )
        self.sequential = ItemFactory.create(
            parent_location=self.chapter.location, category='sequential', display_name='Lesson 1'
        )
        self.vertical = ItemFactory.create(
            parent_location=self.sequential.location, category='vertical', display_name='Subsection 1'
        )
        self.vertical_2 = ItemFactory.create(
            parent_location=self.sequential.location, category='vertical', display_name='Subsection 2'
        )

        self.path = [
            {'display_name': self.chapter.display_name, 'usage_id': unicode(self.chapter.location)},
            {'display_name': self.sequential.display_name, 'usage_id': unicode(self.sequential.location)}
        ]

    def get_bookmark_data(self, block):
        """
        Returns bookmark data for testing.
        """
        return {
            'user': self.user,
            'course_key': self.course.id,
            'usage_key': block.location,
            'display_name': block.display_name,
        }

    def assert_valid_bookmark(self, bookmark_object, bookmark_data):
        """
        Check if the given data matches the specified bookmark.
        """
        self.assertEqual(bookmark_object.user, self.user)
        self.assertEqual(bookmark_object.course_key, bookmark_data['course_key'])
        self.assertEqual(bookmark_object.usage_key, self.vertical.location)
        self.assertEqual(bookmark_object.display_name, bookmark_data['display_name'])
        self.assertEqual(bookmark_object.path, self.path)
        self.assertIsNotNone(bookmark_object.created)

    def test_create_bookmark_success(self):
        """
        Tests creation of bookmark.
        """
        bookmark_data = self.get_bookmark_data(self.vertical)
        bookmark_object = Bookmark.create(bookmark_data)
        self.assert_valid_bookmark(bookmark_object, bookmark_data)


@ddt.ddt
class XBlockCacheModelTest(ModuleStoreTestCase):
    """
    Test the XBlockCache model.
    """

    COURSE_KEY = CourseLocator(org='test', course='test', run='test')
    CHAPTER1_USAGE_KEY = BlockUsageLocator(COURSE_KEY, block_type='chapter', block_id='chapter1')
    SECTION1_USAGE_KEY = BlockUsageLocator(COURSE_KEY, block_type='section', block_id='section1')
    SECTION2_USAGE_KEY = BlockUsageLocator(COURSE_KEY, block_type='section', block_id='section1')
    VERTICAL1_USAGE_KEY = BlockUsageLocator(COURSE_KEY, block_type='vertical', block_id='sequential1')
    PATH1 = [
        {'usage_key': unicode(CHAPTER1_USAGE_KEY), 'display_name': 'Chapter 1'},
        {'usage_key': unicode(SECTION1_USAGE_KEY), 'display_name': 'Section 1'},
    ]
    PATH2 = [
        {'usage_key': unicode(CHAPTER1_USAGE_KEY), 'display_name': 'Chapter 1'},
        {'usage_key': unicode(SECTION2_USAGE_KEY), 'display_name': 'Section 2'},
    ]

    def setUp(self):
        super(XBlockCacheModelTest, self).setUp()

    def assert_xblock_cache_data(self, xblock_cache, data):
        self.assertEqual(xblock_cache.usage_key, data['usage_key'])
        self.assertEqual(xblock_cache.course_key, data['usage_key'].course_key)
        self.assertEqual(xblock_cache.display_name, data['display_name'])

        for index, path in enumerate(data.get('paths', [])):
            for depth, node in enumerate(path):
                self.assertDictEqual(xblock_cache.paths[index][depth], node)

    @ddt.data(
        (
            [
                { 'usage_key': VERTICAL1_USAGE_KEY, },
                { 'display_name': '', 'paths': [], },
            ],
            [
                { 'usage_key': VERTICAL1_USAGE_KEY, 'display_name': 'Vertical 5', 'paths': [ PATH2 ] },
                { 'paths': [ PATH2 ] },
            ],
        ),
        (
            [
                { 'usage_key': VERTICAL1_USAGE_KEY, 'display_name': 'Vertical 4', 'paths': [ PATH1 ] },
                { },
            ],
            [
                { 'usage_key': VERTICAL1_USAGE_KEY, 'display_name': 'Vertical 5', 'paths': [ PATH2 ] },
                { 'paths': [ PATH1, PATH2 ] },
            ],
        ),
    )
    def test_create(self, data):
        """
        Test the the XBlockCache.create constructs and updates objects correctly.
        """
        for create_data, additional_data_to_expect in data:
            xblock_cache = XBlockCache.create(create_data)
            create_data.update(additional_data_to_expect)
            self.assert_xblock_cache_data(xblock_cache, create_data)
