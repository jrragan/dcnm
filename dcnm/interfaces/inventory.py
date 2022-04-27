import json
import logging
from copy import deepcopy
from typing import Optional, Union

import pandas
from pandas import read_excel

from dcnm_connect import HttpApi


class DcnmFabricInventory(HttpApi):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.inventory: dict = {}
        self.serial_numbers: dict = {}
        self.switch_names: dict = {}
        self.fabric_data: dict = {}
        self.fabrics: list[str] = []
        self.all_leaf_switches: list[str] = []
        self.all_notleaf_switches: list[str] = []
        self.all_interfaces: dict[tuple, dict] = {}
        self.all_interfaces_nvpairs: dict[tuple, dict] = {}

    def get_fabrics(self):
        path = '/control/fabrics'
        info = self.get(path)
        self.fabrics = [fabric['fabricName'] for fabric in info['DATA']]
        # print(info)

    def get_fabric_inventory_details(self, fabric: str):

        rc = False
        method = 'GET'
        path = '/control/fabrics/{}/inventory'.format(fabric)

        info = self.get(path)

        self.switch_names[fabric] = {device_data['logicalName']: device_data['serialNumber'] for device_data in
                                     info['DATA']}
        self.serial_numbers[fabric] = {device_data['serialNumber']: device_data['logicalName'] for device_data in
                                       info['DATA']}
        self.inventory[fabric] = {(device_data['logicalName'], device_data['serialNumber']): device_data for device_data
                                  in
                                  info['DATA']}
        # for device_data in info['DATA']:
        #     print(device_data)
        #     key = (device_data.get('logicalName'), device_data.get('serialNumber'))
        #     self.inventory[fabric] = {}
        #     self.serial_numbers[fabric] = {}
        #     self.inventory[fabric][key] = device_data
        #     print(device_data['serialNumber'], device_data['logicalName'])
        #     self.serial_numbers[fabric][device_data['serialNumber']] = device_data.get('logicalName')
        # print(self.serial_numbers)
        # print(self.switch_names)

    def get_all_switches(self):
        path = '/inventory/switches'

        response = self.get(path)
        for switch in json.loads(response['MESSAGE']):
            if switch['switchRole'] == 'leaf':
                self.all_leaf_switches.append(switch['serialNumber'])
            else:
                self.all_notleaf_switches.append(switch['serialNumber'])

    def get_switch_serial(self, fabric: str, switch_name: str):
        # print(fabric)
        # print(switch_name)
        # print(self.switch_names)
        if fabric in self.switch_names:
            return self.switch_names[fabric].get(switch_name, None)
        self.get_fabric_inventory_details(fabric)
        return self.switch_names[fabric].get(switch_name, None)

    def get_switch_name(self, fabric: str, serial: str):
        if fabric in self.switch_names:
            return self.serial_numbers[fabric].get(serial, None)
        self.get_fabric_inventory_details(fabric)
        return self.serial_numbers[fabric].get(serial, None)

    # This call is used to get the details of the given fabric from the DCNM
    def get_fabric_details(self, fabric: str):
        """
        Used to get the details of the given fabric from the DCNM
        Parameters:
            module: Data for module under execution
            fabric: Fabric name
        Returns:
            dict: Fabric details
        """
        path = '/control/fabrics/{}'.format(fabric)

        response = self.get(path)
        self.fabric_data[fabric] = response.get('DATA')

    def get_all_interfaces_detail(self, serial_no: Optional[str] = None, interface: Optional[str] = None):
        path = '/globalInterface'

        params = {'serialNumber': serial_no, 'ifName': interface}

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

    def get_all_interfaces_nvpairs(self, serial_no: Optional[str] = None, interface: Optional[str] = None):
        path = '/interface'

        params = {'serialNumber': serial_no, 'ifName': interface}

        response = self.get(path, params=params)
        for policy in json.loads(response['MESSAGE']):
            for interface in policy['interfaces']:
                # print(interface)
                self.all_interfaces_nvpairs[(interface['ifName'], interface['serialNumber'])] = {
                    'policy': policy['policy'], 'interfaces': [
                        interface
                    ]
                }
        # print(all_interfaces)


class ExcelFileError(Exception):
    pass


def read_existing_descriptions(file: str) -> dict[tuple, str]:
    # wb = load_workbook(filename = file, read_only=True)
    # ws = wb.active
    existing_descriptions_local: dict
    # for row in ws.iter_rows(values_only=True):
    #     existing_descriptions[(row[0], row[1])] = row[2]
    logger.debug("reading excel file {}".format(file))
    df: pandas.DataFrame = read_excel(file)
    # print(df)
    # print(df.columns)
    df.columns = df.columns.str.lower()
    # print(df)
    if 'description' not in df.columns or 'interface' not in df.columns or 'switch' not in df.columns:
        raise ExcelFileError('One or more columns missing')
    existing_descriptions_local = df.to_dict('records')
    # print(existing_descriptions)
    existing_descriptions_local = {(interface['interface'], interface['switch']): interface['description'] for interface
                                   in
                                   existing_descriptions_local}
    logger.debug(existing_descriptions_local)
    return existing_descriptions_local


