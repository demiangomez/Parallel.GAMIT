from django.db import models

class BitField(models.Field):
    """
    Custom field to map PostgreSQL's bit(1) type to a Django field,
    since Django doesn't have a built-in field for this type.

    The fields functions as a boolean field, but is stored as a bit(1) in the database.
    """
    def from_db_value(self, value, expression, connection):
        if value is None:
            return value
        return True if value == '1' else False

    def get_prep_value(self, value):
        if value is None:
            return value
        return '1' if value is True else '0'

    def db_type(self, connection):
        return 'bit(1)'