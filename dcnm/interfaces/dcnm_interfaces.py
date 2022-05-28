import functools
import json
import logging
import re
import sys
import threading
import traceback
from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass
from datetime import timedelta
from itertools import cycle
from pickle import dump, load
from pprint import pprint
from time import sleep, time
from typing import Union, Optional, Any

from DCNM_errors import DCNMServerResponseError, DCNMInterfacesParameterError, \
    DCNMSwitchesPoliciesParameterError, DCNMParamaterError, DCNMSwitchesSwitchesParameterError, DCNMPolicyDeployError, \
    DCNMSwitchStatusParameterError, DCNMSwitchStatusError
from dcnm_connect import HttpApi

logger = logging.getLogger('dcnm_interfaces')


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
            try:
                value = func(*args, **kwargs)
            except Exception as e:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                stacktrace = traceback.extract_tb(exc_traceback)
                logger.debug(
                    "response {}".format(value))
                logger.debug(sys.exc_info())
                logger.debug(stacktrace)
                raise
            finally:
                stop = time()
                if _spin_thread:
                    _stop_spin.set()
                    _spin_thread.join()
                print()
                print("=" * 60)
                print("Elapsed Time: ")
                print("=" * 60)
                pprint(stop - start)
                print("=" * 60)
                print()
            return value

        return wrapper_decrorator

    return decorator


@dataclass
class info_from_policies:
    info: dict
    policyId: str


