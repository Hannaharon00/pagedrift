import pluggy
import os
import importlib
import sys
from loguru import logger

# Global plugin namespace for changedetection.io
PLUGIN_NAMESPACE = "changedetectionio"

# Set up Plugin Manager
plugin_manager = pluggy.PluginManager(PLUGIN_NAMESPACE)

# Register hookspecs
plugin_manager.add_hookspecs(ChangeDetectionSpec)

