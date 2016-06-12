 #!/usr/bin/env python
# -*- coding: utf-8 -*-

# Import standard python modules
from multiprocessing import Queue
import json
import os
import re
import unittest

# Dependencies
import clitable
import textfsm

# Module we're testing
import sshpoller

# TextFSM config settings
index_file = 'index'
template_dir = 'templates'

generic_task = {
    'hostname': '127.0.0.1',
    'username': 'username',
    'password': 'password',
    'device_type': 'generic',
    'parser_mode': 'fsm',
    'commands': '',
    'precommands': '',
}

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
        """ Test float_if_possible
        """
        self.assertIs(type(sshpoller.float_if_possible('100')), float)
        self.assertIs(type(sshpoller.float_if_possible('100.10')), float)
        self.assertIs(type(sshpoller.float_if_possible(100)), float)
        self.assertIs(type(sshpoller.float_if_possible(100.10)), float)
        self.assertIs(type(sshpoller.float_if_possible('abc')), str)

    def test_clitable_to_dict(self):
        """ Test clitable_to_dict()
            Fixtures should reside in $template_dir
            Fixtures files are named "test.*\.txt"
            Expected output files with JSON data are named "test.*_json\.txt"
            So we need to add two files for each device/command we want to test
        """
        for file in os.listdir(template_dir):
            if file.startswith('test') and file.endswith('.txt') and not '_json' in file:
                f_rawtext = open(os.path.join(template_dir, file), 'r')
                f_expected_results = open(re.sub(r'.txt$', '_json.txt', os.path.join(template_dir, file)), 'r')
                rawtxt = f_rawtext.read()
                expected_results = json.load(f_expected_results)
                f_rawtext.close()
                f_expected_results.close()
                cli_table = clitable.CliTable(index_file, template_dir)
                platform = re.match(r'^test_([a-zA-Z0-9]+)_', file).group(1)
                command = re.sub(r'_', ' ', re.match(r'^test_[a-zA-Z0-9]+_(.*)\.txt', file).group(1))
                attrs = {'Command': command, 'Platform': platform}
                cli_table.ParseCmd(rawtxt, attrs)
                self.assertEqual(sshpoller.clitable_to_dict(cli_table), expected_results)

    def test_worker_stop_queue(self):
        """ Test worker()
            Check that the worker won't try to process a task if there's a guardian
        """
        task = 'STOP'
        input_queue = Queue()
        output_queue = Queue()
        input_queue.put(task)
        self.assertFalse(sshpoller.worker(input_queue, output_queue))

if __name__ == '__main__':
    unittest.main()