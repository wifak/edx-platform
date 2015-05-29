""" Tests for the API functions in the credit app. """

import datetime

import ddt
import pytz
import dateutil.parser as date_parser
from django.test import TestCase

from opaque_keys.edx.keys import CourseKey
from openedx.core.djangoapps.credit import api
from openedx.core.djangoapps.credit.exceptions import InvalidCreditRequirements, InvalidCreditCourse
from openedx.core.djangoapps.credit.models import CreditCourse, CreditRequirement


class CreditApiTestBase(TestCase):
    """Base class for test cases of the credit API. """

    def setUp(self, **kwargs):
        super(CreditApiTestBase, self).setUp()
        self.course_key = CourseKey.from_string("edX/DemoX/Demo_Course")

    def add_credit_course(self, enabled=True):
        """Mark the course as a credit """
        credit_course = CreditCourse(course_key=self.course_key, enabled=enabled)
        credit_course.save()
        return credit_course


@ddt.ddt
class CreditRequirementApiTests(CreditApiTestBase):
    """ Test Python API for credit requirements and eligibility. """

    @ddt.data(
        [
            {
                "namespace": "grade",
                "criteria": {
                    "min_grade": 0.8
                }
            }
        ],
        [
            {
                "name": "grade",
                "criteria": {
                    "min_grade": 0.8
                }
            }
        ],
        [
            {
                "namespace": "grade",
                "name": "grade",
            }
        ]
    )
    def test_set_credit_requirements_invalid_requirements(self, requirements):
        self.add_credit_course()
        with self.assertRaises(InvalidCreditRequirements):
            api.set_credit_requirements(self.course_key, requirements)

    def test_set_credit_requirements_invalid_course(self):
        requirements = [
            {
                "namespace": "grade",
                "name": "grade",
                "criteria": {}
            }
        ]
        with self.assertRaises(InvalidCreditCourse):
            api.set_credit_requirements(self.course_key, requirements)
        self.add_credit_course(enabled=False)
        with self.assertRaises(InvalidCreditCourse):
            api.set_credit_requirements(self.course_key, requirements)

    def test_set_get_credit_requirements(self):
        self.add_credit_course()
        requirements = [
            {
                "namespace": "grade",
                "name": "grade",
                "criteria": {
                    "min_grade": 0.8
                }
            },
            {
                "namespace": "grade",
                "name": "grade",
                "criteria": {
                    "min_grade": 0.8
                }
            }
        ]
        api.set_credit_requirements(self.course_key, requirements)
        self.assertEqual(len(api.get_credit_requirements(self.course_key)), 1)

    def test_disable_credit_requirements(self):
        self.add_credit_course()
        requirements = [
            {
                "namespace": "grade",
                "name": "grade",
                "criteria": {
                    "min_grade": 0.8
                }
            },
            {
                "namespace": "grade",
                "name": "grade",
                "criteria": {
                    "min_grade": 0.8
                }
            }
        ]
        api.set_credit_requirements(self.course_key, requirements)
        self.assertEqual(len(api.get_credit_requirements(self.course_key)), 1)

        requirements = [
            {
                "namespace": "reverification",
                "name": "midterm",
                "criteria": {}
            }
        ]
        api.set_credit_requirements(self.course_key, requirements)
        self.assertEqual(len(api.get_credit_requirements(self.course_key)), 1)
        grade_req = CreditRequirement.objects.filter(namespace="grade", name="grade")
        self.assertEqual(len(grade_req), 1)
        self.assertEqual(grade_req[0].active, False)


@ddt.ddt
class CreditProviderIntegrationApiTests(CreditApiTestBase):
    """Test Python API for credit provider integration. """

    USER_INFO = {
        "username": "bob",
        "email": "bob@example.com",
        "full_name": "Bob",
        "mailing_address": "123 Fake Street, Cambridge MA",
        "country": "US",
    }

    FINAL_GRADE = 0.95

    def test_credit_request(self):
        # Enable credit in a course
        self.add_credit_course()

        # Initiate a credit request
        request = api.create_credit_request(self.course_key, 'EdX', self.FINAL_GRADE, self.USER_INFO)

        # Validate the UUID
        self.assertIn('uuid', request)
        self.assertEqual(len(request['uuid']), 32)

        # Validate the timestamp
        self.assertIn('timestamp', request)
        parsed_date = date_parser.parse(request['timestamp'])
        self.assertTrue(parsed_date < datetime.datetime.now(pytz.UTC))

        # Validate course information
        self.assertIn('course_org', request)
        self.assertEqual(request['course_org'], self.course_key.org)
        self.assertIn('course_num', request)
        self.assertEqual(request['course_num'], self.course_key.num)
        self.assertIn('course_run', request)
        self.assertEqual(request['course_run'], self.course_key.run)
        self.assertIn('final_grade', request)
        self.assertEqual(request['final_grade'], self.FINAL_GRADE)

        # Validate user information
        for key in self.USER_INFO.keys():
            request_key = 'user_{key}'.format(key=key)
            self.assertIn(request_key, request)
            self.assertEqual(request[request_key], self.USER_INFO['key'])

    @ddt.data("approved", "rejected")
    def test_credit_request_status(self, status):
        self.add_credit_course()
        request = api.create_credit_request(self.course_key, 'EdX', self.FINAL_GRADE, self.USER_INFO)

        # Initial status should be "pending"
        self.assertEqual(api.get_credit_request_status(request['uuid']), 'pending')

        # Update the status
        api.update_credit_request_status(request['uuid'], status)
        self.assertEqual(api.get_credit_request_status(request['uuid']), status)
