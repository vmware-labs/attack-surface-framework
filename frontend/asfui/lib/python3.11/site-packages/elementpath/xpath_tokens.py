#
# Copyright (c), 2018-2022, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
"""
XPathToken class and derived classes for other XPath objects (functions, constructors,
axes, maps, arrays). XPath's error creation and node helper functions are embedded in
XPathToken class, in order to raise errors related to token instances.
"""
import decimal
import math
from copy import copy
from decimal import Decimal
from itertools import product
from typing import TYPE_CHECKING, cast, Dict, Optional, List, Tuple, \
    Union, Any, Iterable, Iterator, SupportsFloat, Type
import urllib.parse

from .exceptions import ElementPathError, ElementPathValueError, \
    ElementPathTypeError, MissingContextError, xpath_error
from .helpers import ordinal, get_double, split_function_test
from .namespaces import XSD_NAMESPACE, XPATH_FUNCTIONS_NAMESPACE, \
    XPATH_MATH_FUNCTIONS_NAMESPACE, XSD_SCHEMA, XSD_DECIMAL, \
    XSD_ANY_TYPE, XSD_ANY_SIMPLE_TYPE, XSD_ANY_ATOMIC_TYPE
from .xpath_nodes import XPathNode, ElementNode, AttributeNode, \
    DocumentNode, NamespaceNode, SchemaElementNode
from .datatypes import xsd10_atomic_types, AbstractDateTime, AnyURI, \
    UntypedAtomic, Timezone, DateTime10, Date10, DayTimeDuration, Duration, \
    Integer, DoubleProxy10, DoubleProxy, QName, AtomicValueType, AnyAtomicType
from .protocols import ElementProtocol, DocumentProtocol, XsdAttributeProtocol, \
    XsdElementProtocol, XsdTypeProtocol, XsdSchemaProtocol
from .sequence_types import is_sequence_type_restriction, match_sequence_type
from .schema_proxy import AbstractSchemaProxy
from .tdop import Token, MultiLabel
from .xpath_context import XPathContext, XPathSchemaContext

if TYPE_CHECKING:
    from .xpath1 import XPath1Parser
    from .xpath2 import XPath2Parser
    from .xpath30 import XPath30Parser

    XPathParserType = Union[XPath1Parser, XPath2Parser, XPath30Parser]
else:
    XPathParserType = Any

_XSD_SPECIAL_TYPES = {XSD_ANY_TYPE, XSD_ANY_SIMPLE_TYPE, XSD_ANY_ATOMIC_TYPE}

_CHILD_AXIS_TOKENS = {
    '*', 'node', 'child', 'text', '(name)', ':', '[', 'document-node',
    'element', 'comment', 'processing-instruction', 'schema-element'
}
_LEAF_ELEMENTS_TOKENS = {
    '(name)', '*', ':', '..', '.', '[', 'self', 'child', 'parent',
    'following-sibling', 'preceding-sibling', 'ancestor', 'ancestor-or-self',
    'descendant', 'descendant-or-self', 'following', 'preceding'
}

# Type annotations aliases
NargsType = Optional[Union[int, Tuple[int, Optional[int]]]]
ClassCheckType = Union[Type[Any], Tuple[Type[Any], ...]]
PrincipalNodeType = Union[ElementProtocol, AttributeNode, ElementNode]
OperandsType = Tuple[Optional[AtomicValueType], Optional[AtomicValueType]]
XPathResultType = Union[
    AtomicValueType,
    ElementProtocol,
    XsdAttributeProtocol,
    Tuple[Optional[str], str],
    DocumentProtocol,
    DocumentNode
]

XPathTokenType = Union['XPathToken', 'XPathAxis', 'XPathFunction', 'XPathConstructor']
XPathFunctionArgType = Union[None, 'XPathToken', XPathNode, AtomicValueType,
                             List[Union['XPathToken', XPathNode, AtomicValueType]]]


