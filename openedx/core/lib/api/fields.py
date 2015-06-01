"""Common DRF serializer fields"""
from django.core.exceptions import ValidationError

from rest_framework.fields import CharField


class NonEmptyCharField(CharField):
    """
    A field that enforces non-emptiness even for partial updates.

    This is necessary because prior to version 3, DRF skips validation for empty
    values. Thus, CharField's min_length and RegexField cannot be used to
    enforce this constraint.
    """
    def validate(self, value):
        super(NonEmptyCharField, self).validate(value)
        if not value:
            raise ValidationError(self.error_messages["required"])
