from rest_framework.views import exception_handler
from django.db.utils import IntegrityError
from rest_framework.response import Response
from rest_framework import status
from drf_standardized_errors.handler import ExceptionHandler
from rest_framework.exceptions import APIException


class CustomIntegrityErrorExceptionHandler(APIException):
    """
        Class built mainly for handling some foreign key errors,
        which are not handled by Django models,
        but by the database itself. With this class, we can
        display error details to the user.
    """
    status_code = 400
    default_code = 'IntegrityError occurred in db.'
    default_detail = 'IntegrityError occurred in db.'


class CustomValidationErrorExceptionHandler(APIException):
    status_code = 400
    default_code = 'ValidationError occurred.'
    default_detail = 'ValidationError occurred.'


class CustomServerErrorExceptionHandler(APIException):
    status_code = 400
    default_code = 'ServerError occurred.'
    default_detail = 'ServerError occurred.'


class CustomExceptionHandler(ExceptionHandler):
    """
        This custom handler makes CustomIntegrityErrorExceptionHandler perform instead
        of the default handler for IntegrityError exceptions.
    """

    def convert_known_exceptions(self, exc: Exception) -> Exception:
        if isinstance(exc, IntegrityError):
            return CustomIntegrityErrorExceptionHandler(str(exc))
        else:
            return super().convert_known_exceptions(exc)
