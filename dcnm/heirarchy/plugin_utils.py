import argparse
import functools
import importlib
import inspect
import logging
import sys
import traceback
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Set

from handler import Handler

logger = logging.getLogger(__name__)


class NameConflictError(BaseException):
    """Raise for errors in adding plugins due to the same name."""


class RegisterPlugin:
    """Register an instantiated plugin to the PLUGINS dict."""

    def __init__(self, name):
        self.alt_name = name

    def __call__(self, plugin_class):
        plugin_class.alt_name = self.alt_name
        return plugin_class


class PlugIn(ABC):
    """
    Plugin Abstract Base Class
    """

    def __init__(self):
        print(f"initialize {self.__class__.__name__}")
        self.handler: Optional[Handler] = None
        self.args = None
        self.serials = None
        self.leaf_only: bool = False

    @abstractmethod
    def initialize(self, handler: Handler, args: argparse.Namespace,
                   serials: Optional[list] = None) -> Any:
        """
        Initializes plugin
        """
        pass

    @abstractmethod
    def __call__(self, *args, **kwargs) -> bool:
        """
        Calls the plugin for each interface and returns True
        if the interface is to be changed

        :param args: possible arguments for the plugin
        :return: bool
        """
        pass


class PlugInInitializationError(Exception):
    pass


def singleton(cls):
    """Make a class a Singleton class (only one instance)"""

    @functools.wraps(cls)
    def wrapper_singleton(*args, **kwargs):
        if not wrapper_singleton.instance:
            wrapper_singleton.instance = cls(*args, **kwargs)
        return wrapper_singleton.instance

    wrapper_singleton.instance = None
    return wrapper_singleton


@singleton
class PlugInEngine:
    # We are going to receive a list of plugins as parameter
    def __init__(self, plugin_module: str = "plugins"):
        self.plugin_module = importlib.import_module(plugin_module, ".")
        # self._check_loaded_plugin_state(self.plugin_module)
        self.plugins: Dict = {}
        self._initialize_plugins()
        self._selected_plugins: Set = set()

    def _initialize_plugins(self):
        for name, obj in inspect.getmembers(self.plugin_module):
            if inspect.isclass(obj):
                for base in obj.__bases__:
                    if 'PlugIn' in str(base):
                        print(obj)
                        if hasattr(obj, "alt_name"):
                            app_name = obj.alt_name
                        else:
                            app_name = obj.__name__
                        self.plugins[app_name] = obj()
                        break

    def set_plugins(self, plugins: List):
        self._selected_plugins = {plugin for plugin in plugins if plugin in self.plugins.keys()}

    @property
    def selected_plugins(self):
        return self._selected_plugins

    def initialize_selected_plugins(self, handler: Handler, args: argparse.Namespace, serials: Optional[list] = None):
        try:
            for plugin in self.selected_plugins:
                logger.debug("initialize_selected_plugins: intializing {}".format(plugin))
                self.plugins[plugin].initialize(handler, args, serials)
        except:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            stacktrace = traceback.extract_tb(exc_traceback)
            logger.critical("ERROR Initializing Plugin {}".format(plugin))
            logger.debug(sys.exc_info())
            logger.debug(stacktrace)
            raise PlugInInitializationError("Error Initializing Plugin {}".format(plugin))

    def run_selected_plugins(self, interface: tuple, details: dict, leaf: bool):
       change = False
       for plugin in self.selected_plugins:
           # if the function is to run only on leaf switches and this is a leaf switch
           # or the function can run on any switch
           if (self.plugins[plugin].leaf_only and leaf) or not self.plugins[plugin].leaf_only:
               logger.debug("run_selected_plugins: sending {} to plugin {}".format(interface, plugin))
               logger.debug("detail: {}".format(details))
               logger.debug("{}".format(self.plugins[plugin]))
               change = self.plugins[plugin](interface, details) or change
           else:
               change = change or False
       return change


if __name__ == '__main__':
    app = PlugInEngine()
    print(app.plugin_module)
    # print(print(inspect.getmembers(app.plugin_module)))
    print(app.plugins)
    print(list(app.plugins.keys()))
