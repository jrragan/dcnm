import functools
import json
import logging
import re
import threading
from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass
from datetime import timedelta
from itertools import cycle
from pickle import dump, load
from pprint import pprint
from time import sleep, time, perf_counter
from typing import Union, Optional, Callable, Any

import pandas
from colorama import init, Back, Fore, Style
from pandas import read_excel
from yaspin import yaspin

from dcnm_connect import HttpApi

logger = logging.getLogger('dcnm_interfaces')

def _dbg(header: str, data=None):
    """ Output verbose data """

    print("=" * 60)
    print(header)
    print("=" * 60)
    if data:
        pprint(data)
        print("=" * 60)
    print()

def error_handler(msg):
    def decorator(func):
        @functools.wraps(func)
        def wrapper_decorator(*args, **kwargs):
            try:
                value = func(*args, **kwargs)
            except DCNMServerResponseError as e:
                logger.debug(e.args)
                e = eval(e.args[0])
                if isinstance(e['DATA'], (list, tuple)):
                    logger.critical("{} - {}".format(msg, e['DATA'][0]['message']))
                elif isinstance(e['DATA'], str):
                    logger.critical("{} - {}".format(msg, e['DATA']))
                logger.debug("{}".format(e))
                raise
            return value

        return wrapper_decorator

    return decorator

def _spin(msg, start, frames, _stop_spin):
    while not _stop_spin.is_set():
        frame = next(frames)
        sec, fsec = divmod(round(100 * (time() - start)), 100)
        frame += "  ({} : {}.{:02.0f})".format(msg, timedelta(seconds=sec), fsec)
        print('\r', frame, sep='', end='', flush=True)
        sleep(0.2)

def spinner(msg="Elapsed Time"):
    def decorator(func):
        @functools.wraps(func)
        def wrapper_decrorator(*args, **kwargs):
            _stop_spin = threading.Event()
            start = time()
            _spin_thread = threading.Thread(target=_spin, args=(msg, start, cycle(r'-\|/'), _stop_spin))
            _spin_thread.start()
            value = func(*args, **kwargs)
            stop = time()
            if _spin_thread:
                _stop_spin.set()
                _spin_thread.join()
            print()
            _dbg("Elapsed Time: ", stop - start)
            return value
        return wrapper_decrorator

    return decorator


class DCNMInterfacesParameterError(Exception):
    pass


class DCNMSwitchesPoliciesParameterError(Exception):
    pass


class DCNMParamaterError(Exception):
    pass


@dataclass
class info_from_policies:
    info: dict
    policyId: str


class DCNMSwitchStatusError(Exception):
    pass


class DCNMSwitchStatusParameterError(Exception):
    pass


class DCNMServerResponseError(Exception):
    pass


class DCNMPolicyDeployError(Exception):
    pass


