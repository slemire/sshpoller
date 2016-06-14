# sshpoller
[![Build Status](https://travis-ci.org/slemire/sshpoller.svg?branch=master)](https://travis-ci.org/slemire/sshpoller)
[![Coverage Status](https://coveralls.io/repos/github/slemire/sshpoller/badge.svg?branch=master)](https://coveralls.io/github/slemire/sshpoller?branch=master)

## Description
This is a Python SSH screen scrapper that parses the output of commands sent to a network device and returns the information in various output formats. It uses netmiko/paramiko to do the SSH connection and TextFSM to parse the command outputs. It can be used to poll a device at a specified interval and save some metrics obtained in an InfluxDB database. A use case for this would be polling a device for metrics that don't have any OID's associated with them, as is often the case with low-level debug commands.

## Requirements
 * textfsm
 * netmiko
 * influxdbclient

## Input
 * Command line args
 * YAML file

## Parsing mode
 * TextFSM (default)
 * CSV (Can be used for some commands on F5 ADC's that can output to csv)
 
## Output supported
 * JSON
 * InfluxDB

##Usage
```
./sshpoller.py -h
usage: sshpoller.py [-h] [-H HOSTNAME] [-c COMMANDS [COMMANDS ...]]
                    [-C PRECOMMANDS [PRECOMMANDS ...]] [-d DEVICE_TYPE]
                    [-m {json,influx}] [-i INTERVAL] [-u USERNAME]
                    [-p PASSWORD] [-P {fsm,csv}] [-t THREADS] [-y YAML] [-v]

Screen scrapping poller with JSON & InfluxDB output

optional arguments:
  -h, --help            show this help message and exit
  -H HOSTNAME, --hostname HOSTNAME
                        hostname
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
  -P {fsm,csv}, --parse {fsm,csv}
                        Text input format (default = fsm)
  -t THREADS, --threads THREADS
                        # of threads
  -y YAML, --yaml YAML  YAML input file
  -v, --verbose         increase output verbosity
```

###Notes:

* Thread count is set to the number of YAML tasks for the moment
* The device_type has to match netmiko supported device types (see netmiko's doc)

##Examples:

1.. Get the interface statistics from a Juniper SRX firewall and output to line protocol

```
./sshpoller.py -H <host> -m line -u <username> -p <password> -c "show interfaces extensive" -d juniper
show_interfaces_extensive,host="172.23.10.2" input_bytes=1181166996.0,output_bytes=93588462.0,intf_name="ge-0/0/0"
show_interfaces_extensive,host="172.23.10.2" input_bytes=1299006466.0,output_bytes=9905560226.0,intf_name="ge-0/0/1"
show_interfaces_extensive,host="172.23.10.2" input_bytes=2308182648.0,output_bytes=5535522227.0,intf_name="ge-0/0/2"
show_interfaces_extensive,host="172.23.10.2" input_bytes=0.0,output_bytes=20442748.0,intf_name="ge-0/0/3"
show_interfaces_extensive,host="172.23.10.2" input_bytes=0.0,output_bytes=20423509.0,intf_name="ge-0/0/4"
```

2.. Same thing as above but write the metrics into InfluxDB database directly, by default it will send the command and write the information into InfluxDB every 10 seconds. The InfluxDB database name and credentials is currently hardcoded in the script.

```
./sshpoller.py -H 172.23.10.2 -m influx -u <username> -p <password> -c "show interfaces extensive" -d juniper
```

3.. Same as above but we will also add a tag when writing our data into InfluxDB. In the command argument, we specify which Value in the TextFSM template we want to use as the tag. By default, this script uses the hostname as the only tag, adding another tag to index such as the interface name is useful.

``` 
./sshpoller.py -H 172.23.10.2 -m influx -u <username> -p <password> -c "show interfaces extensive:intf_name" -d juniper
```

4.. Parse CSV command output from a device and write to InfluxDB. Some commands on F5 load-balancers support csv output so we don't need to craft a TextFSM template for it.

```
/sshpoller.py -H 172.23.10.30 -m influx -u <username> -p <password> -c "tmctl -c -d blade tmm/tcp4" -d f5_ltm -P csv
```
