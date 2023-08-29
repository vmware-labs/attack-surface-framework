#
# Copyright (c), 2018-2021, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING, cast, Any, Dict, List, Optional, Iterator, Union

from .exceptions import ElementPathTypeError
from .protocols import ElementProtocol, XsdTypeProtocol, XsdAttributeProtocol, \
    XsdElementProtocol, XsdSchemaProtocol
from .datatypes import AtomicValueType
from .etree import is_etree_element
from .xpath_context import XPathSchemaContext

if TYPE_CHECKING:
    from .xpath2 import XPath2Parser
    from .xpath30 import XPath30Parser

    XPathParserType = Union[XPath2Parser, XPath30Parser]
else:
    XPathParserType = Any


class AbstractSchemaProxy(metaclass=ABCMeta):
    """
    Abstract base class for defining schema proxies.

    :param schema: a schema instance that implements the `AbstractEtreeElement` interface.
    :param base_element: the schema element used as base item for static analysis.
    """
    def __init__(self, schema: XsdSchemaProtocol,
                 base_element: Optional[ElementProtocol] = None) -> None:
        if not is_etree_element(schema):
            raise ElementPathTypeError(
                "argument {!r} is not a compatible schema instance".format(schema)
            )
        if base_element is not None and not is_etree_element(base_element):
            raise ElementPathTypeError(
                "argument 'base_element' is not a compatible element instance"
            )

        self._schema = schema
        self._base_element: Optional[ElementProtocol] = base_element

    def bind_parser(self, parser: XPathParserType) -> None:
        """
        Binds a parser instance with schema proxy adding the schema's atomic types constructors.
        This method can be redefined in a concrete proxy to optimize schema bindings.

        :param parser: a parser instance.
        """
        if parser.schema is not self:
            parser.schema = self

        for xsd_type in self.iter_atomic_types():
            if xsd_type.name is not None:  # pragma: no cover
                parser.schema_constructor(xsd_type.name)

    def get_context(self) -> XPathSchemaContext:
        """
        Get a context instance for static analysis phase.

        :returns: an `XPathSchemaContext` instance.
        """
        return XPathSchemaContext(root=self._schema, item=self._base_element)

    def find(self, path: str, namespaces: Optional[Dict[str, str]] = None) \
            -> Optional[XsdElementProtocol]:
        """
        Find a schema element or attribute using an XPath expression.

        :param path: an XPath expression that selects an element or an attribute node.
        :param namespaces: an optional mapping from namespace prefix to namespace URI.
        :return: The first matching schema component, or ``None`` if there is no match.
        """
        return cast(Optional[XsdElementProtocol], self._schema.find(path, namespaces))

    @property
    def xsd_version(self) -> str:
        """The XSD version, returns '1.0' or '1.1'."""
        return self._schema.xsd_version

    def get_type(self, qname: str) -> Optional[XsdTypeProtocol]:
        """
        Get the XSD global type from the schema's scope. A concrete implementation must
        return an object that supports the protocols `XsdTypeProtocol`, or `None` if
        the global type is not found.

        :param qname: the fully qualified name of the type to retrieve.
        :returns: an object that represents an XSD type or `None`.
        """
        return self._schema.maps.types.get(qname)

    def get_attribute(self, qname: str) -> Optional[XsdAttributeProtocol]:
        """
        Get the XSD global attribute from the schema's scope. A concrete implementation must
        return an object that supports the protocol `XsdAttributeProtocol`, or `None` if
        the global attribute is not found.

        :param qname: the fully qualified name of the attribute to retrieve.
        :returns: an object that represents an XSD attribute or `None`.
        """
        return self._schema.maps.attributes.get(qname)

    def get_element(self, qname: str) -> Optional[XsdElementProtocol]:
        """
        Get the XSD global element from the schema's scope. A concrete implementation must
        return an object that supports the protocol `XsdElementProtocol` interface, or
        `None` if the global element is not found.

        :param qname: the fully qualified name of the element to retrieve.
        :returns: an object that represents an XSD element or `None`.
        """
        return self._schema.maps.elements.get(qname)

    def get_substitution_group(self, qname: str) -> Optional[List[XsdElementProtocol]]:
        """
        Get a substitution group. A concrete implementation must returns a list containing
        substitution elements or `None` if the substitution group is not found. Moreover each item
        of the returned list must be an object that implements the `AbstractXsdElement` interface.

        :param qname: the fully qualified name of the substitution group to retrieve.
        :returns: a list containing substitution elements or `None`.
        """
        return self._schema.maps.substitution_groups.get(qname)

    @abstractmethod
    def is_instance(self, obj: Any, type_qname: str) -> bool:
        """
        Returns `True` if *obj* is an instance of the XSD global type, `False` if not.

        :param obj: the instance to be tested.
        :param type_qname: the fully qualified name of the type used to test the instance.
        """

    @abstractmethod
    def cast_as(self, obj: Any, type_qname: str) -> AtomicValueType:
        """
        Converts *obj* to the Python type associated with an XSD global type. A concrete
        implementation must raises a `ValueError` or `TypeError` in case of a decoding
        error or a `KeyError` if the type is not bound to the schema's scope.

        :param obj: the instance to be cast.
        :param type_qname: the fully qualified name of the type used to convert the instance.
        """

    @abstractmethod
    def iter_atomic_types(self) -> Iterator[XsdTypeProtocol]:
        """
        Returns an iterator for not builtin atomic types defined in the schema's scope. A concrete
        implementation must yield objects that implement the protocol `XsdTypeProtocol`.
        """


__all__ = ['AbstractSchemaProxy']
