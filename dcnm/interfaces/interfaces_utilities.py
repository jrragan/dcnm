import logging
import pathlib
import sys
import traceback
from copy import deepcopy
from functools import partial
from pickle import load
from pprint import pprint
from typing import Callable, Optional, Union, Dict, List, Tuple

import pandas
from colorama import init, Back, Fore, Style
from pandas import read_excel

from DCNM_errors import DCNMPolicyDeployError
from DCNM_errors import ExcelFileError, DCNMFileError
from dcnm_interfaces import DcnmInterfaces

logger = logging.getLogger('interfaces_utilities')


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
        existing_descriptions_local = {(interface['interface'], interface['switch']): interface['description'] for interface
                                       in
                                       existing_descriptions_local}
        logger.debug("read_existing_descriptions: existing descriptions: {}".format(existing_descriptions_local))
        return existing_descriptions_local


def get_interfaces_to_change(dcnm: DcnmInterfaces,
                             change_functions: List[Tuple[Callable, Optional[dict], bool]]) -> Tuple[
                              Dict[tuple, dict], Dict[tuple, dict]]:
    """

    :param dcnm: dcnm object
    :type dcnm: DcnmInterfaces
    :param change_functions: a list of tuples with each tuple of the form
    (a function object to call, an optional dictionary containing args to pass to function, a boolean which is True
    if the function is to run only on leaf switches)
    :type change_functions: list[tuple[Callable, Optional[dict], bool]]
    :return: a tuple of dictionaries
    :rtype: tuple[dict[tuple, dict], dict[tuple, dict]]

    provide a list of callables to apply
    the function iterates through the interface tuple and interface policy details of the all_interfaces_nvpairs
    parameter and provides each of those values along with the optional dictionary of parameters to each callable
    returns two dictionaries. the first is the interfaces to change along with the changes to make and the other
    is the original dictionary of policies
    """
    existing_interfaces = deepcopy(dcnm.all_interfaces_nvpairs)
    interfaces_to_change: Dict[tuple, dict] = {}
    interfaces_original: Dict[tuple, dict] = {}
    for interface, details in existing_interfaces.items():
        change: bool = False
        # print(details)
        change = _run_functions(change_functions, details, interface,
                                leaf=interface[1] in dcnm.all_leaf_switches)
        if change:
            interfaces_original[interface] = dcnm.all_interfaces_nvpairs[interface]
            interfaces_to_change[interface] = details
    logger.debug("Interfaces to change: {}".format(interfaces_to_change))
    return interfaces_to_change, interfaces_original


def _run_functions(change_functions, details, interface, leaf=True):
    """

    :param change_functions:
    :type change_functions:
    :param details:
    :type details:
    :param interface:
    :type interface:
    :param leaf:
    :type leaf:
    :return:
    :rtype:

    helper function
    """
    change = False
    for function in change_functions:
        # if the function is to run only on leaf switches and this is a leaf switch
        # or the function can run on any switch
        if (function[2] and leaf) or not function[2]:
            if function[1]:
                logger.debug("_run_functions: sending {} to function {}".format(interface, function))
                logger.debug("detail: {}".format(details))
                logger.debug("{}".format(function[0]))
                change = function[0](interface, details, **function[1]) or change
            else:
                logger.debug("_run_functions: sending {} to function {}".format(interface, function))
                logger.debug("detail: {}".format(details))
                logger.debug("{}".format(function[0]))
                change = function[0](interface, details) or change
        else:
            change = change or False

    return change


def verify_interface_change(dcnm: DcnmInterfaces, interfaces_will_change: dict, verbose: bool = True, **kwargs):
    dcnm.get_interfaces_nvpairs(save_prev=True, **kwargs)
    failed: set = set()
    success: set = set()
    if verbose: _dbg("Verifying Interface Configurations")
    interfaces_will_change_local = deepcopy(interfaces_will_change)
    all_interfaces_nv_pairs_local = deepcopy(dcnm.all_interfaces_nvpairs)
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
            logger.critical("Configuration pulled from DCNM: {}".format(dcnm.all_interfaces_nvpairs[interface]))
            failed.add(interface)
    if failed:
        if failed:
            _failed_dbg("verify_interface_change:  Failed configuring {}".format(failed),
                        ("Failed verification config changes to for the following switches:", failed))
    else:
        logger.debug("verify_interface_change: No Failures!")
        if verbose: _dbg("Successfully Verified All Interface Changes! Yay!")
    # return success, failed


