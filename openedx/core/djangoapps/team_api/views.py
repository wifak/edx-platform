"""
NOTE: this API is WIP and has not yet been approved. Do not use this API without talking to Christina or Andy.

For more information, see:
https://openedx.atlassian.net/wiki/display/TNL/Team+API
"""
from rest_framework.generics import GenericAPIView
from rest_framework.serializers import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
from rest_framework import permissions

from django.core.paginator import Paginator
from django.db.models import Count

from student.models import CourseEnrollment

import sys

from openedx.core.lib.api.authentication import (
    SessionAuthenticationAllowInactiveUser,
    OAuth2AuthenticationAllowInactiveUser,
)
from openedx.core.lib.api.parsers import MergePatchParser
from openedx.core.lib.api.permissions import IsUserInUrlOrStaff, IsStaffOrReadOnly, IsActiveOrReadOnly
from openedx.core.lib.api.view_utils import RetrievePatchAPIView
# from ..errors import UserNotFound, UserNotAuthorized
from xmodule.modulestore.django import modulestore

from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey

from courseware.courses import get_course

from .models import CourseTeam
from .serializers import CourseTeamSerializer


class TeamsListView(GenericAPIView):
    """
        **Use Cases**

            Get or create a course team.

        **Example Requests**:

            GET /api/team/v0/teams

            POST /api/team/v0/teams

        **Response Values for GET**

            The following options can be specified as query parameters:

            * course_id: Filters the result to teams belonging to the given course.

            * topic_id: Filters the result to teams associated with the given topic.

            * text_search: Currently not supported.

            * order_by: Must be one of the following:

                * name: Orders results by case insensitive team name (default).

                * open_slots: Orders results by most open slots.

                * last_activity: Currently not supported.

            * page_size: Number of results to return per page.

            * page: Page number to retrieve.

            * include_inactive: If true, inactive teams will be returned. The default is to not include inactive teams.

            If the user is logged in, the response contains:

            * count: The total number of teams matching the request.

            * next: The URL to the next page of results, or null if this is the last page.

            * previous: The URL to the previous page of results, or null if this is the first page.

            * num_pages: The total number of pages in the result.

            * results: A list of the teams matching the request.

                * id: The team's unique identifier.

                * name: The name of the team.

                * is_active: True if the team is currently active. If false, the team is considered "soft deleted" and
                  will not be included by default in results.

                * course_id: The identifier for the course this team belongs to.

                * topic_id: Optionally specifies which topic the team is associated with.

                * date_created: Date and time when the team was created.

                * description: A description of the team.

                * country: Optionally specifies which country the team is associated with.

                * language: Optionally specifies which language the team is associated with.

                * membership: A list of the users that are members of the team. See membership endpoint for more detail.

            For all text fields, clients rendering the values should take care
            to HTML escape them to avoid script injections, as the data is
            stored exactly as specified. The intention is that plain text is
            supported, not HTML.

            If the user is not logged in, a 403 error is returned.

            If the specified course_id is not valid or the user attempts to
            use an unsupported query parameter, a 400 error is returned.

            If the response does not exist, a 404 error is returned. For
            example, the course_id may not reference a real course or the page
            number may be beyond the last page.

        **Response Values for POST**

            Any logged in user who has verified their email address can create
            a team. The format mirrors that of a GET for an individual team,
            but does not include the id, is_active, date_created, or membership
            fields. id is automatically computed based on name.

            If the user is not logged in or has not verified their email, a
            403 error is returned.

            If the course_id is not valid or extra fields are included in the
            request, a 400 error is returned.

            If the specified course does not exist, a 404 error is returned.
    """

    # SessionAuthenticationAllowInactiveUser must come first to return a 403 for unauthenticated users
    authentication_classes = (SessionAuthenticationAllowInactiveUser, OAuth2AuthenticationAllowInactiveUser)
    permission_classes = (permissions.IsAuthenticated, IsActiveOrReadOnly)

    paginate_by = 10
    paginate_by_param = 'page_size'
    pagination_serializer_class = PaginationSerializer
    serializer_class = CourseTeamSerializer

    def get_serializer_context(self):
        """
        Adds expand information from query parameters to the serializer context to support expandable fields.
        """
        result = super(TeamsListView, self).get_serializer_context()
        result['expand'] = [x for x in self.request.QUERY_PARAMS.get('expand', '').split(',') if x]
        return result

    def get(self, request):
        """
        GET /api/team/v0/teams/
        """
        result_filter = {
            'is_active': True
        }

        if 'course_id' in request.QUERY_PARAMS:
            try:
                course_key = CourseKey.from_string(request.QUERY_PARAMS['course_id'])
                result_filter.update({'course_id': course_key})
            except InvalidKeyError:
                return Response({'detail': "course_id is not valid"}, status=status.HTTP_400_BAD_REQUEST)
        if 'topic_id' in request.QUERY_PARAMS:
            result_filter.update({'topic_id': request.QUERY_PARAMS['topic_id']})
        if 'include_inactive' in request.QUERY_PARAMS and request.QUERY_PARAMS['include_inactive'].lower() == 'true':
            del result_filter['is_active']
        if 'text_search' in request.QUERY_PARAMS:
            return Response({'detail': "text_search is not yet supported"}, status=status.HTTP_400_BAD_REQUEST)

        queryset = CourseTeam.objects.filter(**result_filter)
        queryset = queryset.extra(select={'lower_name': "lower(name)"})

        order_by_field = 'lower_name'
        if 'order_by' in request.QUERY_PARAMS:
            order_by_input = request.QUERY_PARAMS['order_by']
            if order_by_input == 'name':
                order_by_field = 'lower_name'
            elif order_by_input == 'open_slots':
                queryset = queryset.annotate(team_size=Count('users'))
                order_by_field = 'team_size'
            elif order_by_input == 'last_activity':
                return Response({'detail': "last_activity is not yet supported"}, status=status.HTTP_400_BAD_REQUEST)

        queryset = queryset.order_by(order_by_field)

        if not queryset:
            return Response(status=status.HTTP_404_NOT_FOUND)

        page = self.paginate_queryset(queryset)
        serializer = self.get_pagination_serializer(page)
        return Response(serializer.data)

    def post(self, request):
        """
        POST /api/team/v0/teams/
        """
        field_errors = {}
        course_key = None

        try:
            course_key = CourseKey.from_string(request.DATA.get('course_id'))
            get_course(course_key)
        except InvalidKeyError:
            field_errors['course_id'] = {
                'developer_message': "course_id is not valid.",
            }
        except ValueError:
            return Response(status=status.HTTP_404_NOT_FOUND)

        for key in request.DATA:
            if key not in ['name', 'course_id', 'description', 'topic_id', 'country', 'language']:
                field_errors[key] = {
                    'developer_message': "This field is not present on this resource",
                }

        team = CourseTeam.create(
            name=request.DATA.get('name', ""),
            course_id=course_key,
            description=request.DATA.get('description', ""),
            topic_id=request.DATA.get('topic_id'),
            country=request.DATA.get('country'),
            language=request.DATA.get('language'),
        )

        try:
            team.full_clean()
            team.save()
        except ValidationError as e:
            for key, error in e.message_dict.iteritems():
                field_errors[key] = {
                    'developer_message': error[0],
                }

        if field_errors:
            return Response({
                'field_errors': field_errors,
            }, status=status.HTTP_400_BAD_REQUEST)

        return Response(CourseTeamSerializer(team).data)


