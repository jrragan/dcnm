import argparse
import logging
import pathlib
import sys
import traceback
from copy import deepcopy
from functools import partial
from pickle import load
from pprint import pprint
from typing import Optional, Union, Dict, List, Tuple, Set, Callable, Iterable

from colorama import init, Back, Fore, Style

from DCNM_errors import DCNMPolicyDeployError, DCNMValueError
from DCNM_errors import ExcelFileError, DCNMFileError
from handler import Handler
from plugin_utils import PlugInEngine

logger = logging.getLogger(__name__)


def _dbg(header: str, data=None):
    """ Output verbose data """

    print("=" * 60)
    print(header)
    print("=" * 60)
    if data:
        pprint(data)
        print("=" * 60)
    print()


def read_existing_descriptions(file: str) -> Dict[tuple, str]:
    """
    :param file: an Excel file path/name containing columns "interface", "switch" and "description"
    the switch column is the switch serial number
    :type file: str
    :return: dictionary
    :rtype: dict[tuple, str]

    Read in an Excel file and return a dictionary of form {(interface, switch_serial_number): interface_description}
    """
    import pandas
    from pandas import read_excel
    if _file_check(file, skip_load=True):
        existing_descriptions_local: dict
        logger.debug("reading excel file {}".format(file))
        df: pandas.DataFrame = read_excel(file)
        df.columns = df.columns.str.lower()
        if 'description' not in df.columns or 'interface' not in df.columns or 'switch' not in df.columns:
            logger.debug("Columns missing. {}".format(df.columns))
            raise ExcelFileError('One or more columns missing')
        existing_descriptions_local = df.to_dict('records')
        # print(existing_descriptions)
        existing_descriptions_local = {(interface['interface'], interface['switch']): interface['description'] for
                                       interface
                                       in
                                       existing_descriptions_local}
        logger.debug("read_existing_descriptions: existing descriptions: {}".format(existing_descriptions_local))
        return existing_descriptions_local


def get_interfaces_to_change(handler: Handler,
                             plugins: PlugInEngine,
                             args: argparse.Namespace,
                             serials: Optional[Union[List, Tuple, str]]) -> Tuple[
    Dict[tuple, dict], Dict[tuple, dict]]:
    """

    :param handler: An object that provides access to DCNM-interfacing objects
    :type handler: Handler
    :param plugins: An object of the PlugInEngine class that provides access to plugins selected by the cli
    :type plugins: PlugInEngine
    :param args: cli args, required by the plugins
    :type args: argparse.Namespace
    :param serials: a serial number or list of serial numbers of switches
    :type serials: list, tuple, str
    :return: two dictionaries of interfaces, one containing the changes to make,
    the other containing the original configuration
    :rtype: tuple of dictionaries

    takes the list of interfaces provided by the handler and runs then through the cli-selected
    plugins in the plugin engine to determine which interfaces to change
    """
    existing_interfaces = deepcopy(handler.all_interfaces_nvpairs)
    interfaces_to_change: Dict[tuple, dict] = {}
    interfaces_original: Dict[tuple, dict] = {}
    # initialize selected plugins
    logger.debug("get_interfaces_to_change: initializing plugins")
    plugins.initialize_selected_plugins(handler, args, serials)
    logger.debug("get_interfaces_to_change: running plugins")
    for interface, details in existing_interfaces.items():
        change: bool = False
        # print(details)
        change = plugins.run_selected_plugins(interface, details,
                                              leaf=interface[1] in handler.all_leaf_switches)
        if change:
            interfaces_original[interface] = handler.all_interfaces_nvpairs[interface]
            interfaces_to_change[interface] = details
    logger.debug("Interfaces to change: {}".format(interfaces_to_change))
    return interfaces_to_change, interfaces_original