class XPathToken(Token[XPathTokenType]):
    """Base class for XPath tokens."""
    parser: XPathParserType
    xsd_types: Optional[Dict[Optional[str], Union[XsdTypeProtocol, List[XsdTypeProtocol]]]]
    namespace: Optional[str]
    occurrence: Optional[str]

    xsd_types = None  # for XPath 2.0+ XML Schema types labeling
    namespace = None  # for namespace binding of names and wildcards
    occurrence = None  # occurrence indicator for item types

    def evaluate(self, context: Optional[XPathContext] = None) -> Any:
        """
        Evaluate default method for XPath tokens.

        :param context: The XPath dynamic context.
        """
        return [x for x in self.select(context)]

    def select(self, context: Optional[XPathContext] = None) -> Iterator[Any]:
        """
        Select operator that generates XPath results.

        :param context: The XPath dynamic context.
        """
        item = self.evaluate(context)
        if isinstance(item, list):
            yield from item
        else:
            yield item

    def __str__(self) -> str:
        if self.symbol == '$':
            return '$%s variable reference' % (self[0].value if self._items else '')
        elif self.symbol == ',':
            return 'comma operator' if self.parser.version > '1.0' else 'comma symbol'
        elif self.symbol == '(':
            if not self or self[0].span[0] >= self.span[0]:
                return 'parenthesized expression'
            else:
                return 'function call expression'
        return super(XPathToken, self).__str__()

    @property
    def source(self) -> str:
        symbol = self.symbol
        if self.label == 'axis':
            # For XPath 2.0 'attribute' multirole token ('kind test', 'axis')
            return '%s::%s' % (symbol, self[0].source)
        elif symbol == '/' or symbol == '//':
            if not self:
                return symbol
            elif len(self) == 1:
                return f'{symbol}{self[0].source}'
            else:
                return f'{self[0].source}{symbol}{self[1].source}'
        elif symbol == '(':
            if not self:
                return '()'
            elif len(self) == 2:
                return f'{self[0].source}({self[1].source})'
            elif self[0].span[0] < self.span[0]:
                return f'{self[0].source}()'
            else:
                return f'({self[0].source})'
        elif symbol == '[':
            return '%s[%s]' % (self[0].source, self[1].source)
        elif symbol == ',':
            return '%s, %s' % (self[0].source, self[1].source)
        elif symbol == '$' or symbol == '@':
            return f'{symbol}{self[0].source}'
        elif symbol == '#':
            return '%s#%s' % (self[0].source, self[1].source)
        elif symbol == '{' or symbol == 'Q{':
            return '%s%s}%s' % (symbol, self[0].value, self[1].source)
        elif symbol == '=>':
            if isinstance(self[1], XPathFunction):
                return '%s => %s%s' % (self[0].source, self[1].symbol, self[2].source)
            return '%s => %s%s' % (self[0].source, self[1].source, self[2].source)
        elif symbol == 'if':
            return 'if (%s) then %s else %s' % (self[0].source, self[1].source, self[2].source)
        elif symbol == 'instance':
            return '%s instance of %s' % (self[0].source, ''.join(t.source for t in self[1:]))
        elif symbol in ('treat', 'cast', 'castable'):
            return '%s %s as %s' % (self[0].source, symbol, ''.join(t.source for t in self[1:]))
        elif symbol == 'for':
            return 'for %s return %s' % (
                ', '.join('%s in %s' % (self[k].source, self[k + 1].source)
                          for k in range(0, len(self) - 1, 2)),
                self[-1].source
            )
        elif symbol in ('every', 'some'):
            return '%s %s satisfies %s' % (
                symbol,
                ', '.join('%s in %s' % (self[k].source, self[k + 1].source)
                          for k in range(0, len(self) - 1, 2)),
                self[-1].source
            )
        elif symbol == 'let':
            return 'let %s return %s' % (
                ', '.join('%s := %s' % (self[k].source, self[k + 1].source)
                          for k in range(0, len(self) - 1, 2)),
                self[-1].source
            )
        elif symbol in ('-', '+') and len(self) == 1:
            return symbol + self[0].source
        return super(XPathToken, self).source

    @property
    def child_axis(self) -> bool:
        """Is `True` if the token apply child axis for default, `False` otherwise."""
        if self.symbol not in _CHILD_AXIS_TOKENS:
            return False
        elif self.symbol == '[':
            return self._items[0].child_axis
        elif self.symbol != ':':
            return True
        return not self._items[1].label.endswith('function')

    ###
    # Tokens tree analysis methods
    def iter_leaf_elements(self) -> Iterator[str]:
        """
        Iterates through the leaf elements of the token tree if there are any,
        returning QNames in prefixed format. A leaf element is an element
        positioned at last path step. Does not consider kind tests and wildcards.
        """
        if self.symbol in ('(name)', ':'):
            yield cast(str, self.value)
        elif self.symbol in ('//', '/'):
            if self._items[-1].symbol in _LEAF_ELEMENTS_TOKENS:
                yield from self._items[-1].iter_leaf_elements()

        elif self.symbol in ('[',):
            yield from self._items[0].iter_leaf_elements()
        else:
            for tk in self._items:
                yield from tk.iter_leaf_elements()

    def parse_sequence_type(self) -> 'XPathToken':
        if self.parser.next_token.label in ('kind test', 'sequence type', 'function test'):
            token = self.parser.expression(rbp=85)
        else:
            if self.parser.next_token.symbol == 'Q{':
                token = self.parser.advance().nud()
            elif self.parser.next_token.symbol != '(name)':
                raise self.wrong_syntax()
            else:
                self.parser.advance()
                if self.parser.next_token.symbol == ':':
                    left = self.parser.token
                    self.parser.advance()
                    token = self.parser.token.led(left)
                else:
                    token = self.parser.token

                if self.parser.next_token.symbol in ('::', '('):
                    raise self.parser.next_token.wrong_syntax()

        next_symbol = self.parser.next_token.symbol
        if token.symbol != 'empty-sequence' and next_symbol in ('?', '*', '+'):
            token.occurrence = next_symbol
            self.parser.advance()
        return token

    def parse_occurrence(self) -> None:
        if self.parser.next_token.symbol in ('*', '+', '?'):
            self.occurrence = self.parser.next_token.symbol
            self.parser.advance()
            self.parser.next_token.unexpected('*', '+', '?')

    ###
    # Dynamic context methods
    def get_argument(self, context: Optional[XPathContext],
                     index: int = 0,
                     required: bool = False,
                     default_to_context: bool = False,
                     default: Optional[AtomicValueType] = None,
                     cls: Optional[Type[Any]] = None,
                     promote: Optional[ClassCheckType] = None) -> Any:
        """
        Get the argument value of a function of constructor token. A zero length sequence is
        converted to a `None` value. If the function has no argument returns the context's
        item if the dynamic context is not `None`.

        :param context: the dynamic context.
        :param index: an index for select the argument to be got, the first for default.
        :param required: if set to `True` missing or empty sequence arguments are not allowed.
        :param default_to_context: if set to `True` then the item of the dynamic context is \
        returned when the argument is missing.
        :param default: the default value returned in case the argument is an empty sequence. \
        If not provided returns `None`.
        :param cls: if a type is provided performs a type checking on item.
        :param promote: a class or a tuple of classes that are promoted to `cls` class.
        """
        item: Union[None, ElementProtocol, DocumentProtocol,
                    XPathNode, AnyAtomicType, XPathFunction]

        try:
            token = self._items[index]
        except IndexError:
            if default_to_context:
                if context is None:
                    raise self.missing_context() from None
                item = context.item if context.item is not None else context.root
            elif required:
                msg = "missing %s argument" % ordinal(index + 1)
                raise self.error('XPST0017', msg) from None
            else:
                return default
        else:
            if isinstance(token, XPathFunction) and token.is_reference():
                return token  # It's a function reference

            item = None
            for k, result in enumerate(token.select(copy(context))):
                if k == 0:
                    item = result
                elif self.parser.compatibility_mode:
                    break
                elif isinstance(context, XPathSchemaContext):
                    # Multiple schema nodes are ignored but do not raise. The target
                    # of schema context selection is XSD type association and multiple
                    # node coherency is already checked at schema level.
                    break
                else:
                    msg = "a sequence of more than one item is not allowed as argument"
                    raise self.error('XPTY0004', msg)
            else:
                if item is None:
                    if not required:
                        return default
                    ord_arg = ordinal(index + 1)
                    msg = "A not empty sequence required for {} argument"
                    raise self.error('XPTY0004', msg.format(ord_arg))

        if cls is not None:
            return self.validated_value(item, cls, promote, index)
        return item

    def get_argument_tokens(self) -> List['XPathToken']:
        """
        Builds and returns the argument tokens list, expanding the comma tokens.
        """
        tk = self
        tokens = []
        while True:
            if tk.symbol == ',':
                tokens.append(tk[1])
                tk = tk[0]
            else:
                tokens.append(tk)
                return tokens[::-1]

    def get_function(self, context: Optional[XPathContext], arity: int = 0) -> 'XPathFunction':
        if isinstance(self, XPathFunction):
            func = self
        elif self.symbol in (':', 'Q{') and isinstance(self[1], XPathFunction):
            func = self[1]
        elif self.symbol == '(name)':
            msg = f'unknown function: {self.value}#{arity}'
            raise self.error('XPST0017', msg)
        else:
            func = self.evaluate(context)
            if not isinstance(func, XPathFunction):
                msg = f'unknown function: {func}#{arity}'
                raise self.error('XPST0017', msg)

        max_args = func.max_args
        if func.min_args > arity or max_args is not None and max_args < arity:
            msg = f'unknown function: {func.symbol}#{arity}'
            raise self.error('XPST0017', msg)

        return func

    def validated_value(self, item: Any, cls: Type[Any],
                        promote: Optional[ClassCheckType] = None,
                        index: Optional[int] = None) -> Any:
        """
        Type promotion checking (see "function conversion rules" in XPath 2.0 language definition)
        """
        if isinstance(item, (cls, ValueToken)):
            return item
        elif promote and isinstance(item, promote):
            return cls(item)

        if self.parser.compatibility_mode:
            if issubclass(cls, str):
                return self.string_value(item)
            elif issubclass(cls, float) or issubclass(float, cls):
                return self.number_value(item)

        if issubclass(cls, XPathToken) or self.parser.version == '1.0':
            code = 'XPTY0004'
        else:
            value = self.data_value(item)
            if isinstance(value, cls):
                return value
            elif isinstance(value, AnyURI) and issubclass(cls, str):
                return cls(value)
            elif isinstance(value, UntypedAtomic):
                try:
                    return cls(value)
                except (TypeError, ValueError):
                    pass

            code = 'FOTY0012' if value is None else 'XPTY0004'

        if index is None:
            msg = f"item type is {type(item)!r} instead of {cls!r}"
        else:
            msg = f"{ordinal(index+1)} argument has type {type(item)!r} instead of {cls!r}"
        raise self.error(code, msg)

    def iter_flatten(self, context: Optional[XPathContext] = None) -> Iterator[Any]:

        def _iter_flatten(items: Iterable[Any]) -> Iterator[Any]:
            for item in items:
                if isinstance(item, list):
                    yield from _iter_flatten(item)
                elif isinstance(item, XPathArray):
                    yield from item.iter_flatten(context)
                else:
                    yield item

        yield from _iter_flatten(self.select(context))

    def atomization(self, context: Optional[XPathContext] = None) \
            -> Iterator[AtomicValueType]:
        """
        Helper method for value atomization of a sequence.

        Ref: https://www.w3.org/TR/xpath31/#id-atomization

        :param context: the XPath dynamic context.
        """
        for item in self.iter_flatten(context):
            if isinstance(item, XPathNode):
                try:
                    value = item.typed_value
                except (TypeError, ValueError) as err:
                    raise self.error('XPDY0050', str(err))
                else:
                    if value is None:
                        msg = f"argument node {item!r} does not have a typed value"
                        raise self.error('FOTY0012', msg)
                    elif isinstance(value, list):
                        yield from value
                    else:
                        yield value

            elif isinstance(item, XPathFunction) and not isinstance(item, XPathArray):
                raise self.error('FOTY0013', f"{item.label!r} has no typed value")
            elif isinstance(item, AnyAtomicType):
                yield cast(AtomicValueType, item)
            else:
                msg = f"sequence item {item!r} is not appropriate for the context"
                raise self.error('XPTY0004', msg)

    def get_atomized_operand(self, context: Optional[XPathContext] = None) \
            -> Optional[AtomicValueType]:
        """
        Get the atomized value for an XPath operator.

        :param context: the XPath dynamic context.
        :return: the atomized value of a single length sequence or `None` if the sequence is empty.
        """
        selector = iter(self.atomization(context))
        try:
            value = next(selector)
        except StopIteration:
            return None
        else:
            item = getattr(context, 'item', None)

            try:
                next(selector)
            except StopIteration:
                if isinstance(value, UntypedAtomic):
                    value = str(value)

                if not isinstance(context, XPathSchemaContext) and \
                        item is not None and \
                        self.xsd_types and \
                        isinstance(value, str):

                    xsd_type = self.get_xsd_type(item)
                    if xsd_type is None or xsd_type.name in _XSD_SPECIAL_TYPES:
                        pass
                    else:
                        try:
                            value = xsd_type.decode(value)
                        except (TypeError, ValueError):
                            msg = "Type {!r} is not appropriate for the context"
                            raise self.error('XPTY0004', msg.format(type(value)))

                return value
            else:
                msg = "atomized operand is a sequence of length greater than one"
                raise self.error('XPTY0004', msg)

    def iter_comparison_data(self, context: XPathContext) -> Iterator[OperandsType]:
        """
        Generates comparison data couples for the general comparison of sequences.
        Different sequences maybe generated with an XPath 2.0 parser, depending on
        compatibility mode setting.

        Ref: https://www.w3.org/TR/xpath20/#id-general-comparisons

        :param context: the XPath dynamic context.
        """
        left_values: Any
        right_values: Any

        if self.parser.compatibility_mode:
            left_values = [x for x in self._items[0].atomization(copy(context))]
            right_values = [x for x in self._items[1].atomization(copy(context))]
            # Boolean comparison if one of the results is a single boolean value (1.)
            try:
                if isinstance(left_values[0], bool):
                    if len(left_values) == 1:
                        yield left_values[0], self.boolean_value(right_values)
                        return
                if isinstance(right_values[0], bool):
                    if len(right_values) == 1:
                        yield self.boolean_value(left_values), right_values[0]
                        return
            except IndexError:
                return

            # Converts to float for lesser-greater operators (3.)
            if self.symbol in ('<', '<=', '>', '>='):
                yield from product(map(float, left_values), map(float, right_values))
                return
            elif self.parser.version == '1.0':
                yield from product(left_values, right_values)
                return
        else:
            left_values = self._items[0].atomization(copy(context))
            right_values = self._items[1].atomization(copy(context))

        for values in product(left_values, right_values):
            if any(isinstance(x, bool) for x in values):
                if any(isinstance(x, (str, Integer)) for x in values):
                    msg = "cannot compare {!r} and {!r}"
                    raise TypeError(msg.format(type(values[0]), type(values[1])))
            elif any(isinstance(x, Integer) for x in values) and \
                    any(isinstance(x, str) for x in values):
                msg = "cannot compare {!r} and {!r}"
                raise TypeError(msg.format(type(values[0]), type(values[1])))
            elif any(isinstance(x, float) for x in values):
                if isinstance(values[0], decimal.Decimal):
                    yield float(values[0]), values[1]
                    continue
                elif isinstance(values[1], decimal.Decimal):
                    yield values[0], float(values[1])
                    continue

            yield values

    def select_results(self, context: Optional[XPathContext]) -> Iterator[XPathResultType]:
        """
        Generates formatted XPath results.

        :param context: the XPath dynamic context.
        """
        if context is not None:
            self.parser.check_variables(context.variables)

        for result in self.select(context):
            if not isinstance(result, XPathNode):
                yield result
            elif isinstance(result, NamespaceNode):
                if self.parser.compatibility_mode:
                    yield result.prefix, result.uri
                else:
                    yield result.uri
            elif isinstance(result, DocumentNode):
                if result.is_extended():
                    yield result
                else:
                    yield result.value
            else:
                yield result.value

    def get_results(self, context: XPathContext) -> Union[List[XPathResultType], AtomicValueType]:
        """
        Returns results formatted according to XPath specifications.

        :param context: the XPath dynamic context.
        :return: a list or a simple datatype when the result is a single simple type \
        generated by a literal or function token.
        """
        if context is not None:
            self.parser.check_variables(context.variables)

        results = []
        item = None
        for item in self.select(context):
            if not isinstance(item, XPathNode):
                results.append(item)
            elif isinstance(item, NamespaceNode):
                if self.parser.compatibility_mode:
                    results.append((item.prefix, item.uri))
                else:
                    results.append(item.uri)
            elif isinstance(item, DocumentNode):
                if item.is_extended():
                    results.append(item)
                else:
                    results.append(item.value)
            else:
                results.append(item.value)

        if len(results) == 1 and not isinstance(item, (ElementNode, DocumentNode)):
            if isinstance(item, (bool, int, float, Decimal)):
                return item
            elif self.label in ('function', 'literal'):
                return cast(AtomicValueType, results[0])

        return results

    def get_operands(self, context: XPathContext, cls: Optional[Type[Any]] = None) \
            -> OperandsType:
        """
        Returns the operands for a binary operator. Float arguments are converted
        to decimal if the other argument is a `Decimal` instance.

        :param context: the XPath dynamic context.
        :param cls: if a type is provided performs a type checking on item.
        :return: a couple of values representing the operands. If any operand \
        is not available returns a `(None, None)` couple.
        """
        op1 = self.get_argument(context, cls=cls)
        if op1 is None:
            return None, None
        elif isinstance(op1, ElementNode):
            op1 = self._items[0].data_value(op1)

        op2 = self.get_argument(context, index=1, cls=cls)
        if op2 is None:
            return None, None
        elif isinstance(op2, ElementNode):
            op2 = self._items[1].data_value(op2)

        if isinstance(op1, AbstractDateTime) and isinstance(op2, AbstractDateTime):
            if context is not None and context.timezone is not None:
                if op1.tzinfo is None:
                    op1.tzinfo = context.timezone
                if op2.tzinfo is None:
                    op2.tzinfo = context.timezone
        else:
            if isinstance(op1, UntypedAtomic):
                op1 = self.cast_to_double(op1.value)
                if isinstance(op2, Decimal):
                    return op1, float(op2)
            if isinstance(op2, UntypedAtomic):
                op2 = self.cast_to_double(op2.value)
                if isinstance(op1, Decimal):
                    return float(op1), op2

        if isinstance(op1, float):
            if isinstance(op2, Duration):
                return Decimal(op1), op2
            if isinstance(op2, Decimal):
                return op1, type(op1)(op2)
        if isinstance(op2, float):
            if isinstance(op1, Duration):
                return op1, Decimal(op2)
            if isinstance(op1, Decimal):
                return type(op2)(op1), op2

        return op1, op2

    def get_absolute_uri(self, uri: str,
                         base_uri: Optional[str] = None,
                         as_string: bool = True) -> Union[str, AnyURI]:
        """
        Obtains an absolute URI from the argument and the static context.

        :param uri: a string representing an URI.
        :param base_uri: an alternative base URI, otherwise the base_uri \
        of the static context is used.
        :param as_string: if `True` then returns the URI as a string, otherwise \
        returns the URI as xs:anyURI instance.
        :returns: the argument if it's an absolute URI. Otherwise returns the URI
        obtained by the join o the base_uri of the static context with the
        argument. Returns the argument if the base_uri is `None'.
        """
        if not base_uri:
            base_uri = self.parser.base_uri

        uri_parts: urllib.parse.ParseResult = urllib.parse.urlparse(uri)
        if uri_parts.scheme or uri_parts.netloc or base_uri is None:
            return uri if as_string else AnyURI(uri)

        base_uri_parts: urllib.parse.SplitResult = urllib.parse.urlsplit(base_uri)
        if base_uri_parts.fragment or not base_uri_parts.scheme and \
                not base_uri_parts.netloc and not base_uri_parts.path.startswith('/'):
            raise self.error('FORG0002', '{!r} is not suitable as base URI'.format(base_uri))

        if uri_parts.path.startswith('/') and base_uri_parts.path not in ('', '/'):
            return uri if as_string else AnyURI(uri)

        if as_string:
            return urllib.parse.urljoin(base_uri, uri)
        return AnyURI(urllib.parse.urljoin(base_uri, uri))

    def get_namespace(self, prefix: str) -> str:
        """
        Resolves a prefix to a namespace raising an error (FONS0004) if the
        prefix is not found in the namespace map.
        """
        try:
            return self.parser.namespaces[prefix]
        except KeyError as err:
            msg = 'no namespace found for prefix %r' % str(err)
            raise self.error('FONS0004', msg) from None

    def bind_namespace(self, namespace: str) -> None:
        """
        Bind a token with a namespace. The token has to be a name, a name wildcard,
        a function or a constructor, otherwise a syntax error is raised. Functions
        and constructors must be limited to its namespaces.
        """
        if self.symbol in ('(name)', '*') or isinstance(self, ProxyToken):
            pass
        elif namespace == self.parser.function_namespace:
            if self.label != 'function':
                msg = "a name, a wildcard or a function expected"
                raise self.wrong_syntax(msg, code='XPST0017')
            elif isinstance(self.label, MultiLabel):
                self.label = 'function'
        elif namespace == XSD_NAMESPACE:
            if self.label != 'constructor function':
                msg = "a name, a wildcard or a constructor function expected"
                raise self.wrong_syntax(msg, code='XPST0017')
            elif isinstance(self.label, MultiLabel):
                self.label = 'constructor function'
        elif namespace == XPATH_MATH_FUNCTIONS_NAMESPACE:
            if self.label != 'math function':
                msg = "a name, a wildcard or a math function expected"
                raise self.wrong_syntax(msg, code='XPST0017')
            elif isinstance(self.label, MultiLabel):
                self.label = 'math function'
        elif not self.label.endswith('function'):
            msg = "a name, a wildcard or a function expected"
            raise self.wrong_syntax(msg, code='XPST0017')
        elif self.namespace and namespace != self.namespace:
            msg = "unmatched namespace"
            raise self.wrong_syntax(msg, code='XPST0017')

        self.namespace = namespace

    def adjust_datetime(self, context: XPathContext, cls: Type[AbstractDateTime]) \
            -> Union[List[Any], AbstractDateTime, DayTimeDuration]:
        """
        XSD datetime adjust function helper.

        :param context: the XPath dynamic context.
        :param cls: the XSD datetime subclass to use.
        :return: an empty list if there is only one argument that is the empty sequence \
        or the adjusted XSD datetime instance.
        """
        timezone: Optional[Any]
        item: Optional[AbstractDateTime]
        _item: Union[AbstractDateTime, DayTimeDuration]

        if len(self) == 1:
            item = self.get_argument(context, cls=cls)
            if item is None:
                return []
            timezone = getattr(context, 'timezone', None)
        else:
            item = self.get_argument(context, cls=cls)
            timezone = self.get_argument(context, 1, cls=DayTimeDuration)

            if timezone is not None:
                try:
                    timezone = Timezone.fromduration(timezone)
                except ValueError as err:
                    raise self.error('FODT0003', str(err)) from None
            if item is None:
                return []

        _item = copy(item)
        _tzinfo = _item.tzinfo
        try:
            if _tzinfo is not None and timezone is not None:
                if isinstance(_item, DateTime10):
                    _item += timezone.offset
                elif not isinstance(item, Date10):
                    _item += timezone.offset - _tzinfo.offset
                elif timezone.offset < _tzinfo.offset:
                    _item -= timezone.offset - _tzinfo.offset
                    _item -= DayTimeDuration.fromstring('P1D')
        except OverflowError as err:
            raise self.error('FODT0001', str(err)) from None

        if not isinstance(_item, DayTimeDuration):
            _item.tzinfo = timezone
        return _item

    ###
    # XSD types related methods
    def select_xsd_nodes(self, schema_context: XPathSchemaContext, name: str) \
            -> Iterator[Union[None, AttributeNode, ElementNode]]:
        """
        Selector for XSD nodes (elements, attributes and schemas). If there is
        a match with an attribute or an element the node's type is added to
        matching types of the token. For each matching elements or attributes
        yields tuple nodes containing the node, its type and a compatible value
        for doing static evaluation. For matching schemas yields the original
        instance.

        :param schema_context: an XPathSchemaContext instance.
        :param name: a QName in extended format.
        """
        xsd_node: Any
        xsd_root = cast(Union[XsdSchemaProtocol, XsdElementProtocol],
                        schema_context.root.value)

        for xsd_node in schema_context.iter_children_or_self():
            if xsd_node is None:
                if name == XSD_SCHEMA == schema_context.root.elem.tag:
                    yield None

            elif isinstance(xsd_node, AttributeNode):
                assert not isinstance(xsd_node.value, str)
                if not xsd_node.value.is_matching(name):
                    continue

                if xsd_node.name is not None:
                    self.add_xsd_type(xsd_node)
                else:
                    # node is an XSD attribute wildcard
                    xsd_attribute = xsd_root.maps.attributes.get(name)
                    if xsd_attribute is not None:
                        self.add_xsd_type(xsd_attribute)

                yield xsd_node

            elif isinstance(xsd_node, SchemaElementNode):
                if name == XSD_SCHEMA == xsd_node.elem.tag:
                    # The element is a schema
                    yield xsd_node

                elif xsd_node.elem.is_matching(name, self.parser.namespaces.get('')):
                    if xsd_node.elem.name is not None:
                        self.add_xsd_type(xsd_node)
                    else:
                        # node is an XSD element wildcard
                        xsd_element = xsd_root.maps.elements.get(name)
                        if xsd_element is not None:
                            for child in schema_context.root.children:
                                if child.value is xsd_element:
                                    xsd_node = child
                                    self.add_xsd_type(xsd_node)
                                    break
                            else:
                                self.add_xsd_type(xsd_element)

                    yield xsd_node

    def add_xsd_type(self, item: Any) -> Optional[XsdTypeProtocol]:
        """
        Adds an XSD type association from an item. The association is
        added using the item's name and type.
        """
        if isinstance(item, XPathNode):
            item = item.value

        # TODO: replace with protocol check (XsdAttributeProtocol, XsdElementProtocol)
        if not hasattr(item, 'type') or not hasattr(item, 'xsd_version'):
            return None

        name: str = item.name
        xsd_type: XsdTypeProtocol = item.type

        if self.xsd_types is None:
            self.xsd_types = {name: xsd_type}
        else:
            obj = self.xsd_types.get(name)
            if obj is None:
                self.xsd_types[name] = xsd_type
            elif not isinstance(obj, list):
                if obj is not xsd_type:
                    self.xsd_types[name] = [obj, xsd_type]
            elif xsd_type not in obj:
                obj.append(xsd_type)

        return xsd_type

    def get_xsd_type(self, item: Union[str, PrincipalNodeType]) \
            -> Optional[XsdTypeProtocol]:
        """
        Returns the XSD type associated with an item. Match by item's name
        and XSD validity. Returns `None` if no XSD type is matching.

        :param item: a string or an AttributeNode or an element.
        """
        if not self.xsd_types or isinstance(self.xsd_types, AbstractSchemaProxy):
            return None
        elif isinstance(item, AttributeNode):
            if item.xsd_type is not None:
                return item.xsd_type
            xsd_type = self.xsd_types.get(item.name)
        elif isinstance(item, ElementNode):
            if item.xsd_type is not None:
                return item.xsd_type
            xsd_type = self.xsd_types.get(item.elem.tag)
        elif isinstance(item, str):
            xsd_type = self.xsd_types.get(item)
        else:
            return None

        x: XsdTypeProtocol
        if not xsd_type:
            return None
        elif not isinstance(xsd_type, list):
            return xsd_type
        elif isinstance(item, AttributeNode):
            for x in xsd_type:
                if x.is_valid(item.value):
                    return x
        elif isinstance(item, ElementNode):
            for x in xsd_type:
                if x.is_simple():
                    if x.is_valid(item.elem.text):
                        return x
                elif x.is_valid(item.elem):
                    return x

        return xsd_type[0]

    def get_typed_node(self, item: PrincipalNodeType) -> PrincipalNodeType:
        """
        Returns a typed node if the item is matching an XSD type.

        Ref:
          https://www.w3.org/TR/xpath20/#id-processing-model
          https://www.w3.org/TR/xpath20/#id-static-analysis
          https://www.w3.org/TR/xquery-semantics/

        :param item: an untyped attribute or element.
        :return: a typed AttributeNode/ElementNode if the argument is matching \
        any associated XSD type.
        """
        if isinstance(item, (ElementNode, AttributeNode)) and item.xsd_type is not None:
            return item

        xsd_type = self.get_xsd_type(item)
        if xsd_type is not None and isinstance(item, (ElementNode, AttributeNode)):
            item.xsd_type = xsd_type
        return item

    def cast_to_qname(self, qname: str) -> QName:
        """Cast a prefixed qname string to a QName object."""
        try:
            if ':' not in qname:
                return QName(self.parser.namespaces.get(''), qname.strip())
            pfx, _ = qname.strip().split(':')
            return QName(self.parser.namespaces[pfx], qname)
        except ValueError:
            msg = 'invalid value {!r} for an xs:QName'.format(qname.strip())
            raise self.error('FORG0001', msg)
        except KeyError as err:
            raise self.error('FONS0004', 'no namespace found for prefix {}'.format(err))

    def cast_to_double(self, value: Union[SupportsFloat, str]) -> float:
        """Cast a value to xs:double."""
        try:
            if self.parser.xsd_version == '1.0':
                return cast(float, DoubleProxy10(value))
            return cast(float, DoubleProxy(value))
        except ValueError as err:
            raise self.error('FORG0001', str(err))  # str or UntypedAtomic

    def cast_to_primitive_type(self, obj: Any, type_name: str) -> Any:
        if obj is None or not type_name.startswith('xs:') or type_name.count(':') != 1:
            return obj

        type_name = type_name[3:].rstrip('+*?')
        token = cast(XPathConstructor, self.parser.symbol_table[type_name](self.parser))

        def cast_value(v: Any) -> Any:
            try:
                if isinstance(v, (UntypedAtomic, AnyURI)):
                    return token.cast(v)
                elif isinstance(v, float) or \
                        isinstance(v, xsd10_atomic_types[XSD_DECIMAL]):
                    if type_name in ('double', 'float'):
                        return token.cast(v)
            except (ValueError, TypeError):
                return v
            else:
                return v

        if isinstance(obj, list):
            return [cast_value(x) for x in obj]
        else:
            return cast_value(obj)

    ###
    # XPath data accessors base functions
    def boolean_value(self, obj: Any) -> bool:
        """
        The effective boolean value, as computed by fn:boolean().
        """
        if isinstance(obj, list):
            if not obj:
                return False
            elif isinstance(obj[0], XPathNode):
                return True
            elif len(obj) > 1:
                message = "effective boolean value is not defined for a sequence " \
                          "of two or more items not starting with an XPath node."
                raise self.error('FORG0006', message)
            else:
                obj = obj[0]

        if isinstance(obj, (int, str, UntypedAtomic, AnyURI)):  # Include bool
            return bool(obj)
        elif isinstance(obj, (float, Decimal)):
            return False if math.isnan(obj) else bool(obj)
        elif obj is None:
            return False
        elif isinstance(obj, XPathNode):
            return True
        else:
            message = "effective boolean value is not defined for {!r}.".format(type(obj))
            raise self.error('FORG0006', message)

    def data_value(self, obj: Any) -> Optional[AtomicValueType]:
        """
        The typed value, as computed by fn:data() on each item.
        Returns an instance of UntypedAtomic for untyped data.

        https://www.w3.org/TR/xpath20/#dt-typed-value
        """
        if obj is None:
            return None
        elif isinstance(obj, XPathNode):
            try:
                return obj.typed_value
            except (TypeError, ValueError) as err:
                raise self.error('XPDY0050', str(err))
        elif isinstance(obj, XPathFunction):
            if not isinstance(obj, XPathArray):
                raise self.error('FOTY0013', f"{obj.label!r} has no typed value")

            values = [self.data_value(x) for x in obj.iter_flatten()]
            return values[0] if len(values) == 1 else None
        else:
            return cast(AtomicValueType, obj)

    def string_value(self, obj: Any) -> str:
        """
        The string value, as computed by fn:string().
        """
        if obj is None:
            return ''
        elif isinstance(obj, XPathNode):
            return obj.string_value
        elif isinstance(obj, bool):
            return 'true' if obj else 'false'
        elif isinstance(obj, Decimal):
            value = format(obj, 'f')
            if '.' in value:
                return value.rstrip('0').rstrip('.')
            return value

        elif isinstance(obj, float):
            if math.isnan(obj):
                return 'NaN'
            elif math.isinf(obj):
                return str(obj).upper()

            value = str(obj)
            if '.' in value:
                value = value.rstrip('0').rstrip('.')
            if '+' in value:
                value = value.replace('+', '')
            if 'e' in value:
                return value.upper()
            return value

        elif isinstance(obj, XPathFunction):
            if self.symbol in ('concat', '||'):
                raise self.error('FOTY0013', f"an argument of {self} is a function")
            else:
                raise self.error('FOTY0014', f"{obj.label!r} has no string value")

        return str(obj)

    def number_value(self, obj: Any) -> float:
        """
        The numeric value, as computed by fn:number() on each item. Returns a float value.
        """
        try:
            if isinstance(obj, XPathNode):
                return get_double(self.string_value(obj), self.parser.xsd_version)
            else:
                return get_double(obj, self.parser.xsd_version)
        except (TypeError, ValueError):
            return math.nan

    ###
    # Error handling helpers and shortcuts
    def error(self, code: Union[str, QName],
              message_or_error: Union[None, str, Exception] = None) -> ElementPathError:
        return xpath_error(code, message_or_error, self, self.parser.namespaces)

    def expected(self, *symbols: str,
                 message: Optional[str] = None,
                 code: str = 'XPST0003') -> None:
        if symbols and self.symbol not in symbols:
            raise self.wrong_syntax(message, code)

    def unexpected(self, *symbols: str,
                   message: Optional[str] = None,
                   code: str = 'XPST0003') -> None:
        if not symbols or self.symbol in symbols:
            raise self.wrong_syntax(message, code)

    def wrong_syntax(self, message: Optional[str] = None,  # type: ignore[override]
                     code: str = 'XPST0003') -> ElementPathError:
        if self.label == 'function':
            code = 'XPST0017'

        if message:
            return self.error(code, message)

        error = super(XPathToken, self).wrong_syntax(message)
        return self.error(code, str(error))

    def wrong_value(self, message: Optional[str] = None) -> ElementPathValueError:
        return cast(ElementPathValueError, self.error('FOCA0002', message))

    def wrong_type(self, message: Optional[str] = None) -> ElementPathTypeError:
        return cast(ElementPathTypeError, self.error('FORG0006', message))

    def missing_context(self, message: Optional[str] = None) -> MissingContextError:
        return cast(MissingContextError, self.error('XPDY0002', message))