def push_to_dcnm(dcnm: DcnmInterfaces, interfaces_to_change: dict, verbose: bool = True) -> set:
    # make changes
    success: set
    failure: set
    if verbose:
        _dbg("Putting changes to dcnm")
    success, failure = dcnm.put_interface_changes(interfaces_to_change)
    if failure:
        _failed_dbg("Failed putting to DCNM for the following: {}".format(failure),
                    ("Failed pushing config changes to DCNM for the following switches:", failure))
    else:
        if verbose: _dbg("Successfully Pushed All Configurations!")
    logger.debug("push_to_dcnm: success: {}".format(success))
    if verbose: _dbg("Successfully Pushed Following Configs", success)
    return success


def deploy_to_fabric_using_interface_deploy(dcnm: DcnmInterfaces, deploy,
                                            policies: Optional[Union[list, tuple, str]] = None,
                                            deploy_timeout: int = 300,
                                            fallback: bool = False,
                                            verbose: bool = True):
    deploy_list: list = DcnmInterfaces.create_deploy_list(deploy)
    if verbose:
        _dbg('Deploying changes to switches')
    if dcnm.deploy_interfaces(deploy_list, deploy_timeout=deploy_timeout):
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
        if isinstance(policies, str):
            policies = [policies]
        if verbose: _dbg("DEPLOYING POLICIES: ", policies)
        if dcnm.deploy_policies(policies, deploy_timeout=deploy_timeout):
            logger.debug('successfully deployed policies {}'.format(policies))
            if verbose:
                _dbg('!!Successfully Deployed Config Policies to Switches!!', policies)
        else:
            _failed_dbg("Failed deploying policies {}".format(policies),
                        ('Failed deploying the following policies:', policies))
    print()
    print('=' * 40)
    print('=' * 40)
    print("FINISHED DEPLOYING. GO GET A BEER!")
    print('=' * 40)


def deploy_to_fabric_using_switch_deploy(dcnm: DcnmInterfaces, serial_numbers: Optional[Union[str, list]],
                                         deploy_timeout: int = 300,
                                         verbose: bool = True):
    deployed: set = set()
    logger.info("Deploying changes to switches")
    if verbose:
        _dbg('Deploying changes to switches', serial_numbers)
    if isinstance(serial_numbers, str): serial_numbers = [serial_numbers]
    if serial_numbers is None:
        if not (dcnm.all_leaf_switches or dcnm.all_notleaf_switches):
            raise DCNMPolicyDeployError("serial numbers must be either a string or a list\n"
                                        "alternatively, the get_all_switches or get_switches_by_serial_number\n"
                                        "must be called before using this function")
        else:
            serial_numbers = list(dcnm.all_leaf_switches.keys()) + list(dcnm.all_notleaf_switches.keys())
    logger.debug("deploy_to_fabric_using_switch_deploy: deploying: serial numbers: {}".format(serial_numbers))
    reduced_serial_numbers = serial_numbers.copy()
    if len(reduced_serial_numbers) > 1:
        if not dcnm.all_switches_vpc_pairs:
            dcnm.get_switches_vpc_pairs()
    for serial_number in reduced_serial_numbers:
        if serial_number in deployed:
            continue
        if dcnm.deploy_switch_config(serial_number):
            logger.debug('deploy returned successfully')
            if verbose: _dbg('deploy returned successfully for: ', serial_number)
        else:
            _failed_dbg("Failed deploying config to switch {}".format(serial_number),
                        ("Failed deploying configs to the following switch:", serial_number))
        deployed.add(serial_number)
        if len(reduced_serial_numbers) > 1 and serial_number in dcnm.all_switches_vpc_pairs \
                and dcnm.all_switches_vpc_pairs[serial_number] is not None:
            deployed.add(dcnm.all_switches_vpc_pairs[serial_number])
    logger.debug("Deployed or attempted to deploy the following: {}".format(deployed))
    if verbose: _dbg("Deployed or attempted to deploy the following: ", deployed)
    logger.info('waiting for switches status')
    if verbose: _dbg('waiting for switches status')
    result = dcnm.wait_for_switches_status(serial_numbers=serial_numbers, timeout=deploy_timeout)
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
    depickle_conf = _file_check(pickle_file, loader=load, type='rb')
    return depickle_conf


def _file_check(file, loader=None, skip_load=False, as_list=False, type='r'):
    file_path = pathlib.Path(file)
    if file_path.is_file():
        if not skip_load:
            try:
                with open(file, type) as f:
                    if loader is not None:
                        contents = loader(f)
                    else:
                        if as_list:
                            contents = [item.strip() for item in f]
                        else:
                            contents = f.read()
            except:
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
