import abc
import logging
import re
from abc import ABCMeta
from typing import List, Union, Optional

from DCNM_utils import _check_patterns

logger = logging.getLogger(__name__)


class Filter(metaclass=ABCMeta):
    def __init__(self, element_name):
        self.element_name = element_name

    @abc.abstractmethod
    def match(self, policy_dict: dict):
        element = search_for(policy_dict, self.get_element_name())
        return element

    def get_element_name(self):
        return self.element_name


class RegexFilter(Filter):
    def __init__(self, element_name: str, pattern: str):
        super().__init__(element_name)
        self.regex = re.compile(pattern)

    def match(self, policy_dict: dict):
        element = super().match(policy_dict)
        if element is not None and self.regex.search(element):
            return True
        return False


class PatternFilter(Filter):
    def __init__(self, element_name: str, pattern: Union[list, tuple]):
        super().__init__(element_name)
        self.pattern = pattern

    def match(self, policy_dict: dict):
        element = super().match(policy_dict)
        logger.debug(f"PatternFilter: element: {element} - pattern: {self.pattern}")
        if element is not None and _check_patterns(self.pattern, element):
            logger.debug(f"PatternFilter: returning True for element {element}")
            return True
        return False


def search_for(data, key):
    if isinstance(data, dict) and key in data:
        return data[key]
    elif isinstance(data, dict):
        for element in data:
            result = search_for(data[element], key)
            if result is not None:
                return result
    elif isinstance(data, list):
        for element in data:
            return search_for(element, key)
    else:
        return None


def filterfactory(filter_dict: dict):
    logger.debug(f"filterfactory: filter_dict: {filter_dict}")
    filters: List[Union[PatternFilter, RegexFilter]] = []
    for key, patterns in filter_dict.items():
        logger.debug(f"filterfactory: type(patterns): {type(patterns)}")
        if isinstance(patterns, (list, tuple)):
            filters.append(PatternFilter(key, patterns))
        elif isinstance(patterns, str):
            filters.append(RegexFilter(key, patterns))
    return filters