class XPathAxis(XPathToken):
    pattern = r'\b[^\d\W][\w.\-\xb7\u0300-\u036F\u203F\u2040]*(?=\s*\:\:|\s*\(\:.*\:\)\s*\:\:)'
    label = 'axis'
    reverse_axis: bool = False

    def __str__(self) -> str:
        return f'{self.symbol!r} axis'

    def nud(self) -> 'XPathAxis':
        self.parser.advance('::')
        self.parser.expected_next(
            '(name)', '*', '{', 'Q{', 'text', 'node', 'document-node',
            'comment', 'processing-instruction', 'element', 'attribute',
            'schema-attribute', 'schema-element', 'namespace-node',
        )
        self._items[:] = self.parser.expression(rbp=self.rbp),
        return self

    @property
    def source(self) -> str:
        return '%s::%s' % (self.symbol, self[0].source)


class ValueToken(XPathToken):
    """
    A dummy token for encapsulating a value.
    """
    symbol = '(value)'

    @property
    def source(self) -> str:
        return str(self.value)

    def evaluate(self, context: Optional[XPathContext] = None) -> Any:
        return self.value

    def select(self, context: Optional[XPathContext] = None) -> Iterator[Any]:
        if isinstance(self.value, list):
            yield from self.value
        elif self.value is not None:
            yield self.value


