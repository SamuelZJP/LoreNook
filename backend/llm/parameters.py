from copy import deepcopy


def merge_parameters(defaults: dict, explicit: dict) -> dict:
    """Fill absent mapping keys; explicit scalar/null/list values replace defaults."""
    merged = deepcopy(defaults)
    for key, value in explicit.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge_parameters(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged
