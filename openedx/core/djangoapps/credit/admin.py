"""
Django admin page for credit eligibility
"""
from django.contrib import admin
from .models import CreditCourse


admin.site.register(CreditCourse)
