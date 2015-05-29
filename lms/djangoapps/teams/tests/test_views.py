"""Tests for the teams API at the HTTP request level."""
# pylint: disable=maybe-no-member
import json

import ddt

from django.conf import settings
from django.core.urlresolvers import reverse
from rest_framework.test import APITestCase
from unittest import skipUnless

from student.tests.factories import UserFactory
from student.models import CourseEnrollment
from xmodule.modulestore.tests.factories import CourseFactory
from .factories import CourseTeamFactory
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase


@ddt.ddt
class TestTeamAPI(APITestCase, ModuleStoreTestCase):
    """
    Tests of the Team API
    """

    test_password = 'password'

    topics_count = 10

    def setUp(self):
        super(TestTeamAPI, self).setUp()

        teams_configuration = {
            'topics':
            [
                {
                    'id': 'topic_{}'.format(i),
                    'name': 'Topic {}'.format(i),
                    'description': 'Description for topic {}.'.format(i)
                } for i in range(self.topics_count)
            ]
        }

        self.test_course_1 = CourseFactory.create(
            org='TestX',
            course='TS101',
            display_name='Test Course',
            teams_configuration=teams_configuration
        )
        self.test_course_2 = CourseFactory.create(org='MIT', course='6.002x', display_name='Circuits')

        self.student_user = UserFactory.create(password=self.test_password)
        self.student_user_enrolled = UserFactory.create(password=self.test_password)
        self.student_user_not_active = UserFactory.create(password=self.test_password, is_active=False)
        self.staff_user = UserFactory.create(password=self.test_password, is_staff=True)

        self.test_team_1 = CourseTeamFactory.create(
            name='solar team',
            course_id=self.test_course_1.id,
            topic_id='renewable'
        )
        self.test_team_2 = CourseTeamFactory.create(name='Wind Team', course_id=self.test_course_2.id)
        self.test_team_3 = CourseTeamFactory.create(name='Nuclear Team', course_id=self.test_course_1.id)
        self.test_team_4 = CourseTeamFactory.create(name='coal team', course_id=self.test_course_2.id, is_active=False)

        self.test_team_1.add_user(self.student_user)

        CourseEnrollment.get_or_create_enrollment(
            self.student_user_enrolled, self.test_course_1.location.course_key
        )

    def setup_inactive_user(self):
        """
        Creates a user, logs them in, then makes them inactive. Used for testing inactive user permissions.
        """
        test_user = UserFactory.create(password=self.test_password)
        self.client.login(username=test_user.username, password=self.test_password)
        test_user.is_active = False
        test_user.save()

    def get_teams_list(self, expected_status, user=None, data=None):
        """
        Gets the list of teams as the given user with data as query params. Verifies expected_status.
        """
        user = user if user else self.student_user
        self.client.login(username=user.username, password=self.test_password)
        response = self.client.get(reverse('teams_list'), data=data)
        self.assertEqual(expected_status, response.status_code)
        return response

    def get_teams_list_json(self, user=None, data=None):
        """
        Gets the list of teams as the given user with data as query params, returning the result as a dict.
        """
        response = self.get_teams_list(200, user=user, data=data)
        return json.loads(response.content)

    def test_list_teams_anonymous(self):
        response = self.client.get(reverse('teams_list'))
        self.assertEqual(403, response.status_code)

    def test_list_teams_logged_in(self):
        teams = self.get_teams_list_json()
        self.assertEqual(3, teams['count'])

    def test_list_teams_logged_in_not_active(self):
        self.setup_inactive_user()
        response = self.client.get(reverse('teams_list'))
        self.assertEqual(200, response.status_code)

    def test_list_teams_filter_invalid_course_id(self):
        self.get_teams_list(400, data={'course_id': 'foobar'})

    def test_list_teams_filter_course_id(self):
        teams = self.get_teams_list_json(data={'course_id': str(self.test_course_2.id)})
        self.assertEqual(1, teams['count'])
        self.assertEqual(teams['results'][0]['name'], 'Wind Team')

    def test_list_teams_filter_topic_id(self):
        teams = self.get_teams_list_json(data={
            'course_id': str(self.test_course_1.id),
            'topic_id': 'renewable',
        })
        self.assertEqual(1, teams['count'])
        self.assertEqual(teams['results'][0]['name'], 'solar team')

    def test_list_teams_filter_include_inactive(self):
        teams = self.get_teams_list_json(data={'include_inactive': True})
        self.assertEqual(4, teams['count'])

    # Text search is not yet implemented, so this should return HTTP
    # 400 for now
    def test_list_teams_filter_text_search(self):
        self.get_teams_list(400, data={'text_search': 'foobar'})

    def test_list_teams_order_by_name(self):
        teams = self.get_teams_list_json(data={'order_by': 'name'})
        self.assertEqual(3, teams['count'])
        self.assertEqual([team['name'] for team in teams['results']], ['Nuclear Team', 'solar team', 'Wind Team'])

    def test_list_teams_order_by_open_slots(self):
        teams = self.get_teams_list_json(data={'order_by': 'open_slots'})
        self.assertEqual(3, teams['count'])
        self.assertEqual([team['name'] for team in teams['results']], ['Wind Team', 'Nuclear Team', 'solar team'])

    def test_list_teams_order_by_last_activity(self):
        self.get_teams_list(400, data={'order_by': 'last_activity'})

    def test_list_team_no_results(self):
        self.get_teams_list(404, data={'course_id': 'foobar/foobar/foobar'})
        self.get_teams_list(404, data={'topic_id': 'foobar'})

    def build_team_data(self, name="Test team", course=None, description="Filler description", **kwargs):
        """
        Creates the payload for creating a team. kwargs can be used to specify additional fields.
        """
        data = kwargs
        course = course if course else self.test_course_1
        data.update({
            'name': name,
            'course_id': str(course.id),
            'description': description,
        })
        return data

    def post_create_team(self, expected_status, data, user=None):
        """
        Posts data to the team creation endpoint as user. Verifies expected_status.
        """
        user = user if user else self.student_user
        self.client.login(username=user.username, password=self.test_password)
        response = self.client.post(reverse('teams_list'), data=data)
        self.assertEquals(response.status_code, expected_status)
        return response

    def post_create_team_json(self, expected_status, data, user=None):
        """
        Posts data to the team creation endpoint as user. Verifies expected_status and returns the result as a dict.
        """
        response = self.post_create_team(expected_status, data, user=user)
        return json.loads(response.content)

    def test_create_team_anonymous(self):
        response = self.client.post(reverse('teams_list'), self.build_team_data())
        self.assertEquals(403, response.status_code)

    def test_create_team_logged_in_not_active(self):
        self.setup_inactive_user()
        response = self.client.post(reverse('teams_list'), self.build_team_data())
        self.assertEquals(403, response.status_code)

    def test_create_team_logged_in(self):
        new_team = self.post_create_team_json(200, self.build_team_data(name="New Team"))
        self.assertEquals(new_team['id'], 'new-team')

        teams = self.get_teams_list_json()
        self.assertIn("New Team", [team['name'] for team in teams['results']])

    def test_create_team_naming(self):
        new_teams = [
            self.post_create_team_json(200, self.build_team_data(name=name))
            for name in ["The Best Team", "The Best Team", "The Best Team", "The Best Team 2"]
        ]
        self.assertEquals(
            [team['id'] for team in new_teams],
            ['the-best-team', 'the-best-team-2', 'the-best-team-3', 'the-best-team-2-2']
        )

    @ddt.data((400, {
        'name': 'Bad Course Id',
        'course_id': 'foobar',
        'description': "Filler Description"
    }), (404, {
        'name': "Non-existent course id",
        'course_id': 'foobar/foobar/foobar',
        'description': "Filler Description"
    }))
    @ddt.unpack
    def test_create_team_invalid_course_data(self, expected_status, data):
        self.post_create_team(expected_status, data=data)

    def test_create_team_blank_name(self):
        self.post_create_team(400, self.build_team_data(name=""))

    def test_create_team_missing_name(self):
        self.post_create_team(400, {
            'course_id': str(self.test_course_1.id),
            'description': "foobar"
        })

    @ddt.data({'description': '', 'name': 'x' * 1000, 'foobar': 'foobar'})
    def test_create_team_bad_fields(self, kwargs):
        self.post_create_team(400, self.build_team_data(**kwargs))

    def test_create_team_full(self):
        team = self.post_create_team_json(200, self.build_team_data(
            name="Fully specified team",
            course=self.test_course_1,
            description="Another fantastic team",
            topic_id='great-topic',
            country='USA',
            language='English'
        ))

        # Remove date_created because it changes between test runs
        del team['date_created']
        self.assertEquals(team, {
            'name': "Fully specified team",
            'language': "English",
            'country': "USA",
            'is_active': True,
            'membership': [],
            'topic_id': "great-topic",
            'course_id': str(self.test_course_1.id),
            'id': 'fully-specified-team',
            'description': "Another fantastic team",
        })

    def get_team_detail(self, team_id, expected_status, user=None):
        """
        Gets detailed team information for team_id as the given user. Verifies expected_status.
        """
        user = user if user else self.student_user
        self.client.login(username=user.username, password=self.test_password)
        response = self.client.get(reverse('teams_detail', args=[team_id]))
        self.assertEquals(response.status_code, expected_status)
        return response

    def get_team_detail_json(self, team_id, expected_status, user=None):
        """
        Gets detailed team information for team_id as the given user, returning the result as a dict.
        """
        response = self.get_team_detail(team_id, expected_status, user=user)
        return json.loads(response.content)

    def test_detail_team_anonymous(self):
        response = self.client.get(reverse('teams_detail', args=[self.test_team_1.team_id]))
        self.assertEquals(response.status_code, 403)

    def test_detail_team_logged_in_not_active(self):
        self.setup_inactive_user()
        response = self.client.get(reverse('teams_detail', args=[self.test_team_1.team_id]))
        self.assertEquals(response.status_code, 200)

    def test_detail_team_logged_in(self):
        team = self.get_team_detail_json(self.test_team_1.team_id, 200)
        self.assertEquals(team['description'], self.test_team_1.description)

    def test_detail_team_does_not_exist(self):
        self.get_team_detail('foobar', 404)

    def patch_team_detail(self, team_id, expected_status, user=None, data=None):
        """
        Patches the team with team_id using data as user. Verifies expected_status.
        """
        user = user if user else self.student_user
        data = data if data else {}
        data = json.dumps(data)
        self.client.login(username=user.username, password=self.test_password)
        response = self.client.patch(
            reverse('teams_detail', args=[team_id]),
            data=data,
            content_type='application/merge-patch+json',
        )
        self.assertEquals(response.status_code, expected_status)

    def test_update_team_anonymous(self):
        response = self.client.patch(reverse('teams_detail', args=[self.test_team_1.team_id]))
        self.assertEquals(response.status_code, 403)

    def test_update_team_logged_in(self):
        self.patch_team_detail(self.test_team_1.team_id, 403)

    def test_update_team_staff(self):
        self.patch_team_detail(self.test_team_1.team_id, 200, user=self.staff_user, data={'name': 'foo'})
        team = self.get_team_detail_json(self.test_team_1.team_id, 200, user=self.staff_user)
        self.assertEquals(team['name'], 'foo')

    @ddt.data(('foo', 'bar'), ('team_id', 'foobar'), ('description', ''))
    @ddt.unpack
    def test_update_team_bad_requests(self, key, value):
        self.patch_team_detail(self.test_team_1.team_id, 400, user=self.staff_user, data={key: value})

    def test_update_team_does_not_exist(self):
        self.patch_team_detail('foobar', 404, user=self.staff_user)

    def test_list_topics_anonymous(self):
        response = self.client.get(reverse('topics_list'), data={'course_id': str(self.test_course_1.id)})
        self.assertEqual(403, response.status_code)

    def test_list_topics_unenrolled(self):
        self.client.login(username=self.student_user, password=self.test_password)
        response = self.client.get(reverse('topics_list'), data={'course_id': str(self.test_course_1.id)})
        self.assertEqual(403, response.status_code)

    @ddt.data('A+BOGUS+COURSE', 'A/BOGUS/COURSE')
    def test_list_topics_invalid_course_key(self, course_id):
        self.client.login(username=self.student_user_enrolled, password=self.test_password)
        response = self.client.get(reverse('topics_list'), data={'course_id': course_id})
        self.assertEqual(404, response.status_code)

    def test_list_topics_without_course_id(self):
        self.client.login(username=self.student_user_enrolled, password=self.test_password)
        response = self.client.get(reverse('topics_list'))
        self.assertEqual(400, response.status_code)

    def test_list_topics_order_by_name_by_default(self):
        self.client.login(username=self.student_user_enrolled, password=self.test_password)
        response = self.client.get(reverse('topics_list'), data={'course_id': str(self.test_course_1.id)})
        self.assertEqual(200, response.status_code)
        topics = response.data['results']
        self.assertEqual(topics, sorted(topics, key=lambda t: t['name']))

    def test_list_topics_order_by_name(self):
        self.client.login(username=self.student_user_enrolled, password=self.test_password)
        data = {'course_id': str(self.test_course_1.id), 'order_by': 'name'}
        response = self.client.get(reverse('topics_list'), data=data)
        self.assertEqual(200, response.status_code)
        topics = response.data['results']
        self.assertEqual(topics, sorted(topics, key=lambda t: t['name']))

    def test_list_topics_invalid_ordering(self):
        self.client.login(username=self.student_user_enrolled, password=self.test_password)
        data = {'course_id': str(self.test_course_1.id), 'order_by': 'BOGUS'}
        response = self.client.get(reverse('topics_list'), data=data)
        self.assertEqual(400, response.status_code)

    def test_list_topics_pagination(self):
        page_size = 2
        self.client.login(username=self.student_user_enrolled, password=self.test_password)
        data = {'course_id': str(self.test_course_1.id), 'page_size': str(page_size)}
        response = self.client.get(reverse('topics_list'), data=data)
        self.assertEqual(200, response.status_code)
        self.assertEqual(page_size, len(response.data['results']))
        self.assertIn('next', response.data)
        self.assertIn('previous', response.data)
        self.assertEqual(response.data['previous'], None)
        self.assertNotEqual(response.data['next'], None)

    def test_topic_detail_anonymous(self):
        response = self.client.get(
            reverse('topics_detail', kwargs={'topic_id': 'topic_0', 'course_id': str(self.test_course_1.id)})
        )
        self.assertEqual(403, response.status_code)

    def test_topic_detail_unenrolled(self):
        self.client.login(username=self.student_user, password=self.test_password)
        response = self.client.get(
            reverse('topics_detail', kwargs={'topic_id': 'topic_0', 'course_id': str(self.test_course_1.id)})
        )
        self.assertEqual(403, response.status_code)

    @ddt.data('A+BOGUS+COURSE', 'A/BOGUS/COURSE')
    def test_topic_detail_invalid_course_id(self, course_id):
        self.client.login(username=self.student_user_enrolled, password=self.test_password)
        response = self.client.get(
            reverse('topics_detail', kwargs={'topic_id': 'topic_0', 'course_id': course_id})
        )
        self.assertEqual(404, response.status_code)

    def test_topic_detail_invalid_topic_id(self):
        self.client.login(username=self.student_user_enrolled, password=self.test_password)
        response = self.client.get(
            reverse('topics_detail', kwargs={'topic_id': 'bogus_topic', 'course_id': str(self.test_course_1.id)})
        )
        self.assertEqual(404, response.status_code)

    def test_topic_detail_inactive(self):
        self.client.login(username=self.student_user_enrolled, password=self.test_password)
        response = self.client.get(
            reverse('topics_detail', kwargs={'topic_id': 'inactive', 'course_id': str(self.test_course_1.id)})
        )
        self.assertEqual(404, response.status_code)

    def test_topic_detail_success(self):
        self.client.login(username=self.student_user_enrolled, password=self.test_password)
        response = self.client.get(
            reverse('topics_detail', kwargs={'topic_id': 'topic_0', 'course_id': str(self.test_course_1.id)})
        )
        self.assertEqual(200, response.status_code)
        for field in ('id', 'name', 'description'):
            self.assertIn(field, response.data)
