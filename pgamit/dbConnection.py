"""
Project: Parallel.Archive
Date: 02/16/2017
Author: Demian D. Gomez

This class is used to connect to the database and handles inserts, updates and selects
It also handles the error, info and warning messages
"""

import platform
import configparser
import inspect
import re
import psycopg2
import psycopg2.extras
import psycopg2.extensions
from decimal import Decimal

# app
from pgamit.Utils import file_read_all, file_append, create_empty_cfg


DB_HOST = 'localhost'
DB_USER = 'postgres'
DB_PASS = ''
DB_NAME = 'gnss_data'


DEBUG = False


def cast_array_to_float(recordset):

    if len(recordset) > 0:
        if not isinstance(recordset[0], dict):
            result = []
            for record in recordset:
                new_record = []
                for field in record:
                    if isinstance(field, list):
                        new_record.append([float(value) if isinstance(value, Decimal) else value for value in field])
                    else:
                        if isinstance(field, Decimal):
                            new_record.append(float(field))
                        else:
                            new_record.append(field)

                result.append(tuple(new_record))

            return result
        else:
            # Convert any DECIMAL values to float
            for record in recordset:
                for key, value in record.items():
                    if isinstance(value, Decimal):
                        record[key] = float(value)
                    elif isinstance(value, list) and all(isinstance(i, Decimal) for i in value):
                        record[key] = [float(i) for i in value]

    return recordset


# class to match the pygreSQl structure using psycopg2
class query_obj(object):
    def __init__(self, cursor):
        self.rows = []
        # to maintain backwards compatibility
        try:
            self.rows = cast_array_to_float(cursor.fetchall())
        except psycopg2.ProgrammingError as e:
            if 'no results to fetch' in str(e):
                pass
            else:
                raise e

    def dictresult(self):
        return self.rows

    def ntuples(self):
        return len(self.rows)

    def getresult(self):
        return [tuple(d.values()) for d in self.rows]

    def __len__(self):
        return len(self.rows)


def debug(s):
    if DEBUG:
        file_append('/tmp/db.log', "DB: %s\n" % s)


class dbErrInsert (psycopg2.errors.UniqueViolation): pass


class dbErrUpdate (Exception): pass


class dbErrConnect(Exception): pass


class dbErrDelete (Exception): pass


class DatabaseError(psycopg2.DatabaseError): pass


