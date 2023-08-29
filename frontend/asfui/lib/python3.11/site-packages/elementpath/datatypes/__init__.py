#
# Copyright (c), 2018-2020, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
"""
XSD atomic datatypes subpackage. Includes a class for UntypedAtomic data and
classes for other XSD built-in types. This subpackage raises only built-in
exceptions in order to be reusable in other packages.
"""
from decimal import Decimal
from typing import Dict, Optional, Union

from ..namespaces import XSD_NAMESPACE
from ..protocols import XsdTypeProtocol

from .atomic_types import xsd10_atomic_types, xsd11_atomic_types, \
    AtomicTypeMeta, AnyAtomicType
from .untyped import UntypedAtomic
from .qname import AbstractQName, QName, Notation
from .numeric import Float10, Float, Integer, Int, NegativeInteger, \
    PositiveInteger, NonNegativeInteger, NonPositiveInteger, Long, \
    Short, Byte, UnsignedByte, UnsignedInt, UnsignedLong, UnsignedShort
from .string import NormalizedString, XsdToken, Name, NCName, NMToken, Id, \
    Idref, Language, Entity
from .uri import AnyURI
from .binary import AbstractBinary, Base64Binary, HexBinary
from .datetime import AbstractDateTime, DateTime10, DateTime, DateTimeStamp, \
    Date10, Date, GregorianDay, GregorianMonth, GregorianYear, GregorianYear10, \
    GregorianMonthDay, GregorianYearMonth, GregorianYearMonth10, Time, Timezone, \
    Duration, DayTimeDuration, YearMonthDuration, OrderedDateTime
from .proxies import BooleanProxy, DecimalProxy, DoubleProxy10, DoubleProxy, \
    StringProxy, NumericProxy, ArithmeticProxy

xsd11_atomic_types.update(
    (k, v) for k, v in xsd10_atomic_types.items() if k not in xsd11_atomic_types
)

DatetimeValueType = AbstractDateTime  # keep until v5.0 for backward compatibility
AtomicValueType = Union[str, int, float, Decimal, bool, AnyAtomicType]


