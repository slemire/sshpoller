# sshpoller
[![Build Status](https://travis-ci.org/slemire/sshpoller.svg?branch=master)](https://travis-ci.org/slemire/sshpoller)
[![Coverage Status](https://coveralls.io/repos/github/slemire/sshpoller/badge.svg?branch=master)](https://coveralls.io/github/slemire/sshpoller?branch=master)

## Description
This is a Python SSH screen scrapper that parses the output of commands sent to a network device and returns the information in various output formats. It uses netmiko/paramiko to do the SSH connection and TextFSM to parse the command outputs. It can be used to poll a device at a specified interval and save some metrics to an InfluxDB database. A typical use case for this would be polling a device for metrics that don't have any SNMP OID's associated with them, as is often the case with low-level debug commands.

## Requirements
 * textfsm
 * netmiko
 * influxdbclient
 * MockSSH (to run tests)

### Input
 * Command line args
 * YAML file (to process multiple commands per device)

### Parsing mode
 * TextFSM (default)
 * CSV (Can be used for some commands on F5 ADC's that can output to csv)

### Output supported
 * JSON (used by default, to validate the parser's results)
 * InfluxDB

##Usage

    ./sshpoller.py -h
    usage: sshpoller.py [-h] (-H HOSTNAME | -y YAML) [-c COMMANDS [COMMANDS ...]]
                        [-C PRECOMMANDS [PRECOMMANDS ...]] [-d DEVICE_TYPE]
                        [-m {json,influx}] [-i INTERVAL] [-u USERNAME]
                        [-p PASSWORD] [-o PORT] [-P {fsm,csv}] [-t THREADS] [-v]

    Screen scrapping poller with InfluxDB output

    optional arguments:
      -h, --help            show this help message and exit
      -H HOSTNAME, --hostname HOSTNAME
                            hostname
      -y YAML, --yaml YAML  YAML input file
      -c COMMANDS [COMMANDS ...], --commands COMMANDS [COMMANDS ...]
                            Command:Tags
      -C PRECOMMANDS [PRECOMMANDS ...], --precommands PRECOMMANDS [PRECOMMANDS ...]
                            Commands sent after connection (will not be parsed)
      -d DEVICE_TYPE, --device_type DEVICE_TYPE
                            Device type (FSM mode only)
      -m {json,influx}, --mode {json,influx}
                            Output mode (default = json)
      -i INTERVAL, --interval INTERVAL
                            Polling interval (sec)
      -u USERNAME, --username USERNAME
                            SSH username
      -p PASSWORD, --password PASSWORD
                            SSH password
      -o PORT, --port PORT  SSH port
      -P {fsm,csv}, --parse {fsm,csv}
                            Text input format (default = fsm)
      -t THREADS, --threads THREADS
                            # of threads
      -v, --verbose         increase output verbosity

###Notes:

* The thread count parameters is not currently implemented. The # of threads will be the size of the YAML task list.
* The device_type has to match netmiko supported device types (i.e. see netmiko's doc)
* The InfluxDB parameters are hardcoded in the SSH_Poller class definition at the moment

##Examples:

1. Get the interface statistics off a Cisco NX-OS switch every 2 minutes, then put the information in the InfluxDB. The first half of the command flag parameter specified the command and the second part defined the tag that'll be added to the value written to InfluxDB. If you're writing several values to the database (getting some metrics off multiple interfaces for example), it is important to specify in the tag field the TextFSM Value parameter. In this example, intf_name is the Value parameter in the TextFSM template.

    ```./sshpoller.py -H <hostname/ip> -m influx -u <username> -p <password> -i 120 -c "show interfaces extensive:intf_name" -d cisco_nxos```

2. Parse CSV command output from an F5 load-balancer every 5 minutes and and write the data in InfluxDB. Some commands on F5 load-balancers support csv output so we don't need to craft a TextFSM template for it. In this example we'll pass a precommand argument to start a bash shell before we issue the command to be parsed.

    ```./sshpoller.py -H <hostname/ip> -m influx -u <username> -p <password> -c "tmctl -c -d blade tmm/tcp4" -C "bash" -d f5_ltm -P csv```

3. To send multiple commands to the same device, you can create a YAML and put a series of commands.


    ```./sshpoller.py -u <username> -p <password> -y <YAML_file>```

    YAML file content:

        ---
        -
          device_name: localhost
          port: 9999
          device_type: cisco_nxos
          parse_mode: fsm
          post_login_commands:
          commands:
            - show version
            - show interface:intf_name