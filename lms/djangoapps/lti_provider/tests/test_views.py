"""
Tests for the LTI provider views
"""

from django.core.urlresolvers import reverse
from django.test import TestCase
from django.test.client import RequestFactory
from mock import patch, MagicMock

from lti_provider import views
from lti_provider.signature_validator import SignatureValidator
from opaque_keys.edx.keys import CourseKey, UsageKey
from student.tests.factories import UserFactory
from courseware.tests.test_views import RenderXBlockMixin


LTI_DEFAULT_PARAMS = {
    'roles': u'Instructor,urn:lti:instrole:ims/lis/Administrator',
    'context_id': u'lti_launch_context_id',
    'oauth_version': u'1.0',
    'oauth_consumer_key': u'consumer_key',
    'oauth_signature': u'OAuth Signature',
    'oauth_signature_method': u'HMAC-SHA1',
    'oauth_timestamp': u'OAuth Timestamp',
    'oauth_nonce': u'OAuth Nonce',
}

COURSE_KEY = CourseKey.from_string('some/course/id')
USAGE_KEY = UsageKey.from_string('i4x://some/course/problem/uuid').map_into_course(COURSE_KEY)
COURSE_PARAMS = {
    'course_key': COURSE_KEY,
    'usage_key': USAGE_KEY
}


ALL_PARAMS = dict(LTI_DEFAULT_PARAMS.items() + COURSE_PARAMS.items())


def build_launch_request(authenticated=True):
    """
    Helper method to create a new request object for the LTI launch.
    """
    request = RequestFactory().post('/')
    request.user = UserFactory.create()
    request.user.is_authenticated = MagicMock(return_value=authenticated)
    request.session = {}
    request.POST.update(LTI_DEFAULT_PARAMS)
    return request


def build_run_request(authenticated=True):
    """
    Helper method to create a new request object
    """
    request = RequestFactory().get('/')
    request.user = UserFactory.create()
    request.user.is_authenticated = MagicMock(return_value=authenticated)
    request.session = {views.LTI_SESSION_KEY: ALL_PARAMS.copy()}
    return request


class LtiLaunchTest(TestCase):
    """
    Tests for the lti_launch view
    """

    @patch.dict('django.conf.settings.FEATURES', {'ENABLE_LTI_PROVIDER': True})
    def setUp(self):
        super(LtiLaunchTest, self).setUp()
        # Always accept the OAuth signature
        SignatureValidator.verify = MagicMock(return_value=True)

    @patch('lti_provider.views.render_xblock')
    def test_valid_launch(self, render):
        """
        Verifies that the LTI launch succeeds when passed a valid request.
        """
        request = build_launch_request()
        views.lti_launch(request, unicode(COURSE_KEY), unicode(USAGE_KEY))
        render.assert_called_with(request, unicode(ALL_PARAMS['usage_key']))

    def launch_with_missing_parameter(self, missing_param):
        """
        Helper method to remove a parameter from the LTI launch and call the view
        """
        request = build_launch_request()
        del request.POST[missing_param]
        return views.lti_launch(request, None, None)

    def test_launch_with_missing_parameters(self):
        """
        Runs through all required LTI parameters and verifies that the lti_launch
        view returns Bad Request if any of them are missing.
        """
        for missing_param in views.REQUIRED_PARAMETERS:
            response = self.launch_with_missing_parameter(missing_param)
            self.assertEqual(
                response.status_code, 400,
                'Launch should fail when parameter ' + missing_param + ' is missing'
            )

    def test_launch_with_disabled_feature_flag(self):
        """
        Verifies that the LTI launch will fail if the ENABLE_LTI_PROVIDER flag
        is not set
        """
        with patch.dict('django.conf.settings.FEATURES', {'ENABLE_LTI_PROVIDER': False}):
            request = build_launch_request()
            response = views.lti_launch(request, None, None)
            self.assertEqual(response.status_code, 403)

    @patch('lti_provider.views.lti_run')
    def test_session_contents_after_launch(self, _run):
        """
        Verifies that the LTI parameters and the course and usage IDs are
        properly stored in the session
        """
        request = build_launch_request()
        views.lti_launch(request, unicode(COURSE_KEY), unicode(USAGE_KEY))
        session = request.session[views.LTI_SESSION_KEY]
        self.assertEqual(session['course_key'], COURSE_KEY, 'Course key not set in the session')
        self.assertEqual(session['usage_key'], USAGE_KEY, 'Usage key not set in the session')
        for key in views.REQUIRED_PARAMETERS:
            self.assertEqual(session[key], request.POST[key], key + ' not set in the session')

    def test_redirect_for_non_authenticated_user(self):
        """
        Verifies that if the lti_launch view is called by an unauthenticated
        user, the response will redirect to the login page with the correct
        URL
        """
        request = build_launch_request(False)
        response = views.lti_launch(request, unicode(COURSE_KEY), unicode(USAGE_KEY))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/accounts/login?next=/lti_provider/lti_run')

    def test_forbidden_if_signature_fails(self):
        """
        Verifies that the view returns Forbidden if the LTI OAuth signature is
        incorrect.
        """
        SignatureValidator.verify = MagicMock(return_value=False)
        request = build_launch_request()
        response = views.lti_launch(request, None, None)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.status_code, 403)


class LtiRunTest(TestCase):
    """
    Tests for the lti_run view
    """
    def test_forbidden_if_session_key_missing(self):
        """
        Verifies that the lti_run view returns a Forbidden status if the session
        doesn't have an entry for the LTI parameters.
        """
        request = build_run_request()
        del request.session[views.LTI_SESSION_KEY]
        response = views.lti_run(request)
        self.assertEqual(response.status_code, 403)

    def test_forbidden_if_session_incomplete(self):
        """
        Verifies that the lti_run view returns a Forbidden status if the session
        is missing any of the required LTI parameters or course information.
        """
        extra_keys = ['course_key', 'usage_key']
        for key in views.REQUIRED_PARAMETERS + extra_keys:
            request = build_run_request()
            del request.session[views.LTI_SESSION_KEY][key]
            response = views.lti_run(request)
            self.assertEqual(
                response.status_code,
                403,
                'Expected Forbidden response when session is missing ' + key
            )

    @patch('lti_provider.views.render_xblock')
    def test_session_cleared_in_view(self, _render):
        """
        Verifies that the LTI parameters are cleaned out of the session after
        launching the view to prevent a launch being replayed.
        """
        request = build_run_request()
        views.lti_run(request)
        self.assertNotIn(views.LTI_SESSION_KEY, request.session)


class LtiRunTestRender(RenderXBlockMixin):
    """
    Tests for the rendering returned by lti_run view
    """
    @patch.dict('django.conf.settings.FEATURES', {'ENABLE_LTI_PROVIDER': True})
    def setUp(self):
        super(LtiRunTestRender, self).setUp()

    def get_response(self):
        """
        Overridable method to get the response from the endpoint that is being tested.
        """
        lti_launch_url = reverse(
            'lti_provider_launch',
            kwargs={'course_id': unicode(self.course.id), 'usage_id': unicode(self.html_block.location)}
        )
        SignatureValidator.verify = MagicMock(return_value=True)
        return self.client.post(lti_launch_url, data=LTI_DEFAULT_PARAMS)
