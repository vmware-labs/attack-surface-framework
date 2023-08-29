#
# Copyright (c), 2018-2021, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
# mypy: ignore-errors
"""
XPath 2.0 implementation - part 3 (functions)
"""
import math
import datetime
import time
import re
import os.path
import unicodedata
from copy import copy
from decimal import Decimal, DecimalException
from string import ascii_letters
from urllib.parse import urlsplit, quote as urllib_quote

from ..exceptions import ElementPathValueError
from ..helpers import QNAME_PATTERN, is_idrefs, is_xml_codepoint, round_number
from ..datatypes import DateTime10, DateTime, Date10, Date, Float10, \
    DoubleProxy, Time, Duration, DayTimeDuration, YearMonthDuration, \
    UntypedAtomic, AnyURI, QName, NCName, Id, ArithmeticProxy, NumericProxy
from ..namespaces import XML_NAMESPACE, get_namespace, split_expanded_name, \
    XML_BASE, XML_ID, XML_LANG
from ..compare import deep_equal
from ..sequence_types import match_sequence_type
from ..xpath_context import XPathSchemaContext
from ..xpath_nodes import XPathNode, DocumentNode, ElementNode
from ..xpath_tokens import XPathFunction
from ..regex import RegexError, translate_pattern
from ..collations import CollationManager
from ._xpath2_operators import XPath2Parser

method = XPath2Parser.method
function = XPath2Parser.function


def is_local_url_scheme(scheme):
    return scheme in ('', 'file') or len(scheme) == 1 and scheme in ascii_letters


def is_local_dir_url(url):
    url_parts = urlsplit(url)
    return is_local_url_scheme(url_parts.scheme) and os.path.isdir(url_parts.path.lstrip(':'))


###
# Sequence types (allowed only for type checking in treat-as/instance-of statements)
function('empty-sequence', nargs=0, label='sequence type')


@method(function('item', nargs=0, label='sequence type'))
def evaluate_item_sequence_type(self, context=None):
    if context is None:
        raise self.missing_context()
    return context.root if context.item is None else context.item


@method('item')
def nud_item_sequence_type(self):
    XPathFunction.nud(self)
    if self.parser.next_token.symbol in ('*', '+', '?'):
        self.occurrence = self.parser.next_token.symbol
        self.parser.advance()
    return self


###
# Function for QNames
@method(function('prefix-from-QName', nargs=1,
                 sequence_types=('xs:QName?', 'xs:NCName?')))
def evaluate_prefix_from_qname_function(self, context=None):
    if self.context is not None:
        context = self.context

    qname = self.get_argument(context)
    if qname is None:
        return []
    elif not isinstance(qname, QName):
        raise self.error('XPTY0004', 'argument has an invalid type %r' % type(qname))
    return NCName(qname.prefix) if qname.prefix else []


@method(function('local-name-from-QName', nargs=1,
                 sequence_types=('xs:QName?', 'xs:NCName?')))
def evaluate_local_name_from_qname_function(self, context=None):
    if self.context is not None:
        context = self.context

    qname = self.get_argument(context)
    if qname is None:
        return []
    elif not isinstance(qname, QName):
        if self.parser.version >= '3.0' and \
                isinstance(self.data_value(qname), UntypedAtomic):
            code = 'XPTY0117'
        else:
            code = 'XPTY0004'
        raise self.error(code, 'argument has an invalid type %r' % type(qname))
    return NCName(qname.local_name)


@method(function('namespace-uri-from-QName', nargs=1,
                 sequence_types=('xs:QName?', 'xs:anyURI?')))
def evaluate_uri_from_qname_function(self, context=None):
    if self.context is not None:
        context = self.context

    qname = self.get_argument(context)
    if qname is None:
        return []
    elif not isinstance(qname, QName):
        if self.parser.version >= '3.0' and \
                isinstance(self.data_value(qname), UntypedAtomic):
            code = 'XPTY0117'
        else:
            code = 'XPTY0004'
        raise self.error(code, 'argument has an invalid type %r' % type(qname))
    return AnyURI(qname.uri or '')


@method(function('namespace-uri-for-prefix', nargs=2,
                 sequence_types=('xs:string?', 'element()', 'xs:anyURI?')))
def evaluate_namespace_uri_for_prefix_function(self, context=None):
    if self.context is not None:
        context = self.context
    elif context is None:
        raise self.missing_context()

    prefix = self.get_argument(context=copy(context))
    if prefix is None:
        prefix = ''
    if not isinstance(prefix, str):
        raise self.error('FORG0006', '1st argument has an invalid type %r' % type(prefix))

    elem = self.get_argument(context, index=1)
    if not isinstance(elem, ElementNode):
        raise self.error('FORG0006', '2nd argument %r is not an element node' % elem)

    ns_uris = {get_namespace(e.tag) for e in elem.elem.iter() if not callable(e.tag)}
    for p, uri in self.parser.namespaces.items():
        if uri in ns_uris:
            if p == prefix:
                if not prefix or uri:
                    return AnyURI(uri)
                else:
                    msg = 'Prefix %r is associated to no namespace'
                    raise self.error('XPST0081', msg % prefix)
    else:
        return []


@method(function('in-scope-prefixes', nargs=1, sequence_types=('element()', 'xs:string*')))
def select_in_scope_prefixes_function(self, context=None):
    if self.context is not None:
        context = self.context
    elif context is None:
        raise self.missing_context()

    arg = self.get_argument(context, required=True)
    if not isinstance(arg, ElementNode):
        raise self.error('XPTY0004', 'argument %r is not an element node' % arg)

    elem = arg.elem
    if isinstance(context, XPathSchemaContext):
        # For schema context returns prefixes of static namespaces
        for pfx, uri in self.parser.namespaces.items():
            if uri:
                yield pfx or ''
    elif hasattr(elem, 'nsmap'):
        # For lxml returns Element nsmap prefixes, replacing None with ''
        if 'xml' not in elem.nsmap:
            yield 'xml'
        for pfx, uri in elem.nsmap.items():
            if uri:
                yield pfx or ''
    else:
        # For ElementTree returns module registered prefixes
        for pfx, uri in self.parser.namespaces.items():
            if uri:
                yield pfx or ''

        if context.namespaces:
            yield from (x for x in context.namespaces if x not in self.parser.namespaces)


@method(function('resolve-QName', nargs=2,
                 sequence_types=('xs:string?', 'element()', 'xs:QName?')))