def verify_interface_change(handler: Handler, interfaces_will_change: dict, verbose: bool = True, **kwargs):
    """

    :param handler: An object that provides access to DCNM-interfacing objects
    :type handler: Handler
    :param interfaces_will_change: a dictionary of interfaces
    :type interfaces_will_change: dict
    :param verbose: output more information if this is set
    :type verbose: bool
    :param kwargs:
    :type kwargs:
    :return: None
    :rtype:

    Pulls interface information from DCNM and compares it to the interfaces_will_change dict.
    Displays failures.
    """
    handler.get_interfaces_nvpairs(save_prev=True, **kwargs)
    failed: set = set()
    success: set = set()
    if verbose:
        _dbg("Verifying Interface Configurations")
    interfaces_will_change_local = deepcopy(interfaces_will_change)
    all_interfaces_nv_pairs_local = deepcopy(handler.all_interfaces_nvpairs)
    for interface in interfaces_will_change:
        # priority changes, so remove from comparison
        interfaces_will_change_local[interface]['interfaces'][0]['nvPairs'].pop('PRIORITY', None)
        interfaces_will_change_local[interface]['interfaces'][0]['nvPairs'].pop('FABRIC_NAME', None)
        all_interfaces_nv_pairs_local[interface]['interfaces'][0]['nvPairs'].pop('PRIORITY', None)
        all_interfaces_nv_pairs_local[interface]['interfaces'][0]['nvPairs'].pop('FABRIC_NAME', None)
        if interfaces_will_change_local[interface] == all_interfaces_nv_pairs_local[interface]:
            logger.debug("Verification confirmed for interface {}".format(interface))
            logger.debug("{}".format(interfaces_will_change[interface]))
            success.add(interface)
        else:
            logger.critical("Verification failed for interface {}".format(interface))
            logger.critical("Desired configuration: {}".format(interfaces_will_change[interface]))
            logger.critical("Configuration pulled from DCNM: {}".format(handler.all_interfaces_nvpairs[interface]))
            failed.add(interface)
    if failed:
        if failed:
            _failed_dbg("verify_interface_change:  Failed configuring {}".format(failed),
                        ("Failed verification config changes to for the following switches:", failed))
    else:
        logger.debug("verify_interface_change: No Failures!")
        if verbose:
            _dbg("Successfully Verified All Interface Changes! Yay!")
    # return success, failed


def push_to_dcnm(handler: Handler, interfaces_to_change: dict, verbose: bool = True) -> set:
    """

    :param handler: An object that provides access to DCNM-interfacing objects
    :type handler: Handler
    :param interfaces_will_change: a dictionary of interfaces
    :type interfaces_will_change: dict
    :param verbose: output more information if this is set
    :type verbose: bool
    :return: successful changes
    :rtype: set

    Uses the handler to push desired changes to DCNM. Displays failures. Returns successes
    """
    success: set
    failure: set
    if verbose:
        _dbg("Putting changes to dcnm")
    success, failure = handler.put_interface_changes(interfaces_to_change)
    if failure:
        _failed_dbg("Failed putting to DCNM for the following: {}".format(failure),
                    ("Failed pushing config changes to DCNM for the following switches:", failure))
    else:
        if verbose:
            _dbg("Successfully Pushed All Configurations!")
    logger.debug("push_to_dcnm: success: {}".format(success))
    if verbose:
        _dbg("Successfully Pushed Following Configs", success)
    return success


def create_deploy_list(deploy_list: Union[Set[tuple], List[tuple], Tuple[tuple]]) -> List[dict]:
    """

    :param deploy_list: an iterator with items of the form ('Ethernet1/38', 'FDO24270209')
    :type deploy_list: iterator
    :return: new_deploy_list
    :rtype: list[dict]

    takes an iterator of the form [('Ethernet1/38', 'FDO24270209')] and returns a list of the form
    [{'serialNumber': 'FDO24270209', 'ifName': 'Ethernet1/38'
    """
    new_deploy_list: list = []
    for interface, switch in deploy_list:
        new_deploy_list.append({'serialNumber': switch, 'ifName': interface})
    return new_deploy_list


