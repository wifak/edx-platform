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

        self.test_team_1 = CourseTeamFactory.create(name='solar team', course_id=self.test_course_1.id)
        self.test_team_2 = CourseTeamFactory.create(name='Wind Team', course_id=self.test_course_2.id)
        self.test_team_3 = CourseTeamFactory.create(name='Nuclear Team', course_id=self.test_course_1.id)

        self.test_team_1.add_user(self.student_user)

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
        test_user = UserFactory.create(password=self.test_password)
        self.client.login(username=test_user.username, password=self.test_password)
        test_user.is_active = False
        test_user.save()
        response = self.client.get(reverse('teams_list'))
        self.assertEqual(200, response.status_code)

    def test_list_teams_filter_invalid_course_id(self):
        self.get_teams_list(self.student_user, 400, data={'course_id': 'foobar'})

    def test_list_teams_filter_course_id(self):
        teams = self.get_teams_list_json(self.student_user, data={'course_id': str(self.test_course_2.id)})
        self.assertEqual(1, teams['count'])

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
