"""
History/diff rendering for text_json_diff processor.

This module handles the visualization of text/HTML/JSON changes by rendering
a side-by-side or unified diff view with syntax highlighting and change markers.
"""

import os
import time
from flask_babel import gettext
from loguru import logger

from changedetectionio import diff, strtobool
from changedetectionio.diff import (
    REMOVED_STYLE, ADDED_STYLE, REMOVED_INNER_STYLE, ADDED_INNER_STYLE,
    REMOVED_PLACEMARKER_OPEN, REMOVED_PLACEMARKER_CLOSED,
    ADDED_PLACEMARKER_OPEN, ADDED_PLACEMARKER_CLOSED,
    CHANGED_PLACEMARKER_OPEN, CHANGED_PLACEMARKER_CLOSED,
    CHANGED_INTO_PLACEMARKER_OPEN, CHANGED_INTO_PLACEMARKER_CLOSED
)
from changedetectionio.notification.handler import apply_html_color_to_body


def build_diff_cell_visualizer(content, resolution=100):
    """
    Build a visual cell grid for the diff visualizer.

    Analyzes the content for placemarkers indicating changes and creates a
    grid of cells representing the document, with each cell marked as:
    - 'deletion' for removed content
    - 'insertion' for added content
    - 'mixed' for cells containing both deletions and insertions
    - empty string for cells with no changes

    Args:
        content: The diff content with placemarkers
        resolution: Number of cells to create (default 100)

    Returns:
        List of dicts with 'class' key for each cell's CSS class
    """
    if not content:
        return [{'class': ''} for _ in range(resolution)]
    now = time.time()
    # Work with character positions for better accuracy
    content_length = len(content)

    if content_length == 0:
        return [{'class': ''} for _ in range(resolution)]

    chars_per_cell = max(1, content_length / resolution)

    # Track change type for each cell
    cell_data = {}

    # Placemarkers to detect
    change_markers = {
        REMOVED_PLACEMARKER_OPEN: 'deletion',
        ADDED_PLACEMARKER_OPEN: 'insertion',
        CHANGED_PLACEMARKER_OPEN: 'deletion',
        CHANGED_INTO_PLACEMARKER_OPEN: 'insertion',
    }

    # Find all occurrences of each marker
    for marker, change_type in change_markers.items():
        pos = 0
        while True:
            pos = content.find(marker, pos)
            if pos == -1:
                break

            # Calculate which cell this marker falls into
            cell_index = min(int(pos / chars_per_cell), resolution - 1)

            if cell_index not in cell_data:
                cell_data[cell_index] = change_type
            elif cell_data[cell_index] != change_type:
                # Mixed changes in this cell
                cell_data[cell_index] = 'mixed'

            pos += len(marker)

    # Build the cell list
    cells = []
    for i in range(resolution):
        change_type = cell_data.get(i, '')
        cells.append({'class': change_type})

    logger.debug(f"Built diff cell visualizer: {len([c for c in cells if c['class']])} cells with changes out of {resolution} in {time.time() - now:.2f}s")

    return cells

# Diff display preferences configuration - single source of truth
DIFF_PREFERENCES_CONFIG = {
    'changesOnly': {'default': True, 'type': 'bool'},
    'ignoreWhitespace': {'default': False, 'type': 'bool'},
    'removed': {'default': True, 'type': 'bool'},
    'added': {'default': True, 'type': 'bool'},
    'replaced': {'default': True, 'type': 'bool'},
    'type': {'default': 'diffLines', 'type': 'value'},
    'llm_all_changes': {'default': False, 'type': 'bool'},
}

