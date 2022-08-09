import importlib
import inspect
import logging
import os
from typing import Optional, Callable, List, Dict

from DCNM_connect import DcnmRestApi

logger = logging.getLogger(__name__)


class HandlerError(Exception):
    pass


class SingletonMeta(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(SingletonMeta, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class Handler(metaclass=SingletonMeta):
    def __init__(self, dcnm: DcnmRestApi, module_directory: str = '.'):
        self.dcnm = dcnm
        self.module_directory = module_directory
        files: List[str] = self._get_module_list(module_directory)
        self.dcnm_objects: Dict[str, object] = self._import_dcnm_objects(files)
        self.dcnm_objects_dirs: Dict[str, List] = self._get_dcnm_objects_dirs()

    def _get_module_list(self, module_directory: str):
        files = [f.replace('.py', '') for f in os.listdir(module_directory) if f.startswith('dcnm_')]
        return files

    def _import_dcnm_objects(self, files: List[str]):
        _modules = [importlib.import_module(file, ".") for file in files]
        dcnm_objects = {}
        for m in _modules:
            for k, v in inspect.getmembers(m):
                if "Dcnm" in k and inspect.isclass(v) and any(["DcnmComponent" in str(base) for base in v.__bases__]):
                    dcnm_objects[k] = v(self, self.dcnm)
                    break
        logger.debug(dcnm_objects)
        return dcnm_objects

    def __getattr__(self, name: str):
        logger.debug(f"handler: __getattr__: getting {name} of type {type(name)}")
        dcnm_object_name = self.find_dcnm_object_attr(name)
        attribute = getattr(self.dcnm_objects[dcnm_object_name], name, None)
        if attribute is None:
            logger.debug(f"handler: __getattr__: Cannot find attribute {name}")
            raise HandlerError(f"Handler Cannot Find Attribute {name}")
        logger.debug(f"handler: __getattr__: attribute is {attribute}")
        if callable(attribute):
            def _method(*args, **kwargs):
                logger.debug(f"handler: __getattr__: tried to handle unknown method {name}")
                if args:
                    logger.debug(f"handler: __getattr__: it had arguments: {args}, {kwargs}")
                y = attribute(*args, **kwargs)
                logger.debug(f"handler: __getattr__: y from __call__ is {y} and is {type(y)}")
                return y

            return _method
        else:
            return attribute

    def _get_dcnm_objects_dirs(self):
        return {name: dir(dcnm_obj) for name, dcnm_obj in self.dcnm_objects.items()}

    def find_dcnm_object_attr(self, attribute):
        for name, dir in self.dcnm_objects_dirs.items():
            if attribute in dir:
                return name

    def __dir__(self):
        dirs = object.__dir__(self)
        for dcnm_obj in self.dcnm_objects.values():
            dirs += dir(dcnm_obj)
        return sorted(list(set(dirs)))

    def __repr__(self):
        return f'{type(self).__name__}({self.dcnm!r}, module_directory={self.module_directory!r})'


class DcnmComponent:
    def __init__(self, handler: Handler, dcnm_connector: DcnmRestApi, **kwargs):
        self.handler = handler
        self.dcnm = dcnm_connector
        super().__init__(**kwargs)

    def __getattr__(self, name):
        logger.debug(f"DcnmComponent: __getattr__: getting {name} of type {type(name)}")
        return getattr(self.handler, name)


if __name__ == '__main__':
    dcnm = DcnmRestApi('10.10.10.10')
    handler = Handler(dcnm)
    print(handler.dcnm_objects)
    print(dir(handler))
    print(handler.dcnm_objects_dirs)
    print(handler.find_dcnm_object_attr("get_switch_fabric"))