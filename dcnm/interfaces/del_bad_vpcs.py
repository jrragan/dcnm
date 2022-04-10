# Disable Cert Check Validation Errors
import csv
import logging
from pprint import pprint
from typing import Optional, Union

from inventory import DcnmFabricInventory
from utils import command_args, validate_csv_rows, _dbg

logger = logging.getLogger('del_bad_vpcs')

CSV_REQUIRED_KEYS = [
    "fabric",
    "switchName"]


class ParamError(Exception):
    """ Exception raised for incorrect params """
    pass


class ParamInterfaceError(ParamError):
    """ Exception raised for incorrect interface params """
    pass


# Deletes intent from DCNM but doesnt deploy to the switches
def mark_delete_vpc(dcnm: DcnmFabricInventory, entry: dict) -> Optional[bool]:
    path = "/interface/markdelete"
    interfaces = [
        {
            "serialNumber": entry["vpcPair"],
            "ifName": "vpc%s" % entry["vpcId"]
        }
    ]

    ifName = "vpc%s" % entry["vpcId"]
    logger.info("delete existing vpc interface %s" % ifName)
    logger.debug(entry)
    logger.debug("json payload: {}".format(interfaces))
    info = dcnm.delete(path, data=interfaces, errors=[(500, "Invalid payload or any internal server error")])
    if info["RETURN_CODE"] != 200:
        logger.debug(info)
        logger.critical("DELETE OF {} FAILED".format(ifName))
        return False
    return True


def get_vpc_pair(dcnm: DcnmFabricInventory, serialNumber: str) -> Optional[str]:
    """ Get vpc pair data from api and return data structure """

    path = "/interface/vpcpair_serial_number"
    data = dcnm.get(path, errors=[
        (500, "The specified serial number is not part of a vPC pair or any other internal server error.")],
                    params={'serial_number': serialNumber})
    if 'vpc_pair_sn' in data["DATA"]:
        return data['DATA']['vpc_pair_sn']

    return None


def csv_to_module_params(dcnm: DcnmFabricInventory, csv_rows: list) -> dict:
    """ convert csv rows (one row per interface) to ansible style params

        module_params = {
            'fabric_vpcpair_id': {
                'vpcPair': 'peer1serialNum~peer2serialNum',
                    # retrieved from dcnm, set by this function
                'fabric': 'CIC_UAT_ENG_FAB_1',
                'vpcId': '400',
                'vlan': '200',
                'mode': 'active',
                'hostName': 'server_hostname',
                'policy': 'int_vpc_access_host_11_1',
                'interfaces': [
                    {
                        'nc-cic-ecl2013': [
                            {
                                'name': 'Eth1/43',
                                    # switchPort in csv
                                'neighbor': 'Flex Lom/1'
                                    # concatenation of "hostSlot/hostPort"
                            },
                            {
                                'name': 'Eth1/44',
                                'neighbor': 'I/O Slot 7/1'
                            },
                        ],
                    },
                    {
                        'nc-cic-ecl2014': [
                            {
                                'name': 'Eth1/43',
                                'neighbor': 'Flex Lom/2'
                            },
                            {
                                'name': 'Eth1/44',
                                'neighbor': 'I/O Slot 7/2'
                            },
                        ]
                    }
                ]
            }
        }

        ansible yaml formatted:
        - fabric: CIC_UAT_ENG_FAB_1
          vpcId: 400
          vlan: 200
          mode: active
          hostName: server_hostname
          policy: int_vpc_access_host_11_1
          interfaces:
            - nc-cic-ecl2013:
              - name: Eth1/43
                neighbor: Flex Lom/1
              - name: Eth1/44
                neighbor: I/O Slot 7/1
            - nc-cic-ecl2014:
              - name: Eth1/43
                neighbor: Flex Lom/2
              - name: Eth1/44
                neighbor: I/O Slot 7/2
    """

    module_params = {}

    for row in csv_rows:
        vpcId = row['vpcId']
        if not vpcId:
            continue

        fabric = row['fabric']
        ##REMOVING CASE INSENSITIVE CHECK
        # switchName = (row['switchName']).lower()
        switchName = (row['switchName'])
        # print(switchName)
        serialNumber = dcnm.get_switch_serial(fabric, switchName)
        if not serialNumber:
            logger.warning("NO SERIAL NUMBER FOUND FOR {}! SKIPPING.".format(switchName))
            continue
        vpcPair = get_vpc_pair(dcnm, serialNumber)
        if not vpcPair:
            raise Exception('no vpc pair found', switchName, fabric)

        # create entry for this vpc if none exists
        index = (fabric, vpcPair, vpcId)
        if index not in module_params:
            params = dict(row)
            params['vpcId'] = vpcId
            params['vpcPair'] = vpcPair

            module_params[index] = params

    return module_params


