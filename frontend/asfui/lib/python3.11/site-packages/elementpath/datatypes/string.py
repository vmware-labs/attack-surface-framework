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
from typing import Any

from ..helpers import NORMALIZE_PATTERN, collapse_white_spaces
from .atomic_types import AnyAtomicType


class NormalizedString(str, AnyAtomicType):
    name = 'normalizedString'
    pattern = re.compile('^[^\t\r]*$')

    def __new__(cls, obj: Any) -> 'NormalizedString':
        try:
            return super().__new__(cls, NORMALIZE_PATTERN.sub(' ', obj))
        except TypeError:
            return super().__new__(cls, obj)


class XsdToken(NormalizedString):
    name = 'token'
    pattern = re.compile(r'^[\S\xa0]*(?: [\S\xa0]+)*$')

    def __new__(cls, value: Any) -> 'XsdToken':
        if not isinstance(value, str):
            value = str(value)
        else:
            value = collapse_white_spaces(value)

        match = cls.pattern.match(value)
        if match is None:
            raise ValueError('invalid value {!r} for xs:{}'.format(value, cls.name))
        return super(NormalizedString, cls).__new__(cls, value)


class Language(XsdToken):
    name = 'language'
    pattern = re.compile(r'^[a-zA-Z]{1,8}(-[a-zA-Z0-9]{1,8})*$')

    def __new__(cls, value: Any) -> 'Language':
        if isinstance(value, bool):
            value = 'true' if value else 'false'
        elif not isinstance(value, str):
            value = str(value)
        else:
            value = collapse_white_spaces(value)

        match = cls.pattern.match(value)
        if match is None:
            raise ValueError('invalid value {!r} for xs:{}'.format(value, cls.name))
        return super(NormalizedString, cls).__new__(cls, value)


class Name(XsdToken):
    name = 'Name'
    pattern = re.compile(r'^(?:[^\d\W]|:)[\w.\-:\u00B7\u0300-\u036F\u203F\u2040]*$')


class NCName(Name):
    name = 'NCName'
    pattern = re.compile(r'^[^\d\W][\w.\-\u00B7\u0300-\u036F\u203F\u2040]*$')


class Id(NCName):
    name = 'ID'


class Idref(NCName):
    name = 'IDREF'


class Entity(NCName):
    name = 'ENTITY'


class NMToken(XsdToken):
    name = 'NMTOKEN'
    pattern = re.compile(r'^[\w.\-:\u00B7\u0300-\u036F\u203F\u2040]+$')
