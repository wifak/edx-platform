"""
Defines serializers used by the Teams API.
"""

from django.contrib.auth.models import User
from rest_framework import serializers
from openedx.core.lib.api.fields import ExpandableField
from .models import CourseTeam, CourseTeamMembership
from openedx.core.djangoapps.user_api.serializers import UserSerializer


class CollapsedUserSerializer(serializers.HyperlinkedModelSerializer):
    """
    Serializes users in a collapsed format, with just a username and url.
    """
    url = serializers.HyperlinkedIdentityField(view_name='accounts_api', lookup_field='username')

    class Meta(object):
        """
        Defines meta information for the ModelSerializer.
        """
        model = User
        fields = ("username", "url")
        read_only_fields = ("username",)


class CollapsedCourseTeamSerializer(serializers.HyperlinkedModelSerializer):
    """
    Serializes CourseTeams in a collapsed format, with just an id and url.
    """
    id = serializers.CharField(source='team_id', read_only=True)  # pylint: disable=invalid-name
    url = serializers.HyperlinkedIdentityField(view_name='teams_detail', lookup_field='team_id')

    class Meta(object):
        """
        Defines meta information for the ModelSerializer.
        """
        model = CourseTeam
        fields = ("id", "url")


class UserMembershipSerializer(serializers.ModelSerializer):
    """
    Serializes CourseTeamMemberships with only information about the user and date_joined, for listing team members.
    """
    user = ExpandableField(
        collapsed_serializer=CollapsedUserSerializer(),
        expanded_serializer=UserSerializer(),
    )

    class Meta(object):
        """
        Defines meta information for the ModelSerializer.
        """
        model = CourseTeamMembership
        fields = ("user", "date_joined")
        read_only_fields = ("date_joined",)


class MembershipSerializer(serializers.ModelSerializer):
    """
    Serializes CourseTeamMemberships with information about both teams and users.
    """
    user = CollapsedUserSerializer(read_only=True)
    team = CollapsedCourseTeamSerializer(read_only=True)

    class Meta(object):
        """
        Defines meta information for the ModelSerializer.
        """
        model = CourseTeamMembership
        fields = ("user", "team", "date_joined")
        read_only_fields = ("date_joined",)


class CourseTeamSerializer(serializers.ModelSerializer):
    """
    Serializes a CourseTeam with membership information.
    """
    id = serializers.CharField(source='team_id', read_only=True)  # pylint: disable=invalid-name
    membership = UserMembershipSerializer(many=True, read_only=True)

    class Meta(object):
        """
        Defines meta information for the ModelSerializer.
        """
        model = CourseTeam
        fields = (
            "id",
            "name",
            "is_active",
            "course_id",
            "topic_id",
            "date_created",
            "description",
            "country",
            "language",
            "membership",
        )
        read_only_fields = ("course_id", "date_created")


class TopicSerializer(serializers.Serializer):
    """Serializes a topic."""
    description = serializers.CharField()
    name = serializers.CharField()
    id = serializers.CharField()  # pylint: disable=invalid-name
