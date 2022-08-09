import argparse
import logging
from pickle import dump
from time import strftime, gmtime
from typing import Union, Optional, Dict, List

from DCNM_connect import DcnmRestApi
from handler import Handler
from interfaces_utilities import depickle, _get_serial_numbers
from interfaces_utilities import get_interfaces_to_change, push_to_dcnm, \
    deploy_to_fabric_using_interface_deploy, verify_interface_change, _dbg, deploy_to_fabric_using_switch_deploy
from plugin_utils import PlugInEngine


def command_args(plugins: List[str]) -> argparse.Namespace:
    """ define and parse command line arguments """

    parser = argparse.ArgumentParser(description="Automation of interface configuration changes via dcnm\n"
                                                 "at least one plugin must be included or the program won't do "
                                                 "anything.\n\n"
                                                 "You must also include a list of serial numbers, a serial\n"
                                                 "numbers file or the --all option. \n Serial numbers and serial\n"
                                                 "numbers file can be mixed. \n")
    parser.add_argument('dcnm', metavar="IP_or_DNS_NAME",
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
        metavar="SERIALSFILE",
        type=str,
        default="",
        help="read serial numbers from a file",
    )
    parser.add_argument("-P", "--plugins", nargs="+", choices=plugins, required=True,
                        help="enter one or more plugins to determine the actions of the script")
    parser.add_argument("-e", "--all", action="store_true",
                        help="perform actions for all switches")
    parser.add_argument("-x", "--excel", metavar="EXCEL_FILE",
                        help="descriptions xlsx file")
    parser.add_argument("-g", "--debug", action="store_true",
                        help="Shortcut for setting screen and logfile levels to DEBUG")
    parser.add_argument("-s", "--screenloglevel", default="INFO",
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'], help="Default is INFO.")
    parser.add_argument("-l", "--loglevel", default=None,
                        choices=['NONE', 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                        help="Default is NONE.")
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
    parser.add_argument("-U", "--uplinks", default="uplinks.yaml",
                        metavar="FILE",
                        help="filename for yaml file containing uplink information\n"
                             "default filename is 'uplinks.yaml'")

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


def _normal_deploy(args: argparse.Namespace, handler: Handler, plugins: PlugInEngine):
    """

    :param args: cli options provided by user
    :type args: argparse.Namespace
    :param handler: object responsible for finding correct dcnm-interfacing object for a method or attribute
    request
    :type handler: Handler
    :param plugins: object responsible for running user specified plugins for choosing interfaces to change
    :type: plugins: PlugInEngine

    master function to push changes to dcnm, deploy changes to fabric and verify changes based on cli args
    """
    logger.info("_normal_deploy: Pushing to DCNM and Deploying")
    if args.verbose:
        _dbg("Pushing to DCNM and Deploying")
    serials = _get_serial_numbers(args)
    handler.get_interfaces_nvpairs(serial_numbers=serials)
    if args.all:
        handler.get_all_switches()
    else:
        handler.get_switches_by_serial_number(serial_numbers=serials)
    if args.verbose:
        _dbg("number of leaf switches", len(handler.all_leaf_switches))
        _dbg("leaf switches", handler.all_leaf_switches)
    policy_ids: Union[set, list, None] = None
    interfaces_will_change, interfaces_existing_conf = get_interfaces_to_change(handler, plugins, args, serials)
    with open(args.icpickle, 'wb') as f:
        dump(interfaces_existing_conf, f)
    if args.verbose:
        _dbg("interfaces to change", interfaces_will_change)
    _deploy_stub(args, handler, interfaces_will_change, policy_ids, serials)


def _deploy_stub(args: argparse.Namespace, handler: Handler, interfaces_will_change: dict,
                 policy_ids: Optional[Union[list, tuple, str]], serials: list):
    success: set = push_to_dcnm(handler, interfaces_will_change, verbose=args.verbose)
    if args.switch_deploy:
        deploy_to_fabric_using_switch_deploy(handler, serials, deploy_timeout=args.timeout, verbose=args.verbose)
    else:
        deploy_to_fabric_using_interface_deploy(handler, success, policies=policy_ids, deploy_timeout=args.timeout,
                                                fallback=args.backout,
                                                verbose=args.verbose)
    # Verify
    verify_interface_change(handler, interfaces_will_change, serial_numbers=serials, verbose=args.verbose)


def _fallback(args: argparse.Namespace, handler: Handler, plugins: PlugInEngine):
    """
    fallback to original config: push changes to dcnm, deploy changes to fabric and verify changes based on cli args
    """
    if args.verbose:
        _dbg("FALLING BACK!")
    logger.info("FALLING BACK")
    serials = _get_serial_numbers(args)
    if args.switch_deploy:
        if args.all:
            handler.get_all_switches()
        else:
            handler.get_switches_by_serial_number(serial_numbers=serials)
        if args.verbose:
            _dbg("number of leaf switches", len(handler.all_leaf_switches))
            _dbg("leaf switches", handler.all_leaf_switches)

    interfaces_existing_conf = depickle(args.icpickle)
    if args.verbose:
        _dbg("these interface configs will be restored", interfaces_existing_conf)

    policy_ids: Union[list, None] = None
    if args.description and not args.excel:
        interface_desc_policies: Dict[str, list] = depickle(args.pickle)
        policy_ids: set = set()
        for serial_number in interface_desc_policies:
            for policy in interface_desc_policies[serial_number]:
                handler.post_new_policy(policy)
                policy_ids.add(policy["policyId"])
        policy_ids: list = list(policy_ids)
        if args.verbose:
            _dbg("these switch policies will be restored", interface_desc_policies)
    _deploy_stub(args, handler, interfaces_existing_conf, policy_ids, serials)


if __name__ == '__main__':
    # initialize plugins
    plugins = PlugInEngine()
    # parse cli args
    args = command_args(list(plugins.plugins.keys()))
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
    dcnm = DcnmRestApi(args.dcnm, dryrun=args.dryrun)
    dcnm.logon(username=args.username)

    #initialize handler
    if args.verbose:
        _dbg("Initializing Handler...")
    handler = Handler(dcnm)

    #passing selected plugins
    if args.verbose:
        _dbg("Initializing Plugins...")
    plugins.set_plugins(args.plugins)
    if not args.backout:
        if args.verbose:
            _dbg("Normal Deploy...")
        _normal_deploy(args, handler, plugins)

    # Fallback
    else:
        if args.verbose:
            _dbg("Fallback...")
        _fallback(args, handler, plugins)

    print('=' * 40)
    print("FINISHED. GO GET PLASTERED!")
    print('=' * 40)