class ProxyToken(XPathToken):
    """
    A proxy token for resolving or calling namespace related functions.

    It cannot handle symbols associated with tokens that are not related
    to namespaces, like operators, type tests or axes. Those tokens can
    have also different binding powers, so handling disambiguation could
    be impracticable.
    """
    label = 'proxy function'

    def nud(self) -> XPathToken:
        lookup_name = f'{{{self.namespace or XPATH_FUNCTIONS_NAMESPACE}}}{self.value}'
        try:
            token = self.parser.symbol_table[lookup_name](self.parser)
        except KeyError:
            if self.namespace == XSD_NAMESPACE:
                msg = f'unknown constructor function {self.symbol!r}'
            else:
                msg = f'unknown function {self.symbol!r}'
            raise self.error('XPST0017', msg) from None
        else:
            if self.parser.next_token.symbol == '#':
                if self.parser.version >= '2.0':
                    return token

            return token.nud()


class XPathFunction(XPathToken):
    """
    A token for processing XPath functions.
    """
    _name: Optional[QName] = None
    pattern = r'(?<!\$)\b[^\d\W][\w.\-\xb7\u0300-\u036F\u203F\u2040]*' \
              r'(?=\s*(?:\(\:.*\:\))?\s*\((?!\:))'

    sequence_types: Tuple[str, ...] = ()
    "Sequence types of arguments and of the return value of the function."

    nargs: NargsType = None
    "Number of arguments: a single value or a couple with None that means unbounded."

    context: Optional[XPathContext] = None
    "Dynamic context associated by function reference evaluation."

    def __init__(self, parser: 'XPath1Parser', nargs: Optional[int] = None) -> None:
        super().__init__(parser)
        if isinstance(nargs, int) and nargs != self.nargs:
            if nargs < 0:
                raise self.error('XPST0017', 'number of arguments must be non negative')
            elif self.nargs is None:
                self.nargs = nargs
            elif isinstance(self.nargs, int):
                raise self.error('XPST0017', 'incongruent number of arguments')
            elif self.nargs[0] > nargs or self.nargs[1] is not None and self.nargs[1] < nargs:
                raise self.error('XPST0017', 'incongruent number of arguments')
            else:
                self.nargs = nargs

    def __repr__(self) -> str:
        if self.nargs == self.__class__.nargs:
            return '%s(%r)' % (self.__class__.__name__, self.parser)
        return '%s(%r, %r)' % (self.__class__.__name__, self.parser, self.nargs)

    def __str__(self) -> str:
        namespace = self.namespace
        if namespace is None or namespace == XPATH_FUNCTIONS_NAMESPACE:
            return f'{self.symbol!r} {self.label}'

        for prefix, uri in self.parser.namespaces.items():
            if uri == namespace:
                return f"'{prefix}:{self.symbol}' {self.label}"
        else:
            return f"'Q{{{namespace}}}{self.symbol}' {self.label}"

    def __call__(self, *args: XPathFunctionArgType,
                 context: Optional[XPathContext] = None) -> Any:
        self.check_arguments_number(len(args))

        # Check provided argument with arity
        if self.nargs is None or self.nargs == len(args):
            pass
        elif isinstance(self.nargs, tuple):
            if len(args) < self.nargs[0]:
                raise self.error('XPTY0004', "missing required arguments")
            elif self.nargs[1] is not None and len(args) > self.nargs[1]:
                raise self.error('XPTY0004', "too many arguments")
        elif self.nargs > len(args):
            raise self.error('XPTY0004', "missing required arguments")
        else:
            raise self.error('XPTY0004', "too many arguments")

        context = copy(context)
        if self.label == 'partial function':
            for value, tk in zip(args, filter(lambda x: x.symbol == '?', self)):
                if isinstance(value, XPathToken) and not isinstance(value, XPathFunction):
                    tk.value = value.evaluate(context)
                else:
                    tk.value = value
        else:
            self.clear()
            for value in args:
                if isinstance(value, XPathToken):
                    self._items.append(value)
                else:
                    self._items.append(ValueToken(self.parser, value=value))

            if any(tk.symbol == '?' and not tk for tk in self._items):
                self.to_partial_function()
                return self

        if isinstance(self.label, MultiLabel):
            # Disambiguate multi-label tokens
            if self.namespace == XSD_NAMESPACE and \
                    'constructor function' in self.label.values:
                self.label = 'constructor function'
            else:
                for label in self.label.values:
                    if label.endswith('function'):
                        self.label = label
                        break

        if self.label == 'partial function':
            result = self._partial_evaluate(context)
        else:
            result = self.evaluate(context)

        return self.validated_result(result)

    def check_arguments_number(self, nargs: int) -> None:
        """Check the number of arguments against function arity."""
        if self.nargs is None or self.nargs == nargs:
            pass
        elif isinstance(self.nargs, tuple):
            if nargs < self.nargs[0]:
                raise self.error('XPTY0004', "missing required arguments")
            elif self.nargs[1] is not None and nargs > self.nargs[1]:
                raise self.error('XPTY0004', "too many arguments")
        elif self.nargs > nargs:
            raise self.error('XPTY0004', "missing required arguments")
        else:
            raise self.error('XPTY0004', "too many arguments")

    def validated_result(self, result: Any) -> Any:
        if isinstance(result, XPathToken) and result.symbol == '?':
            return result
        elif match_sequence_type(result, self.sequence_types[-1], self.parser):
            return result

        _result = self.cast_to_primitive_type(result, self.sequence_types[-1])
        if not match_sequence_type(_result, self.sequence_types[-1], self.parser):
            msg = "{!r} does not match sequence type {}"
            raise self.error('XPTY0004', msg.format(result, self.sequence_types[-1]))
        return _result

    @property
    def source(self) -> str:
        if self.label in ('sequence type', 'kind test', ''):
            return '%s(%s)%s' % (
                self.symbol, ', '.join(item.source for item in self), self.occurrence or ''
            )
        return '%s(%s)' % (self.symbol, ', '.join(item.source for item in self))

    @property
    def name(self) -> Optional[QName]:
        if self._name is not None:
            return self._name
        elif self.symbol == 'function':
            return None
        elif self.label == 'partial function':
            return None
        elif not self.namespace or self.namespace == XPATH_FUNCTIONS_NAMESPACE:
            self._name = QName(XPATH_FUNCTIONS_NAMESPACE, 'fn:%s' % self.symbol)
        elif self.namespace == XSD_NAMESPACE:
            self._name = QName(XSD_NAMESPACE, 'xs:%s' % self.symbol)
        elif self.namespace == XPATH_MATH_FUNCTIONS_NAMESPACE:
            self._name = QName(XPATH_MATH_FUNCTIONS_NAMESPACE, 'math:%s' % self.symbol)
        else:
            for pfx, uri in self.parser.namespaces.items():
                if uri == self.namespace:
                    self._name = QName(uri, f'{pfx}:{self.symbol}')
                    break
            else:
                self._name = QName(self.namespace, self.symbol)

        return self._name

    @property
    def arity(self) -> int:
        if isinstance(self.nargs, int):
            return self.nargs
        return len(self._items)

    @property
    def min_args(self) -> int:
        if isinstance(self.nargs, int):
            return self.nargs
        elif isinstance(self.nargs, (tuple, list)):
            return self.nargs[0]
        else:
            return 0

    @property
    def max_args(self) -> Optional[int]:
        if isinstance(self.nargs, int):
            return self.nargs
        elif isinstance(self.nargs, (tuple, list)):
            return self.nargs[1]
        else:
            return None

    def is_reference(self) -> int:
        if not isinstance(self.nargs, int):
            return False
        return self.nargs and not len(self._items)

    def nud(self) -> 'XPathFunction':
        self.value = None
        if not self.parser.parse_arguments:
            return self

        code = 'XPST0017' if self.label == 'function' else 'XPST0003'
        self.parser.advance('(')
        if self.nargs is None:
            del self._items[:]
            if self.parser.next_token.symbol in (')', '(end)'):
                raise self.error(code, 'at least an argument is required')
            while True:
                self.append(self.parser.expression(5))
                if self.parser.next_token.symbol != ',':
                    break
                self.parser.advance()
        elif self.nargs == 0:
            if self.parser.next_token.symbol != ')':
                if self.parser.next_token.symbol != '(end)':
                    raise self.error(code, '%s has no arguments' % str(self))
                raise self.parser.next_token.wrong_syntax()
            self.parser.advance()
            return self
        else:
            if isinstance(self.nargs, (tuple, list)):
                min_args, max_args = self.nargs
            else:
                min_args = max_args = self.nargs

            k = 0
            while k < min_args:
                if self.parser.next_token.symbol in (')', '(end)'):
                    msg = 'Too few arguments: expected at least %s arguments' % min_args
                    raise self.error('XPST0017', msg if min_args > 1 else msg[:-1])

                self._items[k:] = self.parser.expression(5),
                k += 1
                if k < min_args:
                    if self.parser.next_token.symbol == ')':
                        msg = f'{str(self)}: Too few arguments, expected ' \
                              f'at least {min_args} arguments'
                        raise self.error(code, msg if min_args > 1 else msg[:-1])
                    self.parser.advance(',')

            while max_args is None or k < max_args:
                if self.parser.next_token.symbol == ',':
                    self.parser.advance(',')
                    self._items[k:] = self.parser.expression(5),
                elif k == 0 and self.parser.next_token.symbol != ')':
                    self._items[k:] = self.parser.expression(5),
                else:
                    break  # pragma: no cover
                k += 1

            if self.parser.next_token.symbol == ',':
                msg = 'Too many arguments: expected at most %s arguments' % max_args
                raise self.error(code, msg if max_args != 1 else msg[:-1])

        self.parser.advance(')')
        if any(tk.symbol == '?' and not tk for tk in self._items):
            self.to_partial_function()

        return self

    def match_function_test(self, function_test: Union[str, List[str]],
                            as_argument: bool = False) -> bool:
        """
        Match if function signature satisfies the provided *function_test*.
        For default return type is covariant and arguments are contravariant.
        If *as_argument* is `True` the match is inverted.

        References:
          https://www.w3.org/TR/xpath-31/#id-function-test
          https://www.w3.org/TR/xpath-31/#id-sequencetype-subtype
        """
        if isinstance(function_test, list):
            sequence_types = function_test
        else:
            sequence_types = split_function_test(function_test)
        if not sequence_types or not sequence_types[-1]:
            return False
        elif sequence_types[0] == '*':
            return True

        signature = [x for x in self.sequence_types[:self.arity]]
        signature.append(self.sequence_types[-1])

        if len(sequence_types) != len(signature):
            return False

        if as_argument:
            iterator = zip(sequence_types[:-1], signature[:-1])
        else:
            iterator = zip(signature[:-1], sequence_types[:-1])

        # compare sequence types
        for st1, st2 in iterator:
            if not is_sequence_type_restriction(st1, st2):
                return False
        else:
            st1, st2 = sequence_types[-1], signature[-1]
            return is_sequence_type_restriction(st1, st2)

    def to_partial_function(self) -> None:
        """Convert a function to a partial function."""
        nargs = len([tk and not tk for tk in self._items if tk.symbol == '?'])
        assert nargs, "a partial function requires at least a placeholder token"

        if self.label != 'partial function':
            def evaluate(context: Optional[XPathContext] = None) -> Any:
                return self

            def select(context: Optional[XPathContext] = None) -> Any:
                yield self

            if self.__class__.evaluate is not XPathToken.evaluate:
                setattr(self, '_partial_evaluate', self.evaluate)
            if self.__class__.select is not XPathToken.select:
                setattr(self, '_partial_select', self.select)

            setattr(self, 'evaluate', evaluate)
            setattr(self, 'select', select)

        self._name = None
        self.label = 'partial function'
        self.nargs = nargs

    def _partial_evaluate(self, context: Optional[XPathContext] = None) -> Any:
        return [x for x in self._partial_select(context)]

    def _partial_select(self, context: Optional[XPathContext] = None) -> Iterator[Any]:
        item = self._partial_evaluate(context)
        if item is not None:
            if isinstance(item, list):
                yield from item
            else:
                if context is not None:
                    context.item = item
                yield item


