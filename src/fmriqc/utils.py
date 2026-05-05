"""Shared utility functions for fmriqc.

This module contains common utility functions used across multiple modules
to avoid code duplication.
"""

from typing import Any, Dict, Tuple

import numpy as np


def split_dict_arrays(data: Dict[str, Any]) -> Tuple[Dict[str, np.ndarray], Dict[str, Any]]:
    """Split a dictionary into arrays and scalars.

    Separates numpy arrays from scalar values in a dictionary, useful for
    serialization and storage where arrays and scalars need different handling.

    Parameters
    ----------
    data : Dict[str, Any]
        Dictionary potentially containing both arrays and scalar values

    Returns
    -------
    Tuple[Dict[str, np.ndarray], Dict[str, Any]]
        Two dictionaries: first containing only arrays, second containing scalars

    Examples
    --------
    >>> data = {'arr': np.array([1, 2, 3]), 'val': 42, 'name': 'test'}
    >>> arrays, scalars = split_dict_arrays(data)
    >>> 'arr' in arrays
    True
    >>> 'val' in scalars
    True
    """
    arrays: Dict[str, np.ndarray] = {}
    scalars: Dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, np.ndarray):
            arrays[key] = value
        else:
            scalars[key] = value
    return arrays, scalars


def coerce_scalar(value: Any) -> Any:
    """Convert numpy scalar types to Python native types.

    Handles conversion of numpy generic types (np.float64, np.int32, etc.)
    to Python native types (float, int, etc.) for JSON serialization and
    general compatibility.

    Parameters
    ----------
    value : Any
        Value to convert, typically a numpy scalar or Python native type

    Returns
    -------
    Any
        Python native type if input was numpy generic, otherwise unchanged

    Examples
    --------
    >>> coerce_scalar(np.float64(3.14))
    3.14
    >>> coerce_scalar(42)
    42
    """
    if isinstance(value, np.generic):
        return value.item()
    return value
