import unittest

import sshpoller

class Test_SSH_Poller(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_output_json(self):
        task = {
            'hostname': 'test_hostname',
            'username': 'test_username',
            'password': 'test_password',
            'device_type': 'cisco_nxos',
            'parser_mode': 'fsm',
            'commands': ['show interfaces']
        }

        a = sshpoller.SSH_Poller(task)
        self.assertEqual(a.output_json(),123)

if __name__ == '__main__':
    unittest.main()