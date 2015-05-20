"""
Common utility functions useful throughout the certificates
"""
from django.core.urlresolvers import reverse


def get_certificate_url(user_id, course_id):
    """
    Generates a valid certificate url pointing to the web/html view
    """
    reverse_kwargs = dict(
        user_id=str(user_id),
        course_id=unicode(course_id)
    )
    return u'{url}'.format(url=reverse('cert_html_view', kwargs=reverse_kwargs))
