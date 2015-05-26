"""
NOTE: this API is WIP and has not yet been approved. Do not use this API without talking to Christina or Andy.

For more information, see:
https://openedx.atlassian.net/wiki/display/TNL/Team+API
"""
from rest_framework.views import APIView
from rest_framework.generics import GenericAPIView, RetrieveUpdateAPIView
from rest_framework.mixins import RetrieveModelMixin, UpdateModelMixin
from rest_framework.serializers import ValidationError
from rest_framework.response import Response
from rest_framework import status
from rest_framework import permissions
from rest_framework.parsers import JSONParser

from django.db import transaction
from django.db.models import Count
from django.utils.translation import ugettext as _

from openedx.core.lib.api.authentication import (
    SessionAuthenticationAllowInactiveUser,
    OAuth2AuthenticationAllowInactiveUser,
)
from openedx.core.lib.api.parsers import MergePatchParser
from openedx.core.lib.api.permissions import IsUserInUrlOrStaff, IsStaffOrReadOnly, IsActiveOrReadOnly
from openedx.core.lib.api.serializers import PaginationSerializer
#from ..errors import UserNotFound, UserNotAuthorized

from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey

from courseware.courses import get_course

from .models import CourseTeam, CourseTeamMembership
from .serializers import CourseTeamSerializer, MembershipSerializer


class RetrievePatchAPIView(RetrieveModelMixin, UpdateModelMixin, GenericAPIView):
    """
    Concrete view for retrieving and updating a model instance. Like DRF's RetriveUpdateAPIView, but without PUT.
    """
    def get(self, request, *args, **kwargs):
        return self.retrieve(request, *args, **kwargs)

    def patch(self, request, *args, **kwargs):
        field_errors = self._validate_patch(request.DATA)
        if field_errors:
            return Response({'field_errors': field_errors}, status=status.HTTP_400_BAD_REQUEST)
        return self.partial_update(request, *args, **kwargs)

    def _validate_patch(self, patch):
        field_errors = {}
        serializer = self.get_serializer(self.get_object_or_none(), data=patch, partial=True)
        fields = self.get_serializer().get_fields()

        for key in patch:
            if key not in fields:
                field_errors[key] = {
                    'developer_message': "This field is not present on this resource",
                }
            elif fields[key].read_only:
                field_errors[key] = {
                    'developer_message': "This field is not editable",
                }

        if not serializer.is_valid():
            errors = serializer.errors
            for key, error in errors.iteritems():
                field_errors[key] = {
                    'developer_message': u"Value '{field_value}' is not valid for field '{field_name}': {error}".format(
                        field_value=patch[key], field_name=key, error=error
                    ),
                    'user_message': _(u"This value is invalid."),
                }

        return field_errors


class TeamsListView(GenericAPIView):

    # SessionAuthenticationAllowInactiveUser must come first to return a 403 for unauthenticated users
    authentication_classes = (SessionAuthenticationAllowInactiveUser, OAuth2AuthenticationAllowInactiveUser)
    permission_classes = (permissions.IsAuthenticated, IsActiveOrReadOnly)

    paginate_by = 10
    paginate_by_param = 'page_size'
    pagination_serializer_class = PaginationSerializer
    serializer_class = CourseTeamSerializer

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
        if 'include_inactive' in request.QUERY_PARAMS and request.QUERY_PARAMS['include_inactive'] == 'true':
            del result_filter['is_active']
        if 'text_search' in request.QUERY_PARAMS:
            return Response({'detail': "text_search is not yet supported"}, status=status.HTTP_400_BAD_REQUEST)

        queryset = CourseTeam.objects.filter(**result_filter)

        order_by_field = 'name'
        if 'order_by' in request.QUERY_PARAMS:
            order_by_input = request.QUERY_PARAMS['order_by']
            if order_by_input == 'name':
                order_by_field = 'name'
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

    authentication_classes = (SessionAuthenticationAllowInactiveUser, OAuth2AuthenticationAllowInactiveUser)
    permission_classes = (permissions.IsAuthenticated, IsStaffOrReadOnly)
    lookup_field = 'team_id'
    serializer_class = CourseTeamSerializer
    parser_classes = (MergePatchParser,)

    def get_queryset(self):
        return CourseTeam.objects.all()

#
# class TeamMembershipListView(APIView):
#
#     authentication_classes = (OAuth2AuthenticationAllowInactiveUser, SessionAuthenticationAllowInactiveUser)
#     #permission_classes = (permissions.IsAuthenticated,)
#
#     def get(self, request):
#         """
#         GET /api/team/v0/team_membership
#         """
#         serializer = MembershipSerializer(CourseTeamMembership.objects.all(), many=True)
#         return Response(serializer.data)
#
# class TeamMembershipDetailView(APIView):
#
#     def get(self, request, team_id, username):
#         """
#         GET /api/team/v0/team_membership/{team_id},{username}
#         """
#
#         try:
#             membership = CourseTeamMembership.objects.get(team__team_id=team_id, user__username=username)
#             return Response(MembershipSerializer(membership).data)
#         except CourseTeamMembership.DoesNotExist:
#             return Response(status=status.HTTP_404_NOT_FOUND)
