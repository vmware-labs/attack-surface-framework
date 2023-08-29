#
# Copyright (c), 2022, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
import re
from itertools import zip_longest
from typing import TYPE_CHECKING, cast, Any, Optional

from .exceptions import ElementPathKeyError, xpath_error
from .helpers import OCCURRENCE_INDICATORS, EQNAME_PATTERN, WHITESPACES_PATTERN
from .namespaces import XSD_NAMESPACE, XSD_ERROR, XSD_ANY_SIMPLE_TYPE, XSD_NUMERIC, \
    get_expanded_name
from .datatypes import xsd10_atomic_types, xsd11_atomic_types, AnyAtomicType, \
    QName, NumericProxy
from .xpath_nodes import XPathNode, DocumentNode, ElementNode, AttributeNode
from . import xpath_tokens

if TYPE_CHECKING:
    from .xpath1 import XPath1Parser

XSD_EXTENDED_PREFIX = f'{{{XSD_NAMESPACE}}}'

COMMON_SEQUENCE_TYPES = {
    'xs:anyType', 'xs:anySimpleType', 'xs:anyAtomicType',
    'xs:boolean', 'xs:decimal', 'xs:double', 'xs:float', 'xs:string',
    'xs:date', 'xs:dateTime', 'xs:gDay', 'xs:gMonth', 'xs:gMonthDay',
    'xs:gYear', 'xs:gYearMonth', 'xs:time', 'xs:duration', 'xs:dayTimeDuration',
    'xs:yearMonthDuration', 'xs:QName', 'xs:anyURI', 'xs:normalizedString',
    'xs:token', 'xs:language', 'xs:Name', 'xs:NCName', 'xs:ID', 'xs:IDREF',
    'xs:ENTITY', 'xs:NMTOKEN', 'xs:base64Binary', 'xs:hexBinary',
    'xs:integer', 'xs:long', 'xs:int', 'xs:short', 'xs:byte',
    'xs:positiveInteger', 'xs:negativeInteger', 'xs:numeric',
    'xs:nonPositiveInteger', 'xs:nonNegativeInteger', 'xs:unsignedLong',
    'xs:unsignedInt', 'xs:unsignedShort', 'xs:unsignedByte',
    'xs:untyped', 'xs:untypedAtomic', 'attribute()', 'attribute(*)',
    'element()', 'element(*)', 'text()', 'document-node()', 'comment()',
    'processing-instruction()', 'item()', 'node()', 'numeric'
}

###
# Sequence type checking
SEQUENCE_TYPE_PATTERN = re.compile(r'\s?([()?*+,])\s?')


def normalize_sequence_type(sequence_type: str) -> str:
    sequence_type = WHITESPACES_PATTERN.sub(' ', sequence_type).strip()
    sequence_type = SEQUENCE_TYPE_PATTERN.sub(r'\1', sequence_type)
    return sequence_type.replace(',', ', ').replace(')as', ') as')


def is_sequence_type_restriction(st1: str, st2: str) -> bool:
    """Returns `True` if st2 is a restriction of st1."""
    st1, st2 = normalize_sequence_type(st1), normalize_sequence_type(st2)

    if st2 in ('empty-sequence()', 'none') and \
            (st1 in ('empty-sequence()', 'none') or st1.endswith(('?', '*'))):
        return True

    # check occurrences
    if st1[-1] not in '?+*':
        if st2[-1] in '+*':
            return False
        elif st2[-1] == '?':
            st2 = st2[:-1]

    elif st1[-1] == '+':
        st1 = st1[:-1]
        if st2[-1] in '?*':
            return False
        elif st2[-1] == '+':
            st2 = st2[:-1]

    elif st1[-1] == '*':
        st1 = st1[:-1]
        if st2[-1] in '?+':
            return False
        elif st2[-1] == '*':
            st2 = st2[:-1]

    else:
        st1 = st1[:-1]
        if st2[-1] in '+*':
            return False
        elif st2[-1] == '?':
            st2 = st2[:-1]

    if st1 == st2:
        return True
    elif st1 == 'item()':
        return True
    elif st2 == 'item()':
        return False
    elif st1 == 'node()':
        return st2.startswith(('element(', 'attribute(', 'comment(', 'text(',
                               'processing-instruction(', 'document(', 'namespace('))
    elif st2 == 'node()':
        return False
    elif st1 == 'xs:anyAtomicType':
        try:
            return issubclass(xsd11_atomic_types[st2[3:]], AnyAtomicType)
        except KeyError:
            return False
    elif st1.startswith('xs:'):
        if st2 == 'xs:anyAtomicType':
            return True

        try:
            return issubclass(xsd11_atomic_types[st2[3:]], xsd11_atomic_types[st1[3:]])
        except KeyError:
            return False
    elif not st1.startswith('function('):
        return False

    if st1 == 'function(*)':
        return st2.startswith('function(')

    parts1 = st1[9:].partition(') as ')
    parts2 = st2[9:].partition(') as ')

    for st1, st2 in zip_longest(parts1[0].split(', '), parts2[0].split(', ')):
        if st1 is None or st2 is None:
            return False
        if not is_sequence_type_restriction(st2, st1):
            return False
    else:
        if not is_sequence_type_restriction(parts1[2], parts2[2]):
            return False
        return True


