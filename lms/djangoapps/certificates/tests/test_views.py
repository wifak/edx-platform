"""Tests for certificates views. """

import json
import ddt
from uuid import uuid4
from nose.plugins.attrib import attr

from django.conf import settings
from django.core.cache import cache
from django.core.urlresolvers import reverse
from django.test import TestCase
from django.test.client import Client
from django.test.utils import override_settings

from opaque_keys.edx.locator import CourseLocator
from openedx.core.lib.tests.assertions.events import assert_event_matches
from student.tests.factories import UserFactory
from track.tests import EventTrackingTestCase
from xmodule.modulestore.tests.factories import CourseFactory
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase

from certificates.api import get_certificate_url
from certificates.models import ExampleCertificateSet, ExampleCertificate, GeneratedCertificate, BadgeAssertion
from certificates.tests.factories import (
    CertificateHtmlViewConfigurationFactory,
    LinkedInAddToProfileConfigurationFactory,
    BadgeAssertionFactory,
)
from lms import urls

FEATURES_WITH_CERTS_ENABLED = settings.FEATURES.copy()
FEATURES_WITH_CERTS_ENABLED['CERTIFICATES_HTML_VIEW'] = True

FEATURES_WITH_CERTS_DISABLED = settings.FEATURES.copy()
FEATURES_WITH_CERTS_DISABLED['CERTIFICATES_HTML_VIEW'] = False


