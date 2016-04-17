#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Import standard python modules
import argparse
from getpass import getpass
import csv
import json
import logging
import os
import re
import sys
from time import sleep
from multiprocessing import Process, Queue

# TextFSM module : https://github.com/google/textfsm
import clitable
import textfsm

# Netmiko module : https://github.com/ktbyers/netmiko
from netmiko import ConnectHandler, ssh_exception

# InfluxDB module : https://github.com/influxdata/influxdb-python
from influxdb import InfluxDBClient

CSV_DELIMITER = ','

# TESTFSM config settings
index_file = 'index'
template_dir = 'templates'

# INFLUXDBCLIENT config settings
db_host = '127.0.0.1'
db_port = 8086
db_name = 'db_name'
db_user = 'root'
db_password = 'root'

class SSH_Poller:
    """ SSH Poller class """

    hostname = ''
    username = ''
    password = ''
    command_list = []
    data_list = []
    prompt = ''
    parser_mode = ''
    interval = ''
    sock = ConnectHandler

    def __init__(self, task):
        self.hostname = task['hostname']
        self.username = task['username']
        self.password = task['password']
        self.device_type = task['device_type']
        self.parser_mode = task['parser_mode']
        
        for command in task['commands']:
            # Command doesn't contain tags attribute
            if len(command.split(':')) == 1:
                self.command_list.append({'command':command.split(':')[0], 'tag':''})
            # Command contains tags attribute
            elif len(command.split(':')) == 2:
                self.command_list.append({'command':command.split(':')[0], 'tag':command.split(':')[1]})

    def get_datalist(self):
        return data_list

    def connect(self):
        """ Connects SSH session """

        try:
            self.sock = ConnectHandler(
                    device_type=self.device_type,
                    ip=self.hostname,
                    username=self.username,
                    password=self.password)
            logging.debug('Connection to %s successful!' % self.hostname)            
            self.prompt = self.sock.find_prompt()

            if self.prompt:
                logging.debug('Prompt found: %s' % self.prompt)
            else:
                logging.debug('No prompt found')

        except ssh_exception.NetMikoAuthenticationException:
            logging.error('Authentication error, username was %s' % self.username)
            return False

        except:            
            print("Unexpected error:", sys.exc_info()[0])
            raise

        return True

    def disconnect(self):
        """ Disconnects SSH session """

        self.sock.disconnect()
        logging.debug('Connection cleaned-up')

    def parse_fsm(self, result, command):
        """ Parse command output through TextFSM """

        result = ''.join(result)
        cli_table = clitable.CliTable(index_file, template_dir)
        attrs = {'Command': command['command'], 'Platform': self.device_type}

        try:
            cli_table.ParseCmd(result, attrs)

            data = {}
            data['tag'] = command['tag']
            data['command'] = command['command']
            data['fields'] = clitable_to_dict(cli_table)

            # Convert values to float if possible
            data_float = []

            for i in data['fields']:
                i = dict((k, float_if_possible(v)) for (k, v) in i.items())
                data_float.append(i)
                data['fields'] = data_float          

            self.data_list.append(data)
            return True

        except clitable.CliTableError as e:
            logging.error('FSM parsing error: %s' % str(e))
            return False

    def parse_csv(self, result, command):
        """ Parse command output as csv """
        
        keys = result.split("\n")[0].split(CSV_DELIMITER)
        values =  result.split("\n")[1].split(CSV_DELIMITER)

        if len(keys) != len(values):
            logging.error('CSV format invalid')
            return False

        data = {}
        data['tag'] = command['tag']
        data['command'] = command['command']
        data['fields'] = []

        for i in range(0, len(keys) - 1):
            data['fields'].append({keys[i] : float_if_possible(values[i])})

        self.data_list.append(data)
        return True

    def send_commands(self):
        """ Send all commands in task
            Stores all parsed output in self.data_list
        """

        for command in self.command_list:
            logging.debug('Sending command: %s' % command['command'])
            result = self.sock.send_command(command['command'])
            if self.parser_mode == 'fsm':
                self.parse_fsm(result, command)
            elif self.parser_mode == 'csv':
                self.parse_csv(result, command)

    def output_json(self):
        """ Return results in JSON format """

        print(json.dumps(self.data_list, indent=2))

    def output_line(self):
        """ Return results in line protocol format """

        for data in self.data_list:
            for field in data['fields']:
                measurement = re.sub('\s', '_', data['command'])

                if data['tag']:
                    line = '%s,%s=%s,host=%s ' % (measurement, data['tag'], quotes_in_str(field[data['tag']]), quotes_in_str(self.hostname))
                else:
                    line = '%s,host=%s ' % (measurement, quotes_in_str(self.hostname))

                if data['tag']:
                    field.pop(data['tag'])

                i = len(field)
                j = 0

                for key, value in field.iteritems():
                    j = j + 1
                    if j == i:
                        line = '%s%s=%s' % (line, key, quotes_in_str(value))
                    else:
                        line = '%s%s=%s,' % (line, key, quotes_in_str(value))
            
                print line

    def output_influxdb(self):
        """ Writes data to the InfluxDB """

        for data in self.data_list:
            measurement = data['command']

            for field in data['fields']:                
                
                # Build JSON body for the REST API call
                json_body = [
                    {
                        'measurement': measurement,
                        'tags': {
                            'host': self.hostname
                        },
                        'fields': field
                    }
                ] 

                if data['tag']:
                    json_body[0]['tags'][data['tag']] = field[data['tag']]
                
                client = InfluxDBClient(db_host, db_port, db_user, db_password, db_name)
                client.write_points(json_body)