ATOMIC_VALUES: Dict[Optional[str], AtomicValueType] = {
    f'{{{XSD_NAMESPACE}}}untypedAtomic': UntypedAtomic('1'),
    f'{{{XSD_NAMESPACE}}}anyType': UntypedAtomic('1'),
    f'{{{XSD_NAMESPACE}}}anySimpleType': UntypedAtomic('1'),
    f'{{{XSD_NAMESPACE}}}anyAtomicType': UntypedAtomic('1'),
    f'{{{XSD_NAMESPACE}}}boolean': True,
    f'{{{XSD_NAMESPACE}}}decimal': Decimal('1.0'),
    f'{{{XSD_NAMESPACE}}}double': 1.0,
    f'{{{XSD_NAMESPACE}}}float': Float10(1.0),
    f'{{{XSD_NAMESPACE}}}string': '  alpha\t',
    f'{{{XSD_NAMESPACE}}}date': Date.fromstring('2000-01-01'),
    f'{{{XSD_NAMESPACE}}}dateTime': DateTime.fromstring('2000-01-01T12:00:00'),
    f'{{{XSD_NAMESPACE}}}gDay': GregorianDay.fromstring('---31'),
    f'{{{XSD_NAMESPACE}}}gMonth': GregorianMonth.fromstring('--12'),
    f'{{{XSD_NAMESPACE}}}gMonthDay': GregorianMonthDay.fromstring('--12-01'),
    f'{{{XSD_NAMESPACE}}}gYear': GregorianYear.fromstring('1999'),
    f'{{{XSD_NAMESPACE}}}gYearMonth': GregorianYearMonth.fromstring('1999-09'),
    f'{{{XSD_NAMESPACE}}}time': Time.fromstring('09:26:54'),
    f'{{{XSD_NAMESPACE}}}duration': Duration.fromstring('P1MT1S'),
    f'{{{XSD_NAMESPACE}}}dayTimeDuration': DayTimeDuration.fromstring('P1DT1S'),
    f'{{{XSD_NAMESPACE}}}yearMonthDuration': YearMonthDuration.fromstring('P1Y1M'),
    f'{{{XSD_NAMESPACE}}}QName': QName("http://www.w3.org/2001/XMLSchema", 'xs:element'),
    f'{{{XSD_NAMESPACE}}}anyURI': AnyURI('https://example.com'),
    f'{{{XSD_NAMESPACE}}}normalizedString': NormalizedString(' alpha  '),
    f'{{{XSD_NAMESPACE}}}token': XsdToken('a token'),
    f'{{{XSD_NAMESPACE}}}language': Language('en-US'),
    f'{{{XSD_NAMESPACE}}}Name': Name('_a.name::'),
    f'{{{XSD_NAMESPACE}}}NCName': NCName('nc-name'),
    f'{{{XSD_NAMESPACE}}}ID': Id('id1'),
    f'{{{XSD_NAMESPACE}}}IDREF': Idref('id_ref1'),
    f'{{{XSD_NAMESPACE}}}ENTITY': Entity('entity1'),
    f'{{{XSD_NAMESPACE}}}NMTOKEN': NMToken('a_token'),
    f'{{{XSD_NAMESPACE}}}base64Binary': Base64Binary(b'YWxwaGE='),
    f'{{{XSD_NAMESPACE}}}hexBinary': HexBinary(b'31'),
    f'{{{XSD_NAMESPACE}}}dateTimeStamp': DateTimeStamp.fromstring('2000-01-01T12:00:00+01:00'),
    f'{{{XSD_NAMESPACE}}}integer': Integer(1),
    f'{{{XSD_NAMESPACE}}}long': Long(1),
    f'{{{XSD_NAMESPACE}}}int': Int(1),
    f'{{{XSD_NAMESPACE}}}short': Short(1),
    f'{{{XSD_NAMESPACE}}}byte': Byte(1),
    f'{{{XSD_NAMESPACE}}}positiveInteger': PositiveInteger(1),
    f'{{{XSD_NAMESPACE}}}negativeInteger': NegativeInteger(-1),
    f'{{{XSD_NAMESPACE}}}nonPositiveInteger': NonPositiveInteger(0),
    f'{{{XSD_NAMESPACE}}}nonNegativeInteger': NonNegativeInteger(0),
    f'{{{XSD_NAMESPACE}}}unsignedLong': UnsignedLong(1),
    f'{{{XSD_NAMESPACE}}}unsignedInt': UnsignedInt(1),
    f'{{{XSD_NAMESPACE}}}unsignedShort': UnsignedShort(1),
    f'{{{XSD_NAMESPACE}}}unsignedByte': UnsignedByte(1),
}


def get_atomic_value(xsd_type: Optional[XsdTypeProtocol]) -> AtomicValueType:
    """Gets an atomic value for an XSD type instance. Used for schema contexts."""
    if xsd_type is None:
        return UntypedAtomic('1')

    try:
        return ATOMIC_VALUES[xsd_type.name]
    except KeyError:
        try:
            return ATOMIC_VALUES[xsd_type.root_type.name]
        except KeyError:
            return UntypedAtomic('1')


__all__ = ['xsd10_atomic_types', 'xsd11_atomic_types', 'get_atomic_value',
           'AtomicTypeMeta', 'AnyAtomicType', 'NumericProxy', 'ArithmeticProxy',
           'AbstractDateTime', 'DateTime10', 'DateTime', 'DateTimeStamp', 'Date10',
           'Date', 'Time', 'GregorianDay', 'GregorianMonth', 'GregorianMonthDay',
           'GregorianYear10', 'GregorianYear', 'GregorianYearMonth10', 'GregorianYearMonth',
           'Timezone', 'Duration', 'YearMonthDuration', 'DayTimeDuration', 'StringProxy',
           'NormalizedString', 'XsdToken', 'Language', 'Name', 'NCName', 'Id', 'Idref',
           'Entity', 'NMToken', 'Base64Binary', 'HexBinary', 'Float10', 'Float',
           'Integer', 'NonPositiveInteger', 'NegativeInteger', 'Long', 'Int', 'Short',
           'Byte', 'NonNegativeInteger', 'PositiveInteger', 'UnsignedLong', 'UnsignedInt',
           'UnsignedShort', 'UnsignedByte', 'AnyURI', 'Notation', 'QName', 'BooleanProxy',
           'DecimalProxy', 'DoubleProxy10', 'DoubleProxy', 'UntypedAtomic', 'AbstractBinary',
           'AtomicValueType', 'DatetimeValueType', 'OrderedDateTime', 'AbstractQName']