def get_interface(dcnm: DcnmFabricInventory, serialNumber: str, ifName: str) -> Optional[list]:
    """ Get interface data from api """

    path = "/interface"
    params = {'serialNumber': serialNumber, 'ifName': ifName}
    info = dcnm.get(path, params=params)
    if info["RETURN_CODE"] != 200:
        logger.debug(info)
        logger.critical("GETTING INFORMATION FOR {} FAILED".format(ifName))
        return
    return info['DATA']


def check_vpc(existing_interface: list) -> bool:
    return ("pc" in existing_interface[0]["interfaces"][0]["ifName"]) or (
            "pc" in existing_interface[0]["interfaces"][0]["nvPairs"]["INTF_NAME"])


def correct_vpc_interface(existing_interface: list):
    """[
      {
        "policy": "int_vpc_access_host_11_1",
        "interfaces": [
          {
            "serialNumber": "9ON2MZ9WFJZ~91GSQO37LRC",
            "ifName": "vpc404",
            "nvPairs": {
              "PEER1_PO_DESC": "CUPRA90A0483",
              "PEER2_MEMBER_INTERFACES": "Ethernet1/9,Ethernet1/10",
              "PEER2_PO_DESC": "CUPRA90A0483",
              "PEER1_MEMBER_INTERFACES": "Ethernet1/9,Ethernet1/10",
              "BPDUGUARD_ENABLED": "true",
              "createVpc": "true",
              "PC_MODE": "active",
              "PEER2_ACCESS_VLAN": "100",
              "PRIORITY": "500",
              "FABRIC_NAME": "vxlan_cml_1",
              "PEER1_PCID": "404",
              "POLICY_ID": "POLICY-292930",
              "PEER1_ACCESS_VLAN": "100",
              "INTF_NAME": "vpc404",
              "MTU": "jumbo",
              "PORTTYPE_FAST_ENABLED": "true",
              "PEER2_PO_CONF": "  no lacp suspend-individual\n  service-policy type qos input QOS-IN no-stats",
              "PEER1_PO_CONF": "  no lacp suspend-individual\n  service-policy type qos input QOS-IN no-stats",
              "ADMIN_STATE": "true",
              "PEER2_PCID": "404",
              "POLICY_DESC": ""
            }
          }
        ]
      }
    ]"""
    interface = existing_interface[0]
    interface["interfaces"][0]["nvPairs"]["INTF_NAME"] = interface["interfaces"][0]["ifName"] = \
        interface["interfaces"][0]["ifName"].replace("pc", "PC")
    interface["interfaces"][0]["nvPairs"].pop("POLICY_ID")
    interface["interfaceType"] = "INTERFACE_VPC"
    interface["interfaces"][0]["interfaceType"] = "INTERFACE_VPC"
    interface["interfaces"][0]["nvPairs"].pop("createVpc")
    interface["skipResourceCheck"] = "false"
    interface["interfaces"][0]["fabricName"] = interface["interfaces"][0]["nvPairs"].pop("FABRIC_NAME")
    interface["interfaces"][0]["nvPairs"]["ENABLE_MIRROR_CONFIG"] = "false"
    interface["interfaces"][0]["nvPairs"].pop("POLICY_DESC")
    # since a dict is mutable, no return is necessary


