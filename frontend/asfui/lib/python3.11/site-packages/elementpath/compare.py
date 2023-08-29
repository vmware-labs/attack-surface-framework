#
# Copyright (c), 2022, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
import math
from decimal import Decimal
from functools import cmp_to_key
from itertools import zip_longest
from typing import Any, Callable, Optional, Iterable, Iterator

from .protocols import ElementProtocol
from .exceptions import xpath_error
from .datatypes import UntypedAtomic, AnyURI, AbstractQName
from .collations import UNICODE_CODEPOINT_COLLATION, CollationManager
from .xpath_nodes import XPathNode, ElementNode, AttributeNode, NamespaceNode, \
    TextNode, CommentNode, ProcessingInstructionNode, DocumentNode
from .xpath_tokens import XPathToken, XPathFunction, XPathMap, XPathArray


def deep_equal(seq1: Iterable[Any],
               seq2: Iterable[Any],
               collation: Optional[str] = None,
               token: Optional[XPathToken] = None) -> bool:

    etree_node_types = (ElementNode, CommentNode, ProcessingInstructionNode)

    def etree_deep_equal(e1: ElementProtocol, e2: ElementProtocol) -> bool:
        if cm.ne(e1.tag, e2.tag):
            return False
        elif cm.ne((e1.text or '').strip(), (e2.text or '').strip()):
            return False
        elif cm.ne((e1.tail or '').strip(), (e2.tail or '').strip()):
            return False
        elif len(e1) != len(e2) or len(e1.attrib) != len(e2.attrib):
            return False

        items1 = {(cm.strxfrm(k), cm.strxfrm(v)) for k, v in e1.attrib.items()}
        items2 = {(cm.strxfrm(k), cm.strxfrm(v)) for k, v in e2.attrib.items()}
        if items1 != items2:
            return False
        return all(etree_deep_equal(c1, c2) for c1, c2 in zip(e1, e2))

    if collation is None:
        collation = UNICODE_CODEPOINT_COLLATION

    with CollationManager(collation, token=token) as cm:
        for value1, value2 in zip_longest(seq1, seq2):
            if isinstance(value1, XPathFunction) and \
                    not isinstance(value1, (XPathMap, XPathArray)):
                raise xpath_error('FOTY0015', token=token)
            if isinstance(value2, XPathFunction) and \
                    not isinstance(value2, (XPathMap, XPathArray)):
                raise xpath_error('FOTY0015', token=token)

            if (value1 is None) ^ (value2 is None):
                return False
            elif value1 is None:
                return True
            elif isinstance(value1, XPathNode) ^ isinstance(value2, XPathNode):
                return False
            elif isinstance(value1, XPathNode):
                assert isinstance(value2, XPathNode)
                if value1.kind != value2.kind:
                    return False
                elif isinstance(value1, etree_node_types):
                    assert isinstance(value2, etree_node_types)
                    if not etree_deep_equal(value1.elem, value2.elem):
                        return False
                elif isinstance(value1, DocumentNode):
                    assert isinstance(value2, DocumentNode)
                    for child1, child2 in zip_longest(value1, value2):
                        if child1 is None or child2 is None:
                            return False
                        elif child1.kind != child2.kind:
                            return False
                        elif isinstance(child1, etree_node_types):
                            assert isinstance(child2, etree_node_types)
                            if not etree_deep_equal(child1.elem, child2.elem):
                                return False
                        elif isinstance(child1, TextNode):
                            assert isinstance(child2, TextNode)
                            if cm.ne(child1.value, child2.value):
                                return False

                elif cm.ne(value1.value, value2.value):
                    return False
                elif isinstance(value1, AttributeNode):
                    if cm.ne(value1.name, value2.name):
                        return False
                elif isinstance(value1, NamespaceNode):
                    assert isinstance(value2, NamespaceNode)
                    if cm.ne(value1.prefix, value2.prefix):
                        return False
            else:
                try:
                    if isinstance(value1, bool):
                        if not isinstance(value2, bool) or value1 is not value2:
                            return False

                    elif isinstance(value2, bool):
                        return False

                    if isinstance(value1, AbstractQName):
                        if not isinstance(value2, AbstractQName) or value1 != value2:
                            return False

                    elif isinstance(value2, AbstractQName):
                        return False

                    elif isinstance(value1, (str, AnyURI, UntypedAtomic)) \
                            and isinstance(value2, (str, AnyURI, UntypedAtomic)):
                        if cm.strcoll(str(value1), str(value2)):
                            return False

                    elif isinstance(value1, UntypedAtomic) \
                            or isinstance(value2, UntypedAtomic):
                        return False

                    elif isinstance(value1, float):
                        if math.isnan(value1):
                            if not math.isnan(value2):
                                return False
                        elif math.isinf(value1):
                            if value1 != value2:
                                return False
                        elif isinstance(value2, Decimal):
                            if value1 != float(value2):
                                return False
                        elif not isinstance(value2, (value1.__class__, int)):
                            return False
                        elif value1 != value2:
                            return False

                    elif isinstance(value2, float):
                        if math.isnan(value2):
                            return False
                        elif math.isinf(value2):
                            if value1 != value2:
                                return False
                        elif isinstance(value1, Decimal):
                            if value2 != float(value1):
                                return False
                        elif not isinstance(value1, (value2.__class__, int)):
                            return False
                        elif value1 != value2:
                            return False
                    elif value1 != value2:
                        return False
                except TypeError:
                    return False

    return True


