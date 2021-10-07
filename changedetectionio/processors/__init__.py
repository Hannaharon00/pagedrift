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



def get_custom_watch_obj_for_processor(processor_name):
    from changedetectionio.model import Watch
    watch_class = Watch.model
    processor_classes = find_processors()
    custom_watch_obj = next((tpl for tpl in processor_classes if tpl[1] == processor_name), None)
    if custom_watch_obj:
        # Parent of .processor.py COULD have its own Watch implementation
        parent_module = get_parent_module(custom_watch_obj[0])
        if hasattr(parent_module, 'Watch'):
            watch_class = parent_module.Watch

    return watch_class


def find_processor_module(processor_name):
    """
    Find the processor module by name.

    Args:
        processor_name: Processor machine name (e.g., 'image_ssim_diff')

    Returns:
        module: The processor's parent module, or None if not found
    """
    processor_classes = find_processors()
    processor_tuple = next((tpl for tpl in processor_classes if tpl[1] == processor_name), None)

    if processor_tuple:
        # Return the parent module (the package containing processor.py)
        return get_parent_module(processor_tuple[0])

    return None


@lru_cache(maxsize=1)
def get_plugin_processor_metadata():
    """Get metadata from plugin processors."""
    metadata = {}
    try:
        from changedetectionio.pluggy_interface import plugin_manager
        plugin_results = plugin_manager.hook.register_processor()

        for result in plugin_results:
            if result and isinstance(result, dict):
                processor_name = result.get('processor_name')
                meta = result.get('metadata', {})
                if processor_name:
                    metadata[processor_name] = meta
    except Exception as e:
        logger.warning(f"Error getting plugin processor metadata: {e}")
    return metadata

@lru_cache(maxsize=32)
def _available_processors_cached(locale_str):
    """
    Internal cached function that includes locale in cache key.
    This ensures translations are cached per-language instead of globally.

    :param locale_str: The locale string (e.g., 'en', 'it', 'zh')
    :return: A list of tuples (processor_name, translated_description, weight)
    """
    processor_classes = find_processors()

    # Check if DISABLED_PROCESSORS env var is set
    disabled_processors_env = os.getenv('DISABLED_PROCESSORS', 'image_ssim_diff').strip()
    disabled_processors = []
    if disabled_processors_env:
        # Parse comma-separated list and strip whitespace
        disabled_processors = [p.strip() for p in disabled_processors_env.split(',') if p.strip()]
        logger.info(f"DISABLED_PROCESSORS set, disabling: {disabled_processors}")

    available = []
    plugin_metadata = get_plugin_processor_metadata()

    for module, sub_package_name in processor_classes:
        # Skip disabled processors
        if sub_package_name in disabled_processors:
            logger.debug(f"Skipping processor '{sub_package_name}' (in DISABLED_PROCESSORS)")
            continue

        # Check if this is a plugin processor
        if sub_package_name in plugin_metadata:
            meta = plugin_metadata[sub_package_name]
            description = gettext(meta.get('name', sub_package_name))
            # Plugin processors start from weight 10 to separate them from built-in processors
            weight = 100 + meta.get('processor_weight', 0)
        else:
            # Try to get the 'name' attribute from the processor module first
            if hasattr(module, 'name'):
                description = gettext(module.name)
            else:
                # Fall back to processor_description from parent module's __init__.py
                parent_module = get_parent_module(module)
                if parent_module and hasattr(parent_module, 'processor_description'):
                    description = gettext(parent_module.processor_description)
                else:
                    # Final fallback to a readable name
                    description = sub_package_name.replace('_', ' ').title()

            # Get weight for sorting (lower weight = higher in list)
            weight = 0  # Default weight for processors without explicit weight

            # Check processor module itself first
            if hasattr(module, 'processor_weight'):
                weight = module.processor_weight
            else:
                # Fall back to parent module (package __init__.py)
                parent_module = get_parent_module(module)
                if parent_module and hasattr(parent_module, 'processor_weight'):
                    weight = parent_module.processor_weight

        available.append((sub_package_name, description, weight))

    # Sort by weight (lower weight = appears first)
    available.sort(key=lambda x: x[2])

    # Return as tuples without weight (for backwards compatibility)
    return [(name, desc) for name, desc, weight in available]

def available_processors():
    """
    Get a list of processors by name and description for the UI elements.
    Can be filtered via DISABLED_PROCESSORS environment variable (comma-separated list).

    This function delegates to a locale-aware cached version to ensure translations
    are cached per-language instead of globally.

    :return: A list of tuples (processor_name, translated_description)
    """
    # Get current locale and use it as cache key
    # Convert Babel Locale object to string for use as cache key
    locale = get_locale()
    locale_str = str(locale) if locale else 'en'
    return _available_processors_cached(locale_str)