def evaluate_resolve_qname_function(self, context=None):
    if self.context is not None:
        context = self.context

    qname = self.get_argument(context=copy(context))
    if qname is None:
        return []
    elif not isinstance(qname, str):
        raise self.error('FORG0006', '1st argument has an invalid type %r' % type(qname))

    if context is None:
        raise self.missing_context()

    elem = self.get_argument(context, index=1)
    if not isinstance(elem, ElementNode):
        raise self.error('FORG0006', '2nd argument %r is not an element node' % elem)

    qname = qname.strip()
    match = QNAME_PATTERN.match(qname)
    if match is None:
        raise self.error('FOCA0002', '1st argument must be an xs:QName')

    prefix = match.groupdict()['prefix'] or ''
    if prefix == 'xml':
        return QName(XML_NAMESPACE, qname)

    try:
        nsmap = elem.nsmap
    except AttributeError:
        nsmap = self.parser.namespaces

    for pfx, uri in nsmap.items():
        if pfx is None:
            pfx = ''
        if pfx == prefix:
            if pfx:
                return QName(uri, '{}:{}'.format(pfx, match.groupdict()['local']))
            else:
                return QName(uri, match.groupdict()['local'])

    if prefix or '' in nsmap or None in nsmap:
        raise self.error('FONS0004', 'no namespace found for prefix %r' % prefix)
    return QName('', qname)


###
# Accessor functions
@method(function('node-name', nargs=1, sequence_types=('node()?', 'xs:QName?')))
def evaluate_node_name_function(self, context=None):
    if self.context is not None:
        context = self.context

    arg = self.get_argument(context)
    if arg is None:
        return []
    elif not isinstance(arg, XPathNode):
        raise self.error('XPTY0004', 'an XPath node required')

    name = arg.name
    if name is None:
        return []
    elif name.startswith('{'):
        # name is a QName in extended format
        namespace, local_name = split_expanded_name(name)
        for pfx, uri in self.parser.namespaces.items():
            if uri == namespace:
                return QName(uri, '{}:{}'.format(pfx, local_name))
        raise self.error('FONS0004', 'no prefix found for namespace {}'.format(namespace))
    else:
        # name is a local name
        return QName(self.parser.namespaces.get('', ''), name)


@method(function('nilled', nargs=1, sequence_types=('node()?', 'xs:boolean?')))
def evaluate_nilled_function(self, context=None):
    if self.context is not None:
        context = self.context

    arg = self.get_argument(context)
    if arg is None:
        return []
    elif not isinstance(arg, XPathNode):
        raise self.error('XPTY0004', 'an XPath node required')
    return arg.nilled


@method(function('data', nargs=1, sequence_types=('item()*', 'xs:anyAtomicType*')))
def select_data_function(self, context=None):
    yield from self[0].atomization(self.context or context)


@method(function('base-uri', nargs=(0, 1), sequence_types=('node()?', 'xs:anyURI?')))
def evaluate_base_uri_function(self, context=None):
    if self.context is not None:
        context = self.context

    item = self.get_argument(context, default_to_context=True)
    if context is None:
        raise self.missing_context("context item is undefined")
    elif item is None:
        return []
    elif not isinstance(item, XPathNode):
        raise self.error('XPTY0004', "context item is not a node")
    elif isinstance(item, DocumentNode):
        for e in item:
            if isinstance(e, ElementNode):
                base_uri = e.elem.get(XML_BASE)
                if base_uri is not None:
                    return AnyURI(base_uri)
        else:
            return AnyURI('')
    else:
        context.item = item
        base_uri = []
        for item in context.iter_ancestors(axis='ancestor-or-self'):
            if isinstance(item, ElementNode):
                uri = item.elem.get(XML_BASE)
                if uri is not None:
                    if base_uri and urlsplit(uri).scheme:
                        break

                    base_uri.append(uri)
                    if not urlsplit(uri).path.endswith('/'):
                        break

        return AnyURI(''.join(base_uri))


@method(function('document-uri', nargs=1, sequence_types=('node()?', 'xs:anyURI?')))
def evaluate_document_uri_function(self, context=None):
    if self.context is not None:
        context = self.context
    elif context is None:
        raise self.missing_context()

    arg = self.get_argument(context)
    if isinstance(arg, DocumentNode):
        uri = arg.document_uri
        if uri is not None:
            return AnyURI(uri)
        elif isinstance(context.root, DocumentNode):
            if context.documents:
                for uri, doc in context.documents.items():
                    if doc and doc.document is context.root.document:
                        return AnyURI(uri)

    return []


###
# Number functions
@method(function('round-half-to-even', nargs=(1, 2),
                 sequence_types=('xs:numeric?', 'xs:integer', 'xs:numeric?')))
def evaluate_round_half_to_even_function(self, context=None):
    if self.context is not None:
        context = self.context

    item = self.get_argument(context)
    if item is None:
        return []
    elif isinstance(item, float) and (math.isnan(item) or math.isinf(item)):
        return item
    elif not isinstance(item, (float, int, Decimal)):
        code = 'XPTY0004' if isinstance(item, str) else 'FORG0006'
        raise self.error(code, "invalid argument type {!r}".format(type(item)))

    precision = 0 if len(self) < 2 else self[1].evaluate(context)
    try:
        if isinstance(item, int):
            return round(item, precision)
        elif isinstance(item, Decimal):
            return round(item, precision)
        elif isinstance(item, Float10):
            return Float10(round(item, precision))
        return float(round(Decimal.from_float(item), precision))
    except TypeError as err:
        raise self.error('XPTY0004', err)
    except (DecimalException, OverflowError):
        if isinstance(item, Decimal):
            return Decimal.from_float(round(float(item), precision))
        return round(item, precision)


@method(function('abs', nargs=1, sequence_types=('xs:numeric?', 'xs:numeric?')))
def evaluate_abs_function(self, context=None):
    if self.context is not None:
        context = self.context

    item = self.get_argument(context)
    if item is None:
        return []
    elif isinstance(item, float) and math.isnan(item):
        return item
    elif isinstance(item, XPathNode):
        value = self.string_value(item)
        try:
            return abs(Decimal(value))
        except DecimalException:
            raise self.error('FOCA0002', "invalid string value {!r} for {!r}".format(value, item))
    elif isinstance(item, bool) or not isinstance(item, (float, int, Decimal)):
        raise self.error('XPTY0004', "invalid argument type {!r}".format(type(item)))
    else:
        return abs(item)


###
# Aggregate functions
@method(function('avg', nargs=1, sequence_types=('xs:anyAtomicType*', 'xs:anyAtomicType')))
def evaluate_avg_function(self, context=None):
    if self.context is not None:
        context = self.context

    values = []
    for item in self[0].atomization(context):
        if isinstance(item, UntypedAtomic):
            values.append(self.cast_to_double(item.value))
        elif isinstance(item, (AnyURI, bool)):
            raise self.error('FORG0006', 'non numeric value {!r} in the sequence'.format(item))
        else:
            values.append(item)

    if not values:
        return []
    elif isinstance(values[0], Duration):
        value = values[0]
        try:
            for item in values[1:]:
                value = value + item
            return value / len(values)
        except TypeError as err:
            raise self.error('FORG0006', err)
    elif all(isinstance(x, int) for x in values):
        result = sum(values) / Decimal(len(values))
        return int(result) if result % 1 == 0 else result
    elif all(isinstance(x, (int, Decimal)) for x in values):
        return sum(values) / Decimal(len(values))
    elif all(not isinstance(x, DoubleProxy) for x in values):
        try:
            return sum(Float10(x) if isinstance(x, Decimal) else x for x in values) / len(values)
        except TypeError as err:
            raise self.error('FORG0006', err)
    else:
        try:
            return sum(float(x) if isinstance(x, Decimal) else x for x in values) / len(values)
        except TypeError as err:
            raise self.error('FORG0006', err)


