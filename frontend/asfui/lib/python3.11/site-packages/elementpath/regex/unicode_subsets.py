#
# Copyright (c), 2016-2020, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
"""
This module defines Unicode character categories and blocks.
"""
from sys import maxunicode
from typing import cast, Iterable, Iterator, List, MutableSet, Union, Optional

from .unicode_categories import RAW_UNICODE_CATEGORIES
from .codepoints import CodePoint, code_point_order, code_point_repr, \
    iter_code_points, get_code_point_range

CodePointsArgType = Union[str, 'UnicodeSubset', List[CodePoint], Iterable[CodePoint]]


class RegexError(Exception):
    """
    Error in a regular expression or in a character class specification.
    This exception is derived from `Exception` base class and is raised
    only by the regex subpackage.
    """


def iterparse_character_subset(s: str, expand_ranges: bool = False) -> Iterator[CodePoint]:
    """
    Parses a regex character subset, generating a sequence of code points
    and code points ranges. An unescaped hyphen (-) that is not at the
    start or at the and is interpreted as range specifier.

    :param s: a string representing the character subset.
    :param expand_ranges: if set to `True` then expands character ranges.
    :return: yields integers or couples of integers.
    """
    escaped = False
    on_range = False
    char = ''
    length = len(s)
    subset_index_iterator = iter(range(len(s)))
    for k in subset_index_iterator:
        if k == 0:
            char = s[0]
            if char == '\\':
                escaped = True
            elif char in r'[]' and length > 1:
                raise RegexError("bad character %r at position 0" % char)
            elif expand_ranges:
                yield ord(char)
            elif length <= 2 or s[1] != '-':
                yield ord(char)
        elif s[k] == '-':
            if escaped or (k == length - 1):
                char = s[k]
                yield ord(char)
                escaped = False
            elif on_range:
                char = s[k]
                yield ord(char)
                on_range = False
            else:
                # Parse character range
                on_range = True
                k = next(subset_index_iterator)
                end_char = s[k]
                if end_char == '\\' and (k < length - 1):
                    if s[k + 1] in r'-|.^?*+{}()[]':
                        k = next(subset_index_iterator)
                        end_char = s[k]
                    elif s[k + 1] in r'sSdDiIcCwWpP':
                        msg = "bad character range '%s-\\%s' at position %d: %r"
                        raise RegexError(msg % (char, s[k + 1], k - 2, s))

                if ord(char) > ord(end_char):
                    msg = "bad character range '%s-%s' at position %d: %r"
                    raise RegexError(msg % (char, end_char, k - 2, s))
                elif expand_ranges:
                    yield from range(ord(char) + 1, ord(end_char) + 1)
                else:
                    yield ord(char), ord(end_char) + 1

        elif s[k] in r'|.^?*+{}()':
            if escaped:
                escaped = False
            on_range = False
            char = s[k]
            yield ord(char)
        elif s[k] in r'[]':
            if not escaped and length > 1:
                raise RegexError("bad character %r at position %d" % (s[k], k))
            escaped = on_range = False
            char = s[k]
            if k >= length - 2 or s[k + 1] != '-':
                yield ord(char)
        elif s[k] == '\\':
            if escaped:
                escaped = on_range = False
                char = '\\'
                yield ord(char)
            else:
                escaped = True
        else:
            if escaped:
                escaped = False
                yield ord('\\')
            on_range = False
            char = s[k]
            if k >= length - 2 or s[k + 1] != '-':
                yield ord(char)
    if escaped:
        yield ord('\\')