class DcnmInterfaces(HttpApi):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.all_leaf_switches: dict[str, str] = {}
        self.all_notleaf_switches: dict[str, str] = {}
        self.all_interfaces: dict[tuple, dict] = {}
        self.all_interfaces_nvpairs: dict[tuple, dict] = {}
        # needed for fallback
        self.all_interfaces_nvpairs_prev: dict[tuple, dict] = {}
        self.all_switches_policies = defaultdict(list)
        self.all_switches_policies_prev: dict = {}
        self.fabrics: dict[str, dict] = {}

    @error_handler("ERROR getting switch serial numbers")
    def get_all_switches(self):
        """
        Pulls all switch serial numbers from DCNM inventory

        stores result in two attributes of the form {SN: fabric_name}
        all_leaf_switches
        all_notleaf_switches

        """

        if self.all_leaf_switches:
            self.all_leaf_switches.clear()
        if self.all_notleaf_switches:
            self.all_notleaf_switches.clear()

        path = '/inventory/switches'

        response = self._check_response(self.get(path))
        for switch in json.loads(response['MESSAGE']):
            if switch['switchRole'] == 'leaf':
                self.all_leaf_switches[switch['serialNumber']] = switch['fabricName']
            else:
                self.all_notleaf_switches[switch['serialNumber']] = switch['fabricName']

    @error_handler("ERROR:  get_switches_by_serial_number: getting switch roles for serial number")
    def get_switches_by_serial_number(self, serial_numbers: Optional[list] = None):
        if serial_numbers and not isinstance(serial_numbers, (list, tuple)):
            raise DCNMInterfacesParameterError('serial_numbers must be a list or a tuple')
        elif serial_numbers and isinstance(serial_numbers, (list, tuple)):
            if self.all_leaf_switches:
                self.all_leaf_switches.clear()
            if self.all_notleaf_switches:
                self.all_notleaf_switches.clear()

            path = '/control/switches/roles'
            params = {'serialNumber': ','.join(serial_numbers)}
            logger.info("get_switches_by_serial_number: for serial numbers: {}".format(serial_numbers))
            response = self._check_response(self.get(path, params=params))

            for switch in json.loads(response['MESSAGE']):
                fabricName = self.get_switch_fabric(switch['serialNumber'])
                if switch['role'] == 'leaf':
                    self.all_leaf_switches[switch['serialNumber']] = fabricName
                else:
                    self.all_notleaf_switches[switch['serialNumber']] = fabricName
        else:
            self.get_all_switches()

    @error_handler("ERROR: get_switches_policies: getting switch policies for serial number")
    def get_switches_policies(self, serial_numbers: Optional[Union[str, list]] = None, fabric: Optional[str] = None,
                              description: Optional[Union[str, list]] = None,
                              entityName: Optional[str] = None,
                              entityType: Optional[str] = None,
                              templateName: Optional[Union[str, list]] = None,
                              config: Optional[Union[str, list]] = None,
                              save_to_file: Optional[str] = None,
                              save_prev: bool = False):
        """

        :param serial_numbers: optional list of switch serial numbers
        :type serial_numbers: list or None
        :param fabric: optional regex str
        :type fabric: str or None
        :param description: optional regex str
        :type description:  str or None
        :param entityName: optional regex str
        :type entityName: str or None
        :param entityType: optional regex str
        :type entityType: str or None
        :param templateName: optional regex str
        :type templateName: str or None
        :param config: optional regex str
        :type config: str or None
        :return: filtered dictionary of switch policies
        :rtype: dict[serial_number: [list of policies]}

        filter out the wanted policies from all_leaf_switches_policies and all_notleaf_switches_policies and return
        a new dictionary of those policies

        {
        'FDO24261WAT': [
              {
                "id": 5416040,
                "policyId": "POLICY-5416040",
                "description": "",
                "serialNumber": "FDO24261WAT",
                "entityType": "SWITCH",
                "entityName": "SWITCH",
                "templateName": "tcam_config",
                "templateContentType": "TEMPLATE_CLI",
                "nvPairs": {
                  "TCAM_NAME": "ing-racl",
                  "TCAM_SIZE": "1792"
                },
                "generatedConfig": "hardware access-list tcam region ing-racl 1792\n\n\n",
                "autoGenerated": true,
                "deleted": false,
                "source": "",
                "priority": 5,
                "status": "NA",
                "statusOn": 1649994831875,
                "createdOn": 1649994831875,
                "modifiedOn": 1649994831875,
                "fabricName": "site-2",
                "resourcesLinked": ""
              },
              {
                "id": 5230630,
                "policyId": "POLICY-5230630",
                "serialNumber": "FDO24261WAT",
                "entityType": "SWITCH",
                "entityName": "SWITCH",
                "templateName": "nve_lb_id",
                "templateContentType": "PYTHON",
                "nvPairs": {
                  "PRIORITY": "10",
                  "POLICY_DESC": "",
                  "id": "1",
                  "POLICY_ID": "POLICY-5230630"
                },
                "generatedConfig": "",
                "autoGenerated": true,
                "deleted": false,
                "source": "",
                "priority": 10,
                "statusOn": 1649994831907,
                "modifiedOn": 1649994831907,
                "fabricName": "site-2",
                "resourcesLinked": ""
              },
              {
                "id": 5256540,
                "policyId": "POLICY-5256540",
                "serialNumber": "FDO24261WAT",
                "entityType": "SWITCH",
                "entityName": "SWITCH",
                "templateName": "switch_role_simulated",
                "templateContentType": "PYTHON",
                "nvPairs": {
                  "SWITCH_ROLE": "leaf",
                  "PRIORITY": "10",
                  "POLICY_DESC": "",
                  "POLICY_ID": "POLICY-5256540"
                },
                "generatedConfig": "",
                "autoGenerated": true,
                "deleted": false,
                "source": "",
                "priority": 10,
                "statusOn": 1649994841772,
                "modifiedOn": 1649994841772,
                "fabricName": "site-2",
                "resourcesLinked": ""
              },
              {
                "id": 5233000,
                "policyId": "POLICY-5233000",
                "serialNumber": "FDO24261WAT",
                "entityType": "SWITCH",
                "entityName": "SWITCH",
                "templateName": "bgp_lb_id",
                "templateContentType": "PYTHON",
                "nvPairs": {
                  "PRIORITY": "10",
                  "POLICY_DESC": "",
                  "id": "0",
                  "POLICY_ID": "POLICY-5233000"
                },
                "generatedConfig": "",
                "autoGenerated": true,
                "deleted": false,
                "source": "",
                "priority": 10,
                "statusOn": 1649994835880,
                "modifiedOn": 1649994835880,
                "fabricName": "site-2",
                "resourcesLinked": ""
              }
        ]
        }
        """
        if self.all_switches_policies and not save_prev:
            self.all_switches_policies.clear()
        elif self.all_switches_policies and save_prev:
            self.all_switches_policies_prev = deepcopy(self.all_switches_policies)
            self.all_switches_policies.clear()

        path = '/control/policies/switches'

        if serial_numbers and isinstance(serial_numbers, (list, tuple)):
            params = {'serialNumber': ','.join(serial_numbers)}
        elif serial_numbers and isinstance(serial_numbers, str):
            params = {'serialNumber': serial_numbers}
        elif not self.all_leaf_switches and not self.all_notleaf_switches:
            raise DCNMSwitchesPoliciesParameterError("Provide either a list of serial numbers or first run either"
                                                     "get_all_switches or get_switches_by_serial_numbers")
        else:
            params = {
                'serialNumber': ','.join(list(self.all_leaf_switches.keys()) + list(self.all_notleaf_switches.keys()))}

        logger.info("get_switches_policies: getting switch policies for serial number: {}".format(serial_numbers))
        response = self._check_response(self.get(path, params=params))

        for policy in json.loads(response['MESSAGE']):
            self.all_switches_policies[policy['serialNumber']].append(policy)

        if fabric:
            for sn, policy in deepcopy(self.all_switches_policies).items():
                if self.all_leaf_switches.get(sn, 'nothing_here') != fabric and \
                        self.all_notleaf_switches.get(sn, 'nothing_here') != fabric:
                    del self.all_switches_policies[sn]

        if isinstance(description, str): description = [description]
        if isinstance(templateName, str): templateName = [templateName]
        if isinstance(config, str): config = [config]
        try:
            for sn, policy_list in deepcopy(self.all_switches_policies).items():
                for policy in deepcopy(policy_list):
                    if description:
                        if not self._check_patterns(description, policy['description']):
                            self.all_switches_policies[sn].remove(policy)
                            continue

                    if entityName:
                        pattern = re.compile(entityName)
                        if not pattern.search(policy['entityName']):
                            self.all_switches_policies[sn].remove(policy)
                            continue

                    if entityType:
                        pattern = re.compile(entityType)
                        if not pattern.search(policy['entityType']):
                            self.all_switches_policies[sn].remove(policy)
                            continue

                    if templateName and isinstance(templateName, (list, tuple)):
                        if not self._check_patterns(templateName, policy['templateName']):
                            self.all_switches_policies[sn].remove(policy)
                            continue
                    elif templateName:
                        raise DCNMSwitchesPoliciesParameterError("templateName parameter must be a list or tuple")

                    if config and isinstance(config, (list, tuple)):
                        if not self._check_patterns(config, policy['generatedConfig']):
                            self.all_switches_policies[sn].remove(policy)
                            continue
                    elif config:
                        raise DCNMSwitchesPoliciesParameterError("config parameter must be a list or tuple")
        except DCNMParamaterError:
            raise DCNMSwitchesPoliciesParameterError("description must be a string or a list of strings\n"
                                                     "templateName must be a string or a list of strings\n"
                                                     "config must be a string or a list of strings")
        except DCNMSwitchesPoliciesParameterError:
            raise

        # remove empty keys
        for sn, policies in deepcopy(self.all_switches_policies).items():
            if not self.all_switches_policies[sn]:
                del self.all_switches_policies[sn]

        if save_to_file is not None:
            with open(save_to_file, 'w') as f:
                f.write(str(self.all_switches_policies))

    def delete_switch_policies(self, policyId: Union[str, list]):
        if isinstance(policyId, str):
            path: str = f'/control/policies/{policyId}'
        elif isinstance(policyId, (list, tuple)):
            path: str = f'/control/policies/policyIds?policyIds={",".join(policyId)}'
        info = self._check_action_response(self.delete(path, errors=[
            (500, "Invalid payload or any other internal server error (e.g. policy does not exist)")]),
                                           "delete_switch_policies", "DELETE OF", policyId)
        return info

    @error_handler("ERROR: get_all_interfaces_detail: getting interface details for serial number")
    def get_all_interfaces_detail(self, serial_number: Optional[str] = None, interface: Optional[str] = None):
        """

        :param self:
        :type self:
        :param serial_number: optional filter
        :type serial_number: str
        :param interface: optional filter
        :type interface: str
        :return: dictionary of the form with entries for all switches
        {(interface['ifName'], interface['serialNo'],) = {
                'interface_name': interface['ifName'], 'interface_type': interface['ifType'],
                'fabric': interface['fabricName'], 'switch_name': interface['sysName'],
                'switch_serial': interface['serialNo'],
                'entity_id': interface['entityId'],
                'interface_policy': interface['underlayPoliciesStr'],
                'isPhysical': interface['isPhysical'],
                'interface_desc': interface['description']}
                }

        :rtype: dict[tuple, dict]

        pulls a list of all interfaces from dcnm of the following form. returns a dictionary with a subset of
        values

        [
        {
            "name": null,
            "domainID": 0,
            "wwn": null,
            "membership": null,
            "ports": 0,
            "model": "N9K-C9336C-FX2",
            "version": null,
            "upTime": 35784632,
            "ipAddress": "10.0.7.32",
            "mgmtAddress": null,
            "vendor": "Cisco",
            "displayHdrs": [
                "Name",
                "IP Address",
                "Fabric",
                "WWN",
                "FC Ports",
                "Vendor",
                "Model",
                "Release",
                "UpTime"
            ],
            "displayValues": [
                "bl4001",
                "10.0.7.32",
                "site-2",
                "FDO22423DNC",
                "36",
                "Cisco",
                "N9K-C9336C-FX2",
                "9.3(9)",
                "4 days, 03:24:06"
            ],
            "colDBId": 0,
            "fid": 4,
            "isLan": false,
            "isNonNexus": false,
            "is_smlic_enabled": false,
            "present": true,
            "licenseViolation": false,
            "managable": true,
            "mds": false,
            "connUnitStatus": 0,
            "standbySupState": 0,
            "activeSupSlot": 0,
            "unmanagableCause": "",
            "lastScanTime": 1647617239427,
            "fabricName": "site-2",
            "modelType": 0,
            "logicalName": "bl4001",
            "switchDbID": 5165810,
            "uid": 0,
            "release": "9.3(9)",
            "location": "",
            "contact": "",
            "upTimeStr": "4 days, 03:24:06",
            "upTimeNumber": 0,
            "network": "LAN",
            "nonMdsModel": "N9K-C9336C-FX2",
            "numberOfPorts": 36,
            "availPorts": 0,
            "usedPorts": 0,
            "vsanWwn": null,
            "vsanWwnName": null,
            "swWwn": null,
            "swWwnName": "FDO22423DNC",
            "serialNumber": "FDO22423DNC",
            "domain": null,
            "principal": null,
            "status": "ok",
            "index": 1,
            "licenseDetail": null,
            "isPmCollect": false,
            "sanAnalyticsCapable": false,
            "vdcId": -1,
            "vdcName": "",
            "vdcMac": null,
            "fcoeEnabled": false,
            "cpuUsage": 4,
            "memoryUsage": 28,
            "scope": null,
            "fex": false,
            "health": 98,
            "npvEnabled": false,
            "linkName": null,
            "username": "y9fzO6teTGs8QpyOWpSHn4d7sMNB/My3LI9zRSiTQZm3hQ==",
            "primaryIP": null,
            "primarySwitchDbID": 0,
            "secondaryIP": "",
            "secondarySwitchDbID": 0,
            "switchRole": "border",
            "mode": "Normal",
            "hostName": "bl4001.wellsfargo.svs.cisco.com",
            "ipDomain": "wellsfargo.svs.cisco.com",
            "modules": null,
            "fexMap": {},
            "isVpcConfigured": false,
            "vpcDomain": 0,
            "role": null,
            "peer": null,
            "peerSerialNumber": null,
            "peerSwitchDbId": 0,
            "peerlinkState": null,
            "keepAliveState": null,
            "consistencyState": false,
            "sendIntf": null,
            "recvIntf": null
        }
        ]
        """

        if self.all_interfaces:
            self.all_interfaces.clear()

        path = '/globalInterface'

        params = {'serialNumber': serial_number, 'ifName': interface}

        logger.info("get_all_interfaces_detail: getting interface details for serial number: {}".format(serial_number))
        response = self._check_response(self.get(path, params=params))

        for interface in json.loads(response['MESSAGE']):
            # print(interface)
            self.all_interfaces[(interface['ifName'], interface['serialNo'],)] = {
                'interface_name': interface['ifName'], 'interface_type': interface['ifType'],
                'fabric': interface['fabricName'], 'switch_name': interface['sysName'],
                'switch_serial': interface['serialNo'],
                'entity_id': interface['entityId'],
                'interface_policy': interface['underlayPoliciesStr'],
                'isPhysical': interface['isPhysical'],
                'interface_desc': interface['description']}

    @error_handler("ERROR: get_all_interfaces_nvpairs: getting interface details and nvpairs for serial number")
    def get_all_interfaces_nvpairs(self, serial_number: Optional[str] = None,
                                   interface: Optional[str] = None) -> dict[tuple, dict]:
        """

        :param self:
        :type self:
        :param interface: optional filter, ifName
        :type interface: str

        pulls all interface policy information from dcnm. can optionally filter by serial number or ifName
        saves to a dictionary of the following form with the attribute name all_interfaces_nvpairs

        {
        ('Ethernet1/38', 'FDO242600CW'): {'interfaces': [{'ifName': 'Ethernet1/38',
                                               'nvPairs': {'ADMIN_STATE': 'true',
                                                           'ALLOWED_VLANS': 'none',
                                                           'BPDUGUARD_ENABLED': 'no',
                                                           'CONF': 'no cdp '
                                                                   'enable',
                                                           'DESC': '',
                                                           'GF': '',
                                                           'INTF_NAME': 'Ethernet1/38',
                                                           'MTU': 'jumbo',
                                                           'POLICY_DESC': '',
                                                           'POLICY_ID': 'POLICY-5247430',
                                                           'PORTTYPE_FAST_ENABLED': 'true',
                                                           'PRIORITY': '450',
                                                           'PTP': 'false',
                                                           'SPEED': 'Auto'},
                                               'serialNumber': 'FDO242600CW'}],
                               'policy': 'int_trunk_host_11_1'},
        ('Ethernet1/38', 'FDO24261WAT'): {'interfaces': [{'ifName': 'Ethernet1/38',
                                               'nvPairs': {'ADMIN_STATE': 'true',
                                                           'ALLOWED_VLANS': 'none',
                                                           'BPDUGUARD_ENABLED': 'no',
                                                           'CONF': 'no cdp '
                                                                   'enable',
                                                           'DESC': '',
                                                           'GF': '',
                                                           'INTF_NAME': 'Ethernet1/38',
                                                           'MTU': 'jumbo',
                                                           'POLICY_DESC': '',
                                                           'POLICY_ID': 'POLICY-5258530',
                                                           'PORTTYPE_FAST_ENABLED': 'true',
                                                           'PRIORITY': '450',
                                                           'PTP': 'false',
                                                           'SPEED': 'Auto'},
                                               'serialNumber': 'FDO24261WAT'}],
                               'policy': 'int_trunk_host_11_1'}
                               }


        """

        # skip_save is a boolean. if true do not save interface information to the instance variable, instead return
        # the requested interface information dictionary
        # for use with get_interfaces_nvpairs method

        local_all_interfaces_nvpairs: dict[tuple, dict] = {}

        path = '/interface'

        params = {'serialNumber': serial_number, 'ifName': interface}
        logger.info("get_all_interfaces_nvpairs: serial_number: {}".format(serial_number))
        response = self._check_response(self.get(path, params=params))
        logger.debug("get_all_interfaces_nvpairs: response: {}".format(response))
        for policy in json.loads(response['MESSAGE']):
            for interface in policy['interfaces']:
                # print(interface)
                local_all_interfaces_nvpairs[(interface['ifName'], interface['serialNumber'])] = {
                    'policy': policy['policy'], 'interfaces': [
                        interface
                    ]
                }

        return local_all_interfaces_nvpairs

    def get_interfaces_nvpairs(self, serial_numbers: Optional[Union[list, tuple]] = None,
                               interface: Optional[str] = None,
                               policy: Optional[Union[str, list[str]]] = None,
                               config: Optional[Union[str, list[str]]] = None,
                               non_config: Optional[Union[str, list[str]]] = None,
                               nv_pairs: Optional[list[tuple[str, str]]] = None,
                               save_to_file: Optional[str] = None,
                               save_prev: bool = False):
        """

        :param nv_pairs: optional list of tuples of form [(nvpair key, regex to match value)]
        :type nv_pairs: list or tuple of tuples
        :param serial_numbers: required list or tuple of switch serial numbers
        :type serial_numbers: list or tuple
        :param save_to_file: optional parameter, if None do not save, if str use as filename to save to
        :type save_to_file: None or str
        :param save_prev: if True and  attribute all_interfaces_nvpairs exists,
        copy to attribute all_interfaces_nvpairs_prev
        :type save_prev: bool

        pulls all interface policy information from dcnm for a list of serial numbers.
        saves to a dictionary of the following form with the attribute name all_interfaces_nvpairs
        """

        if self.all_interfaces_nvpairs and not save_prev:
            self.all_interfaces_nvpairs.clear()
        elif self.all_interfaces_nvpairs and save_prev:
            self.all_interfaces_nvpairs_prev = deepcopy(self.all_interfaces_nvpairs)
            self.all_interfaces_nvpairs.clear()

        if serial_numbers and isinstance(serial_numbers, str):
            serial_numbers = [serial_numbers]

        if serial_numbers and isinstance(serial_numbers, (list, tuple)):

            for sn in serial_numbers:
                interfaces = self.get_all_interfaces_nvpairs(serial_number=sn, interface=interface)
                self.all_interfaces_nvpairs.update((interfaces))
        else:
            self.all_interfaces_nvpairs = self.get_all_interfaces_nvpairs(interface=interface)

        if isinstance(policy, str): policy = [policy]
        if isinstance(config, str): config = [config]
        if isinstance(non_config, str): non_config = [non_config]
        if policy or config or non_config or nv_pairs:
            try:
                self.all_interfaces_nvpairs = DcnmInterfaces.get_filtered_interfaces_nvpairs(
                    self.all_interfaces_nvpairs,
                    policy=policy, config=config,
                    non_config=non_config,
                    nv_pairs=nv_pairs)
                # logger.debug("get_interfaces_nvpairs: {}".format(self.all_interfaces_nvpairs))
            except DCNMParamaterError:
                logger.critical("ERROR: get_interfaces_nvpairs: serial_numbers must be a string or a list of strings\n"
                                "policy must be a string or a list of strings\n"
                                "nv_pairs must be a list of tuples of two strings\n"
                                "config must be a string or a list of strings")
                raise DCNMInterfacesParameterError("serial_numbers must be a string or a list of strings\n"
                                                   "policy must be a string or a list of strings\n"
                                                   "nv_pairs must be a list of tuples of two strings\n"
                                                   "config must be a string or a list of strings")

        if save_to_file is not None:
            with open(save_to_file, 'w') as f:
                f.write(str(self.all_interfaces_nvpairs))

    @spinner()
    def deploy_switch_config(self, serial_number: str, fabric: Optional[str] = None) -> bool:
        """

        :param serial_number: required, serial number of switch
        :type serial_number: str
        :param fabric: optional, fabric name
        :type fabric: str
        :return: True if successful, False otherwise
        :rtype: bool

        Deploy configuration of switch specified by the serial number. If fabric is not provided the script will attempt
        to discover it. Returns True if successful, False otherwise.
        """

        if fabric is None:
            fabric = self.all_leaf_switches.get(serial_number) or self.all_notleaf_switches.get(serial_number)
            if not fabric:
                fabric = self.get_switch_fabric(serial_number)
        path: str = f'/control/fabrics/{fabric}/config-deploy/{serial_number}'
        info = self._check_action_response(self.post(path, errors=[(400, "Invalid value supplied"),
                                                                   (500,
                                                                    "Invalid payload or any other internal server error")]),
                                           "desploy_switch_config", "CONFIG SAVE OF {} switch".format(fabric),
                                           serial_number)
        return info

    def put_interface(self, interface: tuple, details: dict) -> bool:
        """

        :param self:
        :type self:
        :param interface: should be form of (ifName, switch_serial_number)
        :type interface: tuple
        :param details: should be of form
        {'interfaces': [{'ifName': 'mgmt0',
                                        'nvPairs': {'ADMIN_STATE': 'true',
                                                    'CDP_ENABLE': 'false',
                                                    'CONF': '  ip address '
                                                            '10.0.7.11/24\r',
                                                    'DESC': '',
                                                    'INTF_NAME': 'mgmt0',
                                                    'POLICY_DESC': '',
                                                    'POLICY_ID': 'POLICY-5188410',
                                                    'PRIORITY': '900'},
                                        'serialNumber': 'FDO243901FD'}],
                        'policy': 'int_mgmt_11_1'}

                        or

                        {'interfaces': [{'ifName': 'Ethernet1/38',
                                               'nvPairs': {'ADMIN_STATE': 'true',
                                                           'ALLOWED_VLANS': 'none',
                                                           'BPDUGUARD_ENABLED': 'no',
                                                           'CONF': 'no cdp '
                                                                   'enable',
                                                           'DESC': '',
                                                           'GF': '',
                                                           'INTF_NAME': 'Ethernet1/38',
                                                           'MTU': 'jumbo',
                                                           'POLICY_DESC': '',
                                                           'POLICY_ID': 'POLICY-5247430',
                                                           'PORTTYPE_FAST_ENABLED': 'true',
                                                           'PRIORITY': '450',
                                                           'PTP': 'false',
                                                           'SPEED': 'Auto'},
                                               'serialNumber': 'FDO242600CW'}],
                               'policy': 'int_trunk_host_11_1'}
        :type details: dict
        :return: True if successful else False
        :rtype: bool

        Changes interface configuration on DCNM. This does not create a new interface.
        """
        path: str = '/interface'
        info = self._check_action_response(self.put(path, data=details, errors=[
            (500, "Invalid payload or any other internal server error")]), "put_interface",
                                           "CREATION OF", interface)
        return info

    def put_interface_changes(self, interfaces_will_change: dict[tuple, dict]) -> tuple[set, set]:
        """

        :param self:
        :type self:
        :param interfaces_will_change: this is of form

        {
        ('Ethernet1/38', 'FDO242600CW'): {'interfaces': [{'ifName': 'Ethernet1/38',
                                               'nvPairs': {'ADMIN_STATE': 'true',
                                                           'ALLOWED_VLANS': 'none',
                                                           'BPDUGUARD_ENABLED': 'no',
                                                           'CONF': 'no cdp '
                                                                   'enable',
                                                           'DESC': '',
                                                           'GF': '',
                                                           'INTF_NAME': 'Ethernet1/38',
                                                           'MTU': 'jumbo',
                                                           'POLICY_DESC': '',
                                                           'POLICY_ID': 'POLICY-5247430',
                                                           'PORTTYPE_FAST_ENABLED': 'true',
                                                           'PRIORITY': '450',
                                                           'PTP': 'false',
                                                           'SPEED': 'Auto'},
                                               'serialNumber': 'FDO242600CW'}],
                               'policy': 'int_trunk_host_11_1'},
            ('Ethernet1/38', 'FDO24261WAT'): {'interfaces': [{'ifName': 'Ethernet1/38',
                                               'nvPairs': {'ADMIN_STATE': 'true',
                                                           'ALLOWED_VLANS': 'none',
                                                           'BPDUGUARD_ENABLED': 'no',
                                                           'CONF': 'no cdp '
                                                                   'enable',
                                                           'DESC': '',
                                                           'GF': '',
                                                           'INTF_NAME': 'Ethernet1/38',
                                                           'MTU': 'jumbo',
                                                           'POLICY_DESC': '',
                                                           'POLICY_ID': 'POLICY-5258530',
                                                           'PORTTYPE_FAST_ENABLED': 'true',
                                                           'PRIORITY': '450',
                                                           'PTP': 'false',
                                                           'SPEED': 'Auto'},
                                               'serialNumber': 'FDO24261WAT'}],
                               'policy': 'int_trunk_host_11_1'}
                               }
        :type interfaces_will_change: dict, the key is a tuple, the value is a dictionary
        :return: two sets, one of successful configurations, one of failed configurations
        :rtype: (set, set, )

        iterates through a dictionary of interfaces to change and calls method to push changes to DCNM
        """
        interfaces_will_change_local: dict[tuple, dict] = deepcopy(interfaces_will_change)
        failed: set = set()
        success: set = set()
        for interface, details in interfaces_will_change_local.items():
            result = self.put_interface(interface, details)
            if not result:
                logger.critical(
                    "put_interface_changes:  Failed putting new interface configuration to DCNM for {}".format(
                        interface))
                logger.critical(details)
                failed.add(interface)
            elif result:
                logger.info("put_interface_changes:  {} successfully changed. Yay.".format(interface))
                logger.debug(details)
                success.add(interface)
            else:
                logger.critical("ERROR: put_interface_changes:  Don't know what happened: {}".format(result))
                logger.critical("ERROR: put_interface_changes:  {} : {}".format(interface, details))
                failed.add(interface)
        logger.debug("put_interface_changes:  Successfully configured {}".format(success))
        if failed:
            logger.critical("ERROR: put_interface_changes:  Failed configuring {}".format(failed))
        else:
            logger.debug("put_interface_changes: No Failures!")
        return success, failed

    @spinner()
    def deploy_interfaces(self, payload: Union[list, dict], deploy_timeout: int=300) -> Optional[bool]:
        """

        :param self:
        :type self:
        :param payload:
        list of form
        [
          {
            "serialNumber": "SN1",
            "ifName": "Ethernet1/5"
          },
          { "serialNumber": "SN2",
            "ifName": "Ethernet1/6"
            }
        ]

        alternatively, payload can be a single dictionary
        {
            "serialNumber": "SN1",
            "ifName": "Ethernet1/5"
          }

        :type payload: list or dictionary
        :return: True if successful, False otherwise
        :rtype: bool

        Provide a list of interfaces to deploy. Returns True if successful.
        """
        path = '/globalInterface/deploy'
        if isinstance(payload, dict):
            payload = [payload]
        temp_timers = self.timeout
        self.timeout = deploy_timeout
        logger.debug("deploy_interfaces: deploying interfaces {}".format(payload))
        info = self._check_action_response(self.post(path, data=payload), "deploy_interfaces",
                                           "DEPLOY OF", payload)
        self.timeout = temp_timers
        return info

    @spinner()
    def deploy_fabric_config(self, fabric: str, deploy_timeout: int=300) -> Optional[bool]:
        """

        :param fabric: name of fabric
        :type fabric: str
        :return: True if successful, False otherwise
        :rtype: bool
        """
        path = f'/control/fabrics/{fabric}/config-deploy'
        temp_timers = self.timeout
        self.timeout = deploy_timeout
        logger.debug("deploying config fabric {}".format(fabric))
        info = self._check_action_response(self.post(path,
                                                     errors=[
                                                         (500,
                                                          "Fabric name is invalid or config deployment failed due to internal server error")]),
                                           "deploy_fabric_config", "DEPLOY OF FABRIC", fabric)
        self.timeout = temp_timers
        return info

    @spinner()
    def deploy_policies(self, policies: list, deploy_timeout: int=300) -> Optional[bool]:
        """

        :param policies: list of policies to deploy, Eg :- ["POLICY-1200","POLICY-1220"]
        :type fabric: list
        :return: True if successful, False otherwise
        :rtype: bool
        """
        path = '/control/policies/deploy'
        temp_timers = self.timeout
        self.timeout = deploy_timeout
        if isinstance(policies, tuple):
            policies = list(policies)
        elif not isinstance(policies, list):
            raise DCNMPolicyDeployError("must provide a list of policy ids")
        logger.info("deploying policies {}".format(policies))
        info = self._check_action_response(self.post(path, data=policies), "deploy_policies", "DEPLOY OF POLICIES",
                                           policies)
        self.timeout = temp_timers
        return info

    @error_handler("ERROR: get_switch_fabric: failed getting switch fabric for serial number")
    def get_switch_fabric(self, serial_number: str) -> str:
        """

        :param serial_number: serial number of switch
        :type serial_number: str
        :return: fabric name
        :rtype: str

        provide serial number of switch, returns name of fabric to which switch belongs
        """
        path = f'/control/switches/{serial_number}/fabric-name'
        logger.debug("get_switch_fabric: getting fabric for switch {}".format(serial_number))
        response = self._check_response(self.get(path, errors=[(500, "Invalid switch or Other exception")]))
        return json.loads(response['MESSAGE'])['fabricName']

    @error_handler("ERROR: get_fabric_details: failed getting fabric details")
    def get_fabric_details(self, fabric: str):
        """
        Provide the name of a fabric, details are stored in object variable fabrics. API call returns
        a dictionary similar to the below example.

        {
          "id": 4,
          "fabricId": "FABRIC-4",
          "fabricName": "site-2",
          "fabricType": "Switch_Fabric",
          "fabricTypeFriendly": "Switch Fabric",
          "fabricTechnology": "VXLANFabric",
          "fabricTechnologyFriendly": "VXLAN Fabric",
          "provisionMode": "DCNMTopDown",
          "deviceType": "n9k",
          "replicationMode": "Multicast",
          "asn": "65504",
          "siteId": "65504",
          "templateName": "Easy_Fabric_11_1",
          "nvPairs": {
            "TE_INTERNET_VRF": "",
            "MSO_SITE_ID": "",
            "PHANTOM_RP_LB_ID1": "",
            "PHANTOM_RP_LB_ID2": "",
            "PHANTOM_RP_LB_ID3": "",
            "IBGP_PEER_TEMPLATE": "",
            "PHANTOM_RP_LB_ID4": "",
            "abstract_ospf": "base_ospf",
            "FEATURE_PTP": "false",
            "L3_PARTITION_ID_RANGE": "50000-59000",
            "DHCP_START_INTERNAL": "",
            "SSPINE_COUNT": "0",
            "ADVERTISE_PIP_BGP": "true",
            "BFD_PIM_ENABLE": "true",
            "FABRIC_VPC_QOS_POLICY_NAME": "spine_qos_for_fabric_vpc_peering",
            "DHCP_END": "",
            "UNDERLAY_IS_V6": "false",
            "FABRIC_VPC_DOMAIN_ID": "1",
            "FABRIC_MTU_PREV": "9216",
            "BFD_ISIS_ENABLE": "false",
            "HD_TIME": "180",
            "OSPF_AUTH_ENABLE": "true",
            "LOOPBACK1_IPV6_RANGE": "",
            "ROUTER_ID_RANGE": "",
            "ENABLE_MACSEC": "false",
            "MSO_CONNECTIVITY_DEPLOYED": "",
            "DEAFULT_QUEUING_POLICY_OTHER": "queuing_policy_default_other",
            "MACSEC_REPORT_TIMER": "",
            "PREMSO_PARENT_FABRIC": "",
            "PTP_DOMAIN_ID": "",
            "USE_LINK_LOCAL": "true",
            "AUTO_SYMMETRIC_VRF_LITE": "false",
            "ENABLE_PBR": "false",
            "BSTRAP_ONLY_IMG_CMPL": "false",
            "DCI_SUBNET_TARGET_MASK": "31",
            "VPC_PEER_LINK_PO": "500",
            "TE_DNS_SERVER_IP_LIST": "",
            "ISIS_AUTH_ENABLE": "false",
            "REPLICATION_MODE": "Multicast",
            "ANYCAST_RP_IP_RANGE": "10.254.254.0/31",
            "VPC_ENABLE_IPv6_ND_SYNC": "true",
            "TCAM_ALLOCATION": "true",
            "abstract_isis_interface": "isis_interface",
            "SERVICE_NETWORK_VLAN_RANGE": "3000-3199",
            "MACSEC_ALGORITHM": "",
            "ISIS_LEVEL": "level-2",
            "SUBNET_TARGET_MASK": "31",
            "abstract_anycast_rp": "anycast_rp",
            "DEAFULT_QUEUING_POLICY_R_SERIES": "queuing_policy_default_r_series",
            "TE_DNS_DOMAIN": "",
            "BROWNFIELD_NETWORK_NAME_FORMAT": "Auto_Net_VNI$$VNI$$_VLAN$$VLAN_ID$$",
            "temp_vpc_peer_link": "int_vpc_peer_link_po_11_1",
            "ENABLE_FABRIC_VPC_DOMAIN_ID": "true",
            "IBGP_PEER_TEMPLATE_LEAF": "",
            "DCI_SUBNET_RANGE": "10.33.0.0/16",
            "ENABLE_NXAPI": "true",
            "VRF_LITE_AUTOCONFIG": "Back2Back&ToExternal",
            "MGMT_GW_INTERNAL": "",
            "GRFIELD_DEBUG_FLAG": "Disable",
            "VRF_VLAN_RANGE": "2000-2299",
            "ISIS_AUTH_KEYCHAIN_NAME": "",
            "SSPINE_ADD_DEL_DEBUG_FLAG": "Disable",
            "abstract_bgp_neighbor": "evpn_bgp_rr_neighbor",
            "OSPF_AUTH_KEY_ID": "127",
            "PIM_HELLO_AUTH_ENABLE": "false",
            "abstract_feature_leaf": "base_feature_leaf_upg",
            "BFD_AUTH_ENABLE": "false",
            "BGP_LB_ID": "0",
            "LOOPBACK1_IP_RANGE": "10.23.0.0/22",
            "AAA_SERVER_CONF": "feature tacacs+\ntacacs-server timeout 3\ntacacs-server host 172.31.7.251 key 7 \"F1whg.321\" timeout 10\ntacacs-server host 172.31.7.250 key 7 \"F1whg.321\" timeout 10\ntacacs-server host 172.31.7.248 key 7 \"F1whg.321\" timeout 10\ntacacs-server host 2001:172:31:7::251 key 7 \"F1whg.321\" timeout 10\ntacacs-server host 2001:172:31:7::250 key 7 \"F1whg.321\" timeout 10\ntacacs-server host 2001:172:31:7::248 key 7 \"F1whg.321\" timeout 10\naaa group server tacacs+ wells\n    server 172.31.7.251\n    server 2001:172:31:7::251\n    server 172.31.7.250\n    server 2001:172:31:7::250\n    server 172.31.7.248\n    server 2001:172:31:7::248\n    deadtime 3\n    use-vrf management\naaa authentication login default group wells \naaa authentication login console local \naaa authorization config-commands default group wells local \naaa authorization commands default group wells local \naaa accounting default group wells\ntacacs-server directed-request\nsystem login block-for 45 attempts 3 within 60",
            "VPC_PEER_KEEP_ALIVE_OPTION": "management",
            "enableRealTimeBackup": "true",
            "TE_PROXY_ENABLE": "",
            "V6_SUBNET_TARGET_MASK": "126",
            "STRICT_CC_MODE": "true",
            "VPC_PEER_LINK_VLAN": "3600",
            "abstract_trunk_host": "int_trunk_host_11_1",
            "BGP_AUTH_ENABLE": "true",
            "RP_MODE": "asm",
            "enableScheduledBackup": "true",
            "BFD_OSPF_ENABLE": "true",
            "abstract_ospf_interface": "ospf_interface_11_1",
            "MACSEC_FALLBACK_ALGORITHM": "",
            "TE_ENABLE": "false",
            "LOOPBACK0_IP_RANGE": "10.22.0.0/22",
            "ENABLE_AAA": "true",
            "DEPLOYMENT_FREEZE": "false",
            "L2_HOST_INTF_MTU_PREV": "9216",
            "NTP_SERVER_IP_LIST": "",
            "ENABLE_AGENT": "false",
            "MACSEC_FALLBACK_KEY_STRING": "",
            "FF": "Easy_Fabric",
            "FABRIC_TYPE": "Switch_Fabric",
            "SPINE_COUNT": "0",
            "abstract_extra_config_bootstrap": "extra_config_bootstrap_11_1",
            "MPLS_LOOPBACK_IP_RANGE": "",
            "LINK_STATE_ROUTING_TAG_PREV": "UNDERLAY",
            "DHCP_ENABLE": "false",
            "BFD_AUTH_KEY_ID": "",
            "MSO_SITE_GROUP_NAME": "",
            "MGMT_PREFIX_INTERNAL": "",
            "DHCP_IPV6_ENABLE_INTERNAL": "",
            "BGP_AUTH_KEY_TYPE": "3",
            "SITE_ID": "65504",
            "temp_anycast_gateway": "anycast_gateway",
            "BRFIELD_DEBUG_FLAG": "Disable",
            "BGP_AS": "65504",
            "BOOTSTRAP_MULTISUBNET": "",
            "ISIS_P2P_ENABLE": "",
            "ENABLE_NGOAM": "true",
            "CDP_ENABLE": "false",
            "TE_PROXY_IP": "",
            "PTP_LB_ID": "",
            "DHCP_IPV6_ENABLE": "DHCPv4",
            "MACSEC_KEY_STRING": "",
            "OSPF_AUTH_KEY": "a667d47acc18ea6b",
            "ENABLE_FABRIC_VPC_DOMAIN_ID_PREV": "true",
            "EXTRA_CONF_LEAF": "snmp-server community wellsrw group network-admin\nsnmp-server community WellsRO group network-operator\nsnmp-server community WellsRW group network-admin\nsnmp-server community wellsro group network-operator\nsnmp-server community WellsRO use-ipv4acl SSH-VTY-RESTRICT use-ipv6acl SSH-VTY-IPv6\nsnmp-server community WellsRW use-ipv4acl SSH-VTY-RESTRICT use-ipv6acl SSH-VTY-IPv6\nsnmp-server community wellsro use-ipv4acl SSH-VTY-RESTRICT use-ipv6acl SSH-VTY-IPv6\nsnmp-server community wellsrw use-ipv4acl SSH-VTY-RESTRICT use-ipv6acl SSH-VTY-IPv6\nlogging timestamp milliseconds\nline vty\n  exec-timeout 240\n  access-class SSH-VTY-RESTRICT in\n  ipv6 access-class SSH-VTY-IPv6 in",
            "vrf_extension_template": "Default_VRF_Extension_Universal",
            "DHCP_START": "",
            "ENABLE_TRM": "false",
            "FEATURE_PTP_INTERNAL": "false",
            "ENABLE_NXAPI_HTTP": "false",
            "MPLS_LB_ID": "",
            "abstract_isis": "base_isis_level2",
            "FABRIC_VPC_DOMAIN_ID_PREV": "1",
            "ROUTE_MAP_SEQUENCE_NUMBER_RANGE": "1-65534",
            "NETWORK_VLAN_RANGE": "2300-2999",
            "STATIC_UNDERLAY_IP_ALLOC": "false",
            "MGMT_V6PREFIX_INTERNAL": "",
            "MPLS_HANDOFF": "false",
            "scheduledTime": "01:30",
            "TE_NTP_SERVER_IP_LIST": "",
            "ANYCAST_LB_ID": "",
            "MACSEC_CIPHER_SUITE": "",
            "MSO_CONTROLER_ID": "",
            "POWER_REDUNDANCY_MODE": "combined",
            "BFD_ENABLE": "true",
            "abstract_extra_config_leaf": "extra_config_leaf",
            "ANYCAST_GW_MAC": "4000.0000.00aa",
            "abstract_dhcp": "base_dhcp",
            "EXTRA_CONF_SPINE": "snmp-server community wellsrw group network-admin\nsnmp-server community WellsRO group network-operator\nsnmp-server community WellsRW group network-admin\nsnmp-server community wellsro group network-operator\nsnmp-server community WellsRO use-ipv4acl SSH-VTY-RESTRICT use-ipv6acl SSH-VTY-IPv6\nsnmp-server community WellsRW use-ipv4acl SSH-VTY-RESTRICT use-ipv6acl SSH-VTY-IPv6\nsnmp-server community wellsro use-ipv4acl SSH-VTY-RESTRICT use-ipv6acl SSH-VTY-IPv6\nsnmp-server community wellsrw use-ipv4acl SSH-VTY-RESTRICT use-ipv6acl SSH-VTY-IPv6\nlogging timestamp milliseconds\nline vty\n  exec-timeout 240\n  access-class SSH-VTY-RESTRICT in\n  ipv6 access-class SSH-VTY-IPv6 in",
            "NTP_SERVER_VRF": "",
            "LINK_STATE_ROUTING_TAG": "UNDERLAY",
            "RP_LB_ID": "254",
            "BOOTSTRAP_CONF": "ntp server 172.31.7.53 prefer use-vrf management key 1\nntp server 2001:172:31:7::53 prefer use-vrf management key 1\nntp source-interface mgmt0\nntp authenticate\nntp authentication-key 1 md5 fewhg 7\nntp trusted-key 1\nno hardware access-list update atomic\nssh key rsa 2048 force\nip domain-name wellsfargo.svs.cisco.com",
            "LINK_STATE_ROUTING": "ospf",
            "ISIS_AUTH_KEY": "",
            "network_extension_template": "Default_Network_Extension_Universal",
            "DNS_SERVER_IP_LIST": "172.31.7.55,172.31.7.51,2001:172:31:7::55,2001:172:31:7::51",
            "ENABLE_EVPN": "true",
            "abstract_multicast": "base_multicast_11_1",
            "VPC_DELAY_RESTORE_TIME": "60",
            "BFD_AUTH_KEY": "",
            "AGENT_INTF": "eth0",
            "FABRIC_MTU": "9216",
            "L3VNI_MCAST_GROUP": "",
            "VPC_DOMAIN_ID_RANGE": "1-1000",
            "BFD_IBGP_ENABLE": "true",
            "VPC_AUTO_RECOVERY_TIME": "360",
            "DNS_SERVER_VRF": "management",
            "SYSLOG_SEV": "5",
            "abstract_loopback_interface": "int_fabric_loopback_11_1",
            "SYSLOG_SERVER_VRF": "management",
            "EXTRA_CONF_INTRA_LINKS": "service-policy type qos input QOS-IN no-stats",
            "SNMP_SERVER_HOST_TRAP": "true",
            "PIM_HELLO_AUTH_KEY": "",
            "abstract_extra_config_spine": "extra_config_spine",
            "TE_ACCOUNT_TOKEN": "",
            "temp_vpc_domain_mgmt": "vpc_domain_mgmt",
            "V6_SUBNET_RANGE": "",
            "SUBINTERFACE_RANGE": "2-511",
            "BGP_AUTH_KEY": "a667d47acc18ea6b",
            "abstract_routed_host": "int_routed_host_11_1",
            "default_network": "Default_Network_Universal",
            "ISIS_AUTH_KEYCHAIN_KEY_ID": "",
            "MGMT_V6PREFIX": "",
            "abstract_feature_spine": "base_feature_spine_upg",
            "ENABLE_DEFAULT_QUEUING_POLICY": "true",
            "RP_COUNT": "2",
            "abstract_vlan_interface": "int_fabric_vlan_11_1",
            "FABRIC_NAME": "site-2",
            "abstract_pim_interface": "pim_interface",
            "LOOPBACK0_IPV6_RANGE": "",
            "NVE_LB_ID": "1",
            "VPC_DELAY_RESTORE": "150",
            "TE_PROXY_BYPASS": "",
            "ENABLE_VPC_PEER_LINK_NATIVE_VLAN": "true",
            "L2_HOST_INTF_MTU": "9216",
            "abstract_route_map": "route_map",
            "abstract_vpc_domain": "base_vpc_domain_11_1",
            "ACTIVE_MIGRATION": "false",
            "COPP_POLICY": "strict",
            "DHCP_END_INTERNAL": "",
            "BOOTSTRAP_ENABLE": "true",
            "default_vrf": "Default_VRF_Universal",
            "OSPF_AREA_ID": "0.0.0.0",
            "SYSLOG_SERVER_IP_LIST": "172.31.7.77",
            "software_image": "9.3(9)",
            "ENABLE_TENANT_DHCP": "true",
            "ANYCAST_RP_IP_RANGE_INTERNAL": "10.254.254.0/31",
            "RR_COUNT": "2",
            "BOOTSTRAP_MULTISUBNET_INTERNAL": "",
            "MGMT_GW": "",
            "MGMT_PREFIX": "",
            "abstract_bgp_rr": "evpn_bgp_rr",
            "abstract_bgp": "base_bgp",
            "SUBNET_RANGE": "10.24.0.0/16",
            "DEAFULT_QUEUING_POLICY_CLOUDSCALE": "WF_QoS_506d",
            "MULTICAST_GROUP_SUBNET": "239.250.253.0/25",
            "FABRIC_INTERFACE_TYPE": "unnumbered",
            "FABRIC_VPC_QOS": "false",
            "AAA_REMOTE_IP_ENABLED": "true",
            "L2_SEGMENT_ID_RANGE": "30000-49000"
          },
          "vrfTemplate": "Default_VRF_Universal",
          "networkTemplate": "Default_Network_Universal",
          "vrfExtensionTemplate": "Default_VRF_Extension_Universal",
          "networkExtensionTemplate": "Default_Network_Extension_Universal",
          "createdOn": 1582778773952,
          "modifiedOn": 1650129264820
        }
        """

        path = f'/control/fabrics/{fabric}'

        logger.info("get_fabric_details: getting fabric details for: {}".format(fabric))
        response = self._check_response(self.get(path))

        self.fabrics[fabric] = json.loads(response['MESSAGE'])

    def post_new_policy(self, details: str) -> bool:
        """

        :param details: policy id to deploy
        :type details: str
        :return: True if successful, False otherwise
        :rtype: bool

        {
        "id": 582700,
        "policyId": "POLICY-582700",
        "description": "interface descriptions",
        "serialNumber": "FDO24261WAT",
        "entityType": "SWITCH",
        "entityName": "SWITCH",
        "templateName": "switch_freeform",
        "templateContentType": "PYTHON",
        "nvPairs": {
            "SERIAL_NUMBER": "",
            "SECENTITY": "",
            "PRIORITY": "500",
            "POLICY_DESC": "interface descriptions",
            "CONF": "interface Ethernet1/7\n  description Test 7\ninterface Ethernet1/8\n  description Test 8",
            "SECENTTYPE": "",
            "FABRIC_NAME": "vxlan_cml_3",
            "POLICY_ID": "POLICY-582700"
        },
        "generatedConfig": "interface Ethernet1/5\n  description Test 5\ninterface Ethernet1/6\n  description Test 6\n\n\n",
        "autoGenerated": false,
        "deleted": false,
        "source": "",
        "priority": 500,
        "status": "NA",
        "statusOn": 1648585732573,
        "createdOn": 1648585732573,
        "modifiedOn": 1648585732573,
        "fabricName": "vxlan_cml_3",
        "resourcesLinked": ""
        }
        """
        path = '/control/policies'
        logger.debug("post_new_policy: details: {}".format(details))
        info = self._check_action_response(self.post(path, data=details, errors=[
            (500, "Invalid payload or any other internal server error")]), "post_new_policy",
                                           "CREATION OF POLICY", details)
        return info

    def get_switches_status(self, serial_numbers: Optional[Union[str, list[str]]]) -> dict[str, str]:
        local_status: dict[str, list] = {}
        result_status: dict[str, str] = {}
        if serial_numbers:
            if isinstance(serial_numbers, str):
                serial_numbers = [serial_numbers]
        else:
            if self.all_leaf_switches and self.all_notleaf_switches:
                serial_numbers = list(self.all_leaf_switches.keys()) + list(self.all_notleaf_switches.keys())
            else:
                logger.critical(
                    "ERROR: get_switches_status: One of the get switches methods must be run if a list of serial numbers\n"
                    "is not provided.")
                raise DCNMSwitchStatusParameterError("Must provide a serial number or a list of serial numbers\n"
                                                     "Or get_all_switches or get_switches_by_serial_number\n"
                                                     "Must have prevously been run!")
        for serial_number in serial_numbers:
            fabric: str = self.all_leaf_switches.get(serial_number) or self.all_notleaf_switches.get(serial_number)
            if not fabric:
                fabric = self.get_switch_fabric(serial_number)
            if fabric in local_status:
                continue
            if fabric not in self.fabrics:
                self.get_fabric_details(fabric)
            fabric_id: str = self.fabrics[fabric]['id']
            path = f'/control/status?entityTypeFilter=SWITCH&fabricId={fabric_id}'
            response = self.get(path)
            logger.debug("get_switches_status: response: {}".format(response))
            if response['RETURN_CODE'] > 299:
                logger.error(
                    "ERROR: get_switches_status: error returned getting statuses for fabric {} {}".format(fabric,
                                                                                                          fabric_id))
            elif response['MESSAGE']:
                local_status[fabric] = json.loads(response['MESSAGE'])
            else:
                logger.error(
                    "ERROR: get_switches_status: no statuses returned for fabric {} {}".format(fabric, fabric_id))
        if not local_status:
            logger.critical("get_switches_status: no statuses returned for any fabrics!")
            raise DCNMSwitchStatusError("ERROR: No Statuses Returned for Any Fabrics")
        for status in sum(local_status.values(), []):
            if status['entityName'] in serial_numbers:
                result_status[status['entityName']] = status['status']
        logger.debug("get_switches_status: result: {}".format(result_status))
        return result_status

    @spinner("elapsed time waiting for switches status")
    def wait_for_switches_status(self, status: str = "In-Sync", timeout: float = 300, sleep_time: float = 10,
                                 serial_numbers: Optional[Union[str, list[str]]] = None) -> Union[bool, dict]:
        """

        :param status: switch status to watch for
        :type status: str
        :param timeout: maximum time to wait for status on all switches
        :type timeout: float
        :param sleep_time: time between status calls
        :type sleep_time: float
        :param serial_numbers: optional list of switch serial numbers
        :type serial_numbers: list
        :return: True or dictionary
        :rtype: bool or dict

        Wait for a list of switches (either a provided list or all previously discovered switches) to change to
        status. Waits for a maximum of timeout. If successful returns True, else returns a dictionary of serial numbers
        that failed to attain status.
        """
        start = time()
        logger.info("Checking for switch status")
        response: Union[None, dict] = None
        result: bool = False
        while (time() - start) <= timeout:
            response: dict = self.get_switches_status(serial_numbers=serial_numbers)
            logger.debug("wait_for_switches_status: response: {}".format(response))

            if response:
                result: bool = all(stat == status for stat in response.values())
                logger.debug("wait_for_switches_status: result: {}".format(result))
            else:
                logger.critical("ERROR: wait_for_switches_status: Unable to retrieve switch statuses!")
                raise DCNMSwitchStatusError("Unable to retrieve switch statuses!")
            if result:
                logger.debug("Switch statuses successfully achieved: {}".format(status))
                return result
            else:
                logger.info("checking switch statuses: time elapsed: {}".format(time() - start))
                sleep(sleep_time)
        logger.critical(
            "ERROR: wait_for_switches_status: timed out waiting for switch statuses to become {}".format(status))
        if result:
            return True
        bad_results: dict = {key: value for key, value in response.items() if value != status}
        logger.critical("ERROR: These switches did not achieve the desired status: {}".format(bad_results))
        return bad_results

    @staticmethod
    def _check_patterns(patterns: list[Union[str, tuple]], string_to_check: Union[str, dict]) -> bool:
        """

        :param patterns: regular expressions or a tuple
        :type patterns: a lists of strings or tuples
        :param string_to_check: string or a dictionary to be matched
        :type string_to_check:
        :return: true if matched
        :rtype: bool

        helper function for matching regular expressions.
        if pattern is a tuple, the regular expression is element one and element zero is the key of a dictionary where
        the value is the string to be matched
        """
        if isinstance(patterns, (list, tuple)):
            for pattern in patterns:
                if isinstance(pattern, str):
                    pattern = re.compile(pattern, re.MULTILINE)
                    if pattern.search(string_to_check):
                        return True
                elif isinstance(pattern, (list, tuple)):
                    pattern = re.compile(pattern[1], re.MULTILINE)
                    if pattern.search(string_to_check[pattern[0]]):
                        return True
                else:
                    logger.error("_check_patterns: failure: pattern {}, string {}".format(pattern, string_to_check))
                    raise DCNMParamaterError("pattern must be a string or tuple of two strings")
        else:
            logger.error("_check_patterns: patterns wrong type {}".format(patterns))
            raise DCNMParamaterError("patterns must be a string or a list or tuple")
        return False

    @staticmethod
    def create_deploy_list(deploy_list: Union[set[tuple], list[tuple], tuple[tuple]]) -> list[dict]:
        """

        :param deploy_list: an iterator with items of the form ('Ethernet1/38', 'FDO24270209')
        :type deploy_list: iterator
        :return: new_deploy_list
        :rtype: list[dict]

        takes an iterator of the form [('Ethernet1/38', 'FDO24270209')] and returns a list of the form
        [{'serialNumber': 'FDO24270209', 'ifName': 'Ethernet1/38'
        """
        new_deploy_list: list = []
        for interface, switch in deploy_list:
            new_deploy_list.append({'serialNumber': switch, 'ifName': interface})
        return new_deploy_list

    @staticmethod
    def get_filtered_interfaces_nvpairs(interfaces_nv_pairs: dict, policy: Optional[Union[str, list[str]]] = None,
                                        config: Optional[Union[str, list[str]]] = None,
                                        non_config: Optional[Union[str, list[str]]] = None,
                                        nv_pairs: Optional[list[tuple[str, str]]] = None,
                                        ) -> dict:
        """

        :param interfaces_nv_pairs: dictionary of interface policy details including nvpairs
        :type interfaces_nv_pairs: dict
        :param policy: a policy name or list of policy names to match
        :type policy: optional str or list of strings
        :param config: configuration or list of configurations to match
        :type config: optional str or list of strings
        :param non_config: a missing configuration of list of configurations to match
        :type non_config: optional str or list of strings
        :param nv_pairs: a list of key value tuples within nvpairs to match
        :type nv_pairs: optional list of tuples of form (str, str)
        :return: a new dictionary with only the entries that match all patterns
        :rtype: dict

        provide a dictionary of interface policies of the below form. it filters out all elements that do not match the
        provided patterns and returns a new dictionary with only those elements.

        {
            ('Ethernet1/38', 'FDO242600CW'): {
                'interfaces': [
                    {
                        'ifName': 'Ethernet1/38',
                        'nvPairs': {
                            'ADMIN_STATE': 'true',
                            'ALLOWED_VLANS': 'none',
                            'BPDUGUARD_ENABLED': 'no',
                            'CONF': 'no cdp '
                                                                           'enable',
                            'DESC': '',
                            'GF': '',
                            'INTF_NAME': 'Ethernet1/38',
                            'MTU': 'jumbo',
                            'POLICY_DESC': '',
                            'POLICY_ID': 'POLICY-5247430',
                            'PORTTYPE_FAST_ENABLED': 'true',
                            'PRIORITY': '450',
                            'PTP': 'false',
                            'SPEED': 'Auto'
                        },
                        'serialNumber': 'FDO242600CW'
                    }
                ],
                'policy': 'int_trunk_host_11_1'
            },
            ('Ethernet1/38', 'FDO24261WAT'): {
                'interfaces': [
                    {
                        'ifName': 'Ethernet1/38',
                        'nvPairs': {
                            'ADMIN_STATE': 'true',
                            'ALLOWED_VLANS': 'none',
                            'BPDUGUARD_ENABLED': 'no',
                            'CONF': 'no cdp '
                                                                           'enable',
                            'DESC': '',
                            'GF': '',
                            'INTF_NAME': 'Ethernet1/38',
                            'MTU': 'jumbo',
                            'POLICY_DESC': '',
                            'POLICY_ID': 'POLICY-5258530',
                            'PORTTYPE_FAST_ENABLED': 'true',
                            'PRIORITY': '450',
                            'PTP': 'false',
                            'SPEED': 'Auto'
                        },
                        'serialNumber': 'FDO24261WAT'
                    }
                ],
                'policy': 'int_trunk_host_11_1'
            }
        }
        """
        interfaces_nv_pairs_local = deepcopy(interfaces_nv_pairs)

        if isinstance(policy, str): policy = [policy]
        if isinstance(config, str): config = [config]
        if isinstance(non_config, str): config = [config]
        try:
            for interface, interface_policy in deepcopy(interfaces_nv_pairs_local).items():
                if policy:
                    if not DcnmInterfaces._check_patterns(policy, interface_policy['policy']):
                        del interfaces_nv_pairs_local[interface]
                        continue

                if nv_pairs:
                    if not DcnmInterfaces._check_patterns(nv_pairs, interface_policy['interfaces'][0]['nvPairs']):
                        del interfaces_nv_pairs_local[interface]
                        continue

                if config:
                    if not DcnmInterfaces._check_patterns(config, interface_policy['interfaces'][0]['nvPairs']['CONF']):
                        del interfaces_nv_pairs_local[interface]
                        continue

                if config:
                    if DcnmInterfaces._check_patterns(config, interface_policy['interfaces'][0]['nvPairs']['CONF']):
                        del interfaces_nv_pairs_local[interface]
                        continue

        except DCNMParamaterError:
            logger.error("ERROR: get_filtered_interfaces_nvpairs: Failed filtering nvpairs dictionary for {}".format(
                interfaces_nv_pairs))
            logger.error(
                "ERROR: get_filtered_interfaces_nvpairs: Error in filters: policy {} or config {} or nv_pairs {}".format(
                    policy, config, nv_pairs))
            raise DCNMInterfacesParameterError("serial_numbers must be a string or a list of strings\n"
                                               "policy must be a string or a list of strings\n"
                                               "nv_pairs must be a list of tuples of two strings\n"
                                               "config must be a string or a list of strings")
        return interfaces_nv_pairs_local

    @staticmethod
    def get_info_from_policies_config(policies: dict[str, list], config: str,
                                      key_tuple: Optional[Union[list[int], tuple[int]]] = [0],
                                      value_tuple: Optional[Union[list[int], tuple[int]]] = [1]) -> Optional[list[
        info_from_policies]]:
        """

        :param policies: a dictionary of switch policies
        :type policies: dict
        :param config: config to match within switch policies, this is a regex that may contain groups
        :type config: str
        :param key_tuple: if provided, each int represents a group value to include in the dictionary key of the
          returned dictionary. serial number is always appended as the final tuple value
        :type key_tuple: optional list or tuple of ints
        :param value_tuple: if provided, if provided, each int represents a group value to include in the dictionary value of the
          returned dictionary
        :type value_tuple: optional list or tuple of ints
        :return:
        :rtype: list of dictionaries

        takes switch policies and patterns to match
        returns list of info_from_polices data class objects of the form
        info_from_policies(existing_descriptions_local, policyId)
        where existing_descriptions is a dictionary and the policyId is a str
        """
        existing_policyId_local = []
        policies_local: dict = deepcopy(policies)
        pattern = re.compile(config, re.MULTILINE)
        for SN, policies in policies_local.items():
            existing_descriptions_local: dict = dict()
            for policy in policies:
                policyId = policy['policyId']
                result = pattern.findall(policy['generatedConfig'])
                if result:
                    for item in result:
                        derived_key = list()
                        derived_value = list()
                        if key_tuple:
                            for i in key_tuple:
                                derived_key.append(item[i])
                        derived_key.append(SN)
                        if len(derived_key) == 1:
                            derived_key = derived_key[0]
                        else:
                            derived_key = tuple(derived_key)
                        if value_tuple:
                            for i in value_tuple:
                                derived_value.append(item[i])
                        if len(derived_value) == 1:
                            derived_value = derived_value[0]
                        else:
                            derived_value = tuple(value_tuple)
                        existing_descriptions_local[derived_key] = derived_value
                    existing_policyId_local.append(info_from_policies(existing_descriptions_local, policyId))
        logger.debug(
            "read_existing_descriptions_from_policies: existing descriptions: {}".format(existing_descriptions_local))
        if not existing_policyId_local:
            return None
        return existing_policyId_local

    def _check_response(self, response: dict):
        if response['RETURN_CODE'] > 299:
            logger.error("ERROR IN RESPONSE FROM DCNM: {}".format(response))
            raise DCNMServerResponseError("{}".format(response))
        else:
            return response

    def _check_action_response(self, response: dict, method: str, message: str, data: Any) -> bool:
        if response["RETURN_CODE"] != 200:
            logger.critical("ERROR: {}: {} {} FAILED".format(method, message, data))
            logger.critical("ERROR: {}: returned info {}".format(method, response))
            return False
        logger.debug("{} successful: {}".format(method, response))
        return True