@attr('shard_1')
@ddt.ddt
class UpdateExampleCertificateViewTest(TestCase):
    """Tests for the XQueue callback that updates example certificates. """

    COURSE_KEY = CourseLocator(org='test', course='test', run='test')

    DESCRIPTION = 'test'
    TEMPLATE = 'test.pdf'
    DOWNLOAD_URL = 'http://www.example.com'
    ERROR_REASON = 'Kaboom!'

    def setUp(self):
        super(UpdateExampleCertificateViewTest, self).setUp()
        self.cert_set = ExampleCertificateSet.objects.create(course_key=self.COURSE_KEY)
        self.cert = ExampleCertificate.objects.create(
            example_cert_set=self.cert_set,
            description=self.DESCRIPTION,
            template=self.TEMPLATE,
        )
        self.url = reverse('certificates.views.update_example_certificate')

        # Since rate limit counts are cached, we need to clear
        # this before each test.
        cache.clear()

    def test_update_example_certificate_success(self):
        response = self._post_to_view(self.cert, download_url=self.DOWNLOAD_URL)
        self._assert_response(response)

        self.cert = ExampleCertificate.objects.get()
        self.assertEqual(self.cert.status, ExampleCertificate.STATUS_SUCCESS)
        self.assertEqual(self.cert.download_url, self.DOWNLOAD_URL)

    def test_update_example_certificate_invalid_key(self):
        payload = {
            'xqueue_header': json.dumps({
                'lms_key': 'invalid'
            }),
            'xqueue_body': json.dumps({
                'username': self.cert.uuid,
                'url': self.DOWNLOAD_URL
            })
        }
        response = self.client.post(self.url, data=payload)
        self.assertEqual(response.status_code, 404)

    def test_update_example_certificate_error(self):
        response = self._post_to_view(self.cert, error_reason=self.ERROR_REASON)
        self._assert_response(response)

        self.cert = ExampleCertificate.objects.get()
        self.assertEqual(self.cert.status, ExampleCertificate.STATUS_ERROR)
        self.assertEqual(self.cert.error_reason, self.ERROR_REASON)

    @ddt.data('xqueue_header', 'xqueue_body')
    def test_update_example_certificate_invalid_params(self, missing_param):
        payload = {
            'xqueue_header': json.dumps({
                'lms_key': self.cert.access_key
            }),
            'xqueue_body': json.dumps({
                'username': self.cert.uuid,
                'url': self.DOWNLOAD_URL
            })
        }
        del payload[missing_param]

        response = self.client.post(self.url, data=payload)
        self.assertEqual(response.status_code, 400)

    def test_update_example_certificate_missing_download_url(self):
        payload = {
            'xqueue_header': json.dumps({
                'lms_key': self.cert.access_key
            }),
            'xqueue_body': json.dumps({
                'username': self.cert.uuid
            })
        }
        response = self.client.post(self.url, data=payload)
        self.assertEqual(response.status_code, 400)

    def test_update_example_cetificate_non_json_param(self):
        payload = {
            'xqueue_header': '{/invalid',
            'xqueue_body': '{/invalid'
        }
        response = self.client.post(self.url, data=payload)
        self.assertEqual(response.status_code, 400)

    def test_unsupported_http_method(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    def test_bad_request_rate_limiting(self):
        payload = {
            'xqueue_header': json.dumps({
                'lms_key': 'invalid'
            }),
            'xqueue_body': json.dumps({
                'username': self.cert.uuid,
                'url': self.DOWNLOAD_URL
            })
        }

        # Exceed the rate limit for invalid requests
        # (simulate a DDOS with invalid keys)
        for _ in range(100):
            response = self.client.post(self.url, data=payload)
            if response.status_code == 403:
                break

        # The final status code should indicate that the rate
        # limit was exceeded.
        self.assertEqual(response.status_code, 403)

    def _post_to_view(self, cert, download_url=None, error_reason=None):
        """Simulate a callback from the XQueue to the example certificate end-point. """
        header = {'lms_key': cert.access_key}
        body = {'username': cert.uuid}

        if download_url is not None:
            body['url'] = download_url

        if error_reason is not None:
            body['error'] = 'error'
            body['error_reason'] = self.ERROR_REASON

        payload = {
            'xqueue_header': json.dumps(header),
            'xqueue_body': json.dumps(body)
        }
        return self.client.post(self.url, data=payload)

    def _assert_response(self, response):
        """Check the response from the callback end-point. """
        content = json.loads(response.content)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(content['return_code'], 0)


@attr('shard_1')
class CertificatesViewsTests(ModuleStoreTestCase, EventTrackingTestCase):
    """
    Tests for the manual refund page
    """
    def setUp(self):
        super(CertificatesViewsTests, self).setUp()
        self.client = Client()
        self.course = CourseFactory.create(
            org='testorg', number='run1', display_name='refundable course'
        )
        self.course_id = self.course.location.course_key
        self.user = UserFactory.create(
            email='joe_user@edx.org',
            username='joeuser',
            password='foo'
        )
        self.user.profile.name = "Joe User"
        self.user.profile.save()
        self.client.login(username=self.user.username, password='foo')

        self.cert = GeneratedCertificate.objects.create(
            user=self.user,
            course_id=self.course_id,
            verify_uuid=uuid4(),
            download_uuid=uuid4(),
            grade="0.95",
            key='the_key',
            distinction=True,
            status='generated',
            mode='honor',
            name=self.user.profile.name,
        )
        CertificateHtmlViewConfigurationFactory.create()
        LinkedInAddToProfileConfigurationFactory.create()

    def _add_course_certificates(self, count=1, signatory_count=0, is_active=True):
        """
        Create certificate for the course.
        """
        signatories = [
            {
                'name': 'Signatory_Name ' + str(i),
                'title': 'Signatory_Title ' + str(i),
                'organization': 'Signatory_Organization ' + str(i),
                'signature_image_path': '/static/certificates/images/demo-sig{}.png'.format(i),
                'id': i,
            } for i in xrange(0, signatory_count)

        ]

        certificates = [
            {
                'id': i,
                'name': 'Name ' + str(i),
                'description': 'Description ' + str(i),
                'course_title': 'course_title_' + str(i),
                'org_logo_path': '/t4x/orgX/testX/asset/org-logo-{}.png'.format(i),
                'signatories': signatories,
                'version': 1,
                'is_active': is_active
            } for i in xrange(0, count)
        ]

        self.course.certificates = {'certificates': certificates}
        self.course.save()
        self.store.update_item(self.course, self.user.id)

    @override_settings(FEATURES=FEATURES_WITH_CERTS_ENABLED)
    def test_render_html_view_valid_certificate(self):
        test_url = get_certificate_url(
            user_id=self.user.id,
            course_id=unicode(self.course.id)  # pylint: disable=no-member
        )
        self._add_course_certificates(count=1, signatory_count=2)
        response = self.client.get(test_url)
        self.assertIn(str(self.cert.verify_uuid), response.content)

        # Hit any "verified" mode-specific branches
        self.cert.mode = 'verified'
        self.cert.save()
        response = self.client.get(test_url)
        self.assertIn(str(self.cert.verify_uuid), response.content)

        # Hit any 'xseries' mode-specific branches
        self.cert.mode = 'xseries'
        self.cert.save()
        response = self.client.get(test_url)
        self.assertIn(str(self.cert.verify_uuid), response.content)

    @override_settings(FEATURES=FEATURES_WITH_CERTS_ENABLED)
    def test_render_html_view_with_valid_signatories(self):
        test_url = get_certificate_url(
            user_id=self.user.id,
            course_id=self.course.id.to_deprecated_string()  # pylint: disable=no-member
        )
        self._add_course_certificates(count=1, signatory_count=2)
        response = self.client.get(test_url)
        self.assertIn('course_title_0', response.content)
        self.assertIn('/t4x/orgX/testX/asset/org-logo-0.png', response.content)
        self.assertIn('Signatory_Name 0', response.content)
        self.assertIn('Signatory_Title 0', response.content)
        self.assertIn('Signatory_Organization 0', response.content)
        self.assertIn('/static/certificates/images/demo-sig0.png', response.content)

    @override_settings(FEATURES=FEATURES_WITH_CERTS_ENABLED)
    def test_course_display_name_not_override_with_course_title(self):
        # if certificate in descriptor has not course_title then course name should not be overridden with this title.
        test_url = get_certificate_url(
            user_id=self.user.id,
            course_id=self.course.id.to_deprecated_string()  # pylint: disable=no-member
        )
        test_certificates = [
            {
                'id': 0,
                'name': 'Name 0',
                'description': 'Description 0',
                'signatories': [],
                'version': 1,
                'is_active':True
            }
        ]
        self.course.certificates = {'certificates': test_certificates}
        self.course.save()
        self.store.update_item(self.course, self.user.id)
        response = self.client.get(test_url)
        self.assertNotIn('test_course_title_0', response.content)
        self.assertIn('refundable course', response.content)

    @override_settings(FEATURES=FEATURES_WITH_CERTS_ENABLED)
    def test_certificate_view_without_org_logo(self):
        test_url = get_certificate_url(
            user_id=self.user.id,
            course_id=self.course.id.to_deprecated_string()  # pylint: disable=no-member
        )
        test_certificates = [
            {
                'id': 0,
                'name': 'Certificate Name 0',
                'signatories': [],
                'version': 1,
                'is_active': True
            }
        ]
        self.course.certificates = {'certificates': test_certificates}
        self.course.save()
        self.store.update_item(self.course, self.user.id)
        response = self.client.get(test_url)
        # make sure response html has only one organization logo container for edX
        self.assertContains(response, "<li class=\"wrapper-organization\">", 1)

    @override_settings(FEATURES=FEATURES_WITH_CERTS_ENABLED)
    def test_render_html_view_without_signatories(self):
        test_url = get_certificate_url(
            user_id=self.user.id,
            course_id=self.course.id.to_deprecated_string()  # pylint: disable=no-member
        )
        self._add_course_certificates(count=1, signatory_count=0)
        response = self.client.get(test_url)
        self.assertNotIn('Signatory_Name 0', response.content)
        self.assertNotIn('Signatory_Title 0', response.content)

    @override_settings(FEATURES=FEATURES_WITH_CERTS_DISABLED)
    def test_render_html_view_invalid_feature_flag(self):
        test_url = get_certificate_url(
            user_id=self.user.id,
            course_id=self.course.id.to_deprecated_string()  # pylint: disable=no-member
        )
        response = self.client.get(test_url)
        self.assertIn('invalid', response.content)

    @override_settings(FEATURES=FEATURES_WITH_CERTS_ENABLED)
    def test_render_html_view_invalid_course_id(self):
        test_url = get_certificate_url(
            user_id=self.user.id,
            course_id='az/23423/4vs'
        )

        response = self.client.get(test_url)
        self.assertIn('invalid', response.content)

    @override_settings(FEATURES=FEATURES_WITH_CERTS_ENABLED)
    def test_render_html_view_invalid_course(self):
        test_url = get_certificate_url(
            user_id=self.user.id,
            course_id='missing/course/key'
        )
        response = self.client.get(test_url)
        self.assertIn('invalid', response.content)

    @override_settings(FEATURES=FEATURES_WITH_CERTS_ENABLED)
    def test_render_html_view_invalid_user(self):
        test_url = get_certificate_url(
            user_id=111,
            course_id=self.course.id.to_deprecated_string()  # pylint: disable=no-member
        )
        response = self.client.get(test_url)
        self.assertIn('invalid', response.content)

    @override_settings(FEATURES=FEATURES_WITH_CERTS_ENABLED)
    def test_render_html_view_invalid_user_certificate(self):
        self.cert.delete()
        self.assertEqual(len(GeneratedCertificate.objects.all()), 0)
        test_url = get_certificate_url(
            user_id=self.user.id,
            course_id=self.course.id.to_deprecated_string()  # pylint: disable=no-member
        )
        response = self.client.get(test_url)
        self.assertIn('invalid', response.content)

    @override_settings(FEATURES=FEATURES_WITH_CERTS_ENABLED)
    def test_render_html_view_with_preview_mode(self):
        """
        test certificate web view should render properly along with its signatories information when accessing it in
        preview mode. Either the certificate is marked active or not.
        """
        self.cert.delete()
        self.assertEqual(len(GeneratedCertificate.objects.all()), 0)
        self._add_course_certificates(count=1, signatory_count=2)
        test_url = get_certificate_url(
            user_id=self.user.id,
            course_id=self.course.id.to_deprecated_string()  # pylint: disable=no-member
        )
        response = self.client.get(test_url + '?preview=honor')
        self.assertNotIn(self.course.display_name, response.content)
        self.assertIn('course_title_0', response.content)
        self.assertIn('Signatory_Title 0', response.content)

        # mark certificate inactive but accessing in preview mode.
        self._add_course_certificates(count=1, signatory_count=2, is_active=False)
        response = self.client.get(test_url + '?preview=honor')
        self.assertNotIn(self.course.display_name, response.content)
        self.assertIn('course_title_0', response.content)
        self.assertIn('Signatory_Title 0', response.content)

    @override_settings(FEATURES=FEATURES_WITH_CERTS_ENABLED)
    def test_render_html_view_invalid_certificate_configuration(self):
        test_url = get_certificate_url(
            user_id=self.user.id,
            course_id=unicode(self.course.id)  # pylint: disable=no-member
        )
        response = self.client.get(test_url)
        self.assertIn("Invalid Certificate", response.content)

    def test_evidence_event_sent(self):
        test_url = get_certificate_url(user_id=self.user.id, course_id=self.course_id) + '?evidence_visit=1'
        self.recreate_tracker()
        assertion = BadgeAssertion(
            user=self.user, course_id=self.course_id, mode='honor',
            data={
                'image': 'http://www.example.com/image.png',
                'json': {'id': 'http://www.example.com/assertion.json'},
                'issuer': 'http://www.example.com/issuer.json',

            }
        )
        assertion.save()
        response = self.client.get(test_url)
        self.assertEqual(response.status_code, 200)
        assert_event_matches(
            {
                'name': 'edx.badges.assertion.evidence_visit',
                'data': {
                    'course_id': 'testorg/run1/refundable_course',
                    # pylint: disable=no-member
                    'assertion_id': assertion.id,
                    'assertion_json_url': 'http://www.example.com/assertion.json',
                    'assertion_image_url': 'http://www.example.com/image.png',
                    'user_id': self.user.id,
                    'issuer': 'http://www.example.com/issuer.json',
                    'enrollment_mode': 'honor',
                },
            },
            self.get_event()
        )


class TrackShareRedirectTest(ModuleStoreTestCase, EventTrackingTestCase):
    """
    Verifies the badge image share event is sent out.
    """
    def setUp(self):
        super(TrackShareRedirectTest, self).setUp()
        self.client = Client()
        self.course = CourseFactory.create(
            org='testorg', number='run1', display_name='trackable course'
        )
        self.assertion = BadgeAssertionFactory(
            user=self.user, course_id=self.course.id, data={
                'image': 'http://www.example.com/image.png',
                'json': {'id': 'http://www.example.com/assertion.json'},
                'issuer': 'http://www.example.com/issuer.json',
            },
        )
        # Enabling the feature flag isn't enough to change the URLs-- they're already loaded by this point.
        self.old_patterns = urls.urlpatterns
        urls.urlpatterns += (urls.BADGE_SHARE_TRACKER_URL,)

    def tearDown(self):
        super(TrackShareRedirectTest, self).tearDown()
        urls.urlpatterns = self.old_patterns

    def test_social_event_sent(self):
        test_url = '/certificates/badge_share_tracker/{}/social_network/{}/'.format(
            unicode(self.course.id),
            self.user.username,
        )
        self.recreate_tracker()
        response = self.client.get(test_url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], 'http://www.example.com/image.png')
        assert_event_matches(
            {
                'name': 'edx.badges.assertion.shared',
                'data': {
                    'course_id': 'testorg/run1/trackable_course',
                    'social_network': 'social_network',
                    # pylint: disable=no-member
                    'assertion_id': self.assertion.id,
                    'assertion_json_url': 'http://www.example.com/assertion.json',
                    'assertion_image_url': 'http://www.example.com/image.png',
                    'user_id': self.user.id,
                    'issuer': 'http://www.example.com/issuer.json',
                    'enrollment_mode': 'honor',
                },
            },
            self.get_event()
        )
