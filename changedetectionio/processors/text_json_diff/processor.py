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


class ContentTransformer:
    """Handles text transformations like trimming, sorting, and deduplication."""

    @staticmethod
    def trim_whitespace(text):
        """Remove leading/trailing whitespace from each line."""
        # Use generator expression to avoid building intermediate list
        return '\n'.join(line.strip() for line in text.replace("\n\n", "\n").splitlines())

    @staticmethod
    def remove_duplicate_lines(text):
        """Remove duplicate lines while preserving order."""
        return '\n'.join(dict.fromkeys(line for line in text.replace("\n\n", "\n").splitlines()))

    @staticmethod
    def sort_alphabetically(text):
        """Sort lines alphabetically (case-insensitive)."""
        # Remove double line feeds before sorting
        text = text.replace("\n\n", "\n")
        return '\n'.join(sorted(text.splitlines(), key=lambda x: x.lower()))

    @staticmethod
    def extract_lines_containing(text, substrings):
        """Keep only lines that contain at least one of the given substrings (case-insensitive)."""
        needles = [s.lower() for s in substrings if s.strip()]
        if not needles:
            return text
        return '\n'.join(
            line for line in text.splitlines()
            if any(needle in line.lower() for needle in needles)
        )

    @staticmethod
    def extract_by_regex(text, regex_patterns):
        """Extract text matching regex patterns."""
        # Use list of strings instead of concatenating lists repeatedly (avoids O(n²) behavior)
        regex_matched_output = []

        for s_re in regex_patterns:
            # Check if it's perl-style regex /.../
            if re.search(PERL_STYLE_REGEX, s_re, re.IGNORECASE):
                regex = html_tools.perl_style_slash_enclosed_regex_to_options(s_re)
                result = re.findall(regex, text)

                for match in result:
                    if type(match) is tuple:
                        regex_matched_output.extend(match)
                        regex_matched_output.append('\n')
                    else:
                        regex_matched_output.append(match)
                        regex_matched_output.append('\n')
            else:
                # Plain text search (case-insensitive)
                r = re.compile(re.escape(s_re), re.IGNORECASE)
                res = r.findall(text)
                if res:
                    for match in res:
                        regex_matched_output.append(match)
                        regex_matched_output.append('\n')

        return ''.join(regex_matched_output) if regex_matched_output else ''


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