@method(function('max', nargs=(1, 2),
                 sequence_types=('xs:anyAtomicType*', 'xs:string', 'xs:anyAtomicType?')))
@method(function('min', nargs=(1, 2),
                 sequence_types=('xs:anyAtomicType*', 'xs:string', 'xs:anyAtomicType?')))
def evaluate_max_min_functions(self, context=None):

    def max_or_min():
        if not values:
            return values
        elif all(isinstance(x, str) for x in values):
            if to_any_uri:
                return AnyURI(aggregate_func(values))
        elif any(isinstance(x, str) for x in values):
            if any(isinstance(x, ArithmeticProxy) for x in values):
                raise self.error('FORG0006', "cannot compare strings with numeric data")
        elif all(isinstance(x, (Decimal, int)) for x in values):
            return aggregate_func(values)
        elif any(isinstance(x, float) and math.isnan(x) for x in values):
            return float_class('NaN')
        elif all(isinstance(x, (int, float, Decimal)) for x in values):
            return float_class(aggregate_func(values))
        return aggregate_func(values)

    values = []
    float_class = None
    to_any_uri = None
    aggregate_func = max if self.symbol == 'max' else min

    if self.context is not None:
        context = self.context

    for item in self[0].atomization(context):
        if isinstance(item, UntypedAtomic):
            values.append(self.cast_to_double(item))
            float_class = float
        elif isinstance(item, float):
            values.append(item)
            if float_class is None:
                float_class = type(item)
            elif float_class is Float10 and not isinstance(item, Float10):
                float_class = float
        elif isinstance(item, AnyURI):
            values.append(item.value)
            if to_any_uri is None:
                to_any_uri = True
        elif isinstance(item, (DayTimeDuration, YearMonthDuration)):
            values.append(item)
        elif isinstance(item, (Duration, QName)):
            raise self.error('FORG0006', "xs:{} is not an ordered type".format(type(item).name))
        else:
            to_any_uri = False
            values.append(item)

    if len(self) < 2:
        collation = self.parser.default_collation
    else:
        collation = self.get_argument(context, 1, required=True, cls=str)

    with CollationManager(collation, self):
        try:
            return max_or_min()
        except TypeError as err:
            raise self.error('FORG0006', err)


###
# General functions for sequences
@method(function('empty', nargs=1, sequence_types=('item()*', 'xs:boolean')))
@method(function('exists', nargs=1, sequence_types=('item()*', 'xs:boolean')))
def evaluate_empty_and_exists_functions(self, context=None):
    return next(iter(self.select(self.context or context)))


@method('empty')
def select_empty_function(self, context=None):
    try:
        value = next(iter(self[0].select(self.context or context)))
    except StopIteration:
        yield True
    else:
        yield not value and isinstance(value, list)


@method('exists')
def select_exists_function(self, context=None):
    try:
        value = next(iter(self[0].select(self.context or context)))
    except StopIteration:
        yield False
    else:
        yield not (not value and isinstance(value, list))


@method(function('distinct-values', nargs=(1, 2),
                 sequence_types=('xs:anyAtomicType*', 'xs:string', 'xs:anyAtomicType*')))
def select_distinct_values_function(self, context=None):

    def distinct_values(case_insensitive=False):
        nan = False
        results = []
        for value in self[0].atomization(context):
            if case_insensitive and isinstance(value, (str, bytes)):
                value = value.casefold()

            if isinstance(value, (float, Decimal)):
                if math.isnan(value):
                    if not nan:
                        yield value
                        nan = True
                elif all(not math.isclose(value, x, rel_tol=1E-18, abs_tol=0)
                         for x in results if isinstance(x, (int, Decimal, float))):
                    yield value
                    results.append(value)

            elif value not in results:
                yield value
                results.append(value)

    if len(self) < 2:
        collation = self.parser.default_collation
    else:
        collation = self.get_argument(self.context or context, 1, required=True, cls=str)

    with CollationManager(collation, self):
        yield from distinct_values()


@method(function('insert-before', nargs=3,
                 sequence_types=('item()*', 'xs:integer', 'item()*', 'item()*')))
def select_insert_before_function(self, context=None):
    if self.context is not None:
        context = self.context

    position = self.get_argument(context, 1, required=True, cls=int)
    insert_at_pos = max(0, position - 1)

    inserted = False
    for pos, result in enumerate(self[0].select(context)):
        if not inserted and pos == insert_at_pos:
            yield from self[2].select(context)
            inserted = True
        yield result

    if not inserted:
        yield from self[2].select(context)


@method(function('index-of', nargs=(2, 3), sequence_types=(
        'xs:anyAtomicType*', 'xs:anyAtomicType', 'xs:string', 'xs:integer*')))
def select_index_of_function(self, context=None):
    if self.context is not None:
        context = self.context

    value = self[1].get_atomized_operand(copy(context))
    if value is None:
        raise self.error('XPTY0004', "2nd argument cannot be an empty sequence")

    if len(self) < 3:
        collation = self.parser.default_collation
    else:
        collation = self.get_argument(context, 2, required=True, cls=str)

    with CollationManager(collation, self) as manager:
        for pos, result in enumerate(self[0].atomization(context), start=1):
            if manager.eq(result, value):
                yield pos


@method(function('remove', nargs=2, sequence_types=('item()*', 'xs:integer', 'item()*')))
def select_remove_function(self, context=None):
    if self.context is not None:
        context = self.context

    position = self.get_argument(context, 1)
    if not isinstance(position, int):
        raise self.error('XPTY0004', 'an xs:integer required')

    for pos, result in enumerate(self[0].select(context), start=1):
        if pos != position:
            yield result


@method(function('reverse', nargs=1, sequence_types=('item()*', 'item()*')))
def select_reverse_function(self, context=None):
    yield from reversed([x for x in self[0].select(self.context or context)])


@method(function('subsequence', nargs=(2, 3),
                 sequence_types=('item()*', 'xs:double', 'xs:double', 'item()*')))
def select_subsequence_function(self, context=None):
    if self.context is not None:
        context = self.context

    starting_loc = self.get_argument(context, 1, cls=NumericProxy)
    if not math.isnan(starting_loc) and not math.isinf(starting_loc):
        starting_loc = float(round_number(starting_loc))

    if len(self) == 2:
        for pos, result in enumerate(self[0].select(context), start=1):
            if starting_loc <= pos:
                yield result
    else:
        length = self.get_argument(context, 2, cls=NumericProxy)
        if not math.isnan(length) and not math.isinf(length):
            length = float(round_number(length))

        for pos, result in enumerate(self[0].select(context), start=1):
            if starting_loc <= pos < starting_loc + length:
                yield result


