import pluggy
import os
import importlib
import sys
from loguru import logger

# Global plugin namespace for changedetection.io
PLUGIN_NAMESPACE = "changedetectionio"

hookspec = pluggy.HookspecMarker(PLUGIN_NAMESPACE)
hookimpl = pluggy.HookimplMarker(PLUGIN_NAMESPACE)


class ChangeDetectionSpec:
    """Hook specifications for extending changedetection.io functionality."""

    @hookspec
    def ui_edit_stats_extras(watch):
        """Return HTML content to add to the stats tab in the edit view.

        Args:
            watch: The watch object being edited

        Returns:
            str: HTML content to be inserted in the stats tab
        """
        pass

    @hookspec
    def register_content_fetcher(self):
        """Return a tuple of (fetcher_name, fetcher_class) for content fetcher plugins.

        The fetcher_name should start with 'html_' and the fetcher_class
        should inherit from changedetectionio.content_fetchers.base.Fetcher

        Returns:
            tuple: (str: fetcher_name, class: fetcher_class)
        """
        pass

    @hookspec
    def fetcher_status_icon(fetcher_name):
        """Return status icon HTML attributes for a content fetcher.

        Args:
            fetcher_name: The name of the fetcher (e.g., 'html_webdriver', 'html_js_zyte')

        Returns:
            str: HTML string containing <img> tags or other status icon elements
                 Empty string if no custom status icon is needed
        """
        pass

    @hookspec
    def plugin_static_path(self):
        """Return the path to the plugin's static files directory.

        Returns:
            str: Absolute path to the plugin's static directory, or None if no static files
        """
        pass

    @hookspec
    def get_itemprop_availability_override(self, content, fetcher_name, fetcher_instance, url, llm_intent=None):
        """Provide custom implementation of get_itemprop_availability for a specific fetcher.

        This hook allows plugins to provide their own product availability detection
        when their fetcher is being used. This is called as a fallback when the built-in
        method doesn't find good data.

        Args:
            content: The HTML/text content to parse
            fetcher_name: The name of the fetcher being used (e.g., 'html_js_zyte')
            fetcher_instance: The fetcher instance that generated the content
            url: The URL being watched/checked
            llm_intent: Optional user-supplied intent string (e.g. "alert when price drops below $300")

        Returns:
            dict or None: Dictionary with availability data:
                {
                    'price': float or None,
                    'availability': str or None,  # e.g., 'in stock', 'out of stock'
                    'currency': str or None,      # e.g., 'USD', 'EUR'
                }
                Or None if this plugin doesn't handle this fetcher or couldn't extract data
        """
        pass

    @hookspec
    def plugin_settings_tab(self):
        """Return settings tab information for this plugin.

        This hook allows plugins to add their own settings tab to the settings page.
        Settings will be saved to a separate JSON file in the datastore directory.

        Returns:
            dict or None: Dictionary with settings tab information:
                {
                    'plugin_id': str,           # Unique identifier (e.g., 'zyte_fetcher')
                    'tab_label': str,           # Display name for tab (e.g., 'Zyte Fetcher')
                    'form_class': Form,         # WTForms Form class for the settings
                    'template_path': str,       # Optional: path to Jinja2 template (relative to plugin)
                                                # If not provided, a default form renderer will be used
                }
                Or None if this plugin doesn't provide settings
        """
        pass

    @hookspec
    def register_processor(self):
        """Register an external processor plugin.

        External packages can implement this hook to register custom processors
        that will be discovered alongside built-in processors.

        Returns:
            dict or None: Dictionary with processor information:
                {
                    'processor_name': str,      # Machine name (e.g., 'osint_recon')
                    'processor_module': module, # Module containing processor.py
                    'processor_class': class,   # The perform_site_check class
                    'metadata': {               # Optional metadata
                        'name': str,            # Display name
                        'description': str,     # Description
                        'processor_weight': int,# Sort weight (lower = higher priority)
                        'list_badge_text': str, # Badge text for UI
                    }
                }
                Return None if this plugin doesn't provide a processor
        """
        pass

    @hookspec
    def update_handler_alter(update_handler, watch, datastore):
        """Modify or wrap the update_handler before it processes a watch.

        This hook is called after the update_handler (perform_site_check instance) is created
        but before it calls call_browser() and run_changedetection(). Plugins can use this to:
        - Wrap the handler to add logging/metrics
        - Modify handler configuration
        - Add custom preprocessing logic

        Args:
            update_handler: The perform_site_check instance that will process the watch
            watch: The watch dict being processed
            datastore: The application datastore

        Returns:
            object or None: Return a modified/wrapped handler, or None to keep the original.
                           If multiple plugins return handlers, they are chained in registration order.
        """
        pass

    @hookspec
    def update_finalize(update_handler, watch, datastore, processing_exception):
        """Called after watch processing completes (success or failure).

        This hook is called in the finally block after all processing is complete,
        allowing plugins to perform cleanup, update metrics, or log final status.

        The plugin can access update_handler.last_logging_insert_id if it was stored
        during update_handler_alter, and use processing_exception to determine if
        the processing succeeded or failed.

        Args:
            update_handler: The perform_site_check instance (may be None if creation failed)
            watch: The watch dict that was processed (may be None if not loaded)
            datastore: The application datastore
            processing_exception: The exception from the main processing block, or None if successful.
                                 This does NOT include cleanup exceptions - only exceptions from
                                 the actual watch processing (fetch, diff, etc).

        Returns:
            None: This hook doesn't return a value
        """
        pass

    @hookspec
    def get_html_head_extras():
        """Return HTML to inject into the <head> of every page via base.html.

        Plugins can use this to add <script>, <style>, or <link> tags that should
        be present on all pages.  Return a raw HTML string or None.

        IMPORTANT: Always use Flask's url_for() for any src/href URLs so that
        sub-path deployments (nginx reverse proxy with USE_X_SETTINGS / X-Forwarded-Prefix)
        work correctly.  This hook is called inside a request context so url_for() is
        always available.

        For small amounts of CSS/JS, return them inline — no file-serving needed::

            from changedetectionio.pluggy_interface import hookimpl

            @hookimpl
            def get_html_head_extras(self):
                return (
                    '<style>.my-module-banner { color: red; }</style>\\n'
                    '<script>console.log("my_module_content loaded");</script>'
                )

        For larger assets, register your own lightweight Flask routes in the plugin
        module and point to them with url_for() so the sub-path prefix is handled
        automatically::

            from flask import url_for, Response
            from changedetectionio.pluggy_interface import hookimpl
            from changedetectionio.flask_app import app as _app

            MY_CSS = ".my-module-example { color: red; }"
            MY_JS  = "console.log('my_module_content loaded');"

            @_app.route('/my_module_content/css')
            def my_module_content_css():
                return Response(MY_CSS, mimetype='text/css',
                                headers={'Cache-Control': 'max-age=3600'})

            @_app.route('/my_module_content/js')
            def my_module_content_js():
                return Response(MY_JS, mimetype='application/javascript',
                                headers={'Cache-Control': 'max-age=3600'})

            @hookimpl
            def get_html_head_extras(self):
                css = url_for('my_module_content_css')
                js  = url_for('my_module_content_js')
                return (
                    f'<link rel="stylesheet" href="{css}">\\n'
                    f'<script src="{js}" defer></script>'
                )

        Returns:
            str or None: Raw HTML string to inject inside <head>, or None
        """
        pass


