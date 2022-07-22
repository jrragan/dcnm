## introduction
This script connects to a dcnm instance and allows the user to perform one or more of three operations on one or more switches. These operations are:
- correct interface descriptions
- turn off cdp
- enable orphan port suspend

## requirements
Tested with Python 3.6.13
Requires the requests, pyyaml, pandas and colorama packages

The script serializes dictionaries in anticipation of a restore operation. So, write access to the local hard drive is required.

## install
Download the six python files and the uplinks.yaml file to a directory. 

## command line options:

```
PS C:\Users\rragan\Documents\PyProjects\dcnm\dcnm\interfaces> python .\change_interfaces.py --help
usage: change_interfaces.py [-h] -a IP_or_DNS_NAME [-u USERNAME] [-n SERIALS [SERIALS ...]] [-f FILE] [-e] [-x EXCEL_FILE] [-g] [-s LOGLEVEL] [-l LOGLEVEL] [-c] [-m] [-d] [-o] [-p FILE] [-i FILE]
                            [-j] [-b] [-t SECONDS] [-v] [--dryrun | --deploy]

automation of interface configuration changes via dcnm at least one of -c -d or -o must be included or the program won't do anything

optional arguments:
  -h, --help            show this help message and exit
  -a IP_or_DNS_NAME, --dcnm IP_or_DNS_NAME
                        dcnm hostname or ip address
  -u USERNAME, --username USERNAME
                        DCNM username
  -n SERIALS [SERIALS ...], --serials SERIALS [SERIALS ...]
                        enter one or more switch serial numbers
  -f FILE, --input-file FILE
                        read serial numbers from a file
  -e, --all             perform actions for all switches
  -x EXCEL_FILE, --excel EXCEL_FILE
                        descriptions xlsx file
  -g, --debug           Shortcut for setting screen and logfile levels to DEBUG
  -s LOGLEVEL, --screenloglevel LOGLEVEL
                        Default is INFO.
  -l LOGLEVEL, --loglevel LOGLEVEL
                        Default is NONE.
  -c, --cdp             add no cdp enable to interfaces
  -m, --mgmt            include mgmt interfaces in cdp action
  -d, --description     correct interfaces descriptions if this was part of the original change, this parameter must be included with the fallback option
  -o, --orphan          add vpc orphan port configuration to interfaces
  -p FILE, --pickle FILE
                        filename for pickle file used to save original switch configuration policies if included for deploy, it must also be included for backout
  -i FILE, --icpickle FILE
                        filename for pickle file used to save original interface configuration policies if included for deploy, it must also be included for backout
  -j, --switch_deploy   By default interface deploy is used (along with policy deploy when needed. In certain situations this can lead to the need for a second deploy especially when there is a
                        switch level policy applying an interface level config. This option enables a switch level deploy method.
  -b, --backout         Rerun app with this option to fall back to original configuration. If running backout, you should run program with all options included in the original deploy.
  -t SECONDS, --timeout SECONDS
                        timeout in seconds of the deploy operations default is 300 seconds
  -v, --verbose         verbose mode
  --dryrun              dryrun mode, do not deploy changes (default)
  --deploy              deploy mode, deploys changes to dcnm
  ```
  
## uplinks

Potential uplinks are excluded. Uplinks are defined by the file `uplinks.yaml`. The format of the file is

```
93240YC-FX2: !!python/tuple
- 1/49
- 1/60
9336C-FX2: !!python/tuple
- 1/29
- 1/36
```
This file can be modified to change, add or delete uplinks.

