import json
import logging
from collections import defaultdict
from copy import deepcopy
from pickle import dump
from pprint import pprint
from time import time, sleep
from typing import Optional, Union, Dict, List, Tuple

from DCNM_errors import DCNMInterfacesParameterError, DCNMSwitchesPoliciesParameterError, \
    DCNMParameterError, DCNMSwitchesSwitchesParameterError, DCNMSwitchStatusParameterError, DCNMSwitchStatusError
from DCNM_connect import DcnmRestApi
from DCNM_utils import error_handler, _check_response, spinner, get_info_from_policies_config
from plugin_utils import PlugInEngine
from handler import DcnmComponent, Handler
from filters import filterfactory

logger = logging.getLogger(__name__)


class Switch:
    def __init__(self, serial_number: str, switchRole: str, fabricName: str):
        self.serialNumber = serial_number
        self.peerSerialNumber: Optional[str] = None
        self.switchRole = switchRole
        self.fabricName = fabricName
        self.policies: List[Dict] = []
        self.policies_prev: List[Dict] = []

    def add_details(self, details: dict):
        self.__dict__.update(details)

    def add_policies(self, policies):
        if isinstance(policies, list):
            self.policies = self.policies + policies
        elif isinstance(policies, dict):
            self.policies.append(policies)

    def clear_policies(self):
        self.policies = []

    def save_policies(self):
        self.policies_prev = list(deepcopy(self.policies))

    def __str__(self):
        output_str = ""
        for key, item in self.__dict__.items():
            output_str = f"{output_str}\n{key} = {item}"
        return output_str

    def __getitem__(self, key):
        return self.__getattribute__(key)

    def __setitem__(self, key, value):
        self.__setattr__(key, value)

    def __delitem__(self, key):
        self.__delattr__(key)

    def __missing__(self, key):
        raise KeyError(f"Missing some case variant of {key!r}")

    def __iter__(self):
        return iter(list(self.__dict__.items()))

    def __repr__(self):
        return f'{type(self).__name__}({self.serialNumber!r}, {self.switchRole!r}, {self.fabricName!r})'


