#
# Copyright (c), 2018-2020, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
from decimal import Decimal
from urllib.parse import urlparse
from typing import Union

from ..helpers import collapse_white_spaces, WRONG_ESCAPE_PATTERN
from .atomic_types import AnyAtomicType
from .untyped import UntypedAtomic
from .numeric import Integer


class AnyURI(AnyAtomicType):
    """
    Class for xs:anyURI data.

    :param value: a string or an untyped atomic instance.
    """
    value: str
    name = 'anyURI'

    def __init__(self, value: Union[str, bytes, UntypedAtomic, 'AnyURI']) -> None:
        if isinstance(value, str):
            self.value = collapse_white_spaces(value)
        elif isinstance(value, bytes):
            self.value = collapse_white_spaces(value.decode('utf-8'))
        elif isinstance(value, self.__class__):
            self.value = value.value
        elif isinstance(value, UntypedAtomic):
            self.value = collapse_white_spaces(value.value)
        else:
            raise TypeError('the argument has an invalid type %r' % type(value))

        self.validate(self.value)

    def __repr__(self) -> str:
        return '%s(%r)' % (self.__class__.__name__, self.value)

    def __str__(self) -> str:
        return self.value

    def __bool__(self) -> bool:
        return bool(self.value)  # For effective boolean value

    def __hash__(self) -> int:
        return hash(self.value)

    def __contains__(self, item: str) -> bool:
        return item in self.value

    def __eq__(self, other: object) -> bool:
        if isinstance(other, (AnyURI, UntypedAtomic)):
            return self.value == other.value
        elif isinstance(other, (bool, float, Decimal, Integer)):
            raise TypeError("cannot compare {} with xs:{}".format(type(other), self.name))
        return self.value == other

    def __ne__(self, other: object) -> bool:
        if isinstance(other, (AnyURI, UntypedAtomic)):
            return self.value != other.value
        elif isinstance(other, (bool, float, Decimal, Integer)):
            raise TypeError("cannot compare {} with xs:{}".format(type(other), self.name))
        return self.value != other

    def __lt__(self, other: Union[str, 'AnyURI', UntypedAtomic]) -> bool:
        if isinstance(other, (AnyURI, UntypedAtomic)):
            return self.value < other.value
        return self.value < other

    def __le__(self, other: Union[str, 'AnyURI', UntypedAtomic]) -> bool:
        if isinstance(other, (AnyURI, UntypedAtomic)):
            return self.value <= other.value
        return self.value <= other

    def __gt__(self, other: Union[str, 'AnyURI', UntypedAtomic]) -> bool:
        if isinstance(other, (AnyURI, UntypedAtomic)):
            return self.value > other.value
        return self.value > other

    def __ge__(self, other: Union[str, 'AnyURI', UntypedAtomic]) -> bool:
        if isinstance(other, (AnyURI, UntypedAtomic)):
            return self.value >= other.value
        return self.value >= other

    @classmethod
    def validate(cls, value: object) -> None:
        if isinstance(value, cls):
            return
        elif isinstance(value, bytes):
            value = value.decode()
        elif not isinstance(value, str):
            raise cls.invalid_type(value)

        try:
            url_parts = urlparse(value)
            _ = url_parts.port  # check invalid port!
        except ValueError as err:
            msg = 'invalid value {!r} for xs:{} ({})'
            raise ValueError(msg.format(value, cls.name, str(err))) from None
        else:
            if url_parts.path.startswith(':'):
                raise cls.invalid_value(value)
            elif value.count('#') > 1:
                msg = 'invalid value {!r} for xs:{} (too many # characters)'
                raise ValueError(msg.format(value, cls.name))
            elif WRONG_ESCAPE_PATTERN.search(value) is not None:
                msg = 'invalid value {!r} for xs:{} (wrong escaping)'
                raise ValueError(msg.format(value, cls.name))
