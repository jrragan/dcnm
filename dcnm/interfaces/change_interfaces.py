import argparse
import logging
from functools import partial
from pickle import dump
from time import strftime, gmtime
from typing import Union, Optional, Dict, List

import yaml

from DCNM_errors import DCNMValueError
from interfaces_utilities import depickle, _file_check
from dcnm_interfaces import DcnmInterfaces
from interfaces_utilities import read_existing_descriptions, get_interfaces_to_change, push_to_dcnm, \
    deploy_to_fabric_using_interface_deploy, verify_interface_change, _dbg, deploy_to_fabric_using_switch_deploy, \
    _failed_dbg


def command_args() -> argparse.Namespace:
    """ define and parse command line arguments """

    parser = argparse.ArgumentParser(description="automation of interface configuration changes via dcnm\n"
                                                 "at least one of -c -d or -o must be included or the \n"
                                                 "program won't do anything")
    parser.add_argument('-a', "--dcnm", metavar="IP_or_DNS_NAME",
                        required=True,
                        help="dcnm hostname or ip address")
    parser.add_argument("-u", "--username",
                        help="DCNM username")
    parser.add_argument(
        "-n",
        "--serials",
        metavar="SERIALS",
        nargs="+",
        type=str,
        default=[],
        help="enter one or more switch serial numbers",
    )
    parser.add_argument(
        "-f",
        "--input-file",
        metavar="FILE",
        type=str,
        default="",
        help="read serial numbers from a file",
    )
    parser.add_argument("-e", "--all", action="store_true",
                        help="perform actions for all switches")
    parser.add_argument("-x", "--excel", metavar="EXCEL_FILE",
                        help="descriptions xlsx file")
    parser.add_argument("-g", "--debug", action="store_true",
                        help="Shortcut for setting screen and logfile levels to DEBUG")
    parser.add_argument("-s", "--screenloglevel", metavar="LOGLEVEL", default="INFO",
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'], help="Default is INFO.")
    parser.add_argument("-l", "--loglevel", metavar="LOGLEVEL", default=None,
                        choices=['NONE', 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                        help="Default is NONE.")
    parser.add_argument("-c", "--cdp", action="store_true",
                        help="add no cdp enable to interfaces")
    parser.add_argument("-m", "--mgmt", action="store_true",
                        help="include mgmt interfaces in cdp action")
    parser.add_argument("-d", "--description", action="store_true",
                        help="correct interfaces descriptions\n"
                             "if this was part of the original change, this parameter\n"
                             "must be included with the fallback option")
    parser.add_argument("-o", "--orphan", action="store_true",
                        help="add vpc orphan port configuration to interfaces")
    parser.add_argument("-p", "--pickle", default="switches_configuration_policies.pickle",
                        metavar="FILE",
                        help="filename for pickle file used to save original switch configuration policies\n"
                             "if included for deploy, it must also be included for backout")
    parser.add_argument("-i", "--icpickle", default="interfaces_existing_conf.pickle",
                        metavar="FILE",
                        help="filename for pickle file used to save original interface configuration policies\n"
                             "if included for deploy, it must also be included for backout")
    parser.add_argument("-j", "--switch_deploy", action="store_true",
                        help="By default interface deploy is used (along with policy deploy when needed.\n"
                             "In certain situations this can lead to the need for a second deploy especially \n"
                             "when there is a switch level policy applying an interface level config. This option\n"
                             "enables a switch level deploy method.")
    parser.add_argument("-b", "--backout", action="store_true",
                        help="Rerun app with this option to fall back to original configuration.\n"
                             "If running backout, you should run program with all options included\n"
                             "in the original deploy.")
    parser.add_argument("-t", "--timeout", type=int, metavar="SECONDS", default=300,
                        help="timeout in seconds of the deploy operations\n" 
                             "default is 300 seconds")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="verbose mode")

    dryrun = parser.add_mutually_exclusive_group()
    dryrun.add_argument("--dryrun",
                        help="dryrun mode, do not deploy changes (default)",
                        action="store_true")
    dryrun.add_argument("--deploy",
                        help="deploy mode, deploys changes to dcnm",
                        action="store_const",
                        dest="dryrun",
                        const=False)
    dryrun.set_defaults(dryrun=True)

    return parser.parse_args()


def _read_serials_from_file(file: str):
    """

    :param file: name of file of serial numbers
    :type file: str
    :return: list of serial numbers
    :rtype: list
    """
    serials = _file_check(file, as_list=True)
    return serials


def get_desc_changes(dcnm: DcnmInterfaces, pickle: str, excel: Optional[str] = None,
                     verbose: bool = True) -> callable:
    if not excel:
        dcnm.get_switches_policies(templateName=r'switch_freeform\Z',
                                   config=r"interface\s+[a-zA-Z]+\d+/?\d*\n\s+[Dd]escription\s+")
        existing_descriptions_from_policies: list = DcnmInterfaces.get_info_from_policies_config(
            dcnm.all_switches_policies,
            r"interface\s+([a-zA-Z]+\d+/?\d*)\n\s+[dD]escription\s+(.*)")
        if verbose:
            _dbg("switch policies", dcnm.all_switches_policies)
            _dbg("existing description from policies", existing_descriptions_from_policies)
        policy_ids: list = list({c.policyId for c in existing_descriptions_from_policies})
        if verbose:
            _dbg("deleting policy ids", policy_ids)
        # delete the policy
        dcnm.delete_switch_policies(list(policy_ids))
        existing_descriptions: Dict[tuple, str] = {k: v for c in existing_descriptions_from_policies for k, v in
                                                   c.info.items()}
        if verbose:
            _dbg("existing descriptions from switch policies", existing_descriptions)
        with open(pickle, 'wb') as f:
            dump(dcnm.all_switches_policies, f)
    else:
        existing_descriptions = read_existing_descriptions(excel)
        if verbose:
            _dbg("existing descriptions from file", existing_descriptions)

    def descriptions(interface: tuple, detail: dict) -> bool:
        logger.debug("start get_desc_change: interface {}".format(interface))
        logger.debug("detail: {}".format(detail))
        # if it's not a vpc (e.g. vpc1) interface and the description is not already the desired description
        if interface in existing_descriptions and 'vpc' not in interface[0].lower() and \
                detail['interfaces'][0]['nvPairs']['DESC'] != existing_descriptions[interface]:
            logger.debug("interface: {}, new description: {}, old description: {}".format(interface,
                                                                                          existing_descriptions[
                                                                                              interface],
                                                                                          detail['interfaces'][0][
                                                                                              'nvPairs']['DESC']))
            detail['interfaces'][0]['nvPairs']['DESC'] = existing_descriptions[interface]
            return True
        return False

    return descriptions


def get_cdp_change(interface: tuple, detail: dict, mgmt: bool = True) -> bool:
    logger.debug("start get_cdp_change: interface {}".format(interface))
    logger.debug("detail: {}".format(detail))
    # if the mgmt flag is set and it's a mgmt interface and cdp is enabled
    if mgmt and 'mgmt' in interface[0] and detail['interfaces'][0]['nvPairs']['CDP_ENABLE'] == 'true':
        detail['interfaces'][0]['nvPairs']['CDP_ENABLE'] = 'false'
        logger.debug("interface: {}, changing cdp".format(interface))
        logger.debug("CDP_ENABLE: {}".format(detail['interfaces'][0]['nvPairs']['CDP_ENABLE']))
        return True
    # if it's a leaf switch and ethernet interface and not a fabric interface and cdp is enabled
    elif interface[1] in dcnm.all_leaf_switches and 'ethernet' in interface[0].lower() \
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


def get_orphanport_change(dcnm: DcnmInterfaces, uplinks_file: str,
                          serials: Optional[list] = None) -> callable:
    if not dcnm.all_switches_details:
        dcnm.get_switches_details(serial_numbers=serials)
    local_switches_details = dcnm.all_switches_details
    local_uplinks: Dict = _get_uplinks(uplinks_file)
    logger.debug("get_orphanport_change: local_uplinks: {}".format(local_uplinks))

    def orphan_port(interface: tuple, detail: dict) -> bool:
        logger.debug("start get_orphanport_change: interface {}".format(interface))
        logger.debug("detail: {}".format(detail))
        # get uplinks
        model = local_switches_details[interface[1]]['model']
        logger.debug("orphan_port: model: {}".format(model))
        this_model_uplinks: list = [local_uplinks[m] for m in local_uplinks if m in model][0]
        if not this_model_uplinks:
            _failed_dbg('orphan_port: No uplink data for model {}'.format(model), ('No uplink data for model', model))
            raise DCNMValueError('No uplink data for model {}'.format(model))
        logger.debug("orphan_port: this_model_uplinks: {}".format(this_model_uplinks))
        # if not a mgmt interface and either a trunk host or access_host interface
        if 'mgmt' not in interface[0] and \
                interface[0] not in this_model_uplinks and \
                ('int_trunk_host' in detail['policy'] or 'int_access_host' in detail['policy']) and \
                'vpc orphan-port suspend' not in detail['interfaces'][0]['nvPairs']['CONF']:
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

    return orphan_port


def _get_uplinks(uplinks_file):
    yaml_loader = partial(yaml.load, Loader=yaml.FullLoader)
    uplinks = _file_check(uplinks_file, loader=yaml_loader)
    local_uplinks: Dict[str, list] = {}
    for model in uplinks:
        first = uplinks[model][0]
        last = uplinks[model][1]
        interface_range = range(int(first.split('/')[1]), int(last.split('/')[1]) + 1)
        local_uplinks[model] = [f'Ethernet{first.split("/")[0]}/{i}' for i in interface_range]
    return local_uplinks


def _normal_deploy(args: argparse.Namespace, dcnm: DcnmInterfaces):
    """

    :param args:
    :type args:
    :param dcnm:
    :type dcnm:
    :return:
    :rtype:

    push changes to dcnm, deploy changes to fabric and verify changes based on cli args
    """
    logger.info("_normal_deploy: Pushing to DCNM and Deploying")
    if args.verbose:
        _dbg("Pushing to DCNM and Deploying")
    serials = _get_serial_numbers(args)
    # get interface info for these serial numbers
    dcnm.get_interfaces_nvpairs(serial_numbers=serials)
    # if args.verbose: _dbg("interfaces details and nvpairs", dcnm.all_interfaces_nvpairs)
    # get role and fabric info for these serial numbers
    if args.all:
        dcnm.get_all_switches()
    else:
        dcnm.get_switches_by_serial_number(serial_numbers=serials)
    if args.verbose:
        _dbg("number of leaf switches", len(dcnm.all_leaf_switches.keys()))
        _dbg("leaf switches", dcnm.all_leaf_switches.keys())
    policy_ids: Union[set, list, None] = None
    changes_to_make: List[tuple] = []
    if args.description:
        _dbg("Adding Description Changes")
        changes_to_make.append(
            (get_desc_changes(dcnm, args.pickle, excel=args.excel, verbose=args.verbose), None, False))
    if args.cdp:
        _dbg("Adding Disabling of CDP")
        changes_to_make.append((get_cdp_change, {'mgmt': args.mgmt}, False))
    if args.orphan:
        _dbg("Adding Enabling of Orphan Ports")
        changes_to_make.append((get_orphanport_change(dcnm, uplinks_file='uplinks.yaml', serials=serials),
                                None, True))
    interfaces_will_change, interfaces_existing_conf = get_interfaces_to_change(dcnm, changes_to_make)
    with open(args.icpickle, 'wb') as f:
        dump(interfaces_existing_conf, f)
    if args.verbose:
        _dbg("interfaces to change", interfaces_will_change)
    _deploy_stub(args, dcnm, interfaces_will_change, policy_ids, serials)


def _deploy_stub(args: argparse.Namespace, dcnm: DcnmInterfaces, interfaces_will_change: dict,
                 policy_ids: Optional[Union[list, tuple, str]], serials: list):
    success: set = push_to_dcnm(dcnm, interfaces_will_change, verbose=args.verbose)
    if args.switch_deploy:
        deploy_to_fabric_using_switch_deploy(dcnm, serials, deploy_timeout=args.timeout, verbose=args.verbose)
    else:
        deploy_to_fabric_using_interface_deploy(dcnm, success, policies=policy_ids, deploy_timeout=args.timeout,
                                                fallback=args.backout,
                                                verbose=args.verbose)
    # Verify
    verify_interface_change(dcnm, interfaces_will_change, serial_numbers=serials, verbose=args.verbose)


def _get_serial_numbers(args: argparse.Namespace):
    """

    :param args:
    :type args:
    :return:
    :rtype:

    get serial numbers from cli or from filename provided by cli
    """
    # get serial numbers
    serials: Union[None, list] = None
    if not args.all:
        serials: list = args.serials
        if args.input_file:
            serials += _read_serials_from_file(args.input_file)
        if not serials:
            _failed_dbg("No Serial Numbers Provided!", ("No Serial Numbers Provided!",))
            raise DCNMValueError("No Serial Numbers Provided!")
        if args.verbose:
            _dbg("switch serial numbers provided", serials)
    return serials


def _fallback(args: argparse.Namespace, dcnm: DcnmInterfaces):
    """

    :param args:
    :type args:
    :param dcnm:
    :type dcnm:
    :return:
    :rtype:

    fallback to original config: push changes to dcnm, deploy changes to fabric and verify changes based on cli args
    """
    if args.verbose:
        _dbg("FALLING BACK!")
    logger.info("FALLING BACK")
    serials = _get_serial_numbers(args)
    if args.switch_deploy:
        if args.all:
            dcnm.get_all_switches()
        else:
            dcnm.get_switches_by_serial_number(serial_numbers=serials)
        if args.verbose:
            _dbg("number of leaf switches", len(dcnm.all_leaf_switches.keys()))
            _dbg("leaf switches", dcnm.all_leaf_switches.keys())

    interfaces_existing_conf = depickle(args.icpickle)
    if args.verbose:
        _dbg("these interface configs will be restored", interfaces_existing_conf)

    policy_ids: Union[list, None] = None
    if args.description and not args.excel:
        interface_desc_policies: Dict[str, list] = depickle(args.pickle)
        policy_ids: set = set()
        for serial_number in interface_desc_policies:
            for policy in interface_desc_policies[serial_number]:
                dcnm.post_new_policy(policy)
                policy_ids.add(policy["policyId"])
        policy_ids: list = list(policy_ids)
        if args.verbose:
            _dbg("these switch policies will be restored", interface_desc_policies)
    _deploy_stub(args, dcnm, interfaces_existing_conf, policy_ids, serials)


if __name__ == '__main__':
    # parse cli args
    args = command_args()
    mode = "DRYRUN" if args.dryrun else "DEPLOY"

    # set up screen logging
    if args.debug:
        SCREENLOGLEVEL = logging.DEBUG
    else:
        SCREENLOGLEVEL = eval('logging.{}'.format(args.screenloglevel))

    print(SCREENLOGLEVEL)

    logging.basicConfig(level=SCREENLOGLEVEL,
                        format='%(asctime)s | %(process)d | %(threadName)s | (%(filename)s:%(lineno)d) | %(funcName)s | %(levelname)s | message: %(message)s')

    # set up file logging
    if args.loglevel is not None or args.loglevel == 'NONE':
        LOGFILE = "dcnm_interfaces" + strftime("_%y%m%d%H%M%S", gmtime()) + ".log"
        logformat = logging.Formatter(
            '%(asctime)s | %(process)d | %(threadName)s | (%(filename)s:%(lineno)d) | %(funcName)s | %(levelname)s | message: %(message)s')
        if args.debug:
            FILELOGLEVEL = logging.DEBUG
        else:
            FILELOGLEVEL = eval('logging.{}'.format(args.loglevel))
        print(FILELOGLEVEL)
        # file handler
        ch = logging.FileHandler(LOGFILE)
        ch.setLevel(FILELOGLEVEL)
        ch.setFormatter(logformat)
        logging.getLogger('').addHandler(ch)

    logger = logging.getLogger('change_interfaces')
    logger.critical("Started")

    logger.debug(args)
    if args.verbose:
        _dbg("args:", args)
    # prompt stdin for username and password
    print("args parsed -- Running in %s mode" % mode)
    if args.verbose:
        _dbg("Connecting to DCNM...")
    dcnm = DcnmInterfaces(args.dcnm, dryrun=args.dryrun)
    dcnm.logon(username=args.username)

    if not args.backout:
        _normal_deploy(args, dcnm)

    # Fallback
    else:
        _fallback(args, dcnm)

    print('=' * 40)
    print("FINISHED. GO GET PLASTERED!")
    print('=' * 40)
