import os
import uuid

from changedetectionio import strtobool
from .persistence import EntityPersistenceMixin, _determine_entity_type

__all__ = ['EntityPersistenceMixin', 'watch_base']

from ..browser_steps.browser_steps import browser_steps_get_valid_steps

USE_SYSTEM_DEFAULT_NOTIFICATION_FORMAT_FOR_WATCH = 'System default'
CONDITIONS_MATCH_LOGIC_DEFAULT = 'ALL'


class watch_base(dict):
    """
    Base watch domain model (inherits from dict for backward compatibility).

    WARNING: This class inherits from dict, which violates proper encapsulation.
    Dict inheritance is legacy technical debt that should be refactored to a proper
    domain model (e.g., Pydantic BaseModel) for better type safety and validation.

    TODO: Migrate to Pydantic BaseModel for:
          - Type safety and IDE autocomplete
          - Automatic validation
          - Clear separation between domain model and serialization
          - Database backend abstraction (file → postgres → mongodb)
          - Configuration override chain resolution (Watch → Tag → Global)
          - Immutability options
          - Better testing
          - USE https://docs.pydantic.dev/latest/integrations/datamodel_code_generator TO BUILD THE MODEL FROM THE API-SPEC!!!

    CHAIN RESOLUTION ARCHITECTURE:
        The dream is a 3-level override hierarchy:
            Watch settings → Tag/Group settings → Global settings

        Current implementation: MANUAL resolution scattered across codebase
        - Processors manually check watch.get('field')
        - Loop through tags to find overrides_watch=True
        - Fall back to datastore['settings']['application']['field']

        Pydantic implementation: AUTOMATIC resolution via @computed_field
        - Single source of truth for each setting's resolution logic
        - Type-safe, testable, self-documenting
        - Example: watch.resolved_fetch_backend (instead of nested dict navigation)

        See: Watch.py model docstring for detailed Pydantic architecture plan
        See: Tag.py model docstring for tag override explanation
        See: processors/restock_diff/processor.py:184-192 for current manual example

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

    @property
    def data_dir(self):
        """
        The base directory for this watch/tag data (property, computed from UUID).

        Common property for both Watch and Tag objects.
        Returns path like: /datastore/{uuid}/
        """
        return os.path.join(self._datastore_path, self['uuid']) if self._datastore_path else None

    def ensure_data_dir_exists(self):
        """
        Create the data directory if it doesn't exist.

        Common method for both Watch and Tag objects.
        """
        from loguru import logger
        if not os.path.isdir(self.data_dir):
            logger.debug(f"> Creating data dir {self.data_dir}")
            os.mkdir(self.data_dir)

    def get_global_setting(self, *path):
        """
        Get a setting from the global datastore configuration.

        Args:
            *path: Path to the setting (e.g., 'application', 'history_snapshot_max_length')

        Returns:
            The setting value, or None if not found

        Example:
            maxlen = self.get_global_setting('application', 'history_snapshot_max_length')
        """
        if not self._datastore:
            return None

        try:
            value = self._datastore['settings']
            for key in path:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return None

    def _get_commit_data(self):
        """
        Prepare data for commit (can be overridden by subclasses).

        Returns:
            dict: Data to serialize (filtered as needed by subclass)
        """
        import copy

        # Acquire datastore lock to prevent concurrent modifications during copy
        lock = self._datastore.lock if self._datastore and hasattr(self._datastore, 'lock') else None

        if lock:
            with lock:
                snapshot = dict(self)
        else:
            snapshot = dict(self)

        # Deep copy snapshot (slower, but done outside lock to minimize contention)
        # Subclasses can override to filter keys (e.g., Watch excludes processor_config_*)
        return {k: copy.deepcopy(v) for k, v in snapshot.items()}

    def _save_to_disk(self, data_dict, uuid):
        """
        Save data to disk (must be implemented by subclasses).

        Args:
            data_dict: Dictionary to save
            uuid: UUID for logging

