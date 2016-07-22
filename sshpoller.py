#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Import standard python modules
import argparse
from getpass import getpass
import csv
import json
import logging
import sys
from time import sleep, time
import tempfile
import yaml
from multiprocessing import Process, Queue

# TextFSM module : https://github.com/google/textfsm
import clitable

# Netmiko module : https://github.com/ktbyers/netmiko
from netmiko import ConnectHandler, ssh_exception

# InfluxDB module : https://github.com/influxdata/influxdb-python
from influxdb import InfluxDBClient

CSV_DELIMITER = ','

# TESTFSM config settings
index_file = 'index'
template_dir = 'templates'




class SSH_Poller:
    """ SSH Poller class """

    # InfluxDB settings (you should change these)
    db_host = 'localhost'
    db_port = 8086
    db_name = 'db_name'
    db_user = 'root'
    db_password = 'root'

    hostname = ''
    port = 22
    username = ''
    password = ''
    command_list = []
    precommand_list = []
    data_list = []
    prompt = ''
    parser_mode = ''
    interval = ''
    sock = ConnectHandler

    def __init__(self, task):
        self.data_list = []
        self.hostname = task['hostname']
        self.port = task['port']
        self.username = task['username']
        self.password = task['password']
        self.device_type = task['device_type']
        self.parser_mode = task['parser_mode']
        self.precommand_list = task['precommands']

        for command in task['commands']:
            # Command doesn't contain tags attribute
            if len(command.split(':')) == 1:
                self.command_list.append({'command': command.split(':')[0], 'tag': ''})
            # Command contains tags attribute
            elif len(command.split(':')) == 2:
                self.command_list.append({'command': command.split(':')[0], 'tag': command.split(':')[1]})

    def connect(self):
        """ Connects SSH session """

        try:
            self.sock = ConnectHandler(
                device_type=self.device_type,
                ip=self.hostname,
                port=self.port,
                username=self.username,
                password=self.password)
            logging.debug('Connection to %s successful!' % self.hostname)
            self.prompt = self.sock.find_prompt()

            if self.prompt:
                logging.debug('Prompt found: %s' % self.prompt)

                # Send commands after login that won't be parsed
                if self.precommand_list:
                    for precommand in self.precommand_list:
                        self.sock.send_command(precommand)
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
        """ Parses command output through TextFSM """

        result = ''.join(result)
        cli_table = clitable.CliTable(index_file, template_dir)
        attrs = {'Command': command['command'], 'Platform': self.device_type}

        try:
            cli_table.ParseCmd(result, attrs)

            # Timestamp precision is set to 'seconds'
            timestamp = int(time())

            for field in clitable_to_dict(cli_table):
                data = {}
                data['tag'] = {'host': self.hostname, 'command': command['tag']}
                data['command'] = command['command']
                data['fields'] = dict((k, float_if_possible(v)) for (k, v) in field.items())
                if command['tag']:
                    data['tag'][command['tag']] = data['fields'][command['tag']]
                data['timestamp'] = timestamp
                self.data_list.append(data)

            return True

        except clitable.CliTableError as e:
            logging.error('FSM parsing error: %s' % str(e))
            return False

    def parse_csv(self, result, command):
        """ Parse command output as csv """

        # CVS module needs to read from a file, let's create one
        csvfile = tempfile.TemporaryFile()

        result_list = result.split('\n')

        # Add lines until we find first empty line
        for line in result_list:
            if line != "":
                csvfile.write("%s\n" % line)
            else:
                break

        csvfile.seek(0)

        reader = csv.DictReader(csvfile)

        # Timestamp precision is set to 'seconds'
        timestamp = int(time())

        for idx, row in enumerate(reader):
            data = {}
            data['tag'] = {'host': self.hostname, 'instance': idx}
            data['command'] = command['command']
            row = dict((k, float_if_possible(v)) for (k, v) in row.items())
            data['fields'] = row
            data['timestamp'] = timestamp
            self.data_list.append(data)

        return True

    def send_commands(self):
        """ Send all commands in task
            Stores all parsed output in self.data_list
        """

        for command in self.command_list:
            logging.debug('Sending command: %s' % command['command'])
            result = self.sock.send_command(command['command'])
            logging.debug('Output of command: %s' % command['command'])
            logging.debug(result)

            if self.parser_mode == 'fsm':
                self.parse_fsm(result, command)
            elif self.parser_mode == 'csv':
                self.parse_csv(result, command)

    def output_json(self):
        """ Return results in JSON format """

        print(json.dumps(self.data_list, indent=2))

    def output_influxdb(self):
        """ Writes data to the InfluxDB """

        client = InfluxDBClient(self.db_host, self.db_port, self.db_user, self.db_password, self.db_name)

        # TODO: Refactor to batch to optimize writes to the DB
        for data in self.data_list:

            measurement = data['command']

            # Build JSON body for the REST API call
            json_body = [
                {
                    'measurement': measurement,
                    'tags': data['tag'],
                    'fields': data['fields'],
                    'time': data['timestamp']
                }
            ]

            client.write_points(json_body, time_precision='s')