@method(function('unordered', nargs=1, sequence_types=('item()*', 'item()*')))
def select_unordered_function(self, context=None):
    if self.context is not None:
        context = self.context

    yield from sorted([x for x in self[0].select(context)], key=lambda x: self.string_value(x))


###
# Cardinality functions for sequences
@method(function('zero-or-one', nargs=1, sequence_types=('item()*', 'item()?')))
def select_zero_or_one_function(self, context=None):
    results = iter(self[0].select(self.context or context))
    try:
        item = next(results)
    except StopIteration:
        return

    try:
        next(results)
    except StopIteration:
        yield item
    else:
        raise self.error('FORG0003')


@method(function('one-or-more', nargs=1, sequence_types=('item()*', 'item()+')))
def select_one_or_more_function(self, context=None):
    results = iter(self[0].select(self.context or context))
    try:
        item = next(results)
    except StopIteration:
        raise self.error('FORG0004') from None
    else:
        yield item
        while True:
            try:
                yield next(results)
            except StopIteration:
                break


@method(function('exactly-one', nargs=1, sequence_types=('item()*', 'item()')))
def select_exactly_one_function(self, context=None):
    results = iter(self[0].select(context))
    try:
        item = next(results)
    except StopIteration:
        raise self.error('FORG0005') from None
    else:
        try:
            next(results)
        except StopIteration:
            yield item
        else:
            raise self.error('FORG0005')


###
# Comparing sequences
@method(function('deep-equal', nargs=(2, 3),
                 sequence_types=('item()*', 'item()*', 'xs:string', 'xs:boolean')))
def evaluate_deep_equal_function(self, context=None):
    if self.context is not None:
        context = self.context

    if len(self) < 3:
        collation = self.parser.default_collation
    else:
        collation = self.get_argument(context, 2, required=True, cls=str)

    return deep_equal(
        seq1=self[0].select(copy(context)),
        seq2=self[1].select(copy(context)),
        collation=collation,
    )


###
# Regex
@method(function('matches', nargs=(2, 3),
                 sequence_types=('xs:string?', 'xs:string', 'xs:string', 'xs:boolean')))
def evaluate_matches_function(self, context=None):
    if self.context is not None:
        context = self.context

    input_string = self.get_argument(context, default='', cls=str)
    pattern = self.get_argument(context, 1, required=True, cls=str)
    flags = 0
    if len(self) > 2:
        for c in self.get_argument(context, 2, required=True, cls=str):
            if c in 'smix':
                flags |= getattr(re, c.upper())
            elif c == 'q' and self.parser.version > '2':
                pattern = re.escape(pattern)
            else:
                raise self.error('FORX0001', "Invalid regular expression flag %r" % c)

    try:
        python_pattern = translate_pattern(pattern, flags, self.parser.xsd_version)
        return re.search(python_pattern, input_string, flags=flags) is not None
    except (re.error, RegexError) as err:
        msg = "Invalid regular expression: {}"
        raise self.error('FORX0002', msg.format(str(err))) from None
    except OverflowError as err:
        raise self.error('FORX0002', err) from None


REPLACEMENT_PATTERN = re.compile(r'^([^\\$]|\\{2}|\\\$|\$\d+)*$')


@method(function('replace', nargs=(3, 4), sequence_types=(
        'xs:string?', 'xs:string', 'xs:string', 'xs:string', 'xs:string')))
def evaluate_replace_function(self, context=None):
    if self.context is not None:
        context = self.context

    input_string = self.get_argument(context, default='', cls=str)
    pattern = self.get_argument(context, 1, required=True, cls=str)
    replacement = self.get_argument(context, 2, required=True, cls=str)
    flags = 0
    q_flag = False
    if len(self) > 3:
        for c in self.get_argument(context, 3, required=True, cls=str):
            if c in 'smix':
                flags |= getattr(re, c.upper())
            elif c == 'q' and self.parser.version > '2':
                pattern = re.escape(pattern)
                q_flag = True
            else:
                raise self.error('FORX0001', "Invalid regular expression flag %r" % c)

    try:
        python_pattern = translate_pattern(pattern, flags, self.parser.xsd_version)
        pattern = re.compile(python_pattern, flags=flags)
    except (re.error, RegexError):
        raise self.error('FORX0002', "Invalid regular expression %r" % pattern)
    else:
        if pattern.search(''):
            msg = "Regular expression %r matches zero-length string"
            raise self.error('FORX0003', msg % pattern.pattern)
        elif q_flag:
            # use replacement string as is (but inactivating escapes)
            replacement = replacement.replace('\\', '\\\\')
            input_string = input_string.replace('\\', '\\\\')
            return pattern.sub(replacement, input_string).replace('\\\\', '\\')

        elif REPLACEMENT_PATTERN.search(replacement) is None:
            raise self.error('FORX0004', "Invalid replacement string %r" % replacement)
        else:
            for g in range(pattern.groups, -1, -1):
                if '$%d' % g in replacement:
                    replacement = re.sub(r'(?<!\\)\$%d' % g, r'\\g<%d>' % g, replacement)

            return pattern.sub(replacement, input_string).replace('\\$', '$')


@method(function('tokenize', nargs=(1, 3),
                 sequence_types=('xs:string?', 'xs:string', 'xs:string', 'xs:string*')))
def evaluate_tokenize_function(self, context=None):
    if self.context is not None:
        context = self.context

    input_string = self.get_argument(context, cls=str)
    if input_string is None:
        return []
    elif self.parser.version >= '3.1' and len(self) == 1:
        pattern = ' '
        input_string = ' '.join(re.split('[ \t\n\r\f\v]+', input_string.strip(' \t\n\r\f\v')))
    else:
        pattern = self.get_argument(context, 1, required=True, cls=str)

    flags = 0
    if len(self) > 2:
        for c in self.get_argument(context, 2, required=True, cls=str):
            if c in 'smix':
                flags |= getattr(re, c.upper())
            elif c == 'q' and self.parser.version > '2':
                pattern = re.escape(pattern)
            else:
                raise self.error('FORX0001', "Invalid regular expression flag %r" % c)

    try:
        python_pattern = translate_pattern(pattern, flags, self.parser.xsd_version)
        pattern = re.compile(python_pattern, flags=flags)
    except (re.error, RegexError):
        raise self.error('FORX0002', "Invalid regular expression %r" % pattern) from None
    else:
        if pattern.search(''):
            msg = "Regular expression %r matches zero-length string"
            raise self.error('FORX0003', msg % pattern.pattern)

    result = []
    if input_string:
        for value in pattern.split(input_string):
            if value is not None and pattern.search(value) is None:
                result.append(value)

        if len(result) == 1:
            return result[0]

    return result


###
# Functions on anyURI
@method(function('resolve-uri', nargs=(1, 2),
                 sequence_types=('xs:string?', 'xs:string', 'xs:anyURI?')))
