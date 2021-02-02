import functools
from flask import request, abort
from loguru import logger

@functools.cache
def build_merged_spec_dict():
    """
    Load the base OpenAPI spec and merge in any per-processor api.yaml extensions.

    Each processor can provide an api.yaml file alongside its __init__.py that defines
    additional schemas (e.g., processor_config_restock_diff). These are merged into
    WatchBase.properties so the spec accurately reflects what the API accepts.

    Plugin processors (via pluggy) are also supported - they just need an api.yaml
    next to their processor module.

    Returns the merged dict (cached - do not mutate the returned value).
    """
    import os
    import yaml

    spec_path = os.path.join(os.path.dirname(__file__), '../../docs/api-spec.yaml')
    if not os.path.exists(spec_path):
        spec_path = os.path.join(os.path.dirname(__file__), '../docs/api-spec.yaml')

    with open(spec_path, 'r', encoding='utf-8') as f:
        spec_dict = yaml.safe_load(f)

    try:
        from changedetectionio.processors import find_processors, get_parent_module
        for module, proc_name in find_processors():
            parent = get_parent_module(module)
            if not parent or not hasattr(parent, '__file__'):
                continue
            api_yaml_path = os.path.join(os.path.dirname(parent.__file__), 'api.yaml')
            if not os.path.exists(api_yaml_path):
                continue
            with open(api_yaml_path, 'r', encoding='utf-8') as f:
                proc_spec = yaml.safe_load(f)
            # Merge schemas
            proc_schemas = proc_spec.get('components', {}).get('schemas', {})
            spec_dict['components']['schemas'].update(proc_schemas)
            # Inject processor_config_{name} into WatchBase if the schema is defined
            schema_key = f'processor_config_{proc_name}'
            if schema_key in proc_schemas:
                spec_dict['components']['schemas']['WatchBase']['properties'][schema_key] = {
                    '$ref': f'#/components/schemas/{schema_key}'
                }
            # Append x-code-samples from processor paths into existing path operations
            for path, path_item in proc_spec.get('paths', {}).items():
                if path not in spec_dict.get('paths', {}):
                    continue
                for method, operation in path_item.items():
                    if method not in spec_dict['paths'][path]:
                        continue
                    if 'x-code-samples' in operation:
                        existing = spec_dict['paths'][path][method].get('x-code-samples', [])
                        spec_dict['paths'][path][method]['x-code-samples'] = existing + operation['x-code-samples']
    except Exception as e:
        logger.warning(f"Failed to merge processor API specs: {e}")

    return spec_dict


@functools.cache
def get_openapi_spec():
    """Lazy load OpenAPI spec and dependencies only when validation is needed."""
    from openapi_core import OpenAPI  # Lazy import - saves ~10.7 MB on startup
    return OpenAPI.from_dict(build_merged_spec_dict())

@functools.cache
def get_openapi_schema_dict():
    """
    Get the raw OpenAPI spec dictionary for schema access.

    Used by Import endpoint to validate and convert query parameters.
    Returns the merged YAML dict (not the OpenAPI object).
    """
    return build_merged_spec_dict()

@functools.cache
def _resolve_schema_properties(schema_name):
    """
    Generic helper to resolve schema properties, including allOf inheritance.

    Args:
        schema_name: Name of the schema (e.g., 'WatchBase', 'Watch', 'Tag')

    Returns:
        dict: All properties including inherited ones from $ref schemas
    """
    spec_dict = get_openapi_schema_dict()
    schema = spec_dict['components']['schemas'].get(schema_name, {})

    properties = {}

    # Handle allOf (schema inheritance)
    if 'allOf' in schema:
        for item in schema['allOf']:
            # Resolve $ref to parent schema
            if '$ref' in item:
                ref_path = item['$ref'].split('/')[-1]
                ref_schema = spec_dict['components']['schemas'].get(ref_path, {})
                properties.update(ref_schema.get('properties', {}))
            # Add schema-specific properties
            if 'properties' in item:
                properties.update(item['properties'])
    else:
        # Direct properties (no inheritance)
        properties = schema.get('properties', {})

    return properties


@functools.cache
def get_watch_schema_properties():
    """
    Extract watch schema properties from OpenAPI spec for Import endpoint.

    Returns WatchBase properties (all writable Watch fields).
    """
    return _resolve_schema_properties('WatchBase')

