# common/exceptions.py
from django.db import IntegrityError
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status

def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is None and isinstance(exc, IntegrityError):
        return Response(
            {"detail": "Database integrity error: " + str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return response