def create_interface(dcnm: DcnmFabricInventory, existing_interface: list) -> Optional[bool]:
    path = "/globalInterface"
    data = existing_interface[0]
    info = dcnm.post(path, data=data, errors=[
        (500, "Invalid payload or any other internal server error")])
    if info["RETURN_CODE"] != 200:
        logger.debug(info)
        logger.critical("CREATION OF {} FAILED".format(data["interfaces"][0]["ifName"]))
        return False
    return True


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


def get_int_descriptions(dcnm: DcnmFabricInventory, entry: dict) -> Optional[list]:
    interface_descriptions = []
    vpc_serial = entry["interfaces"][0]["serialNumber"]
    sw1_serial = vpc_serial.split("~")[0]
    sw2_serial = vpc_serial.split("~")[1]
    sw1_interfaces = entry["interfaces"][0]["nvPairs"]["PEER1_MEMBER_INTERFACES"].split(",")
    sw2_interfaces = entry["interfaces"][0]["nvPairs"]["PEER2_MEMBER_INTERFACES"].split(",")
    for switch_serial, switch_interfaces in [(sw1_serial, sw1_interfaces), (sw2_serial, sw2_interfaces)]:
        for interface in switch_interfaces:

            info = get_interface(dcnm,
                                 switch_serial,
                                 interface)
            if not info:
                logger.error("Failed Getting Description For {} {}".format(
                    dcnm.get_switch_name(entry["interfaces"][0]["nvPairs"]["FABRIC_NAME"],
                                         switch_serial), interface))
                continue
            interface_descriptions.append(info)

    return interface_descriptions


def change_interface(dcnm: DcnmFabricInventory, existing_interface: list):
    path = "/interface"
    data = existing_interface[0]
    info = dcnm.put(path, data=data)
    if info["RETURN_CODE"] != 200:
        logger.debug(info)
        logger.error("Failed Changing {} {}".format(
            dcnm.get_switch_name(data["interfaces"][0]["nvPairs"]["FABRIC_NAME"],
                                 data["interfaces"][0]["serialNumber"]),
            data["interfaces"][0]["nvPairs"]["INTF_NAME"]))
        return False
    return True


def correct_int_description(interface: list):
    logger.debug("correct_int_description: interface: {}".format(interface))
    logger.debug(interface[0]["interfaces"][0]["nvPairs"]["PRIMARY_INTF"].replace("pc", "PC"))
    interface[0]["interfaces"][0]["nvPairs"]["PRIMARY_INTF"] = \
        interface[0]["interfaces"][0]["nvPairs"]["PRIMARY_INTF"].replace("pc", "PC")
    interface[0]["interfaces"][0]["interfaceType"] = "INTERFACE_ETHERNET"
    interface[0]["interfaces"][0]["fabricName"] = interface[0]["interfaces"][0]["nvPairs"]["FABRIC_NAME"]
    interface[0]["interfaces"][0]["nvPairs"].pop("POLICY_ID")


def create_interface_pti(dcnm: DcnmFabricInventory, existing_interface: list) -> Optional[bool]:
    path = "/globalInterface/pti"
    params = {"isMultiEdit": "false"}
    data = existing_interface[0]
    info = dcnm.post(path, data=data, params=params)
    if info["RETURN_CODE"] != 200:
        logger.debug(info)
        logger.critical("CREATION OF {} FAILED".format(data["interfaces"][0]["ifName"]))
        return False
    return True


def config_save(dcnm: DcnmFabricInventory, fabric: str) -> bool:
    path = "/control/fabrics/{}/config-save".format(fabric)
    info = dcnm.post(path)
    if info["RETURN_CODE"] != 200:
        logger.debug(info)
        logger.critical("CONFIGURATION SAVE FAILED")
        return False
    return True


def vpc_decision(dcnm: DcnmFabricInventory, mode: str, entry: dict) -> Union[bool, str, None]:
    logger.debug("vpc_decisions: entry: {}".format(entry))
    # deploy_payload = [
    ifName = "vPC{}".format(entry['vpcId'])
    serialNumber = entry["vpcPair"].split("~")[0]
    existing_interface = get_interface(dcnm, serialNumber, ifName)
    if not existing_interface:
        logger.critical("Failed Pulling Interface {} Information".format(ifName))
        return False
    logger.info("Interface: {} - {}".format(ifName, serialNumber))
    if mode.lower() == "dryrun": logger.info("Existing Interface: {}".format(existing_interface))
    logger.debug("vpc_decision: existing interface: {}".format(existing_interface))
    if check_vpc(existing_interface):
        int_desc = get_int_descriptions(dcnm, existing_interface[0])
        if not int_desc:
            logger.error("Unable to get descriptions for members of {}".format(ifName))
        if mode.lower() != "dryrun" and not mark_delete_vpc(dcnm, entry):
            return False
        correct_vpc_interface(existing_interface)
        logger.debug("vpc_decision: corrected interface: {}".format(existing_interface))
        if mode.lower() == "dryrun": logger.info("Corrected interface: {}".format(existing_interface))
        for intf in int_desc:
            correct_int_description(intf)
            logger.debug("Corrected Interface Description: {}".format(intf))
        if mode.lower() != "dryrun":
            info = create_interface(dcnm, existing_interface)
            if not info:
                return False
            else:
                for intf in int_desc:
                    info = create_interface_pti(dcnm, intf)
                    if not info:
                        logger.error("Failed changing interface description: {}".format(intf))
        else:
            logger.info("Recreating vpc")
            logger.info("Recreating interface descriptions: {}".format(int_desc))
        return True


def main():
    skipped = set()
    failed = set()
    success = set()

    # parse cli args
    args = command_args()
    mode = "DRYRUN" if args.dryrun else "DEPLOY"

    #set up logging
    if args.debug:
        SCREENLOGLEVEL = logging.DEBUG
        print("DEBUGGING")
        print()
    else:
        SCREENLOGLEVEL = logging.INFO
    # FILELOGLEVEL = logging.DEBUG
    # logformat = logging.Formatter(
    #     '%(asctime)s: %(process)d - %(threadName)s - %(funcName)s - %(name)s - %(levelname)s - message: %(message)s')

    logging.basicConfig(level=SCREENLOGLEVEL,
                        format='%(asctime)s: %(threadName)s - %(funcName)s - %(name)s - %(levelname)s - %(message)s')

    # screen handler
    # ch = logging.StreamHandler()
    # ch.setLevel(SCREENLOGLEVEL)
    # ch.setFormatter(logformat)
    #
    # logging.getLogger('').addHandler(ch)

    logger = logging.getLogger('dcnm')
    logger.debug(args)

    logger.critical("Started")
    # prompt stdin for username and password

    print("starting")

    # read csv data
    csv_rows = []
    with open(args.vpc_csv, newline='') as f:
        reader = csv.DictReader(f, dialect='excel')
        csv_rows = [row for row in reader]

    # validate csv data
    validate_csv_rows(CSV_REQUIRED_KEYS, csv_rows)
    logger.debug(csv_rows)

    # open connection to dcnm
    dcnm = DcnmFabricInventory(args.dcnm, read_timeout=300)
    dcnm.login(username='admin', password='MVhHuBr3')

    # build module_params from csv data
    module_params = csv_to_module_params(dcnm, csv_rows)
    logger.debug("CLI params {}".format(module_params))
    logger.debug("args parsed -- Running in {} mode".format(mode))

    if args.debug:
        _dbg("MODULE PARAMS", module_params)

    # prepare vpc creation api calls
    for name, entry in module_params.items():
        logger.debug(name, entry)
        ifName = "vPC%s" % entry["vpcId"]
        result = vpc_decision(dcnm, mode, entry)
        if result is None:
            logger.info("{} is correctly named. Skipping. {}".format(ifName, name))
            skipped.add(name)
        elif not result:
            logger.critical("Failed deleting and recreating {}. {}".format(ifName, name))
            failed.add(name)
        elif result:
            logger.info("{} successfully deleted, recreated. Yay. {}".format(ifName, name))
            success.add(name)
        else:
            logger.critical("Don't know what happened: {}".format(result))

    logger.debug("Succeeded: {}".format(success))
    logger.critical("Failed: {}".format(failed))
    print("Failed:")
    pprint(failed)
    logger.critical("Skipped: {}".format(skipped))
    print("Skipped:")
    pprint(skipped)


if __name__ == '__main__':

    main()
