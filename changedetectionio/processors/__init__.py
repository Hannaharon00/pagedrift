from functools import lru_cache
from loguru import logger
from flask_babel import gettext, get_locale
import importlib
import inspect
import os
import pkgutil
import re

def find_sub_packages(package_name):
    """
    Find all sub-packages within the given package.

    :param package_name: The name of the base package to scan for sub-packages.
    :return: A list of sub-package names.
    """
    package = importlib.import_module(package_name)
    return [name for _, name, is_pkg in pkgutil.iter_modules(package.__path__) if is_pkg]


@lru_cache(maxsize=1)
def find_processors():
    """
    Find all subclasses of DifferenceDetectionProcessor in the specified package.
    Results are cached to avoid repeated discovery.

    :param package_name: The name of the package to scan for processor modules.
    :return: A list of (module, class) tuples.
    """
    package_name = "changedetectionio.processors"  # Name of the current package/module

    processors = []
    sub_packages = find_sub_packages(package_name)
    from changedetectionio.processors.base import difference_detection_processor

    for sub_package in sub_packages:
        module_name = f"{package_name}.{sub_package}.processor"
        try:
            module = importlib.import_module(module_name)

            # Iterate through all classes in the module
            for name, obj in inspect.getmembers(module, inspect.isclass):
                # Only register classes that are actually defined in this module (not imported)
                if (issubclass(obj, difference_detection_processor) and
                    obj is not difference_detection_processor and
                    obj.__module__ == module.__name__):
                    processors.append((module, sub_package))
                    break  # Only need one processor per module
        except (ModuleNotFoundError, ImportError) as e:
            logger.warning(f"Failed to import module {module_name}: {e} (find_processors())")

    # Discover plugin processors via pluggy
    try:
        from changedetectionio.pluggy_interface import plugin_manager
        plugin_results = plugin_manager.hook.register_processor()

        for result in plugin_results:
            if result and isinstance(result, dict):
                processor_module = result.get('processor_module')
                processor_name = result.get('processor_name')

                if processor_module and processor_name:
                    processors.append((processor_module, processor_name))
                    plugin_path = getattr(processor_module, '__file__', 'unknown location')
                    logger.info(f"Registered plugin processor: {processor_name} from {plugin_path}")
    except Exception as e:
        logger.warning(f"Error loading plugin processors: {e}")

    return processors


def get_parent_module(module):
    module_name = module.__name__
    if '.' not in module_name:
        return None  # Top-level module has no parent
    parent_module_name = module_name.rsplit('.', 1)[0]
    try:
        return importlib.import_module(parent_module_name)
    except Exception as e:
        pass

    return False



