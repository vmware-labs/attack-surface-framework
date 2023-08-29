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
from calendar import isleap, leapdays
from decimal import Decimal
from operator import attrgetter
from typing import Any, Iterator, List, Match, Optional, Union, SupportsFloat

###
# Common sets constants
OCCURRENCE_INDICATORS = frozenset(('?', '*', '+'))
BOOLEAN_VALUES = frozenset(('true', 'false', '1', '0'))
NUMERIC_INF_OR_NAN = frozenset(('INF', '-INF', 'NaN'))
INVALID_NUMERIC = frozenset(
    ('inf', '+inf', '-inf', 'nan', 'infinity', '+infinity', '-infinity')
)

###
# Data validation helpers

NORMALIZE_PATTERN = re.compile(r'[^\S\xa0]')
WHITESPACES_PATTERN = re.compile(r'[^\S\xa0]+')  # include ASCII 160 (non-breaking space)
NCNAME_PATTERN = re.compile(r'^[^\d\W][\w.\-\u00B7\u0300-\u036F\u203F\u2040]*$')
QNAME_PATTERN = re.compile(
    r'^(?:(?P<prefix>[^\d\W][\w\-.\u00B7\u0300-\u036F\u0387\u06DD\u06DE\u203F\u2040]*):)?'
    r'(?P<local>[^\d\W][\w\-.\u00B7\u0300-\u036F\u0387\u06DD\u06DE\u203F\u2040]*)$',
)
EQNAME_PATTERN = re.compile(
    r'^(?:Q{(?P<namespace>[^}]+)}|'
    r'(?P<prefix>[^\d\W][\w\-.\u00B7\u0300-\u036F\u0387\u06DD\u06DE\u203F\u2040]*):)?'
    r'(?P<local>[^\d\W][\w\-.\u00B7\u0300-\u036F\u0387\u06DD\u06DE\u203F\u2040]*)$',
)
WRONG_ESCAPE_PATTERN = re.compile(r'%(?![a-fA-F\d]{2})')
XML_NEWLINES_PATTERN = re.compile('\r\n|\r|\n')


def upper_camel_case(s: str) -> str:
    return re.sub(r'^\d+', '', re.sub(r'[\W_]', '', s.title()))


def collapse_white_spaces(s: str) -> str:
    return WHITESPACES_PATTERN.sub(' ', s).strip(' ')


def is_ncname(s: str) -> bool:
    return re.match(r'^[^\d\W][\w.\-\u00B7\u0300-\u036F\u203F\u2040]*$', s) is not None


def is_idrefs(value: Optional[str]) -> bool:
    return isinstance(value, str) and \
        all(NCNAME_PATTERN.match(x) is not None for x in value.split())


node_position = attrgetter('position')


