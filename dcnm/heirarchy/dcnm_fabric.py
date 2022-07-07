import json
import logging
from typing import Dict

from DCNM_connect import DcnmRestApi
from DCNM_utils import error_handler, _check_response
from handler import DcnmComponent, Handler

logger = logging.getLogger(__name__)


class DcnmFabric(DcnmComponent):
    def __init__(self, handler: Handler, dcnm_connector: DcnmRestApi):
        super().__init__(handler, dcnm_connector)
        self.fabrics: Dict = {}

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

        logger.debug("get_fabric_details: getting fabric ids for")
        response = _check_response(self.dcnm.get(path))

        for fabric in json.loads(response['MESSAGE']):
            self.fabrics[fabric['fabricName']] = fabric

    @error_handler("ERROR: get_fabric_swtiches_detail: getting switch details for all fabric switches")
    def get_fabric_switches_details(self, fabric: str) -> dict:
        local_all_switches_details: Dict[tuple, dict] = {}

        path = f'/control/fabrics/{fabric}/inventory'

        logger.info("get_fabric_switches_detail: getting switch details for fabric {}".format(fabric))
        response = _check_response(self.dcnm.get(path))
        # pprint(json.loads(response['MESSAGE']))
        for switch in json.loads(response['MESSAGE']):
            local_all_switches_details[switch["serialNumber"]] = switch
        return local_all_switches_details

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
        logger.info("get_switch_fabric: getting fabric for switch {}".format(serial_number))
        response = _check_response(self.dcnm.get(path, errors=[(500, "Invalid switch or Other exception")]))
        return json.loads(response['MESSAGE'])['fabricName']