class TeamsDetailView(RetrievePatchAPIView):
    """
        **Use Cases**

            Get or update a course team's information. Updates are supported
            only through merge patch.

        **Example Requests**:

            GET /api/team/v0/teams/{team_id}}

            PATCH /api/team/v0/teams/{team_id} "application/merge-patch+json"

        **Response Values for GET**

            If the user is logged in, the response contains the following fields:

            * id: The team's unique identifier.

            * name: The name of the team.

            * is_active: True if the team is currently active. If false, the team is considered "soft deleted" and
              will not be included by default in results.

            * course_id: The identifier for the course this team belongs to.

            * topic_id: Optionally specifies which topic the team is associated with.

            * date_created: Date and time when the team was created.

            * description: A description of the team.

            * country: Optionally specifies which country the team is associated with.

            * language: Optionally specifies which language the team is associated with.

            * membership: A list of the users that are members of the team. See membership endpoint for more detail.

            For all text fields, clients rendering the values should take care
            to HTML escape them to avoid script injections, as the data is
            stored exactly as specified. The intention is that plain text is
            supported, not HTML.

            If the user is not logged in, a 403 error is returned.

            If the specified team does not exist, a 404 error is returned.

        **Response Values for PATCH**

            Only staff can patch teams. If the specified team does not exist, a
            404 error is returned.

            If "application/merge-patch+json" is not the specified content type,
            a 415 error is returned.

            If the update could not be completed due to validation errors, this
            method returns a 400 error with all error messages in the
            "field_errors" field of the returned JSON.
    """

    authentication_classes = (SessionAuthenticationAllowInactiveUser, OAuth2AuthenticationAllowInactiveUser)
    permission_classes = (permissions.IsAuthenticated, IsStaffOrReadOnly)
    lookup_field = 'team_id'
    serializer_class = CourseTeamSerializer
    parser_classes = (MergePatchParser,)

    def get_queryset(self):
        """
        Returns the queryset used to access the given team.
        """
        return CourseTeam.objects.all()