## example run for the orphan port option
```
C:\Users\rragan\Anaconda3\envs\dcnm\python.exe C:/Users/rragan/Documents/PyProjects/dcnm/dcnm/interfaces/change_interfaces.py -a 10.0.17.99 -n FDO24261WAT FDO242702QK -o -v --deploy -j
20
2022-06-13 13:45:11,837 | 85928 | MainThread | (change_interfaces.py:398) | <module> | CRITICAL | message: Started
============================================================
args:
============================================================
Namespace(all=False, backout=False, cdp=False, dcnm='10.0.17.99', debug=False, description=False, dryrun=False, excel=None, icpickle='interfaces_existing_conf.pickle', input_file='', loglevel=None, mgmt=False, orphan=True, pickle='swi
tches_configuration_policies.pickle', screenloglevel='INFO', serials=['FDO24261WAT', 'FDO242702QK'], switch_deploy=True, timeout=300, username=None, verbose=True)
============================================================

args parsed -- Running in DEPLOY mode
============================================================
Connecting to DCNM...
============================================================

Enter username:  rragan
rragan
Enter password for user rragan: 
2022-06-13 13:45:25,094 | 85928 | MainThread | (change_interfaces.py:254) | _normal_deploy | INFO | message: _normal_deploy: Pushing to DCNM and Deploying
============================================================
Pushing to DCNM and Deploying
============================================================

============================================================
switch serial numbers provided
============================================================
['FDO24261WAT', 'FDO242702QK']
============================================================

2022-06-13 13:45:25,096 | 85928 | MainThread | (dcnm_interfaces.py:893) | get_interfaces_nvpairs | INFO | message: get interfaces nvpairs
2022-06-13 13:45:25,096 | 85928 | MainThread | (dcnm_interfaces.py:848) | get_all_interfaces_nvpairs | INFO | message: get_all_interfaces_nvpairs: serial_number: FDO24261WAT
2022-06-13 13:45:25,278 | 85928 | MainThread | (dcnm_interfaces.py:848) | get_all_interfaces_nvpairs | INFO | message: get_all_interfaces_nvpairs: serial_number: FDO242702QK
2022-06-13 13:45:25,446 | 85928 | MainThread | (dcnm_interfaces.py:152) | get_switches_by_serial_number | INFO | message: get_switches_by_serial_number: for serial numbers: ['FDO24261WAT', 'FDO242702QK']
2022-06-13 13:45:26,078 | 85928 | MainThread | (dcnm_interfaces.py:1204) | get_switch_fabric | INFO | message: get_switch_fabric: getting fabric for switch FDO24261WAT
2022-06-13 13:45:26,237 | 85928 | MainThread | (dcnm_interfaces.py:1204) | get_switch_fabric | INFO | message: get_switch_fabric: getting fabric for switch FDO242702QK
============================================================
number of leaf switches
============================================================
2
============================================================

============================================================
leaf switches
============================================================
dict_keys(['FDO24261WAT', 'FDO242702QK'])
============================================================

============================================================
Adding Enabling of Orphan Ports
============================================================

2022-06-13 13:45:26,404 | 85928 | MainThread | (dcnm_interfaces.py:455) | get_switches_details | INFO | message: get switches details
2022-06-13 13:45:26,404 | 85928 | MainThread | (dcnm_interfaces.py:431) | get_all_switches_details | INFO | message: get_all_switches_detail: getting switch details
============================================================
interfaces to change
============================================================
{('Ethernet1/1', 'FDO24261WAT'): {'interfaces': [{'ifName': 'Ethernet1/1',
                                                  'nvPairs': {'ADMIN_STATE': 'true',
                                                              'ALLOWED_VLANS': 'none',
                                                              'BPDUGUARD_ENABLED': 'no',
                                                              'CONF': 'no cdp '
                                                                      'enable\n'
                                                                      'vpc '
                                                                      'orphan-port '
                                                                      'suspend',
                                                              'DESC': 'TEST1',
                                                              'FABRIC_NAME': 'site-2',
                                                              'INTF_NAME': 'Ethernet1/1',
                                                              'MTU': 'jumbo',
                                                              'POLICY_DESC': '',
                                                              'POLICY_ID': 'POLICY-5262840',
                                                              'PORTTYPE_FAST_ENABLED': 'true',
                                                              'PRIORITY': '500',
                                                              'SPEED': 'Auto'},
                                                  'serialNumber': 'FDO24261WAT'}],
                                  'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/1', 'FDO242702QK'): {'interfaces': [{'ifName': 'Ethernet1/1',
                                                  'nvPairs': {'ADMIN_STATE': 'true',
                                                              'ALLOWED_VLANS': 'none',
                                                              'BPDUGUARD_ENABLED': 'no',
                                                              'CONF': 'no cdp '
                                                                      'enable\n'
                                                                      'vpc '
                                                                      'orphan-port '
                                                                      'suspend\n'
                                                                      '\n'
                                                                      'vpc '
                                                                      'orphan-port '
                                                                      'suspend',
                                                              'DESC': 'Test 1',
                                                              'FABRIC_NAME': 'site-2',
                                                              'INTF_NAME': 'Ethernet1/1',
                                                              'MTU': 'jumbo',
                                                              'POLICY_DESC': '',
                                                              'POLICY_ID': 'POLICY-5263660',
                                                              'PORTTYPE_FAST_ENABLED': 'true',
                                                              'PRIORITY': '500',
                                                              'SPEED': 'Auto'},
                                                  'serialNumber': 'FDO242702QK'}],
                                  'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/11', 'FDO24261WAT'): {'interfaces': [{'ifName': 'Ethernet1/11',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'no cdp '
                                                                       'enable\n'
                                                                       'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'INTF_NAME': 'Ethernet1/11',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5261940',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO24261WAT'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/11', 'FDO242702QK'): {'interfaces': [{'ifName': 'Ethernet1/11',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': '\n'
                                                                       '\n'
                                                                       'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'INTF_NAME': 'Ethernet1/11',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5263210',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO242702QK'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/12', 'FDO24261WAT'): {'interfaces': [{'ifName': 'Ethernet1/12',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'no cdp '
                                                                       'enable\n'
                                                                       'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'INTF_NAME': 'Ethernet1/12',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5261360',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO24261WAT'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/12', 'FDO242702QK'): {'interfaces': [{'ifName': 'Ethernet1/12',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'no cdp '
                                                                       'enable\n'
                                                                       '\n'
                                                                       'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'INTF_NAME': 'Ethernet1/12',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5262890',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO242702QK'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/13', 'FDO24261WAT'): {'interfaces': [{'ifName': 'Ethernet1/13',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'no cdp '
                                                                       'enable\n'
                                                                       'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'INTF_NAME': 'Ethernet1/13',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5261550',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO24261WAT'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/13', 'FDO242702QK'): {'interfaces': [{'ifName': 'Ethernet1/13',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'GF': '',
                                                               'INTF_NAME': 'Ethernet1/13',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5263010',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO242702QK'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/14', 'FDO24261WAT'): {'interfaces': [{'ifName': 'Ethernet1/14',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'no cdp '
                                                                       'enable\n'
                                                                       'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'INTF_NAME': 'Ethernet1/14',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5260960',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO24261WAT'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/14', 'FDO242702QK'): {'interfaces': [{'ifName': 'Ethernet1/14',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'GF': '',
                                                               'INTF_NAME': 'Ethernet1/14',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5262490',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO242702QK'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/15', 'FDO24261WAT'): {'interfaces': [{'ifName': 'Ethernet1/15',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'GF': '',
                                                               'INTF_NAME': 'Ethernet1/15',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5261150',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO24261WAT'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/15', 'FDO242702QK'): {'interfaces': [{'ifName': 'Ethernet1/15',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'GF': '',
                                                               'INTF_NAME': 'Ethernet1/15',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5262680',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO242702QK'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/16', 'FDO24261WAT'): {'interfaces': [{'ifName': 'Ethernet1/16',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'GF': '',
                                                               'INTF_NAME': 'Ethernet1/16',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5260760',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO24261WAT'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/16', 'FDO242702QK'): {'interfaces': [{'ifName': 'Ethernet1/16',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'GF': '',
                                                               'INTF_NAME': 'Ethernet1/16',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5262280',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO242702QK'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/17', 'FDO24261WAT'): {'interfaces': [{'ifName': 'Ethernet1/17',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'GF': '',
                                                               'INTF_NAME': 'Ethernet1/17',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5260860',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO24261WAT'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/17', 'FDO242702QK'): {'interfaces': [{'ifName': 'Ethernet1/17',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'GF': '',
                                                               'INTF_NAME': 'Ethernet1/17',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5262380',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO242702QK'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/18', 'FDO24261WAT'): {'interfaces': [{'ifName': 'Ethernet1/18',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'GF': '',
                                                               'INTF_NAME': 'Ethernet1/18',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5260560',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO24261WAT'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/18', 'FDO242702QK'): {'interfaces': [{'ifName': 'Ethernet1/18',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'GF': '',
                                                               'INTF_NAME': 'Ethernet1/18',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5262080',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO242702QK'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/19', 'FDO24261WAT'): {'interfaces': [{'ifName': 'Ethernet1/19',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'GF': '',
                                                               'INTF_NAME': 'Ethernet1/19',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5260660',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO24261WAT'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/19', 'FDO242702QK'): {'interfaces': [{'ifName': 'Ethernet1/19',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'GF': '',
                                                               'INTF_NAME': 'Ethernet1/19',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5262180',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO242702QK'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/2', 'FDO24261WAT'): {'interfaces': [{'ifName': 'Ethernet1/2',
                                                  'nvPairs': {'ADMIN_STATE': 'true',
                                                              'ALLOWED_VLANS': 'none',
                                                              'BPDUGUARD_ENABLED': 'no',
                                                              'CONF': 'vpc '
                                                                      'orphan-port '
                                                                      'suspend',
                                                              'DESC': 'TestDescriptionfor3int',
                                                              'FABRIC_NAME': 'site-2',
                                                              'INTF_NAME': 'Ethernet1/2',
                                                              'MTU': 'jumbo',
                                                              'POLICY_DESC': '',
                                                              'POLICY_ID': 'POLICY-5262740',
                                                              'PORTTYPE_FAST_ENABLED': 'true',
                                                              'PRIORITY': '500',
                                                              'SPEED': 'Auto'},
                                                  'serialNumber': 'FDO24261WAT'}],
                                  'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/2', 'FDO242702QK'): {'interfaces': [{'ifName': 'Ethernet1/2',
                                                  'nvPairs': {'ADMIN_STATE': 'true',
                                                              'ALLOWED_VLANS': 'none',
                                                              'BPDUGUARD_ENABLED': 'no',
                                                              'CONF': 'vpc '
                                                                      'orphan-port '
                                                                      'suspend',
                                                              'DESC': '',
                                                              'FABRIC_NAME': 'site-2',
                                                              'GF': '',
                                                              'INTF_NAME': 'Ethernet1/2',
                                                              'MTU': 'jumbo',
                                                              'POLICY_DESC': '',
                                                              'POLICY_ID': 'POLICY-5263610',
                                                              'PORTTYPE_FAST_ENABLED': 'true',
                                                              'PRIORITY': '500',
                                                              'PTP': 'false',
                                                              'SPEED': 'Auto'},
                                                  'serialNumber': 'FDO242702QK'}],
                                  'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/20', 'FDO24261WAT'): {'interfaces': [{'ifName': 'Ethernet1/20',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'GF': '',
                                                               'INTF_NAME': 'Ethernet1/20',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5258050',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO24261WAT'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/20', 'FDO242702QK'): {'interfaces': [{'ifName': 'Ethernet1/20',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'GF': '',
                                                               'INTF_NAME': 'Ethernet1/20',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5259580',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO242702QK'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/21', 'FDO24261WAT'): {'interfaces': [{'ifName': 'Ethernet1/21',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'GF': '',
                                                               'INTF_NAME': 'Ethernet1/21',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5257650',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO24261WAT'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/21', 'FDO242702QK'): {'interfaces': [{'ifName': 'Ethernet1/21',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': 'This '
                                                                       'is '
                                                                       'test '
                                                                       'Desc',
                                                               'FABRIC_NAME': 'site-2',
                                                               'INTF_NAME': 'Ethernet1/21',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5259180',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO242702QK'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/22', 'FDO24261WAT'): {'interfaces': [{'ifName': 'Ethernet1/22',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'GF': '',
                                                               'INTF_NAME': 'Ethernet1/22',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5257850',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO24261WAT'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/22', 'FDO242702QK'): {'interfaces': [{'ifName': 'Ethernet1/22',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'GF': '',
                                                               'INTF_NAME': 'Ethernet1/22',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5259380',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO242702QK'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/23', 'FDO24261WAT'): {'interfaces': [{'ifName': 'Ethernet1/23',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'GF': '',
                                                               'INTF_NAME': 'Ethernet1/23',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5257450',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO24261WAT'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/23', 'FDO242702QK'): {'interfaces': [{'ifName': 'Ethernet1/23',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'GF': '',
                                                               'INTF_NAME': 'Ethernet1/23',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5258980',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO242702QK'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/24', 'FDO24261WAT'): {'interfaces': [{'ifName': 'Ethernet1/24',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'GF': '',
                                                               'INTF_NAME': 'Ethernet1/24',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5257550',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO24261WAT'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/24', 'FDO242702QK'): {'interfaces': [{'ifName': 'Ethernet1/24',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'GF': '',
                                                               'INTF_NAME': 'Ethernet1/24',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5259080',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO242702QK'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/25', 'FDO24261WAT'): {'interfaces': [{'ifName': 'Ethernet1/25',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'GF': '',
                                                               'INTF_NAME': 'Ethernet1/25',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5257250',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO24261WAT'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/25', 'FDO242702QK'): {'interfaces': [{'ifName': 'Ethernet1/25',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'GF': '',
                                                               'INTF_NAME': 'Ethernet1/25',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5258790',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO242702QK'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/26', 'FDO24261WAT'): {'interfaces': [{'ifName': 'Ethernet1/26',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'GF': '',
                                                               'INTF_NAME': 'Ethernet1/26',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5257350',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO24261WAT'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/26', 'FDO242702QK'): {'interfaces': [{'ifName': 'Ethernet1/26',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'GF': '',
                                                               'INTF_NAME': 'Ethernet1/26',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5258880',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO242702QK'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/27', 'FDO24261WAT'): {'interfaces': [{'ifName': 'Ethernet1/27',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'GF': '',
                                                               'INTF_NAME': 'Ethernet1/27',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5257050',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO24261WAT'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/27', 'FDO242702QK'): {'interfaces': [{'ifName': 'Ethernet1/27',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'GF': '',
                                                               'INTF_NAME': 'Ethernet1/27',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5258590',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO242702QK'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/28', 'FDO24261WAT'): {'interfaces': [{'ifName': 'Ethernet1/28',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'GF': '',
                                                               'INTF_NAME': 'Ethernet1/28',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5257150',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO24261WAT'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/28', 'FDO242702QK'): {'interfaces': [{'ifName': 'Ethernet1/28',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'GF': '',
                                                               'INTF_NAME': 'Ethernet1/28',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5258690',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO242702QK'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/29', 'FDO24261WAT'): {'interfaces': [{'ifName': 'Ethernet1/29',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'GF': '',
                                                               'INTF_NAME': 'Ethernet1/29',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5256950',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO24261WAT'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/29', 'FDO242702QK'): {'interfaces': [{'ifName': 'Ethernet1/29',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'GF': '',
                                                               'INTF_NAME': 'Ethernet1/29',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5258490',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO242702QK'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/3', 'FDO24261WAT'): {'interfaces': [{'ifName': 'Ethernet1/3',
                                                  'nvPairs': {'ADMIN_STATE': 'true',
                                                              'ALLOWED_VLANS': 'none',
                                                              'BPDUGUARD_ENABLED': 'no',
                                                              'CONF': 'no cdp '
                                                                      'enable\n'
                                                                      'vpc '
                                                                      'orphan-port '
                                                                      'suspend',
                                                              'DESC': 'TestDescriptionfor3int',
                                                              'FABRIC_NAME': 'site-2',
                                                              'INTF_NAME': 'Ethernet1/3',
                                                              'MTU': 'jumbo',
                                                              'POLICY_DESC': '',
                                                              'POLICY_ID': 'POLICY-5262640',
                                                              'PORTTYPE_FAST_ENABLED': 'true',
                                                              'PRIORITY': '500',
                                                              'PTP': 'false',
                                                              'SPEED': 'Auto'},
                                                  'serialNumber': 'FDO24261WAT'}],
                                  'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/3', 'FDO242702QK'): {'interfaces': [{'ifName': 'Ethernet1/3',
                                                  'nvPairs': {'ADMIN_STATE': 'true',
                                                              'ALLOWED_VLANS': 'none',
                                                              'BPDUGUARD_ENABLED': 'no',
                                                              'CONF': 'vpc '
                                                                      'orphan-port '
                                                                      'suspend',
                                                              'DESC': '',
                                                              'FABRIC_NAME': 'site-2',
                                                              'GF': '',
                                                              'INTF_NAME': 'Ethernet1/3',
                                                              'MTU': 'jumbo',
                                                              'POLICY_DESC': '',
                                                              'POLICY_ID': 'POLICY-5263560',
                                                              'PORTTYPE_FAST_ENABLED': 'true',
                                                              'PRIORITY': '500',
                                                              'PTP': 'false',
                                                              'SPEED': 'Auto'},
                                                  'serialNumber': 'FDO242702QK'}],
                                  'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/30', 'FDO24261WAT'): {'interfaces': [{'ifName': 'Ethernet1/30',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'GF': '',
                                                               'INTF_NAME': 'Ethernet1/30',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5259340',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO24261WAT'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/30', 'FDO242702QK'): {'interfaces': [{'ifName': 'Ethernet1/30',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'GF': '',
                                                               'INTF_NAME': 'Ethernet1/30',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5260870',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO242702QK'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/31', 'FDO24261WAT'): {'interfaces': [{'ifName': 'Ethernet1/31',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'GF': '',
                                                               'INTF_NAME': 'Ethernet1/31',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5259440',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO24261WAT'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/31', 'FDO242702QK'): {'interfaces': [{'ifName': 'Ethernet1/31',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'GF': '',
                                                               'INTF_NAME': 'Ethernet1/31',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5260970',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO242702QK'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/32', 'FDO24261WAT'): {'interfaces': [{'ifName': 'Ethernet1/32',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'GF': '',
                                                               'INTF_NAME': 'Ethernet1/32',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5259140',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO24261WAT'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/32', 'FDO242702QK'): {'interfaces': [{'ifName': 'Ethernet1/32',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'GF': '',
                                                               'INTF_NAME': 'Ethernet1/32',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5260670',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO242702QK'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/33', 'FDO24261WAT'): {'interfaces': [{'ifName': 'Ethernet1/33',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'GF': '',
                                                               'INTF_NAME': 'Ethernet1/33',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5259240',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO24261WAT'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/33', 'FDO242702QK'): {'interfaces': [{'ifName': 'Ethernet1/33',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'GF': '',
                                                               'INTF_NAME': 'Ethernet1/33',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5260770',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO242702QK'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/34', 'FDO24261WAT'): {'interfaces': [{'ifName': 'Ethernet1/34',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'GF': '',
                                                               'INTF_NAME': 'Ethernet1/34',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5258940',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO24261WAT'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/34', 'FDO242702QK'): {'interfaces': [{'ifName': 'Ethernet1/34',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'GF': '',
                                                               'INTF_NAME': 'Ethernet1/34',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5260470',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO242702QK'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/35', 'FDO24261WAT'): {'interfaces': [{'ifName': 'Ethernet1/35',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'GF': '',
                                                               'INTF_NAME': 'Ethernet1/35',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5259040',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO24261WAT'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/35', 'FDO242702QK'): {'interfaces': [{'ifName': 'Ethernet1/35',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'GF': '',
                                                               'INTF_NAME': 'Ethernet1/35',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5260570',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO242702QK'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/36', 'FDO24261WAT'): {'interfaces': [{'ifName': 'Ethernet1/36',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'GF': '',
                                                               'INTF_NAME': 'Ethernet1/36',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5258740',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO24261WAT'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/36', 'FDO242702QK'): {'interfaces': [{'ifName': 'Ethernet1/36',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'GF': '',
                                                               'INTF_NAME': 'Ethernet1/36',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5260270',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO242702QK'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/37', 'FDO24261WAT'): {'interfaces': [{'ifName': 'Ethernet1/37',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'GF': '',
                                                               'INTF_NAME': 'Ethernet1/37',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5258840',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO24261WAT'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/37', 'FDO242702QK'): {'interfaces': [{'ifName': 'Ethernet1/37',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'GF': '',
                                                               'INTF_NAME': 'Ethernet1/37',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5260370',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO242702QK'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/38', 'FDO24261WAT'): {'interfaces': [{'ifName': 'Ethernet1/38',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'GF': '',
                                                               'INTF_NAME': 'Ethernet1/38',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5258530',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO24261WAT'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/38', 'FDO242702QK'): {'interfaces': [{'ifName': 'Ethernet1/38',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'GF': '',
                                                               'INTF_NAME': 'Ethernet1/38',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5260070',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO242702QK'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/39', 'FDO24261WAT'): {'interfaces': [{'ifName': 'Ethernet1/39',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'GF': '',
                                                               'INTF_NAME': 'Ethernet1/39',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5258630',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO24261WAT'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/39', 'FDO242702QK'): {'interfaces': [{'ifName': 'Ethernet1/39',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'GF': '',
                                                               'INTF_NAME': 'Ethernet1/39',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5260170',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO242702QK'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/4', 'FDO24261WAT'): {'interfaces': [{'ifName': 'Ethernet1/4',
                                                  'nvPairs': {'ADMIN_STATE': 'true',
                                                              'ALLOWED_VLANS': 'none',
                                                              'BPDUGUARD_ENABLED': 'no',
                                                              'CONF': 'no cdp '
                                                                      'enable\n'
                                                                      'vpc '
                                                                      'orphan-port '
                                                                      'suspend',
                                                              'DESC': 'TestDescriptionfor3int',
                                                              'FABRIC_NAME': 'site-2',
                                                              'INTF_NAME': 'Ethernet1/4',
                                                              'MTU': 'jumbo',
                                                              'POLICY_DESC': '',
                                                              'POLICY_ID': 'POLICY-5262540',
                                                              'PORTTYPE_FAST_ENABLED': 'true',
                                                              'PRIORITY': '500',
                                                              'PTP': 'false',
                                                              'SPEED': 'Auto'},
                                                  'serialNumber': 'FDO24261WAT'}],
                                  'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/4', 'FDO242702QK'): {'interfaces': [{'ifName': 'Ethernet1/4',
                                                  'nvPairs': {'ADMIN_STATE': 'true',
                                                              'ALLOWED_VLANS': 'none',
                                                              'BPDUGUARD_ENABLED': 'no',
                                                              'CONF': 'vpc '
                                                                      'orphan-port '
                                                                      'suspend',
                                                              'DESC': '',
                                                              'FABRIC_NAME': 'site-2',
                                                              'GF': '',
                                                              'INTF_NAME': 'Ethernet1/4',
                                                              'MTU': 'jumbo',
                                                              'POLICY_DESC': '',
                                                              'POLICY_ID': 'POLICY-5263510',
                                                              'PORTTYPE_FAST_ENABLED': 'true',
                                                              'PRIORITY': '500',
                                                              'PTP': 'false',
                                                              'SPEED': 'Auto'},
                                                  'serialNumber': 'FDO242702QK'}],
                                  'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/40', 'FDO24261WAT'): {'interfaces': [{'ifName': 'Ethernet1/40',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'GF': '',
                                                               'INTF_NAME': 'Ethernet1/40',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5260460',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO24261WAT'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/40', 'FDO242702QK'): {'interfaces': [{'ifName': 'Ethernet1/40',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'GF': '',
                                                               'INTF_NAME': 'Ethernet1/40',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5261980',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO242702QK'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/41', 'FDO24261WAT'): {'interfaces': [{'ifName': 'Ethernet1/41',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'GF': '',
                                                               'INTF_NAME': 'Ethernet1/41',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5260260',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO24261WAT'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/41', 'FDO242702QK'): {'interfaces': [{'ifName': 'Ethernet1/41',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'GF': '',
                                                               'INTF_NAME': 'Ethernet1/41',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5261780',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO242702QK'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/42', 'FDO24261WAT'): {'interfaces': [{'ifName': 'Ethernet1/42',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'GF': '',
                                                               'INTF_NAME': 'Ethernet1/42',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5260360',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO24261WAT'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/42', 'FDO242702QK'): {'interfaces': [{'ifName': 'Ethernet1/42',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'GF': '',
                                                               'INTF_NAME': 'Ethernet1/42',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5261880',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO242702QK'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/43', 'FDO24261WAT'): {'interfaces': [{'ifName': 'Ethernet1/43',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'GF': '',
                                                               'INTF_NAME': 'Ethernet1/43',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5260060',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO24261WAT'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/43', 'FDO242702QK'): {'interfaces': [{'ifName': 'Ethernet1/43',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'GF': '',
                                                               'INTF_NAME': 'Ethernet1/43',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5261580',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO242702QK'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/44', 'FDO24261WAT'): {'interfaces': [{'ifName': 'Ethernet1/44',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'GF': '',
                                                               'INTF_NAME': 'Ethernet1/44',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5260160',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO24261WAT'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/44', 'FDO242702QK'): {'interfaces': [{'ifName': 'Ethernet1/44',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'GF': '',
                                                               'INTF_NAME': 'Ethernet1/44',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5261680',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO242702QK'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/45', 'FDO24261WAT'): {'interfaces': [{'ifName': 'Ethernet1/45',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'GF': '',
                                                               'INTF_NAME': 'Ethernet1/45',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5259840',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO24261WAT'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/45', 'FDO242702QK'): {'interfaces': [{'ifName': 'Ethernet1/45',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'GF': '',
                                                               'INTF_NAME': 'Ethernet1/45',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5261370',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO242702QK'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/46', 'FDO24261WAT'): {'interfaces': [{'ifName': 'Ethernet1/46',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'GF': '',
                                                               'INTF_NAME': 'Ethernet1/46',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5259950',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO24261WAT'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/46', 'FDO242702QK'): {'interfaces': [{'ifName': 'Ethernet1/46',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'GF': '',
                                                               'INTF_NAME': 'Ethernet1/46',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5261470',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO242702QK'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/47', 'FDO24261WAT'): {'interfaces': [{'ifName': 'Ethernet1/47',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'GF': '',
                                                               'INTF_NAME': 'Ethernet1/47',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5259640',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO24261WAT'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/47', 'FDO242702QK'): {'interfaces': [{'ifName': 'Ethernet1/47',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'GF': '',
                                                               'INTF_NAME': 'Ethernet1/47',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5261170',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO242702QK'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/48', 'FDO24261WAT'): {'interfaces': [{'ifName': 'Ethernet1/48',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'GF': '',
                                                               'INTF_NAME': 'Ethernet1/48',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5259740',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO24261WAT'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/48', 'FDO242702QK'): {'interfaces': [{'ifName': 'Ethernet1/48',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'vpc '
                                                                       'orphan-port '
                                                                       'suspend',
                                                               'DESC': '',
                                                               'FABRIC_NAME': 'site-2',
                                                               'GF': '',
                                                               'INTF_NAME': 'Ethernet1/48',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5261270',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO242702QK'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/5', 'FDO24261WAT'): {'interfaces': [{'ifName': 'Ethernet1/5',
                                                  'nvPairs': {'ADMIN_STATE': 'true',
                                                              'ALLOWED_VLANS': 'none',
                                                              'BPDUGUARD_ENABLED': 'no',
                                                              'CONF': 'vpc '
                                                                      'orphan-port '
                                                                      'suspend',
                                                              'DESC': 'I am '
                                                                      'the '
                                                                      'fifth '
                                                                      'little '
                                                                      'interface '
                                                                      'on '
                                                                      'first '
                                                                      'leaf',
                                                              'FABRIC_NAME': 'site-2',
                                                              'INTF_NAME': 'Ethernet1/5',
                                                              'MTU': 'jumbo',
                                                              'POLICY_DESC': '',
                                                              'POLICY_ID': 'POLICY-5258320',
                                                              'PORTTYPE_FAST_ENABLED': 'true',
                                                              'PRIORITY': '500',
                                                              'SPEED': 'Auto'},
                                                  'serialNumber': 'FDO24261WAT'}],
                                  'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/5', 'FDO242702QK'): {'interfaces': [{'ifName': 'Ethernet1/5',
                                                  'nvPairs': {'ADMIN_STATE': 'true',
                                                              'ALLOWED_VLANS': 'none',
                                                              'BPDUGUARD_ENABLED': 'no',
                                                              'CONF': 'vpc '
                                                                      'orphan-port '
                                                                      'suspend',
                                                              'DESC': '',
                                                              'FABRIC_NAME': 'site-2',
                                                              'GF': '',
                                                              'INTF_NAME': 'Ethernet1/5',
                                                              'MTU': 'jumbo',
                                                              'POLICY_DESC': '',
                                                              'POLICY_ID': 'POLICY-5259880',
                                                              'PORTTYPE_FAST_ENABLED': 'true',
                                                              'PRIORITY': '500',
                                                              'PTP': 'false',
                                                              'SPEED': 'Auto'},
                                                  'serialNumber': 'FDO242702QK'}],
                                  'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/6', 'FDO24261WAT'): {'interfaces': [{'ifName': 'Ethernet1/6',
                                                  'nvPairs': {'ADMIN_STATE': 'true',
                                                              'ALLOWED_VLANS': 'none',
                                                              'BPDUGUARD_ENABLED': 'no',
                                                              'CONF': 'vpc '
                                                                      'orphan-port '
                                                                      'suspend',
                                                              'DESC': 'I am '
                                                                      'the '
                                                                      'sixth '
                                                                      'little '
                                                                      'interface',
                                                              'FABRIC_NAME': 'site-2',
                                                              'INTF_NAME': 'Ethernet1/6',
                                                              'MTU': 'jumbo',
                                                              'POLICY_DESC': '',
                                                              'POLICY_ID': 'POLICY-5258240',
                                                              'PORTTYPE_FAST_ENABLED': 'true',
                                                              'PRIORITY': '500',
                                                              'SPEED': 'Auto'},
                                                  'serialNumber': 'FDO24261WAT'}],
                                  'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/6', 'FDO242702QK'): {'interfaces': [{'ifName': 'Ethernet1/6',
                                                  'nvPairs': {'ADMIN_STATE': 'true',
                                                              'ALLOWED_VLANS': 'none',
                                                              'BPDUGUARD_ENABLED': 'no',
                                                              'CONF': 'vpc '
                                                                      'orphan-port '
                                                                      'suspend',
                                                              'DESC': '',
                                                              'FABRIC_NAME': 'site-2',
                                                              'GF': '',
                                                              'INTF_NAME': 'Ethernet1/6',
                                                              'MTU': 'jumbo',
                                                              'POLICY_DESC': '',
                                                              'POLICY_ID': 'POLICY-5259790',
                                                              'PORTTYPE_FAST_ENABLED': 'true',
                                                              'PRIORITY': '500',
                                                              'PTP': 'false',
                                                              'SPEED': 'Auto'},
                                                  'serialNumber': 'FDO242702QK'}],
                                  'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/7', 'FDO24261WAT'): {'interfaces': [{'ifName': 'Ethernet1/7',
                                                  'nvPairs': {'ADMIN_STATE': 'true',
                                                              'ALLOWED_VLANS': 'none',
                                                              'BPDUGUARD_ENABLED': 'no',
                                                              'CONF': 'vpc '
                                                                      'orphan-port '
                                                                      'suspend',
                                                              'DESC': '',
                                                              'FABRIC_NAME': 'site-2',
                                                              'INTF_NAME': 'Ethernet1/7',
                                                              'MTU': 'jumbo',
                                                              'POLICY_DESC': '',
                                                              'POLICY_ID': 'POLICY-5258160',
                                                              'PORTTYPE_FAST_ENABLED': 'true',
                                                              'PRIORITY': '500',
                                                              'SPEED': 'Auto'},
                                                  'serialNumber': 'FDO24261WAT'}],
                                  'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/7', 'FDO242702QK'): {'interfaces': [{'ifName': 'Ethernet1/7',
                                                  'nvPairs': {'ADMIN_STATE': 'true',
                                                              'ALLOWED_VLANS': 'none',
                                                              'BPDUGUARD_ENABLED': 'no',
                                                              'CONF': 'no cdp '
                                                                      'enable\n'
                                                                      'vpc '
                                                                      'orphan-port '
                                                                      'suspend',
                                                              'DESC': 'test 7',
                                                              'FABRIC_NAME': 'site-2',
                                                              'INTF_NAME': 'Ethernet1/7',
                                                              'MTU': 'jumbo',
                                                              'POLICY_DESC': '',
                                                              'POLICY_ID': 'POLICY-5259680',
                                                              'PORTTYPE_FAST_ENABLED': 'true',
                                                              'PRIORITY': '500',
                                                              'SPEED': 'Auto'},
                                                  'serialNumber': 'FDO242702QK'}],
                                  'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/8', 'FDO24261WAT'): {'interfaces': [{'ifName': 'Ethernet1/8',
                                                  'nvPairs': {'ADMIN_STATE': 'true',
                                                              'ALLOWED_VLANS': 'none',
                                                              'BPDUGUARD_ENABLED': 'no',
                                                              'CONF': 'no cdp '
                                                                      'enable\n'
                                                                      'vpc '
                                                                      'orphan-port '
                                                                      'suspend',
                                                              'DESC': '',
                                                              'FABRIC_NAME': 'site-2',
                                                              'INTF_NAME': 'Ethernet1/8',
                                                              'MTU': 'jumbo',
                                                              'POLICY_DESC': '',
                                                              'POLICY_ID': 'POLICY-5257950',
                                                              'PORTTYPE_FAST_ENABLED': 'true',
                                                              'PRIORITY': '500',
                                                              'PTP': 'false',
                                                              'SPEED': 'Auto'},
                                                  'serialNumber': 'FDO24261WAT'}],
                                  'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/8', 'FDO242702QK'): {'interfaces': [{'ifName': 'Ethernet1/8',
                                                  'nvPairs': {'ADMIN_STATE': 'true',
                                                              'ALLOWED_VLANS': 'none',
                                                              'BPDUGUARD_ENABLED': 'no',
                                                              'CONF': 'no cdp '
                                                                      'enable\n'
                                                                      'vpc '
                                                                      'orphan-port '
                                                                      'suspend',
                                                              'DESC': 'test 8',
                                                              'FABRIC_NAME': 'site-2',
                                                              'INTF_NAME': 'Ethernet1/8',
                                                              'MTU': 'jumbo',
                                                              'POLICY_DESC': '',
                                                              'POLICY_ID': 'POLICY-5259480',
                                                              'PORTTYPE_FAST_ENABLED': 'true',
                                                              'PRIORITY': '500',
                                                              'SPEED': 'Auto'},
                                                  'serialNumber': 'FDO242702QK'}],
                                  'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/9', 'FDO24261WAT'): {'interfaces': [{'ifName': 'Ethernet1/9',
                                                  'nvPairs': {'ADMIN_STATE': 'true',
                                                              'ALLOWED_VLANS': 'none',
                                                              'BPDUGUARD_ENABLED': 'no',
                                                              'CONF': 'no cdp '
                                                                      'enable\n'
                                                                      'vpc '
                                                                      'orphan-port '
                                                                      'suspend',
                                                              'DESC': '',
                                                              'FABRIC_NAME': 'site-2',
                                                              'INTF_NAME': 'Ethernet1/9',
                                                              'MTU': 'jumbo',
                                                              'POLICY_DESC': '',
                                                              'POLICY_ID': 'POLICY-5257750',
                                                              'PORTTYPE_FAST_ENABLED': 'true',
                                                              'PRIORITY': '500',
                                                              'SPEED': 'Auto'},
                                                  'serialNumber': 'FDO24261WAT'}],
                                  'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/9', 'FDO242702QK'): {'interfaces': [{'ifName': 'Ethernet1/9',
                                                  'nvPairs': {'ADMIN_STATE': 'true',
                                                              'ALLOWED_VLANS': 'none',
                                                              'BPDUGUARD_ENABLED': 'no',
                                                              'CONF': 'no cdp '
                                                                      'enable\n'
                                                                      'vpc '
                                                                      'orphan-port '
                                                                      'suspend',
                                                              'DESC': '',
                                                              'FABRIC_NAME': 'site-2',
                                                              'INTF_NAME': 'Ethernet1/9',
                                                              'MTU': 'jumbo',
                                                              'POLICY_DESC': '',
                                                              'POLICY_ID': 'POLICY-5259290',
                                                              'PORTTYPE_FAST_ENABLED': 'true',
                                                              'PRIORITY': '500',
                                                              'SPEED': 'Auto'},
                                                  'serialNumber': 'FDO242702QK'}],
                                  'policy': 'int_trunk_host_11_1'}}
============================================================

============================================================
Putting changes to dcnm
============================================================

2022-06-13 13:45:26,986 | 85928 | MainThread | (dcnm_interfaces.py:1077) | put_interface_changes | INFO | message: Putting interface changes to dcnm
\  (Elapsed Time : 0:00:54.70)
============================================================
Elapsed Time:
============================================================
54.713783979415894
============================================================

============================================================
Successfully Pushed All Configurations!
============================================================

============================================================
Successfully Pushed Following Configs
============================================================
{('Ethernet1/1', 'FDO24261WAT'),
 ('Ethernet1/1', 'FDO242702QK'),
 ('Ethernet1/11', 'FDO24261WAT'),
 ('Ethernet1/11', 'FDO242702QK'),
 ('Ethernet1/12', 'FDO24261WAT'),
 ('Ethernet1/12', 'FDO242702QK'),
 ('Ethernet1/13', 'FDO24261WAT'),
 ('Ethernet1/13', 'FDO242702QK'),
 ('Ethernet1/14', 'FDO24261WAT'),
 ('Ethernet1/14', 'FDO242702QK'),
 ('Ethernet1/15', 'FDO24261WAT'),
 ('Ethernet1/15', 'FDO242702QK'),
 ('Ethernet1/16', 'FDO24261WAT'),
 ('Ethernet1/16', 'FDO242702QK'),
 ('Ethernet1/17', 'FDO24261WAT'),
 ('Ethernet1/17', 'FDO242702QK'),
 ('Ethernet1/18', 'FDO24261WAT'),
 ('Ethernet1/18', 'FDO242702QK'),
 ('Ethernet1/19', 'FDO24261WAT'),
 ('Ethernet1/19', 'FDO242702QK'),
 ('Ethernet1/2', 'FDO24261WAT'),
 ('Ethernet1/2', 'FDO242702QK'),
 ('Ethernet1/20', 'FDO24261WAT'),
 ('Ethernet1/20', 'FDO242702QK'),
 ('Ethernet1/21', 'FDO24261WAT'),
 ('Ethernet1/21', 'FDO242702QK'),
 ('Ethernet1/22', 'FDO24261WAT'),
 ('Ethernet1/22', 'FDO242702QK'),
 ('Ethernet1/23', 'FDO24261WAT'),
 ('Ethernet1/23', 'FDO242702QK'),
 ('Ethernet1/24', 'FDO24261WAT'),
 ('Ethernet1/24', 'FDO242702QK'),
 ('Ethernet1/25', 'FDO24261WAT'),
 ('Ethernet1/25', 'FDO242702QK'),
 ('Ethernet1/26', 'FDO24261WAT'),
 ('Ethernet1/26', 'FDO242702QK'),
 ('Ethernet1/27', 'FDO24261WAT'),
 ('Ethernet1/27', 'FDO242702QK'),
 ('Ethernet1/28', 'FDO24261WAT'),
 ('Ethernet1/28', 'FDO242702QK'),
 ('Ethernet1/29', 'FDO24261WAT'),
 ('Ethernet1/29', 'FDO242702QK'),
 ('Ethernet1/3', 'FDO24261WAT'),
 ('Ethernet1/3', 'FDO242702QK'),
 ('Ethernet1/30', 'FDO24261WAT'),
 ('Ethernet1/30', 'FDO242702QK'),
 ('Ethernet1/31', 'FDO24261WAT'),
 ('Ethernet1/31', 'FDO242702QK'),
 ('Ethernet1/32', 'FDO24261WAT'),
 ('Ethernet1/32', 'FDO242702QK'),
 ('Ethernet1/33', 'FDO24261WAT'),
 ('Ethernet1/33', 'FDO242702QK'),
 ('Ethernet1/34', 'FDO24261WAT'),
 ('Ethernet1/34', 'FDO242702QK'),
 ('Ethernet1/35', 'FDO24261WAT'),
 ('Ethernet1/35', 'FDO242702QK'),
 ('Ethernet1/36', 'FDO24261WAT'),
 ('Ethernet1/36', 'FDO242702QK'),
 ('Ethernet1/37', 'FDO24261WAT'),
 ('Ethernet1/37', 'FDO242702QK'),
 ('Ethernet1/38', 'FDO24261WAT'),
 ('Ethernet1/38', 'FDO242702QK'),
 ('Ethernet1/39', 'FDO24261WAT'),
 ('Ethernet1/39', 'FDO242702QK'),
 ('Ethernet1/4', 'FDO24261WAT'),
 ('Ethernet1/4', 'FDO242702QK'),
 ('Ethernet1/40', 'FDO24261WAT'),
 ('Ethernet1/40', 'FDO242702QK'),
 ('Ethernet1/41', 'FDO24261WAT'),
 ('Ethernet1/41', 'FDO242702QK'),
 ('Ethernet1/42', 'FDO24261WAT'),
 ('Ethernet1/42', 'FDO242702QK'),
 ('Ethernet1/43', 'FDO24261WAT'),
 ('Ethernet1/43', 'FDO242702QK'),
 ('Ethernet1/44', 'FDO24261WAT'),
 ('Ethernet1/44', 'FDO242702QK'),
 ('Ethernet1/45', 'FDO24261WAT'),
 ('Ethernet1/45', 'FDO242702QK'),
 ('Ethernet1/46', 'FDO24261WAT'),
 ('Ethernet1/46', 'FDO242702QK'),
 ('Ethernet1/47', 'FDO24261WAT'),
 ('Ethernet1/47', 'FDO242702QK'),
 ('Ethernet1/48', 'FDO24261WAT'),
 ('Ethernet1/48', 'FDO242702QK'),
 ('Ethernet1/5', 'FDO24261WAT'),
 ('Ethernet1/5', 'FDO242702QK'),
 ('Ethernet1/6', 'FDO24261WAT'),
 ('Ethernet1/6', 'FDO242702QK'),
 ('Ethernet1/7', 'FDO24261WAT'),
 ('Ethernet1/7', 'FDO242702QK'),
 ('Ethernet1/8', 'FDO24261WAT'),
 ('Ethernet1/8', 'FDO242702QK'),
 ('Ethernet1/9', 'FDO24261WAT'),
 ('Ethernet1/9', 'FDO242702QK')}
============================================================

2022-06-13 13:46:21,915 | 85928 | MainThread | (interfaces_utilities.py:223) | deploy_to_fabric_using_switch_deploy | INFO | message: Deploying changes to switches
============================================================
Deploying changes to switches
============================================================
['FDO24261WAT', 'FDO242702QK']
============================================================

-  (Elapsed Time : 0:00:00.00)2022-06-13 13:46:22,075 | 85928 | MainThread | (dcnm_interfaces.py:956) | deploy_switch_config | INFO | message: deploy switch conifg
/  (Elapsed Time : 0:02:06.36)
============================================================
Elapsed Time: 
============================================================
126.47818160057068
============================================================

============================================================
deploy returned successfully for:
============================================================
'FDO24261WAT'
============================================================

============================================================
Deployed or attempted to deploy the following:
============================================================
{'FDO24261WAT', 'FDO242702QK'}
============================================================

2022-06-13 13:48:28,652 | 85928 | MainThread | (interfaces_utilities.py:254) | deploy_to_fabric_using_switch_deploy | INFO | message: waiting for switches status
============================================================
waiting for switches status
============================================================

2022-06-13 13:48:28,654 | 85928 | MainThread | (dcnm_interfaces.py:1390) | wait_for_switches_status | INFO | message: Checking for switch status
-  (elapsed time waiting for switches status : 0:00:00.00)2022-06-13 13:48:28,654 | 85928 | MainThread | (dcnm_interfaces.py:1323) | get_switches_status | INFO | message: get swtiches status
|  (elapsed time waiting for switches status : 0:00:00.41)
============================================================
Elapsed Time:
============================================================
0.44848132133483887
============================================================

============================================================
!!Successfully Deployed Config Changes to Switches!!
============================================================
['FDO24261WAT', 'FDO242702QK']
============================================================


========================================
========================================
FINISHED DEPLOYING. GO GET A BEER!
========================================
2022-06-13 13:48:29,268 | 85928 | MainThread | (dcnm_interfaces.py:893) | get_interfaces_nvpairs | INFO | message: get interfaces nvpairs
2022-06-13 13:48:29,271 | 85928 | MainThread | (dcnm_interfaces.py:848) | get_all_interfaces_nvpairs | INFO | message: get_all_interfaces_nvpairs: serial_number: FDO24261WAT
2022-06-13 13:48:29,441 | 85928 | MainThread | (dcnm_interfaces.py:848) | get_all_interfaces_nvpairs | INFO | message: get_all_interfaces_nvpairs: serial_number: FDO242702QK
============================================================
Verifying Interface Configurations
============================================================

============================================================
Successfully Verified All Interface Changes! Yay!
============================================================

========================================
FINISHED. GO GET PLASTERED!
========================================

Process finished with exit code 0

```