class DcnmInterfaces(HttpApi):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.all_switches_details = {}
        self.all_switches_vpc_pairs: dict[str, Optional[str]] = {}
        self.all_leaf_switches: dict[str, str] = {}
        self.all_notleaf_switches: dict[str, str] = {}
        self.all_interfaces_details: dict[tuple, dict] = {}
        self.all_interfaces_details_prev: dict[tuple, dict] = {}
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

    @error_handler("ERROR: get_vpc_pair: getting vpc pairs for serial number")
    def get_vpc_pair(self, serial_number: str) -> Optional[str]:
        """ Get vpc pair data from api and return data structure """

        path = "/interface/vpcpair_serial_number"
        data = self._check_response(dcnm.get(path, errors=[
            (500, "The specified serial number is not part of a vPC pair or any other internal server error.")],
                                             params={'serial_number': serial_number}))
        if 'vpc_pair_sn' in data["DATA"]:
            return data['DATA']['vpc_pair_sn']

        return None

    def get_switches_vpc_pairs(self):
        if not self.all_leaf_switches:
            raise DCNMSwitchesSwitchesParameterError("You must first run either get_all_switches or "
                                                     "get_switches_by_serial_numbers")
        for serial_number in self.all_leaf_switches:
            if serial_number not in self.all_switches_vpc_pairs:
                pair = self.get_vpc_pair(serial_number)
                if pair is not None:
                    peer1, peer2 = pair.split('~')
                    self.all_switches_vpc_pairs[peer1], self.all_switches_vpc_pairs[peer2] = peer2, peer1
                else:
                    self.all_switches_vpc_pairs[serial_number] = None

    def delete_switch_policies(self, policyId: Union[str, list]):
        if isinstance(policyId, str):
            path: str = f'/control/policies/{policyId}'
        elif isinstance(policyId, (list, tuple)):
            path: str = f'/control/policies/policyIds?policyIds={",".join(policyId)}'
        info = self._check_action_response(self.delete(path, errors=[
            (500, "Invalid payload or any other internal server error (e.g. policy does not exist)")]),
                                           "delete_switch_policies", "DELETE OF", policyId)
        return info

    @error_handler("ERROR: get_all_switches_detail: getting switch details for all switches")
    def get_all_switches_details(self) -> dict:
        local_all_switches_details: dict[tuple, dict] = {}

        path = '/inventory/switches'

        logger.info("get_all_switches_detail: getting switch details")
        response = self._check_response(self.get(path))
        # pprint(json.loads(response['MESSAGE']))
        for switch in json.loads(response['MESSAGE']):
            local_all_switches_details[switch["serialNumber"]] = switch
        return local_all_switches_details

    @error_handler("ERROR: get_fabric_swtiches_detail: getting switch details for all fabric switches")
    def get_fabric_switches_details(self, fabric:str) -> dict:
        local_all_switches_details: dict[tuple, dict] = {}

        path = f'/control/fabrics/{fabric}/inventory'

        logger.info("get_fabric_switches_detail: getting switch details for fabric {}".format(fabric))
        response = self._check_response(self.get(path))
        # pprint(json.loads(response['MESSAGE']))
        for switch in json.loads(response['MESSAGE']):
            local_all_switches_details[switch["serialNumber"]] = switch
        return local_all_switches_details

    def get_switches_details(self, serial_numbers: Optional[Union[list, tuple]] = None,
                               fabric: Optional[str] = None,
                               save_to_file: Optional[str] = None,
                               save_prev: bool = False):

        if self.all_switches_details and not save_prev:
            self.all_switches_details.clear()
        elif self.all_switches_details and save_prev:
            self.all_switches_details_prev = deepcopy(self.all_switches_details)
            self.all_switches_details.clear()

        if serial_numbers and isinstance(serial_numbers, str):
            serial_numbers = [serial_numbers]

        if fabric is not None and isinstance(fabric, str):
            switches = self.get_fabric_switches_details(fabric)
        elif fabric is not None:
            raise DCNMSwitchesSwitchesParameterError("fabric must be either None or a string")
        else:
            switches = self.get_all_switches_details()

        if serial_numbers and isinstance(serial_numbers, (list, tuple)):
            for sn in deepcopy(switches):
                if sn not in serial_numbers:
                    del switches[sn]

        self.all_switches_details = switches

        if save_to_file is not None:
            with open(save_to_file, 'w') as f:
                f.write(str(self.all_switches_details))

    @error_handler("ERROR: get_all_interfaces_detail: getting interface details for serial number")
    def get_all_interfaces_details(self, serial_number: Optional[str] = None, interface: Optional[str] = None):
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
            "allowAccessAdmin": true,
            "allowAccessAdminReason": null,
            "adminStatus": 1,
            "adminStatusStr": "up",
            "alias": "",
            "allowedVLANs": null,
            "channelId": -1,
            "channelIfIndex": -1,
            "complianceStatus": "In-Sync",
            "deleteReason": null,
            "description": "mgmt0",
            "duplex": null,
            "editBlockReason": null,
            "entityId": "FDO24261WAT~mgmt0",
            "fabricName": "site-2",
            "ifIndex": 83886080,
            "ifName": "mgmt0",
            "ifType": "INTERFACE_MGMT",
            "interfaceDbId": 5169890,
            "ipAddress": "10.0.7.22/24",
            "isDeletable": true,
            "isDiscovered": true,
            "isFex": "false",
            "isPhysical": "true",
            "isRbacAccessible": "true",
            "mgmtIpAddress": "10.0.7.22",
            "mode": null,
            "mtu": 1500,
            "nativeVlanId": -1,
            "neighbours": [],
            "operStatusCause": "ok",
            "operStatusStr": "up",
            "overlayNetwork": [],
            "platform": "N9K",
            "policyChangeSupported": true,
            "portChannelMemberList": null,
            "serialNo": "FDO24261WAT",
            "speedValue": 1000000000,
            "switchDbId": 5164810,
            "sysName": "cl4001",
            "underlayPolicies": [
              {
                "id": 5164430,
                "policyId": "POLICY-5164430",
                "templateName": "int_mgmt_11_1",
                "entityName": "mgmt0",
                "entityType": "INTERFACE",
                "status": "NA",
                "lastModified": 1647552899176,
                "source": "",
                "serialNumber": "FDO24261WAT",
                "policyTag": null,
                "autoGenerated": true
              }
            ],
            "vdcId": 0,
            "vdcName": null,
            "vpcId": 0,
            "vrf": "management",
            "priMemberIntfList": null,
            "secMemberIntfList": null,
            "blockConfig": false,
            "underlayPolicySource": "",
            "underlayPolicyTag": "[interface_edit_policy]",
            "interfaceGroup": null,
            "hasDeletedOverlay": false,
            "externalFabric": false,
            "discovered": true,
            "aafexPort": false,
            "groupAssocSupported": true,
            "editAllowed": true,
            "deletable": true,
            "markDeleted": false
          },
          {
            "allowAccessAdmin": true,
            "allowAccessAdminReason": null,
            "adminStatus": 1,
            "adminStatusStr": "up",
            "alias": "TEST1",
            "allowedVLANs": "none",
            "channelId": -1,
            "channelIfIndex": -1,
            "complianceStatus": "In-Sync",
            "deleteReason": null,
            "description": "Ethernet1/1",
            "duplex": null,
            "editBlockReason": null,
            "entityId": "FDO24261WAT~Ethernet1/1",
            "fabricName": "site-2",
            "ifIndex": 436207616,
            "ifName": "Ethernet1/1",
            "ifType": "INTERFACE_ETHERNET",
            "interfaceDbId": 5169940,
            "ipAddress": null,
            "isDeletable": true,
            "isDiscovered": true,
            "isFex": "false",
            "isPhysical": "true",
            "isRbacAccessible": "true",
            "mgmtIpAddress": "10.0.7.22",
            "mode": "trunk",
            "mtu": 9216,
            "nativeVlanId": -1,
            "neighbours": [
              {
                "sysName": "U19-N9396-1",
                "switchid": 0,
                "type": "LAN",
                "ifName": "Ethernet1/45",
                "connectedToStr": "U19-N9396-1 (Ethernet1/45)",
                "discovered": false
              }
            ],
            "operStatusCause": "ok",
            "operStatusStr": "up",
            "overlayNetwork": [],
            "platform": "N9K",
            "policyChangeSupported": true,
            "portChannelMemberList": null,
            "serialNo": "FDO24261WAT",
            "speedValue": 10000000000,
            "switchDbId": 5164810,
            "sysName": "cl4001",
            "underlayPolicies": [
              {
                "id": 5262840,
                "policyId": "POLICY-5262840",
                "templateName": "int_trunk_host_11_1",
                "entityName": "Ethernet1/1",
                "entityType": "INTERFACE",
                "status": "NA",
                "lastModified": 1652218783957,
                "source": "",
                "serialNumber": "FDO24261WAT",
                "policyTag": null,
                "autoGenerated": true
              }
            ],
            "vdcId": 0,
            "vdcName": null,
            "vpcId": 0,
            "vrf": null,
            "priMemberIntfList": null,
            "secMemberIntfList": null,
            "blockConfig": false,
            "underlayPolicySource": "",
            "underlayPolicyTag": "[interface_edit_policy]",
            "interfaceGroup": null,
            "hasDeletedOverlay": false,
            "externalFabric": false,
            "discovered": true,
            "aafexPort": false,
            "groupAssocSupported": true,
            "editAllowed": true,
            "deletable": true,
            "markDeleted": false
          }]

        """

        local_all_interfaces_details: dict[tuple, dict] = {}

        path = '/interface/detail'

        params = {'serialNumber': serial_number, 'ifName': interface}

        logger.info("get_all_interfaces_detail: getting interface details for serial number: {}".format(serial_number))
        response = self._check_response(self.get(path, params=params))
        #pprint(json.loads(response['MESSAGE']))

        for interface in json.loads(response['MESSAGE']):
            #print(interface)
            local_all_interfaces_details[(interface['ifName'], interface['serialNo'],)] = {
                'interface_name': interface['ifName'], 'interface_type': interface['ifType'],
                'fabric': interface['fabricName'], 'switch_name': interface['sysName'],
                'switch_serial': interface['serialNo'],
                'entity_id': interface['entityId'],
                'isPhysical': interface['isPhysical'],
                'interface_desc': interface['description'],
                'adminStatus': interface['adminStatusStr'],
                'operStatus': interface['operStatusStr'],
                'operStatusCause': interface['operStatusCause'],
                'fabricName': interface['fabricName']}
            if interface['underlayPolicies'] is not None:
                local_all_interfaces_details[(interface['ifName'], interface['serialNo'],)]['interface_policy'] = \
                    interface['underlayPolicies'][0]['templateName']
                local_all_interfaces_details[(interface['ifName'], interface['serialNo'],)]['policyId'] = \
                    interface['underlayPolicies'][0]['policyId']
            else:
                local_all_interfaces_details[(interface['ifName'], interface['serialNo'],)]['interface_policy'] = None
                local_all_interfaces_details[(interface['ifName'], interface['serialNo'],)]['policyId'] = None
        return local_all_interfaces_details

    def get_interfaces_details(self, serial_numbers: Optional[Union[list, tuple]] = None,
                               interface: Optional[str] = None,
                               policy: Optional[Union[str, list[str]]] = None,
                               oper: Optional[Union[str, list[str]]] = None,
                               physical: Optional[bool] = None,
                               save_to_file: Optional[str] = None,
                               save_prev: bool = False):
        """


        :param interface: interface or list of interfaces
        :type interface: str or list
        :param policy: name of a policy or a list of names
        :type policy: str or list
        :param oper: an operational state or list of operational states
        :type oper: str or list
        :param physical: true to get only physical interfaces, false to get only non-physical interfaces
        :type physical: bool
        :param serial_numbers: required list or tuple of switch serial numbers
        :type serial_numbers: list or tuple
        :param save_to_file: optional parameter, if None do not save, if str use as filename to save to
        :type save_to_file: None or str
        :param save_prev: if True and  attribute all_interfaces_nvpairs exists,
        copy to attribute all_interfaces_nvpairs_prev
        :type save_prev: bool

        pulls all interface detail information from dcnm for a list of serial numbers.
        saves to a dictionary of the following form with the attribute name all_interfaces_details

        {('mgmt0', 'FDO24261WAT'): {'interface_name': 'mgmt0', 'interface_type': 'INTERFACE_MGMT', 'fabric': 'site-2',
        'switch_name': 'cl4001', 'switch_serial': 'FDO24261WAT', 'entity_id': 'FDO24261WAT~mgmt0', 'isPhysical': 'true',
         'interface_desc': 'mgmt0', 'adminStatus': 'up', 'operStatus': 'up', 'operStatusCause': 'ok', 'fabricName':
         'site-2', 'interface_policy': 'int_mgmt_11_1', 'policyId': 'POLICY-5164430'}, ('Vlan100', 'FDO24261WAT'):
         {'interface_name': 'Vlan100', 'interface_type': 'INTERFACE_VLAN', 'fabric': 'site-2', 'switch_name':
         'cl4001', 'switch_serial': 'FDO24261WAT', 'entity_id': 'FDO24261WAT~Vlan100', 'isPhysical': 'false',
         'interface_desc': 'Vlan100', 'adminStatus': 'up', 'operStatus': 'up', 'operStatusCause': 'ok',
         'fabricName': 'site-2', 'interface_policy': None, 'policyId': None}}
        """

        if self.all_interfaces_details and not save_prev:
            self.all_interfaces_details.clear()
        elif self.all_interfaces_details and save_prev:
            self.all_interfaces_details_prev = deepcopy(self.all_interfaces_details)
            self.all_interfaces_details.clear()

        if serial_numbers and isinstance(serial_numbers, str):
            serial_numbers = [serial_numbers]

        if serial_numbers and isinstance(serial_numbers, (list, tuple)):

            for sn in serial_numbers:
                interfaces = self.get_all_interfaces_details(serial_number=sn, interface=interface)
                self.all_interfaces_details.update(interfaces)
        else:
            self.all_interfaces_details = self.get_all_interfaces_details(interface=interface)

        if isinstance(policy, str): policy = [policy]
        if isinstance(oper, str): oper = [oper]
        if policy or oper or physical:
            try:
                self.all_interfaces_details = DcnmInterfaces.get_filtered_interfaces_details(
                    self.all_interfaces_details,
                    policy=policy, oper=oper, physical=physical)
                # logger.debug("get_interfaces_nvpairs: {}".format(self.all_interfaces_nvpairs))
            except DCNMParamaterError:
                logger.critical("ERROR: get_interfaces_detail: serial_numbers must be a string or a list of strings\n"
                                "policy must be a string or a list of strings\n"
                                "oper must be a string or a list of strings")
                raise DCNMInterfacesParameterError("serial_numbers must be a string or a list of strings\n"
                                                   "policy must be a string or a list of strings\n"
                                                   "oper must be a string or a list of strings")

        if save_to_file is not None:
            with open(save_to_file, 'w') as f:
                f.write(str(self.all_interfaces_details))


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
    def deploy_switch_config(self, serial_number: str, fabric: Optional[str] = None, deploy_timeout: int = 300) -> bool:
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
        temp_timers = self.timeout
        self.timeout = deploy_timeout
        info = self._check_action_response(self.post(path, errors=[(400, "Invalid value supplied"),
                                                                   (500,
                                                                    "Invalid payload or any other internal server error")]),
                                           "desploy_switch_config", "CONFIG SAVE OF {} switch".format(fabric),
                                           serial_number)
        self.timeout = temp_timers
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
    def deploy_interfaces(self, payload: Union[list, dict], deploy_timeout: int = 300) -> Optional[bool]:
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
    def deploy_fabric_config(self, fabric: str, deploy_timeout: int = 300) -> Optional[bool]:
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
    def deploy_policies(self, policies: list, deploy_timeout: int = 300) -> Optional[bool]:
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

    @error_handler("ERROR: get_fabric_id: failed getting fabric ids")
    def get_fabric_id(self):
        """
        Provide the name of a fabric, details are stored in object variable fabrics. API call returns
        a dictionary similar to the below example.

                [
            {
                "fabricId": 16,
                "fabricName": "site-4",
                "fabricType": "Switch_Fabric",
                "fabricState": "member",
                "fabricParent": "data_center_1",
                "fabricTechnology": "VXLANFabric"
            },
            {
                "fabricId": 18,
                "fabricName": "site-3",
                "fabricType": "Switch_Fabric",
                "fabricState": "member",
                "fabricParent": "data_center_1",
                "fabricTechnology": "VXLANFabric"
            },
            {
                "fabricId": 19,
                "fabricName": "data_center_1",
                "fabricType": "MSD",
                "fabricState": "msd",
                "fabricParent": "None",
                "fabricTechnology": "VXLANFabric"
            },
            {
                "fabricId": 4,
                "fabricName": "site-2",
                "fabricType": "Switch_Fabric",
                "fabricState": "member",
                "fabricParent": "data_center_1",
                "fabricTechnology": "VXLANFabric"
            },
            {
                "fabricId": 20,
                "fabricName": "test",
                "fabricType": "External",
                "fabricState": "standalone",
                "fabricParent": "None",
                "fabricTechnology": "External"
            },
            {
                "fabricId": 21,
                "fabricName": "TestLanFabric",
                "fabricType": "External",
                "fabricState": "standalone",
                "fabricParent": "None",
                "fabricTechnology": "LANClassic"
            }
        ]
        """

        path = f'/control/fabrics/msd/fabric-associations'

        logger.info("get_fabric_details: getting fabric ids for")
        response = self._check_response(self.get(path))

        for fabric in json.loads(response['MESSAGE']):
            self.fabrics[fabric['fabricName']] = fabric

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

    def get_switches_status(self, serial_numbers: Optional[Union[str, list[str]]] = None) -> dict[str, str]:
        local_status: dict[str, list] = {}
        result_status: dict[str, str] = {}
        if serial_numbers:
            if isinstance(serial_numbers, str):
                serial_numbers = [serial_numbers]
        else:
            if self.all_leaf_switches or self.all_notleaf_switches:
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
                self.get_fabric_id()
            fabric_id: str = self.fabrics[fabric]["fabricId"]
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
        if string_to_check is None:
            return False
        elif not isinstance(string_to_check, (str, dict)):
            logger.error("_check_patterns: failure: string_to_check wrong type {}".format(string_to_check))
            raise DCNMParamaterError("string_to_check must be a string or a dictionary")
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

    @staticmethod
    def get_filtered_interfaces_details(interfaces_details, policy, oper, physical):
        interfaces_details_local = deepcopy(interfaces_details)

        if isinstance(policy, str): policy = [policy]
        if isinstance(oper, str): oper = [oper]
        try:
            for interface, interface_policy in deepcopy(interfaces_details_local).items():
                if policy:
                    if not DcnmInterfaces._check_patterns(policy, interface_policy['interface_policy']):
                        del interfaces_details_local[interface]
                        continue

                if oper:
                    if not DcnmInterfaces._check_patterns(oper, interface_policy['operStatus']):
                        del interfaces_details_local[interface]
                        continue

                if physical is not None:
                    if interface_policy['isPhysical'] is not physical:
                        del interfaces_details_local[interface]
                        continue

        except DCNMParamaterError:
            logger.error("ERROR: get_filtered_interfaces_details: Failed filtering details dictionary for {}".format(
                interfaces_details))
            logger.error(
                "ERROR: get_filtered_interfaces_details: Error in filters: policy {} or oper {}".format(
                    policy, oper))
            raise DCNMInterfacesParameterError("serial_numbers must be a string or a list of strings\n"
                                               "policy must be a string or a list of strings\n"
                                               "oper must be a string or a list of strings")
        return interfaces_details_local


if __name__ == '__main__':
    ADDRESS = None
    USERNAME = None
    PASSWORD = None
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
    dcnm = DcnmInterfaces(ADDRESS, dryrun=True)
    dcnm.login(username=USERNAME, password=PASSWORD)

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

    print('=' * 40)
    print()

    # Fallback
    print()
    print('=' * 40)
    print("YOU WANT TO FALLBACK?")
    with open('interfaces_existing_conf.pickle', 'rb') as f:
        interfaces_existing_conf = load(f)
    pprint(interfaces_existing_conf)
    with open('switches_configuration_policies.pickle', 'rb') as f:
        interface_desc_policies: dict[str, list] = load(f)
    pprint(interface_desc_policies)
    policies_ids: list = []
    for serial_number in interface_desc_policies:
        for policy in interface_desc_policies[serial_number]:
            dcnm.post_new_policy(policy)
            policies_ids.append([policy["policyId"]])
    print('=' * 40)
    print("FALLBACK")
    print('=' * 40)
    dcnm.wait_for_switches_status(serial_numbers=['FDO24261WAT', 'FDO242702QK'])
    print('=' * 40)
    dcnm.get_interfaces_details(serial_numbers=['FDO24261WAT'], oper='up')
    print(dcnm.all_interfaces_details)
    print('=' * 40)
    pprint(dcnm.get_all_switches_details())
    print('=' * 40)
    print('=' * 40)
    pprint(dcnm.get_fabric_switches_details('site-2'))
    print('=' * 40)
    print("FINISHED. GO GET PLASTERED!")
    print('=' * 40)
