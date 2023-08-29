#
# Copyright (c), 2018-2020, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
# mypy: ignore-errors
"""Codepoints module generator utility."""

CATEGORIES_TEMPLATE = """#
# Copyright (c), 2018-2020, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
# --- Auto-generated code: don't edit this file ---
#
# Unicode data version {0}
#
RAW_UNICODE_CATEGORIES = {{
    {1}
}}
"""


def get_unicodedata_categories():
    """
    Extracts Unicode categories information from unicodedata library. Each category is
    represented with an ordered list containing code points and code point ranges.

    :return: a dictionary with category names as keys and lists as values.
    """
    categories = {k: [] for k in (
        'C', 'Cc', 'Cf', 'Cs', 'Co', 'Cn',
        'L', 'Lu', 'Ll', 'Lt', 'Lm', 'Lo',
        'M', 'Mn', 'Mc', 'Me',
        'N', 'Nd', 'Nl', 'No',
        'P', 'Pc', 'Pd', 'Ps', 'Pe', 'Pi', 'Pf', 'Po',
        'S', 'Sm', 'Sc', 'Sk', 'So',
        'Z', 'Zs', 'Zl', 'Zp'
    )}

    # Generate major categories
    major_category = 'C'
    start_cp, next_cp = 0, 1
    for cp in range(maxunicode + 1):
        if category(chr(cp))[0] != major_category:
            if cp > next_cp:
                categories[major_category].append((start_cp, cp))
            else:
                categories[major_category].append(start_cp)

            major_category = category(chr(cp))[0]
            start_cp, next_cp = cp, cp + 1
    else:
        if next_cp == maxunicode + 1:
            categories[major_category].append(start_cp)
        else:
            categories[major_category].append((start_cp, maxunicode + 1))

    # Generate minor categories
    minor_category = 'Cc'
    start_cp, next_cp = 0, 1
    for cp in range(maxunicode + 1):
        if category(chr(cp)) != minor_category:
            if cp > next_cp:
                categories[minor_category].append((start_cp, cp))
            else:
                categories[minor_category].append(start_cp)

            minor_category = category(chr(cp))
            start_cp, next_cp = cp, cp + 1
    else:
        if next_cp == maxunicode + 1:
            categories[minor_category].append(start_cp)
        else:
            categories[minor_category].append((start_cp, maxunicode + 1))

    return categories


if __name__ == '__main__':
    import argparse
    import pprint
    import os
    from sys import maxunicode
    from unicodedata import category, unidata_version

    parser = argparse.ArgumentParser(description="Generate Unicode categories module.")
    parser.add_argument('dirpath', type=str, nargs='?',
                        default=os.path.dirname(__file__),
                        help="alternative directory path for generated module.")
    args = parser.parse_args()

    print("+++ Generate Unicode categories module +++\n")
    print("Unicode data version {}\n".format(unidata_version))

    filename = os.path.join(args.dirpath, 'unicode_categories.py')
    if os.path.isfile(filename):
        confirm = input("Overwrite existing module %r? [Y/Yes to confirm] " % filename)
        if confirm.upper() not in ('Y', 'YES'):
            print("Generation not confirmed: exiting ...")
            exit()

    print("Saving Unicode categories codepoints to %r" % filename)

    with open(filename, 'w') as fp:
        categories_repr = pprint.pformat(get_unicodedata_categories(), compact=True)
        indented_repr = '\n   '.join(categories_repr[1:-1].split('\n'))
        fp.write(CATEGORIES_TEMPLATE.format(unidata_version, indented_repr))