def deploy_to_fabric_using_interface_deploy(handler: Handler, deploy: Union[Set[tuple], List[tuple], Tuple[tuple]],
                                            policies: Optional[Union[list, tuple, str]] = None,
                                            deploy_timeout: int = 300,
                                            fallback: bool = False,
                                            verbose: bool = True):
    """

    :param handler: An object that provides access to DCNM-interfacing objects
    :type handler: Handler
    :param deploy: An iterable of the interface changes to deploy to the fabric
    :type deploy: an iterable
    :param policies: policy changes to deploy to the fabric
    :type policies: an iterable or a string
    :param deploy_timeout: timeout of the deploy operation, default is 300 seconds
    :type deploy_timeout: int
    :param fallback: True means this is a fallback operation
    :type fallback: bool
    :param verbose: True means to print more information
    :type verbose: bool

    Pushes interface and policy changes to the fabric using the interface deploy API
    """
    deploy_list: list = create_deploy_list(deploy)
    if verbose:
        _dbg('Deploying changes to switches')
    if handler.deploy_interfaces(deploy_list, deploy_timeout=deploy_timeout):
        logger.debug('successfully deployed to {}'.format(deploy))
        if verbose:
            _dbg('!!Successfully Deployed Config Changes to Switches!!', deploy)
    else:
        _failed_dbg("Failed deploying to {}".format(deploy),
                    ("Failed deploying configs to the following switches:", deploy))
    print()
    print('=' * 40)
    print('=' * 40)
    if policies and fallback:
        fallback_policy_deploy(handler, policies, deploy_timeout=deploy_timeout, verbose=verbose)
    print()
    print('=' * 40)
    print('=' * 40)
    print("FINISHED DEPLOYING. GO GET A BEER!")
    print('=' * 40)


def fallback_policy_deploy(handler: Handler,
                           policies: Union[list, tuple, str], deploy_timeout: int = 300, verbose: bool = True):
    """

    :param handler: An object that provides access to DCNM-interfacing objects
    :type handler: Handler
    :param policies: policy changes to deploy to the fabric
    :type policies: an iterable or a string
    :param deploy_timeout: timeout of the deploy operation, default is 300 seconds
    :type deploy_timeout: int
    :param verbose: True means to print more information
    :type verbose: bool

    Deploys previous policies during fallback operation
    """
    if isinstance(policies, str):
        policies = [policies]
    if verbose:
        _dbg("DEPLOYING POLICIES: ", policies)
    if handler.deploy_policies(policies, deploy_timeout=deploy_timeout):
        logger.debug('successfully deployed policies {}'.format(policies))
        if verbose:
            _dbg('!!Successfully Deployed Config Policies to Switches!!', policies)
    else:
        _failed_dbg("Failed deploying policies {}".format(policies),
                    ('Failed deploying the following policies:', policies))


def deploy_to_fabric_using_switch_deploy(handler: Handler,
                                         serial_numbers: Optional[Union[str, list, tuple]] = None,
                                         deploy_timeout: int = 300,
                                         verbose: bool = True):
    """

    :param handler: An object that provides access to DCNM-interfacing objects
    :type handler: Handler
    :param serial_numbers: serial numbers of swtiches
    :type serial_numbers: iterable or str
    :param deploy_timeout: timeout of the deploy operation, default is 300 seconds
    :type deploy_timeout: int
    :param verbose: True means to print more information
    :type verbose: bool

    Pushes interface and policy changes to the fabric using the switch level deploy API
    """
    deployed: set = set()
    logger.info("Deploying changes to switches")
    if verbose:
        _dbg('Deploying changes to switches', serial_numbers)
    if isinstance(serial_numbers, str):
        serial_numbers = [serial_numbers]
    elif serial_numbers is None:
        if not (handler.all_leaf_switches or handler.all_notleaf_switches):
            raise DCNMPolicyDeployError("serial numbers must be either a string or a list\n"
                                        "alternatively, the get_all_switches or get_switches_by_serial_number\n"
                                        "must be called before using this function")
        else:
            serial_numbers = handler.all_leaf_switches + handler.all_notleaf_switches
    logger.debug("deploy_to_fabric_using_switch_deploy: deploying: serial numbers: {}".format(serial_numbers))
    reduced_serial_numbers = serial_numbers.copy()
    if len(reduced_serial_numbers) > 1:
        if not handler.all_switches_vpc_pairs:
            handler.get_switches_vpc_pairs()
    for serial_number in reduced_serial_numbers:
        if serial_number in deployed:
            continue
        if handler.deploy_switch_config(serial_number):
            logger.debug('deploy returned successfully')
            if verbose:
                _dbg('deploy returned successfully for: ', serial_number)
        else:
            _failed_dbg("Failed deploying config to switch {}".format(serial_number),
                        ("Failed deploying configs to the following switch:", serial_number))
        deployed.add(serial_number)
        if len(reduced_serial_numbers) > 1 and serial_number in handler.switches \
                and handler.switches[serial_number].peerSerialNumber is not None:
            deployed.add(handler.switches[serial_number].peerSerialNumber)
    logger.debug("Deployed or attempted to deploy the following: {}".format(deployed))
    if verbose:
        _dbg("Deployed or attempted to deploy the following: ", deployed)
    logger.info('waiting for switches status')
    if verbose:
        _dbg('waiting for switches status')
    result = handler.wait_for_switches_status(serial_numbers=serial_numbers, timeout=deploy_timeout)
    if isinstance(result, bool):
        logger.debug('successfully deployed config to switch {}'.format(serial_numbers))
        if verbose:
            _dbg('!!Successfully Deployed Config Changes to Switches!!', serial_numbers)
    else:
        _failed_dbg("Failed deploying configs to the following switches {}".format(result),
                    ("Failed deploying configs to the following switches:", result))
    print()
    print('=' * 40)
    print('=' * 40)
    print("FINISHED DEPLOYING. GO GET A BEER!")
    print('=' * 40)


