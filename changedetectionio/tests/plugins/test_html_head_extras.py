"""Test that plugins can inject HTML into base.html <head> via get_html_head_extras hookimpl."""
import pytest
from flask import url_for, Response

from changedetectionio.pluggy_interface import hookimpl, plugin_manager

_MY_JS = "console.log('my_module_content loaded');"
_MY_CSS = ".my-module-example { color: red; }"


class _HeadExtrasPlugin:
    """Test plugin that injects tags pointing at its own Flask routes."""

    @hookimpl
    def get_html_head_extras(self):
        css_url = url_for('test_plugin_my_module_content_css')
        js_url  = url_for('test_plugin_my_module_content_js')
        return (
            f'<link rel="stylesheet" id="test-head-extra-css" href="{css_url}">\n'
            f'<script id="test-head-extra-js" src="{js_url}" defer></script>'
        )


@pytest.fixture(scope='module')
def plugin_routes(live_server):
    """Register plugin asset routes once per module (Flask routes can't be added twice)."""
    app = live_server.app

    @app.route('/test-plugin/my_module_content/css')
    def test_plugin_my_module_content_css():
        return Response(_MY_CSS, mimetype='text/css',
                        headers={'Cache-Control': 'max-age=3600'})

    @app.route('/test-plugin/my_module_content/js')
    def test_plugin_my_module_content_js():
        return Response(_MY_JS, mimetype='application/javascript',
                        headers={'Cache-Control': 'max-age=3600'})