## example cli for backout of the above example
`python .\change_interfaces.py -a 10.0.17.99 -n FDO24261WAT FDO242702QK -o -v --deploy -j -b`

## example run for the description option

```
C:\Users\rragan\Anaconda3\envs\dcnm\python.exe C:/Users/rragan/Documents/PyProjects/dcnm/dcnm/interfaces/change_interfaces.py -a 10.0.17.99 -n FDO24261WAT FDO242702QK -d -v --deploy -j
20
2022-06-13 14:04:32,608 | 38904 | MainThread | (change_interfaces.py:398) | <module> | CRITICAL | message: Started
============================================================
args:
============================================================
Namespace(all=False, backout=False, cdp=False, dcnm='10.0.17.99', debug=False, description=True, dryrun=False, excel=None, icpickle='interfaces_existing_conf.pickle', input_file='', loglevel=None, mgmt=False, orphan=False, pickle='swi
tches_configuration_policies.pickle', screenloglevel='INFO', serials=['FDO24261WAT', 'FDO242702QK'], switch_deploy=True, timeout=300, username=None, verbose=True)
============================================================

args parsed -- Running in DEPLOY mode
============================================================
Connecting to DCNM...
============================================================

Enter username:  rragan
rragan
Enter password for user rragan: 
2022-06-13 14:04:50,317 | 38904 | MainThread | (change_interfaces.py:254) | _normal_deploy | INFO | message: _normal_deploy: Pushing to DCNM and Deploying
============================================================
Pushing to DCNM and Deploying
============================================================

============================================================
switch serial numbers provided
============================================================
['FDO24261WAT', 'FDO242702QK']
============================================================

2022-06-13 14:04:50,320 | 38904 | MainThread | (dcnm_interfaces.py:893) | get_interfaces_nvpairs | INFO | message: get interfaces nvpairs
2022-06-13 14:04:50,320 | 38904 | MainThread | (dcnm_interfaces.py:848) | get_all_interfaces_nvpairs | INFO | message: get_all_interfaces_nvpairs: serial_number: FDO24261WAT
2022-06-13 14:04:50,845 | 38904 | MainThread | (dcnm_interfaces.py:848) | get_all_interfaces_nvpairs | INFO | message: get_all_interfaces_nvpairs: serial_number: FDO242702QK
2022-06-13 14:04:51,660 | 38904 | MainThread | (dcnm_interfaces.py:152) | get_switches_by_serial_number | INFO | message: get_switches_by_serial_number: for serial numbers: ['FDO24261WAT', 'FDO242702QK']
2022-06-13 14:04:52,600 | 38904 | MainThread | (dcnm_interfaces.py:1204) | get_switch_fabric | INFO | message: get_switch_fabric: getting fabric for switch FDO24261WAT
2022-06-13 14:04:53,159 | 38904 | MainThread | (dcnm_interfaces.py:1204) | get_switch_fabric | INFO | message: get_switch_fabric: getting fabric for switch FDO242702QK
============================================================
number of leaf switches
============================================================
2
============================================================

============================================================
leaf switches
============================================================
dict_keys(['FDO24261WAT', 'FDO242702QK'])
============================================================

============================================================
Adding Description Changes
============================================================

2022-06-13 14:04:53,727 | 38904 | MainThread | (dcnm_interfaces.py:321) | get_switches_policies | INFO | message: get_switches_policies: getting switch policies for serial number: None
============================================================
switch policies
============================================================
defaultdict(<class 'list'>,
            {'FDO24261WAT': [{'autoGenerated': False,
                              'createdOn': 1652216948369,
                              'deleted': False,
                              'description': 'interface descriptions',
                              'entityName': 'SWITCH',
                              'entityType': 'SWITCH',
                              'fabricName': 'site-2',
                              'generatedConfig': 'interface Ethernet1/7\n'
                                                 '  description Test 7\n'
                                                 'interface Ethernet1/8\n'
                                                 '  description Test 8\n'
                                                 '\n'
                                                 '\n',
                              'id': 582700,
                              'modifiedOn': 1652216948369,
                              'nvPairs': {'CONF': 'interface Ethernet1/7\n'
                                                  '  description Test 7\n'
                                                  'interface Ethernet1/8\n'
                                                  '  description Test 8',
                                          'FABRIC_NAME': 'vxlan_cml_3',
                                          'POLICY_DESC': 'interface '
                                                         'descriptions',
                                          'POLICY_ID': 'POLICY-582700',
                                          'PRIORITY': '500',
                                          'SECENTITY': '',
                                          'SECENTTYPE': '',
                                          'SERIAL_NUMBER': ''},
                              'policyId': 'POLICY-582700',
                              'priority': 500,
                              'resourcesLinked': '',
                              'serialNumber': 'FDO24261WAT',
                              'source': '',
                              'status': 'NA',
                              'statusOn': 1652216948369,
                              'templateContentType': 'PYTHON',
                              'templateName': 'switch_freeform'},
                             {'autoGenerated': False,
                              'createdOn': 1652216948701,
                              'deleted': False,
                              'description': 'more descriptions',
                              'entityName': 'SWITCH',
                              'entityType': 'SWITCH',
                              'fabricName': 'site-2',
                              'generatedConfig': 'interface Ethernet1/10\n'
                                                 '  description Test 10\n'
                                                 'interface Ethernet1/11\n'
                                                 '  description Test 11\n'
                                                 '\n'
                                                 '\n',
                              'id': 5421000,
                              'modifiedOn': 1652216948701,
                              'nvPairs': {'CONF': 'interface Ethernet1/10\n'
                                                  '  description Test 10\n'
                                                  'interface Ethernet1/11\n'
                                                  '  description Test 11',
                                          'FABRIC_NAME': 'site-2',
                                          'POLICY_DESC': 'more descriptions',
                                          'POLICY_ID': 'POLICY-5421000',
                                          'PRIORITY': '500',
                                          'SECENTITY': '',
                                          'SECENTTYPE': '',
                                          'SERIAL_NUMBER': ''},
                              'policyId': 'POLICY-5421000',
                              'priority': 500,
                              'resourcesLinked': '',
                              'serialNumber': 'FDO24261WAT',
                              'source': '',
                              'status': 'NA',
                              'statusOn': 1652216948701,
                              'templateContentType': 'PYTHON',
                              'templateName': 'switch_freeform'},
                             {'autoGenerated': False,
                              'createdOn': 1652216949039,
                              'deleted': False,
                              'description': 'more more descriptions',
                              'entityName': 'SWITCH',
                              'entityType': 'SWITCH',
                              'fabricName': 'site-2',
                              'generatedConfig': 'interface Ethernet1/12\n'
                                                 '  description Test 12\n'
                                                 'interface Ethernet1/13\n'
                                                 '  description Test 13\n'
                                                 '\n'
                                                 '\n',
                              'id': 5421040,
                              'modifiedOn': 1652216949039,
                              'nvPairs': {'CONF': 'interface Ethernet1/12\n'
                                                  '  description Test 12\n'
                                                  'interface Ethernet1/13\n'
                                                  '  description Test 13',
                                          'FABRIC_NAME': 'site-2',
                                          'POLICY_DESC': 'more more '
                                                         'descriptions',
                                          'POLICY_ID': 'POLICY-5421040',
                                          'PRIORITY': '500',
                                          'SECENTITY': '',
                                          'SECENTTYPE': '',
                                          'SERIAL_NUMBER': ''},
                              'policyId': 'POLICY-5421040',
                              'priority': 500,
                              'resourcesLinked': '',
                              'serialNumber': 'FDO24261WAT',
                              'source': '',
                              'status': 'NA',
                              'statusOn': 1652216949039,
                              'templateContentType': 'PYTHON',
                              'templateName': 'switch_freeform'}],
             'FDO242702QK': [{'autoGenerated': False,
                              'createdOn': 1650295719703,
                              'deleted': False,
                              'description': 'more more descriptions',
                              'entityName': 'SWITCH',
                              'entityType': 'SWITCH',
                              'fabricName': 'site-2',
                              'generatedConfig': 'interface Ethernet1/12\n'
                                                 '  description Test 12\n'
                                                 'interface Ethernet1/13\n'
                                                 '  description Test 13\n'
                                                 '\n'
                                                 '\n',
                              'id': 5421060,
                              'modifiedOn': 1650295719703,
                              'nvPairs': {'CONF': 'interface Ethernet1/12\n'
                                                  '  description Test 12\n'
                                                  'interface Ethernet1/13\n'
                                                  '  description Test 13',
                                          'FABRIC_NAME': 'site-2',
                                          'POLICY_DESC': 'more more '
                                                         'descriptions',
                                          'POLICY_ID': 'POLICY-5421060',
                                          'PRIORITY': '500',
                                          'SECENTITY': '',
                                          'SECENTTYPE': '',
                                          'SERIAL_NUMBER': ''},
                              'policyId': 'POLICY-5421060',
                              'priority': 500,
                              'resourcesLinked': '',
                              'serialNumber': 'FDO242702QK',
                              'source': '',
                              'status': 'NA',
                              'statusOn': 1650295719703,
                              'templateContentType': 'PYTHON',
                              'templateName': 'switch_freeform'},
                             {'autoGenerated': False,
                              'createdOn': 1650295301019,
                              'deleted': False,
                              'description': 'more descriptions',
                              'entityName': 'SWITCH',
                              'entityType': 'SWITCH',
                              'fabricName': 'site-2',
                              'generatedConfig': 'interface Ethernet1/10\n'
                                                 '  description Test 10\n'
                                                 'interface Ethernet1/11\n'
                                                 '  description Test 11\n'
                                                 '\n'
                                                 '\n',
                              'id': 5421020,
                              'modifiedOn': 1650295301019,
                              'nvPairs': {'CONF': 'interface Ethernet1/10\n'
                                                  '  description Test 10\n'
                                                  'interface Ethernet1/11\n'
                                                  '  description Test 11',
                                          'FABRIC_NAME': 'site-2',
                                          'POLICY_DESC': 'more descriptions',
                                          'POLICY_ID': 'POLICY-5421020',
                                          'PRIORITY': '500',
                                          'SECENTITY': '',
                                          'SECENTTYPE': '',
                                          'SERIAL_NUMBER': ''},
                              'policyId': 'POLICY-5421020',
                              'priority': 500,
                              'resourcesLinked': '',
                              'serialNumber': 'FDO242702QK',
                              'source': '',
                              'status': 'NA',
                              'statusOn': 1650295301019,
                              'templateContentType': 'PYTHON',
                              'templateName': 'switch_freeform'}]})
============================================================

============================================================
existing description from policies
============================================================
[InfoFromPolicies(info={('Ethernet1/7', 'FDO24261WAT'): 'Test 7', ('Ethernet1/8', 'FDO24261WAT'): 'Test 8'}, policyId='POLICY-582700'),
 InfoFromPolicies(info={('Ethernet1/10', 'FDO24261WAT'): 'Test 10', ('Ethernet1/11', 'FDO24261WAT'): 'Test 11'}, policyId='POLICY-5421000'),
 InfoFromPolicies(info={('Ethernet1/12', 'FDO24261WAT'): 'Test 12', ('Ethernet1/13', 'FDO24261WAT'): 'Test 13'}, policyId='POLICY-5421040'),
 InfoFromPolicies(info={('Ethernet1/12', 'FDO242702QK'): 'Test 12', ('Ethernet1/13', 'FDO242702QK'): 'Test 13'}, policyId='POLICY-5421060'),
 InfoFromPolicies(info={('Ethernet1/10', 'FDO242702QK'): 'Test 10', ('Ethernet1/11', 'FDO242702QK'): 'Test 11'}, policyId='POLICY-5421020')]
============================================================

============================================================
deleting policy ids
============================================================
['POLICY-582700',
 'POLICY-5421000',
 'POLICY-5421040',
 'POLICY-5421060',
 'POLICY-5421020']
============================================================

2022-06-13 14:04:55,992 | 38904 | MainThread | (dcnm_interfaces.py:415) | delete_switch_policies | INFO | message: delete switch policies
============================================================
existing descriptions from switch policies
============================================================
{('Ethernet1/10', 'FDO24261WAT'): 'Test 10',
 ('Ethernet1/10', 'FDO242702QK'): 'Test 10',
 ('Ethernet1/11', 'FDO24261WAT'): 'Test 11',
 ('Ethernet1/11', 'FDO242702QK'): 'Test 11',
 ('Ethernet1/12', 'FDO24261WAT'): 'Test 12',
 ('Ethernet1/12', 'FDO242702QK'): 'Test 12',
 ('Ethernet1/13', 'FDO24261WAT'): 'Test 13',
 ('Ethernet1/13', 'FDO242702QK'): 'Test 13',
 ('Ethernet1/7', 'FDO24261WAT'): 'Test 7',
 ('Ethernet1/8', 'FDO24261WAT'): 'Test 8'}
============================================================

============================================================
interfaces to change
============================================================
{('Ethernet1/10', 'FDO24261WAT'): {'interfaces': [{'ifName': 'Ethernet1/10',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': '100',
                                                               'CONF': '',
                                                               'DESC': 'Test '
                                                                       '10',
                                                               'FABRIC_NAME': 'site-2',
                                                               'INTF_NAME': 'Ethernet1/10',
                                                               'INTF_PTP': 'false',
                                                               'PC_MODE': 'active',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5411560',
                                                               'PO_ID': 'port-channel1',
                                                               'PRIMARY_INTF': 'vPC1',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false'},
                                                   'serialNumber': 'FDO24261WAT'}],
                                   'policy': 'int_vpc_trunk_po_member_11_1'},
 ('Ethernet1/10', 'FDO242702QK'): {'interfaces': [{'ifName': 'Ethernet1/10',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': '100',
                                                               'CONF': 'no cdp '
                                                                       'enable',
                                                               'DESC': 'Test '
                                                                       '10',
                                                               'FABRIC_NAME': 'site-2',
                                                               'INTF_NAME': 'Ethernet1/10',
                                                               'PC_MODE': 'active',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5411510',
                                                               'PO_ID': 'port-channel1',
                                                               'PRIMARY_INTF': 'vPC1',
                                                               'PRIORITY': '500'},
                                                   'serialNumber': 'FDO242702QK'}],
                                   'policy': 'int_vpc_trunk_po_member_11_1'},
 ('Ethernet1/11', 'FDO24261WAT'): {'interfaces': [{'ifName': 'Ethernet1/11',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'no cdp '
                                                                       'enable',
                                                               'DESC': 'Test '
                                                                       '11',
                                                               'FABRIC_NAME': 'site-2',
                                                               'INTF_NAME': 'Ethernet1/11',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5261940',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO24261WAT'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/11', 'FDO242702QK'): {'interfaces': [{'ifName': 'Ethernet1/11',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': '\n',
                                                               'DESC': 'Test '
                                                                       '11',
                                                               'FABRIC_NAME': 'site-2',
                                                               'INTF_NAME': 'Ethernet1/11',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5263210',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO242702QK'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/12', 'FDO24261WAT'): {'interfaces': [{'ifName': 'Ethernet1/12',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'no cdp '
                                                                       'enable',
                                                               'DESC': 'Test '
                                                                       '12',
                                                               'FABRIC_NAME': 'site-2',
                                                               'INTF_NAME': 'Ethernet1/12',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5261360',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO24261WAT'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/12', 'FDO242702QK'): {'interfaces': [{'ifName': 'Ethernet1/12',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'no cdp '
                                                                       'enable\n',
                                                               'DESC': 'Test '
                                                                       '12',
                                                               'FABRIC_NAME': 'site-2',
                                                               'INTF_NAME': 'Ethernet1/12',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5262890',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO242702QK'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/13', 'FDO24261WAT'): {'interfaces': [{'ifName': 'Ethernet1/13',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': 'no cdp '
                                                                       'enable',
                                                               'DESC': 'Test '
                                                                       '13',
                                                               'FABRIC_NAME': 'site-2',
                                                               'INTF_NAME': 'Ethernet1/13',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5261550',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO24261WAT'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/13', 'FDO242702QK'): {'interfaces': [{'ifName': 'Ethernet1/13',
                                                   'nvPairs': {'ADMIN_STATE': 'true',
                                                               'ALLOWED_VLANS': 'none',
                                                               'BPDUGUARD_ENABLED': 'no',
                                                               'CONF': '',
                                                               'DESC': 'Test '
                                                                       '13',
                                                               'FABRIC_NAME': 'site-2',
                                                               'GF': '',
                                                               'INTF_NAME': 'Ethernet1/13',
                                                               'MTU': 'jumbo',
                                                               'POLICY_DESC': '',
                                                               'POLICY_ID': 'POLICY-5263010',
                                                               'PORTTYPE_FAST_ENABLED': 'true',
                                                               'PRIORITY': '500',
                                                               'PTP': 'false',
                                                               'SPEED': 'Auto'},
                                                   'serialNumber': 'FDO242702QK'}],
                                   'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/7', 'FDO24261WAT'): {'interfaces': [{'ifName': 'Ethernet1/7',
                                                  'nvPairs': {'ADMIN_STATE': 'true',
                                                              'ALLOWED_VLANS': 'none',
                                                              'BPDUGUARD_ENABLED': 'no',
                                                              'CONF': '',
                                                              'DESC': 'Test 7',
                                                              'FABRIC_NAME': 'site-2',
                                                              'INTF_NAME': 'Ethernet1/7',
                                                              'MTU': 'jumbo',
                                                              'POLICY_DESC': '',
                                                              'POLICY_ID': 'POLICY-5258160',
                                                              'PORTTYPE_FAST_ENABLED': 'true',
                                                              'PRIORITY': '500',
                                                              'SPEED': 'Auto'},
                                                  'serialNumber': 'FDO24261WAT'}],
                                  'policy': 'int_trunk_host_11_1'},
 ('Ethernet1/8', 'FDO24261WAT'): {'interfaces': [{'ifName': 'Ethernet1/8',
                                                  'nvPairs': {'ADMIN_STATE': 'true',
                                                              'ALLOWED_VLANS': 'none',
                                                              'BPDUGUARD_ENABLED': 'no',
                                                              'CONF': 'no cdp '
                                                                      'enable',
                                                              'DESC': 'Test 8',
                                                              'FABRIC_NAME': 'site-2',
                                                              'INTF_NAME': 'Ethernet1/8',
                                                              'MTU': 'jumbo',
                                                              'POLICY_DESC': '',
                                                              'POLICY_ID': 'POLICY-5257950',
                                                              'PORTTYPE_FAST_ENABLED': 'true',
                                                              'PRIORITY': '500',
                                                              'PTP': 'false',
                                                              'SPEED': 'Auto'},
                                                  'serialNumber': 'FDO24261WAT'}],
                                  'policy': 'int_trunk_host_11_1'}}
============================================================

============================================================
Putting changes to dcnm
============================================================

2022-06-13 14:04:57,494 | 38904 | MainThread | (dcnm_interfaces.py:1077) | put_interface_changes | INFO | message: Putting interface changes to dcnm
-  (Elapsed Time : 0:00:09.95)
============================================================
Elapsed Time:
============================================================
10.044122219085693
============================================================

============================================================
Successfully Pushed All Configurations!
============================================================

============================================================
Successfully Pushed Following Configs
============================================================
{('Ethernet1/10', 'FDO24261WAT'),
 ('Ethernet1/10', 'FDO242702QK'),
 ('Ethernet1/11', 'FDO24261WAT'),
 ('Ethernet1/11', 'FDO242702QK'),
 ('Ethernet1/12', 'FDO24261WAT'),
 ('Ethernet1/12', 'FDO242702QK'),
 ('Ethernet1/13', 'FDO24261WAT'),
 ('Ethernet1/13', 'FDO242702QK'),
 ('Ethernet1/7', 'FDO24261WAT'),
 ('Ethernet1/8', 'FDO24261WAT')}
============================================================

2022-06-13 14:05:07,662 | 38904 | MainThread | (interfaces_utilities.py:223) | deploy_to_fabric_using_switch_deploy | INFO | message: Deploying changes to switches
============================================================
Deploying changes to switches
============================================================
['FDO24261WAT', 'FDO242702QK']
============================================================

2022-06-13 14:05:08,473 | 38904 | MainThread | (dcnm_interfaces.py:956) | deploy_switch_config | INFO | message: deploy switch conifg
\  (Elapsed Time : 0:00:07.75)
============================================================
Elapsed Time:
============================================================
7.823987007141113
============================================================

============================================================
deploy returned successfully for:
============================================================
'FDO24261WAT'
============================================================

============================================================
Deployed or attempted to deploy the following:
============================================================
{'FDO242702QK', 'FDO24261WAT'}
============================================================

2022-06-13 14:05:16,425 | 38904 | MainThread | (interfaces_utilities.py:254) | deploy_to_fabric_using_switch_deploy | INFO | message: waiting for switches status
============================================================
waiting for switches status
============================================================

2022-06-13 14:05:16,426 | 38904 | MainThread | (dcnm_interfaces.py:1390) | wait_for_switches_status | INFO | message: Checking for switch status
-  (elapsed time waiting for switches status : 0:00:00.00)2022-06-13 14:05:16,427 | 38904 | MainThread | (dcnm_interfaces.py:1323) | get_switches_status | INFO | message: get swtiches status
|  (elapsed time waiting for switches status : 0:00:01.27)
============================================================
Elapsed Time:
============================================================
1.360194206237793
============================================================

============================================================
!!Successfully Deployed Config Changes to Switches!!
============================================================
['FDO24261WAT', 'FDO242702QK']
============================================================


========================================
========================================
FINISHED DEPLOYING. GO GET A BEER!
========================================
2022-06-13 14:05:17,912 | 38904 | MainThread | (dcnm_interfaces.py:893) | get_interfaces_nvpairs | INFO | message: get interfaces nvpairs
2022-06-13 14:05:17,916 | 38904 | MainThread | (dcnm_interfaces.py:848) | get_all_interfaces_nvpairs | INFO | message: get_all_interfaces_nvpairs: serial_number: FDO24261WAT
2022-06-13 14:05:18,434 | 38904 | MainThread | (dcnm_interfaces.py:848) | get_all_interfaces_nvpairs | INFO | message: get_all_interfaces_nvpairs: serial_number: FDO242702QK
============================================================
Verifying Interface Configurations
============================================================

============================================================
Successfully Verified All Interface Changes! Yay!
============================================================

========================================
FINISHED. GO GET PLASTERED!
========================================

Process finished with exit code 0

```