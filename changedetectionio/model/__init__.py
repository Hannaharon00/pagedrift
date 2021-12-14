import os
import uuid

from changedetectionio import strtobool
from .persistence import EntityPersistenceMixin, _determine_entity_type

__all__ = ['EntityPersistenceMixin', 'watch_base']

from ..browser_steps.browser_steps import browser_steps_get_valid_steps

USE_SYSTEM_DEFAULT_NOTIFICATION_FORMAT_FOR_WATCH = 'System default'
CONDITIONS_MATCH_LOGIC_DEFAULT = 'ALL'


        """Override dict.update() to track modifications to writable fields."""
        # Call parent update first
        super().update(*args, **kwargs)

        # Mark as edited for any writable fields that were updated
        # Handle both update(dict) and update(key=value) forms
        if args:
            for key in args[0].keys():
                self._mark_field_as_edited(key)
        for key in kwargs.keys():
            self._mark_field_as_edited(key)


    def pop(self, key, *args):
        """Override dict.pop() to track removal of writable fields."""
        result = super().pop(key, *args)
        self._mark_field_as_edited(key)
        return result

    def setdefault(self, key, default=None):
        """Override dict.setdefault() to track modifications to writable fields."""
        # Only marks as edited if key didn't exist (i.e., a new value was set)
        existed = key in self
        result = super().setdefault(key, default)
        if not existed:
            self._mark_field_as_edited(key)
        return result

    @property
    def was_edited(self):
        """
        Check if watch configuration was edited since last processing.

        Returns:
            bool: True if writable fields were modified, False otherwise
        """
        return getattr(self, '_watch_base__watch_was_edited', False)

    def reset_watch_edited_flag(self):
        """
        Reset the watch edited flag after successful processing.

        Call this after processing completes to allow future content-only change detection.
        """
        self.__watch_was_edited = False

    @classmethod
    def get_property_names(cls):
        """
        Get all @property attribute names from this model class using introspection.

        This discovers computed/derived properties that are not stored in the datastore.
        These properties should be filtered out during PUT/POST requests.

        Returns:
            frozenset: Immutable set of @property attribute names from the model class
        """
        import functools

        # Create a cached version if it doesn't exist
        if not hasattr(cls, '_cached_get_property_names'):
            @functools.cache
            def _get_props():
                properties = set()
                # Use introspection to find all @property attributes
                for name in dir(cls):
                    # Skip private/magic attributes
                    if name.startswith('_'):
                        continue
                    try:
                        attr = getattr(cls, name)
                        # Check if it's a property descriptor
                        if isinstance(attr, property):
                            properties.add(name)
                    except (AttributeError, TypeError):
                        continue
                return frozenset(properties)

            cls._cached_get_property_names = _get_props

        return cls._cached_get_property_names()

    def __deepcopy__(self, memo):
        """
        Custom deepcopy for all watch_base subclasses (Watch, Tag, etc.).

