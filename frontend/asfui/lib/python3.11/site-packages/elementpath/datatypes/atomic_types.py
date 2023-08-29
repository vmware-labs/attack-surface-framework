#
# Copyright (c), 2018-2020, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
from abc import ABCMeta
from typing import Any, Dict, Optional, Pattern, Tuple, Type
import re

XSD_NAMESPACE = "http://www.w3.org/2001/XMLSchema"

###
# Classes for XSD built-in atomic types. All defined classes use a
# metaclass that adds some common methods and registers each class
# into a dictionary. Some classes of XSD primitive types are defined
# as proxies of basic Python datatypes.

xsd10_atomic_types: Dict[Optional[str], 'AtomicTypeMeta'] = {}
"""Dictionary of builtin XSD 1.0 atomic types."""

xsd11_atomic_types: Dict[Optional[str], 'AtomicTypeMeta'] = {}
"""Dictionary of builtin XSD 1.1 atomic types."""


class AtomicTypeMeta(ABCMeta):
    """
    Metaclass for creating XSD atomic types. The created classes
    are decorated with missing attributes and methods. When a name
    attribute is provided the class is registered into a global map
    of XSD atomic types and also the expanded name is added.
    """
    xsd_version: str
    pattern: Pattern[str]
    name: Optional[str] = None

    def __new__(mcs, class_name: str, bases: Tuple[Type[Any], ...], dict_: Dict[str, Any]) \
            -> 'AtomicTypeMeta':
        try:
            name = dict_['name']
        except KeyError:
            name = dict_['name'] = None  # do not inherit name

        if name is not None and not isinstance(name, str):
            raise TypeError("attribute 'name' must be a string or None")

        dict_['is_valid'] = classmethod(mcs.is_valid)
        dict_['invalid_type'] = classmethod(mcs.invalid_type)
        dict_['invalid_value'] = classmethod(mcs.invalid_value)
        cls = super(AtomicTypeMeta, mcs).__new__(mcs, class_name, bases, dict_)

        # Add missing attributes and methods
        if not hasattr(cls, 'xsd_version'):
            cls.xsd_version = '1.0'
        if not hasattr(cls, 'pattern'):
            cls.pattern = re.compile(r'^$')

        # Register class with a name
        if name:
            expanded_name = '{%s}%s' % (XSD_NAMESPACE, name)
            if cls.xsd_version == '1.0':
                xsd10_atomic_types[name] = xsd10_atomic_types[expanded_name] = cls
            else:
                xsd11_atomic_types[name] = xsd11_atomic_types[expanded_name] = cls

        return cls

    def validate(cls, value: object) -> None:
        if isinstance(value, cls):
            return
        elif isinstance(value, str):
            if cls.pattern.match(value) is None:
                raise cls.invalid_value(value)
        else:
            raise cls.invalid_type(value)

    def is_valid(cls, value: object) -> bool:
        try:
            cls.validate(value)
        except (TypeError, ValueError):
            return False
        else:
            return True

    def invalid_type(cls, value: object) -> TypeError:
        if cls.name:
            return TypeError('invalid type {!r} for xs:{}'.format(type(value), cls.name))
        return TypeError('invalid type {!r} for {!r}'.format(type(value), cls))

    def invalid_value(cls, value: object) -> ValueError:
        if cls.name:
            return ValueError('invalid value {!r} for xs:{}'.format(value, cls.name))
        return ValueError('invalid value {!r} for {!r}'.format(value, cls))


class AnyAtomicType(metaclass=AtomicTypeMeta):
    name = 'anyAtomicType'
