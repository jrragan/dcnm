import importlib
import inspect
import logging
import os
from typing import Optional, Callable

from DCNM_connect import DcnmRestApi

logger = logging.getLogger(__name__)


class HandlerError(Exception):
    pass


class Handler:
    def __init__(self, dcnm: DcnmRestApi, dir='.'):
        self.dcnm = dcnm
        files = self._get_module_list(dir)
        self.dcnm_objects = self._import_dcnm_objects(files)

    def is_callable(self, name) -> Optional[Callable]:
        logger.debug(f"Handler: is_callable: checking {name}")
        for dcnm_obj in self.dcnm_objects.values():
            logger.debug(f"object dict: {dcnm_obj.__dict__}")
            if name in dcnm_obj.__class__.__dict__ or name in dcnm_obj.__dict__:
                logger.debug(f"Handler: found name {name} in {dcnm_obj}")
                return getattr(dcnm_obj, name)

    def __call__(self, name, *args, **kwargs):
        logger.debug(f"called {name}")
        logger.debug(args)
        print(kwargs)
        for dcnm_obj in self.dcnm_objects.values():
            if name in dcnm_obj.__class__.__dict__:
                return getattr(dcnm_obj, name)(*args, **kwargs)

    def _get_module_list(self, dir):
        files = [f.replace('.py', '') for f in os.listdir(dir) if f.startswith('dcnm_')]
        return files

    def _import_dcnm_objects(self, files):
        _modules = [importlib.import_module(file, ".") for file in files]
        dcnm_objects = {}
        for m in _modules:
            #print(f"module: {m}")
            for k, v in inspect.getmembers(m):
                # print(f"k: {k}, v: {v}")
                if "Dcnm" in k and inspect.isclass(v):
                    # print(k,v)
                    #print(f"k: {k}, v: {v}")
                    #print(f"bases: {v.__bases__}")
                    for base in v.__bases__:
                        if 'DcnmComponent' in str(base):
                            #print(f"{k} is of DcnmComponent")
                            dcnm_objects[k] = v(self, self.dcnm)
                            #print(f"dict after instantiation: {dcnm_objects[k].__dict__}")
                            #print(f"members after instantiation: {dcnm_objects[k].__class__.__dict__}")
                            break
        print(dcnm_objects)
        return dcnm_objects

    def __getattr__(self, name):
        logger.debug(f"handler: __getattr__: getting {name} of type {type(name)}")
        attribute = self.is_callable(name)
        if attribute is None:
            logger.debug(f"handler: __getattr__: Cannot find attribute {name}")
            raise HandlerError(f"Handler Cannot Find Attribute {name}")
        logger.debug(f"handler: __getattr__: attribute is {attribute}")
        if callable(attribute):
            def _method(*args, **kwargs):
                logger.debug("handler: __getattr__: tried to handle unknown method " + name)
                if args:
                    logger.debug("handler: __getattr__: it had arguments: " + str(args))
                y = self.__call__(name, *args, **kwargs)
                logger.debug(f"handler: __getattr__: y from __call__ is {y} and is {type(y)}")
                return y

            return _method
        else:
            return attribute


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        #print("singleton meta")
        if cls not in cls._instances:
            #print("Singleton running super")
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class DcnmComponent():
    def __init__(self, handler: Handler, dcnm_connector: DcnmRestApi, **kwargs):
        self.handler = handler
        self.dcnm = dcnm_connector
        super().__init__(**kwargs)

    def __getattr__(self, name):
        #print(f"class is {self.__class__}")
        logger.debug(f"DcnmComponent: __getattr__: getting {name} of type {type(name)}")
        # attribute = self.handler.is_callable(name)
        # print(f"attribute is {attribute}")
        # if callable(attribute):
        #     def _method(*args):
        #         logger.debug("tried to handle unknown method " + name)
        #         if args:
        #             logger.debug("it had arguments: " + str(args))
        #         y = self.handler(name, *args)
        #         logger.debug(f"y from handler is {y} and is {type(y)}")
        #         return y
        #
        #     return _method
        # else:
        #     return attribute
        return getattr(self.handler, name)


if __name__ == '__main__':
    dcnm = DcnmRestApi('10.10.10.10')
    handler = Handler(dcnm)
    print(handler.dcnm_objects)