class ExcelFileError(Exception):
    pass


def read_existing_descriptions(file: str) -> dict[tuple, str]:
    """

    :param file: an excel file path/name containing columns "interface", "switch" and "description"
    the switch column is the switch serial number
    :type file: str
    :return: dictionary
    :rtype: dict[tuple, str]

    Read in an excel file and return a dictionary of form {(interface, switch_serial_number): interface_description}
    """
    existing_descriptions_local: dict
    logger.debug("reading excel file {}".format(file))
    df: pandas.DataFrame = read_excel(file)
    df.columns = df.columns.str.lower()
    if 'description' not in df.columns or 'interface' not in df.columns or 'switch' not in df.columns:
        logger.debug("Columns missing. {}".format(df.columns))
        raise ExcelFileError('One or more columns missing')
    existing_descriptions_local = df.to_dict('records')
    # print(existing_descriptions)
    existing_descriptions_local = {(interface['interface'], interface['switch']): interface['description'] for interface
                                   in
                                   existing_descriptions_local}
    logger.debug("read_existing_descriptions: existing descriptions: {}".format(existing_descriptions_local))
    return existing_descriptions_local


def get_interfaces_to_change(dcnm: DcnmInterfaces,
                             change_functions: list[tuple[Callable, Optional[dict], bool]]) -> tuple[
    dict[tuple, dict], dict[tuple, dict]]:
    """

    :param dcnm: dcnm object
    :type dcnm: DcnmInterfaces
    :param change_functions: a list of tuples with each tuple of the form
    (a function object to call, an optional dictionary containing args to pass to function
    :type change_functions: list[tuple[Callable, Optional[dict], bool]]
    :return: a tuple of dictionaries
    :rtype: tuple[dict[tuple, dict], dict[tuple, dict]]

    provide a list of callables to apply
    the function iterates through the interface tuple and interface policy details of the all_interfaces_nvpairs
    parameter and provides each of those values along with the optional dictionary of parameters to each callable
    returns two dictionaries. the first is the interfaces to change along with the changes to make and the other
    is the original dictionary of policies
    """
    existing_interfaces = deepcopy(dcnm.all_interfaces_nvpairs)
    interfaces_to_change: dict[tuple, dict] = {}
    interfaces_original: dict[tuple, dict] = {}
    for interface, details in existing_interfaces.items():
        change = False
        if interface[1] in dcnm.all_leaf_switches.keys():
            # print(details)
            if ('ethernet' in details['interfaces'][0]['ifName'].lower() or
                'mgmt' in details['interfaces'][0]['ifName'].lower()) and 'fabric' not in details['policy']:
                change = _run_functions(change_functions, details, interface, leaf=True)
        else:
            if 'mgmt' not in interface[0]:
                continue
            else:
                change = _run_functions(change_functions, details, interface, leaf=False)
        if change:
            interfaces_original[interface] = dcnm.all_interfaces_nvpairs[interface]
            interfaces_to_change[interface] = details
    logger.debug("Interfaces to change: {}".format(interfaces_to_change))
    return interfaces_to_change, interfaces_original


