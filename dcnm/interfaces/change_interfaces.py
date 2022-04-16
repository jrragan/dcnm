import argparse
import logging
import pathlib
import sys
from pickle import dump, load
from pprint import pprint
from time import strftime, gmtime

from dcnm.interfaces.dcnm_interfaces import DcnmInterfaces, read_existing_descriptions, get_desc_change, get_cdp_change, \
    get_orphanport_change, get_interfaces_to_change, push_to_dcnm, deploy_to_fabric, verify_interface_change


def command_args() -> argparse.Namespace:
    """ define and parse command line arguments """

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-a', "--dcnm",
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
    parser.add_argument("-x", "--excel",
                        help="descriptions xlsx file")
    parser.add_argument("-g", "--debug", action="store_true",
                        help="Shortcut for setting screen and logfile levels to DEBUG")
    parser.add_argument("-s", "--screenloglevel", default="INFO",
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'], help="Default is INFO.")
    parser.add_argument("-l", "--loglevel", default="NONE",
                        choices=['NONE', 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                        help="Default is NONE.")
    parser.add_argument("-c", "--cdp", action="store_true",
                        help="add no cdp enable to interfaces")
    parser.add_argument("-m", "--mgmt", action="store_true",
                        help="include mgmt interfaces in cdp action")
    parser.add_argument("-d", "--description", action="store_true",
                        help="correct interfaces descriptions")
    parser.add_argument("-o", "--orphan", action="store_true",
                        help="add vpc orphan port configuration to interfaces")
    parser.add_argument("-p", "--pickle", default="switches_configuration_policies.pickle",
                        help="filename for pickle file used to save original switch configuration policies")
    parser.add_argument("-i", "--icpickle", default="interfaces_existing_conf.pickle",
                        help="filename for pickle file used to save original interface configuration policies")
    parser.add_argument("-b", "--backout", action="store_true",
                        help="rerun app with this option to fall back to original configuration")
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


def _get_sns(user_args):
    serials: list = user_args.serials
    if user_args.input_file:
        serials += _read_serials_from_file(user_args.input_file)
    return serials


class DCNMFileError(Exception):
    pass


def _read_serials_from_file(file):
    file_path = pathlib.Path(file)
    if file_path.is_file():
        with file_path.open() as serials_file:
            serials = [serial.strip() for serial in serials_file]
            if serials:
                return serials
            logger.critical(f"Error: empty input file, {file}")
            raise DCNMFileError(f"Error: empty input file, {file}")
    else:
        logger.critical("Error: input file not found")
        raise DCNMFileError("Error: input file not found")
    return []


class DCNMValueError(Exception):
    pass


def _normal_deploy(args, dcnm):
    # get serial numbers
    serials: list = _get_sns(args)
    if not serials:
        logger.critical("No Serial Numbers Provided!")
        raise DCNMValueError("No Serial Numbers Provided!")
    if args.verbose: print(serials)
    # get interface info for these serial numbers
    dcnm.get_interfaces_nvpairs(serial_numbers=serials)
    if args.verbose: pprint(dcnm.all_interfaces_nvpairs)
    # get role and fabric info for these serial numbers
    dcnm.get_switches_by_serial_number(serial_numbers=serials)
    if args.verbose:
        print("=" * 40)
        print(len(dcnm.all_leaf_switches.keys()))
        print(dcnm.all_leaf_switches.keys())
    if args.description:
        if not args.excel:
            dcnm.get_switches_policies(templateName='switch_freeform\Z',
                                       config=r"interface\s+[a-zA-Z]+\d+/?\d*\n\s+description\s+")
            existing_descriptions_from_policies: list = DcnmInterfaces.get_info_from_policies_config(
                dcnm.all_switches_policies,
                r"interface\s+([a-zA-Z]+\d+/?\d*)\n\s+description\s+(.*)")
            if args.verbose:
                print("=" * 40)
                pprint(dcnm.all_switches_policies)
                print("=" * 40)
                pprint(existing_descriptions_from_policies)
            policy_ids: set = {c.policyId for c in existing_descriptions_from_policies}
            if args.verbose: print(policy_ids)
            # delete the policy
            dcnm.delete_switch_policies(list(policy_ids))
            existing_descriptions: dict[tuple, str] = {k: v for c in existing_descriptions_from_policies for k, v in
                                                       c.info.items()}
            if args.verbose: pprint(existing_descriptions)
            with open(args.pickle, 'wb') as f:
                dump(dcnm.all_switches_policies, f)
        else:
            existing_descriptions = read_existing_descriptions(args.excel)
            if args.verbose: print(existing_descriptions)
    changes_to_make: list = []
    if args.description: changes_to_make.append(
        (get_desc_change, {'existing_descriptions': existing_descriptions}, False))
    if args.cdp: changes_to_make.append((get_cdp_change, {'mgmt': args.mgmt}, False))
    if args.orphan: changes_to_make.append((get_orphanport_change, None, True))
    interfaces_will_change, interfaces_existing_conf = get_interfaces_to_change(dcnm, changes_to_make)
    with open(args.icpickle, 'wb') as f:
        dump(interfaces_existing_conf, f)
    if args.verbose:
        print('=' * 40)
        print()
        pprint(interfaces_will_change)
    success: tuple = push_to_dcnm(dcnm, interfaces_will_change, args.verbose)
    deploy_to_fabric(dcnm, success, args.verbose)
    # Verify
    success, failure = verify_interface_change(dcnm, interfaces_will_change, serial_numbers=serials)
    if args.verbose:
        if failure:
            pprint("verify_interface_change:  Failed configuring {}".format(failure))
        else:
            pprint("verify_interface_change: No Failures!")


def _fallback(args, dcnm):
    with open(args.icpickle, 'rb') as f:
        interfaces_existing_conf = load(f)
    if args.verbose: pprint(interfaces_existing_conf)
    success = push_to_dcnm(dcnm, interfaces_existing_conf)
    deploy_to_fabric(dcnm, success)
    if args.description:
        with open(args.pickle, 'rb') as f:
            interface_desc_policies: dict[str, list] = load(f)
            for serial_number in interface_desc_policies:
                for policy in interface_desc_policies[serial_number]:
                    dcnm.post_new_policy(policy)
        if args.verbose: pprint(interface_desc_policies)


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
                        format='%(asctime)s: %(process)d - %(threadName)s - %(funcName)s - %(name)s - %(levelname)s - message: %(message)s')

    # set up file logging
    if args.loglevel is not None:
        LOGFILE = "dcnm_interfaces" + strftime("_%y%m%d%H%M%S", gmtime()) + ".log"
        logformat = logging.Formatter(
            '%(asctime)s: %(process)d - %(threadName)s - %(funcName)s - %(name)s - %(levelname)s - message: %(message)s')
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

    # prompt stdin for username and password
    print("args parsed -- Running in %s mode" % mode)
    dcnm = DcnmInterfaces(args.dcnm, dryrun=args.dryrun)
    dcnm.login(username=args.username)

    if not args.fallback:
        _normal_deploy(args, dcnm)

    # Fallback
    else:
        _fallback(args, dcnm)

    print('=' * 40)
    print("FINISHED. GO GET PLASTERED!")
    print('=' * 40)