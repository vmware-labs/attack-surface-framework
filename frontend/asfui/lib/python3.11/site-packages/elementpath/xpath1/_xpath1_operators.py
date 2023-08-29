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
XPath 1.0 implementation - part 2 (operators and expressions)
"""
import math
import decimal
import operator
from copy import copy

from ..datatypes import AnyURI
from ..exceptions import ElementPathKeyError, ElementPathTypeError
from ..helpers import collapse_white_spaces, node_position
from ..datatypes import AbstractDateTime, Duration, DayTimeDuration, \
    YearMonthDuration, NumericProxy, ArithmeticProxy
from ..xpath_context import XPathSchemaContext
from ..namespaces import XMLNS_NAMESPACE, XSD_NAMESPACE
from ..schema_proxy import AbstractSchemaProxy
from ..xpath_nodes import XPathNode, ElementNode, AttributeNode, DocumentNode
from ..xpath_tokens import XPathToken

from .xpath1_parser import XPath1Parser

OPERATORS_MAP = {
    '=': operator.eq,
    '!=': operator.ne,
    '>': operator.gt,
    '>=': operator.ge,
    '<': operator.lt,
    '<=': operator.le,
}

register = XPath1Parser.register
nullary = XPath1Parser.nullary
prefix = XPath1Parser.prefix
infix = XPath1Parser.infix
postfix = XPath1Parser.postfix
method = XPath1Parser.method
function = XPath1Parser.function
axis = XPath1Parser.axis


@method(register('(name)', bp=10, label='literal'))
def nud_name_literal(self):
    if self.parser.next_token.symbol == '::':
        msg = "axis '%s::' not found" % self.value
        if self.parser.compatibility_mode:
            raise self.error('XPST0010', msg)
        raise self.error('XPST0003', msg)
    elif self.parser.next_token.symbol == '(':
        if self.parser.version >= '2.0':
            pass  # XP30+ has led() for '(' operator that can check this
        elif self.namespace == XSD_NAMESPACE:
            raise self.error('XPST0017', 'unknown constructor function {!r}'.format(self.value))
        elif self.namespace or self.value not in self.parser.RESERVED_FUNCTION_NAMES:
            raise self.error('XPST0017', 'unknown function {!r}'.format(self.value))
        else:
            msg = f"{self.value!r} is not allowed as function name"
            raise self.error('XPST0003', msg)

    return self


@method('(name)')
def evaluate_name_literal(self, context=None):
    return [x for x in self.select(context)]


@method('(name)')
def select_name_literal(self, context=None):
    if context is None:
        raise self.missing_context()
    elif isinstance(context, XPathSchemaContext):
        yield from self.select_xsd_nodes(context, self.value)
        return
    else:
        name = self.value
        default_namespace = self.parser.default_namespace

    # With an ElementTree context checks if the token is bound to an XSD type. If not
    # try a match using the element path. If this match fails the xsd_type attribute
    # is set with the schema object to prevent other checks until the schema change.
    if self.xsd_types is self.parser.schema:

        # Untyped selection
        for item in context.iter_children_or_self():
            if item.match_name(name, default_namespace):
                yield item

    elif self.xsd_types is None or isinstance(self.xsd_types, AbstractSchemaProxy):

        # Try to match the type using the item's path
        for item in context.iter_children_or_self():
            if item.match_name(name, default_namespace):

                if item.xsd_type is not None:
                    yield item
                else:
                    xsd_node = self.parser.schema.find(item.path, self.parser.namespaces)
                    if xsd_node is None:
                        self.xsd_types = self.parser.schema
                    elif isinstance(item, AttributeNode):
                        self.xsd_types = {item.name: xsd_node.type}
                    else:
                        self.xsd_types = {item.elem.tag: xsd_node.type}

                    context.item = self.get_typed_node(item)
                    yield context.item

    else:
        # XSD typed selection
        for item in context.iter_children_or_self():
            if item.match_name(name, default_namespace):
                if item.xsd_type is not None:
                    yield item
                else:
                    context.item = self.get_typed_node(item)
                    yield context.item


###
# Prefixed reference (name or function)

class _PrefixedReferenceToken(XPathToken):

    symbol = lookup_name = ':'
    lbp = 95
    rbp = 95

    def __init__(self, parser, value=None):
        super().__init__(parser, value)

        # Change bind powers if it cannot be a namespace related token
        if self.is_spaced():
            self.lbp = self.rbp = 0
        elif self.parser.token.symbol not in ('*', '(name)', 'array'):
            self.lbp = self.rbp = 0

    def __str__(self):
        if len(self) < 2:
            return 'unparsed prefixed reference'
        elif self[1].label.endswith('function'):
            return f"{self.value!r} {self[1].label}"
        elif '*' in self.value:
            return f"{self.value!r} prefixed wildcard"
        else:
            return f"{self.value!r} prefixed name"

    @property
    def source(self) -> str:
        if self.occurrence:
            return ':'.join(tk.source for tk in self) + self.occurrence
        else:
            return ':'.join(tk.source for tk in self)

    def led(self, left):
        version = self.parser.version
        if self.is_spaced():
            if version <= '3.0':
                raise self.wrong_syntax("a QName cannot contains spaces before or after ':'")
            return left

        if version == '1.0':
            left.expected('(name)')
        elif version <= '3.0':
            left.expected('(name)', '*')
        elif left.symbol not in ('(name)', '*'):
            return left

        if not self.parser.next_token.label.endswith('function'):
            self.parser.expected_next('(name)', '*')

        if left.symbol == '(name)':
            try:
                namespace = self.get_namespace(left.value)
            except ElementPathKeyError:
                self.parser.advance()  # Assure there isn't a following incomplete comment
                self[:] = left, self.parser.token
                msg = "prefix {!r} is not declared".format(left.value)
                raise self.error('XPST0081', msg) from None
            else:
                self.parser.next_token.bind_namespace(namespace)
        elif self.parser.next_token.symbol != '(name)':
            raise self.wrong_syntax()

        self[:] = left, self.parser.expression(95)
        if self[1].label.endswith('function'):
            self.value = f'{self[0].value}:{self[1].symbol}'
        else:
            self.value = f'{self[0].value}:{self[1].value}'
        return self

    def evaluate(self, context=None):
        if self[1].label.endswith('function'):
            return self[1].evaluate(context)
        return [x for x in self.select(context)]

    def select(self, context=None):
        if self[1].label.endswith('function'):
            value = self[1].evaluate(context)
            if isinstance(value, list):
                yield from value
            elif value is not None:
                yield value
            return

        if self[0].value == '*':
            name = '*:%s' % self[1].value
        else:
            name = '{%s}%s' % (self.get_namespace(self[0].value), self[1].value)

        if context is None:
            raise self.missing_context()
        elif isinstance(context, XPathSchemaContext):
            yield from self.select_xsd_nodes(context, name)

        elif self.xsd_types is self.parser.schema:
            for item in context.iter_children_or_self():
                if item.match_name(name):
                    yield item

        elif self.xsd_types is None or isinstance(self.xsd_types, AbstractSchemaProxy):
            for item in context.iter_children_or_self():
                if item.match_name(name):
                    assert isinstance(item, (ElementNode, AttributeNode))
                    if item.xsd_type is not None:
                        yield item
                    else:
                        xsd_node = self.parser.schema.find(item.path, self.parser.namespaces)
                        if xsd_node is not None:
                            self.add_xsd_type(xsd_node)
                        else:
                            self.xsd_types = self.parser.schema

                        context.item = self.get_typed_node(item)
                        yield context.item

        else:
            # XSD typed selection
            for item in context.iter_children_or_self():
                if item.match_name(name):
                    assert isinstance(item, (ElementNode, AttributeNode))
                    if item.xsd_type is not None:
                        yield item
                    else:
                        context.item = self.get_typed_node(item)
                        yield context.item


XPath1Parser.symbol_table[':'] = _PrefixedReferenceToken


###
# Namespace URI as in ElementPath
@method('{', bp=95)
def nud_namespace_uri(self):
    if self.parser.strict and self.symbol == '{':
        raise self.wrong_syntax("not allowed symbol if parser has strict=True")

    self.parser.next_token.unexpected('{')
    if self.parser.next_token.symbol == '}':
        namespace = ''
    else:
        namespace = self.parser.next_token.value + self.parser.advance_until('}')
        namespace = collapse_white_spaces(namespace)

    try:
        AnyURI(namespace)
    except ValueError as err:
        msg = f"invalid URI in an EQName: {str(err)}"
        raise self.error('XQST0046', msg) from None

    if namespace == XMLNS_NAMESPACE:
        msg = f"cannot use the URI {XMLNS_NAMESPACE!r}!r in an EQName"
        raise self.error('XQST0070', msg)

    self.parser.advance()
    if not self.parser.next_token.label.endswith('function'):
        self.parser.expected_next('(name)', '*')
    self.parser.next_token.bind_namespace(namespace)

    self[:] = self.parser.symbol_table['(string)'](self.parser, namespace), \
        self.parser.expression(90)

    if self[1].value is None or not self[0].value:
        self.value = self[1].value
    else:
        self.value = '{%s}%s' % (self[0].value, self[1].value)
    return self


@method('{')
def evaluate_namespace_uri(self, context=None):
    if self[1].label.endswith('function'):
        return self[1].evaluate(context)
    return [x for x in self.select(context)]


@method('{')
def select_namespace_uri(self, context=None):
    if self[1].label.endswith('function'):
        yield self[1].evaluate(context)
        return
    elif context is None:
        raise self.missing_context()

    if isinstance(context, XPathSchemaContext):
        yield from self.select_xsd_nodes(context, self.value)

    elif self.xsd_types is None:
        for item in context.iter_children_or_self():
            if item.match_name(self.value):
                yield item
    else:
        # XSD typed selection
        for item in context.iter_children_or_self():
            if item.match_name(self.value):
                assert isinstance(item, (ElementNode, AttributeNode))
                if item.xsd_type is not None:
                    yield item
                else:
                    context.item = self.get_typed_node(item)
                    yield context.item


###
# Variables
@method('$', bp=90)
def nud_variable_reference(self):
    self.parser.expected_next('(name)')
    self[:] = self.parser.expression(rbp=90),
    if ':' in self[0].value:
        raise self[0].wrong_syntax("variable reference requires a simple reference name")
    return self


@method('$')
def evaluate_variable_reference(self, context=None):
    if context is None:
        raise self.missing_context()

    try:
        value = context.variables[self[0].value]
    except KeyError as err:
        raise self.error('XPST0008', 'unknown variable %r' % str(err)) from None
    else:
        return value if value is not None else []


###
# Nullary operators (use only the context)
@method(nullary('*'))
def select_wildcard(self, context=None):
    if self:
        # Product operator
        item = self.evaluate(context)
        if item or not isinstance(item, list):
            if context is not None:
                context.item = item
            yield item
    elif context is None:
        raise self.missing_context()

    # Wildcard literal
    elif isinstance(context, XPathSchemaContext):
        for item in context.iter_children_or_self():
            if item is not None:
                self.add_xsd_type(item)
                yield item

    elif self.xsd_types is None:
        for item in context.iter_children_or_self():
            if item is None:
                pass  # '*' wildcard doesn't match document nodes
            elif context.axis == 'attribute':
                if isinstance(item, AttributeNode):
                    yield item
            elif isinstance(item, ElementNode):
                yield item

    else:
        # XSD typed selection
        for item in context.iter_children_or_self():
            if context.item is not None and context.is_principal_node_kind():
                if isinstance(item, (ElementNode, AttributeNode)) and \
                        item.xsd_type is not None:
                    yield item
                else:
                    context.item = self.get_typed_node(item)
                    yield context.item


@method(nullary('.'))
def select_self_shortcut(self, context=None):
    if context is None:
        raise self.missing_context()

    elif isinstance(context, XPathSchemaContext):
        for item in context.iter_self():
            if isinstance(item, (AttributeNode, ElementNode)):
                if item.is_schema_node():
                    self.add_xsd_type(item)
                elif item is context.root:
                    # item is the schema
                    for xsd_element in item:
                        self.add_xsd_type(xsd_element)
            yield item

    elif self.xsd_types is None:
        for item in context.iter_self():
            if item is not None:
                yield item
            elif isinstance(context.root, DocumentNode):
                yield context.root

    else:
        for item in context.iter_self():
            if item is not None:
                if isinstance(item, (ElementNode, AttributeNode)) and \
                        item.xsd_type is not None:
                    yield item
                else:
                    context.item = self.get_typed_node(item)
                    yield context.item
            elif isinstance(context.root, DocumentNode):
                yield context.root


@method(nullary('..'))
def select_parent_shortcut(self, context=None):
    if context is None:
        raise self.missing_context()
    yield from context.iter_parent()


###
# Logical Operators
@method(infix('or', bp=20))
def evaluate_or_operator(self, context=None):
    return self.boolean_value(self[0].evaluate(copy(context))) or \
        self.boolean_value(self[1].evaluate(copy(context)))


@method(infix('and', bp=25))
def evaluate_and_operator(self, context=None):
    return self.boolean_value(self[0].evaluate(copy(context))) and \
        self.boolean_value(self[1].evaluate(copy(context)))


###
# Comparison operators
@method('=', bp=30)
@method('!=', bp=30)
@method('<', bp=30)
@method('>', bp=30)
@method('<=', bp=30)
@method('>=', bp=30)
def led_comparison_operators(self, left):
    if left.symbol in OPERATORS_MAP:
        raise self.wrong_syntax()
    self[:] = left, self.parser.expression(rbp=30)
    return self


@method('=')
@method('!=')
@method('<')
@method('>')
@method('<=')
@method('>=')
def evaluate_comparison_operators(self, context=None):
    op = OPERATORS_MAP[self.symbol]
    try:
        return any(op(x1, x2) for x1, x2 in self.iter_comparison_data(context))
    except ElementPathTypeError:
        raise
    except TypeError as err:
        raise self.error('XPTY0004', err) from None
    except ValueError as err:
        raise self.error('FORG0001', err) from None


###
# Numerical operators
@method(infix('+', bp=40))
def evaluate_plus_operator(self, context=None):
    if len(self) == 1:
        arg = self.get_argument(context, cls=NumericProxy)
        return [] if arg is None else +arg
    else:
        op1, op2 = self.get_operands(context, cls=ArithmeticProxy)
        if op1 is None:
            return []

        try:
            return op1 + op2
        except TypeError as err:
            raise self.error('XPTY0004', err) from None
        except OverflowError as err:
            if isinstance(op1, AbstractDateTime):
                raise self.error('FODT0001', err) from None
            elif isinstance(op1, Duration):
                raise self.error('FODT0002', err) from None
            else:
                raise self.error('FOAR0002', err) from None


@method(infix('-', bp=40))
def evaluate_minus_operator(self, context=None):
    if len(self) == 1:
        arg = self.get_argument(context, cls=NumericProxy)
        return [] if arg is None else -arg
    else:
        op1, op2 = self.get_operands(context, cls=ArithmeticProxy)
        if op1 is None:
            return []

        try:
            return op1 - op2
        except TypeError as err:
            raise self.error('XPTY0004', err) from None
        except OverflowError as err:
            if isinstance(op1, AbstractDateTime):
                raise self.error('FODT0001', err) from None
            elif isinstance(op1, Duration):
                raise self.error('FODT0002', err) from None
            else:
                raise self.error('FOAR0002', err) from None


@method('+')
@method('-')
def nud_plus_minus_operators(self):
    self[:] = self.parser.expression(rbp=70),
    return self


@method(infix('*', bp=45))
def evaluate_multiply_operator(self, context=None):
    if self:
        op1, op2 = self.get_operands(context, cls=ArithmeticProxy)
        if op1 is None:
            return []
        try:
            if isinstance(op2, (YearMonthDuration, DayTimeDuration)):
                return op2 * op1
            return op1 * op2
        except TypeError as err:
            if isinstance(op1, (float, decimal.Decimal)):
                if math.isnan(op1):
                    raise self.error('FOCA0005') from None
                elif math.isinf(op1):
                    raise self.error('FODT0002') from None

            if isinstance(op2, (float, decimal.Decimal)):
                if math.isnan(op2):
                    raise self.error('FOCA0005') from None
                elif math.isinf(op2):
                    raise self.error('FODT0002') from None

            raise self.error('XPTY0004', err) from None
        except ValueError as err:
            raise self.error('FOCA0005', err) from None
        except OverflowError as err:
            if isinstance(op1, AbstractDateTime):
                raise self.error('FODT0001', err) from None
            elif isinstance(op1, Duration):
                raise self.error('FODT0002', err) from None
            else:
                raise self.error('FOAR0002', err) from None
    else:
        # This is not a multiplication operator but a wildcard select statement
        return [x for x in self.select(context)]


@method(infix('div', bp=45))
def evaluate_div_operator(self, context=None):
    dividend, divisor = self.get_operands(context, cls=ArithmeticProxy)
    if dividend is None:
        return []
    elif divisor != 0:
        try:
            if isinstance(dividend, int) and isinstance(divisor, int):
                return decimal.Decimal(dividend) / decimal.Decimal(divisor)
            return dividend / divisor
        except TypeError as err:
            raise self.error('XPTY0004', err) from None
        except ValueError as err:
            raise self.error('FOCA0005', err) from None
        except OverflowError as err:
            raise self.error('FOAR0002', err) from None
        except (ZeroDivisionError, decimal.DivisionByZero):
            raise self.error('FOAR0001') from None

    elif isinstance(dividend, AbstractDateTime):
        raise self.error('FODT0001')
    elif isinstance(dividend, Duration):
        raise self.error('FODT0002')
    elif not self.parser.compatibility_mode and \
            isinstance(dividend, (int, decimal.Decimal)) and \
            isinstance(divisor, (int, decimal.Decimal)):
        raise self.error('FOAR0001')
    elif dividend == 0:
        return math.nan
    elif dividend > 0:
        return float('-inf') if str(divisor).startswith('-') else float('inf')
    else:
        return float('inf') if str(divisor).startswith('-') else float('-inf')


@method(infix('mod', bp=45))
def evaluate_mod_operator(self, context=None):
    op1, op2 = self.get_operands(context, cls=NumericProxy)
    if op1 is None:
        return []
    elif op2 == 0 and isinstance(op2, float):
        return math.nan
    elif math.isinf(op2) and not math.isinf(op1) and op1 != 0:
        return op1 if self.parser.version != '1.0' else math.nan

    try:
        if isinstance(op1, int) and isinstance(op2, int):
            return op1 % op2 if op1 * op2 >= 0 else -(abs(op1) % op2)
        return op1 % op2
    except TypeError as err:
        raise self.error('FORG0006', err) from None
    except (ZeroDivisionError, decimal.InvalidOperation):
        raise self.error('FOAR0001') from None


# Resolve the intrinsic ambiguity of some infix operators
@method('or')
@method('and')
@method('div')
@method('mod')
def nud_disambiguation_of_infix_operators(self):
    return self.as_name()


###
# Union expressions
@method('|', bp=50)
def led_union_operator(self, left):
    self.cut_and_sort = True
    if left.symbol in ('|', 'union'):
        left.cut_and_sort = False
    self[:] = left, self.parser.expression(rbp=50)
    return self


@method('|')
def select_union_operator(self, context=None):
    if context is None:
        raise self.missing_context()

    results = {item for k in range(2) for item in self[k].select(copy(context))}
    if any(not isinstance(x, XPathNode) for x in results):
        raise self.error('XPTY0004', 'only XPath nodes are allowed')
    elif not self.cut_and_sort:
        yield from results
    else:
        yield from sorted(results, key=node_position)


###
# Path expressions
@method('//', bp=75)
def nud_descendant_path(self):
    if self.parser.next_token.label not in self.parser.PATH_STEP_LABELS:
        self.parser.expected_next(*self.parser.PATH_STEP_SYMBOLS)

    self[:] = self.parser.expression(75),
    return self


@method('/', bp=75)
def nud_child_path(self):
    if self.parser.next_token.label not in self.parser.PATH_STEP_LABELS:
        try:
            self.parser.expected_next(*self.parser.PATH_STEP_SYMBOLS)
        except SyntaxError:
            return self

    self[:] = self.parser.expression(75),
    return self


@method('//')
@method('/')
def led_child_or_descendant_path(self, left):
    if left.symbol in ('/', '//', ':', '[', '$'):
        pass
    elif left.label not in self.parser.PATH_STEP_LABELS and \
            left.symbol not in self.parser.PATH_STEP_SYMBOLS:
        raise self.wrong_syntax()

    if self.parser.next_token.label not in self.parser.PATH_STEP_LABELS:
        self.parser.expected_next(*self.parser.PATH_STEP_SYMBOLS)

    self[:] = left, self.parser.expression(75)
    return self


@method('/')
def select_child_path(self, context=None):
    """
    Child path expression. Selects child:: axis as default (when bind to '*' or '(name)').
    """
    if context is None:
        raise self.missing_context()
    elif not self:
        if isinstance(context.root, DocumentNode):
            yield context.root
    elif len(self) == 1:
        if context.item is context.root and context.item.parent is not None:
            return  # A rooted subtree -> document root produce []
        elif not isinstance(context, XPathSchemaContext):
            context.item = None
        else:
            context.item = context.root
        yield from self[0].select(context)
    else:
        items = set()
        for _ in context.inner_focus_select(self[0]):
            if not isinstance(context.item, XPathNode):
                msg = f"Intermediate step contains an atomic value {context.item!r}"
                raise self.error('XPTY0019', msg)

            for result in self[1].select(context):
                if not isinstance(result, XPathNode):
                    yield result
                elif result in items:
                    pass
                elif isinstance(result, ElementNode):
                    if result.elem not in items:
                        items.add(result)
                        yield result
                else:
                    items.add(result)
                    yield result
                    if isinstance(context, XPathSchemaContext):
                        self[1].add_xsd_type(result)


@method('//')
def select_descendant_path(self, context=None):
    """Operator '//' is a short equivalent to /descendant-or-self::node()/"""
    if context is None:
        raise self.missing_context()
    elif len(self) == 2:
        items = set()
        for _ in context.inner_focus_select(self[0]):
            if not isinstance(context.item, XPathNode):
                raise self.error('XPTY0019')

            for _ in context.iter_descendants():
                for result in self[1].select(context):
                    if not isinstance(result, XPathNode):
                        yield result
                    elif result in items:
                        pass
                    elif isinstance(result, ElementNode):
                        if result.elem not in items:
                            items.add(result)
                            yield result
                    else:
                        items.add(result)
                        yield result
                        if isinstance(context, XPathSchemaContext):
                            self[1].add_xsd_type(result)

    else:
        if context.item is context.root and context.item.parent is not None:
            return  # A rooted subtree -> document root produce []
        elif not isinstance(context, XPathSchemaContext):
            context.item = None
        else:
            context.item = context.root

        items = set()
        for _ in context.iter_descendants():
            for result in self[0].select(context):
                if not isinstance(result, XPathNode):
                    items.add(result)
                elif result in items:
                    pass
                elif isinstance(result, ElementNode):
                    if result.elem not in items:
                        items.add(result)
                else:
                    items.add(result)
                    if isinstance(context, XPathSchemaContext):
                        self[0].add_xsd_type(result)

        yield from sorted(items, key=node_position)


###
# Predicate filters
@method('[', bp=80)
def led_predicate(self, left):
    self[:] = left, self.parser.expression()
    self.parser.advance(']')
    return self


@method('[')
def select_predicate(self, context=None):
    if context is None:
        raise self.missing_context()

    for _ in context.inner_focus_select(self[0]):
        if (self[1].label in ('axis', 'kind test') or self[1].symbol == '..') \
                and not isinstance(context.item, XPathNode):
            raise self.error('XPTY0020')
        elif False and isinstance(context, XPathSchemaContext):
            yield context.item
            continue

        predicate = [x for x in self[1].select(copy(context))]
        if len(predicate) == 1 and isinstance(predicate[0], NumericProxy):
            if context.position == predicate[0]:
                yield context.item
        elif self.boolean_value(predicate):
            yield context.item


###
# Parenthesized expressions
@method('(', bp=100)
def nud_parenthesized_expr(self):
    self[:] = self.parser.expression(),
    self.parser.advance(')')
    return self


@method('(')
def evaluate_parenthesized_expr(self, context=None):
    return self[0].evaluate(context)


@method('(')
def select_parenthesized_expr(self, context=None):
    return self[0].select(context)

# XPath 1.0 definitions continue into module xpath1_functions
