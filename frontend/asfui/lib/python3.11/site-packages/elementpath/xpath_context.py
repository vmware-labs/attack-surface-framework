#
# Copyright (c), 2018-2021, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
import datetime
import importlib
from copy import copy
from itertools import chain
from types import ModuleType
from typing import TYPE_CHECKING, cast, overload, Dict, Any, List, Iterator, \
    Optional, Sequence, Union, Callable, Set

from .exceptions import ElementPathTypeError
from .namespaces import NamespacesType
from .datatypes import AnyAtomicType, Timezone, Language
from .protocols import ElementProtocol, DocumentProtocol
from .etree import is_etree_element, is_etree_document
from .xpath_nodes import ChildNodeType, XPathNode, AttributeNode, NamespaceNode, \
    CommentNode, ProcessingInstructionNode, ElementNode, DocumentNode
from .tree_builders import RootArgType, get_node_tree

if TYPE_CHECKING:
    from .xpath_tokens import XPathToken, XPathAxis, XPathFunction
    ItemType = Union[XPathNode, AnyAtomicType, XPathFunction]
else:
    ItemType = Any

__all__ = ['XPathContext', 'XPathSchemaContext']

ItemArgType = Union[RootArgType, ItemType]


def is_xpath_node(obj: Any) -> bool:
    return isinstance(obj, XPathNode) or is_etree_element(obj) or is_etree_document(obj)


