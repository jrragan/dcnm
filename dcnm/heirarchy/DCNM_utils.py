import functools
import logging
import re
import sys
import threading
import traceback
from copy import deepcopy
from datetime import timedelta
from itertools import cycle
from pprint import pprint
from time import time, sleep
from typing import Dict, Optional, Union, List, Tuple, Any

from DCNM_errors import DCNMServerResponseError, DCNMParameterError
from policies import InfoFromPolicies

logger = logging.getLogger('dcnm_utils')


def error_handler(msg):
    def decorator(func):
        @functools.wraps(func)
        def wrapper_decorator(*args, **kwargs):
            try:
                value = func(*args, **kwargs)
            except DCNMServerResponseError as e:
                logger.debug(e.args)
                e = eval(e.args[0])
                if isinstance(e['DATA'], (list, tuple)):
                    logger.critical("{} - {}".format(msg, e['DATA'][0]['message']))
                elif isinstance(e['DATA'], str):
                    logger.critical("{} - {}".format(msg, e['DATA']))
                logger.debug("{}".format(e))
                raise
            return value

        return wrapper_decorator

    return decorator


def _spin(msg, start, frames, _stop_spin):
    while not _stop_spin.is_set():
        frame = next(frames)
        sec, fsec = divmod(round(100 * (time() - start)), 100)
        frame += "  ({} : {}.{:02.0f})".format(msg, timedelta(seconds=sec), fsec)
        print('\r', frame, sep='', end='', flush=True)
        sleep(0.2)


def spinner(msg="Elapsed Time"):
    def decorator(func):
        @functools.wraps(func)
        def wrapper_decrorator(*args, **kwargs):
            _stop_spin = threading.Event()
            start = time()
            _spin_thread = threading.Thread(target=_spin, args=(msg, start, cycle(r'-\|/'), _stop_spin))
            _spin_thread.start()
            try:
                value = func(*args, **kwargs)
            except Exception as e:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                stacktrace = traceback.extract_tb(exc_traceback)
                logger.debug(
                    "response {}".format(value))
                logger.debug(sys.exc_info())
                logger.debug(stacktrace)
                raise
            finally:
                stop = time()
                if _spin_thread:
                    _stop_spin.set()
                    _spin_thread.join()
                print()
                print("=" * 60)
                print("Elapsed Time: ")
                print("=" * 60)
                pprint(stop - start)
                print("=" * 60)
                print()
            return value

        return wrapper_decrorator

    return decorator


def _check_response(response: dict):
    if response['RETURN_CODE'] > 299:
        logger.error("ERROR IN RESPONSE FROM DCNM: {}".format(response))
        raise DCNMServerResponseError("{}".format(response))
    else:
        return response


def _check_action_response(response: dict, method: str, message: str, data: Any) -> bool:
    if response["RETURN_CODE"] != 200:
        logger.critical("ERROR: {}: {} {} FAILED".format(method, message, data))
        logger.critical("ERROR: {}: returned info {}".format(method, response))
        return False
    logger.debug("{} successful: {}".format(method, response))
    return True


def get_info_from_policies_config(policies: Dict[str, list], config: str,
                                  key_tuple: Optional[Union[List[int], Tuple[int]]] = [0],
                                  value_tuple: Optional[Union[List[int], Tuple[int]]] = [1]) -> Optional[List[
    InfoFromPolicies]]:
    """

    :param policies: a dictionary of switch policies
    :type policies: dict
    :param config: config to match within switch policies, this is a regex that may contain groups
    :type config: str
    :param key_tuple: if provided, each int represents a group value to include in the dictionary key of the
          returned dictionary. serial number is always appended as the final tuple value. by default the first
          value (result[0]) is appended
    :type key_tuple: optional list or tuple of ints
    :param value_tuple: if provided, if provided, each int represents a group value to include in the dictionary value of the
          returned dictionary. by default the second item (result[1]) is appended
    :type value_tuple: optional list or tuple of ints
    :return:
    :rtype: list of dictionaries

    takes switch policies and patterns to match
    returns list of info_from_polices data class objects of the form
    InfoFromPolicies(existing_descriptions_local, policyId)
    where existing_descriptions is a dictionary and the policyId is a str
    """
    existing_policyId_local = []
    policies_local: dict = deepcopy(policies)
    pattern = re.compile(config, re.MULTILINE)
    for SN, policies in policies_local.items():
        for policy in policies:
            policyId = policy['policyId']
            existing_descriptions_local: dict = dict()
            result = pattern.findall(policy['generatedConfig'])
            if result:
                for item in result:
                    derived_key = list()
                    derived_value = list()
                    if key_tuple:
                        for i in key_tuple:
                            derived_key.append(item[i])
                    derived_key.append(SN)
                    if len(derived_key) == 1:
                        derived_key = derived_key[0]
                    else:
                        derived_key = tuple(derived_key)
                    if value_tuple:
                        for i in value_tuple:
                            derived_value.append(item[i])
                    if len(derived_value) == 1:
                        derived_value = derived_value[0]
                    else:
                        derived_value = tuple(value_tuple)
                    existing_descriptions_local[derived_key] = derived_value
                    logger.debug("derived key {}, derived value {}".format(derived_key, derived_value))

                existing_descriptions_local[derived_key] = derived_value
            logger.debug(
                "read_existing_descriptions_from_policies: existing descriptions: {}".format(
                    existing_descriptions_local))
            existing_policyId_local.append(InfoFromPolicies(existing_descriptions_local, policyId))
    if not existing_policyId_local:
        return None
    return existing_policyId_local


def _check_patterns(patterns: List[Union[str, tuple]], string_to_check: Union[str, dict]) -> bool:
    """
    :param patterns: regular expressions or a tuple
    :type patterns: a lists of strings or tuples
    :param string_to_check: string or a dictionary to be matched
    :type string_to_check:
    :return: true if matched
    :rtype: bool

    helper function for matching regular expressions.
    if pattern is a tuple, the regular expression is element one and element zero is the key of a dictionary where
    the value is the string to be matched
    """
    if string_to_check is None:
        return False
    elif not isinstance(string_to_check, (str, dict)):
        logger.error("_check_patterns: failure: string_to_check wrong type {}".format(string_to_check))
        raise DCNMParameterError("string_to_check must be a string or a dictionary")
    if isinstance(patterns, (list, tuple)):
        for pattern in patterns:
            if isinstance(pattern, str):
                pattern = re.compile(pattern, re.MULTILINE)
                if pattern.search(string_to_check):
                    return True
            elif isinstance(pattern, (list, tuple)):
                pattern = re.compile(pattern[1], re.MULTILINE)
                if pattern.search(string_to_check[pattern[0]]):
                    return True
            else:
                logger.error("_check_patterns: failure: pattern {}, string {}".format(pattern, string_to_check))
                raise DCNMParameterError("pattern must be a string or tuple of two strings")
    else:
        logger.error("_check_patterns: patterns wrong type {}".format(patterns))
        raise DCNMParameterError("patterns must be a list or tuple")
    return False