def _run_functions(change_functions, details, interface, leaf=True):
    """

    :param change_functions:
    :type change_functions:
    :param details:
    :type details:
    :param interface:
    :type interface:
    :param leaf:
    :type leaf:
    :return:
    :rtype:

    helper function
    """
    change = False
    for function in change_functions:
        if (function[2] and leaf) or not function[2]:
            if function[1]:
                logger.debug("_run_functions: sending {} to function {}".format(interface, function))
                logger.debug("detail: {}".format(details))
                logger.debug("{}".format(function[0]))
                change = function[0](interface, details, **function[1]) or change
            else:
                logger.debug("_run_functions: sending {} to function {}".format(interface, function))
                logger.debug("detail: {}".format(details))
                logger.debug("{}".format(function[0]))
                change = function[0](interface, details) or change
        else:
            change = change or False

    return change


def get_desc_change(interface: tuple, detail: dict, existing_descriptions: dict[tuple, str]) -> bool:
    logger.debug("start get_desc_change: interface {}".format(interface))
    logger.debug("detail: {}".format(detail))
    if interface in existing_descriptions and detail['interfaces'][0]['nvPairs']['DESC'] != existing_descriptions[
        interface]:
        logger.debug("interface: {}, new description: {}, old description: {}".format(interface,
                                                                                      existing_descriptions[interface],
                                                                                      detail['interfaces'][0][
                                                                                          'nvPairs']['DESC']))
        detail['interfaces'][0]['nvPairs']['DESC'] = existing_descriptions[interface]
        return True
    return False