def evaluate_resolve_uri_function(self, context=None):
    if self.context is not None:
        context = self.context

    relative = self.get_argument(context, cls=str)
    if len(self) == 1:
        if self.parser.base_uri is None:
            raise self.error('FONS0005')
        elif relative is None:
            return []
        elif not AnyURI.is_valid(relative):
            raise self.error('FORG0002', '{!r} is not a valid URI'.format(relative))
        else:
            return self.get_absolute_uri(relative, as_string=False)

    base_uri = self.get_argument(context, index=1, required=True, cls=str)
    if not AnyURI.is_valid(base_uri):
        raise self.error('FORG0002', '{!r} is not a valid URI'.format(base_uri))
    elif relative is None:
        return []
    elif not AnyURI.is_valid(relative):
        raise self.error('FORG0002', '{!r} is not a valid URI'.format(relative))
    else:
        return self.get_absolute_uri(relative, base_uri, as_string=False)


###
# String functions

@method(function('codepoints-to-string', nargs=1,
                 sequence_types=('xs:integer*', 'xs:string')))
def evaluate_codepoints_to_string_function(self, context=None):
    if self.context is not None:
        context = self.context

    result = []
    for value in self[0].select(context):
        if isinstance(value, UntypedAtomic):
            value = int(value)

        if not isinstance(value, int):
            msg = "invalid type {} for codepoint {}".format(type(value), value)
            if isinstance(value, str):
                raise self.error('XPTY0004', msg)
            raise self.error('FORG0006', msg)
        elif is_xml_codepoint(value):
            result.append(chr(value))
        else:
            msg = "{} is not a valid XML 1.0 codepoint".format(value)
            raise self.error('FOCH0001', msg)

    return ''.join(result)


@method(function('string-to-codepoints', nargs=1,
                 sequence_types=('xs:string?', 'xs:integer*')))
def evaluate_string_to_codepoints_function(self, context=None):
    arg = self.get_argument(self.context or context, cls=str)
    return [ord(c) for c in arg] if arg else []


@method(function('compare', nargs=(2, 3),
                 sequence_types=('xs:string?', 'xs:string?', 'xs:string', 'xs:integer?')))
def evaluate_compare_function(self, context=None):
    if self.context is not None:
        context = self.context

    comp1 = self.get_argument(context, 0, cls=str, promote=(AnyURI, UntypedAtomic))
    comp2 = self.get_argument(context, 1, cls=str, promote=(AnyURI, UntypedAtomic))
    if comp1 is None or comp2 is None:
        return []

    if len(self) < 3:
        collation = self.parser.default_collation
    else:
        collation = self.get_argument(context, 2, required=True)

    with CollationManager(collation, self) as manager:
        value = manager.strcoll(comp1, comp2)

    return 0 if not value else 1 if value > 0 else -1


@method(function('contains', nargs=(2, 3),
                 sequence_types=('xs:string?', 'xs:string?', 'xs:string', 'xs:boolean')))
def evaluate_contains_function(self, context=None):
    if self.context is not None:
        context = self.context

    arg1 = self.get_argument(context, default='', cls=str)
    arg2 = self.get_argument(context, index=1, default='', cls=str)

    if len(self) < 3:
        collation = self.parser.default_collation
    else:
        collation = self.get_argument(context, 2, required=True, cls=str)

    with CollationManager(collation, self) as manager:
        return manager.contains(arg1, arg2)


@method(function('codepoint-equal', nargs=2,
                 sequence_types=('xs:string?', 'xs:string?', 'xs:boolean?')))
def evaluate_codepoint_equal_function(self, context=None):
    if self.context is not None:
        context = self.context

    comp1 = self.get_argument(context, 0, cls=str)
    comp2 = self.get_argument(context, 1, cls=str)
    if comp1 is None or comp2 is None:
        return []
    elif len(comp1) != len(comp2):
        return False
    else:
        return all(ord(c1) == ord(c2) for c1, c2 in zip(comp1, comp2))


@method(function('string-join', nargs=2,
                 sequence_types=('xs:string*', 'xs:string', 'xs:string')))
def evaluate_string_join_function(self, context=None):
    if self.context is not None:
        context = self.context

    items = [
        self.validated_value(s, cls=str, promote=AnyURI, index=k)
        for k, s in enumerate(self[0].atomization(context))
    ]
    return self.get_argument(context, 1, required=True, cls=str).join(items)


@method(function('normalize-unicode', nargs=(1, 2),
                 sequence_types=('xs:string?', 'xs:string', 'xs:string')))
def evaluate_normalize_unicode_function(self, context=None):
    if self.context is not None:
        context = self.context

    arg = self.get_argument(context, default='', cls=str)
    if len(self) > 1:
        normalization_form = self.get_argument(context, 1, cls=str)
        if normalization_form is None:
            raise self.error('XPTY0004', "2nd argument can't be an empty sequence")
        else:
            normalization_form = normalization_form.strip().upper()
    else:
        normalization_form = 'NFC'

    if normalization_form == 'FULLY-NORMALIZED':
        msg = "%r normalization form not supported" % normalization_form
        raise self.error('FOCH0003', msg)
    if not arg:
        return ''
    elif not normalization_form:
        return arg

    try:
        return unicodedata.normalize(normalization_form, arg)
    except ValueError:
        msg = "unsupported normalization form %r" % normalization_form
        raise self.error('FOCH0003', msg) from None


@method(function('upper-case', nargs=1, sequence_types=('xs:string?', 'xs:string')))
def evaluate_upper_case_function(self, context=None):
    return self.get_argument(self.context or context, default='', cls=str).upper()


@method(function('lower-case', nargs=1, sequence_types=('xs:string?', 'xs:string')))
def evaluate_lower_case_function(self, context=None):
    return self.get_argument(self.context or context, default='', cls=str).lower()


@method(function('encode-for-uri', nargs=1, sequence_types=('xs:string?', 'xs:string')))
def evaluate_encode_for_uri_function(self, context=None):
    uri_part = self.get_argument(self.context or context, cls=str)
    return '' if uri_part is None else urllib_quote(uri_part, safe='~')


@method(function('iri-to-uri', nargs=1, sequence_types=('xs:string?', 'xs:string')))
def evaluate_iri_to_uri_function(self, context=None):
    iri = self.get_argument(self.context or context, cls=str, promote=AnyURI)
    return '' if iri is None else urllib_quote(iri, safe='-_.!~*\'()#;/?:@&=+$,[]%')


@method(function('escape-html-uri', nargs=1, sequence_types=('xs:string?', 'xs:string')))
def evaluate_escape_html_uri_function(self, context=None):
    uri = self.get_argument(self.context or context, cls=str)
    if uri is None:
        return ''
    return urllib_quote(uri, safe=''.join(chr(cp) for cp in range(32, 127)))


@method(function('starts-with', nargs=(2, 3),
                 sequence_types=('xs:string?', 'xs:string?', 'xs:string', 'xs:boolean')))
