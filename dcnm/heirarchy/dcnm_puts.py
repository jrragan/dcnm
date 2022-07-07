import logging
from copy import deepcopy
from typing import Dict, Tuple, Union

from DCNM_connect import DcnmRestApi
from DCNM_utils import spinner, _check_action_response
from handler import Handler, DcnmComponent, Singleton

logger = logging.getLogger('dcnm_puts')


class ChangeDcnmPolicy(DcnmComponent, metaclass=Singleton):
    def __init__(self, handler: Handler, dcnm_connector: DcnmRestApi):
        super().__init__(handler, dcnm_connector)

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
        info = _check_action_response(self.dcnm.put(path, data=details, errors=[
            (500, "Invalid payload or any other internal server error")]), "put_interface",
                                      "CREATION OF", interface)
        return info

    @spinner()
    def put_interface_changes(self, interfaces_will_change: Dict[tuple, dict]) -> Tuple[set, set]:
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
        logger.info("Putting interface changes to dcnm")
        interfaces_will_change_local: Dict[tuple, dict] = deepcopy(interfaces_will_change)
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
                logger.debug("put_interface_changes:  {} successfully changed. Yay.".format(interface))
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
        logger.info("post new policy to dcnm")
        logger.debug("post_new_policy: details: {}".format(details))
        info = _check_action_response(self.dcnm.post(path, data=details, errors=[
            (500, "Invalid payload or any other internal server error")]), "post_new_policy",
                                           "CREATION OF POLICY", details)
        return info

    def delete_switch_policies(self, policyId: Union[str, list]):
        logger.info("delete switch policies")
        if isinstance(policyId, str):
            path: str = f'/control/policies/{policyId}'
        elif isinstance(policyId, (list, tuple)):
            path: str = f'/control/policies/policyIds?policyIds={",".join(policyId)}'
        info = _check_action_response(self.dcnm.delete(path, errors=[
            (500, "Invalid payload or any other internal server error (e.g. policy does not exist)")]),
                                           "delete_switch_policies", "DELETE OF", policyId)
        return info

    