class ContentProcessor:
    """Handles content preprocessing, filtering, and extraction."""

    def __init__(self, fetcher, watch, filter_config, datastore):
        self.fetcher = fetcher
        self.watch = watch
        self.filter_config = filter_config
        self.datastore = datastore

    def preprocess_rss(self, content):
        """
        Convert CDATA/comments in RSS to usable text.

        Supports two RSS processing modes:
        - 'default': Inline CDATA replacement (original behavior)
        - 'formatted': Format RSS items with title, link, guid, pubDate, and description (CDATA unmarked)
        """
        from changedetectionio import rss_tools
        rss_mode = self.datastore.data["settings"]["application"].get("rss_reader_mode")
        if rss_mode:
            # Format RSS items nicely with CDATA content unmarked and converted to text
            return rss_tools.format_rss_items(content)
        else:
            # Default: Original inline CDATA replacement
            return cdata_in_document_to_text(html_content=content)

    def preprocess_pdf(self, raw_content):
        """Convert PDF to HTML using external tool."""
        from shutil import which
        tool = os.getenv("PDF_TO_HTML_TOOL", "pdftohtml")
        if not which(tool):
            raise PDFToHTMLToolNotFound(
                f"Command-line `{tool}` tool was not found in system PATH, was it installed?"
            )

        import subprocess
        proc = subprocess.Popen(
            [tool, '-stdout', '-', '-s', 'out.pdf', '-i'],
            stdout=subprocess.PIPE,
            stdin=subprocess.PIPE
        )
        proc.stdin.write(raw_content)
        proc.stdin.close()
        html_content = proc.stdout.read().decode('utf-8')
        proc.wait(timeout=60)

        # Add metadata for change detection
        metadata = (
            f"<p>Added by changedetection.io: Document checksum - "
            f"{hashlib.md5(raw_content).hexdigest().upper()} "
            f"Original file size - {len(raw_content)} bytes</p>"
        )
        return html_content.replace('</body>', metadata + '</body>')

    def preprocess_json(self, raw_content):
        """Format and sort JSON content."""
        # Then we re-format it, else it does have filters (later on) which will reformat it anyway
        try:
            content = html_tools.extract_json_as_string(content=raw_content, json_filter="json:$")
        except html_tools.JSONNotFound:
            # The Content-Type header indicated JSON, but no parsable JSON was found in the body
            # (e.g. GWT-RPC or other formats that some servers mislabel as application/json).
            # Don't error the whole watch - keep the raw content so it can still be shown/diffed.
            # Re https://github.com/dgtlmoon/changedetection.io/issues/3827
            logger.warning("Content-Type indicated JSON but no parsable JSON was found, keeping raw content")
            return raw_content

        # Sort JSON to avoid false alerts from reordering
        try:
            content = json.dumps(json.loads(content), sort_keys=True, indent=2, ensure_ascii=False)
        except Exception:
            # Might be malformed JSON, continue anyway
            pass

        return content

    def apply_include_filters(self, content, stream_content_type):
        """Apply CSS, XPath, or JSON filters to extract specific content."""
        filtered_content = ""

        for filter_rule in self.filter_config.include_filters:
            # XPath filters
            if filter_rule[0] == '/' or filter_rule.startswith('xpath:'):
                filtered_content += html_tools.xpath_filter(
                    xpath_filter=filter_rule.replace('xpath:', ''),
                    html_content=content,
                    append_pretty_line_formatting=not self.watch.is_source_type_url,
                    is_xml=stream_content_type.is_rss or stream_content_type.is_xml
                )

            # XPath1 filters (first match only)
            elif filter_rule.startswith('xpath1:'):
                filtered_content += html_tools.xpath1_filter(
                    xpath_filter=filter_rule.replace('xpath1:', ''),
                    html_content=content,
                    append_pretty_line_formatting=not self.watch.is_source_type_url,
                    is_xml=stream_content_type.is_rss or stream_content_type.is_xml
                )

            # JSON filters
            elif any(filter_rule.startswith(prefix) for prefix in JSON_FILTER_PREFIXES):
                filtered_content += html_tools.extract_json_as_string(
                    content=content,
                    json_filter=filter_rule
                )

            # CSS selectors, default fallback
            else:
                filtered_content += html_tools.include_filters(
                    include_filters=filter_rule,
                    html_content=content,
                    append_pretty_line_formatting=not self.watch.is_source_type_url
                )

        # Raise error if filter returned nothing
        if not filtered_content.strip():
            raise FilterNotFoundInResponse(
                msg=self.filter_config.include_filters,
                screenshot=self.fetcher.screenshot,
                xpath_data=self.fetcher.xpath_data
            )

        return filtered_content

    def apply_subtractive_selectors(self, content):
        """Remove elements matching subtractive selectors."""
        return html_tools.element_removal(self.filter_config.subtractive_selectors, content)

    def extract_text_from_html(self, html_content, stream_content_type):
        """Convert HTML to plain text."""
        do_anchor = self.datastore.data["settings"]["application"].get("render_anchor_tag_content", False)

        return html_tools.html_to_text(
            html_content=html_content,
            render_anchor_tag_content=do_anchor,
            is_rss=stream_content_type.is_rss
        )


class ChecksumCalculator:
    """Calculates checksums with various options."""

    @staticmethod
    def calculate(text, ignore_whitespace=False):
        """Calculate MD5 checksum of text content."""
        if ignore_whitespace:
            text = text.translate(TRANSLATE_WHITESPACE_TABLE)
        return hashlib.md5(text.encode('utf-8')).hexdigest()