def get_cdp_change(interface: tuple, detail: dict, mgmt: bool = True) -> bool:
    logger.debug("start get_cdp_change: interface {}".format(interface))
    logger.debug("detail: {}".format(detail))
    if mgmt and 'mgmt' in interface[0] and detail['interfaces'][0]['nvPairs']['CDP_ENABLE'] == 'true':
        detail['interfaces'][0]['nvPairs']['CDP_ENABLE'] = 'false'
        logger.debug("interface: {}, changing cdp".format(interface))
        logger.debug("CDP_ENABLE: {}".format(detail['interfaces'][0]['nvPairs']['CDP_ENABLE']))
        return True
    elif 'mgmt' not in interface[0] and 'no cdp enable' not in detail['interfaces'][0]['nvPairs']['CONF']:
        if not detail['interfaces'][0]['nvPairs']['CONF']:
            detail['interfaces'][0]['nvPairs']['CONF'] = 'no cdp enable'
            logger.debug("interface: {}, changing cdp".format(interface))
            logger.debug("CONF: {}".format(detail['interfaces'][0]['nvPairs']['CONF']))
            return True
        else:
            # print(interface, detail)
            detail['interfaces'][0]['nvPairs']['CONF'] = '{}\n{}'.format(
                detail['interfaces'][0]['nvPairs']['CONF'],
                'no cdp enable')
            logger.debug("interface: {}, changing cdp".format(interface))
            logger.debug("multiple CONF: {}".format(detail['interfaces'][0]['nvPairs']['CONF']))
            return True
    return False