###
# Date/Time helpers
MONTH_DAYS = [0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
MONTH_DAYS_LEAP = [0, 31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


def adjust_day(year: int, month: int, day: int) -> int:
    if month in (1, 3, 5, 7, 8, 10, 12):
        return day
    elif month in (4, 6, 9, 11):
        return min(day, 30)
    else:
        return min(day, 29) if isleap(year) else min(day, 28)


def days_from_common_era(year: int) -> int:
    """
    Returns the number of days from from 0001-01-01 to the provided year. For a
    common era year the days are counted until the last day of December, for a
    BCE year the days are counted down from the end to the 1st of January.
    """
    if year > 0:
        return year * 365 + year // 4 - year // 100 + year // 400
    elif year >= -1:
        return year * 366
    else:
        year = -year - 1
        return -(366 + year * 365 + year // 4 - year // 100 + year // 400)


DAYS_IN_4Y = days_from_common_era(4)
DAYS_IN_100Y = days_from_common_era(100)
DAYS_IN_400Y = days_from_common_era(400)


def months2days(year: int, month: int, months_delta: int) -> int:
    """
    Converts a delta of months to a delta of days, counting from the 1st day of the month,
    relative to the year and the month passed as arguments.

    :param year: the reference start year, a negative or zero value means a BCE year \
    (0 is 1 BCE, -1 is 2 BCE, -2 is 3 BCE, etc).
    :param month: the starting month (1-12).
    :param months_delta: the number of months, if negative count backwards.
    """
    if not months_delta:
        return 0

    total_months = month - 1 + months_delta
    target_year = year + total_months // 12
    target_month = total_months % 12 + 1

    if month <= 2:
        y_days = 365 * (target_year - year) + leapdays(year, target_year)
    else:
        y_days = 365 * (target_year - year) + leapdays(year + 1, target_year + 1)

    months_days = MONTH_DAYS_LEAP if isleap(target_year) else MONTH_DAYS
    if target_month >= month:
        m_days = sum(months_days[m] for m in range(month, target_month))
        return y_days + m_days if y_days >= 0 else y_days + m_days
    else:
        m_days = sum(months_days[m] for m in range(target_month, month))
        return y_days - m_days if y_days >= 0 else y_days - m_days


def round_number(value: Union[float, int, Decimal]) -> Union[float, int, Decimal]:
    if math.isnan(value) or math.isinf(value):
        return value

    number = Decimal(value)
    if number > 0:
        return type(value)(number.quantize(Decimal('1'), rounding='ROUND_HALF_UP'))
    else:
        return type(value)(number.quantize(Decimal('1'), rounding='ROUND_HALF_DOWN'))


def normalized_seconds(seconds: Decimal) -> str:
    # Decimal.normalize() does not remove exp every time: eg. Decimal('1E+1')
    return '{:.6f}'.format(seconds).rstrip('0').rstrip('.')


def is_xml_codepoint(cp: int) -> bool:
    return cp in (0x9, 0xA, 0xD) or \
        0x20 <= cp <= 0xD7FF or \
        0xE000 <= cp <= 0xFFFD or \
        0x10000 <= cp <= 0x10FFFF


def ordinal(n: int) -> str:
    if n in (11, 12, 13):
        return '%dth' % n

    least_significant_digit = n % 10
    if least_significant_digit == 1:
        return '%dst' % n
    elif least_significant_digit == 2:
        return '%dnd' % n
    elif least_significant_digit == 3:
        return '%drd' % n
    else:
        return '%dth' % n


def get_double(value: Union[SupportsFloat, str], xsd_version: str = '1.0') -> float:
    if isinstance(value, str):
        value = collapse_white_spaces(value)
        if value in NUMERIC_INF_OR_NAN or xsd_version != '1.0' and value == '+INF':
            if value == 'NaN':
                return math.nan  # for NaN use the predefined instance to keep identity
        elif value.lower() in INVALID_NUMERIC:
            raise ValueError(f'invalid value {value!r} for xs:double/xs:float')
    elif math.isnan(value):
        return math.nan

    return float(value)


def numeric_equal(op1: SupportsFloat, op2: SupportsFloat) -> bool:
    if op1 == op2:
        return True
    return math.isclose(op1, op2, rel_tol=1e-7, abs_tol=0.0)


def numeric_not_equal(op1: SupportsFloat, op2: SupportsFloat) -> bool:
    if op1 == op2:
        return False
    return not math.isclose(op1, op2, rel_tol=1e-7, abs_tol=0.0)


def equal(op1: Any, op2: Any) -> bool:
    if isinstance(op1, float) and math.isnan(op1):
        return isinstance(op2, float) and math.isnan(op2)
    return bool(op1 == op2)


def not_equal(op1: Any, op2: Any) -> bool:
    if isinstance(op1, float) and math.isnan(op1):
        return not isinstance(op2, float) or not math.isnan(op2)
    return bool(op1 != op2)


def match_wildcard(name: str, wildcard: str) -> bool:
    if wildcard == '*' or wildcard == '*:*':
        return True
    elif wildcard.startswith('*:'):
        if name.startswith('{'):
            return name.endswith(f'}}{wildcard[2:]}')
        else:
            return name == wildcard[2:]
    elif wildcard.startswith('{') and wildcard.endswith('}*') or wildcard.endswith(':*'):
        return name.startswith(wildcard[:-1])
    else:
        return False


def escape_json_string(s: str, escaped: bool = False) -> str:
    if escaped:
        s = s.replace('\\"', '"')
    else:
        s = s.replace('\\', '\\\\')

    s = s.replace('\"', '\\"').\
        replace('\b', r'\b').\
        replace('\r', r'\r').\
        replace('\n', r'\n').\
        replace('\t', r'\t').\
        replace('\f', r'\f').\
        replace('/', r'\/')
    return ''.join(
        rf'\u{ord(x):04X}' if 1 <= ord(x) <= 31 or 127 <= ord(x) <= 159 else x
        for x in s
    )


def unescape_json_string(s: str) -> str:

    def unicode_escape_callback(match: Match[str]) -> str:
        return chr(int(match.group(1).upper(), 16))

    s = s.replace('\\"', '\"').\
        replace(r'\b', '\b').\
        replace(r'\r', '\r').\
        replace(r'\n', '\n').\
        replace(r'\t', '\t').\
        replace(r'\f', '\f').\
        replace(r'\/', '/').\
        replace('\\\\', '\\')

    return re.sub(r'\\u([0-9A-Fa-f]{4})', unicode_escape_callback, s)


def iter_sequence(obj: Any) -> Iterator[Any]:
    if obj is None:
        return
    elif isinstance(obj, list):
        for item in obj:
            yield from iter_sequence(item)
    else:
        yield obj


def split_function_test(function_test: str) -> List[str]:
    if not function_test.startswith('function('):
        return []
    elif function_test == 'function(*)':
        return ['*']

    parts = function_test[9:].partition(') as ')
    if parts[0]:
        sequence_types = parts[0].split(', ')
        sequence_types.append(parts[2])
    else:
        sequence_types = [parts[2]]

    return sequence_types
