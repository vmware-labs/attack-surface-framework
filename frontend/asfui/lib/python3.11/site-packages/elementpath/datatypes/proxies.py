#
# Copyright (c), 2018-2020, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
import re
import math
from decimal import Decimal
from typing import Any, Union, SupportsFloat

from ..helpers import BOOLEAN_VALUES, collapse_white_spaces, get_double
from .atomic_types import AnyAtomicType
from .untyped import UntypedAtomic
from .numeric import Float10, Integer
from .datetime import AbstractDateTime, Duration

FloatArgType = Union[SupportsFloat, str, bytes]

####
# Type proxies for basic Python datatypes: a proxy class creates
# and validates its Python datatype and virtual registered types.


class BooleanProxy(AnyAtomicType):
    name = 'boolean'
    pattern = re.compile(r'^(?:true|false|1|0)$')

    def __new__(cls, value: object) -> bool:  # type: ignore[misc]
        if isinstance(value, bool):
            return value
        elif isinstance(value, (int, float, Decimal)):
            if math.isnan(value):
                return False
            return bool(value)
        elif isinstance(value, UntypedAtomic):
            value = value.value
        elif not isinstance(value, str):
            raise TypeError('invalid type {!r} for xs:{}'.format(type(value), cls.name))

        if value.strip() not in BOOLEAN_VALUES:
            raise ValueError('invalid value {!r} for xs:{}'.format(value, cls.name))
        return 't' in value or '1' in value

    @classmethod
    def __subclasshook__(cls, subclass: type) -> bool:
        return issubclass(subclass, bool)

    @classmethod
    def validate(cls, value: object) -> None:
        if isinstance(value, bool):
            return
        elif isinstance(value, str):
            if cls.pattern.match(value) is None:
                raise cls.invalid_value(value)
        else:
            raise cls.invalid_type(value)


class DecimalProxy(AnyAtomicType):
    name = 'decimal'
    pattern = re.compile(r'^[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)$')

    def __new__(cls, value: Any) -> Decimal:  # type: ignore[misc]
        if isinstance(value, (str, UntypedAtomic)):
            value = collapse_white_spaces(str(value)).replace(' ', '')
            if cls.pattern.match(value) is None:
                raise cls.invalid_value(value)
        elif isinstance(value, (float, Float10, Decimal)):
            if math.isinf(value) or math.isnan(value):
                raise cls.invalid_value(value)
        try:
            return Decimal(value)
        except (ValueError, ArithmeticError):
            msg = 'invalid value {!r} for xs:{}'
            raise ArithmeticError(msg.format(value, cls.name)) from None

    @classmethod
    def __subclasshook__(cls, subclass: type) -> bool:
        return issubclass(subclass, (int, Decimal, Integer)) and not issubclass(subclass, bool)

    @classmethod
    def validate(cls, value: object) -> None:
        if isinstance(value, Decimal):
            if math.isnan(value) or math.isinf(value):
                raise cls.invalid_value(value)
        elif isinstance(value, (int, Integer)) and not isinstance(value, bool):
            return
        elif isinstance(value, str):
            if cls.pattern.match(value) is None:
                raise cls.invalid_value(value)
        else:
            raise cls.invalid_type(value)


class DoubleProxy10(AnyAtomicType):
    name = 'double'
    xsd_version = '1.0'
    pattern = re.compile(
        r'^(?:[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[Ee][+-]?[0-9]+)?|[+-]?INF|NaN)$'
    )

    def __new__(cls, value: Union[SupportsFloat, str]) -> float:  # type: ignore[misc]
        return get_double(value, cls.xsd_version)

    @classmethod
    def __subclasshook__(cls, subclass: type) -> bool:
        return issubclass(subclass, float) and not issubclass(subclass, Float10)

    @classmethod
    def validate(cls, value: object) -> None:
        if isinstance(value, float) and not isinstance(value, Float10):
            return
        elif isinstance(value, str):
            if cls.pattern.match(value) is None:
                raise cls.invalid_value(value)
        else:
            raise cls.invalid_type(value)


class DoubleProxy(DoubleProxy10):
    name = 'double'
    xsd_version = '1.1'


class StringProxy(AnyAtomicType):
    name = 'string'

    def __new__(cls, *args: object, **kwargs: object) -> str:  # type: ignore[misc]
        return str(*args, **kwargs)

    @classmethod
    def __subclasshook__(cls, subclass: type) -> bool:
        return issubclass(subclass, str)

    @classmethod
    def validate(cls, value: object) -> None:
        if not isinstance(value, str):
            raise cls.invalid_type(value)


####
# Type proxies for multiple type-checking in XPath expressions
class NumericTypeMeta(type):
    """Metaclass for checking numeric classes and instances."""

    def __instancecheck__(cls, instance: object) -> bool:
        return isinstance(instance, (int, float, Decimal)) and not isinstance(instance, bool)

    def __subclasscheck__(cls, subclass: type) -> bool:
        if issubclass(subclass, bool):
            return False
        return issubclass(subclass, int) or issubclass(subclass, float) \
            or issubclass(subclass, Decimal)


class NumericProxy(metaclass=NumericTypeMeta):
    """Proxy for xs:numeric related types. Builds xs:float instances."""

    def __new__(cls, *args: FloatArgType, **kwargs: FloatArgType) -> float:  # type: ignore[misc]
        return float(*args, **kwargs)


class ArithmeticTypeMeta(type):
    """Metaclass for checking numeric, datetime and duration classes/instances."""

    def __instancecheck__(cls, instance: object) -> bool:
        return isinstance(
            instance, (int, float, Decimal, AbstractDateTime, Duration, UntypedAtomic)
        ) and not isinstance(instance, bool)

    def __subclasscheck__(cls, subclass: type) -> bool:
        if issubclass(subclass, bool):
            return False
        return issubclass(subclass, int) or issubclass(subclass, float) or \
            issubclass(subclass, Decimal) or issubclass(subclass, Duration) \
            or issubclass(subclass, AbstractDateTime) or issubclass(subclass, UntypedAtomic)


class ArithmeticProxy(metaclass=ArithmeticTypeMeta):
    """Proxy for arithmetic related types. Builds xs:float instances."""

    def __new__(cls, *args: FloatArgType, **kwargs: FloatArgType) -> float:  # type: ignore[misc]
        return float(*args, **kwargs)
