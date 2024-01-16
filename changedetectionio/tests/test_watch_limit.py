#!/usr/bin/env python3
"""PAGE_WATCH_LIMIT - the optional cap on how many watches one instance will hold.

The limit is enforced in datastore.add_watch(), which every add path funnels through, but each
surface has to report it in its own terms: a flash for the UI, a 429 for the API, one flash for
a whole file in the importers, and nothing at all (just a None) where there's no request context.
"""