class DcnmSwitches(DcnmComponent):
    def __init__(self, handler: Handler, dcnm_connector: DcnmRestApi):
        super().__init__(handler, dcnm_connector)
        self.switches: dict = {}
        self._all_leaf_switches: Optional[List[str]] = None
        self._all_notleaf_switches: Optional[List[str]] = None
        self.all_switches_vpc_pairs: bool = False
        self.all_switches_details: bool = False
        self.all_switches_policies: bool = False
        self.all_switches_policies_prev: bool = False
        self._switches_policies = defaultdict(list)
        self._switches_policies_prev = defaultdict(list)

    @error_handler("ERROR getting switch serial numbers")
    def get_all_switches(self):
        """
        Pulls all switch serial numbers from DCNM inventory

        stores result in two attributes of the form {SN: fabric_name}
        all_leaf_switches
        all_notleaf_switches

        """
        logger.info("get all switches")
        if self.all_leaf_switches:
            self.all_leaf_switches.clear()
        if self.all_notleaf_switches:
            self.all_notleaf_switches.clear()
        self.switches.clear()
        self.all_switches_vpc_pairs: bool = False
        self.all_switches_details: bool = False
        self.all_switches_policies: bool = False
        self.all_switches_policies_prev: bool = False
        self._switches_policies.clear()
        self._switches_policies_prev.clear()

        path = '/inventory/switches'

        response = _check_response(self.dcnm.get(path))
        self.switch_factory(response)

    def switch_factory(self, response):
        for switch in json.loads(response['MESSAGE']):
            role = switch.get('switchRole')
            if role is None:
                role = switch.get('role')
            self.switches[switch['serialNumber']] = Switch(switch['serialNumber'], role,
                                                           switch.get('fabricName',
                                                                      self.get_switch_fabric(
                                                                          switch['serialNumber'])))

    @error_handler("ERROR:  get_switches_by_serial_number: getting switch roles for serial number")
    def get_switches_by_serial_number(self, serial_numbers: Optional[list] = None, clear_prev=False):
        if serial_numbers and not isinstance(serial_numbers, (list, tuple)):
            raise DCNMInterfacesParameterError('serial_numbers must be a list or a tuple')
        elif serial_numbers and isinstance(serial_numbers, (list, tuple)):
            if clear_prev:
                if self.all_leaf_switches:
                    self.all_leaf_switches.clear()
                if self.all_notleaf_switches:
                    self.all_notleaf_switches.clear()
                self.switches.clear()
                self.all_switches_vpc_pairs: bool = False
                self.all_switches_details: bool = False
                self.all_switches_policies: bool = False
                self.all_switches_policies_prev: bool = False
                self._switches_policies.clear()
                self._switches_policies_prev.clear()

            path = '/control/switches/roles'
            params = {'serialNumber': ','.join(serial_numbers)}
            logger.info("get_switches_by_serial_number: for serial numbers: {}".format(serial_numbers))
            response = _check_response(self.dcnm.get(path, params=params))

            self.switch_factory(response)
        else:
            self.get_all_switches()

    @property
    def all_leaf_switches(self):
        if not self._all_leaf_switches:
            self._all_leaf_switches = [serial for serial, obj in self.switches.items() if obj.switchRole == "leaf"]
        return self._all_leaf_switches

    @property
    def all_notleaf_switches(self):
        if not self._all_notleaf_switches:
            self._all_notleaf_switches = [serial for serial, obj in self.switches.items() if obj.switchRole != "leaf"]
        return self._all_notleaf_switches

    @property
    def switches_policies(self):
        if not self._switches_policies:
            self._switches_policies = {serial_number: switch.policies
                                       for serial_number, switch in self.switches.items() if switch.policies}
        return self._switches_policies

    @property
    def switches_policies_prev(self):
        if not self.all_switches_policies_prev:
            self._switches_policies_prev = {serial_number: switch.policies_prev
                                            for serial_number, switch in self.switches.items()}
        return self._switches_policies_prev

    def get_switch(self, serial_number):
        return self.switches.get(serial_number)

    def delete_switch(self, serial_number):
        if serial_number in self.switches:
            del self.switches[serial_number]

    def get_switch_policies(self, serial_number):
        switch =  self.switches.get(serial_number)
        return switch.policies

    def delete_switch_policies(self, serial_number):
        if serial_number in self.switches:
            self.switches[serial_number].policies.clear()

    @error_handler("ERROR: get_switches_policies: getting switch policies for serial number")
    def get_switches_policies(self, serial_numbers: Optional[Union[str, list]] = None, fabric: Optional[str] = None,
                              description: Optional[Union[str, list]] = None,
                              entityName: Optional[str] = None,
                              entityType: Optional[str] = None,
                              templateName: Optional[Union[str, list]] = None,
                              generatedConfig: Optional[Union[str, list]] = None,
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
        :param generatedConfig: optional regex str
        :type generatedConfig: str or None
        :param save_to_file: optional parameter, if None do not save, if str use as filename to save to
        :type save_to_file: None or str
        :param save_prev: if True and  attribute all_switches_policies exists,
        copy to attribute all_switches_policies_prev
        :type save_prev: bool
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
            for switch in self.switches:
                switch.clear_policies()
        elif self.all_switches_policies and save_prev:
            for switch in self.switches:
                switch.save_policies()
                switch.clear_policies()
                self.all_switches_policies_prev = True

        if isinstance(description, str):
            description = [description]
        if isinstance(templateName, str):
            templateName = [templateName]
        if isinstance(generatedConfig, str):
            generatedConfig = [generatedConfig]
        filter_dict = {'description': description, 'entityName': entityName,
                       'entityType': entityType, 'templateName': templateName, 'generatedConfig': generatedConfig}
        filters = filterfactory(filter_dict)

        for sn, switch in self.switches.items():
            if switch.policies and not save_prev:
                switch.clear_policies()
            elif switch.policies and save_prev:
                switch.save_policies()
                switch.clear_policies()

        path = '/control/policies/switches'

        params = self.determine_parameters(serial_numbers)

        logger.info("get_switches_policies: getting switch policies for serial number: {}".format(serial_numbers))
        response = _check_response(self.dcnm.get(path, params=params))

        all_switches_policies: defaultdict[List] = defaultdict(list)
        for policy in json.loads(response['MESSAGE']):
            all_switches_policies[policy['serialNumber']].append(policy)
        logger.debug(list(all_switches_policies.keys()))

        if fabric:
            for sn, policy in deepcopy(all_switches_policies).items():
                if self.switches.get(sn) is not None and self.switches.get(sn).fabricName != fabric:
                    del all_switches_policies[sn]

        if filters:
            logger.debug(f"filters: {filters}")
            try:
                for sn, policy_list in deepcopy(all_switches_policies).items():
                    # logger.debug(f"filters checking {sn}")
                    for policy in deepcopy(policy_list):
                        logger.debug(f"checking policy {policy}")
                        if not all(f.match(policy) for f in filters):
                            # logger.debug(f"deleting policy {policy}")
                            all_switches_policies[sn].remove(policy)
            except DCNMParameterError:
                raise DCNMSwitchesPoliciesParameterError("description must be a string or a list of strings\n"
                                                         "templateName must be a string or a list of strings\n"
                                                         "config must be a string or a list of strings")
            except DCNMSwitchesPoliciesParameterError:
                raise

        logger.debug(f"get_switches_policies: policies after filtering: {all_switches_policies}")
        # remove empty keys and save to switch objects
        for sn, policies in deepcopy(all_switches_policies).items():
            if not all_switches_policies[sn]:
                del all_switches_policies[sn]
            else:
                logger.debug(f"get_switches_policies: adding policies to switch object")
                logger.debug(f"switch {sn}, policies {policies}")
                self.switches[sn].add_policies(policies)

        self.all_switches_policies = True

        if save_to_file is not None:
            with open(save_to_file, 'w') as f:
                f.write(str(self.switches_policies))

    def determine_parameters(self, serial_numbers):
        if serial_numbers and isinstance(serial_numbers, (list, tuple)):
            params = {'serialNumber': ','.join(serial_numbers)}
        elif serial_numbers and isinstance(serial_numbers, str):
            params = {'serialNumber': serial_numbers}
        elif not self.all_leaf_switches and not self.all_notleaf_switches:
            raise DCNMSwitchesPoliciesParameterError("Provide either a list of serial numbers or first run either"
                                                     "get_all_switches or get_switches_by_serial_numbers")
        else:
            params = {'serialNumber': ','.join(list(self.switches.keys()))}
        return params

    @error_handler("ERROR: get_vpc_pair: getting vpc pairs for serial number")
    def get_vpc_pair(self, serial_number: str) -> Optional[str]:
        """ Get vpc pair data from api and return data structure """

        path = "/interface/vpcpair_serial_number"
        data = _check_response(self.dcnm.get(path, errors=[
            (500, "The specified serial number is not part of a vPC pair or any other internal server error.")],
                                             params={'serial_number': serial_number}))
        if 'vpc_pair_sn' in data["DATA"]:
            return data['DATA']['vpc_pair_sn']

        return None

    def get_switches_vpc_pairs(self):
        if not self.switches:
            raise DCNMSwitchesSwitchesParameterError("You must first run either get_all_switches or "
                                                     "get_switches_by_serial_numbers")
        for serial_number, switch in self.switches.items():
            if not hasattr(switch, "peerSerialNumber"):
                pair = self.get_vpc_pair(serial_number)
                if pair is not None:
                    peer1, peer2 = pair.split('~')
                    self.switches[peer1].peerSerialNumber = peer2
                    self.switches[peer2].peerSerialNumber = peer1
                else:
                    self.switches[serial_number].peerSerialNumber = None
        self.all_switches_vpc_pairs = True

    def get_switches_details(self, serial_numbers: Optional[Union[List[str], Tuple[str], str]] = None,
                             fabric: Optional[str] = None,
                             save_to_file: Optional[str] = None):

        if serial_numbers and isinstance(serial_numbers, str):
            serial_numbers = [serial_numbers]
        elif serial_numbers is None:
            serial_numbers = list(self.switches.keys())
        elif serial_numbers and not isinstance(serial_numbers, (list, tuple)):
            logger.critical(
                "ERROR: get_switches_details: serial number must be a string or a list or tuple of strings")
            raise DCNMSwitchesSwitchesParameterError("serial number must be a string or a list or tuple of strings")
        else:
            logger.critical(
                "ERROR: get_switches_details: Unknown Error in compiling serial numbers. Unable to complete.")
            raise DCNMSwitchesSwitchesParameterError("get_switches_details: something went wrong. Unable to complete.")

        fabric_set = set()
        if fabric is not None and isinstance(fabric, str):
            fabric_set.add(fabric)
        elif fabric is not None:
            logger.critical(
                "ERROR: get_switches_details: fabric must be either None or a string")
            raise DCNMSwitchesSwitchesParameterError("fabric must be either None or a string")
        elif fabric is None:
            for serial_number in serial_numbers:
                fabric_set.add(self.switches[serial_number].fabricName)
        else:
            logger.critical(
                "ERROR: get_switches_details: Error compiling fabrics. Unable to complete.")
            raise DCNMSwitchesSwitchesParameterError("get_switches_details: something went wrong. Unable to complete.")

        switches_details: Dict[tuple, dict] = {}
        for fabric in fabric_set:
            switches_details.update(self.get_fabric_switches_details(fabric))

        for sn, switch in self.switches:
            switch.add_details(switches_details[sn])

        if save_to_file is not None:
            with open(save_to_file, 'w') as f:
                f.write(str(switches_details))

        self.all_switches_details = True

    def get_switches_status(self, serial_numbers: Optional[Union[str, List[str]]] = None) -> Dict[str, str]:
        logger.info("get switches status")
        local_status: Dict[str, list] = {}
        result_status: Dict[str, str] = {}
        if serial_numbers:
            if isinstance(serial_numbers, str):
                serial_numbers = [serial_numbers]
        else:
            if self.switches:
                serial_numbers = list(self.switches.keys())
            else:
                logger.critical(
                    "ERROR: get_switches_status: One of the get switches "
                    "methods must be run if a list of serial numbers\n"
                    "is not provided.")
                raise DCNMSwitchStatusParameterError("Must provide a serial number or a list of serial numbers\n"
                                                     "Or get_all_switches or get_switches_by_serial_number\n"
                                                     "Must have prevously been run!")
        for serial_number in serial_numbers:
            fabric: str = self.switches[serial_number].fabricName
            if fabric in local_status:
                continue
            if fabric not in self.fabrics:
                self.get_fabric_id()
            fabric_id: str = self.fabrics[fabric]["fabricId"]
            path = f'/control/status?entityTypeFilter=SWITCH&fabricId={fabric_id}'
            response = self.dcnm.get(path)
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
                                 serial_numbers: Optional[Union[str, List[str]]] = None) -> Union[bool, dict]:
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


