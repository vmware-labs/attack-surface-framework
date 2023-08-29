#
# Copyright (c), 2021, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
"""
Define type hints protocols for XPath related objects.
"""
import sys
from typing import overload, Any


if sys.version_info < (3, 8):
    # for Python < 3.8 fallback to typing.Any
    ElementProtocol = Any
    LxmlElementProtocol = Any
    DocumentProtocol = Any
    XsdValidatorProtocol = Any
    XsdSchemaProtocol = Any
    XsdComponentProtocol = Any
    XsdTypeProtocol = Any
    XsdElementProtocol = Any
    XsdAttributeProtocol = Any
    GlobalMapsProtocol = Any
    XMLSchemaProtocol = Any
else:
    from typing import Dict, Iterator, Iterable, List, Literal, \
        Optional, Protocol, Sized, Hashable, Union, TypeVar, runtime_checkable

    _T = TypeVar("_T")

    @runtime_checkable
    class ElementProtocol(Iterable['ElementProtocol'], Sized, Hashable, Protocol):
        def find(
            self, path: str, namespaces: Optional[Dict[str, str]] = ...
        ) -> Optional['ElementProtocol']: ...
        def iter(self, tag: Optional[str] = ...) -> Iterator['ElementProtocol']: ...
        @overload
        def get(self, key: str, default: None = ...) -> Optional[str]: ...
        # noinspection PyOverloads
        @overload
        def get(self, key: str, default: _T) -> Union[str, _T]: ...
        tag: str
        attrib: Dict[str, Any]
        text: Optional[str]
        tail: Optional[str]

    @runtime_checkable
    class LxmlElementProtocol(ElementProtocol, Protocol):
        def getroottree(self) -> 'DocumentProtocol': ...
        def getnext(self) -> Optional['LxmlElementProtocol']: ...
        def getparent(self) -> Optional['LxmlElementProtocol']: ...
        def getprevious(self) -> Optional['LxmlElementProtocol']: ...
        def itersiblings(self, tag: Optional[str] = ..., preceding: bool = False,
                         *tags: str) -> Iterable['LxmlElementProtocol']: ...
        nsmap: Dict[Optional[str], str]

    @runtime_checkable
    class DocumentProtocol(Iterable[ElementProtocol], Hashable, Protocol):
        def getroot(self) -> ElementProtocol: ...
        def parse(self, source: Any, *args: Any, **kwargs: Any) -> 'DocumentProtocol': ...
        def iter(self, tag: Optional[str] = ...) -> Iterator[ElementProtocol]: ...

    @runtime_checkable
    class XsdValidatorProtocol(Protocol):
        def is_matching(self, name: Optional[str],
                        default_namespace: Optional[str] = None) -> bool: ...
        xsd_version: Literal['1.0', '1.1']
        name: Optional[str]
        maps: 'GlobalMapsProtocol'

    @runtime_checkable
    class XsdSchemaProtocol(XsdValidatorProtocol, ElementProtocol, Protocol):
        tag: Literal['{http://www.w3.org/2001/XMLSchema}schema']
        attrib: Dict[str, 'XsdAttributeProtocol']
        text: None
    XMLSchemaProtocol = XsdSchemaProtocol  # for backward compatibility

    @runtime_checkable
    class XsdComponentProtocol(XsdValidatorProtocol, Protocol):
        parent: Optional['XsdComponentProtocol']

    @runtime_checkable
    class XsdTypeProtocol(XsdComponentProtocol, Protocol):
        def is_simple(self) -> bool:
            """Returns `True` if it's a simpleType instance, `False` if it's a complexType."""
            ...

        def is_empty(self) -> bool:
            """
            Returns `True` if it's a simpleType instance or a complexType with empty content,
            `False` otherwise.
            """
            ...

        def has_simple_content(self) -> bool:
            """
            Returns `True` if it's a simpleType instance or a complexType with simple content,
            `False` otherwise.
            """
            ...

        def has_mixed_content(self) -> bool:
            """
            Returns `True` if it's a complexType with mixed content, `False` otherwise.
            """
            ...

        def is_element_only(self) -> bool:
            """
            Returns `True` if it's a complexType with element-only content, `False` otherwise.
            """
            ...

        def is_key(self) -> bool:
            """Returns `True` if it's a simpleType derived from xs:ID, `False` otherwise."""
            ...

        def is_qname(self) -> bool:
            """Returns `True` if it's a simpleType derived from xs:QName, `False` otherwise."""
            ...

        def is_notation(self) -> bool:
            """Returns `True` if it's a simpleType derived from xs:NOTATION, `False` otherwise."""
            ...

        def is_valid(self, obj: Any, *args: Any, **kwargs: Any) -> bool:
            """
            Validates an XML object node using the XSD type. The argument *obj* is an element
            for complex type nodes or a text value for simple type nodes. Returns `True` if
            the argument is valid, `False` otherwise.
            """
            ...

        def validate(self, obj: Any, *args: Any, **kwargs: Any) -> None:
            """
            Validates an XML object node using the XSD type. The argument *obj* is an element
            for complex type nodes or a text value for simple type nodes. Raises a `ValueError`
            compatible exception (a `ValueError` or a subclass of it) if the argument is not valid.
            """
            ...

        def decode(self, obj: Any, *args: Any, **kwargs: Any) -> Any:
            """
            Decodes an XML object node using the XSD type. The argument *obj* is an element
            for complex type nodes or a text value for simple type nodes. Raises a `ValueError`
            or a `TypeError` compatible exception if the argument it's not valid.
            """
            ...

        root_type: 'XsdTypeProtocol'
        """
        The type at base of the definition of the XSD type. For a special type is the type
        itself. For an atomic type is the primitive type. For a list is the primitive type
        of the item. For a union is the base union type. For a complex type is xs:anyType.
        """

    @runtime_checkable
    class XsdAttributeProtocol(XsdComponentProtocol, Protocol):
        type: Optional[XsdTypeProtocol]
        ref: Optional['XsdAttributeProtocol']

    @runtime_checkable
    class XsdElementProtocol(XsdComponentProtocol, ElementProtocol, Protocol):
        type: Optional[XsdTypeProtocol]
        ref: Optional['XsdElementProtocol']
        attrib: Dict[str, XsdAttributeProtocol]
        text: None

    class GlobalMapsProtocol(Protocol):
        types: Dict[str, XsdTypeProtocol]
        attributes: Dict[str, XsdAttributeProtocol]
        elements: Dict[str, XsdElementProtocol]
        substitution_groups: Dict[str, List[XsdElementProtocol]]


__all__ = ['ElementProtocol', 'LxmlElementProtocol', 'DocumentProtocol',
           'XsdValidatorProtocol', 'XsdSchemaProtocol', 'XsdComponentProtocol',
           'XsdTypeProtocol', 'XsdElementProtocol', 'XsdAttributeProtocol',
           'GlobalMapsProtocol', 'XMLSchemaProtocol']
