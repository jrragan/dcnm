import json
import logging
import re
from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass
from pickle import dump, load
from pprint import pprint
from typing import Union, Optional, Callable

import pandas
from pandas import read_excel

from dcnm.interfaces.dcnm_connect import HttpApi


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

        response = self.get(path)
        for switch in json.loads(response['MESSAGE']):
            if switch['switchRole'] == 'leaf':
                self.all_leaf_switches[switch['serialNumber']] = switch['fabricName']
            else:
                self.all_notleaf_switches[switch['serialNumber']] = switch['fabricName']

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
            response = self.get(path, params=params)
            for switch in json.loads(response['MESSAGE']):
                fabricName = self.get_switch_fabric(switch['serialNumber'])
                if switch['role'] == 'leaf':
                    self.all_leaf_switches[switch['serialNumber']] = fabricName
                else:
                    self.all_notleaf_switches[switch['serialNumber']] = fabricName
        else:
            self.get_all_switches()

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

        response = self.get(path, params=params)

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
        info = self.delete(path, errors=[
            (500, "Invalid payload or any other internal server error (e.g. policy does not exist)")])
        logger.debug("delete_switch_policies: info: {}".format(policyId))
        if info["RETURN_CODE"] != 200:
            logger.critical("delete_switch_policies: DELETE OF {} FAILED".format(policyId))
            logger.critical("delete_switch_policies: info returned from put: {}".format(info))
            logger.debug(policyId)
            return False
        else:
            logger.info("delete_switch_policies:  {} successfully changed. Yay.".format(policyId))
        return True

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

        response = self.get(path, params=params)
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

        response = self.get(path, params=params)
        for policy in json.loads(response['MESSAGE']):
            for interface in policy['interfaces']:
                # print(interface)
                local_all_interfaces_nvpairs[(interface['ifName'], interface['serialNumber'])] = {
                    'policy': policy['policy'], 'interfaces': [
                        interface
                    ]
                }

        return local_all_interfaces_nvpairs

    def get_interfaces_nvpairs(self, serial_numbers: Union[list, tuple],
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
                self.all_interfaces_nvpairs = DcnmInterfaces.get_filtered_interfaces_nvpairs(self.all_interfaces_nvpairs,
                                                                                             policy=policy, config=config,
                                                                                             non_config=non_config,
                                                                                             nv_pairs=nv_pairs)
            except DCNMParamaterError:
                raise DCNMInterfacesParameterError("serial_numbers must be a string or a list of strings\n"
                                                   "policy must be a string or a list of strings\n"
                                                   "nv_pairs must be a list of tuples of two strings\n"
                                                   "config must be a string or a list of strings")

        if save_to_file is not None:
            with open(save_to_file, 'w') as f:
                f.write(str(self.all_interfaces_nvpairs))

    def save_fabric_config(self, fabric: str):
        path: str = f'/control/fabrics/{fabric}/config-save'
        info = self.post(path, errors=[(400, "Invalid value supplied"),
            (500, "Invalid payload or any other internal server error")])
        logger.debug("put_interface: info: {}".format(info))
        if info["RETURN_CODE"] != 200:
            logger.critical("save_fabric_config: CONFIG SAVE OF {} FAILED".format(fabric))
            logger.critical("save_fabric_config: info returned from put: {}".format(info))
            return False
        return True

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
        info = self.put(path, data=details, errors=[
            (500, "Invalid payload or any other internal server error")])
        logger.debug("interface_put: info: {}".format(info))
        if info["RETURN_CODE"] != 200:
            logger.critical("put_interface: CREATION OF {} FAILED".format(interface))
            logger.critical("put_interface: info returned from put: {}".format(info))
            logger.debug(details)
            return False
        return True

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
                logger.critical("put_interface_changes:  Don't know what happened: {}".format(result))
                logger.critical("put_interface_changes:  {} : {}".format(interface, details))
                failed.add(interface)
        logger.debug("put_interface_changes:  Successfully configured {}".format(success))
        if failed:
            logger.critical("put_interface_changes:  Failed configuring {}".format(failed))
        else:
            logger.debug("put_interface_changes: No Failures!")
        return success, failed

    def deploy_interfaces(self, payload: Union[list, dict]) -> Optional[bool]:
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

        """
        path = '/globalInterface/deploy'
        if isinstance(payload, dict):
            payload = [payload]
        temp_timers = self.timeout
        self.timeout = 300
        logger.debug("deploying interfaces {}".format(payload))
        info = self.post(path, data=payload)
        if info["RETURN_CODE"] != 200:
            logger.critical("DEPLOY OF {} FAILED".format(payload))
            logger.critical("deploy_interfaces: returned info {}".format(info))
            self.timeout = temp_timers
            return False
        logger.debug("deploy_interfaces: successfully deployed: {}".format(info))
        self.timeout = temp_timers
        return True

    def deploy_fabric_config(self, fabric: str) -> Optional[bool]:
        path = f'/control/fabrics/{fabric}/config-deploy'
        temp_timers = self.timeout
        self.timeout = 300
        logger.debug("deploying config fabric {}".format(fabric))
        info = self.post(path)
        if info["RETURN_CODE"] != 200:
            logger.critical("DEPLOY OF FABRIC {} FAILED".format(fabric))
            logger.critical("deploy_fabric_config: returned info {}".format(info))
            self.timeout = temp_timers
            return False
        logger.debug("deploy_fabric_config: successfully deployed: {}".format(info))
        self.timeout = temp_timers
        return True

    def get_switch_fabric(self, serial_number: str):
        path = f'/control/switches/{serial_number}/fabric-name'

        response = self.get(path)
        return json.loads(response['MESSAGE'])['fabricName']

    def post_new_policy(self, details):
        """

        :param details:
        :type details:
        :return:
        :rtype:

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
        path = 'control/policies'

        info = self.put(path, data=details, errors=[
            (500, "Invalid payload or any other internal server error")])
        logger.debug("post_new_policy: info: {}".format(info))
        if info["RETURN_CODE"] != 200:
            logger.critical("post_new_policy: CREATION OF POLICY {} FAILED".format(details))
            logger.critical("post_new_policy: info returned from post: {}".format(info))
            logger.debug(details)
            return False
        return True

    @staticmethod
    def _check_patterns(patterns: list[Union[str, tuple]], string_to_check: Union[str, dict]) -> bool:
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
                               ):
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
            logger.error("get_filtered_interfaces_nvpairs: Failed filtering nvpairs dictionary for {}".format(interfaces_nv_pairs))
            logger.error("get_filtered_interfaces_nvpairs: Error in filters: policy {} or config {} or nv_pairs {}".format(policy, config, nv_pairs))
            raise DCNMInterfacesParameterError("serial_numbers must be a string or a list of strings\n"
                                               "policy must be a string or a list of strings\n"
                                               "nv_pairs must be a list of tuples of two strings\n"
                                               "config must be a string or a list of strings")
        return interfaces_nv_pairs_local

    @staticmethod
    def get_info_from_policies_config(policies: dict[str, list], config: str,
                                                key_tuple: Optional[list[int]] = [0],
                                                value_tuple: Optional[list[int]] = [1]) -> list[info_from_policies]:
        existing_policyId_local: list = list()
        policies_local = deepcopy(policies)
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
        return existing_policyId_local


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
                             change_functions: list[tuple[Callable, Optional[dict], bool]]) -> tuple[dict[tuple, dict], dict[tuple, dict]]:
    """

    :param dcnm:
    :type dcnm:
    :param existing_descriptions:
    :type existing_descriptions:
    :param change_functions: each interface is run through a list of functions
      these lists are treated as a boolean or
    :type change_functions:
    a list of tuples, each tuple is a (function, optional dictionary of extra kw parameters, and a bool
     True means apply only to leafs
    :return: two dictionaries, one of the changes to be made to selected interfaces
      the other of the original details
    :rtype:

    takes the existing description and interface details from dcnm and selects the interfaces that need to
    be changed, returns both changes and existing details
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

    # if (change_functions[0][2] and leaf) or not change_functions[0][2]:
    #     if change_functions[0][1]:
    #         logger.debug("_run_functions: sending {} to function {}".format(interface, change_functions[0]))
    #         logger.debug("detail: {}".format(details))
    #         logger.debug("{}".format(change_functions[0][0]))
    #         change = change or change_functions[0][0](interface, details, **change_functions[0][1])
    #     else:
    #         logger.debug("_run_functions: sending {} to function {}".format(interface, change_functions[0]))
    #         logger.debug("detail: {}".format(details))
    #         logger.debug("{}".format(change_functions[0][0]))
    #         change = change or change_functions[0][0](interface, details)
    # else:
    #     change = change or False
    #
    # if (change_functions[1][2] and leaf) or not change_functions[1][2]:
    #     if change_functions[1][1]:
    #         logger.debug("_run_functions: sending {} to function {}".format(interface, change_functions[1]))
    #         logger.debug("detail: {}".format(details))
    #         logger.debug("{}".format(change_functions[1][0]))
    #         change = change or change_functions[1][0](interface, details, **change_functions[1][1])
    #     else:
    #         logger.debug("_run_functions: sending {} to function {}".format(interface, change_functions[1]))
    #         logger.debug("detail: {}".format(details))
    #         logger.debug("{}".format(change_functions[1][0]))
    #         change = change or change_functions[1][0](interface, details)
    # else:
    #     change = change or False
    #
    # if (change_functions[2][2] and leaf) or not change_functions[2][2]:
    #     if change_functions[2][1]:
    #         logger.debug("_run_functions: sending {} to function {}".format(interface, change_functions[2]))
    #         logger.debug("detail: {}".format(details))
    #         logger.debug("{}".format(change_functions[2][0]))
    #         change = change or change_functions[2][0](interface, details, **change_functions[2][1])
    #     else:
    #         logger.debug("_run_functions: sending {} to function {}".format(interface, change_functions[2]))
    #         logger.debug("detail: {}".format(details))
    #         logger.debug("{}".format(change_functions[2][0]))
    #         change = change or change_functions[2][0](interface, details)
    # else:
    #     change = change or False
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


def get_cdp_change(interface: tuple, detail: dict) -> bool:
    logger.debug("start get_cdp_change: interface {}".format(interface))
    logger.debug("detail: {}".format(detail))
    if 'mgmt' in interface[0] and detail['interfaces'][0]['nvPairs']['CDP_ENABLE'] == 'true':
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
    elif 'mgmt' not in interface[0] and ('int_trunk_host' in detail['policy'] or 'int_access_host' in detail['policy'])  and 'vpc orphan-port enable' not in detail['interfaces'][0]['nvPairs']['CONF']:
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


def verify_interface_change(dcnm, interfaces_will_change, **kwargs):
    dcnm.get_interfaces_nvpairs(save_prev=True, **kwargs)
    failed: set = set()
    success: set = set()
    for interface in interfaces_will_change:
        if interfaces_will_change[interface] == dcnm.all_interfaces_nvpairs[interface]:
            logger.debug("Verification confirmed for interface {}".format(interface))
            logger.debug("{}".format(interfaces_will_change[interface]))
            success.add(interface)
        else:
            logger.critical("Verification failed for interface {}".format(interface))
            logger.critical("Desired configuration: {}".format(interfaces_will_change[interface]))
            logger.critical("Configuration pulled from DCNM: {}".format(dcnm.all_interfaces_nvpairs[interface]))
            failed.add(interface)
    if failed:
        logger.critical("verify_interface_change:  Failed configuring {}".format(failed))
    else:
        logger.debug("verify_interface_change: No Failures!")
    return success, failed


def push_to_dcnm(dcnm, interfaces_to_change):
    print()
    print('=' * 40)
    # make changes
    success: set
    failure: set
    print('=' * 40)
    print("Putting changes to dcnm")
    print('=' * 40)
    success, failure = dcnm.put_interface_changes(interfaces_to_change)
    if failure:
        print()
        print()
        print('*' * 60)
        print('Failed pushing config changes to DCNM for the following switches:')
        print(failure)
        print('*' * 60)
        print()
        print()
    print('=' * 40)
    print('Deploying changes to switches')
    print('=' * 40)
    return success


def deploy_to_fabric(dcnm, deploy):
    deploy_list: list
    deploy_list = DcnmInterfaces.create_deploy_list(deploy)
    if dcnm.deploy_interfaces(deploy_list):
        logger.debug('successfully deployed to {}'.format(deploy))
        print()
        print()
        print('*' * 60)
        print('!!Successfully Deployed Config Changes to Switches!!')
        print(deploy)
        print('*' * 60)
        print()
        print()
    else:
        logger.critical("Failed deploying to {}".format(deploy))
        print()
        print()
        print('*' * 60)
        print('Failed deploying configs to the following switches:')
        print(deploy)
        print('*' * 60)
        print()
        print()
    print()
    print('=' * 40)
    print("FINISHED. GO GET A BEER!")
    print('=' * 40)


if __name__ == '__main__':
    SCREENLOGLEVEL = logging.INFO
    FILELOGLEVEL = logging.DEBUG
    logformat = logging.Formatter(
        '%(asctime)s: %(process)d - %(threadName)s - %(funcName)s - %(name)s - %(levelname)s - message: %(message)s')

    logging.basicConfig(level=SCREENLOGLEVEL,
                        format='%(asctime)s: %(threadName)s - %(funcName)s - %(name)s - %(levelname)s - %(message)s')

    # screen handler
    # ch = logging.StreamHandler()
    # ch.setLevel(SCREENLOGLEVEL)
    # ch.setFormatter(logformat)
    #
    # logging.getLogger('').addHandler(ch)

    logger = logging.getLogger('dcnminterface')

    logger.critical("Started")
    # prompt stdin for username and password
    dcnm = DcnmInterfaces("10.0.2.248", dryrun=True)
    dcnm.login(username="admin", password="MVhHuBr3")

    dcnm.get_interfaces_nvpairs(save_to_file='all_interfaces.json', serial_numbers=['9Y04VBM75I8', '9A1R3QS819Z'])
    pprint(dcnm.all_interfaces_nvpairs)
    # dcnm.get_all_switches()
    dcnm.get_switches_by_serial_number(serial_numbers=['9Y04VBM75I8', '9A1R3QS819Z'])
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
    existing_descriptions: dict[tuple, str] = {k:v for c in existing_descriptions_from_policies for k, v in c.info.items()}
    pprint(existing_descriptions)
    interfaces_will_change, interfaces_existing_conf = \
        get_interfaces_to_change(dcnm, [(get_desc_change, {'existing_descriptions': existing_descriptions}, False),
                                        (get_cdp_change, None, False),
                                        (get_orphanport_change, None, True)])

    print('=' * 40)
    print()
    with open('interfaces_existing_conf.pickle', 'wb') as f:
        dump(interfaces_existing_conf, f)
    with open('interfaces_will_change.json', 'w') as f:
        f.write(str(interfaces_will_change))

    pprint(interfaces_will_change)

    success = push_to_dcnm(dcnm, interfaces_will_change)
    deploy_to_fabric(dcnm, success)

    # Verify
    verify_interface_change(dcnm, interfaces_will_change,  serial_numbers=['9Y04VBM75I8', '9A1R3QS819Z'])

    # Fallback
    print()
    print('=' * 40)
    print("YOU WANT TO FALLBACK?")
    with open('interfaces_existing_conf.pickle', 'rb') as f:
        interfaces_existing_conf = load(f)
    pprint(interfaces_existing_conf)
    success = push_to_dcnm(dcnm, interfaces_existing_conf)
    deploy_to_fabric(dcnm, success)
    with open('interfaces_existing_conf.pickle', 'rb') as f:
        interface_desc_policies: dict[str, list] = load(f)
    pprint(interface_desc_policies)
    for serial_number in interface_desc_policies:
        for policy in interface_desc_policies[serial_number]:
            dcnm.post_new_policy(policy)
    print('=' * 40)
    print("FINISHED. GO GET PLASTERED!")
    print('=' * 40)