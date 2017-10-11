"""
Project:
Date: 10/10/17 3:07 PM
Author: Demian D. Gomez
"""

import pyTerminal
import pyOptions
import argparse
import dbConnection
import pyStationInfo
from datetime import datetime
import curses
from curses import panel
import time

cnn = dbConnection.Cnn('gnss_data.cfg')
Config = pyOptions.ReadOptions("gnss_data.cfg")  # type: pyOptions.ReadOptions
tc = pyTerminal.TerminalController()
selection = 0
stn = None
records = []

class Menu(object):

    def __init__(self, items, stdscreen, title='', type='main', record_index=None):
        self.window = stdscreen.subwin(0,0)
        self.window.keypad(1)
        self.panel = panel.new_panel(self.window)
        self.panel.hide()
        panel.update_panels()

        self.position = 0
        self.items = items
        if type == 'edit':
            self.items.append({'field': 'Save and exit', 'function': 'save_changes'})
        else:
            self.items.append({'field': 'Exit', 'function': 'exit'})

        self.title = title
        self.type = type
        self.edit_field = ''
        self.edit_mode = False
        self.edited_fields = dict()
        self.record_index = record_index

    def navigate(self, n):
        self.position += n
        if self.position < 0:
            self.position = 0
        elif self.position >= len(self.items):
            self.position = len(self.items)-1

    def display(self):
        self.panel.top()
        self.panel.show()
        self.window.clear()

        while True:
            self.window.refresh()

            if self.title:
                sx = 2
                self.window.addstr(1, 1, self.title, curses.color_pair(1))
            else:
                sx = 1

            curses.doupdate()
            for index, item in enumerate(self.items):
                if index == self.position:
                    mode = curses.A_REVERSE
                else:
                    mode = curses.A_NORMAL

                if self.type == 'edit' and index < len(self.items)-1:
                    if index == self.position and self.edit_mode:
                        msg = '%2d. %s' % (index, item['field'] + ': ' + self.edit_field)
                        self.window.addstr(sx + index, 1, msg, curses.color_pair(2))
                    else:
                        msg = '%2d. %s' % (index, item['field'] + ': ' + item['value'])
                        self.window.addstr(sx + index, 1, msg, mode)
                else:
                    msg = '%2d. %s' % (index, item['field'])
                    self.window.addstr(sx+index, 1, msg, mode)

            key = self.window.getch()

            if key in [curses.KEY_ENTER, ord('\n')]:
                if self.position == len(self.items) - 1 and self.type != 'edit':
                    break

                elif self.position < len(self.items) - 1 and self.type != 'edit':
                    self.items[self.position]['function'](self)

                else:
                    if not self.edit_mode:
                        if self.position == len(self.items) - 1:
                            # save changes
                            if save_changes(self):
                                break

                        else:
                            # enter edit mode
                            self.enter_edit_mode()

                    else:
                        if self.exit_edit_mode():
                            self.navigate(1)

            elif key == curses.KEY_UP and not self.edit_mode:
                self.navigate(-1)

            elif key == curses.KEY_DOWN and not self.edit_mode:
                self.navigate(1)

            elif key == 27:
                if self.edit_mode:
                    self.cancel_edit()
                else:
                    # exit screen
                    break
            else:
                if self.type == 'edit':
                    # edit mode, hightlight the field and replace text
                    if key == 4: # control + D
                        # ask if user want to delete record
                        self.window.addstr(sx + len(self.items), 1, 'Are you sure you want to delete this record?', curses.color_pair(2))
                        key = self.window.getch()
                        if chr(key).upper() == 'Y':
                            # delete record
                            delete_record(self)
                            break
                    else:
                        if not self.edit_mode:
                            self.enter_edit_mode(clear=True)

                        if key == curses.KEY_BACKSPACE or key == 127:
                            self.edit_field = self.edit_field[0:-1]

                        elif key < 256:
                            self.edit_field += chr(key)

                    self.window.clear()

        self.window.clear()
        self.panel.hide()
        panel.update_panels()
        curses.doupdate()

    def enter_edit_mode(self, clear=False):
        self.edit_mode = True
        if not clear:
            self.edit_field = self.items[self.position]['value']
        else:
            self.edit_field = ''
        self.window.clear()

    def exit_edit_mode(self):

        if self.items[self.position]['field'] in ['DateStart', 'DateEnd']:
            # VALIDATE THE date strings
            stninfo = pyStationInfo.StationInfoRecord()

            try:
                if self.edit_field == '' and self.items[self.position]['field'] == 'DateEnd':
                    _, self.edit_field = stninfo.datetime2stninfodate(datetime(2010,01,01), None)
                else:
                    date,_ = stninfo.stninfodate2datetime(self.edit_field, self.edit_field)
                    # if success, then reformat the datetime
                    self.edit_field, _ = stninfo.datetime2stninfodate(date, date)

            except Exception:
                self.ShowError('Invalid station information datetime format!')
                return False

        elif self.items[self.position]['field'] in ['AntennaEast', 'AntennaNorth', 'AntennaHeight']:
            # field has to be numeric
            try:
                _ = float(self.edit_field)

            except Exception:
                self.ShowError('Value must be numeric!')
                return False

        elif self.items[self.position]['field'] == 'HeightCode':

            if not self.edit_field.upper() in ['DHTGP', 'DHPAB', 'SLBDN', 'SLBCR', 'SLTEP', 'DHBCR', 'SLHGP', 'SLTGN', 'DHARP', 'SLBCE']:
                self.ShowError('Value must be one of the following: ' + ' '.join(['DHTGP', 'DHPAB', 'SLBDN', 'SLBCR', 'SLTEP', 'DHBCR', 'SLHGP', 'SLTGN', 'DHARP', 'SLBCE']))
                return False

            else:
                self.edit_field = self.edit_field.upper()
        else:
            self.edit_field = self.edit_field.upper()

        self.edited_fields[self.items[self.position]['field']] = self.edit_field
        self.items[self.position]['value'] = self.edit_field
        self.edit_field = ''
        self.edit_mode = False
        self.window.clear()
        return True

    def cancel_edit(self):
        self.edit_field = ''
        self.edit_mode = False
        self.window.clear()

    def abort_changes(self):
        exit()

    def ShowError(self, error):
        self.window.addstr(self.position + 2, 40, ' -> ' + error, curses.color_pair(2))
        self.window.refresh()
        time.sleep(2)
        if self.position < len(self.items)-1:
            self.edit_field = self.items[self.position]['value']
        self.window.clear()
        self.edit_mode = False