class XPathContext:
    """
    The XPath dynamic context. The static context is provided by the parser.

    Usually the dynamic context instances are created providing only the root element.
    Variable values argument is needed if the XPath expression refers to in-scope variables.
    The other optional arguments are needed only if a specific position on the context is
    required, but have to be used with the knowledge of what is their meaning.

    :param root: the root of the XML document, can be a ElementTree instance or an Element.
    :param namespaces: a dictionary with mapping from namespace prefixes into URIs, \
    used when namespace information is not available within document and element nodes. \
    This can be useful when the dynamic context has additional namespaces and root \
    is an Element or an ElementTree instance of the standard library.
    :param item: the context item. A `None` value means that the context is positioned on \
    the document node.
    :param position: the current position of the node within the input sequence.
    :param size: the number of items in the input sequence.
    :param axis: the active axis. Used to choose when apply the default axis ('child' axis).
    :param variables: dictionary of context variables that maps a QName to a value.
    :param current_dt: current dateTime of the implementation, including explicit timezone.
    :param timezone: implicit timezone to be used when a date, time, or dateTime value does \
    not have a timezone.
    :param documents: available documents. This is a mapping of absolute URI \
    strings onto document nodes. Used by the function fn:doc.
    :param collections: available collections. This is a mapping of absolute URI \
    strings onto sequences of nodes. Used by the XPath 2.0+ function fn:collection.
    :param default_collection: this is the sequence of nodes used when fn:collection \
    is called with no arguments.
    :param text_resources: available text resources. This is a mapping of absolute URI strings \
    onto text resources. Used by XPath 3.0+ function fn:unparsed-text/fn:unparsed-text-lines.
    :param resource_collections: available URI collections. This is a mapping of absolute \
    URI strings to sequence of URIs. Used by the XPath 3.0+ function fn:uri-collection.
    :param default_resource_collection: this is the sequence of URIs used when \
    fn:uri-collection is called with no arguments.
    :param allow_environment: defines if the access to system environment is allowed, \
    for default is `False`. Used by the XPath 3.0+ functions fn:environment-variable \
    and fn:available-environment-variables.
    """
    _etree: Optional[ModuleType] = None
    root: Union[DocumentNode, ElementNode]
    item: Optional[ItemType]
    total_nodes: int = 0  # Number of nodes associated to the context

    documents: Optional[Dict[str, Union[DocumentNode, ElementNode]]] = None
    collections = None
    default_collection: Optional[List[Union[XPathNode, ElementProtocol, DocumentProtocol]]] = None

    def __init__(self,
                 root: RootArgType,
                 namespaces: Optional[NamespacesType] = None,
                 item: Optional[ItemArgType] = None,
                 position: int = 1,
                 size: int = 1,
                 axis: Optional[str] = None,
                 variables: Optional[Dict[str, Any]] = None,
                 current_dt: Optional[datetime.datetime] = None,
                 timezone: Optional[Union[str, Timezone]] = None,
                 documents: Optional[Dict[str, RootArgType]] = None,
                 collections: Optional[Dict[str, List[ItemArgType]]] = None,
                 default_collection: Optional[str] = None,
                 text_resources: Optional[Dict[str, str]] = None,
                 resource_collections: Optional[Dict[str, List[str]]] = None,
                 default_resource_collection: Optional[str] = None,
                 allow_environment: bool = False,
                 default_language: Optional[str] = None,
                 default_calendar: Optional[str] = None,
                 default_place: Optional[str] = None) -> None:

        self.namespaces = dict(namespaces) if namespaces else {}
        self.root = get_node_tree(root, self.namespaces)

        if item is not None:
            self.item = self.get_context_item(item)
        elif isinstance(self.root, ElementNode):
            self.item = self.root
        elif self.root.document is root or isinstance(root, DocumentNode):
            self.item = None
        else:
            self.item = self.get_context_item(root)

        self.position = position
        self.size = size
        self.axis = axis

        if timezone is None or isinstance(timezone, Timezone):
            self.timezone = timezone
        else:
            self.timezone = Timezone.fromstring(timezone)
        self.current_dt = current_dt or datetime.datetime.now(tz=self.timezone)

        if documents is not None:
            self.documents = {k: get_node_tree(v, self.namespaces) if v is not None else v
                              for k, v in documents.items()}

        if variables is None:
            self.variables = {}
        else:
            self.variables = {k: self.get_context_item(v) for k, v in variables.items()}

        if collections is not None:
            self.collections = {k: self.get_context_item(v) if v is not None else v
                                for k, v in collections.items()}

        if default_collection is not None:
            if isinstance(default_collection, list) and \
                    all(is_xpath_node(x) for x in default_collection):
                self.default_collection = self.get_context_item(default_collection)
            else:
                msg = "'default_collection' argument must be a list of XPath nodes"
                raise ElementPathTypeError(msg)

        self.text_resources = text_resources if text_resources is not None else {}
        self.resource_collections = resource_collections
        self.default_resource_collection = default_resource_collection
        self.allow_environment = allow_environment
        self.default_language = None if default_language is None else Language(default_language)
        self.default_calendar = default_calendar
        self.default_place = default_place

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}(root={self.root.value})'

    def __copy__(self) -> 'XPathContext':
        obj: XPathContext = object.__new__(self.__class__)
        obj.__dict__.update(self.__dict__)
        obj.axis = None
        obj.variables = {k: v for k, v in self.variables.items()}
        return obj

    @property
    def etree(self) -> ModuleType:
        if self._etree is None:
            etree_module_name = self.root.value.__class__.__module__
            self._etree: ModuleType = importlib.import_module(etree_module_name)
        return self._etree

    def get_root(self, node: Any) -> Union[None, ElementNode, DocumentNode]:
        if any(node is x for x in self.root.iter()):
            return self.root

        if self.documents is not None:
            try:
                for uri, doc in self.documents.items():
                    if any(node is x for x in doc.iter()):
                        return doc
            except AttributeError:
                pass

        return None

    def is_principal_node_kind(self) -> bool:
        if self.axis == 'attribute':
            return isinstance(self.item, AttributeNode)
        elif self.axis == 'namespace':
            return isinstance(self.item, NamespaceNode)
        else:
            return isinstance(self.item, ElementNode)

    @overload
    def get_context_item(self, item: ItemArgType) -> ItemType: ...

    @overload
    def get_context_item(self, item: List[ItemArgType]) -> List[ItemType]: ...

    def get_context_item(self, item: Union[ItemArgType, List[ItemArgType]]) \
            -> Union[ItemType, List[ItemType]]:
        """
        Checks the item and returns an item suitable for XPath processing.
        For XML trees and elements try a match with an existing node in the
        context. If it fails then builds a new node.
        """
        if isinstance(item, XPathNode):
            return item
        elif isinstance(item, (list, tuple)):
            return [self.get_context_item(x) for x in item]
        elif is_etree_document(item):
            if item is self.root.value:
                return self.root

            if self.documents:
                for doc in self.documents.values():
                    if item is doc.value:
                        return doc

        elif is_etree_element(item):
            try:
                return self.root.elements[item]  # type: ignore[index]
            except (TypeError, KeyError):
                pass

            if self.documents:
                for doc in self.documents.values():
                    if doc.elements is not None and item in doc.elements:
                        return doc.elements[item]  # type: ignore[index]

            if callable(item.tag):  # type: ignore[union-attr]
                if item.tag.__name__ == 'Comment':  # type: ignore[union-attr]
                    return CommentNode(cast(ElementProtocol, item))
                else:
                    return ProcessingInstructionNode(cast(ElementProtocol, item))
        else:
            return cast(Union[AnyAtomicType, 'XPathFunction'], item)

        return get_node_tree(
            root=cast(Union[RootArgType], item),
            namespaces=self.namespaces
        )

    def inner_focus_select(self, token: Union['XPathToken', 'XPathAxis']) -> Iterator[Any]:
        """Apply the token's selector with an inner focus."""
        status = self.item, self.size, self.position, self.axis
        results = [x for x in token.select(copy(self))]
        self.axis = None

        if token.label == 'axis' and cast('XPathAxis', token).reverse_axis:
            self.size = self.position = len(results)
            for self.item in results:
                yield self.item
                self.position -= 1
        else:
            self.size = len(results)
            for self.position, self.item in enumerate(results, start=1):
                yield self.item

        self.item, self.size, self.position, self.axis = status

    def iter_product(self, selectors: Sequence[Callable[[Any], Any]],
                     varnames: Optional[Sequence[str]] = None) -> Iterator[Any]:
        """
        Iterator for cartesian products of selectors.

        :param selectors: a sequence of selector generator functions.
        :param varnames: a sequence of variables for storing the generated values.
        """
        iterators = [x(self) for x in selectors]
        dimension = len(iterators)
        prod = [None] * dimension
        max_index = dimension - 1

        k = 0
        while True:
            try:
                value = next(iterators[k])
            except StopIteration:
                if not k:
                    return
                iterators[k] = selectors[k](self)
                k -= 1
            else:
                if varnames is not None:
                    try:
                        self.variables[varnames[k]] = value
                    except (TypeError, IndexError):
                        pass

                prod[k] = value
                if k == max_index:
                    yield tuple(prod)
                else:
                    k += 1

    ##
    # Context item iterators for axis

    def iter_self(self) -> Iterator[Optional[ItemType]]:
        """Iterator for 'self' axis and '.' shortcut."""
        status = self.axis
        self.axis = 'self'
        yield self.item
        self.axis = status

    def iter_attributes(self) -> Iterator[AttributeNode]:
        """Iterator for 'attribute' axis and '@' shortcut."""
        status: Any

        if isinstance(self.item, AttributeNode):
            status = self.axis
            self.axis = 'attribute'
            yield self.item
            self.axis = status
            return
        elif isinstance(self.item, ElementNode):
            status = self.item, self.axis
            self.axis = 'attribute'

            for self.item in self.item.attributes:
                yield self.item

            self.item, self.axis = status

    def iter_children_or_self(self) -> Iterator[Optional[ItemType]]:
        """Iterator for 'child' forward axis and '/' step."""
        if self.axis is not None:
            yield self.item
        elif isinstance(self.item, (ElementNode, DocumentNode)):
            _status = self.item, self.axis
            self.axis = 'child'

            for self.item in self.item:
                yield self.item

            self.item, self.axis = _status

        elif self.item is None:
            self.axis = 'child'

            if isinstance(self.root, DocumentNode):
                for self.item in self.root:
                    yield self.item
            else:
                # document position without a document node -> yield root ElementNode
                yield self.root

            self.item = self.axis = None

    def iter_parent(self) -> Iterator[Union[ElementNode, DocumentNode]]:
        """Iterator for 'parent' reverse axis and '..' shortcut."""
        if not isinstance(self.item, XPathNode):
            return  # not applicable

        if self.item is not self.root:
            parent = self.item.parent
            if parent is not None:
                status = self.item, self.axis
                self.axis = 'parent'

                self.item = parent
                yield self.item

                self.item, self.axis = status

    def iter_siblings(self, axis: Optional[str] = None) -> Iterator[ChildNodeType]:
        """
        Iterator for 'following-sibling' forward axis and 'preceding-sibling' reverse axis.

        :param axis: the context axis, default is 'following-sibling'.
        """
        if not isinstance(self.item, XPathNode) or self.item is self.root:
            return

        parent = self.item.parent
        if parent is None:
            return

        item = self.item
        status = self.item, self.axis
        self.axis = axis or 'following-sibling'

        if axis == 'preceding-sibling':
            for child in parent:  # pragma: no cover
                if child is item:
                    break
                self.item = child
                yield child
        else:
            follows = False
            for child in parent:
                if follows:
                    self.item = child
                    yield child
                elif child is item:
                    follows = True
        self.item, self.axis = status

    def iter_descendants(self, axis: Optional[str] = None) -> Iterator[Union[None, XPathNode]]:
        """
        Iterator for 'descendant' and 'descendant-or-self' forward axes and '//' shortcut.

        :param axis: the context axis, for default has no explicit axis.
        """
        descendants: Iterator[Union[None, XPathNode]]
        with_self = axis != 'descendant'

        if isinstance(self.item, (ElementNode, DocumentNode)):
            descendants = self.item.iter_descendants(with_self)
        elif self.item is None:
            if isinstance(self.root, DocumentNode):
                descendants = self.root.iter_descendants(with_self)
            elif with_self:
                # Yields None in order to emulate position on document
                # FIXME replacing the self.root with ElementTree(self.root)?
                descendants = chain((None,), self.root.iter_descendants())
            else:
                descendants = self.root.iter_descendants()
        else:
            if with_self and isinstance(self.item, XPathNode):
                self.axis, axis = axis, self.axis
                yield self.item
                self.axis = axis
            return

        status = self.item, self.axis
        self.axis = axis
        for self.item in descendants:
            yield self.item
        self.item, self.axis = status

    def iter_ancestors(self, axis: Optional[str] = None) -> Iterator[XPathNode]:
        """
        Iterator for 'ancestor' and 'ancestor-or-self' reverse axes.

        :param axis: the context axis, default is 'ancestor'.
        """
        if not isinstance(self.item, XPathNode):
            return  # item is not an XPath node or document position without a document root

        status = self.item, self.axis
        self.axis = axis or 'ancestor'

        ancestors: List[XPathNode] = []
        if axis == 'ancestor-or-self':
            ancestors.append(self.item)

        if self.item is not self.root:
            parent = self.item.parent
            while parent is not None:
                ancestors.append(parent)
                if parent is self.root:
                    break
                parent = parent.parent

        for self.item in reversed(ancestors):
            yield self.item

        self.item, self.axis = status

    def iter_preceding(self) -> Iterator[Union[DocumentNode, ChildNodeType]]:
        """Iterator for 'preceding' reverse axis."""
        ancestors: Set[Union[ElementNode, DocumentNode]]
        item: XPathNode
        parent: Union[None, ElementNode, DocumentNode]

        if not isinstance(self.item, XPathNode) or self.item is self.root:
            return

        parent = self.item.parent
        if parent is None:
            return

        status = self.item, self.axis
        self.axis = 'preceding'

        ancestors = set()
        while parent is not None:
            ancestors.add(parent)
            if parent is self.root:
                break
            parent = parent.parent

        item = self.item
        for self.item in self.root.iter_descendants():
            if self.item is item:
                break
            if self.item not in ancestors:
                yield self.item

        self.item, self.axis = status

    def iter_followings(self) -> Iterator[ChildNodeType]:
        """Iterator for 'following' forward axis."""
        if self.item is None or self.item is self.root:
            return
        elif isinstance(self.item, ElementNode):
            status = self.item, self.axis
            self.axis = 'following'
            item = self.item

            descendants = set(item.iter_descendants())
            for self.item in self.root.iter_descendants(with_self=False):
                if item.position < self.item.position and self.item not in descendants:
                    yield cast(ChildNodeType, self.item)

            self.item, self.axis = status


class XPathSchemaContext(XPathContext):
    """
    The XPath dynamic context base class for schema bounded parsers. Use this class
    as dynamic context for schema instances in order to perform a schema-based type
    checking during the static analysis phase. Don't use this as dynamic context on
    XML instances.
    """
    root: ElementNode