if __name__ == 'main':
    print('top')
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

    logger = logging.getLogger('dcnmswitches')

    print("starting")
    logger.critical("Started")
    # prompt stdin for username and password
    dcnm = DcnmRestApi(ADDRESS, dryrun=True)
    dcnm.logon(username=USERNAME, password=PASSWORD)
    plugins = PlugInEngine()
    handler = Handler(dcnm)
    # handler.get_interfaces_nvpairs(save_to_file='all_interfaces.json', serial_numbers=['FDO24261WAT', 'FDO242702QK'])
    # pprint(handler.all_interfaces_nvpairs)
    # dcnm.get_all_switches()
    handler.get_switches_by_serial_number(serial_numbers=['FDO24261WAT', 'FDO242702QK'])
    print("=" * 40)
    print(len(handler.all_leaf_switches))
    print(handler.all_leaf_switches)
    # existing_descriptions = read_existing_descriptions('interface_descriptions.xlsx')
    # print(existing_descriptions)

    # dcnm.get_switches_policies(serial_numbers=['9Y04VBM75I8', '9A1R3QS819Z'])
    # print("=" * 40)
    # pprint(dcnm.all_switches_policies)

    # dcnm.get_switches_policies(serial_numbers=['9Y04VBM75I8'], templateName='switch_freeform\Z')
    # pprint(dcnm.all_switches_policies)
    #
    handler.get_switches_policies(templateName=r'switch_freeform\Z',
                                  config=r"interface\s+[a-zA-Z]+\d+/?\d*\n\s+description\s+")
    print("=" * 40)
    pprint(handler.switches_policies)

    existing_descriptions_from_policies: list = get_info_from_policies_config(handler.switches_policies,
                                                                              r"interface\s+([a-zA-Z]+\d+/?\d*)\n\s+description\s+(.*)")

    print("=" * 40)
    pprint(existing_descriptions_from_policies)
    with open('switches_configuration_policies.pickle', 'wb') as f:
        dump(handler.switches_policies, f)
    policy_ids: set = {c.policyId for c in existing_descriptions_from_policies}
    print(policy_ids)
