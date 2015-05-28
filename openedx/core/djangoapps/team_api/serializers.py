from django.contrib.auth.models import User
from rest_framework import serializers
from .models import CourseTeam, CourseTeamMembership
from ..user_api.serializers import UserSerializer


class ExpandableField(serializers.Field):
    def __init__(self, **kwargs):
        if 'collapsed_serializer' not in kwargs or 'expanded_serializer' not in kwargs:
            raise ValueError
        self.collapsed = kwargs.pop('collapsed_serializer')
        self.expanded = kwargs.pop('expanded_serializer')
        super(ExpandableField, self).__init__(**kwargs)

    def field_to_native(self, obj, field_name):
        if 'expand' in self.context and field_name in self.context['expand']:
            self.expanded.initialize(self, field_name)
            return self.expanded.field_to_native(obj, field_name)
        else:
            self.collapsed.initialize(self, field_name)
            return self.collapsed.field_to_native(obj, field_name)


class CollapsedUserSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='accounts_api', lookup_field='username')

    class Meta:
        model = User
        fields = ("username", "url")


class CollapsedCourseTeamSerializer(serializers.HyperlinkedModelSerializer):
    id = serializers.CharField(source='team_id')
    url = serializers.HyperlinkedIdentityField(view_name='teams_detail', lookup_field='team_id')

    class Meta:
        model = CourseTeam
        fields = ("id", "url")


class UserMembershipSerializer(serializers.ModelSerializer):
    user = ExpandableField(
        collapsed_serializer=CollapsedUserSerializer(),
        expanded_serializer=UserSerializer(),
    )

    class Meta:
        model = CourseTeamMembership
        fields = ("user", "date_joined")


class MembershipSerializer(serializers.ModelSerializer):
    user = CollapsedUserSerializer()
    team = CollapsedCourseTeamSerializer()

    class Meta:
        model = CourseTeamMembership
        fields = ("user", "team", "date_joined")


class CourseTeamSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source='team_id', read_only=True)
    membership = UserMembershipSerializer(many=True, read_only=True)

    class Meta:
        model = CourseTeam
        fields = ("id", "name", "is_active", "course_id", "topic_id", "date_created", "description", "country", "language", "membership")
        read_only_fields = ("course_id", "date_created")
