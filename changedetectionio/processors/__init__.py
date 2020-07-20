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