def quotes_in_str(value):
    """ Add quotes around value if it's a string """
    if type(value) == str:
        return("\"%s\"" % value)
    else:
        return(value)

def int_if_possible(value):
    """ Convert to int if possible """
    try: return int(value)
    except: return value

def float_if_possible(value):
    """ Convert to float if possible """
    try: return float(value)
    except: return value

def clitable_to_dict(cli_table):
    """Converts TextFSM cli_table object to list of dictionaries """

    objs = []
    for row in cli_table:
        temp_dict = {}
        for index, element in enumerate(row):
            temp_dict[cli_table.header[index].lower()] = element
        objs.append(temp_dict)

    return objs

def worker(input_queue, output_queue):
    """ Worker thread """

    # Fetch a task from the queue
    task = input_queue.get()

    # Exit if guardian is found
    if task == 'STOP':
        return

    poller = SSH_Poller(task)
    if poller.connect():
        if task['mode'] == 'json':
            poller.send_commands()
            poller.output_json()
        elif task['mode'] == 'line':
            poller.send_commands()
            poller.output_line()
        elif task['mode'] == 'influx':
            logging.info('InfluxDB mode selected, polling every %s seconds' % task['interval'])
            while True:
                poller.send_commands()
                poller.output_influxdb()
                sleep(task['interval'])
    else:
        return

def main(args, loglevel):
    
    # Logging format
    logging.basicConfig(format="%(asctime)s %(levelname)s: %(message)s", level=loglevel)

    # Set variables from CLI args
    hostname = args.hostname
    username = args.username
    password = args.password
    mode = args.mode                # Valid choices: json, line, influx
    device_type = args.device_type  # Valid choices documented in netmiko
    parser_mode = args.parse        # Valid choices : fsm, csv
    commands = args.commands
    num_threads = args.threads
    interval = args.interval

    # Ask for credentials if not passed from CLI args
    if not username:
        username = raw_input('Enter username:')
    if not password:
        password = getpass('Enter password:')

    input_queue = Queue()
    output_queue = Queue()

    # Add our task to the queue
    task = {
        'hostname': hostname,
        'username': username,
        'password': password,
        'mode': mode,
        'device_type': device_type,
        'parser_mode': parser_mode,
        'commands': commands,
        'interval': interval    
    }
    input_queue.put(task)
    logging.debug('Added task to the queue: %s' % task)

    # Add guardian to the queue
    for i in range(1, num_threads + 1):
        input_queue.put('STOP')

    # Start processes
    for i in range(1, num_threads + 1):
        p = Process(target=worker, args=(input_queue, output_queue))
        p.start()
        logging.debug('Process %s PID %s started' % (i, p.pid))
    
if __name__ == '__main__':    
    
    # Setup parser    
    parser = argparse.ArgumentParser( 
                        description = "Screen scrapping poller for InfluxDB/telegraf",
                        epilog = "As an alternative to the commandline, params can be placed in a file, one per line, and specified on the commandline like '%(prog)s @params.conf'.",
                        fromfile_prefix_chars = '@' )
    parser.add_argument(
                        "-H",
                        "--hostname",
                        help = "hostname",
                        required = True)
    parser.add_argument(
                        "-c",
                        "--commands",
                        nargs = "+",
                        help = "Command:Tags",
                        required = True)
    parser.add_argument(
                        "-d",
                        "--device_type",
                        help = "Device type (FSM mode only)",
                        default = 'linux')
    parser.add_argument(
                        "-m",
                        "--mode",
                        help = "Output mode (default = json)",
                        choices = ['json', 'line', 'influx'],
                        default = 'json')
    parser.add_argument(
                        "-i",
                        "--interval",
                        help = "Polling interval (sec)",
                        default = 10
                        )
    parser.add_argument(
                        "-u",
                        "--username",
                        help = "SSH username")
    parser.add_argument(
                        "-p",
                        "--password",
                        help = "SSH password")
    parser.add_argument(
                        "-P",
                        "--parse",
                        help = "Parser mode (default = fsm)",
                        choices = ['fsm', 'csv'],
                        default = 'fsm'
                        )
    parser.add_argument(
                        "-t",
                        "--threads",
                        help = "# of threads",
                        default = 1)
    parser.add_argument(
                        "-y",
                        "--yaml",
                        help = "YAML task list",
                        )
    parser.add_argument(
                        "-v",
                        "--verbose",
                        help = "increase output verbosity",
                        action = "store_true")
    args = parser.parse_args()
  
    # Setup logging
    if args.verbose:
        loglevel = logging.DEBUG
    else:
        loglevel = logging.ERROR

    main(args, loglevel)