# Set up Plugin Manager
plugin_manager = pluggy.PluginManager(PLUGIN_NAMESPACE)

# Register hookspecs
plugin_manager.add_hookspecs(ChangeDetectionSpec)

# Load plugins from subdirectories
def load_plugins_from_directories():
    # List of (python_package_prefix, filesystem_path) pairs to scan for plugins.
    # NOTE: processors/restock_diff/plugins is intentionally excluded here — those
    # plugins are registered via register_builtin_restock_plugins() to avoid the
    # circular import: restock_diff/__init__.py → model.Watch → content_fetchers → pluggy_interface.
    plugin_dirs = [
        (
            'changedetectionio.conditions.plugins',
            os.path.join(os.path.dirname(__file__), 'conditions', 'plugins'),
        ),
    ]

    for module_prefix, dir_path in plugin_dirs:
        if not os.path.exists(dir_path):
            continue

        # Get all Python files (excluding __init__.py)
        for filename in os.listdir(dir_path):
            if filename.endswith(".py") and filename != "__init__.py":
                module_name = filename[:-3]  # Remove .py extension
                module_path = f"{module_prefix}.{module_name}"

                try:
                    module = importlib.import_module(module_path)
                    # Register the plugin with pluggy
                    plugin_manager.register(module, module_name)
                except (ImportError, AttributeError) as e:
                    print(f"Error loading plugin {module_name}: {e}")

# Load plugins
load_plugins_from_directories()

# Discover installed plugins from external packages (if any)
plugin_manager.load_setuptools_entrypoints(PLUGIN_NAMESPACE)

# Function to inject datastore into plugins that need it
def inject_datastore_into_plugins(datastore):
    """Inject the global datastore into plugins that need access to settings.

    This should be called after plugins are loaded and datastore is initialized.

    Args:
        datastore: The global ChangeDetectionStore instance
    """
    for plugin_name, plugin_obj in plugin_manager.list_name_plugin():
        # Check if plugin has datastore attribute and it's not set
        if hasattr(plugin_obj, 'datastore'):
            if plugin_obj.datastore is None:
                plugin_obj.datastore = datastore
                logger.debug(f"Injected datastore into plugin: {plugin_name}")