def delete_record(menu):
    global StnInfo

    if not 'New station information' in menu.title:
        StnInfo.DeleteStationInfo(StnInfo.records[menu.record_index])


def save_changes(menu):
    # trigger an update of the station info
    global StnInfo

    # check if there are any changes
    if len(menu.edited_fields.keys()) > 0:
        record = dict()
        stnrec = pyStationInfo.StationInfoRecord()

        record['NetworkCode'] = stn['NetworkCode']
        record['StationCode'] = stn['StationCode']

        for item in menu.items[0:-1]:
            if item['field'] in menu.edited_fields.keys():
                record[item['field']] = menu.edited_fields[item['field']]
            else:
                record[item['field']] = item['value']

            if item['field'] in ['DateStart', 'DateEnd']:

                if item['field'] == 'DateStart':
                    date, _ = stnrec.stninfodate2datetime(item['value'], item['value'])
                else:
                    _, date = stnrec.stninfodate2datetime('2010 001 00 00 00', item['value'])

                record[item['field']] = date

        # try to insert and catch errors
        try:
            if 'New station information' in menu.title:
                # insert new
                StnInfo.InsertStationInfo(record)
            else:
                # update a station info record
                StnInfo.UpdateStationInfo(StnInfo.records[menu.record_index], record)

        except Exception as e:
            menu.ShowError(str(e))
            return False

        # nothing failed, exit
    return True

