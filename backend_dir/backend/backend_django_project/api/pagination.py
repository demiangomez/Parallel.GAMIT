from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response


class CustomPagination(LimitOffsetPagination):
    """
    Does the same as LimitOffsetPagination it doesnt return any of the additional pagination-related fields.
    Adds a total_count field to the response, which contains the total number of items in the queryset.
    That way, the front-end can compute how many pages there are in total.
    """

    def paginate_queryset(self, queryset, request, view=None):
        self.custom_queryset = queryset

        return super().paginate_queryset(queryset, request, view)

    def get_paginated_response(self, data):
        response_data = {"total_count": super().get_count(
            self.custom_queryset), "data": data}

        return Response(response_data)

    def get_paginated_response_schema(self, schema):
        return {
            'type': 'object',
            'properties': {
                'count': {
                    'type': 'integer',
                    'example': 10,
                    'description': 'the number of objects retrieved AFTER pagination (if required) and AFTER filtering'
                },
                'total_count': {
                    'type': 'integer',
                    'example': 10,
                    'description': 'the number of objects BEFORE pagination (if required) and AFTER filtering'
                },
                'result': schema
            }
        }
