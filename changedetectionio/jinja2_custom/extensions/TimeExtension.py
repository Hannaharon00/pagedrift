"""
Jinja2 TimeExtension - Custom date/time handling for templates.

This extension provides the {% now %} tag for Jinja2 templates, offering timezone-aware
date/time formatting with support for time offsets.

Why This Extension Exists:
    The Arrow library has a now() function (arrow.now()), but Jinja2 templates cannot
    directly call Python functions - they need extensions or filters to expose functionality.

    This TimeExtension serves as a Jinja2-to-Arrow bridge that:

    1. Makes Arrow accessible in templates - Jinja2 requires registering functions/tags
       through extensions. You cannot use arrow.now() directly in a template.

    2. Provides template-friendly syntax - Instead of complex Python code, you get clean tags:
       {% now 'UTC' %}
       {% now 'UTC' + 'hours=2' %}
       {% now 'Europe/London', '%Y-%m-%d' %}

    3. Adds convenience features on top of Arrow:
       - Default timezone from environment variable (TZ) or config
       - Default datetime format configuration
       - Offset syntax parsing: 'hours=2,minutes=30' → shift(hours=2, minutes=30)
       - Empty string timezone support to use configured defaults

    4. Maintains security - Works within Jinja2's sandboxed environment so users
       cannot access arbitrary Python code or objects.

    Essentially, this is a Jinja2 wrapper around arrow.now() and arrow.shift() that
    provides user-friendly template syntax while maintaining security.

Basic Usage:
    {% now 'UTC' %}
    # Output: Wed, 09 Dec 2015 23:33:01

Custom Format:
    {% now 'UTC', '%Y-%m-%d %H:%M:%S' %}
    # Output: 2015-12-09 23:33:01

Timezone Support:
    {% now 'America/New_York' %}
    {% now 'Europe/London' %}
    {% now '' %}  # Uses default timezone from environment.default_timezone

Time Offsets (Addition):
    {% now 'UTC' + 'hours=2' %}
    {% now 'UTC' + 'hours=2,minutes=30' %}
    {% now 'UTC' + 'days=1,hours=2,minutes=15,seconds=10' %}

Time Offsets (Subtraction):
    {% now 'UTC' - 'minutes=11' %}
    {% now 'UTC' - 'days=2,minutes=33,seconds=1' %}