class UnicodeSubset(MutableSet[CodePoint]):
    """
    Represents a subset of Unicode code points, implemented with an ordered list of
    integer values and ranges. Codepoints can be added or discarded using sequences
    of integer values and ranges or with strings equivalent to regex character set.

    :param codepoints: a sequence of integer values and ranges, another UnicodeSubset \
    instance ora a string equivalent of a regex character set.
    """
    __slots__ = '_codepoints',
    _codepoints: List[CodePoint]

    def __init__(self, codepoints: Optional[CodePointsArgType] = None) -> None:
        if not codepoints:
            self._codepoints = list()
        elif isinstance(codepoints, list):
            self._codepoints = sorted(codepoints, key=code_point_order)
        elif isinstance(codepoints, UnicodeSubset):
            self._codepoints = codepoints.codepoints.copy()
        else:
            self._codepoints = list()
            self.update(codepoints)

    @property
    def codepoints(self) -> List[CodePoint]:
        return self._codepoints

    def __repr__(self) -> str:
        return '%s(%r)' % (self.__class__.__name__, str(self))

    def __str__(self) -> str:
        return ''.join(code_point_repr(cp) for cp in self._codepoints)

    def copy(self) -> 'UnicodeSubset':
        return self.__copy__()

    def __copy__(self) -> 'UnicodeSubset':
        return UnicodeSubset(self._codepoints)

    def __reversed__(self) -> Iterator[int]:
        for item in reversed(self._codepoints):
            if isinstance(item, int):
                yield item
            else:
                yield from reversed(range(item[0], item[1]))

    def complement(self) -> Iterator[CodePoint]:
        last_cp = 0
        for cp in self._codepoints:
            if isinstance(cp, int):
                cp = cp, cp + 1

            diff = cp[0] - last_cp
            if diff > 2:
                yield last_cp, cp[0]
            elif diff == 2:
                yield last_cp
                yield last_cp + 1
            elif diff == 1:
                yield last_cp
            elif diff:
                raise ValueError("unordered code points found in {!r}".format(self))
            last_cp = cp[1]

        if last_cp < maxunicode:
            yield last_cp, maxunicode + 1
        elif last_cp == maxunicode:
            yield maxunicode

    def iter_characters(self) -> Iterator[str]:
        return map(chr, self.__iter__())

    #
    # MutableSet's abstract methods implementation
    def __contains__(self, value: object) -> bool:
        if not isinstance(value, int):
            try:
                value = ord(value)  # type: ignore[arg-type]
            except TypeError:
                return False

        for cp in self._codepoints:
            if not isinstance(cp, int):
                if cp[0] > value:
                    return False
                elif cp[1] <= value:
                    continue
                else:
                    return True
            elif cp > value:
                return False
            elif cp == value:
                return True
        return False

    def __iter__(self) -> Iterator[int]:
        for cp in self._codepoints:
            if isinstance(cp, int):
                yield cp
            else:
                yield from range(*cp)

    def __len__(self) -> int:
        k = 0
        for _ in self:
            k += 1
        return k

    def update(self, *others: Union[str, Iterable[CodePoint]]) -> None:
        for value in others:
            if isinstance(value, str):
                for cp in iter_code_points(iterparse_character_subset(value), reverse=True):
                    self.add(cp)
            else:
                for cp in iter_code_points(value, reverse=True):
                    self.add(cp)

    def add(self, value: CodePoint) -> None:
        try:
            start_value, end_value = get_code_point_range(value)  # type: ignore[misc]
        except TypeError:
            raise ValueError("{!r} is not a Unicode code point value/range".format(value))

        code_points = self._codepoints
        last_index = len(code_points) - 1
        for k, cp in enumerate(code_points):
            if isinstance(cp, int):
                cp = cp, cp + 1

            if end_value < cp[0]:
                code_points.insert(k, value)
            elif start_value > cp[1]:
                continue
            elif end_value > cp[1]:
                if k == last_index:
                    code_points[k] = min(cp[0], start_value), end_value
                else:
                    next_cp = code_points[k + 1]
                    higher_bound = next_cp if isinstance(next_cp, int) else next_cp[0]
                    if end_value <= higher_bound:
                        code_points[k] = min(cp[0], start_value), end_value
                    else:
                        code_points[k] = min(cp[0], start_value), higher_bound
                        start_value = higher_bound
                        continue
            elif start_value < cp[0]:
                code_points[k] = start_value, cp[1]
            break
        else:
            self._codepoints.append(value)

    def difference_update(self, *others: Union[str, Iterable[CodePoint]]) -> None:
        for value in others:
            if isinstance(value, str):
                for cp in iter_code_points(iterparse_character_subset(value), reverse=True):
                    self.discard(cp)
            else:
                for cp in iter_code_points(value, reverse=True):
                    self.discard(cp)

    def discard(self, value: CodePoint) -> None:
        try:
            start_cp, end_cp = get_code_point_range(value)  # type: ignore[misc]
        except TypeError:
            raise ValueError("{!r} is not a Unicode code point value/range".format(value))

        code_points = self._codepoints
        for k in reversed(range(len(code_points))):
            cp = code_points[k]
            if isinstance(cp, int):
                cp = cp, cp + 1

            if start_cp >= cp[1]:
                break
            elif end_cp >= cp[1]:
                if start_cp <= cp[0]:
                    del code_points[k]
                elif start_cp - cp[0] > 1:
                    code_points[k] = cp[0], start_cp
                else:
                    code_points[k] = cp[0]
            elif end_cp > cp[0]:
                if start_cp <= cp[0]:
                    if cp[1] - end_cp > 1:
                        code_points[k] = end_cp, cp[1]
                    else:
                        code_points[k] = cp[1] - 1
                else:
                    if cp[1] - end_cp > 1:
                        code_points.insert(k + 1, (end_cp, cp[1]))
                    else:
                        code_points.insert(k + 1, cp[1] - 1)
                    if start_cp - cp[0] > 1:
                        code_points[k] = cp[0], start_cp
                    else:
                        code_points[k] = cp[0]

    #
    # MutableSet's mixin methods override
    def clear(self) -> None:
        del self._codepoints[:]

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Iterable):
            return NotImplemented
        elif isinstance(other, UnicodeSubset):
            return self._codepoints == other._codepoints
        else:
            return self._codepoints == other

    def __ior__(self, other: object) -> 'UnicodeSubset':
        if not isinstance(other, Iterable):
            return NotImplemented
        elif isinstance(other, UnicodeSubset):
            other = reversed(other._codepoints)
        elif isinstance(other, str):
            other = reversed(UnicodeSubset(other)._codepoints)
        else:
            other = iter_code_points(other, reverse=True)

        for cp in other:
            self.add(cp)
        return self

    def __or__(self, other: object) -> 'UnicodeSubset':
        obj = self.copy()
        return obj.__ior__(other)

    def __isub__(self, other: object) -> 'UnicodeSubset':
        if not isinstance(other, Iterable):
            return NotImplemented
        elif isinstance(other, UnicodeSubset):
            other = reversed(other._codepoints)
        elif isinstance(other, str):
            other = reversed(UnicodeSubset(other)._codepoints)
        else:
            other = iter_code_points(other, reverse=True)

        for cp in other:
            self.discard(cp)
        return self

    def __sub__(self, other: object) -> 'UnicodeSubset':
        obj = self.copy()
        return obj.__isub__(other)

    __rsub__ = __sub__

    def __iand__(self, other: object) -> 'UnicodeSubset':
        if not isinstance(other, Iterable):
            return NotImplemented

        for value in (self - other):
            self.discard(value)
        return self

    def __and__(self, other: object) -> 'UnicodeSubset':
        obj = self.copy()
        return obj.__iand__(other)

    def __ixor__(self, other: object) -> 'UnicodeSubset':
        if other is self:
            self.clear()
            return self
        elif not isinstance(other, Iterable):
            return NotImplemented
        elif not isinstance(other, UnicodeSubset):
            other = UnicodeSubset(cast(Union[str, Iterable[CodePoint]], other))

        for value in other:
            if value in self:
                self.discard(value)
            else:
                self.add(value)
        return self

    def __xor__(self, other: object) -> 'UnicodeSubset':
        obj = self.copy()
        return obj.__ixor__(other)