def get_orphanport_change(interface: tuple, detail: dict) -> bool:
    logger.debug("start get_orphanport_change: interface {}".format(interface))
    logger.debug("detail: {}".format(detail))
    if 'mgmt' in interface[0]:
        return False
    elif 'mgmt' not in interface[0] and ('int_trunk_host' in detail['policy'] or 'int_access_host' in detail[
        'policy']) and 'vpc orphan-port enable' not in detail['interfaces'][0]['nvPairs']['CONF']:
        if not detail['interfaces'][0]['nvPairs']['CONF']:
            detail['interfaces'][0]['nvPairs']['CONF'] = 'vpc orphan-port enable'
            logger.debug("interface: {}, changing orphan port enable".format(interface))
            logger.debug("orphan port CONF: {}".format(detail['interfaces'][0]['nvPairs']['CONF']))
            return True
        else:
            # print(interface, detail)
            detail['interfaces'][0]['nvPairs']['CONF'] = '{}\n{}'.format(
                detail['interfaces'][0]['nvPairs']['CONF'],
                'vpc orphan-port enable')
            logger.debug("interface: {}, changing orphan port enable".format(interface))
            logger.debug("orphan port multiple CONF: {}".format(detail['interfaces'][0]['nvPairs']['CONF']))
            return True
    return False


