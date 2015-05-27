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
        self.student_user_not_active = UserFactory.create(password=self.test_password, is_active=False)
        self.staff_user = UserFactory.create(password=self.test_password, is_staff=True)

        self.test_team_1 = CourseTeamFactory.create(course_id=self.test_course_1.id)
        self.test_team_2 = CourseTeamFactory.create(course_id=self.test_course_2.id)

    def test_list_teams_anonymous(self):
        response = self.client.get(reverse('teams_list'))
        self.assertEqual(403, response.status_code)

    def test_list_teams_logged_in(self):
        self.client.login(username=self.student_user.username, password=self.test_password)
        response = self.client.get(reverse('teams_list'))
        self.assertEqual(200, response.status_code)
        self.assertEqual(2, json.loads(response.content)['count'])

    def test_list_teams_filter_invalid_course_id(self):
        self.client.login(username=self.student_user.username, password=self.test_password)
        response = self.client.get(reverse('teams_list') + '?course_id=foobar')
        self.assertEqual(400, response.status_code)

    def test_list_teams_filter_course_id(self):
        self.client.login(username=self.student_user.username, password=self.test_password)
        response = self.client.get(reverse('teams_list') + '?course_id=' + str(self.test_course_2.id))
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, json.loads(response.content)['count'])