def get_records():

    global StnInfo
    StnInfo = pyStationInfo.StationInfo(cnn, stn['NetworkCode'], stn['StationCode'], allow_empty=True)

    records = StnInfo.return_stninfo_short().split('\n')
    out = []

    for record in records:
        out.append({'field': record, 'function': selection_main_menu})

    return out


def selection_main_menu(menu):
    global StnInfo

    if menu.position < len(StnInfo.records):
        # edit
        edit_record(menu.position)

    elif menu.position == len(StnInfo.records):
        # insert new record
        record = dict()
        record['ReceiverCode'] = ''
        record['ReceiverSerial'] = ''
        record['ReceiverFirmware'] = ''
        record['AntennaCode'] = ''
        record['AntennaSerial'] = ''
        record['AntennaHeight'] = '0.000'
        record['AntennaNorth'] = '0.000'
        record['AntennaEast'] = '0.000'
        record['HeightCode'] = 'DHARP'
        record['RadomeCode'] = ''
        record['ReceiverVers'] = ''
        record['DateStart'] = ''
        record['DateEnd'] = ''

        new_record = []

        for field, value in record.iteritems():
            new_record.append({'field': field, 'value': str(value)})

        new_record = sorted(new_record, key=lambda k: k['field'])

        edit_menu = Menu(new_record, screen, 'New station information record (ESC to cancel)', 'edit')

        edit_menu.display()

    elif menu.position == len(StnInfo.records)+1:
        exit()

    # reload the main menu
    menu.items = get_records()
    menu.items += [{'field': 'Insert new station information record', 'function': selection_main_menu}]
    menu.items += [{'field': 'Exit', 'function': 'exit'}]

    return

def edit_record(position):

    global StnInfo

    items = get_fields(position)

    menu = Menu(items, screen, 'Editing (ESC to cancel): ' + StnInfo.return_stninfo_short().split('\n')[position], 'edit', record_index=position)

    menu.display()


def get_fields(position):
    out = []
    global StnInfo

    record = StnInfo.records[position]

    for field, value in record.iteritems():
        if field not in ['NetworkCode', 'StationCode']:
            if type(value) is str:
                out.append({'field': field, 'value': value})

            elif field in ['DateStart', 'DateEnd']:
                stnrec = pyStationInfo.StationInfoRecord()
                if field == 'DateStart':
                    date, _ = stnrec.datetime2stninfodate(value, value)
                else:
                    _, date = stnrec.datetime2stninfodate(datetime(2010,1,1), value)
                out.append({'field': field, 'value': date})

            else:
                out.append({'field': field, 'value': str(value)})

    return sorted(out, key=lambda k: k['field'])

class MyApp(object):

    def __init__(self, stdscreen):

        curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)
        curses.init_pair(2, curses.COLOR_RED, curses.COLOR_WHITE)

        global screen
        screen = stdscreen
        self.screen = stdscreen
        curses.curs_set(0)

        main_menu_items = get_records()

        main_menu_items += [{'field': 'Insert new station information record', 'function': selection_main_menu}]

        main_menu = Menu(main_menu_items, self.screen, 'Station information new/edit/delete - %s.%s' % (stn['NetworkCode'], stn['StationCode']))

        main_menu.display()

if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='Plot ETM for stations in the database')

    parser.add_argument('stn', type=str, nargs=1, help="Station name given in net.stnm format.")

    args = parser.parse_args()

    stn = args.stn[0]

    if '.' in stn:
        rs = cnn.query(
            'SELECT * FROM stations WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\' ORDER BY "NetworkCode", "StationCode"' % (
                stn.split('.')[0], stn.split('.')[1]))
    else:
        rs = cnn.query(
            'SELECT * FROM stations WHERE "StationCode" = \'%s\' ORDER BY "NetworkCode", "StationCode"' % (stn))

    if rs.ntuples() == 0:
        print tc.render('${RED}ERROR: Station code not found!${NORMAL}')
        exit()
    elif rs.ntuples() > 1:
        print tc.render('${RED}ERROR: More than one station found! Use net.stnm instead of stnm${NORMAL}')
        exit()
    else:
        stn = rs.dictresult()[0]

    curses.wrapper(MyApp)
