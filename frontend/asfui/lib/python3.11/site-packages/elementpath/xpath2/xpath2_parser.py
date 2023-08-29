#
# Copyright (c), 2018-2021, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
"""
XPath 2.0 implementation - part 1 (parser class and symbols)
"""
from abc import ABCMeta
import locale
from collections.abc import MutableSequence
from urllib.parse import urlparse
from typing import cast, Any, Callable, ClassVar, Dict, List, \
    MutableMapping, Optional, Tuple, Type, Union

from ..helpers import upper_camel_case, is_ncname, ordinal
from ..exceptions import ElementPathError, ElementPathTypeError, \
    ElementPathValueError, MissingContextError, xpath_error
from ..namespaces import NamespacesType, XSD_NAMESPACE, XML_NAMESPACE, \
    XPATH_FUNCTIONS_NAMESPACE, XQT_ERRORS_NAMESPACE, \
    XSD_NOTATION, XSD_ANY_ATOMIC_TYPE, get_prefixed_name
from ..collations import UNICODE_COLLATION_BASE_URI, UNICODE_CODEPOINT_COLLATION
from ..datatypes import UntypedAtomic, AtomicValueType, QName
from ..xpath_tokens import NargsType, XPathToken, ProxyToken, XPathFunction, XPathConstructor
from ..xpath_context import XPathContext
from ..sequence_types import is_sequence_type, match_sequence_type
from ..schema_proxy import AbstractSchemaProxy
from ..xpath1 import XPath1Parser