class XPathConstructor(XPathFunction):
    """
    A token for processing XPath 2.0+ constructors.
    """
    @staticmethod
    def cast(value: Any) -> AtomicValueType:
        raise NotImplementedError()


class XPathMap(XPathFunction):
    """
    A token for processing XPath 3.1+ maps. Map instances have the double role of
    tokens and of dictionaries, depending on the way that are created (using a map
    constructor or a function). The map is fully set after the protected attribute
    _map is evaluated from tokens or initialized from arguments.
    """
    symbol = 'map'
    label = 'map'
    pattern = r'(?<!\$)\bmap(?=\s*(?:\(\:.*\:\))?\s*\{(?!\:))'
    _map: Optional[Dict[Optional[AnyAtomicType], Any]] = None
    _values: List[XPathToken]
    _nan_key: Optional[float] = None

    def __init__(self, parser: 'XPath1Parser', items: Optional[Any] = None) -> None:
        super().__init__(parser)
        self._values = []
        if items is not None:
            _items = items.items() if isinstance(items, dict) else items
            _map: Dict[Any, Any] = {}
            for k, v in _items:
                if k is None:
                    raise self.error('XPTY0004', 'missing key value')
                elif isinstance(k, float) and math.isnan(k):
                    if self._nan_key is not None:
                        raise self.error('XQDY0137')
                    self._nan_key, _map[None] = k, v
                    continue
                elif k in _map:
                    raise self.error('XQDY0137')

                if isinstance(v, list):
                    _map[k] = v[0] if len(v) == 1 else v
                else:
                    _map[k] = v

            self._map = _map

    def __repr__(self) -> str:
        return '%s(%r, %r)' % (self.__class__.__name__, self.parser, self._map)

    def __str__(self) -> str:
        if self._map is None:
            return f'not evaluated map constructor with {len(self._items)} entries'
        return f'map{self._map}'

    def __len__(self) -> int:
        if self._map is None:
            return len(self._items)
        return len(self._map)

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, XPathMap):
            if self._map is None or other._map is None:
                raise ElementPathValueError("cannot compare not evaluated maps")
            return self._map == other._map
        return NotImplemented

    def nud(self) -> 'XPathMap':
        self.parser.advance('{')
        del self._items[:]
        if self.parser.next_token.symbol not in ('}', '(end)'):
            while True:
                key = self.parser.expression(5)
                self._items.append(key)
                if self.parser.token.symbol != ':':
                    self.parser.advance(':')
                self._values.append(self.parser.expression(5))

                if self.parser.next_token.symbol != ',':
                    break
                self.parser.advance()

        self.parser.advance('}')
        return self

    @property
    def source(self) -> str:
        if self._map is None:
            items = ', '.join(f'{tk.source}:{tv.source}' for tk, tv in zip(self, self._values))
        else:
            items = ', '.join(f'{k!r}:{v!r}' for k, v in self._map.items())
        return f'map{{{items}}}'

    def evaluate(self, context: Optional[XPathContext] = None) -> 'XPathMap':
        if self._map is not None:
            return self
        return XPathMap(
            parser=self.parser,
            items=(
                (k.get_atomized_operand(context), v.evaluate(context))
                for k, v in zip(self._items, self._values)
            )
        )

    def _evaluate(self, context: Optional[XPathContext] = None) -> Dict[AnyAtomicType, Any]:
        _map: Dict[Any, Any] = {}
        nan_key = None

        for key, value in zip(self._items, self._values):
            k = key.get_atomized_operand(context)
            if k is None:
                raise self.error('XPTY0004', 'missing key value')
            elif isinstance(k, float) and math.isnan(k):
                if nan_key is not None:
                    raise self.error('XQDY0137')
                nan_key, _map[None] = k, value.evaluate(context)
                continue
            elif k in _map:
                raise self.error('XQDY0137')

            v = value.evaluate(context)
            if isinstance(v, list):
                _map[k] = v[0] if len(v) == 1 else v
            else:
                _map[k] = v

        self._nan_key = nan_key
        return cast(Dict[AnyAtomicType, Any], _map)

    def __call__(self, *args: XPathFunctionArgType,
                 context: Optional[XPathContext] = None) -> Any:
        if len(args) == 1 and isinstance(args[0], list) and len(args[0]) == 1:
            args = args[0][0],
        if len(args) != 1 or not isinstance(args[0], AnyAtomicType):
            raise self.error('XPST0003', 'exactly one atomic argument is expected')

        map_dict: Dict[Any, Any]
        key = args[0]
        if self._map is not None:
            map_dict = self._map
        else:
            map_dict = self._evaluate(context)

        try:
            if isinstance(key, float) and math.isnan(key):
                return map_dict[None]
            else:
                return map_dict[key]
        except KeyError:
            return []

    def keys(self, context: Optional[XPathContext] = None) -> List[AnyAtomicType]:
        if self._map is not None:
            keys = [self._nan_key if k is None else k for k in self._map.keys()]
        else:
            keys = [self._nan_key if k is None else k for k in self._evaluate(context).keys()]
        return cast(List[AnyAtomicType], keys)

    def values(self, context: Optional[XPathContext] = None) -> List[Any]:
        if self._map is not None:
            return [v for v in self._map.values()]
        return [v for v in self._evaluate(context).values()]

    def items(self, context: Optional[XPathContext] = None) -> List[Tuple[AnyAtomicType, Any]]:
        _map: Dict[Any, Any]
        if self._map is not None:
            _map = self._map
        else:
            _map = self._evaluate(context)

        return [(self._nan_key, v) if k is None else (k, v) for k, v in _map.items()]

    def match_function_test(self, function_test: Union[str, List[str]],
                            as_argument: bool = False) -> bool:
        if isinstance(function_test, list):
            sequence_types = function_test
        else:
            sequence_types = split_function_test(function_test)

        if not sequence_types or not sequence_types[-1]:
            return False
        elif sequence_types[0] == '*':
            return True
        elif len(sequence_types) != 2:
            return False

        key_st, value_st = sequence_types
        if key_st.endswith(('+', '*')):
            return False
        elif value_st != 'empty-sequence()' and not value_st.endswith(('?', '*')):
            return False
        else:
            return any(match_sequence_type(k, key_st, self.parser, False) and
                       match_sequence_type(v, value_st, self.parser)
                       for k, v in self.items())