class Cnn(object):

    def __init__(self, configfile, use_float=False, write_cfg_file=False):

        options = {'hostname': DB_HOST,
                   'username': DB_USER,
                   'password': DB_PASS,
                   'database': DB_NAME}

        self.active_transaction = False
        self.options            = options
        
        # parse session config file
        config = configparser.ConfigParser()

        try:
            config.read_string(file_read_all(configfile))
        except FileNotFoundError:
            if write_cfg_file:
                create_empty_cfg()
                print(' >> No gnss_data.cfg file found, an empty one has been created. Replace all the necessary '
                      'config and try again.')
                exit(1)
            else:
                raise
        # get the database config
        options.update(dict(config.items('postgres')))

        # register an adapter to convert decimal to float
        # see: https://www.psycopg.org/docs/faq.html#faq-float
        DEC2FLOAT = psycopg2.extensions.new_type(
            psycopg2.extensions.DECIMAL.values,
            'DEC2FLOAT',
            lambda value, curs: float(value) if value is not None else None)

        # Define the custom type for an array of decimals
        DECIMAL_ARRAY_TYPE = psycopg2.extensions.new_type(
            (psycopg2.extensions.DECIMAL.values,),  # This matches the type codes for DECIMAL
            'DECIMAL_ARRAY',  # Name of the type
            lambda value, curs: [float(d) for d in value] if value is not None else None
        )

        psycopg2.extensions.register_type(DEC2FLOAT)
        psycopg2.extensions.register_type(DECIMAL_ARRAY_TYPE)

        # open connection to server
        err = None
        for i in range(3):
            try:
                self.cnn = psycopg2.connect(host=options['hostname'], user=options['username'],
                                            password=options['password'], dbname=options['database'])

                self.cnn.autocommit = True
                self.cursor = self.cnn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

                debug("Database connection established")

            except psycopg2.Error as e:
                raise e
            else:
                break
        else:
            raise dbErrConnect(err)

    def query(self, command):
        try:
            self.cursor.execute(command)

            debug(" QUERY: command=%r" % command)

            # passing a query object to match response from pygresql
            return query_obj(self.cursor)
        except Exception as e:
            raise DatabaseError(e)

    def query_float(self, command, as_dict=False):
        # deprecated: using psycopg2 now solves the problem of returning float numbers
        # still in to maintain backwards compatibility
        try:
            if not as_dict:
                cursor = self.cnn.cursor()
                cursor.execute(command)
                recordset = cast_array_to_float(cursor.fetchall())
            else:
                # return results as a dictionary
                self.cursor.execute(command)
                recordset = cast_array_to_float(self.cursor.fetchall())

            return recordset
        except Exception as e:
            raise DatabaseError(e)

    def get(self, table, filter_fields, return_fields=None, limit=None):
        """
        Selects from the given table the records that match filter_fields and returns ONE dictionary.
        Method should not be used to retrieve more than one single record.
        Parameters:
        table (str): The table to select from.
        filter_fields (dict): The dictionary where the keys are the field names and the values are the filter values.
        return_fields (list of str): The fields to return. If empty return all columns
        limit (int): sets a limit for rows in case it is a query to determine if records exist

        Returns:
        list: A list of dictionaries, each representing a record that matches the filter.
        """

        if return_fields is None:
            return_fields = list(self.get_columns(table).keys())

        where_clause = ' AND '.join([f'"{key}" = %s' if val is not None else f'"{key}" IS %s'
                                     for key, val in zip(filter_fields.keys(), filter_fields.values())])
        fields_clause = ', '.join([f'"{field}"' for field in return_fields])
        if where_clause:
            query = f'SELECT {fields_clause} FROM {table} WHERE {where_clause}'
        else:
            query = f'SELECT {fields_clause} FROM {table}'
        values = list(filter_fields.values())
        # new feature to limit the results
        if limit:
            query += ' LIMIT %i' % limit

        try:
            self.cursor.execute(query, values)
            records = self.cursor.fetchall()
            debug(f"SELECT: query={query}, values={values}")

            if len(records) > 0:
                return records[0]
            else:
                raise DatabaseError('query returned no records: ' + query)

        except psycopg2.Error as e:
            raise e

    def get_columns(self, table):
        tblinfo = self.query('select column_name, data_type from information_schema.columns where table_name=\'%s\''
                             % table).dictresult()

        return {field['column_name']: field['data_type'] for field in tblinfo}

    def begin_transac(self):
        # do not begin a new transaction with another one active.
        if self.active_transaction:
            self.rollback_transac()

        self.active_transaction = True
        self.cursor.execute('BEGIN TRANSACTION')

    def commit_transac(self):
        self.active_transaction = False
        self.cursor.execute('COMMIT')

    def rollback_transac(self):
        self.active_transaction = False
        self.cursor.execute('ROLLBACK')

    def insert(self, table, **kw):
        debug("INSERT: table=%r kw=%r" % (table, kw))

        # figure out any extra columns and remove them from the incoming **kw
        cols = list(self.get_columns(table).keys())

        # assuming fields are passed through kw which are keyword arguments
        fields = [k for k in kw.keys() if k in cols]
        values = [v for v, k in zip(kw.values(), kw.keys()) if k in cols]

        # form the insert query dynamically
        placeholders = ', '.join(['%s'] * len(fields))
        columns = '", "'.join(fields)
        query = f'INSERT INTO {table} ("{columns}") VALUES ({placeholders})'
        try:
            self.cursor.execute(query, values)
            self.cnn.commit()
        except psycopg2.errors.UniqueViolation as e:
            self.cnn.rollback()
            raise dbErrInsert(e)

    def update(self, table, set_row, **kwargs):
        """
        Updates the specified table with new field values. The row(s) are updated based on the primary key(s)
        indicated in the 'row' dictionary. New values are specified in kwargs. Field names must be enclosed
        with double quotes to handle camel case names.

        Parameters:
        table (str): The table to update.
        set_row (dict): New field values for the row.
        kwargs: The dictionary where the keys are the primary key fields and the values are the row's identifiers.
        """
        # Build the SET clause of the query
        set_clause = ', '.join([f'"{field}" = %s' for field in set_row.keys()])

        # Build the WHERE clause based on the row dictionary
        where_clause = ' AND '.join([f'"{key}" = %s' if val is not None else f'"{key}" IS %s'
                                     for key, val in zip(kwargs.keys(), kwargs.values())])
        # Construct query
        query = f'UPDATE {table} SET {set_clause} WHERE {where_clause}'

        # Values to use in the query
        values = list(set_row.values()) + list(kwargs.values())

        try:
            self.cursor.execute(query, values)
            self.cnn.commit()
            debug(f"UPDATE {table}: set={set_row}, where={kwargs}")
            debug(query)
        except psycopg2.Error as e:
            self.cnn.rollback()
            raise dbErrUpdate(e)

    def delete(self, table, **kw):
        """
        Deletes row(s) from the specified table based on the provided keyword arguments.

        Parameters:
        table (str): The table to delete from.
        kw: Keywords to identify the row(s) to be deleted.
        """
        debug("DELETE: table=%r kw=%r" % (table, kw))

        if not kw:
            raise ValueError("No conditions provided for deletion")

        where_clause = ' AND '.join([f'"{key}" = %s' if val is not None else f'"{key}" IS %s'
                                     for key, val in zip(kw.keys(), kw.values())])
        query = f'DELETE FROM {table} WHERE {where_clause}'
        values = list(kw.values())

        try:
            self.cursor.execute(query, values)
            self.cnn.commit()
            debug(f"DELETE FROM {table}: kw={kw}")
        except psycopg2.Error as e:
            self.cnn.rollback()
            raise dbErrDelete(e)

    def insert_event(self, event):
        debug("EVENT: event=%r" % (event.db_dict()))

        self.insert('events', **event.db_dict())

    def insert_event_bak(self, type, module, desc):
        debug("EVENT_BAK: type=%r module=%r desc=%r" % (type, module, desc))

        # do not insert if record exists
        desc = '%s%s' % (module, desc.replace('\'', ''))
        desc = re.sub(r'[^\x00-\x7f]+', '', desc)
        # remove commands from events
        # modification introduced by DDG (suggested by RS)
        desc = re.sub(r'BASH.*', '', desc)
        desc = re.sub(r'PSQL.*', '', desc)

        # warn = self.query('SELECT * FROM events WHERE "EventDescription" = \'%s\'' % (desc))

        # if warn.ntuples() == 0:
        self.insert('events', EventType=type, EventDescription=desc)

    def insert_warning(self, desc):
        self.insert_event_bak('warn', _caller_str(), desc)

    def insert_error(self, desc):
        self.insert_event_bak('error', _caller_str(), desc)

    def insert_info(self, desc):
        self.insert_event_bak('info', _caller_str(), desc)

    def close(self):
        self.cursor.close()
        self.cnn.close()

    def __del__(self):
        if self.active_transaction:
            self.cnn.rollback()


def _caller_str():
    # get the module calling to make clear how is logging this message
    frame = inspect.stack()[2]
    line   = frame[2]
    caller = frame[3]
    
    return '[%s:%s(%s)]\n' % (platform.node(), caller, str(line))

