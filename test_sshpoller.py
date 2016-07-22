#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Import standard python modules
from multiprocessing import Process, Queue
import json
import os
import random
import re
import string
from time import sleep
import unittest

# Dependencies
import clitable
import MockSSH

# Module we're testing
import sshpoller

# Mock libraries for SSH
from test_sshpoller_mock import mock_cisco, mock_f5

# InfluxDB module : https://github.com/influxdata/influxdb-python
from influxdb import InfluxDBClient

# TextFSM config settings
index_file = 'index'
template_dir = 'templates'

class SSH_PollerTest(unittest.TestCase):

    def test_quotes_in_str(self):
        """ Test quotes_in_str()
        """
        self.assertEqual(sshpoller.quotes_in_str(r'hello'), r'"hello"')
        self.assertEqual(sshpoller.quotes_in_str(r'12345'), r'"12345"')
        self.assertEqual(sshpoller.quotes_in_str(12345), 12345)

    def test_int_if_possible(self):
        """ Test int_if_possible()
        """
        self.assertIs(type(sshpoller.int_if_possible('100')), int)
        self.assertIs(type(sshpoller.int_if_possible(100)), int)
        self.assertIs(type(sshpoller.int_if_possible('abc')), str)

    def test_float_if_possible(self):
        """ Test float_if_possible()
        """
        self.assertIs(type(sshpoller.float_if_possible('100')), float)
        self.assertIs(type(sshpoller.float_if_possible('100.10')), float)
        self.assertIs(type(sshpoller.float_if_possible(100)), float)
        self.assertIs(type(sshpoller.float_if_possible(100.10)), float)
        self.assertIs(type(sshpoller.float_if_possible('abc')), str)

    def test_worker_stop_queue(self):
        """ Test worker()
            Check that the worker won't try to process a task if there's a guardian
        """
        task = 'STOP'
        input_queue = Queue()
        output_queue = Queue()
        input_queue.put(task)
        self.assertFalse(sshpoller.worker(input_queue, output_queue))

    def test_parse_fsm(self):
        """ Test parse_fsm() function
        """

        # Cisco 'show version'
        task = {
            'hostname': 'localhost',
            'username': 'test',
            'password': 'test',
            'port': 9999,
            'device_type': 'cisco_nxos',
            'parser_mode': 'fsm',
            'precommands': '',
            'commands': ['show version'],
        }
        poller = sshpoller.SSH_Poller(task)
        mock_output = open(os.path.join('mockssh', 'cisco_show_version.txt'), 'r').read()
        expected_results = json.loads(open(os.path.join('mockssh', 'cisco_show_version.json'), 'r').read())
        poller.parse_fsm(mock_output, {'command': 'show version', 'tag': ''})
        
        # Remove timestamp since it'll never match
        for item in poller.data_list:
            item.pop('timestamp', None)
        for item in expected_results:
            item.pop('timestamp', None)    

        self.assertEqual(json.dumps(poller.data_list), json.dumps(expected_results))

        # Cisco 'show interface'
        task = {
            'hostname': 'localhost',
            'username': 'test',
            'password': 'test',
            'port': 9999,
            'device_type': 'cisco_nxos',
            'parser_mode': 'fsm',
            'precommands': '',
            'commands': ['show interface'],
        }
        poller = sshpoller.SSH_Poller(task)
        mock_output = open(os.path.join('mockssh', 'cisco_show_interface.txt'), 'r').read()
        expected_results = json.loads(open(os.path.join('mockssh', 'cisco_show_interface.json'), 'r').read())
        poller.parse_fsm(mock_output, {'command': 'show interface', 'tag': ''})
        
        # Remove timestamp since it'll never match
        for item in poller.data_list:
            item.pop('timestamp', None)
        for item in expected_results:
            item.pop('timestamp', None)   

        self.assertEqual(json.dumps(poller.data_list), json.dumps(expected_results))

        # Cisco 'show platform software qd info counters'
        task = {
            'hostname': 'localhost',
            'username': 'test',
            'password': 'test',
            'port': 9999,
            'device_type': 'cisco_nxos',
            'parser_mode': 'fsm',
            'precommands': '',
            'commands': ['show platform software qd info counters'],
        }
        poller = sshpoller.SSH_Poller(task)
        mock_output = open(os.path.join('mockssh', 'cisco_show_platform_software_qd_info_counters.txt'), 'r').read()
        expected_results = json.loads(open(os.path.join('mockssh', 'cisco_show_platform_software_qd_info_counters.json'), 'r').read())
        poller.parse_fsm(mock_output, {'command': 'show platform software qd info counters', 'tag': ''})
        
        # Remove timestamp since it'll never match
        for item in poller.data_list:
            item.pop('timestamp', None)
        for item in expected_results:
            item.pop('timestamp', None) 

        self.assertEqual(json.dumps(poller.data_list), json.dumps(expected_results))

        # F5 'show sys tmm-info'
        task = {
            'hostname': 'localhost',
            'username': 'test',
            'password': 'test',
            'port': 9999,
            'device_type': 'f5_ltm',
            'parser_mode': 'fsm',
            'precommands': '',
            'commands': ['show sys tmm-info'],
        }
        poller = sshpoller.SSH_Poller(task)

        # Fetch data from fixtures
        mock_output = open(os.path.join('mockssh', 'f5_show_tmm_info.txt'), 'r').read()
        expected_results = json.loads(open(os.path.join('mockssh', 'f5_show_tmm_info.json'), 'r').read())

        # Parse data through TextFSM
        poller.parse_fsm(mock_output, {'command': 'show sys tmm-info', 'tag': ''})
        
        # Remove timestamp since it'll never match
        for item in poller.data_list:
            item.pop('timestamp', None)
        for item in expected_results:
            item.pop('timestamp', None) 

        self.assertEqual(json.dumps(poller.data_list), json.dumps(expected_results))

    def test_parse_csv(self):
        """ Test parse_csv() function
        """
        # F5 'show sys tmm-info'
        task = {
            'hostname': 'localhost',
            'username': 'test',
            'password': 'test',
            'port': 9999,
            'device_type': 'f5_ltm',
            'parser_mode': 'csv',
            'precommands': '',
            'commands': ['tmctl -c pva_stat'],
        }
        poller = sshpoller.SSH_Poller(task)

        # Fetch data from fixtures
        mock_output = open(os.path.join('mockssh', 'f5_tmctl_csv.txt'), 'r').read()
        expected_results = json.loads(open(os.path.join('mockssh', 'f5_tmctl_csv.json'), 'r').read())

        # Parse CSV data
        poller.parse_csv(mock_output, {'command': 'tmctl -c pva_stat', 'tag': ''})
        
        # Remove timestamp since it'll never match
        for item in poller.data_list:
            item.pop('timestamp', None)
        for item in expected_results:
            item.pop('timestamp', None) 

        self.assertEqual(json.dumps(poller.data_list), json.dumps(expected_results))

    def test_output_influxdb(self):
        """ Test output_influxdb()
        """
        task = {
            'hostname': 'localhost',
            'username': 'test',
            'password': 'test',
            'port': 9999,
            'device_type': 'cisco_nxos',
            'parser_mode': 'fsm',
            'precommands': '',
            'commands': ['show interface:intf_name'],
        }
        poller = sshpoller.SSH_Poller(task)

        # Generate a random name for our database
        poller.db_name = 'testsshpoller_%s' % ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(5))
        
        # Create client and connect to the database
        client = InfluxDBClient(host='127.0.0.1', port=poller.db_port, username=poller.db_user, password=poller.db_password)
        client.create_database(poller.db_name)

        # Get our fixture data
        poller.data_list = json.loads(open(os.path.join('mockssh', 'cisco_show_interface_tag.json'), 'r').read())

        # Write data to InfluxDB
        poller.output_influxdb()        

        # Query database
        query_results = client.query('select * from "show interface"', database=poller.db_name)

        # Fetch expected results
        expected_results = json.loads(open(os.path.join('mockssh', 'cisco_show_interface_influx.json'), 'r').read())

        self.assertEqual(query_results.raw, expected_results)

        # Clean up
        client.drop_database(poller.db_name)

if __name__ == '__main__':
    unittest.main()
