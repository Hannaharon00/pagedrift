"""
Notification settings — child blueprint of /settings.

Registered by the parent settings blueprint at url_prefix='/notifications', so the
URLs land at /settings/notifications/<backend>. Today the only backend is apprise;
future backends (simple_email, raw webhooks, etc.) slot in as sibling routes here
without re-shaping the URL space again.

The eventual data-model refactor is to give each notification config its own
uuid (`notification_uuid`) referenced from global/watch/group settings, instead
of inlining apprise URL strings on every record — that's not done here; this
file just gives that future work a stable home.
"""
import os