class TeamMembershipListView(APIView):

    authentication_classes = (OAuth2AuthenticationAllowInactiveUser, SessionAuthenticationAllowInactiveUser)
    #permission_classes = (permissions.IsAuthenticated,)

    def get(self, request):
        """
        GET /api/team/v0/team_membership
        """
        serializer = MembershipSerializer(CourseTeamMembership.objects.all(), many=True)
        return Response(serializer.data)


class TeamMembershipDetailView(APIView):

    def get(self, request, team_id, username):
        """
        GET /api/team/v0/team_membership/{team_id},{username}
        """

        try:
            membership = CourseTeamMembership.objects.get(team__team_id=team_id, user__username=username)
            return Response(MembershipSerializer(membership).data)
        except CourseTeamMembership.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)


class TopicListView(APIView):
    """HTTP endpoint for retreiving a list of topics for a given course."""

    authentication_classes = (SessionAuthenticationAllowInactiveUser,)
    permission_classes = (permissions.IsAuthenticated,)

    page_size = 10
    # TODO determine the correct max page size
    max_page_size = sys.maxint

    def get(self, request):
        """
        GET /api/team/v0/topics/?course_id={course_id}
        """
        try:
            course_id_string = request.QUERY_PARAMS.get('course_id', None)
            if course_id_string is None:
                return Response(status=status.HTTP_400_BAD_REQUEST)

            course_id = CourseKey.from_string(course_id_string)

            course_module = modulestore().get_course(course_id)
            if course_module is None:  # course is None if not found
                return Response(status=status.HTTP_404_NOT_FOUND)

            if CourseEnrollment.get_enrollment(request.user, course_id) is None:
                return Response({'detail': "user must be enrolled"}, status=status.HTTP_403_FORBIDDEN)

            topics = [t for t in course_module.teams_topics if t['is_active']]

            if 'text_search' in request.QUERY_PARAMS:
                return Response({'detail': "text_search is not yet supported"}, status=status.HTTP_400_BAD_REQUEST)

            ordering = request.QUERY_PARAMS.get('order_by', 'name')
            if ordering == 'name':
                topics = sorted(topics, key=lambda t: t['name'])
            elif ordering == 'team_count':
                topics = sorted(topics, cmp=lambda t1, t2: t1['team_count'] > t2['team_count'])
            else:
                return Response({'detail': "unsupported order_by value {}".format(ordering)},
                                status=status.HTTP_400_BAD_REQUEST)

            if 'page_size' in request.QUERY_PARAMS:
                self.page_size = min(self.max_page_size, int(request.QUERY_PARAMS['page_size']))

            paginator = Paginator(topics, self.page_size)
            page = paginator.page(request.QUERY_PARAMS.get('page', 1))
            serializer = PaginationSerializer(instance=page)
            return Response(serializer.data)  # May be None
        except InvalidKeyError:
            return Response(status=status.HTTP_404_NOT_FOUND)


class TopicDetailView(APIView):
    """HTTP endpoint for retreiving details of a particular topic."""

    authentication_classes = (SessionAuthenticationAllowInactiveUser,)
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, topic_id, course_id):
        """
        GET /api/team/v0/topics/{topic_id},{course_id}/
        """
        try:
            course_id = CourseKey.from_string(course_id)
            course_module = modulestore().get_course(course_id)
            if course_module is None:
                return Response(status=status.HTTP_404_NOT_FOUND)

            if CourseEnrollment.get_enrollment(request.user, course_id) is None:
                return Response({'detail': "user must be enrolled"}, status=status.HTTP_403_FORBIDDEN)

            topics = [t for t in course_module.teams_topics if t['id'] == topic_id]

            if len(topics) == 0:
                return Response(status=status.HTTP_404_NOT_FOUND)

            topic = topics[0]

            if not topic['is_active']:
                return Response(status=status.HTTP_404_NOT_FOUND)

            return Response(topic)
        except InvalidKeyError:
            return Response(status=status.HTTP_404_NOT_FOUND)