def evaluate_starts_with_function(self, context=None):
    if self.context is not None:
        context = self.context

    arg1 = self.get_argument(context, default='', cls=str)
    arg2 = self.get_argument(context, index=1, default='', cls=str)

    if len(self) < 3:
        collation = self.parser.default_collation
    else:
        collation = self.get_argument(context, 2, required=True, cls=str)

    with CollationManager(collation, self) as manager:
        return manager.startswith(arg1, arg2)


@method(function('ends-with', nargs=(2, 3),
                 sequence_types=('xs:string?', 'xs:string?', 'xs:string', 'xs:boolean')))
def evaluate_ends_with_function(self, context=None):
    if self.context is not None:
        context = self.context

    arg1 = self.get_argument(context, default='', cls=str)
    arg2 = self.get_argument(context, index=1, default='', cls=str)

    if len(self) < 3:
        collation = self.parser.default_collation
    else:
        collation = self.get_argument(context, 2, required=True, cls=str)

    with CollationManager(collation, self) as manager:
        return manager.endswith(arg1, arg2)


@method(function('substring-before', nargs=(2, 3),
                 sequence_types=('xs:string?', 'xs:string?', 'xs:string', 'xs:string')))
@method(function('substring-after', nargs=(2, 3),
                 sequence_types=('xs:string?', 'xs:string?', 'xs:string', 'xs:string')))
def evaluate_substring_functions(self, context=None):
    if self.context is not None:
        context = self.context

    arg1 = self.get_argument(context, default='', cls=str)
    arg2 = self.get_argument(context, index=1, default='', cls=str)

    if len(self) < 3:
        collation = self.parser.default_collation
    else:
        collation = self.get_argument(context, 2, required=True, cls=str)

    with CollationManager(collation, self) as manager:
        index = manager.find(arg1, arg2)

    if index < 0:
        return ''
    if self.symbol == 'substring-before':
        return arg1[:index]
    else:
        return arg1[index + len(arg2):]


###
# Functions on durations, dates and times
@method(function('years-from-duration', nargs=1,
                 sequence_types=('xs:duration?', 'xs:integer?')))