def get_interfaces_to_change(dcnm: DcnmFabricInventory, existing_descriptions: dict[tuple, str]) -> dict[tuple, dict]:
    interfaces_to_change: dict[tuple, dict] = {}
    for interface, details in dcnm.all_interfaces_nvpairs.items():
        change_cdp: bool = False
        change_desc: bool = False
        if interface[1] in dcnm.all_leaf_switches:
            # print(details)
            if ('ethernet' in details['interfaces'][0]['ifName'].lower() or
                'mgmt' in details['interfaces'][0]['ifName'].lower()) and 'fabric' not in details['policy']:
                change_desc = get_desc_change(interface, details, existing_descriptions)
                change_cdp = get_cdp_change(interface, details)
        else:
            if 'mgmt' not in interface[0]:
                continue
            else:
                change_cdp = get_cdp_change(interface, details)
        if change_desc or change_cdp:
            interfaces_to_change[interface] = details
    logger.debug("Interfaces to change: {}".format(interfaces_to_change))
    return interfaces_to_change


def get_desc_change(interface: tuple, detail: dict, existing_descriptions: dict[tuple, str]) -> bool:
    # get desc changes
    if interface in existing_descriptions:
        logger.debug("interface: {}, new description: {}, old description: {}".format(interface,
                                                                                      existing_descriptions[interface],
                                                                                      detail['interfaces'][0][
                                                                                          'nvPairs']['DESC']))
        detail['interfaces'][0]['nvPairs']['DESC'] = existing_descriptions[interface]
        return True
    return False


def get_cdp_change(interface: tuple, detail: dict) -> bool:
    # get cdp changes
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
            detail['interfaces'][0]['nvPairs']['CONF'] = '{}\\n{}'.format(
                detail['interfaces'][0]['nvPairs']['CONF'],
                'no cdp enable')
            logger.debug("interface: {}, changing cdp".format(interface))
            logger.debug("multiple CONF: {}".format(detail['interfaces'][0]['nvPairs']['CONF']))
            return True
    return False


def put_interface(dcnm: DcnmFabricInventory, interface: tuple, details: dict) -> bool:
    path: str = '/interface'
    info = dcnm.put(path, data=details, errors=[
        (500, "Invalid payload or any other internal server error")])
    logger.debug("put_interface info: {}", format(info))
    if info["RETURN_CODE"] != 200:
        logger.critical("CREATION OF {} FAILED".format(interface))
        logger.debug(details)
        return False
    return True


def put_interface_changes(dcnm: DcnmFabricInventory, interfaces_will_change: dict[tuple, dict]):
    interfaces_will_change_local: dict[tuple, dict] = deepcopy(interfaces_will_change)
    failed: set = set()
    success: set = set()
    for interface, details in interfaces_will_change_local.items():
        result = put_interface(dcnm, interface, details)
        if not result:
            logger.critical("Failed putting new interface configuration for {}".format(interface))
            logger.critical(details)
            failed.add(interface)
        elif result:
            logger.info("{} successfully changed. Yay.".format(interface))
            logger.debug(details)
            success.add(interface)
        else:
            logger.critical("Don't know what happened: {}".format(result))
            logger.critical("{} : {}".format(interface, details))
            failed.add(interface)


def deploy_vpc(dcnm: DcnmFabricInventory, payload=Union[list, dict]) -> Optional[bool]:
    path = '/globalInterface/deploy'
    if isinstance(payload, dict):
        payload = [payload]
    temp_timers = dcnm.timeout
    dcnm.timeout = 300
    info = dcnm.post(path, data=payload)
    if info["RETURN_CODE"] != 200:
        logger.debug(info)
        logger.critical("DEPLOY OF {} FAILED".format(payload))
        dcnm.timeout = temp_timers
        return False
    dcnm.timeout = temp_timers
    return True


if __name__ == '__main__':
    SCREENLOGLEVEL = logging.DEBUG
    FILELOGLEVEL = logging.DEBUG
    logformat = logging.Formatter(
        '%(asctime)s: %(process)d - %(threadName)s - %(funcName)s - %(name)s - %(levelname)s - message: %(message)s')

    logging.basicConfig(level=SCREENLOGLEVEL,
                        format='%(asctime)s: %(process)d - %(threadName)s - %(funcName)s - %(name)s - %(levelname)s - message: %(message)s')

    # screen handler
    # ch = logging.StreamHandler()
    # ch.setLevel(SCREENLOGLEVEL)
    # ch.setFormatter(logformat)
    #
    # logging.getLogger('').addHandler(ch)

    logger = logging.getLogger('dcnm')

    logger.critical("Started")
    # prompt stdin for username and password
    dcnm = DcnmFabricInventory("10.0.17.99")
    dcnm.login(username="rragan", password="MVhHuBr3")
    # info = dcnm.get_all_interfaces(filter='vpc')
    # info = dcnm.get_all_interfaces()
    # print(info)
    dcnm.get_fabrics()
    # print(dcnm.fabrics)
    # dcnm.get_all_interfaces_detail()
    # print(dcnm.all_interfaces)
    dcnm.get_all_interfaces_nvpairs()
    # print(dcnm.all_interfaces_nvpairs)
    dcnm.get_all_switches()
    # print(len(dcnm.all_leaf_switches))
    # print(dcnm.all_leaf_switches)
    existing_descriptions = read_existing_descriptions('interface_descriptions.xlsx')
    # print(existing_descriptions)

    interfaces_will_change: dict[tuple, dict] = get_interfaces_to_change(dcnm, existing_descriptions)

    print('=' * 40)
    with open('interfaces_will_change.json', 'w') as f:
        f.write(str(interfaces_will_change))

    # pprint(interfaces_will_change)

    # make changes
    # put_interface_changes(dcnm, interfaces_will_change)