class XPath2Parser(XPath1Parser):
    """
    XPath 2.0 expression parser class. This is the default parser used by XPath selectors.
    A parser instance represents also the XPath static context. With *variable_types* you
    can pass a dictionary with the types of the in-scope variables.
    Provide a *namespaces* dictionary argument for mapping namespace prefixes to URI inside
    expressions. If *strict* is set to `False` the parser enables also the parsing of QNames,
    like the ElementPath library. There are some additional XPath 2.0 related arguments.

    :param namespaces: a dictionary with mapping from namespace prefixes into URIs.
    :param variable_types: a dictionary with the static context's in-scope variable \
    types. It defines the associations between variables and static types.
    :param strict: if strict mode is `False` the parser enables parsing of QNames, \
    like the ElementPath library. Default is `True`.
    :param compatibility_mode: if set to `True` the parser instance works with \
    XPath 1.0 compatibility rules.
    :param default_namespace: the default namespace to apply to unprefixed names. \
    For default no namespace is applied (empty namespace '').
    :param function_namespace: the default namespace to apply to unprefixed function \
    names. For default the namespace "http://www.w3.org/2005/xpath-functions" is used.
    :param schema: the schema proxy class or instance to use for types, attributes and \
    elements lookups. If an `AbstractSchemaProxy` subclass is provided then a schema \
    proxy instance is built without the optional argument, that involves a mapping of \
    only XSD builtin types. If it's not provided the XPath 2.0 schema's related \
    expressions cannot be used.
    :param base_uri: an absolute URI maybe provided, used when necessary in the \
    resolution of relative URIs.
    :param default_collation: the default string collation to use. If not set the \
    environment's default locale setting is used.
    :param document_types: statically known documents, that is a dictionary from \
    absolute URIs onto types. Used for type check when calling the *fn:doc* function \
    with a sequence of URIs. The default type of a document is 'document-node()'.
    :param collection_types: statically known collections, that is a dictionary from \
    absolute URIs onto types. Used for type check when calling the *fn:collection* \
    function with a sequence of URIs. The default type of a collection is 'node()*'.
    :param default_collection_type: this is the type of the sequence of nodes that \
    would result from calling the *fn:collection* function with no arguments. \
    Default is 'node()*'.
    """
    version = '2.0'
    default_collation = UNICODE_CODEPOINT_COLLATION

    DEFAULT_NAMESPACES: ClassVar[Dict[str, str]] = {
        'xml': XML_NAMESPACE,
        'xs': XSD_NAMESPACE,
        'fn': XPATH_FUNCTIONS_NAMESPACE,
        'err': XQT_ERRORS_NAMESPACE
    }

    PATH_STEP_LABELS = ('axis', 'function', 'kind test')
    PATH_STEP_SYMBOLS = {
        '(integer)', '(string)', '(float)', '(decimal)', '(name)', '*', '@', '..', '.', '(', '{'
    }

    # https://www.w3.org/TR/xpath20/#id-reserved-fn-names
    RESERVED_FUNCTION_NAMES = {
        'attribute', 'comment', 'document-node', 'element', 'empty-sequence',
        'if', 'item', 'node', 'processing-instruction', 'schema-attribute',
        'schema-element', 'text', 'typeswitch',
    }

    function_signatures: Dict[Tuple[QName, int], str] = XPath1Parser.function_signatures.copy()
    namespaces: Dict[str, str]
    token: XPathToken
    next_token: XPathToken

    @staticmethod
    def tracer(trace_data: str) -> None:
        """Trace data collector"""

    def __init__(self, namespaces: Optional[NamespacesType] = None,
                 strict: bool = True,
                 compatibility_mode: bool = False,
                 default_collation: Optional[str] = None,
                 default_namespace: Optional[str] = None,
                 function_namespace: Optional[str] = None,
                 xsd_version: Optional[str] = None,
                 schema: Optional[AbstractSchemaProxy] = None,
                 base_uri: Optional[str] = None,
                 variable_types: Optional[Dict[str, str]] = None,
                 document_types: Optional[Dict[str, str]] = None,
                 collection_types: Optional[Dict[str, str]] = None,
                 default_collection_type: str = 'node()*') -> None:

        super(XPath2Parser, self).__init__(namespaces, strict)
        self.compatibility_mode = compatibility_mode

        if default_collation is not None:
            self.default_collation = default_collation
        else:
            # Obtain the current collation locale using setlocale() with `None`.
            # Consider only configured UTF-8 encodings, otherwise keep Unicode
            # Codepoint Collation.
            _locale = locale.setlocale(locale.LC_COLLATE, None)
            if '.' in _locale:
                language_code, encoding = _locale.split('.')
                if encoding.lower() == 'utf-8':
                    self.default_collation = f'{UNICODE_COLLATION_BASE_URI}?lang={language_code}'

        self._xsd_version = xsd_version if xsd_version is not None else '1.0'

        if default_namespace is not None:
            self.default_namespace = self.namespaces[''] = default_namespace
        else:
            self.default_namespace = self.namespaces.get('', '')

        if function_namespace is not None:
            self.function_namespace = function_namespace

        if schema is None:
            pass
        elif not isinstance(schema, AbstractSchemaProxy):
            msg = "argument 'schema' must be an instance of AbstractSchemaProxy"
            raise ElementPathTypeError(msg)
        else:
            schema.bind_parser(self)

        if not variable_types:
            self.variable_types = {}
        elif all(is_sequence_type(v, self) for v in variable_types.values()):
            self.variable_types = variable_types.copy()
        else:
            raise ElementPathValueError('invalid sequence type for in-scope variable types')

        self.base_uri = None if base_uri is None else urlparse(base_uri).geturl()

        if document_types:
            if any(not is_sequence_type(v, self) for v in document_types.values()):
                raise ElementPathValueError('invalid sequence type in document_types argument')
        self.document_types = document_types

        if collection_types:
            if any(not is_sequence_type(v, self) for v in collection_types.values()):
                raise ElementPathValueError('invalid sequence type in collection_types argument')
        self.collection_types = collection_types

        if not is_sequence_type(default_collection_type, self):
            raise ElementPathValueError('invalid sequence type for '
                                        'default_collection_type argument')
        self.default_collection_type = default_collection_type

    def __repr__(self) -> str:
        args = []
        if self.compatibility_mode:
            args.append('compatibility_mode=True')
        if self.default_collation != UNICODE_CODEPOINT_COLLATION:
            args.append(f'default_collation={self.default_collation!r}')
        if self.function_namespace != XPATH_FUNCTIONS_NAMESPACE:
            args.append(f'function_namespace={self.function_namespace!r}')
        if self._xsd_version != '1.0':
            args.append(f'xsd_version={self._xsd_version!r}')
        if self.schema is not None:
            args.append(f'schema={self.schema!r}')
        if self.base_uri is not None:
            args.append(f'base_uri={self.base_uri!r}')
        if self.variable_types:
            args.append(f'variable_types={self.variable_types!r}')
        if self.document_types:
            args.append(f'document_types={self.document_types!r}')
        if self.collection_types:
            args.append(f'collection_types={self.collection_types!r}')
        if self.default_collection_type != 'node()*':
            args.append(f'default_collection_type={self.default_collection_type!r}')
        if not args:
            return super().__repr__()

        repr_string = super().__repr__()[:-1]
        if repr_string.endswith('('):
            return f"{repr_string}{', '.join(args)})"
        return f"{repr_string}, {', '.join(args)})"

    def __getstate__(self) -> Dict[str, Any]:
        state = self.__dict__.copy()
        state.pop('symbol_table', None)
        state.pop('tokenizer', None)
        return state

    @property
    def xsd_version(self) -> str:
        if self.schema is None:
            return self._xsd_version

        try:
            return self.schema.xsd_version
        except (AttributeError, NotImplementedError):
            return self._xsd_version

    def advance(self, *symbols: str,  message: Optional[str] = None) -> XPathToken:
        super(XPath2Parser, self).advance(*symbols, message=message)

        if self.next_token.symbol == '(:':
            # Parses and consumes an XPath 2.0 comment. A comment is delimited
            # by symbols '(:' and ':)' and can be nested. The current token is
            # saved and restored after parsing the entire comment. Comments
            # cannot be inside a prefixed name ':' specification.
            self.token.unexpected(':')
            token = self.token

            comment_level = 1
            while comment_level:
                self.advance_until('(:', ':)')
                if self.next_token.symbol == ':)':
                    comment_level -= 1
                else:
                    comment_level += 1
            self.advance(':)')

            self.next_token.unexpected(':')
            self.token = token

        return self.token

    @classmethod
    def constructor(cls, symbol: str, bp: int = 90, nargs: NargsType = 1,
                    sequence_types: Union[Tuple[()], Tuple[str, ...], List[str]] = (),
                    label: Union[str, Tuple[str, ...]] = 'constructor function') \
            -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Creates a constructor token class."""
        def nud_(self: XPathConstructor) -> XPathConstructor:
            try:
                self.parser.advance('(')
                self[0:] = self.parser.expression(5),
                if self.parser.next_token.symbol == ',':
                    msg = 'Too many arguments: expected at most 1 argument'
                    raise self.error('XPST0017', msg)
                self.parser.advance(')')
                self.value = None
            except SyntaxError:
                raise self.error('XPST0017') from None

            if self[0].symbol == '?':
                self.to_partial_function()
            return self

        def evaluate_(self: XPathConstructor, context: Optional[XPathContext] = None) \
                -> Union[List[None], AtomicValueType]:
            if self.context is not None:
                context = self.context

            arg = self.data_value(self.get_argument(context))
            if arg is None:
                return []
            elif arg == '?' and self[0].symbol == '?':
                raise self.error('XPTY0004', "cannot evaluate a partial function")

            try:
                if isinstance(arg, UntypedAtomic):
                    return self.cast(arg.value)
                return self.cast(arg)
            except ElementPathError:
                raise
            except (TypeError, ValueError) as err:
                raise self.error('FORG0001', err) from None

        if not sequence_types:
            assert nargs == 1
            sequence_types = ('xs:anyAtomicType?', 'xs:%s?' % symbol)

        token_class = cls.register(symbol, nargs=nargs, sequence_types=sequence_types,
                                   label=label, bases=(XPathConstructor,), lbp=bp, rbp=bp,
                                   nud=nud_, evaluate=evaluate_)

        def bind(func: Callable[..., Any]) -> Callable[..., Any]:
            method_name = func.__name__.partition('_')[0]
            if method_name != 'cast':
                raise ValueError("The function name must be 'cast' or starts with 'cast_'")
            setattr(token_class, method_name, func)
            return func
        return bind

    def schema_constructor(self, atomic_type_name: str, bp: int = 90) \
            -> Type[XPathFunction]:
        """Registers a token class for a schema atomic type constructor function."""
        if atomic_type_name in (XSD_ANY_ATOMIC_TYPE, XSD_NOTATION):
            raise xpath_error('XPST0080')

        def nud_(self_: XPathFunction) -> XPathFunction:
            self_.parser.advance('(')
            self_[0:] = self_.parser.expression(5),
            self_.parser.advance(')')

            try:
                self_.value = self_.evaluate()  # Static context evaluation
            except MissingContextError:
                self_.value = None
            return self_

        def evaluate_(self_: XPathFunction, context: Optional[XPathContext] = None) \
                -> Union[List[None], AtomicValueType]:
            arg = self_.get_argument(context)
            if arg is None or self_.parser.schema is None:
                return []

            value = self_.string_value(arg)
            try:
                return self_.parser.schema.cast_as(value, atomic_type_name)
            except (TypeError, ValueError) as err:
                raise self_.error('FORG0001', err)

        symbol = get_prefixed_name(atomic_type_name, self.namespaces)
        token_class_name = "_%sConstructorFunction" % symbol.replace(':', '_')
        kwargs = {
            'symbol': symbol,
            'nargs': 1,
            'label': 'constructor function',
            'pattern': r'\b%s(?=\s*\(|\s*\(\:.*\:\)\()' % symbol,
            'lbp': bp,
            'rbp': bp,
            'nud': nud_,
            'evaluate': evaluate_,
            '__module__': self.__module__,
            '__qualname__': token_class_name,
            '__return__': None
        }
        token_class = cast(
            Type[XPathFunction], ABCMeta(token_class_name, (XPathFunction,), kwargs)
        )
        MutableSequence.register(token_class)

        if self.symbol_table is self.__class__.symbol_table:
            self.symbol_table = dict(self.__class__.symbol_table)
        self.symbol_table[symbol] = token_class
        self.tokenizer = None

        return token_class

    def external_function(self,
                          callback: Callable[..., Any],
                          name: Optional[str] = None,
                          prefix: Optional[str] = None,
                          sequence_types: Tuple[str, ...] = (),
                          bp: int = 90) -> Type[XPathFunction]:
        """Registers a token class for an external function."""
        import inspect

        symbol = name or callback.__name__
        if not is_ncname(symbol):
            raise ElementPathValueError(f'{symbol!r} is not a name')
        elif symbol in self.RESERVED_FUNCTION_NAMES:
            raise ElementPathValueError(f'{symbol!r} is a reserved function name')

        nargs: NargsType
        spec = inspect.getfullargspec(callback)
        if spec.varargs is not None:
            if spec.args:
                nargs = len(spec.args), None
            else:
                nargs = None
        elif spec.defaults is None:
            nargs = len(spec.args)
        else:
            nargs = len(spec.args) - len(spec.defaults), len(spec.args)

        if prefix:
            namespace = self.namespaces[prefix]
            qname = QName(namespace, f'{prefix}:{symbol}')
        else:
            namespace = XPATH_FUNCTIONS_NAMESPACE
            qname = QName(XPATH_FUNCTIONS_NAMESPACE, f'fn:{symbol}')

        class_name = f'{upper_camel_case(qname.qname)}ExternalFunction'
        lookup_name = qname.expanded_name

        if self.symbol_table is self.__class__.symbol_table:
            self.symbol_table = dict(self.__class__.symbol_table)

        if lookup_name in self.symbol_table:
            msg = f'function {qname.qname!r} is already registered'
            raise ElementPathValueError(msg)
        elif symbol not in self.symbol_table or \
                not issubclass(self.symbol_table[symbol], ProxyToken):

            if symbol in self.symbol_table:
                token_cls = self.symbol_table[symbol]
                if not issubclass(token_cls, XPathFunction) \
                        or token_cls.label == 'kind test':
                    msg = f'{symbol!r} name collides with {token_cls!r}'
                    raise ElementPathValueError(msg)
                if namespace == token_cls.namespace:
                    msg = f'function {qname.qname!r} is already registered'
                    raise ElementPathValueError(msg)

                # Copy the token class before register the proxy token
                self.symbol_table[f'{{{token_cls.namespace}}}{symbol}'] = token_cls

            proxy_class_name = f'{upper_camel_case(qname.local_name)}ProxyToken'
            kwargs = {
                'class_name': proxy_class_name,
                'symbol': symbol,
                'lbp': bp,
                'rbp': bp,
                '__module__': self.__module__,
                '__qualname__': proxy_class_name,
                '__return__': None
            }
            proxy_class = cast(
                Type[ProxyToken], ABCMeta(class_name, (ProxyToken,), kwargs)
            )
            MutableSequence.register(proxy_class)
            self.symbol_table[symbol] = proxy_class

        def evaluate_external_function(self_: XPathFunction,
                                       context: Optional[XPathContext] = None) -> Any:
            args = []
            for k in range(len(self_)):
                arg = self_.get_argument(context, index=k)
                args.append(arg)

            if sequence_types:
                for k, (arg, st) in enumerate(zip(args, sequence_types), start=1):
                    if not match_sequence_type(arg, st, self):
                        msg_ = f"{ordinal(k)} argument does not match sequence type {st!r}"
                        raise xpath_error('XPDY0050', msg_)

                result = callback(*args)
                if not match_sequence_type(result, sequence_types[-1], self):
                    msg_ = f"Result does not match sequence type {sequence_types[-1]!r}"
                    raise xpath_error('XPDY0050', msg_)
                return result

            return callback(*args)

        kwargs = {
            'class_name': class_name,
            'symbol': symbol,
            'namespace': namespace,
            'label': 'external function',
            'nargs': nargs,
            'lbp': bp,
            'rbp': bp,
            'evaluate': evaluate_external_function,
            '__module__': self.__module__,
            '__qualname__': class_name,
            '__return__': None
        }
        if sequence_types:
            # Register function signature(s)
            kwargs['sequence_types'] = sequence_types
            if self.function_signatures is self.__class__.function_signatures:
                self.function_signatures = dict(self.__class__.function_signatures)

            if nargs is None:
                pass  # pragma: no cover
            elif isinstance(nargs, int):
                assert len(sequence_types) == nargs + 1
                self.function_signatures[(qname, nargs)] = 'function({}) as {}'.format(
                    ', '.join(sequence_types[:-1]), sequence_types[-1]
                )
            elif nargs[1] is None:
                assert len(sequence_types) == nargs[0] + 1
                self.function_signatures[(qname, nargs[0])] = 'function({}, ...) as {}'.format(
                    ', '.join(sequence_types[:-1]), sequence_types[-1]
                )
            else:
                assert len(sequence_types) == nargs[1] + 1
                for arity in range(nargs[0], nargs[1] + 1):
                    self.function_signatures[(qname, arity)] = 'function({}) as {}'.format(
                        ', '.join(sequence_types[:arity]), sequence_types[-1]
                    )

        token_class = cast(
            Type[XPathFunction], ABCMeta(class_name, (XPathFunction,), kwargs)
        )
        MutableSequence.register(token_class)

        self.symbol_table[lookup_name] = token_class
        self.tokenizer = None
        return token_class

    def is_schema_bound(self) -> bool:
        return self.schema is not None and 'symbol_table' in self.__dict__

    def parse(self, source: str) -> XPathToken:
        if self.tokenizer is None:
            self.tokenizer = self.create_tokenizer(self.symbol_table)

        root_token = super(XPath1Parser, self).parse(source)
        if root_token.label in ('sequence type', 'function test'):
            raise root_token.error('XPST0003', "not allowed in XPath expression")

        if self.schema is None:
            try:
                root_token.evaluate()  # Static context evaluation
            except MissingContextError:
                pass
        else:
            # Static context evaluation with a dynamic schema context
            context = self.schema.get_context()
            for _ in root_token.select(context):
                pass

        return root_token

    def check_variables(self, values: MutableMapping[str, Any]) -> None:
        if self.variable_types is None:
            return

        for varname, xsd_type in self.variable_types.items():
            if varname not in values:
                raise xpath_error('XPST0008', "missing variable {!r}".format(varname))

        for varname, value in values.items():
            try:
                sequence_type = self.variable_types[varname]
            except KeyError:
                sequence_type = 'item()*' if isinstance(value, list) else 'item()'

            if not match_sequence_type(value, sequence_type, self):
                message = "Unmatched sequence type for variable {!r}".format(varname)
                raise xpath_error('XPDY0050', message)


##
# Remove symbols that have to be redefined for XPath 2.0.
XPath2Parser.unregister(',')
XPath2Parser.unregister('(')
XPath2Parser.unregister('$')
XPath2Parser.unregister('contains')
XPath2Parser.unregister('lang')
XPath2Parser.unregister('id')
XPath2Parser.unregister('substring-before')
XPath2Parser.unregister('substring-after')
XPath2Parser.unregister('starts-with')

###
# Symbols
XPath2Parser.register('then')
XPath2Parser.register('else')
XPath2Parser.register('in')
XPath2Parser.register('return')
XPath2Parser.register('satisfies')
XPath2Parser.register('?')
XPath2Parser.register('(:')
XPath2Parser.register(':)')

# XPath 2.0 definitions continue into module xpath2_operators
