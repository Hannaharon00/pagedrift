import pluggy
import os
import importlib
import sys
from . import default_plugin

# ✅ Ensure that the namespace in HookspecMarker matches PluginManager
PLUGIN_NAMESPACE = "changedetectionio_conditions"

hookspec = pluggy.HookspecMarker(PLUGIN_NAMESPACE)
hookimpl = pluggy.HookimplMarker(PLUGIN_NAMESPACE)


class ConditionsSpec:
    """Hook specifications for extending JSON Logic conditions."""

    @hookspec
    def register_operators():
        """Return a dictionary of new JSON Logic operators."""
        pass

    @hookspec
    def register_operator_choices():
        """Return a list of new operator choices."""
        pass

    @hookspec
    def register_field_choices():
        """Return a list of new field choices."""
        pass

    @hookspec
    def add_data(current_watch_uuid, application_datastruct, ephemeral_data):
        """Add to the datadict"""
        pass
        
    @hookspec
    def ui_edit_stats_extras(watch):
        """Return HTML content to add to the stats tab in the edit view"""
        pass

# ✅ Set up Pluggy Plugin Manager
plugin_manager = pluggy.PluginManager(PLUGIN_NAMESPACE)