class XPathArray(XPathFunction):
    """
    A token for processing XPath 3.1+ arrays.
    """
    symbol = 'array'
    label = 'array'
    pattern = r'(?<!\$)\barray(?=\s*(?:\(\:.*\:\))?\s*\{(?!\:))'
    _array: Optional[List[Any]] = None

    def __init__(self, parser: 'XPath1Parser',
                 items: Optional[Iterable[Any]] = None) -> None:
        if items is not None:
            self._array = [x for x in items]
        super().__init__(parser)

    def __repr__(self) -> str:
        return '%s(%r, %r)' % (self.__class__.__name__, self.parser, self._array)

    def __str__(self) -> str:
        if self._array is not None:
            return str(self._array)
        elif self.symbol == 'array':
            return f'not evaluated curly array constructor with {len(self._items)} items'
        return f'not evaluated square array constructor with {len(self._items)} items'

    def __len__(self) -> int:
        if self._array is None:
            return len(self._items)
        return len(self._array)

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, XPathArray):
            if self._array is None or other._array is None:
                raise ElementPathValueError("cannot compare not evaluated arrays")
            return self._array == other._array
        return NotImplemented

    @property
    def source(self) -> str:
        if self._array is None:
            items = ', '.join(f'{tk.source}' for tk in self)
        else:
            items = ', '.join(f'{v!r}' for v in self._array)
        return f'array{{{items}}}' if self.symbol == 'array' else f'[{items}]'

    def nud(self) -> 'XPathArray':
        self.value = None
        self.parser.advance('{')
        del self._items[:]
        if self.parser.next_token.symbol not in ('}', '(end)'):
            while True:
                self._items.append(self.parser.expression(5))
                if self.parser.next_token.symbol != ',':
                    break
                self.parser.advance()

        self.parser.advance('}')
        return self

    def evaluate(self, context: Optional[XPathContext] = None) -> 'XPathArray':
        if self._array is not None:
            return self
        return XPathArray(self.parser, items=self._evaluate(context))

    def _evaluate(self, context: Optional[XPathContext] = None) -> List[Any]:
        if self.symbol == 'array':
            # A comma in a curly array constructor is the comma operator, not a delimiter.
            items: List[Any] = []
            for tk in self._items:
                items.extend(tk.select(context))
            return items
        else:
            return [tk.evaluate(context) for tk in self._items]

    def __call__(self, *args: XPathFunctionArgType,
                 context: Optional[XPathContext] = None) -> Any:
        if len(args) != 1 or not isinstance(args[0], int):
            raise self.error('XPTY0004', 'exactly one xs:integer argument is expected')

        position = args[0]
        if position <= 0:
            raise self.error('FOAY0001')

        if self._array is not None:
            items = self._array
        else:
            items = self._evaluate(context)

        try:
            return items[position - 1]
        except IndexError:
            raise self.error('FOAY0001')

    def items(self, context: Optional[XPathContext] = None) -> List[Any]:
        if self._array is not None:
            return self._array.copy()
        return self._evaluate(context)

    def iter_flatten(self, context: Optional[XPathContext] = None) -> Iterator[Any]:
        if self._array is not None:
            items = self._array
        else:
            items = self._evaluate(context)

        for item in items:
            if isinstance(item, XPathArray):
                yield from item.iter_flatten(context)
            elif isinstance(item, list):
                yield from item
            else:
                yield item

    def match_function_test(self, function_test: Union[str, List[Any]],
                            as_argument: bool = False) -> bool:
        if isinstance(function_test, list):
            sequence_types = function_test
        else:
            sequence_types = split_function_test(function_test)

        if not sequence_types or not sequence_types[-1]:
            return False
        elif sequence_types[0] == '*':
            return True
        elif len(sequence_types) != 2:
            return False

        index_type, value_type = sequence_types
        if index_type.endswith(('+', '*')):
            return False

        return match_sequence_type(1, index_type) and \
            all(match_sequence_type(v, value_type, self.parser) for v in self.items())
