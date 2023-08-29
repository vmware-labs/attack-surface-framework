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
XPath 1.0 implementation - part 1 (parser class and symbols)
"""
import re
from abc import ABCMeta
from typing import cast, Any, ClassVar, Dict, MutableMapping, \
    Optional, Tuple, Type, Set, Sequence

from ..exceptions import MissingContextError, ElementPathValueError, xpath_error
from ..datatypes import QName
from ..tdop import Token, Parser
from ..namespaces import NamespacesType, XML_NAMESPACE, XSD_NAMESPACE, \
    XPATH_FUNCTIONS_NAMESPACE
from ..sequence_types import match_sequence_type
from ..schema_proxy import AbstractSchemaProxy
from ..xpath_tokens import NargsType, XPathToken, XPathAxis, XPathFunction, ProxyToken


class XPath1Parser(Parser[XPathToken]):
    """
    XPath 1.0 expression parser class. Provide a *namespaces* dictionary argument for
    mapping namespace prefixes to URI inside expressions. If *strict* is set to `False`
    the parser enables also the parsing of QNames, like the ElementPath library.

    :param namespaces: a dictionary with mapping from namespace prefixes into URIs.
    :param strict: a strict mode is `False` the parser enables parsing of QNames \
    in extended format, like the Python's ElementPath library. Default is `True`.
    """
    version = '1.0'
    """The XPath version string."""

    token_base_class: Type[Token[Any]] = XPathToken
    literals_pattern = re.compile(
        r"""'(?:[^']|'')*'|"(?:[^"]|"")*"|(?:\d+|\.\d+)(?:\.\d*)?(?:[Ee][+-]?\d+)?"""
    )
    name_pattern = re.compile(r'[^\d\W][\w.\-\xb7\u0300-\u036F\u203F\u2040]*')

    RESERVED_FUNCTION_NAMES = {
        'comment', 'element', 'node', 'processing-instruction', 'text'
    }

    DEFAULT_NAMESPACES: ClassVar[Dict[str, str]] = {'xml': XML_NAMESPACE}
    """Namespaces known statically by default."""

    # Labels and symbols admitted after a path step
    PATH_STEP_LABELS: ClassVar[Tuple[str, ...]] = ('axis', 'kind test')
    PATH_STEP_SYMBOLS: ClassVar[Set[str]] = {
        '(integer)', '(string)', '(float)', '(decimal)', '(name)', '*', '@', '..', '.', '{'
    }

    # Class attributes for compatibility with XPath 2.0+
    schema: Optional[AbstractSchemaProxy] = None
    variable_types: Optional[Dict[str, str]] = None
    base_uri: Optional[str] = None
    function_namespace = XPATH_FUNCTIONS_NAMESPACE
    function_signatures: Dict[Tuple[QName, int], str] = {}
    parse_arguments: bool = True

    compatibility_mode: bool = True
    """XPath 1.0 compatibility mode."""

    default_namespace: Optional[str] = None
    """
    The default namespace. For XPath 1.0 this value is always `None` because the default
    namespace is ignored (see https://www.w3.org/TR/1999/REC-xpath-19991116/#node-tests).
    """

    def __init__(self, namespaces: Optional[NamespacesType] = None,
                 strict: bool = True) -> None:
        super(XPath1Parser, self).__init__()
        self.namespaces: Dict[str, str] = self.DEFAULT_NAMESPACES.copy()
        if namespaces is not None:
            self.namespaces.update(namespaces)
        self.strict: bool = strict

    def __repr__(self) -> str:
        args = []
        if self.namespaces != self.DEFAULT_NAMESPACES:
            args.append(str(self.other_namespaces))
        if not self.strict:
            args.append('strict=False')
        return f"{self.__class__.__name__}({', '.join(args)})"

    @property
    def other_namespaces(self) -> Dict[str, str]:
        """The subset of namespaces not known by default."""
        return {k: v for k, v in self.namespaces.items()
                if k not in self.DEFAULT_NAMESPACES or self.DEFAULT_NAMESPACES[k] != v}

    @property
    def xsd_version(self) -> str:
        return '1.0'  # Use XSD 1.0 datatypes for default

    def xsd_qname(self, local_name: str) -> str:
        """Returns a prefixed QName string for XSD namespace."""
        if self.namespaces.get('xs') == XSD_NAMESPACE:
            return 'xs:%s' % local_name

        for pfx, uri in self.namespaces.items():
            if uri == XSD_NAMESPACE:
                return '%s:%s' % (pfx, local_name) if pfx else local_name

        raise xpath_error('XPST0081', 'Missing XSD namespace registration')

    @classmethod
    def create_restricted_parser(cls, name: str, symbols: Sequence[str]) \
            -> Type['XPath1Parser']:
        """Get a parser subclass with a restricted set of symbols.s"""
        symbol_table = {
            k: v for k, v in cls.symbol_table.items() if k in symbols
        }
        return cast(Type['XPath1Parser'], ABCMeta(
            f"{name}{cls.__name__}", (cls,), {'symbol_table': symbol_table}
        ))

    @staticmethod
    def unescape(string_literal: str) -> str:
        if string_literal.startswith("'"):
            return string_literal[1:-1].replace("''", "'")
        else:
            return string_literal[1:-1].replace('""', '"')

    @classmethod
    def proxy(cls, symbol: str, label: str = 'proxy', bp: int = 90) -> Type[ProxyToken]:
        """Register a proxy token for a symbol."""
        if symbol in cls.symbol_table and not issubclass(cls.symbol_table[symbol], ProxyToken):
            # Move the token class before register the proxy token
            token_cls = cls.symbol_table.pop(symbol)
            cls.symbol_table[f'{{{token_cls.namespace}}}{symbol}'] = token_cls

        proxy_class = cls.register(symbol, bases=(ProxyToken,), label=label, lbp=bp, rbp=bp)
        return cast(Type[ProxyToken], proxy_class)

    @classmethod
    def axis(cls, symbol: str, reverse_axis: bool = False, bp: int = 80) -> Type[XPathAxis]:
        """Register a token for a symbol that represents an XPath *axis*."""
        token_class = cls.register(symbol, label='axis', bases=(XPathAxis,),
                                   reverse_axis=reverse_axis, lbp=bp, rbp=bp)
        return cast(Type[XPathAxis], token_class)

    @classmethod
    def function(cls, symbol: str,
                 prefix: Optional[str] = None,
                 label: str = 'function',
                 nargs: NargsType = None,
                 sequence_types: Tuple[str, ...] = (),
                 bp: int = 90) -> Type[XPathFunction]:
        """
        Registers a token class for a symbol that represents an XPath function.
        """
        kwargs = {
            'bases': (XPathFunction,),
            'label': label,
            'nargs': nargs,
            'lbp': bp,
            'rbp': bp,
        }
        if 'function' not in label:
            # kind test or sequence type
            return cast(Type[XPathFunction], cls.register(symbol, **kwargs))
        elif symbol in cls.RESERVED_FUNCTION_NAMES:
            raise ElementPathValueError(f'{symbol!r} is a reserved function name')

        if prefix:
            namespace = cls.DEFAULT_NAMESPACES[prefix]
            qname = QName(namespace, '%s:%s' % (prefix, symbol))
            kwargs['lookup_name'] = qname.expanded_name
            kwargs['class_name'] = '_%s%s%s' % (
                prefix.capitalize(),
                symbol.capitalize(),
                str(label).title().replace(' ', '')
            )
            kwargs['namespace'] = namespace
            cls.proxy(symbol, label='proxy function', bp=bp)
        else:
            qname = QName(XPATH_FUNCTIONS_NAMESPACE, 'fn:%s' % symbol)
            kwargs['namespace'] = XPATH_FUNCTIONS_NAMESPACE

        if sequence_types:
            # Register function signature(s)
            kwargs['sequence_types'] = sequence_types

            if nargs is None:
                pass  # pragma: no cover
            elif isinstance(nargs, int):
                assert len(sequence_types) == nargs + 1
                cls.function_signatures[(qname, nargs)] = 'function({}) as {}'.format(
                    ', '.join(sequence_types[:-1]), sequence_types[-1]
                )
            elif nargs[1] is None:
                assert len(sequence_types) == nargs[0] + 1
                cls.function_signatures[(qname, nargs[0])] = 'function({}, ...) as {}'.format(
                    ', '.join(sequence_types[:-1]), sequence_types[-1]
                )
            else:
                assert len(sequence_types) == nargs[1] + 1
                for arity in range(nargs[0], nargs[1] + 1):
                    cls.function_signatures[(qname, arity)] = 'function({}) as {}'.format(
                        ', '.join(sequence_types[:arity]), sequence_types[-1]
                    )

        return cast(Type[XPathFunction], cls.register(symbol, **kwargs))

    def parse(self, source: str) -> XPathToken:
        root_token = super(XPath1Parser, self).parse(source)
        try:
            root_token.evaluate()  # Static context evaluation
        except MissingContextError:
            pass
        return root_token

    def expected_next(self, *symbols: str, message: Optional[str] = None) -> None:
        """
        Checks the next token with a list of symbols. Replaces the next token with
        a '(name)' token if the check fails and the next token can be a name,
        otherwise raises a syntax error.

        :param symbols: a sequence of symbols.
        :param message: optional error message.
        """
        if self.next_token.symbol in symbols:
            return
        elif '(name)' in symbols and \
                not isinstance(self.next_token, (XPathFunction, XPathAxis)) and \
                self.name_pattern.match(self.next_token.symbol) is not None:
            # Disambiguation replacing the next token with a '(name)' token
            self.next_token = self.symbol_table['(name)'](self, self.next_token.symbol)
        else:
            raise self.next_token.wrong_syntax(message)

    def check_variables(self, values: MutableMapping[str, Any]) -> None:
        """Checks the sequence types of the XPath dynamic context's variables."""
        for varname, value in values.items():
            if not match_sequence_type(
                value, 'item()*' if isinstance(value, list) else 'item()', self
            ):
                message = "Unmatched sequence type for variable {!r}".format(varname)
                raise xpath_error('XPDY0050', message)


###
# Special symbols
XPath1Parser.register('(start)')
XPath1Parser.register('(end)')
XPath1Parser.literal('(string)')
XPath1Parser.literal('(float)')
XPath1Parser.literal('(decimal)')
XPath1Parser.literal('(integer)')
XPath1Parser.literal('(invalid)')
XPath1Parser.register('(unknown)')

###
# Simple symbols
XPath1Parser.register(',')
XPath1Parser.register(')', bp=100)
XPath1Parser.register(']')
XPath1Parser.register('::')
XPath1Parser.register('}')

# XPath 1.0 definitions continue into module xpath1_operators
