import logging
from typing import Optional, Union

from DCNM_connect import DcnmRestApi
from DCNM_errors import DCNMPolicyDeployError
from DCNM_utils import spinner, _check_action_response
from handler import Handler, DcnmComponent, Singleton

logger = logging.getLogger('dcnm_deploys')


class DeployDcnmPolicy(DcnmComponent, metaclass=Singleton):
    def __init__(self, handler: Handler, dcnm_connector: DcnmRestApi):
        super().__init__(handler, dcnm_connector)

    @spinner()
    def deploy_interfaces(self, payload: Union[list, dict], deploy_timeout: int = 300) -> Optional[bool]:
        """


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
        :param deploy_timeout: timeout in seconds, default is 5 minutes
        :type deploy_timeout: integer
        :return: True if successful, False otherwise
        :rtype: bool

        Provide a list of interfaces to deploy. Returns True if successful.
        """
        logger.info("Deploying interface configs to switches")
        path = '/globalInterface/deploy'
        if isinstance(payload, dict):
            payload = [payload]
        temp_timers = self.dcnm.timeout
        self.dcnm.timeout = deploy_timeout
        logger.debug("deploy_interfaces: deploying interfaces {}".format(payload))
        info = self._check_action_response(self.post(path, data=payload), "deploy_interfaces",
                                           "DEPLOY OF", payload)
        self.dcnm.timeout = temp_timers
        return info

    @spinner()
    def deploy_fabric_config(self, fabric: str, deploy_timeout: int = 300) -> Optional[bool]:
        """
        :param fabric: name of fabric
        :type fabric: str
        :param deploy_timeout: timeout in seconds, default is 5 minutes
        :type deploy_timeout: int
        :return: True if successful, False otherwise
        :rtype: bool
        """
        path = f'/control/fabrics/{fabric}/config-deploy'
        temp_timers = self.dcnm.timeout
        self.dcnm.timeout = deploy_timeout
        logger.info("deploying config fabric {}".format(fabric))
        info = _check_action_response(self.dcnm.post(path,
                                                     errors=[
                                                         (500,
                                                          "Fabric name is invalid or config deployment failed due to internal server error")]),
                                           "deploy_fabric_config", "DEPLOY OF FABRIC", fabric)
        self.dcnm.timeout = temp_timers
        return info

    @spinner()
    def deploy_policies(self, policies: list, deploy_timeout: int = 300) -> Optional[bool]:
        """

        :param deploy_timeout: timeout in seconds, default is 300 seconds
        :type deploy_timeout: int
        :param policies: list of policies to deploy, Eg :- ["POLICY-1200","POLICY-1220"]
        :return: True if successful, False otherwise
        :rtype: bool
        """
        path = '/control/policies/deploy'
        temp_timers = self.dcnm.timeout
        self.dcnm.timeout = deploy_timeout
        if isinstance(policies, tuple):
            policies = list(policies)
        elif not isinstance(policies, list):
            raise DCNMPolicyDeployError("must provide a list of policy ids")
        logger.info("deploying policies {}".format(policies))
        info = _check_action_response(self.dcnm.post(path, data=policies), "deploy_policies", "DEPLOY OF POLICIES",
                                           policies)
        self.dcnm.timeout = temp_timers
        return info

    @spinner()
    def deploy_switch_config(self, serial_number: str, fabric: Optional[str] = None, deploy_timeout: int = 300) -> bool:
        """


        :param serial_number: required, serial number of switch
        :type serial_number: str
        :param fabric: optional, fabric name
        :type fabric: str
        :param deploy_timeout: optional timeout in seconds, default is 5 minutes
        :type deploy_timeout: integer
        :return: True if successful, False otherwise
        :rtype: bool

        Deploy configuration of switch specified by the serial number. If fabric is not provided the script will attempt
        to discover it. Returns True if successful, False otherwise.
        """
        logger.info("deploy switch conifg")
        if fabric is None:
            fabric = self.handler.switches[serial_number].fabricName
        path: str = f'/control/fabrics/{fabric}/config-deploy/{serial_number}'
        temp_timers = self.dcnm.timeout
        self.dcnm.timeout = deploy_timeout
        info = _check_action_response(self.dcnm.post(path, errors=[(400, "Invalid value supplied"),
                                                                   (500,
                                                                    "Invalid payload or any other internal server error")]),
                                           "desploy_switch_config", "CONFIG SAVE OF {} switch".format(fabric),
                                           serial_number)
        self.dcnm.timeout = temp_timers
        return info
