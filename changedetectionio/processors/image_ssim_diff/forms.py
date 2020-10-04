"""
Configuration forms for fast screenshot comparison processor.
"""

from wtforms import SelectField, StringField, validators, ValidationError, IntegerField
from flask_babel import lazy_gettext as _l
from changedetectionio.forms import processor_text_json_diff_form
import re

from changedetectionio.processors.image_ssim_diff import SCREENSHOT_COMPARISON_THRESHOLD_OPTIONS


def validate_bounding_box(form, field):
    """Validate bounding box format: x,y,width,height with integers."""
    if not field.data:
        return  # Optional field

    if len(field.data) > 100:
        raise ValidationError(_l('Bounding box value is too long'))

    # Should be comma-separated integers
    if not re.match(r'^\d+,\d+,\d+,\d+$', field.data):
        raise ValidationError(_l('Bounding box must be in format: x,y,width,height (integers only)'))

    # Validate values are reasonable (not negative, not ridiculously large)
    parts = [int(p) for p in field.data.split(',')]
    for part in parts:
        if part < 0:
            raise ValidationError(_l('Bounding box values must be non-negative'))
        if part > 10000:  # Reasonable max screen dimension
            raise ValidationError(_l('Bounding box values are too large'))