def quotes_in_str(value):
    """ Add quotes around value if it's a string """
    if type(value) == str:
        return ("\"%s\"" % value)
    else:
        return (value)


def int_if_possible(value):
    """ Convert to int if possible """
    try:
        return int(value)
    except:
        return value


def float_if_possible(value):
    """ Convert to float if possible """
    try:
        return float(value)
    except:
        return value


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
            logging.info('JSON mode selected')
            poller.send_commands()
            poller.output_json()
        elif task['mode'] == 'influx':
            logging.info('InfluxDB mode selected, polling every %s seconds' % task['interval'])
            if task['interval'] == 0:
                # Interval not set, we'll just poll once
                poller.send_commands()
                poller.output_influxdb()
            else:
                # Interval is set, start polling loop
                while True:
                    poller.send_commands()
                    poller.output_influxdb()
                    sleep(float(task['interval']))
    else:
        return


def main(args, loglevel):
    # Logging format
    logging.basicConfig(format="%(asctime)s %(levelname)s: %(message)s", level=loglevel)

    # Set variables from CLI args
    hostname = args.hostname
    port = args.port
    username = args.username
    password = args.password
    mode = args.mode                # Valid choices: json, influx
    device_type = args.device_type  # See netmiko's doc for valid types
    parser_mode = args.parse        # Valid choices : fsm, csv
    commands = args.commands
    precommands = args.precommands
    num_threads = args.threads
    interval = args.interval
    yaml_filename = args.yaml
    yaml_task_list = []

    # Ask for credentials if not passed from CLI args
    if not username:
        username = raw_input('Enter username:')
    if not password:
        password = getpass('Enter password:')

    # YAML file parsing
    if yaml_filename:
        f = open(yaml_filename)
        buf = f.read()
        f.close()
        yaml_task_list = yaml.load(buf)
        num_threads = len(yaml_task_list)

    input_queue = Queue()
    output_queue = Queue()

    if yaml_filename:
        # Add our task to the queue
        for yaml_task in yaml_task_list:
            task = {
                'hostname': yaml_task['device_name'],
                'username': username,
                'password': password,
                'mode': 'influx',
                'device_type': yaml_task['device_type'],
                'parser_mode': yaml_task['parse_mode'],
                'commands': yaml_task['commands'],
                'precommands': yaml_task['post_login_commands'],
                'interval': interval
            }
            if yaml_task['port']:
                task['port'] = yaml_task['port']
            else:
                task['port'] = 22
            input_queue.put(task)
            logging.debug('Added task to the queue: %s' % task)

    else:
        # Add our task to the queue
        task = {
            'hostname': hostname,
            'port': port,
            'username': username,
            'password': password,
            'mode': mode,
            'device_type': device_type,
            'parser_mode': parser_mode,
            'commands': commands,
            'precommands': precommands,
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
        description="Screen scrapping poller with JSON & InfluxDB output",
        epilog="As an alternative to the commandline, params can be placed in a file, one per line, and specified on the commandline like '%(prog)s @params.conf'.",
        fromfile_prefix_chars='@'
    )
    # Hostname and YAML are mutually exclusive
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "-H",
        "--hostname",
        help="hostname",
    )
    group.add_argument(
        "-y",
        "--yaml",
        help="YAML input file",
    )
    parser.add_argument(
        "-c",
        "--commands",
        nargs="+",
        help="Command:Tags",
    )
    parser.add_argument(
        "-C",
        "--precommands",
        nargs="+",
        help="Commands sent after connection (will not be parsed)",
    )
    parser.add_argument(
        "-d",
        "--device_type",
        help="Device type (FSM mode only)",
        default='linux'
    )
    parser.add_argument(
        "-m",
        "--mode",
        help="Output mode (default = json)",
        choices=['json', 'influx'],
        default='json'
    )
    parser.add_argument(
        "-i",
        "--interval",
        help="Polling interval (sec)",
        default=0
    )
    parser.add_argument(
        "-u",
        "--username",
        help="SSH username"
    )
    parser.add_argument(
        "-p",
        "--password",
        help="SSH password"
    )
    parser.add_argument(
        "-o",
        "--port",
        help="SSH port",
        default=22
    )
    parser.add_argument(
        "-P",
        "--parse",
        help="Text input format (default = fsm)",
        choices=['fsm', 'csv'],
        default='fsm'
    )
    parser.add_argument(
        "-t",
        "--threads",
        help="# of threads",
        default=1
    )
    parser.add_argument(
        "-v",
        "--verbose",
        help="increase output verbosity",
        action="store_true"
    )
    args = parser.parse_args()

    # Setup logging
    if args.verbose:
        loglevel = logging.DEBUG
    else:
        loglevel = logging.ERROR

    main(args, loglevel)