def is_instance(obj: Any, type_qname: str, parser: Optional['XPath1Parser'] = None) -> bool:
    """Checks an instance against an XSD type."""
    xsd_version = getattr(parser, 'xsd_version', '1.0')
    if not type_qname.startswith('{'):
        if parser is not None:
            type_qname = get_expanded_name(type_qname, parser.namespaces)
        elif type_qname.startswith('xs:'):
            type_qname = type_qname.replace('xs:', XSD_EXTENDED_PREFIX, 1)

    if type_qname.startswith(XSD_EXTENDED_PREFIX):
        try:
            if xsd_version == '1.1':
                return isinstance(obj, xsd11_atomic_types[type_qname])
            return isinstance(obj, xsd10_atomic_types[type_qname])
        except KeyError:
            pass

        if type_qname == XSD_ERROR:
            return obj is None or obj == []
        elif type_qname == XSD_ANY_SIMPLE_TYPE:
            return isinstance(obj, AnyAtomicType) or \
                isinstance(obj, list) and \
                all(isinstance(x, AnyAtomicType) for x in obj)
        elif type_qname in ('numeric', XSD_NUMERIC):
            return isinstance(obj, NumericProxy)

    if parser is not None and parser.schema is not None:
        try:
            return parser.schema.is_instance(obj, type_qname)
        except KeyError:
            pass

    raise ElementPathKeyError("unknown type %r" % type_qname)


def is_sequence_type(value: Any, parser: Optional['XPath1Parser'] = None) -> bool:
    """Checks if a string is a sequence type specification."""

    def is_st(st: str) -> bool:
        if not st:
            return False
        elif st == 'empty-sequence()' or st == 'none':
            return True
        elif st[-1] in OCCURRENCE_INDICATORS:
            st = st[:-1]

        if st in COMMON_SEQUENCE_TYPES:
            return True

        elif st.startswith(('map(', 'array(')):
            if parser and parser.version < '3.1' or not st.endswith(')'):
                return False

            if st in ('map(*)', 'array(*)'):
                return True

            if st.startswith('map('):
                key_type, _, value_type = st[4:-1].partition(', ')
                return key_type.startswith('xs:') and \
                    not key_type.endswith(('+', '*')) and \
                    is_st(key_type) and \
                    is_st(key_type)
            else:
                return is_st(st[6:-1])

        elif st.startswith('element(') and st.endswith(')'):
            if ',' not in st:
                return EQNAME_PATTERN.match(st[8:-1]) is not None

            try:
                arg1, arg2 = st[8:-1].split(', ')
            except ValueError:
                return False
            else:
                return (arg1 == '*' or EQNAME_PATTERN.match(arg1) is not None) \
                       and EQNAME_PATTERN.match(arg2) is not None

        elif st.startswith('document-node(') and st.endswith(')'):
            if not st.startswith('document-node(element('):
                return False
            return is_st(st[14:-1])

        elif st.startswith('function('):
            if parser and parser.version < '3.0':
                return False
            elif st == 'function(*)':
                return True
            elif ' as ' in st:
                pass
            elif not st.endswith(')'):
                return False
            else:
                return is_st(st[9:-1])

            st, return_type = st.rsplit(' as ', 1)
            if not is_st(return_type):
                return False
            elif st == 'function()':
                return True

            st = st[9:-1]
            if st.endswith(', ...'):
                st = st[:-5]

            if 'function(' not in st:
                return all(is_st(x) for x in st.split(', '))
            elif st.startswith('function(*)') and 'function(' not in st[11:]:
                return all(is_st(x) for x in st.split(', '))

            # Cover only if function() spec is the last argument
            k = st.index('function(')
            if not is_st(st[k:]):
                return False
            return all(is_st(x) for x in st[:k].split(', ') if x)

        elif QName.pattern.match(st) is None:
            return False

        if parser is None:
            return False

        try:
            is_instance(None, st, parser)
        except (KeyError, ValueError):
            return False
        else:
            return True

    if not isinstance(value, str):
        return False
    return is_st(normalize_sequence_type(value))


