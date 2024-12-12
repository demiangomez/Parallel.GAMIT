from django.apps import AppConfig
import threading
import time
import schedule
import sys
import os


class ApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api'
    continuous_thread = None

    def ready(self):

        from django.conf import settings
        from django.core.exceptions import ImproperlyConfigured

        if int(getattr(settings, 'MAX_SIZE_IMAGE_MB', None)) > 75:
            raise ImproperlyConfigured(
                "MAX_SIZE_IMAGE_MB must be equal or less than 75 MB")

        if int(getattr(settings, 'MAX_SIZE_FILE_MB', None)) > 75:
            raise ImproperlyConfigured(
                "MAX_SIZE_FILE_MB must be equal or less than 75 MB")
