import json

from django.core.urlresolvers import reverse
from rest_framework.test import APITestCase, APIClient

from student.tests.factories import UserFactory
from xmodule.modulestore.tests.factories import CourseFactory
from .factories import CourseTeamFactory
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase


class TestTeamAPI(APITestCase, ModuleStoreTestCase):
    """
    Tests of the Team API
    """

    test_password = 'password'

    def setUp(self):
        super(TestTeamAPI, self).setUp()

        self.test_course_1 = CourseFactory.create(org='TestX', course='TS101', display_name='Test Course')
        self.test_course_2 = CourseFactory.create(org='MIT', course='6.002x', display_name='Circuits')

        self.student_user = UserFactory.create(password=self.test_password)
        self.staff_user = UserFactory.create(password=self.test_password, is_staff=True)

        self.test_team_1 = CourseTeamFactory.create(name='solar team', course_id=self.test_course_1.id, topic_id='renewable')
        self.test_team_2 = CourseTeamFactory.create(name='Wind Team', course_id=self.test_course_2.id)
        self.test_team_3 = CourseTeamFactory.create(name='Nuclear Team', course_id=self.test_course_1.id)
        self.test_team_4 = CourseTeamFactory.create(name='coal team', course_id=self.test_course_2.id, is_active=False)

        self.test_team_1.add_user(self.student_user)

    def setup_inactive_user(self):
        test_user = UserFactory.create(password=self.test_password)
        self.client.login(username=test_user.username, password=self.test_password)
        test_user.is_active = False
        test_user.save()

    def get_teams_list(self, user, expected_status, data=None):
        self.client.login(username=user.username, password=self.test_password)
        response = self.client.get(reverse('teams_list'), data=data)
        self.assertEqual(expected_status, response.status_code)
        return response

    def get_teams_list_json(self, user, data=None):
        response = self.get_teams_list(user, 200, data)
        return json.loads(response.content)

    def test_list_teams_anonymous(self):
        response = self.client.get(reverse('teams_list'))
        self.assertEqual(403, response.status_code)

    def test_list_teams_logged_in(self):
        teams = self.get_teams_list_json(self.student_user)
        self.assertEqual(3, teams['count'])

    def test_list_teams_logged_in_not_active(self):
        self.setup_inactive_user()
        response = self.client.get(reverse('teams_list'))
        self.assertEqual(200, response.status_code)

    def test_list_teams_filter_invalid_course_id(self):
        self.get_teams_list(self.student_user, 400, data={'course_id': 'foobar'})

    def test_list_teams_filter_course_id(self):
        teams = self.get_teams_list_json(self.student_user, data={'course_id': str(self.test_course_2.id)})
        self.assertEqual(1, teams['count'])
        self.assertEqual(teams['results'][0]['name'], 'Wind Team')

    def test_list_teams_filter_topic_id(self):
        teams = self.get_teams_list_json(self.student_user, data={
            'course_id': str(self.test_course_1.id),
            'topic_id': 'renewable',
        })
        self.assertEqual(1, teams['count'])
        self.assertEqual(teams['results'][0]['name'], 'solar team')

    def test_list_teams_filter_include_inactive(self):
        teams = self.get_teams_list_json(self.student_user, data={'include_inactive': True})
        self.assertEqual(4, teams['count'])

    def test_list_teams_filter_text_search(self):
        self.get_teams_list(self.student_user, 400, data={'text_search': 'foobar'})

    def test_list_teams_order_by_name(self):
        teams = self.get_teams_list_json(self.student_user, data={'order_by': 'name'})
        self.assertEqual(3, teams['count'])
        self.assertEqual([team['name'] for team in teams['results']], ['Nuclear Team', 'solar team', 'Wind Team'])

    def test_list_teams_order_by_open_slots(self):
        teams = self.get_teams_list_json(self.student_user, data={'order_by': 'open_slots'})
        self.assertEqual(3, teams['count'])
        self.assertEqual([team['name'] for team in teams['results']], ['Wind Team', 'Nuclear Team', 'solar team'])

    def test_list_teams_order_by_last_activity(self):
        self.get_teams_list(self.student_user, 400, data={'order_by': 'last_activity'})

    def test_list_team_no_results(self):
        self.get_teams_list(self.student_user, 404, data={'course_id': 'foobar/foobar/foobar'})
        self.get_teams_list(self.student_user, 404, data={'topic_id': 'foobar'})

    def build_team_data(self, name, course, description="Filler description", data=None):
        data = data if data else {}
        data.update({
            'name': name,
            'course_id': str(course.id),
            'description': description,
        })
        return data

    def post_create_team(self, user, expected_status, data):
        self.client.login(username=user.username, password=self.test_password)
        response = self.client.post(reverse('teams_list'), data=data)
        self.assertEquals(response.status_code, expected_status)
        return response

    def post_create_team_json(self, user, expected_status, data):
        response = self.post_create_team(user, expected_status, data)
        return json.loads(response.content)

    def test_create_team_anonymous(self):
        response = self.client.post(reverse('teams_list'), self.build_team_data("Anonymous Team", self.test_course_1))
        self.assertEquals(403, response.status_code)

    def test_create_team_logged_in_not_active(self):
        self.setup_inactive_user()
        response = self.client.post(reverse('teams_list'), self.build_team_data("Inactive Team", self.test_course_1))
        self.assertEquals(403, response.status_code)

    def test_create_team_logged_in(self):
        new_team = self.post_create_team_json(
            self.student_user,
            200,
            self.build_team_data("New Team", self.test_course_1)
        )
        self.assertEquals(new_team['id'], 'new-team')

        teams = self.get_teams_list_json(self.student_user)
        self.assertIn("New Team", [team['name'] for team in teams['results']])

    def test_create_team_naming(self):
        new_teams = [
            self.post_create_team_json(self.student_user, 200, self.build_team_data(name, self.test_course_1))
            for name in ["The Best Team", "The Best Team", "The Best Team", "The Best Team 2"]
        ]
        self.assertEquals(
            [team['id'] for team in new_teams],
            ['the-best-team', 'the-best-team-2', 'the-best-team-3', 'the-best-team-2-2']
        )

    def test_create_team_invalid_course_id(self):
        self.post_create_team(self.student_user, 400, {
            'name': 'Bad Course Id',
            'course_id': 'foobar',
            'description': "Filler Description",
        })

    def test_create_team_non_existent_course_id(self):
        self.post_create_team(self.student_user, 404, {
            'name': "Non-existent course id",
            'course_id': 'foobar/foobar/foobar',
            'description': "Filler Description",
        })

    def test_create_team_blank_name(self):
        self.post_create_team(self.student_user, 400, self.build_team_data("", self.test_course_1))

    def test_create_team_blank_description(self):
        self.post_create_team(self.student_user, 400, self.build_team_data(
            "Blank Description",
            self.test_course_1,
            description=""
        ))

    def test_create_team_long_name(self):
        self.post_create_team(self.student_user, 400, self.build_team_data(
            ''.join(['x' for i in range(1000)]),
            self.test_course_1,
        ))

    def test_create_team_extra_fields(self):
        self.post_create_team(self.student_user, 400, self.build_team_data(
            "Flawed team",
            self.test_course_1,
            data={'foobar': "foobar"},
        ))

    def test_create_team_full(self):
        team = self.post_create_team_json(self.student_user, 200, self.build_team_data(
            "Fully specified team",
            self.test_course_1,
            description="Another fantastic team",
            data={
                'topic_id': 'great-topic',
                'country': 'USA',
                'language': 'English',
            }
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