def is_empty_sequence(x: Any) -> bool:
    return not x and isinstance(x, list)


def deep_compare(obj1: Any,
                 obj2: Any,
                 collation: Optional[str] = None,
                 token: Optional[XPathToken] = None) -> int:

    msg_tmpl = "Sorting failed, cannot compare {!r} with {!r}"
    etree_node_types = (ElementNode, CommentNode, ProcessingInstructionNode)
    result: int = 0

    def iter_object(obj: Any) -> Iterator[Any]:
        if isinstance(obj, XPathArray):
            yield from obj.items()
        elif isinstance(obj, (list, Iterator)):
            yield from obj
        else:
            yield obj

    def etree_deep_compare(e1: ElementProtocol, e2: ElementProtocol) -> int:
        nonlocal result
        result = cm.strcoll(e1.tag, e2.tag)
        if result:
            return result

        result = cm.strcoll((e1.text or '').strip(), (e2.text or '').strip())
        if result:
            return result

        for a1, a2 in zip_longest(e1.attrib.items(), e2.attrib.items()):
            if a1 is None:
                return 1
            elif a2 is None:
                return -1

            result = cm.strcoll(a1[0], a2[0]) or cm.strcoll(a1[1], a2[1])
            if result:
                return result

        for c1, c2 in zip_longest(e1, e2):
            if c1 is None:
                return 1
            elif c2 is None:
                return -1

            result = etree_deep_compare(c1, c2)
            if result:
                return result
        else:
            result = cm.strcoll((e1.tail or '').strip(), (e2.tail or '').strip())
            if result:
                return result

            return 0

    if collation is None:
        collation = UNICODE_CODEPOINT_COLLATION

    with CollationManager(collation, token=token) as cm:
        for value1, value2 in zip_longest(iter_object(obj1), iter_object(obj2)):
            if isinstance(value1, XPathFunction) and \
                    not isinstance(value1, XPathArray):
                raise xpath_error('FOTY0013', token=token)
            if isinstance(value2, XPathFunction) and \
                    not isinstance(value2, XPathArray):
                raise xpath_error('FOTY0013', token=token)

            if (value1 is None) ^ (value2 is None):
                return -1 if value1 is None else 1

            if is_empty_sequence(value1) ^ is_empty_sequence(value2):
                return -1 if is_empty_sequence(value1) else 1

            if isinstance(value1, XPathNode) ^ isinstance(value2, XPathNode):
                msg = f"cannot compare {type(value1)} with {type(value2)}"
                raise xpath_error('XPTY0004', msg, token=token)
            elif isinstance(value1, XPathNode):
                assert isinstance(value2, XPathNode)
                if value1.kind != value2.kind:
                    msg = f"cannot compare {type(value1)} with {type(value2)}"
                    raise xpath_error('XPTY0004', msg, token=token)
                elif isinstance(value1, etree_node_types):
                    assert isinstance(value2, etree_node_types)
                    result = etree_deep_compare(value1.elem, value2.elem)
                    if result:
                        return result
                elif isinstance(value1, DocumentNode):
                    assert isinstance(value2, DocumentNode)
                    for child1, child2 in zip_longest(value1, value2):
                        if child1 is None:
                            return -1
                        elif child2 is None:
                            return 1
                        elif child1.kind != child2.kind:
                            msg = f"cannot compare {type(child1)} with {type(child2)}"
                            raise xpath_error('XPTY0004', msg, token=token)
                        elif isinstance(child1, etree_node_types):
                            assert isinstance(child2, etree_node_types)
                            result = etree_deep_compare(child1.elem, child2.elem)
                            if result:
                                return result
                        elif isinstance(child1, TextNode):
                            assert isinstance(child2, TextNode)
                            result = cm.strcoll(
                                child1.value.strip(), child2.value.strip()
                            )
                            if result:
                                return result
                else:
                    result = cm.strcoll(value1.value, value2.value)
                    if result:
                        return result

                    if isinstance(value1, AttributeNode):
                        assert isinstance(value2, AttributeNode)
                        result = cm.strcoll(value1.name, value2.name)
                        if result:
                            return result
                    elif isinstance(value1, NamespaceNode):
                        assert isinstance(value2, NamespaceNode)
                        result = cm.strcoll(value1.prefix or '', value2.prefix or '')
                        if result:
                            return result
            else:
                try:
                    if isinstance(value1, bool):
                        if not isinstance(value2, bool):
                            return -1
                        elif value1 is not value2:
                            return -1 if value1 else 1

                    elif isinstance(value2, bool):
                        return -1

                    elif isinstance(value1, UntypedAtomic):
                        if isinstance(value2, UntypedAtomic):
                            result = cm.strcoll(str(value1), str(value2))
                            if result:
                                return result
                        else:
                            msg = msg_tmpl.format(value1, value2)
                            raise xpath_error('XPTY0004', msg, token)

                    elif isinstance(value2, UntypedAtomic):
                        msg = msg_tmpl.format(value1, value2)
                        raise xpath_error('XPTY0004', msg, token)

                    elif isinstance(value1, float):
                        if math.isnan(value1):
                            if not math.isnan(value2):  # type: ignore[arg-type]
                                return -1
                        elif math.isinf(value1):
                            if value1 != value2:
                                return -1 if value1 < value2 else 1  # type: ignore[operator]
                        elif isinstance(value2, Decimal):
                            if value1 != float(value2):
                                return -1 if value1 < float(value2) else 1
                        elif not isinstance(value2, (value1.__class__, int)):
                            return -1
                        elif value1 != value2:
                            return -1 if value1 < value2 else 1

                    elif isinstance(value2, float):
                        if math.isnan(value2):
                            return -1
                        elif math.isinf(value2):
                            if value1 != value2:
                                return -1 if value1 < value2 else 1  # type: ignore[operator]
                        elif isinstance(value1, Decimal):
                            if value2 != float(value1):
                                return -1 if float(value1) < value2 else 1
                        elif not isinstance(value1, (value2.__class__, int)):
                            return -1
                        elif value1 != value2:
                            return -1 if value1 < value2 else 1

                    elif isinstance(value1, (str, AnyURI, UntypedAtomic)) \
                            and isinstance(value2, (str, AnyURI, UntypedAtomic)):
                        result = cm.strcoll(str(value1), str(value2))
                        if result:
                            return result
                    elif value1 != value2:
                        return -1 if value1 < value2 else 1  # type: ignore[operator]

                except TypeError as err:
                    raise xpath_error('XPTY0004', message_or_error=err, token=token)

    return 0


def get_key_function(collation: Optional[str] = None,
                     key_func: Optional[Callable[[Any], Any]] = None,
                     token: Optional[XPathToken] = None) -> Any:

    def compare_func(obj1: Any, obj2: Any) -> int:
        if key_func is not None:
            if isinstance(obj1, (list, Iterator)):
                obj1 = map(key_func, obj1)
            else:
                obj1 = key_func(obj1)

            if isinstance(obj2, (list, Iterator)):
                obj2 = map(key_func, obj2)
            else:
                obj2 = key_func(obj2)

        return deep_compare(obj1, obj2, collation, token)

    return cmp_to_key(compare_func)


def same_key(k1: Any, k2: Any) -> bool:
    if isinstance(k1, (str, AnyURI, UntypedAtomic)):
        if not isinstance(k2, (str, AnyURI, UntypedAtomic)):
            return False
        return str(k1) == str(k2)
    elif isinstance(k1, float) and math.isnan(k1):
        return isinstance(k2, float) and math.isnan(k2)
    elif isinstance(k1, AbstractQName) ^ isinstance(k2, AbstractQName):
        return False

    try:
        return True if k1 == k2 else False
    except TypeError:
        return False  # EAFP :)