def evaluate_years_from_duration_function(self, context=None):
    item = self.get_argument(self.context or context, cls=Duration)
    if item is None:
        return []
    elif item.months >= 0:
        return item.months // 12
    else:
        return -(abs(item.months) // 12)


@method(function('months-from-duration', nargs=1,
                 sequence_types=('xs:duration?', 'xs:integer?')))
def evaluate_months_from_duration_function(self, context=None):
    item = self.get_argument(self.context or context, cls=Duration)
    if item is None:
        return []
    elif item.months >= 0:
        return item.months % 12
    else:
        return -(abs(item.months) % 12)


@method(function('days-from-duration', nargs=1,
                 sequence_types=('xs:duration?', 'xs:integer?')))
def evaluate_days_from_duration_function(self, context=None):
    item = self.get_argument(self.context or context, cls=Duration)
    if item is None:
        return []
    elif item.seconds >= 0:
        return int(item.seconds // 86400)
    else:
        return - int(abs(item.seconds) // 86400)


@method(function('hours-from-duration', nargs=1,
                 sequence_types=('xs:duration?', 'xs:integer?')))
def evaluate_hours_from_duration_function(self, context=None):
    item = self.get_argument(self.context or context, cls=Duration)
    if item is None:
        return []
    elif item.seconds >= 0:
        return int(item.seconds // 3600 % 24)
    else:
        return - int(abs(item.seconds) // 3600 % 24)


@method(function('minutes-from-duration', nargs=1,
                 sequence_types=('xs:duration?', 'xs:integer?')))
def evaluate_minutes_from_duration_function(self, context=None):
    item = self.get_argument(self.context or context, cls=Duration)
    if item is None:
        return []
    elif item.seconds >= 0:
        return int(item.seconds // 60 % 60)
    else:
        return - int(abs(item.seconds) // 60 % 60)


@method(function('seconds-from-duration', nargs=1,
                 sequence_types=('xs:duration?', 'xs:decimal?')))
def evaluate_seconds_from_duration_function(self, context=None):
    item = self.get_argument(self.context or context, cls=Duration)
    if item is None:
        return []
    elif item.seconds >= 0:
        return item.seconds % 60
    else:
        return -(abs(item.seconds) % 60)


@method(function('year-from-dateTime', nargs=1, sequence_types=('xs:dateTime?', 'xs:integer?')))
@method(function('month-from-dateTime', nargs=1, sequence_types=('xs:dateTime?', 'xs:integer?')))
@method(function('day-from-dateTime', nargs=1, sequence_types=('xs:dateTime?', 'xs:integer?')))
@method(function('hours-from-dateTime', nargs=1, sequence_types=('xs:dateTime?', 'xs:integer?')))
@method(function('minutes-from-dateTime', nargs=1, sequence_types=('xs:dateTime?', 'xs:integer?')))
@method(function('seconds-from-dateTime', nargs=1, sequence_types=('xs:dateTime?', 'xs:decimal?')))
def evaluate_from_datetime_functions(self, context=None):
    cls = DateTime if self.parser.xsd_version == '1.1' else DateTime10
    item = self.get_argument(self.context or context, cls=cls)
    if item is None:
        return []
    elif self.symbol.startswith('year'):
        return item.year
    elif self.symbol.startswith('month'):
        return item.month
    elif self.symbol.startswith('day'):
        return item.day
    elif self.symbol.startswith('hour'):
        return item.hour
    elif self.symbol.startswith('minute'):
        return item.minute
    elif item.microsecond:
        return Decimal('{}.{}'.format(item.second, item.microsecond))
    else:
        return item.second


@method(function('timezone-from-dateTime', nargs=1,
                 sequence_types=('xs:dateTime?', 'xs:dayTimeDuration?')))
def evaluate_timezone_from_datetime_function(self, context=None):
    cls = DateTime if self.parser.xsd_version == '1.1' else DateTime10
    item = self.get_argument(self.context or context, cls=cls)
    if item is None or item.tzinfo is None:
        return []
    return DayTimeDuration(seconds=item.tzinfo.offset.total_seconds())


@method(function('year-from-date', nargs=1, sequence_types=('xs:date?', 'xs:integer?')))
@method(function('month-from-date', nargs=1, sequence_types=('xs:date?', 'xs:integer?')))
@method(function('day-from-date', nargs=1, sequence_types=('xs:date?', 'xs:integer?')))
@method(function('timezone-from-date', nargs=1,
                 sequence_types=('xs:date?', 'xs:dayTimeDuration?')))
def evaluate_from_date_functions(self, context=None):
    cls = Date if self.parser.xsd_version == '1.1' else Date10
    item = self.get_argument(self.context or context, cls=cls)
    if item is None:
        return []
    elif self.symbol.startswith('year'):
        return item.year
    elif self.symbol.startswith('month'):
        return item.month
    elif self.symbol.startswith('day'):
        return item.day
    elif item.tzinfo is None:
        return []
    return DayTimeDuration(seconds=item.tzinfo.offset.total_seconds())


@method(function('hours-from-time', nargs=1, sequence_types=('xs:time?', 'xs:integer?')))
def evaluate_hours_from_time_function(self, context=None):
    item = self.get_argument(self.context or context, cls=Time)
    return [] if item is None else item.hour


@method(function('minutes-from-time', nargs=1, sequence_types=('xs:time?', 'xs:integer?')))
def evaluate_minutes_from_time_function(self, context=None):
    item = self.get_argument(self.context or context, cls=Time)
    return [] if item is None else item.minute


@method(function('seconds-from-time', nargs=1, sequence_types=('xs:time?', 'xs:decimal?')))
def evaluate_seconds_from_time_function(self, context=None):
    item = self.get_argument(self.context or context, cls=Time)
    return [] if item is None else item.second + item.microsecond / Decimal('1000000.0')


@method(function('timezone-from-time', nargs=1,
                 sequence_types=('xs:time?', 'xs:dayTimeDuration?')))
def evaluate_timezone_from_time_function(self, context=None):
    item = self.get_argument(self.context or context, cls=Time)
    if item is None or item.tzinfo is None:
        return []
    return DayTimeDuration(seconds=item.tzinfo.offset.total_seconds())


###
# Timezone adjustment functions
@method(function('adjust-dateTime-to-timezone', nargs=(1, 2),
                 sequence_types=('xs:dateTime?', 'xs:dayTimeDuration?', 'xs:dateTime?')))
def evaluate_adjust_datetime_to_timezone_function(self, context=None):
    cls = DateTime if self.parser.xsd_version == '1.1' else DateTime10
    return self.adjust_datetime(self.context or context, cls)


@method(function('adjust-date-to-timezone', nargs=(1, 2),
                 sequence_types=('xs:date?', 'xs:dayTimeDuration?', 'xs:date?')))
def evaluate_adjust_date_to_timezone_function(self, context=None):
    cls = Date if self.parser.xsd_version == '1.1' else Date10
    return self.adjust_datetime(self.context or context, cls)


@method(function('adjust-time-to-timezone', nargs=(1, 2),
                 sequence_types=('xs:time?', 'xs:dayTimeDuration?', 'xs:time?')))
def evaluate_adjust_time_to_timezone_function(self, context=None):
    return self.adjust_datetime(self.context or context, Time)


###
# Static context functions
@method(function('default-collation', nargs=0, sequence_types=('xs:string',)))
def evaluate_default_collation_function(self, context=None):
    return self.parser.default_collation


@method(function('static-base-uri', nargs=0, sequence_types=('xs:anyURI?',)))
def evaluate_static_base_uri_function(self, context=None):
    if self.parser.base_uri is None:
        return []
    return AnyURI(self.parser.base_uri)


###
# Dynamic context functions
@method(function('current-dateTime', nargs=0, sequence_types=('xs:dateTime',)))
def evaluate_current_datetime_function(self, context=None):
    if self.context is not None:
        context = self.context

    dt = datetime.datetime.now() if context is None else context.current_dt
    if self.parser.xsd_version == '1.1':
        return DateTime(dt.year, dt.month, dt.day, dt.hour, dt.minute,
                        dt.second, dt.microsecond, dt.tzinfo)
    return DateTime10(dt.year, dt.month, dt.day, dt.hour, dt.minute,
                      dt.second, dt.microsecond, dt.tzinfo)


@method(function('current-date', nargs=0, sequence_types=('xs:date',)))
def evaluate_current_date_function(self, context=None):
    if self.context is not None:
        context = self.context

    dt = datetime.datetime.now() if context is None else context.current_dt
    if self.parser.xsd_version == '1.1':
        return Date(dt.year, dt.month, dt.day, tzinfo=dt.tzinfo)
    return Date10(dt.year, dt.month, dt.day, tzinfo=dt.tzinfo)


@method(function('current-time', nargs=0, sequence_types=('xs:time',)))
def evaluate_current_time_function(self, context=None):
    if self.context is not None:
        context = self.context

    dt = datetime.datetime.now() if context is None else context.current_dt
    return Time(dt.hour, dt.minute, dt.second, dt.microsecond, dt.tzinfo)


@method(function('implicit-timezone', nargs=0, sequence_types=('xs:dayTimeDuration',)))
def evaluate_implicit_timezone_function(self, context=None):
    if self.context is not None:
        context = self.context

    if context is not None and context.timezone is not None:
        return DayTimeDuration.fromtimedelta(context.timezone.offset)
    else:
        return DayTimeDuration.fromtimedelta(datetime.timedelta(seconds=time.timezone))


###
# The root function (Ref: https://www.w3.org/TR/2010/REC-xpath-functions-20101214/#func-root)
@method(function('root', nargs=(0, 1), sequence_types=('node()?', 'node()?')))
def evaluate_root_function(self, context=None):
    if self.context is not None:
        context = self.context
    elif context is None:
        raise self.missing_context()

    if isinstance(context, XPathSchemaContext):
        return []
    elif not self:
        if context.item is None:
            return context.root
        elif not isinstance(context.item, XPathNode):
            raise self.error('XPTY0004')

        root = context.get_root(context.item)
        return root if root is not None else []

    else:
        item = self.get_argument(context)
        if item is None:
            return []
        elif not isinstance(item, XPathNode):
            raise self.error('XPTY0004')

        root = context.get_root(item)
        return root if root is not None else []


@method(function('lang', nargs=(1, 2),
                 sequence_types=('xs:string?', 'node()', 'xs:boolean')))
def evaluate_lang_function(self, context=None):
    if self.context is not None:
        context = self.context

    if len(self) > 1:
        item = self.get_argument(context, index=1, default_to_context=True)
    elif context is None:
        raise self.missing_context()
    else:
        item = context.item

    if not isinstance(item, ElementNode):
        raise self.error('XPTY0004')

    try:
        lang = item.elem.attrib[XML_LANG].strip()
    except KeyError:
        if len(self) > 1:
            return False

        for elem in context.iter_ancestors():
            try:
                if XML_LANG in elem.elem.attrib:
                    lang = elem.elem.attrib[XML_LANG]
                    break
            except AttributeError:
                pass  # is a document node
        else:
            return False

    test_lang = self.get_argument(context, cls=str)
    if test_lang is None:
        test_lang = ''

    test_lang = test_lang.strip().lower()
    lang = lang.strip().lower()
    return lang == test_lang or lang.startswith(test_lang) and lang[len(test_lang)] == '-'


###
# Functions that generate sequences
@method(function('element-with-id', nargs=(1, 2),
                 sequence_types=('xs:string*', 'node()', 'element()*')))
@method(function('id', nargs=(1, 2),
                 sequence_types=('xs:string*', 'node()', 'element()*')))
def select_id_function(self, context=None):
    if self.context is not None:
        context = self.context

    idrefs = {x for item in self[0].select(copy(context))
              for x in self.string_value(item).split() if Id.is_valid(x)}

    if context is None:
        raise self.missing_context()

    if len(self) == 1:
        node = context.item
        if node is None:
            node = context.root
    else:
        node = self.get_argument(context, index=1)

    if not isinstance(node, XPathNode):
        raise self.error('XPTY0004')

    if isinstance(context, XPathSchemaContext):
        return

    assert context is not None
    root = context.get_root(node)
    if root is None:
        return

    # TODO: PSVI bindings with also xsi:type evaluation
    for element in filter(lambda x: isinstance(x, ElementNode), root.iter_descendants()):
        if element.elem.text in idrefs:
            if self.parser.schema is not None:
                xsd_element = self.parser.schema.find(element.path, self.parser.namespaces)
                if xsd_element is None or not xsd_element.type.is_key():
                    continue

            idrefs.remove(element.elem.text)
            if self.symbol == 'id':
                yield element
            else:
                parent = element.parent
                if parent is not None:
                    yield parent
            continue  # pragma: no cover

        for attr in element.attributes:
            if attr.value in idrefs:
                if attr.name == XML_ID:
                    idrefs.remove(attr.value)
                    yield element
                    break

                if self.parser.schema is None:
                    continue

                xsd_element = self.parser.schema.find(element.path, self.parser.namespaces)
                if xsd_element is None:
                    continue

                xsd_attribute = xsd_element.attrib.get(attr.name)
                if xsd_attribute is None or not xsd_attribute.type.is_key():
                    continue  # pragma: no cover

                idrefs.remove(attr.value)
                yield element
                break


@method(function('idref', nargs=(1, 2), sequence_types=('xs:string*', 'node()', 'node()*')))
def select_idref_function(self, context=None):
    # TODO: PSVI bindings with also xsi:type evaluation
    if self.context is not None:
        context = self.context

    ids = [x for x in self[0].select(context=copy(context))]
    node = self.get_argument(context, index=1, default_to_context=True)

    if isinstance(context, XPathSchemaContext):
        return
    elif context is None or node is not context.item:
        pass
    elif context.item is None:
        node = context.root

    if not isinstance(node, XPathNode):
        raise self.error('XPTY0004')
    elif isinstance(node, (ElementNode, DocumentNode)):
        for element in filter(lambda x: isinstance(x, ElementNode), node.iter_descendants()):
            text = element.elem.text
            if text and is_idrefs(text) and \
                    any(v in text.split() for x in ids for v in x.split()):
                yield element
                continue

            for attr in element.attributes:  # pragma: no cover
                if attr.name != XML_ID and \
                        any(v in attr.value.split() for x in ids for v in x.split()):
                    yield element
                    break


@method(function('doc', nargs=1, sequence_types=('xs:string?', 'document-node()?')))
@method(function('doc-available', nargs=1, sequence_types=('xs:string?', 'xs:boolean')))
def evaluate_doc_functions(self, context=None):
    if self.context is not None:
        context = self.context

    uri = self.get_argument(context)
    if uri is None:
        return [] if self.symbol == 'doc' else False
    elif isinstance(uri, str):
        pass
    elif isinstance(uri, AnyURI):
        uri = str(uri)
    elif isinstance(uri, UntypedAtomic):
        raise self.error('FODC0002')
    else:
        raise self.error('XPTY0004')

    if context is None:
        raise self.missing_context()
    elif isinstance(context, XPathSchemaContext):
        return [] if self.symbol == 'doc' else False

    uri = uri.strip()
    if uri.startswith(':'):
        if self.symbol == 'doc' or self.parser.version <= '3.0':
            raise self.error('FODC0005')
        return False

    try:
        uri = self.get_absolute_uri(uri)
    except ElementPathValueError as err:
        if self.symbol == 'doc':
            raise self.error('FODC0002', err.message) from None
        return False

    try:
        doc = context.documents[uri]
    except (KeyError, TypeError):
        if self.symbol == 'doc':
            if is_local_dir_url(uri):
                raise self.error('FODC0005', 'document URI is a directory')
            raise self.error('FODC0002')
        return False
    else:
        if doc is None:
            raise self.error('FODC0002')

    try:
        sequence_type = self.parser.document_types[uri]
    except (KeyError, TypeError):
        sequence_type = 'document-node()'

    if not match_sequence_type(doc, sequence_type, self.parser):
        msg = f"Type does not match sequence type {sequence_type!r}"
        raise self.error('XPDY0050', msg)

    return doc if self.symbol == 'doc' else True


@method(function('collection', nargs=(0, 1), sequence_types=('xs:string?', 'node()*')))
def evaluate_collection_function(self, context=None):
    if self.context is not None:
        context = self.context

    uri = self.get_argument(context)
    if context is None:
        raise self.missing_context()
    elif isinstance(context, XPathSchemaContext):
        return []
    elif not self or uri is None:
        if context.default_collection is None:
            raise self.error('FODC0002', 'no default collection has been defined')

        collection = context.default_collection
        sequence_type = self.parser.default_collection_type
    else:
        uri = self.get_absolute_uri(uri)
        try:
            collection = context.collections[uri]
        except (KeyError, TypeError):
            if is_local_dir_url(uri):
                raise self.error('FODC0004', 'collection URI is a directory')
            raise self.error('FODC0002', '{!r} collection not found'.format(uri)) from None

        try:
            sequence_type = self.parser.collection_types[uri]
        except (KeyError, TypeError):
            return collection

    if not match_sequence_type(collection, sequence_type, self.parser):
        msg = f"Type does not match sequence type {sequence_type!r}"
        raise self.error('XPDY0050', msg)

    return collection


###
# The error function
#
# https://www.w3.org/TR/2010/REC-xpath-functions-20101214/#func-error
# https://www.w3.org/TR/xpath-functions/#func-error
#
@method(function('error', nargs=(0, 3),
                 sequence_types=('xs:QName?', 'xs:string', 'item()*', 'none')))
def evaluate_error_function(self, context=None):
    if self.context is not None:
        context = self.context

    if not self:
        raise self.error('FOER0000')
    elif len(self) == 1:
        error = self.get_argument(context, cls=QName)
        if error is None:
            raise self.error('XPTY0004', "an xs:QName expected")
        raise self.error(error or 'FOER0000')
    else:
        error = self.get_argument(context, cls=QName)
        description = self.get_argument(context, index=1, cls=str)
        raise self.error(error or 'FOER0000', description)


###
# The trace function
#
# https://www.w3.org/TR/2010/REC-xpath-functions-20101214/#func-trace
#
@method(function('trace', nargs=2, sequence_types=('item()*', 'xs:string', 'item()*')))
def select_trace_function(self, context=None):
    if self.context is not None:
        context = self.context

    label = self.get_argument(context, index=1, cls=str)
    for value in self[0].select(context):
        self.parser.tracer('{} {}'.format(label, str(value).strip()))
        yield value


# XPath 2.0 definitions continue into module xpath2_constructors
