import argparse
import logging
from pickle import dump
from typing import Optional, Dict

from DCNM_errors import DCNMValueError
from handler import Handler
from DCNM_utils import get_info_from_policies_config
from interfaces_utilities import _dbg, read_existing_descriptions, _get_uplinks, _failed_dbg
from plugin_utils import PlugIn, RegisterPlugin

logger = logging.getLogger(__name__)

@RegisterPlugin(name="desc")
class GetDescChanges(PlugIn):
    def initialize(self, handler: Handler, args: argparse.Namespace,
                          serials: Optional[list] = None) -> None:
        self.handler = handler
        self.leaf_only = False
        if not args.excel:
            self.handler.get_switches_policies(templateName=r'switch_freeform\Z',
                                       config=r"interface\s+[a-zA-Z]+\d+/?\d*\n\s+[Dd]escription\s+")
            existing_descriptions_from_policies: list = get_info_from_policies_config(
                {serial_number : switch.policies for serial_number, switch in self.handler.switches.items()},
                r"interface\s+([a-zA-Z]+\d+/?\d*)\n\s+[dD]escription\s+(.*)")
            if args.verbose:
                _dbg("existing description from policies", existing_descriptions_from_policies)
            policy_ids: list = list({c.policyId for c in existing_descriptions_from_policies})
            if args.verbose:
                _dbg("deleting policy ids", policy_ids)
            # delete the policy
            self.handler.delete_switch_policies(list(policy_ids))
            self.existing_descriptions: Dict[tuple, str] = {k: v for c in existing_descriptions_from_policies for k, v in
                                                       c.info.items()}
            if args.verbose:
                _dbg("existing descriptions from switch policies", self.existing_descriptions)
            with open(args.pickle, 'wb') as f:
                dump(self.handler.all_switches_policies, f)
        else:
            self.existing_descriptions = read_existing_descriptions(args.excel)
            if args.verbose:
                _dbg("existing descriptions from file", self.existing_descriptions)

    def __call__(self, interface: tuple, detail: dict) -> bool:
        logger.debug("start get_desc_change: interface {}".format(interface))
        logger.debug("detail: {}".format(detail))
        # if it's not a vpc (e.g. vpc1) interface and the description is not already the desired description
        if interface in self.existing_descriptions and 'vpc' not in interface[0].lower() and \
                detail['interfaces'][0]['nvPairs']['DESC'] != self.existing_descriptions[interface]:
            logger.debug("interface: {}, new description: {}, old description: {}".format(interface,
                                                                                          self.existing_descriptions[
                                                                                              interface],
                                                                                          detail['interfaces'][0][
                                                                                              'nvPairs']['DESC']))
            detail['interfaces'][0]['nvPairs']['DESC'] = self.existing_descriptions[interface]
            return True
        return False


class GetCdpChange(PlugIn):
    def initialize(self, handler: Handler, args: argparse.Namespace,
                          serials: Optional[list] = None) -> None:
        self.args = args
        self.handler = handler
        self.all_leaf_switches = handler.all_leaf_switches
        self.mgmt = args.mgmt
        self.leaf_only = False
    def __call__(self, interface: tuple, detail: dict) -> bool:
        logger.debug("start get_cdp_change: interface {}".format(interface))
        logger.debug("detail: {}".format(detail))
        # if the mgmt flag is set and it's a mgmt interface and cdp is enabled
        if self.mgmt and 'mgmt' in interface[0] and detail['interfaces'][0]['nvPairs']['CDP_ENABLE'] == 'true':
            detail['interfaces'][0]['nvPairs']['CDP_ENABLE'] = 'false'
            logger.debug("interface: {}, changing cdp".format(interface))
            logger.debug("CDP_ENABLE: {}".format(detail['interfaces'][0]['nvPairs']['CDP_ENABLE']))
            return True
        # if it's a leaf switch and ethernet interface and not a fabric interface and cdp is enabled
        elif interface[1] in self.all_leaf_switches and 'ethernet' in interface[0].lower() \
                and 'fabric' not in detail['policy'] \
                and 'no cdp enable' not in detail['interfaces'][0]['nvPairs']['CONF']:
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


class GetOrphanportChange(PlugIn):
    def initialize(self, handler: Handler, args: argparse.Namespace,
                          serials: Optional[list] = None) -> None:
        if not handler.all_switches_details:
            handler.get_switches_details(serial_numbers=serials)
        self.local_switches_details = handler.all_switches_details
        self.local_uplinks: Dict = _get_uplinks(args.uplinks)
        self.leaf_only = True
        logger.debug("get_orphanport_change: local_uplinks: {}".format(self.local_uplinks))

    def __call__(self, interface: tuple, detail: dict) -> bool:
        logger.debug("start get_orphanport_change: interface {}".format(interface))
        logger.debug("detail: {}".format(detail))
        # get uplinks
        model = self.local_switches_details[interface[1]]['model']
        logger.debug("orphan_port: model: {}".format(model))
        this_model_uplinks: list = [self.local_uplinks[m] for m in self.local_uplinks if m in model][0]
        if not this_model_uplinks:
            _failed_dbg('orphan_port: No uplink data for model {}'.format(model), ('No uplink data for model', model))
            raise DCNMValueError('No uplink data for model {}'.format(model))
        logger.debug("orphan_port: this_model_uplinks: {}".format(this_model_uplinks))
        # if not a mgmt interface and either a trunk host or access_host interface
        if 'mgmt' not in interface[0] and \
                interface[0] not in this_model_uplinks and \
                ('int_trunk_host' in detail['policy'] or 'int_access_host' in detail['policy']) and \
                'vpc orphan-port enable' not in detail['interfaces'][0]['nvPairs']['CONF']:
            if not detail['interfaces'][0]['nvPairs']['CONF']:
                detail['interfaces'][0]['nvPairs']['CONF'] = 'vpc orphan-port suspend'
                logger.debug("interface: {}, changing orphan port suspend".format(interface))
                logger.debug("orphan port CONF: {}".format(detail['interfaces'][0]['nvPairs']['CONF']))
                return True
            else:
                # print(interface, detail)
                detail['interfaces'][0]['nvPairs']['CONF'] = '{}\n{}'.format(
                    detail['interfaces'][0]['nvPairs']['CONF'],
                    'vpc orphan-port suspend')
                logger.debug("interface: {}, changing orphan port suspend".format(interface))
                logger.debug("orphan port multiple CONF: {}".format(detail['interfaces'][0]['nvPairs']['CONF']))
                return True
        return False

