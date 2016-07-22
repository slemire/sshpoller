#!/usr/bin/env python
# -*- coding: utf-8 -*-

import MockSSH

fixture = {}
fixture['show version'] = open('mockssh/cisco_show_version.txt').read()
fixture['show interface'] = open('mockssh/cisco_show_interface.txt').read()
fixture['show platform software qd info counters'] = open('mockssh/cisco_show_platform_software_qd_info_counters.txt').read()
fixture['show sys tmm-info'] = open('mockssh/f5_show_tmm_info.txt').read()
fixture['tmctl -c pva_stat'] = open('mockssh/f5_tmctl_csv.txt').read()

def cmd_parser(instance):
    cmd = " ".join(instance.args)
    if cmd in fixture:
        instance.writeln(fixture[cmd])
    else:
        instance.writeln('Invalid command')

def f5_prompt(instance):
    instance.protocol.prompt = '[user@F5-TEST:/S1-green-P:Active:In Sync] ~ # '

cmd_cisco_show = MockSSH.ArgumentValidatingCommand(
     'show',
     [cmd_parser],
     [cmd_parser],
     *[])

cmd_f5_show = MockSSH.ArgumentValidatingCommand(
     'show',
     [cmd_parser],
     [cmd_parser],
     *[])

cmd_f5_bash = MockSSH.ArgumentValidatingCommand(
     'bash',
     [f5_prompt],
     [f5_prompt],
     *[])

cmd_f5_tmctl = MockSSH.ArgumentValidatingCommand(
     'tmctl',
     [cmd_parser],
     [cmd_parser],
     *[])

def mock_cisco():
    commands = [cmd_cisco_show]
    users = {'test': 'test'}
    MockSSH.runServer(commands,
                      prompt="hostname>",
                      interface='127.0.0.1',
                      port=9999,
                      **users)

def mock_f5():
    commands = [cmd_f5_bash, cmd_f5_tmctl, cmd_f5_show]
    users = {'test': 'test'}
    MockSSH.runServer(commands,
                      prompt="user@(F5-TEST)(cfg-sync In Sync)(/S1-green-P:Active)(/Common)(tmos)# ",
                      interface='127.0.0.1',
                      port=9999,
                      **users)                                                   