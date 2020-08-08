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


