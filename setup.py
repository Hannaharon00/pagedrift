#!/usr/bin/env python
import os.path
import re

from setuptools import setup, find_packages
from setuptools.command.build_py import build_py
import shutil

here = os.path.abspath(os.path.dirname(__file__))


def read(*parts):
    with open(os.path.join(here, *parts), 'r', encoding='utf-8') as f:
        return f.read()


