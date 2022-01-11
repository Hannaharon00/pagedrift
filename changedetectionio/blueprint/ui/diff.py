from flask import Blueprint, request, redirect, url_for, flash, render_template, make_response, send_from_directory
from flask_babel import gettext

import re
import importlib
from loguru import logger
from markupsafe import Markup

from changedetectionio.diff import (
    REMOVED_STYLE, ADDED_STYLE, REMOVED_INNER_STYLE, ADDED_INNER_STYLE,
    REMOVED_PLACEMARKER_OPEN, REMOVED_PLACEMARKER_CLOSED,
    ADDED_PLACEMARKER_OPEN, ADDED_PLACEMARKER_CLOSED,
    CHANGED_PLACEMARKER_OPEN, CHANGED_PLACEMARKER_CLOSED,
    CHANGED_INTO_PLACEMARKER_OPEN, CHANGED_INTO_PLACEMARKER_CLOSED
)
from changedetectionio.store import ChangeDetectionStore
from changedetectionio.blueprint import plaintext_response
from changedetectionio.auth_decorator import login_optionally_required


def _clean_litellm_error(exc) -> str:
    """Return a short, human-readable error string from a litellm exception.

    litellm embeds the raw provider JSON in str(exc), which can be hundreds of
    characters of verbose quota detail.  We try to pull just the provider's
    'message' field; failing that we return the first non-empty line with the
    'litellm.XxxError:' class prefix stripped.
    """
    import json, re
    raw = str(exc)
    # Try to parse the embedded JSON block (starts at first '{')
    brace = raw.find('{')
    if brace >= 0:
        try:
            payload = json.loads(raw[brace:])
            msg = (payload.get('error') or {}).get('message') or ''
            if msg:
                # Take only the first sentence / line — provider messages can be long
                return msg.split('\n')[0].split('. ')[0].strip() + '.'
        except Exception:
            pass
    # Fallback: strip the "litellm.XxxError: litellm.XxxError: providerException - " prefix
    first_line = raw.split('\n')[0]
    first_line = re.sub(r'^(litellm\.\w+:\s*)+', '', first_line)
    first_line = re.sub(r'\w+Exception\s*-\s*', '', first_line).strip()
    return first_line or raw.split('\n')[0]


    @diff_blueprint.route("/diff/<uuid_str:uuid>/llm-summary", methods=['GET'])
    @login_optionally_required
    def diff_llm_summary(uuid):
        """
        Generate (or return cached) an AI summary of the diff between two snapshots.
        Called via AJAX from the diff page when no cached summary exists.
        Returns JSON: {"summary": "...", "error": null} or {"summary": null, "error": "..."}
        """
        import difflib
        from flask import jsonify

        try:
            watch = datastore.data['watching'][uuid]
        except KeyError:
            return jsonify({'summary': None, 'error': 'Watch not found'}), 404

        llm_cfg = datastore.data.get('settings', {}).get('application', {}).get('llm', {})
        if not llm_cfg.get('model'):
            return jsonify({'summary': None, 'error': 'LLM not configured'}), 400

        dates = list(watch.history.keys())
        if len(dates) < 2:
            return jsonify({'summary': None, 'error': 'Not enough history'}), 400

        # Default baseline for the watchlist "Summary" link (when no explicit from_version
        # is requested) is configurable at Settings > AI. Default 'second_last_version'
        # compares the previous snapshot; 'since_last_viewed' uses the operator's last view.
        if llm_cfg.get('watchlist_overview_summary', 'second_last_version') == 'since_last_viewed':
            best_from = watch.get_from_version_based_on_last_viewed
            default_from = best_from if best_from else dates[-2]
        else:
            default_from = dates[-2]
        from_version      = request.args.get('from_version', default_from)
        to_version        = request.args.get('to_version', dates[-1])
        from changedetectionio.llm.evaluator import DiffPrefs
        prefs             = DiffPrefs.from_request_args(request.args)
        all_changes       = prefs.all_changes
        ignore_whitespace = prefs.ignore_whitespace
        show_removed      = prefs.show_removed
        show_added        = prefs.show_added

        def _prep(text):
            """Optionally normalise whitespace on each line before diffing."""
            if not ignore_whitespace:
                return text.splitlines()
            return [' '.join(line.split()) for line in text.splitlines()]

        def _make_unified_diff(a_text, b_text):
            lines = list(difflib.unified_diff(_prep(a_text), _prep(b_text), lineterm='', n=3))
            return '\n'.join(lines[2:]) if len(lines) > 2 else '\n'.join(lines)

        def _apply_filters(diff_text):
            """Strip +/- lines the user has hidden in the UI so the LLM matches what they see."""
            if show_removed and show_added:
                return diff_text
            out = []
            for line in diff_text.splitlines():
                if line.startswith('-') and not show_removed:
                    continue
                if line.startswith('+') and not show_added:
                    continue
                out.append(line)
            return '\n'.join(out)

        try:
            from_text = watch.get_history_snapshot(timestamp=from_version)
            to_text = watch.get_history_snapshot(timestamp=to_version)
        except Exception as e:
            return jsonify({'summary': None, 'error': f'Could not read snapshots: {e}'}), 500

        if all_changes:
            # Build sequential diffs for every intermediate snapshot between from and to
            # so the LLM sees the full timeline of changes, not just start→end
            sorted_dates = sorted(dates)
            try:
                start_idx = sorted_dates.index(from_version)
                end_idx   = sorted_dates.index(to_version)
            except ValueError:
                start_idx, end_idx = 0, len(sorted_dates) - 1

            steps = sorted_dates[start_idx:end_idx + 1]
            segments = []
            for i in range(len(steps) - 1):
                a_ts, b_ts = steps[i], steps[i + 1]
                try:
                    a_text = watch.get_history_snapshot(timestamp=a_ts) or ''
                    b_text = watch.get_history_snapshot(timestamp=b_ts) or ''
                except Exception:
                    continue
                seg = _apply_filters(_make_unified_diff(a_text, b_text))
                if seg.strip():
                    segments.append(f'=== {a_ts} → {b_ts} ===\n{seg}')

            diff_text = '\n\n'.join(segments) if segments else ''
        else:
            diff_text = _apply_filters(_make_unified_diff(from_text, to_text))

        if not diff_text.strip():
            return jsonify({'summary': None, 'error': 'No differences found'})

        from changedetectionio.llm.evaluator import (
            summarise_change, get_effective_summary_prompt, build_summary_cache_prompt,
            is_global_token_budget_exceeded, get_global_token_budget_month,
            LLMInputTooLargeError,
        )

        # Diff-pref flags + system prompt + active model are part of the cache key
        # so prompt or model changes bust the cache.
        from changedetectionio.llm.evaluator import get_llm_settings
        _ls = get_llm_settings(datastore)
        _max_summary_tokens = _ls.max_summary_tokens
        _llm_model = _ls.model
        cache_prompt = build_summary_cache_prompt(
            effective_prompt=get_effective_summary_prompt(watch, datastore),
            max_summary_tokens=_max_summary_tokens,
            prefs=prefs,
            model=_llm_model,
        )

        # Check cache — keyed by version pair + prompt hash (invalidates if prompt changes)
        cached = watch.get_llm_diff_summary(from_version, to_version, prompt=cache_prompt)
        if cached:
            import time
            datastore.set_last_viewed(uuid, int(time.time()))
            return jsonify({'summary': cached, 'error': None, 'cached': True})

