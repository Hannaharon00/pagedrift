#!/usr/bin/env python3

"""Re #4021 - the "Mark all viewed" button must be driven by live state, not by render-time presence.

The button used to be wrapped in {% if unread_count %}, so when nothing was unread it did not
exist in the DOM at all. A second tab could therefore never show it after a change arrived, and
never hide it after another tab marked everything viewed - no socket event can style an element
that isn't there.

It is now always rendered and revealed by body.has-any-unviewed, which is set server-side via
extra_classes and kept live by the general_stats_update socket event. These assertions pin both
halves: the element is always present, and the body class tracks the unviewed state.
"""

