"""Watch-list filtering — the single source of truth for "which watches match the
current view".

Shared by the watch list (the rendered table + the /uuids endpoint) and by the
bulk actions in the ui blueprint (mark-all-viewed, recheck-all) so a filtered view
and any action taken on it always operate on the SAME set. Keeping these as plain
functions (rather than duplicated per blueprint) is what stops the action buttons
from drifting away from the list's filter.
"""


def resolve_active_tag_uuid(datastore, active_tag_req):
    if not active_tag_req:
        return None
    for uuid, tag in datastore.data['settings']['application'].get('tags', {}).items():
        if active_tag_req == tag.get('title', '').lower().strip() or active_tag_req == uuid:
            return uuid
    return None


def list_filters_from_args(datastore, args):
    active_tag_req = (args.get('tag') or '').lower().strip()
    return {
        'with_errors': args.get('with_errors') == "1",
        'unread_only': args.get('unread') == "1",
        'deals': args.get('deals') == "1",
        'processor': (args.get('processor') or '').strip(),
        'tag_uuid': resolve_active_tag_uuid(datastore, active_tag_req),
        'search_q': args.get('q').strip().lower() if args.get('q') else False,
    }


def watch_is_deal(watch):
    """A restock/price watch whose latest check reported a price DROP."""
    if not watch.has_restock_info:
        return False
    restock = watch['restock']
    # Defensive: restock should be a Restock, but some sources (e.g. the LLM restock fallback
    # plugin) can leave a plain dict. Normalise so .get_price_change_percent() always exists
    # and a rendering of the watchlist can't 500 over it. Lazy import avoids an import cycle.
    if not hasattr(restock, 'get_price_change_percent'):
        from changedetectionio.processors.restock_diff import Restock
        restock = Restock(restock)
    pct = restock.get_price_change_percent()
    return pct is not None and pct < 0


def watch_matches_tag(datastore, watch, f):
    # Membership includes tags auto-applied via a Tag's url_match_pattern, not just
    # watch['tags'] (manually-assigned) — otherwise a regex-matched watch shows its
    # tag badge on the row but silently drops out of that tag's filtered/tab view.
    return not f['tag_uuid'] or f['tag_uuid'] in datastore.get_all_tags_for_watch(watch['uuid'])


def watch_in_context(datastore, watch, f):
    """Tag + processor — the working set the operator is looking at."""
    if not watch_matches_tag(datastore, watch, f):
        return False
    if f['processor'] and watch.get('processor') != f['processor']:
        return False
    return True


