# HTML to TEXT/JSON DIFFERENCE self.fetcher

import hashlib
import json
import os
import re
import urllib3

from changedetectionio.conditions import execute_ruleset_against_all_plugins
from changedetectionio.content_fetchers.exceptions import checksumFromPreviousCheckWasTheSame
from ..base import difference_detection_processor
from changedetectionio.html_tools import PERL_STYLE_REGEX, cdata_in_document_to_text, TRANSLATE_WHITESPACE_TABLE
from changedetectionio import html_tools, content_fetchers
from changedetectionio.blueprint.price_data_follower import PRICE_DATA_TRACK_ACCEPT
from loguru import logger

from changedetectionio.processors.magic import guess_stream_type

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Translation marker for extraction - allows pybabel to find these strings
def _(x): return x
name = _('Webpage Text/HTML, JSON and PDF changes')
description = _('Detects all text changes where possible')
del _  # Remove marker
processor_weight = -100
list_badge_text = "Text"

JSON_FILTER_PREFIXES = ['json:', 'jq:', 'jqraw:']

# Assume it's this type if the server says nothing on content-type
DEFAULT_WHEN_NO_CONTENT_TYPE_HEADER = 'text/html'

class FilterNotFoundInResponse(ValueError):
    def __init__(self, msg, screenshot=None, xpath_data=None):
        self.screenshot = screenshot
        self.xpath_data = xpath_data
        ValueError.__init__(self, msg)


class PDFToHTMLToolNotFound(ValueError):
    def __init__(self, msg):
        ValueError.__init__(self, msg)


class FilterConfig:
    """Consolidates all filter and rule configurations from watch, tags, and global settings."""

    def __init__(self, watch, datastore):
        self.watch = watch
        self.datastore = datastore
        self.watch_uuid = watch.get('uuid')
        # Cache computed properties to avoid repeated list operations
        self._include_filters_cache = None
        self._subtractive_selectors_cache = None

    def _get_merged_rules(self, attr, include_global=False):
        """Merge rules from watch, tags, and optionally global settings."""
        watch_rules = self.watch.get(attr, [])
        tag_rules = self.datastore.get_tag_overrides_for_watch(uuid=self.watch_uuid, attr=attr)
        rules = list(dict.fromkeys(watch_rules + tag_rules))

        if include_global:
            global_rules = self.datastore.data['settings']['application'].get(f'global_{attr}', [])
            rules = list(dict.fromkeys(rules + global_rules))

        return rules

    @property
    def include_filters(self):
        if self._include_filters_cache is None:
            filters = self._get_merged_rules('include_filters')
            # Inject LD+JSON price tracker rule if enabled
            if self.watch.get('track_ldjson_price_data', '') == PRICE_DATA_TRACK_ACCEPT:
                filters += html_tools.LD_JSON_PRODUCT_OFFER_SELECTORS
            self._include_filters_cache = filters
        return self._include_filters_cache

    @property
    def subtractive_selectors(self):
        if self._subtractive_selectors_cache is None:
            watch_selectors = self.watch.get("subtractive_selectors", [])
            tag_selectors = self.datastore.get_tag_overrides_for_watch(uuid=self.watch_uuid, attr='subtractive_selectors')
            global_selectors = self.datastore.data["settings"]["application"].get("global_subtractive_selectors", [])
            self._subtractive_selectors_cache = [*tag_selectors, *watch_selectors, *global_selectors]
        return self._subtractive_selectors_cache

    @property
    def extract_lines_containing(self):
        return self._get_merged_rules('extract_lines_containing')

    @property
    def extract_text(self):
        return self._get_merged_rules('extract_text')

    @property
    def ignore_text(self):
        return self._get_merged_rules('ignore_text', include_global=True)

    @property
    def trigger_text(self):
        return self._get_merged_rules('trigger_text')

    @property
    def text_should_not_be_present(self):
        return self._get_merged_rules('text_should_not_be_present')

    def get_filter_config_hash(self):
        """
        Stable hash of the effective filter configuration.

        Used by the skip-logic in run_changedetection() so that any change to
        global settings, tag overrides, or watch filters automatically invalidates
        the raw-content-unchanged shortcut — without needing scattered
        clear_all_last_checksums() calls at every settings mutation site.
        """
        app = self.datastore.data['settings']['application']
        config = {
            'extract_lines_containing': sorted(self.extract_lines_containing),
            'extract_text':             sorted(self.extract_text),
            'ignore_text':              sorted(self.ignore_text),
            'include_filters':          sorted(self.include_filters),
            'subtractive_selectors':    sorted(self.subtractive_selectors),
            'text_should_not_be_present': sorted(self.text_should_not_be_present),
            'trigger_text':             sorted(self.trigger_text),
            # Global processing flags not captured by the filter lists above
            'ignore_whitespace':        app.get('ignore_whitespace', False),
            'strip_ignored_lines':      app.get('strip_ignored_lines', False),
        }
        return hashlib.md5(json.dumps(config, sort_keys=True).encode()).hexdigest()

    @property
    def has_include_filters(self):
        return bool(self.include_filters) and bool(self.include_filters[0].strip())

    @property
    def has_include_json_filters(self):
        return any(f.strip().startswith(prefix) for f in self.include_filters for prefix in JSON_FILTER_PREFIXES)

    @property
    def has_subtractive_selectors(self):
        return bool(self.subtractive_selectors) and bool(self.subtractive_selectors[0].strip())


class RuleEngine:
    """Evaluates blocking rules (triggers, conditions, text_should_not_be_present)."""

    @staticmethod
    def evaluate_trigger_text(content, trigger_patterns):
        """
        Check if trigger text is present. If trigger_text is configured,
        content is blocked UNLESS the trigger is found.
        Returns True if blocked, False if allowed.
        """
        if not trigger_patterns:
            return False

        # Assume blocked if trigger_text is configured
        result = html_tools.strip_ignore_text(
            content=str(content),
            wordlist=trigger_patterns,
            mode="line numbers"
        )
        # Unblock if trigger was found
        return not bool(result)

    @staticmethod
    def evaluate_text_should_not_be_present(content, patterns):
        """
        Check if forbidden text is present. If found, block the change.
        Returns True if blocked, False if allowed.
        """
        if not patterns:
            return False

        result = html_tools.strip_ignore_text(
            content=str(content),
            wordlist=patterns,
            mode="line numbers"
        )
        # Block if forbidden text was found
        return bool(result)

    @staticmethod
    def evaluate_conditions(watch, datastore, content):
        """
        Evaluate custom conditions ruleset.
        Returns True if blocked, False if allowed.
        """
        if not watch.get('conditions') or not watch.get('conditions_match_logic'):
            return False

        conditions_result = execute_ruleset_against_all_plugins(
            current_watch_uuid=watch.get('uuid'),
            application_datastruct=datastore.data,
            ephemeral_data={'text': content}
        )

        # Block if conditions not met
        return not conditions_result.get('result')