UNICODE_CATEGORIES = {k: UnicodeSubset(cast(List[CodePoint], v))
                      for k, v in RAW_UNICODE_CATEGORIES.items()}


# See http://www.unicode.org/Public/UNIDATA/Blocks.txt
UNICODE_BLOCKS = {
    'IsBasicLatin': UnicodeSubset('\u0000-\u007F'),
    'IsLatin-1Supplement': UnicodeSubset('\u0080-\u00FF'),
    'IsLatinExtended-A': UnicodeSubset('\u0100-\u017F'),
    'IsLatinExtended-B': UnicodeSubset('\u0180-\u024F'),
    'IsIPAExtensions': UnicodeSubset('\u0250-\u02AF'),
    'IsSpacingModifierLetters': UnicodeSubset('\u02B0-\u02FF'),
    'IsCombiningDiacriticalMarks': UnicodeSubset('\u0300-\u036F'),
    'IsGreek': UnicodeSubset('\u0370-\u03FF'),
    'IsCyrillic': UnicodeSubset('\u0400-\u04FF'),
    'IsArmenian': UnicodeSubset('\u0530-\u058F'),
    'IsHebrew': UnicodeSubset('\u0590-\u05FF'),
    'IsArabic': UnicodeSubset('\u0600-\u06FF'),
    'IsSyriac': UnicodeSubset('\u0700-\u074F'),
    'IsThaana': UnicodeSubset('\u0780-\u07BF'),
    'IsDevanagari': UnicodeSubset('\u0900-\u097F'),
    'IsBengali': UnicodeSubset('\u0980-\u09FF'),
    'IsGurmukhi': UnicodeSubset('\u0A00-\u0A7F'),
    'IsGujarati': UnicodeSubset('\u0A80-\u0AFF'),
    'IsOriya': UnicodeSubset('\u0B00-\u0B7F'),
    'IsTamil': UnicodeSubset('\u0B80-\u0BFF'),
    'IsTelugu': UnicodeSubset('\u0C00-\u0C7F'),
    'IsKannada': UnicodeSubset('\u0C80-\u0CFF'),
    'IsMalayalam': UnicodeSubset('\u0D00-\u0D7F'),
    'IsSinhala': UnicodeSubset('\u0D80-\u0DFF'),
    'IsThai': UnicodeSubset('\u0E00-\u0E7F'),
    'IsLao': UnicodeSubset('\u0E80-\u0EFF'),
    'IsTibetan': UnicodeSubset('\u0F00-\u0FFF'),
    'IsMyanmar': UnicodeSubset('\u1000-\u109F'),
    'IsGeorgian': UnicodeSubset('\u10A0-\u10FF'),
    'IsHangulJamo': UnicodeSubset('\u1100-\u11FF'),
    'IsEthiopic': UnicodeSubset('\u1200-\u137F'),
    'IsCherokee': UnicodeSubset('\u13A0-\u13FF'),
    'IsUnifiedCanadianAboriginalSyllabics': UnicodeSubset('\u1400-\u167F'),
    'IsOgham': UnicodeSubset('\u1680-\u169F'),
    'IsRunic': UnicodeSubset('\u16A0-\u16FF'),
    'IsKhmer': UnicodeSubset('\u1780-\u17FF'),
    'IsMongolian': UnicodeSubset('\u1800-\u18AF'),
    'IsLatinExtendedAdditional': UnicodeSubset('\u1E00-\u1EFF'),
    'IsGreekExtended': UnicodeSubset('\u1F00-\u1FFF'),
    'IsGeneralPunctuation': UnicodeSubset('\u2000-\u206F'),
    'IsSuperscriptsandSubscripts': UnicodeSubset('\u2070-\u209F'),
    'IsCurrencySymbols': UnicodeSubset('\u20A0-\u20CF'),
    'IsCombiningMarksforSymbols': UnicodeSubset('\u20D0-\u20FF'),
    'IsLetterlikeSymbols': UnicodeSubset('\u2100-\u214F'),
    'IsNumberForms': UnicodeSubset('\u2150-\u218F'),
    'IsArrows': UnicodeSubset('\u2190-\u21FF'),
    'IsMathematicalOperators': UnicodeSubset('\u2200-\u22FF'),
    'IsMiscellaneousTechnical': UnicodeSubset('\u2300-\u23FF'),
    'IsControlPictures': UnicodeSubset('\u2400-\u243F'),
    'IsOpticalCharacterRecognition': UnicodeSubset('\u2440-\u245F'),
    'IsEnclosedAlphanumerics': UnicodeSubset('\u2460-\u24FF'),
    'IsBoxDrawing': UnicodeSubset('\u2500-\u257F'),
    'IsBlockElements': UnicodeSubset('\u2580-\u259F'),
    'IsGeometricShapes': UnicodeSubset('\u25A0-\u25FF'),
    'IsMiscellaneousSymbols': UnicodeSubset('\u2600-\u26FF'),
    'IsDingbats': UnicodeSubset('\u2700-\u27BF'),
    'IsBraillePatterns': UnicodeSubset('\u2800-\u28FF'),
    'IsCJKRadicalsSupplement': UnicodeSubset('\u2E80-\u2EFF'),
    'IsKangxiRadicals': UnicodeSubset('\u2F00-\u2FDF'),
    'IsIdeographicDescriptionCharacters': UnicodeSubset('\u2FF0-\u2FFF'),
    'IsCJKSymbolsandPunctuation': UnicodeSubset('\u3000-\u303F'),
    'IsHiragana': UnicodeSubset('\u3040-\u309F'),
    'IsKatakana': UnicodeSubset('\u30A0-\u30FF'),
    'IsBopomofo': UnicodeSubset('\u3100-\u312F'),
    'IsHangulCompatibilityJamo': UnicodeSubset('\u3130-\u318F'),
    'IsKanbun': UnicodeSubset('\u3190-\u319F'),
    'IsBopomofoExtended': UnicodeSubset('\u31A0-\u31BF'),
    'IsEnclosedCJKLettersandMonths': UnicodeSubset('\u3200-\u32FF'),
    'IsCJKCompatibility': UnicodeSubset('\u3300-\u33FF'),
    'IsCJKUnifiedIdeographsExtensionA': UnicodeSubset('\u3400-\u4DB5'),
    'IsCJKUnifiedIdeographs': UnicodeSubset('\u4E00-\u9FFF'),
    'IsYiSyllables': UnicodeSubset('\uA000-\uA48F'),
    'IsYiRadicals': UnicodeSubset('\uA490-\uA4CF'),
    'IsHangulSyllables': UnicodeSubset('\uAC00-\uD7A3'),
    'IsHighSurrogates': UnicodeSubset('\uD800-\uDB7F'),
    'IsHighPrivateUseSurrogates': UnicodeSubset('\uDB80-\uDBFF'),
    'IsLowSurrogates': UnicodeSubset('\uDC00-\uDFFF'),
    'IsPrivateUse': UnicodeSubset('\uE000-\uF8FF\U000F0000-\U000FFFFF\U00100000-\U0010FFFF'),
    'IsCJKCompatibilityIdeographs': UnicodeSubset('\uF900-\uFAFF'),
    'IsAlphabeticPresentationForms': UnicodeSubset('\uFB00-\uFB4F'),
    'IsArabicPresentationForms-A': UnicodeSubset('\uFB50-\uFDFF'),
    'IsCombiningHalfMarks': UnicodeSubset('\uFE20-\uFE2F'),
    'IsCJKCompatibilityForms': UnicodeSubset('\uFE30-\uFE4F'),
    'IsSmallFormVariants': UnicodeSubset('\uFE50-\uFE6F'),
    'IsArabicPresentationForms-B': UnicodeSubset('\uFE70-\uFEFE'),
    'IsSpecials': UnicodeSubset('\uFEFF\uFFF0-\uFFFD'),
    'IsHalfwidthandFullwidthForms': UnicodeSubset('\uFF00-\uFFEF'),
    'IsOldItalic': UnicodeSubset('\U00010300-\U0001032F'),
    'IsGothic': UnicodeSubset('\U00010330-\U0001034F'),
    'IsDeseret': UnicodeSubset('\U00010400-\U0001044F'),
    'IsByzantineMusicalSymbols': UnicodeSubset('\U0001D000-\U0001D0FF'),
    'IsMusicalSymbols': UnicodeSubset('\U0001D100-\U0001D1FF'),
    'IsMathematicalAlphanumericSymbols': UnicodeSubset('\U0001D400-\U0001D7FF'),
    'IsEmoticons': UnicodeSubset('\U0001F600-\U0001F64F'),
    'IsCJKUnifiedIdeographsExtensionB': UnicodeSubset('\U00020000-\U0002A6D6'),
    'IsCJKCompatibilityIdeographsSupplement': UnicodeSubset('\U0002F800-\U0002FA1F'),
    'IsTags': UnicodeSubset('\U000E0000-\U000E007F'),
}

UNICODE_BLOCKS['IsPrivateUse'].update('\U000F0000-\U0010FFFD')


def unicode_subset(name: str) -> UnicodeSubset:
    if name.startswith('Is'):
        try:
            return UNICODE_BLOCKS[name]
        except KeyError:
            raise RegexError("%r doesn't match to any Unicode block." % name)
    else:
        try:
            return UNICODE_CATEGORIES[name]
        except KeyError:
            raise RegexError("%r doesn't match to any Unicode category." % name)