def verify_interface_change(dcnm: DcnmInterfaces, interfaces_will_change: dict, verbose: bool = True, **kwargs):
    dcnm.get_interfaces_nvpairs(save_prev=True, **kwargs)
    failed: set = set()
    success: set = set()
    if verbose: _dbg("Verifying Interface Configurations")
    interfaces_will_change_local = deepcopy(interfaces_will_change)
    all_interfaces_nv_pairs_local = deepcopy(dcnm.all_interfaces_nvpairs)
    for interface in interfaces_will_change:
        #priority changes, so remove from comparison
        interfaces_will_change_local[interface]['interfaces'][0]['nvPairs'].pop('PRIORITY', None)
        interfaces_will_change_local[interface]['interfaces'][0]['nvPairs'].pop('FABRIC_NAME', None)
        all_interfaces_nv_pairs_local[interface]['interfaces'][0]['nvPairs'].pop('PRIORITY', None)
        all_interfaces_nv_pairs_local[interface]['interfaces'][0]['nvPairs'].pop('FABRIC_NAME', None)
        if interfaces_will_change_local[interface] == all_interfaces_nv_pairs_local[interface]:
            logger.debug("Verification confirmed for interface {}".format(interface))
            logger.debug("{}".format(interfaces_will_change[interface]))
            success.add(interface)
        else:
            logger.critical("Verification failed for interface {}".format(interface))
            logger.critical("Desired configuration: {}".format(interfaces_will_change[interface]))
            logger.critical("Configuration pulled from DCNM: {}".format(dcnm.all_interfaces_nvpairs[interface]))
            failed.add(interface)
    if failed:
        if failed:
            _failed_dbg("verify_interface_change:  Failed configuring {}".format(failed),
                        ("Failed verification config changes to for the following switches:", failed))
    else:
        logger.debug("verify_interface_change: No Failures!")
        if verbose: _dbg("Successfully Verified All Interface Changes! Yay!")
    # return success, failed