def _failed_dbg(log_msg: str, messages: tuple):
    init()
    logger.critical(log_msg)
    print()
    print()
    print(Back.BLACK + Fore.RED + '*' * 60)
    for i in messages:
        pprint(i)
    print('*' * 60)
    print()
    print()
    print(Style.RESET_ALL)


def depickle(pickle_file: str):
    depickle_conf = _file_check(pickle_file, loader=load, file_type='rb')
    return depickle_conf


def _file_check(file: str, loader: Callable = None, skip_load: bool = False, as_list: bool = False,
                file_type: str = 'r') -> Union[str, Iterable, bool]:
    """

    :param file: filename
    :type file: str
    :param loader: optional file reader
    :type loader: callable
    :param skip_load: don't read the file, just do the error checks
    :type skip_load: bool
    :param as_list: read the file contents into a list
    :type as_list: bool
    :param file_type: python file mode
    :type file_type: str
    :return: contents of the file or True if skip_load is set to True
    :rtype:

    Do various error checks for files and load contents using either a supplied loader or built-in read function
    """
    file_path = pathlib.Path(file)
    if file_path.is_file():
        if not skip_load:
            try:
                with open(file, file_type) as f:
                    if loader is not None:
                        contents = loader(f)
                    else:
                        if as_list:
                            contents = [item.strip() for item in f]
                        else:
                            contents = f.read()
            except Exception as e:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                stacktrace = traceback.extract_tb(exc_traceback)
                logger.debug(
                    "_file_check: file error {}".format(exc_type))
                logger.debug(sys.exc_info())
                logger.debug(stacktrace)
                raise
            if contents:
                return contents
            logger.critical(f"Error: empty input file, {file}")
            raise DCNMFileError(f"Error: empty input file, {file}")
        else:
            return True
    else:
        logger.critical("Error: file {} not found".format(file))
        _failed_dbg("Error: File {} not found".format(file),
                    ("File not found", file))
        raise DCNMFileError("Error: input file {} not found".format(file))


def _read_serials_from_file(file: str):
    """

    :param file: name of file of serial numbers
    :type file: str
    :return: list of serial numbers
    :rtype: list
    """
    serials = _file_check(file, as_list=True)
    return serials


def _get_uplinks(uplinks_file: str) -> Dict[str, list]:
    """
    :param uplinks_file: yaml file associating serial number to interfaces reserved for uplinks
    :type uplinks_file: yaml file
    :return: uplinks
    :rtype: dictionary, key is serial number, value is list of uplinks
    """
    import yaml
    yaml_loader = partial(yaml.load, Loader=yaml.FullLoader)
    uplinks = _file_check(uplinks_file, loader=yaml_loader)
    local_uplinks: Dict[str, list] = {}
    for model in uplinks:
        first = uplinks[model][0]
        last = uplinks[model][1]
        interface_range = range(int(first.split('/')[1]), int(last.split('/')[1]) + 1)
        local_uplinks[model] = [f'Ethernet{first.split("/")[0]}/{i}' for i in interface_range]
    return local_uplinks


def _get_serial_numbers(args: argparse.Namespace):
    """
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