def match_sequence_type(value: Any,
                        sequence_type: str,
                        parser: Optional['XPath1Parser'] = None,
                        strict: bool = True) -> bool:
    """
    Checks a value instance against a sequence type.

    :param value: the instance to check.
    :param sequence_type: a string containing the sequence type spec.
    :param parser: an optional parser instance for type checking.
    :param strict: if `False` match xs:anyURI with strings.
    """
    def match_st(v: Any, st: str, occurrence: Optional[str] = None) -> bool:
        if st[-1] in OCCURRENCE_INDICATORS and ') as ' not in st:
            return match_st(v, st[:-1], st[-1])
        elif v is None or isinstance(v, list) and v == []:
            return st in ('empty-sequence()', 'none') or occurrence in ('?', '*')
        elif st in ('empty-sequence()', 'none'):
            return False
        elif isinstance(v, list):
            if len(v) == 1:
                return match_st(v[0], st)
            elif occurrence is None or occurrence == '?':
                return False
            else:
                return all(match_st(x, st) for x in v)
        elif st == 'item()':
            return isinstance(v, (XPathNode, AnyAtomicType, list, xpath_tokens.XPathFunction))
        elif st == 'numeric' or st == 'xs:numeric':
            return isinstance(v, NumericProxy)
        elif st.startswith('function('):
            if not isinstance(v, xpath_tokens.XPathFunction):
                return False
            return v.match_function_test(st)

        elif st.startswith('array('):
            if not isinstance(v, xpath_tokens.XPathArray):
                return False
            if st == 'array(*)':
                return True

            item_st = st[6:-1]
            return all(match_st(x, item_st) for x in v.items())

        elif st.startswith('map('):
            if not isinstance(v, xpath_tokens.XPathMap):
                return False
            if st == 'map(*)':
                return True

            key_st, _, value_st = st[4:-1].partition(', ')
            if key_st.endswith(('+', '*')):
                raise xpath_error('XPST0003', 'no multiples occurs for a map key')

            return all(match_st(k, key_st) and match_st(v, value_st) for k, v in v.items())

        if isinstance(v, XPathNode):
            value_kind = v.kind
        elif '(' in st:
            return False
        elif not strict and st == 'xs:anyURI' and isinstance(v, str):
            return True
        else:
            try:
                return is_instance(v, st, parser)
            except (KeyError, ValueError):
                raise xpath_error('XPST0051')

        if st == 'node()':
            return True
        elif not st.startswith(value_kind) or not st.endswith(')'):
            return False
        elif st == f'{value_kind}()':
            return True
        elif value_kind == 'document':
            element_test = st[14:-1]
            if not element_test:
                return True
            document = cast(DocumentNode, v)
            return any(
                match_st(e, element_test) for e in document if isinstance(e, ElementNode)
            )
        elif value_kind not in ('element', 'attribute'):
            return False

        _, params = st[:-1].split('(')
        if ', ' not in st:
            name = params
        else:
            name, type_name = params.rsplit(', ', 1)
            if type_name.endswith('?'):
                type_name = type_name[:-1]
            elif isinstance(v, ElementNode) and v.nilled:
                return False

            if type_name == 'xs:untyped':
                if isinstance(v, (ElementNode, AttributeNode)) \
                        and v.xsd_type is not None:
                    return False
            else:
                try:
                    if not is_instance(v.typed_value, type_name, parser):
                        return False
                except (KeyError, ValueError):
                    raise xpath_error('XPST0051')

        if name == '*':
            return True

        try:
            exp_name = get_expanded_name(name, parser.namespaces)  # type: ignore[union-attr]
        except (KeyError, ValueError):
            return False
        except AttributeError:
            return True if v.name == name else False
        else:
            return True if v.name == exp_name else False

    return match_st(value, normalize_sequence_type(sequence_type))