def push_to_dcnm(dcnm: DcnmInterfaces, interfaces_to_change: dict, verbose: bool = True) -> set:
    # make changes
    success: set
    failure: set
    if verbose:
        _dbg("Putting changes to dcnm")
    success, failure = dcnm.put_interface_changes(interfaces_to_change)
    if failure:
        _failed_dbg("Failed putting to DCNM for the following: {}".format(failure),
                    ("Failed pushing config changes to DCNM for the following switches:", failure))
    else:
        if verbose: _dbg("Successfully Pushed All Configurations!")
    logger.debug("push_to_dcnm: success: {}".format(success))
    if verbose: _dbg("Successfully Pushed Following Configs", success)
    return success


def deploy_to_fabric_using_interface_deploy(dcnm: DcnmInterfaces, deploy,
                                            policies: Optional[Union[list, tuple, str]] = None,
                                            deploy_timeout: int = 300,
                                            fallback: bool = False,
                                            verbose: bool = True):
    deploy_list: list = DcnmInterfaces.create_deploy_list(deploy)
    if verbose:
        _dbg('Deploying changes to switches')
    if dcnm.deploy_interfaces(deploy_list, deploy_timeout=deploy_timeout):
        logger.debug('successfully deployed to {}'.format(deploy))
        if verbose:
            _dbg('!!Successfully Deployed Config Changes to Switches!!', deploy)
    else:
        _failed_dbg("Failed deploying to {}".format(deploy),
                    ("Failed deploying configs to the following switches:", deploy))
    print()
    print('=' * 40)
    print('=' * 40)
    if policies and fallback:
        if isinstance(policies, str):
            policies = [policies]
        if verbose: _dbg("DEPLOYING POLICIES: ", policies)
        if dcnm.deploy_policies(policies, deploy_timeout=deploy_timeout):
            logger.debug('successfully deployed policies {}'.format(policies))
            if verbose:
                _dbg('!!Successfully Deployed Config Policies to Switches!!', policies)
        else:
            _failed_dbg("Failed deploying policies {}".format(policies),
                        ('Failed deploying the following policies:', policies))
    print()
    print('=' * 40)
    print('=' * 40)
    print("FINISHED DEPLOYING. GO GET A BEER!")
    print('=' * 40)


def deploy_to_fabric_using_switch_deploy(dcnm: DcnmInterfaces, serial_number: str,
                                         deploy_timeout: int = 300,
                                         verbose: bool = True):
    if verbose:
        _dbg('Deploying changes to switches')
    tic = perf_counter()
    if dcnm.deploy_switch_config(serial_number):
        toc = perf_counter()
        _dbg(f"Deployed in {toc - tic:0.4f} seconds")
        logger.debug('successfully deployed config to switch {}'.format(serial_number))
        if verbose:
            _dbg('!!Successfully Deployed Config Changes to Switches!!', serial_number)
    else:
        _failed_dbg("Failed deploying to config to switch {}".format(serial_number),
                    ("Failed deploying configs to the following switches:", serial_number))
    print()
    print('=' * 40)
    print('=' * 40)
    print("FINISHED DEPLOYING. GO GET A BEER!")
    print('=' * 40)


def _failed_dbg(log_msg: str, messages: tuple):
    init()
    logger.critical(log_msg)
    print()
    print()
    print(Back.BLACK + Fore.RED + '*' * 60)
    for i in messages:
        pprint(i)
    print('*' * 60)
    print()
    print()
    print(Style.RESET_ALL)


if __name__ == '__main__':
    SCREENLOGLEVEL = logging.DEBUG
    FILELOGLEVEL = logging.DEBUG
    logformat = logging.Formatter(
        '%(asctime)s: %(process)d - %(threadName)s - %(funcName)s - %(name)s - %(levelname)s - message: %(message)s')

    logging.basicConfig(level=SCREENLOGLEVEL,
                        format='%(asctime)s: %(process)d - %(threadName)s - %(funcName)s - %(name)s - %(levelname)s - %(message)s')

    # screen handler
    # ch = logging.StreamHandler()
    # ch.setLevel(SCREENLOGLEVEL)
    # ch.setFormatter(logformat)
    #
    # logging.getLogger('').addHandler(ch)

    logger = logging.getLogger('dcnminterface')

    logger.critical("Started")
    # prompt stdin for username and password
    dcnm = DcnmInterfaces("10.0.17.99", dryrun=True)
    dcnm.login(username="rragan", password="MVhHuBr3")

    dcnm.get_interfaces_nvpairs(save_to_file='all_interfaces.json', serial_numbers=['FDO24261WAT', 'FDO242702QK'])
    pprint(dcnm.all_interfaces_nvpairs)
    # dcnm.get_all_switches()
    dcnm.get_switches_by_serial_number(serial_numbers=['FDO24261WAT', 'FDO242702QK'])
    print("=" * 40)
    print(len(dcnm.all_leaf_switches.keys()))
    print(dcnm.all_leaf_switches.keys())
    # existing_descriptions = read_existing_descriptions('interface_descriptions.xlsx')
    # print(existing_descriptions)

    # dcnm.get_switches_policies(serial_numbers=['9Y04VBM75I8', '9A1R3QS819Z'])
    # print("=" * 40)
    # pprint(dcnm.all_switches_policies)

    # dcnm.get_switches_policies(serial_numbers=['9Y04VBM75I8'], templateName='switch_freeform\Z')
    # pprint(dcnm.all_switches_policies)
    #
    dcnm.get_switches_policies(templateName='switch_freeform\Z',
                               config=r"interface\s+[a-zA-Z]+\d+/?\d*\n\s+description\s+")
    print("=" * 40)
    pprint(dcnm.all_switches_policies)

    existing_descriptions_from_policies: list = DcnmInterfaces.get_info_from_policies_config(dcnm.all_switches_policies,
                                                                                             r"interface\s+([a-zA-Z]+\d+/?\d*)\n\s+description\s+(.*)")

    print("=" * 40)
    pprint(existing_descriptions_from_policies)
    with open('switches_configuration_policies.pickle', 'wb') as f:
        dump(dcnm.all_switches_policies, f)
    policy_ids: set = {c.policyId for c in existing_descriptions_from_policies}
    print(policy_ids)
    dcnm.delete_switch_policies(list(policy_ids))
    existing_descriptions: dict[tuple, str] = {k: v for c in existing_descriptions_from_policies for k, v in
                                               c.info.items()}
    pprint(existing_descriptions)
    interfaces_will_change, interfaces_existing_conf = \
        get_interfaces_to_change(dcnm, [(get_desc_change, {'existing_descriptions': existing_descriptions}, False),
                                        (get_cdp_change, {'mgmt': False}, False),
                                        (get_orphanport_change, None, True)])

    print('=' * 40)
    print()
    with open('interfaces_existing_conf.pickle', 'wb') as f:
        dump(interfaces_existing_conf, f)
    with open('interfaces_will_change.json', 'w') as f:
        f.write(str(interfaces_will_change))

    pprint(interfaces_will_change)

    success = push_to_dcnm(dcnm, interfaces_will_change)
    deploy_to_fabric_using_interface_deploy(dcnm, success, policies=list(policy_ids))

    # Verify
    verify_interface_change(dcnm, interfaces_will_change, serial_numbers=['FDO24261WAT', 'FDO242702QK'])

    # Fallback
    print()
    print('=' * 40)
    print("YOU WANT TO FALLBACK?")
    with open('interfaces_existing_conf.pickle', 'rb') as f:
        interfaces_existing_conf = load(f)
    pprint(interfaces_existing_conf)
    success = push_to_dcnm(dcnm, interfaces_existing_conf)
    with open('switches_configuration_policies.pickle', 'rb') as f:
        interface_desc_policies: dict[str, list] = load(f)
    pprint(interface_desc_policies)
    policies_ids: list = []
    for serial_number in interface_desc_policies:
        for policy in interface_desc_policies[serial_number]:
            dcnm.post_new_policy(policy)
            policies_ids.append([policy["policyId"]])
    deploy_to_fabric_using_interface_deploy(dcnm, success, policies=policies_ids)
    print('=' * 40)
    print("FALLBACK")
    print('=' * 40)
    dcnm.wait_for_switches_status(serial_numbers=['FDO24261WAT', 'FDO242702QK'])
    verify_interface_change(dcnm, interfaces_existing_conf, serial_numbers=['FDO24261WAT', 'FDO242702QK'])
    print('=' * 40)
    print("FINISHED. GO GET PLASTERED!")
    print('=' * 40)
