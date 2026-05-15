# -*- coding: utf-8 -*-

# public api to export
__all__ = [
    'camel_case_to_snake',
    'snake_case_to_camel',
    'reverse',
    'shuffle',
    'strip_html',
    'prettify',
    'asciify',
    'slugify',
    'booleanize',
    'strip_margin',
    'compress',
    'decompress',
    'roman_encode',
    'roman_decode',
]

import base64
import random
import unicodedata
import zlib
from typing import Union
from uuid import uuid4

from aux_mod._regex import *
from aux_mod.errors import InvalidInputError
from aux_mod.validation import is_snake_case, is_full_string, is_camel_case, is_integer, is_string
from typing import Annotated
from typing import Callable
from typing import ClassVar

MutantDict = Annotated[dict[str, Callable], "Mutant"] # type: ignore


def _mutmut_trampoline(orig, mutants, call_args, call_kwargs, self_arg = None): # type: ignore
    """Forward call to original or mutated function, depending on the environment"""
    import os # type: ignore
    mutant_under_test = os.environ['MUTANT_UNDER_TEST'] # type: ignore
    if mutant_under_test == 'fail': # type: ignore
        from mutmut.__main__ import MutmutProgrammaticFailException # type: ignore
        raise MutmutProgrammaticFailException('Failed programmatically')       # type: ignore
    elif mutant_under_test == 'stats': # type: ignore
        from mutmut.__main__ import record_trampoline_hit # type: ignore
        record_trampoline_hit(orig.__module__ + '.' + orig.__name__) # type: ignore
        # (for class methods, orig is bound and thus does not need the explicit self argument)
        result = orig(*call_args, **call_kwargs) # type: ignore
        return result # type: ignore
    prefix = orig.__module__ + '.' + orig.__name__ + '__mutmut_' # type: ignore
    if not mutant_under_test.startswith(prefix): # type: ignore
        result = orig(*call_args, **call_kwargs) # type: ignore
        return result # type: ignore
    mutant_name = mutant_under_test.rpartition('.')[-1] # type: ignore
    if self_arg is not None: # type: ignore
        # call to a class method where self is not bound
        result = mutants[mutant_name](self_arg, *call_args, **call_kwargs) # type: ignore
    else:
        result = mutants[mutant_name](*call_args, **call_kwargs) # type: ignore
    return result # type: ignore


# PRIVATE API


class __RomanNumbers:
    # internal rule mappings for encode()
    __mappings = [
        # units
        {1: 'I', 5: 'V'},
        # tens
        {1: 'X', 5: 'L'},
        # hundreds
        {1: 'C', 5: 'D'},
        # thousands
        {1: 'M'},
    ]

    # swap key/value definitions for decode()
    __reversed_mappings = [{v: k for k, v in m.items()} for m in __mappings]

    @classmethod
    def __encode_digit(cls, index: int, value: int) -> str:
        # if digit is zero, there is no sign to display
        if value == 0:
            return ''

        # from 1 to 3 we have just to repeat the sign N times (eg: III, XXX...)
        if value <= 3:
            return cls.__mappings[index][1] * value

        # if 4 we have to add unit prefix
        if value == 4:
            return cls.__mappings[index][1] + cls.__mappings[index][5]

        # if is 5, is a straight map
        if value == 5:
            return cls.__mappings[index][5]

        # if 6, 7 or 8 we have to append unit suffixes
        if value <= 8:
            suffix = cls.__mappings[index][1] * (value - 5)
            return cls.__mappings[index][5] + suffix

        # if 9 we have to prepend current unit to next
        return cls.__mappings[index][1] + cls.__mappings[index + 1][1]

    @classmethod
    def encode(cls, input_number: Union[str, int]) -> str:
        # force input conversion to a string (we need it in order to iterate on each digit)
        input_string = str(input_number)

        if not is_integer(input_string):
            raise ValueError('Invalid input, only strings or integers are allowed')

        value = int(input_string)

        if value < 1 or value > 3999:
            raise ValueError('Input must be >= 1 and <= 3999')

        input_len = len(input_string)
        output = ''

        # decode digits from right to left (start from units to thousands)
        for index in range(input_len):
            # get actual digit value as int
            digit = int(input_string[input_len - index - 1])

            # encode digit to roman string
            encoded_digit = cls.__encode_digit(index, digit)

            # prepend encoded value to the current output in order to have the final string sorted
            # from thousands to units
            output = encoded_digit + output

        return output

    @classmethod
    def __index_for_sign(cls, sign: str) -> int:
        for index, mapping in enumerate(cls.__reversed_mappings):
            if sign in mapping:
                return index

        raise ValueError('Invalid token found: "{}"'.format(sign))

    @classmethod
    def decode(cls, input_string: str) -> int:
        if not is_full_string(input_string):
            raise ValueError('Input must be a non empty string')

        # reverse the provided string so that we can start parsing from units to thousands
        reversed_string = reverse(input_string.upper())

        # track last used value
        last_value = None

        # computed number to return
        output = 0

        # for each sign in the string we get its numeric value and add or subtract it to the computed output
        for sign in reversed_string:
            # are we dealing with units, tens, hundreds or thousands?
            index = cls.__index_for_sign(sign)

            # it's basically 1 or 5 (based on mapping rules definitions)
            key_value = cls.__reversed_mappings[index][sign]

            # Based on the level (tens, hundreds...) we have to add as many zeroes as the level into which we are
            # in order to have the actual sign value.
            # For instance, if we are at level 2 we are dealing with hundreds, therefore instead of 1 or 5, we will
            # obtain 100 or 500 by adding 2 zeroes
            sign_value = int(str(key_value) + '0' * index)

            # increase total value if we are moving on with level
            if last_value is None or sign_value >= last_value:
                output += sign_value

            # Decrease value if we are back to a previous level
            # For instance, if we are parsing "IX", we first encounter "X" which is ten then "I" which is unit,
            # So we have to do the following operation in order to get 9 (the final result): 10 - 1
            else:
                output -= sign_value

            last_value = sign_value

        return output


class __StringCompressor:

    @staticmethod
    def __require_valid_input_and_encoding(input_string: str, encoding: str):
        if not is_string(input_string):
            raise InvalidInputError(input_string)

        if len(input_string) == 0:
            raise ValueError('Input string cannot be empty')

        if not is_string(encoding):
            raise ValueError('Invalid encoding')

    @classmethod
    def compress(cls, input_string: str, encoding: str = 'utf-8', compression_level: int = 9) -> str:
        cls.__require_valid_input_and_encoding(input_string, encoding)

        if not isinstance(compression_level, int) or compression_level < 0 or compression_level > 9:
            raise ValueError('Invalid compression_level: it must be an "int" between 0 and 9')

        # turns input string into a sequence of bytes using provided encoding
        original_bytes = input_string.encode(encoding)

        # compress bytes using zlib library
        compressed_bytes = zlib.compress(original_bytes, compression_level)

        # encode compressed bytes using base64
        # (this ensure that all characters will be available and that the output string can be used safely in any
        # context such URLs)
        encoded_bytes = base64.urlsafe_b64encode(compressed_bytes)

        # finally turns base64 bytes into a string
        output = encoded_bytes.decode(encoding)

        return output

    @classmethod
    def decompress(cls, input_string: str, encoding: str = 'utf-8') -> str:
        cls.__require_valid_input_and_encoding(input_string, encoding)

        # turns input string into a sequence of bytes
        # (the string is assumed to be a previously compressed string, therefore we have to decode it using base64)
        input_bytes = base64.urlsafe_b64decode(input_string)

        # decompress bytes using zlib
        decompressed_bytes = zlib.decompress(input_bytes)

        # decode the decompressed bytes to get the original string back
        original_string = decompressed_bytes.decode(encoding)

        return original_string


class __StringFormatter:
    def __init__(self, input_string):
        args = [input_string]# type: ignore
        kwargs = {}# type: ignore
        return _mutmut_trampoline(object.__getattribute__(self, 'xǁ__StringFormatterǁ__init____mutmut_orig'), object.__getattribute__(self, 'xǁ__StringFormatterǁ__init____mutmut_mutants'), args, kwargs, self)
    def xǁ__StringFormatterǁ__init____mutmut_orig(self, input_string):
        if not is_string(input_string):
            raise InvalidInputError(input_string)

        self.input_string = input_string
    def xǁ__StringFormatterǁ__init____mutmut_1(self, input_string):
        if is_string(input_string):
            raise InvalidInputError(input_string)

        self.input_string = input_string
    def xǁ__StringFormatterǁ__init____mutmut_2(self, input_string):
        if not is_string(None):
            raise InvalidInputError(input_string)

        self.input_string = input_string
    def xǁ__StringFormatterǁ__init____mutmut_3(self, input_string):
        if not is_string(input_string):
            raise InvalidInputError(None)

        self.input_string = input_string
    def xǁ__StringFormatterǁ__init____mutmut_4(self, input_string):
        if not is_string(input_string):
            raise InvalidInputError(input_string)

        self.input_string = None
    
    xǁ__StringFormatterǁ__init____mutmut_mutants : ClassVar[MutantDict] = { # type: ignore
    'xǁ__StringFormatterǁ__init____mutmut_1': xǁ__StringFormatterǁ__init____mutmut_1, 
        'xǁ__StringFormatterǁ__init____mutmut_2': xǁ__StringFormatterǁ__init____mutmut_2, 
        'xǁ__StringFormatterǁ__init____mutmut_3': xǁ__StringFormatterǁ__init____mutmut_3, 
        'xǁ__StringFormatterǁ__init____mutmut_4': xǁ__StringFormatterǁ__init____mutmut_4
    }
    xǁ__StringFormatterǁ__init____mutmut_orig.__name__ = 'xǁ__StringFormatterǁ__init__'

    def __uppercase_first_char(self, regex_match):
        args = [regex_match]# type: ignore
        kwargs = {}# type: ignore
        return _mutmut_trampoline(object.__getattribute__(self, 'xǁ__StringFormatterǁ__uppercase_first_char__mutmut_orig'), object.__getattribute__(self, 'xǁ__StringFormatterǁ__uppercase_first_char__mutmut_mutants'), args, kwargs, self)

    def xǁ__StringFormatterǁ__uppercase_first_char__mutmut_orig(self, regex_match):
        return regex_match.group(0).upper()

    def xǁ__StringFormatterǁ__uppercase_first_char__mutmut_1(self, regex_match):
        return regex_match.group(0).lower()

    def xǁ__StringFormatterǁ__uppercase_first_char__mutmut_2(self, regex_match):
        return regex_match.group(None).upper()

    def xǁ__StringFormatterǁ__uppercase_first_char__mutmut_3(self, regex_match):
        return regex_match.group(1).upper()
    
    xǁ__StringFormatterǁ__uppercase_first_char__mutmut_mutants : ClassVar[MutantDict] = { # type: ignore
    'xǁ__StringFormatterǁ__uppercase_first_char__mutmut_1': xǁ__StringFormatterǁ__uppercase_first_char__mutmut_1, 
        'xǁ__StringFormatterǁ__uppercase_first_char__mutmut_2': xǁ__StringFormatterǁ__uppercase_first_char__mutmut_2, 
        'xǁ__StringFormatterǁ__uppercase_first_char__mutmut_3': xǁ__StringFormatterǁ__uppercase_first_char__mutmut_3
    }
    xǁ__StringFormatterǁ__uppercase_first_char__mutmut_orig.__name__ = 'xǁ__StringFormatterǁ__uppercase_first_char'

    def __remove_duplicates(self, regex_match):
        args = [regex_match]# type: ignore
        kwargs = {}# type: ignore
        return _mutmut_trampoline(object.__getattribute__(self, 'xǁ__StringFormatterǁ__remove_duplicates__mutmut_orig'), object.__getattribute__(self, 'xǁ__StringFormatterǁ__remove_duplicates__mutmut_mutants'), args, kwargs, self)

    def xǁ__StringFormatterǁ__remove_duplicates__mutmut_orig(self, regex_match):
        return regex_match.group(1)[0]

    def xǁ__StringFormatterǁ__remove_duplicates__mutmut_1(self, regex_match):
        return regex_match.group(None)[0]

    def xǁ__StringFormatterǁ__remove_duplicates__mutmut_2(self, regex_match):
        return regex_match.group(2)[0]

    def xǁ__StringFormatterǁ__remove_duplicates__mutmut_3(self, regex_match):
        return regex_match.group(1)[1]
    
    xǁ__StringFormatterǁ__remove_duplicates__mutmut_mutants : ClassVar[MutantDict] = { # type: ignore
    'xǁ__StringFormatterǁ__remove_duplicates__mutmut_1': xǁ__StringFormatterǁ__remove_duplicates__mutmut_1, 
        'xǁ__StringFormatterǁ__remove_duplicates__mutmut_2': xǁ__StringFormatterǁ__remove_duplicates__mutmut_2, 
        'xǁ__StringFormatterǁ__remove_duplicates__mutmut_3': xǁ__StringFormatterǁ__remove_duplicates__mutmut_3
    }
    xǁ__StringFormatterǁ__remove_duplicates__mutmut_orig.__name__ = 'xǁ__StringFormatterǁ__remove_duplicates'

    def __uppercase_first_letter_after_sign(self, regex_match):
        args = [regex_match]# type: ignore
        kwargs = {}# type: ignore
        return _mutmut_trampoline(object.__getattribute__(self, 'xǁ__StringFormatterǁ__uppercase_first_letter_after_sign__mutmut_orig'), object.__getattribute__(self, 'xǁ__StringFormatterǁ__uppercase_first_letter_after_sign__mutmut_mutants'), args, kwargs, self)

    def xǁ__StringFormatterǁ__uppercase_first_letter_after_sign__mutmut_orig(self, regex_match):
        match = regex_match.group(1)
        return match[:-1] + match[2].upper()

    def xǁ__StringFormatterǁ__uppercase_first_letter_after_sign__mutmut_1(self, regex_match):
        match = None
        return match[:-1] + match[2].upper()

    def xǁ__StringFormatterǁ__uppercase_first_letter_after_sign__mutmut_2(self, regex_match):
        match = regex_match.group(None)
        return match[:-1] + match[2].upper()

    def xǁ__StringFormatterǁ__uppercase_first_letter_after_sign__mutmut_3(self, regex_match):
        match = regex_match.group(2)
        return match[:-1] + match[2].upper()

    def xǁ__StringFormatterǁ__uppercase_first_letter_after_sign__mutmut_4(self, regex_match):
        match = regex_match.group(1)
        return match[:-1] - match[2].upper()

    def xǁ__StringFormatterǁ__uppercase_first_letter_after_sign__mutmut_5(self, regex_match):
        match = regex_match.group(1)
        return match[:+1] + match[2].upper()

    def xǁ__StringFormatterǁ__uppercase_first_letter_after_sign__mutmut_6(self, regex_match):
        match = regex_match.group(1)
        return match[:-2] + match[2].upper()

    def xǁ__StringFormatterǁ__uppercase_first_letter_after_sign__mutmut_7(self, regex_match):
        match = regex_match.group(1)
        return match[:-1] + match[2].lower()

    def xǁ__StringFormatterǁ__uppercase_first_letter_after_sign__mutmut_8(self, regex_match):
        match = regex_match.group(1)
        return match[:-1] + match[3].upper()
    
    xǁ__StringFormatterǁ__uppercase_first_letter_after_sign__mutmut_mutants : ClassVar[MutantDict] = { # type: ignore
    'xǁ__StringFormatterǁ__uppercase_first_letter_after_sign__mutmut_1': xǁ__StringFormatterǁ__uppercase_first_letter_after_sign__mutmut_1, 
        'xǁ__StringFormatterǁ__uppercase_first_letter_after_sign__mutmut_2': xǁ__StringFormatterǁ__uppercase_first_letter_after_sign__mutmut_2, 
        'xǁ__StringFormatterǁ__uppercase_first_letter_after_sign__mutmut_3': xǁ__StringFormatterǁ__uppercase_first_letter_after_sign__mutmut_3, 
        'xǁ__StringFormatterǁ__uppercase_first_letter_after_sign__mutmut_4': xǁ__StringFormatterǁ__uppercase_first_letter_after_sign__mutmut_4, 
        'xǁ__StringFormatterǁ__uppercase_first_letter_after_sign__mutmut_5': xǁ__StringFormatterǁ__uppercase_first_letter_after_sign__mutmut_5, 
        'xǁ__StringFormatterǁ__uppercase_first_letter_after_sign__mutmut_6': xǁ__StringFormatterǁ__uppercase_first_letter_after_sign__mutmut_6, 
        'xǁ__StringFormatterǁ__uppercase_first_letter_after_sign__mutmut_7': xǁ__StringFormatterǁ__uppercase_first_letter_after_sign__mutmut_7, 
        'xǁ__StringFormatterǁ__uppercase_first_letter_after_sign__mutmut_8': xǁ__StringFormatterǁ__uppercase_first_letter_after_sign__mutmut_8
    }
    xǁ__StringFormatterǁ__uppercase_first_letter_after_sign__mutmut_orig.__name__ = 'xǁ__StringFormatterǁ__uppercase_first_letter_after_sign'

    def __ensure_right_space_only(self, regex_match):
        args = [regex_match]# type: ignore
        kwargs = {}# type: ignore
        return _mutmut_trampoline(object.__getattribute__(self, 'xǁ__StringFormatterǁ__ensure_right_space_only__mutmut_orig'), object.__getattribute__(self, 'xǁ__StringFormatterǁ__ensure_right_space_only__mutmut_mutants'), args, kwargs, self)

    def xǁ__StringFormatterǁ__ensure_right_space_only__mutmut_orig(self, regex_match):
        return regex_match.group(1).strip() + ' '

    def xǁ__StringFormatterǁ__ensure_right_space_only__mutmut_1(self, regex_match):
        return regex_match.group(1).strip() - ' '

    def xǁ__StringFormatterǁ__ensure_right_space_only__mutmut_2(self, regex_match):
        return regex_match.group(None).strip() + ' '

    def xǁ__StringFormatterǁ__ensure_right_space_only__mutmut_3(self, regex_match):
        return regex_match.group(2).strip() + ' '

    def xǁ__StringFormatterǁ__ensure_right_space_only__mutmut_4(self, regex_match):
        return regex_match.group(1).strip() + 'XX XX'
    
    xǁ__StringFormatterǁ__ensure_right_space_only__mutmut_mutants : ClassVar[MutantDict] = { # type: ignore
    'xǁ__StringFormatterǁ__ensure_right_space_only__mutmut_1': xǁ__StringFormatterǁ__ensure_right_space_only__mutmut_1, 
        'xǁ__StringFormatterǁ__ensure_right_space_only__mutmut_2': xǁ__StringFormatterǁ__ensure_right_space_only__mutmut_2, 
        'xǁ__StringFormatterǁ__ensure_right_space_only__mutmut_3': xǁ__StringFormatterǁ__ensure_right_space_only__mutmut_3, 
        'xǁ__StringFormatterǁ__ensure_right_space_only__mutmut_4': xǁ__StringFormatterǁ__ensure_right_space_only__mutmut_4
    }
    xǁ__StringFormatterǁ__ensure_right_space_only__mutmut_orig.__name__ = 'xǁ__StringFormatterǁ__ensure_right_space_only'

    def __ensure_left_space_only(self, regex_match):
        args = [regex_match]# type: ignore
        kwargs = {}# type: ignore
        return _mutmut_trampoline(object.__getattribute__(self, 'xǁ__StringFormatterǁ__ensure_left_space_only__mutmut_orig'), object.__getattribute__(self, 'xǁ__StringFormatterǁ__ensure_left_space_only__mutmut_mutants'), args, kwargs, self)

    def xǁ__StringFormatterǁ__ensure_left_space_only__mutmut_orig(self, regex_match):
        return ' ' + regex_match.group(1).strip()

    def xǁ__StringFormatterǁ__ensure_left_space_only__mutmut_1(self, regex_match):
        return ' ' - regex_match.group(1).strip()

    def xǁ__StringFormatterǁ__ensure_left_space_only__mutmut_2(self, regex_match):
        return 'XX XX' + regex_match.group(1).strip()

    def xǁ__StringFormatterǁ__ensure_left_space_only__mutmut_3(self, regex_match):
        return ' ' + regex_match.group(None).strip()

    def xǁ__StringFormatterǁ__ensure_left_space_only__mutmut_4(self, regex_match):
        return ' ' + regex_match.group(2).strip()
    
    xǁ__StringFormatterǁ__ensure_left_space_only__mutmut_mutants : ClassVar[MutantDict] = { # type: ignore
    'xǁ__StringFormatterǁ__ensure_left_space_only__mutmut_1': xǁ__StringFormatterǁ__ensure_left_space_only__mutmut_1, 
        'xǁ__StringFormatterǁ__ensure_left_space_only__mutmut_2': xǁ__StringFormatterǁ__ensure_left_space_only__mutmut_2, 
        'xǁ__StringFormatterǁ__ensure_left_space_only__mutmut_3': xǁ__StringFormatterǁ__ensure_left_space_only__mutmut_3, 
        'xǁ__StringFormatterǁ__ensure_left_space_only__mutmut_4': xǁ__StringFormatterǁ__ensure_left_space_only__mutmut_4
    }
    xǁ__StringFormatterǁ__ensure_left_space_only__mutmut_orig.__name__ = 'xǁ__StringFormatterǁ__ensure_left_space_only'

    def __ensure_spaces_around(self, regex_match):
        args = [regex_match]# type: ignore
        kwargs = {}# type: ignore
        return _mutmut_trampoline(object.__getattribute__(self, 'xǁ__StringFormatterǁ__ensure_spaces_around__mutmut_orig'), object.__getattribute__(self, 'xǁ__StringFormatterǁ__ensure_spaces_around__mutmut_mutants'), args, kwargs, self)

    def xǁ__StringFormatterǁ__ensure_spaces_around__mutmut_orig(self, regex_match):
        return ' ' + regex_match.group(1).strip() + ' '

    def xǁ__StringFormatterǁ__ensure_spaces_around__mutmut_1(self, regex_match):
        return ' ' + regex_match.group(1).strip() - ' '

    def xǁ__StringFormatterǁ__ensure_spaces_around__mutmut_2(self, regex_match):
        return ' ' - regex_match.group(1).strip() + ' '

    def xǁ__StringFormatterǁ__ensure_spaces_around__mutmut_3(self, regex_match):
        return 'XX XX' + regex_match.group(1).strip() + ' '

    def xǁ__StringFormatterǁ__ensure_spaces_around__mutmut_4(self, regex_match):
        return ' ' + regex_match.group(None).strip() + ' '

    def xǁ__StringFormatterǁ__ensure_spaces_around__mutmut_5(self, regex_match):
        return ' ' + regex_match.group(2).strip() + ' '

    def xǁ__StringFormatterǁ__ensure_spaces_around__mutmut_6(self, regex_match):
        return ' ' + regex_match.group(1).strip() + 'XX XX'
    
    xǁ__StringFormatterǁ__ensure_spaces_around__mutmut_mutants : ClassVar[MutantDict] = { # type: ignore
    'xǁ__StringFormatterǁ__ensure_spaces_around__mutmut_1': xǁ__StringFormatterǁ__ensure_spaces_around__mutmut_1, 
        'xǁ__StringFormatterǁ__ensure_spaces_around__mutmut_2': xǁ__StringFormatterǁ__ensure_spaces_around__mutmut_2, 
        'xǁ__StringFormatterǁ__ensure_spaces_around__mutmut_3': xǁ__StringFormatterǁ__ensure_spaces_around__mutmut_3, 
        'xǁ__StringFormatterǁ__ensure_spaces_around__mutmut_4': xǁ__StringFormatterǁ__ensure_spaces_around__mutmut_4, 
        'xǁ__StringFormatterǁ__ensure_spaces_around__mutmut_5': xǁ__StringFormatterǁ__ensure_spaces_around__mutmut_5, 
        'xǁ__StringFormatterǁ__ensure_spaces_around__mutmut_6': xǁ__StringFormatterǁ__ensure_spaces_around__mutmut_6
    }
    xǁ__StringFormatterǁ__ensure_spaces_around__mutmut_orig.__name__ = 'xǁ__StringFormatterǁ__ensure_spaces_around'

    def __remove_internal_spaces(self, regex_match):
        args = [regex_match]# type: ignore
        kwargs = {}# type: ignore
        return _mutmut_trampoline(object.__getattribute__(self, 'xǁ__StringFormatterǁ__remove_internal_spaces__mutmut_orig'), object.__getattribute__(self, 'xǁ__StringFormatterǁ__remove_internal_spaces__mutmut_mutants'), args, kwargs, self)

    def xǁ__StringFormatterǁ__remove_internal_spaces__mutmut_orig(self, regex_match):
        return regex_match.group(1).strip()

    def xǁ__StringFormatterǁ__remove_internal_spaces__mutmut_1(self, regex_match):
        return regex_match.group(None).strip()

    def xǁ__StringFormatterǁ__remove_internal_spaces__mutmut_2(self, regex_match):
        return regex_match.group(2).strip()
    
    xǁ__StringFormatterǁ__remove_internal_spaces__mutmut_mutants : ClassVar[MutantDict] = { # type: ignore
    'xǁ__StringFormatterǁ__remove_internal_spaces__mutmut_1': xǁ__StringFormatterǁ__remove_internal_spaces__mutmut_1, 
        'xǁ__StringFormatterǁ__remove_internal_spaces__mutmut_2': xǁ__StringFormatterǁ__remove_internal_spaces__mutmut_2
    }
    xǁ__StringFormatterǁ__remove_internal_spaces__mutmut_orig.__name__ = 'xǁ__StringFormatterǁ__remove_internal_spaces'

    def __fix_saxon_genitive(self, regex_match):
        args = [regex_match]# type: ignore
        kwargs = {}# type: ignore
        return _mutmut_trampoline(object.__getattribute__(self, 'xǁ__StringFormatterǁ__fix_saxon_genitive__mutmut_orig'), object.__getattribute__(self, 'xǁ__StringFormatterǁ__fix_saxon_genitive__mutmut_mutants'), args, kwargs, self)

    def xǁ__StringFormatterǁ__fix_saxon_genitive__mutmut_orig(self, regex_match):
        return regex_match.group(1).replace(' ', '') + ' '

    def xǁ__StringFormatterǁ__fix_saxon_genitive__mutmut_1(self, regex_match):
        return regex_match.group(1).replace(' ', '') - ' '

    def xǁ__StringFormatterǁ__fix_saxon_genitive__mutmut_2(self, regex_match):
        return regex_match.group(1).replace(None, '') + ' '

    def xǁ__StringFormatterǁ__fix_saxon_genitive__mutmut_3(self, regex_match):
        return regex_match.group(1).replace(' ', None) + ' '

    def xǁ__StringFormatterǁ__fix_saxon_genitive__mutmut_4(self, regex_match):
        return regex_match.group(1).replace('') + ' '

    def xǁ__StringFormatterǁ__fix_saxon_genitive__mutmut_5(self, regex_match):
        return regex_match.group(1).replace(' ', ) + ' '

    def xǁ__StringFormatterǁ__fix_saxon_genitive__mutmut_6(self, regex_match):
        return regex_match.group(None).replace(' ', '') + ' '

    def xǁ__StringFormatterǁ__fix_saxon_genitive__mutmut_7(self, regex_match):
        return regex_match.group(2).replace(' ', '') + ' '

    def xǁ__StringFormatterǁ__fix_saxon_genitive__mutmut_8(self, regex_match):
        return regex_match.group(1).replace('XX XX', '') + ' '

    def xǁ__StringFormatterǁ__fix_saxon_genitive__mutmut_9(self, regex_match):
        return regex_match.group(1).replace(' ', 'XXXX') + ' '

    def xǁ__StringFormatterǁ__fix_saxon_genitive__mutmut_10(self, regex_match):
        return regex_match.group(1).replace(' ', '') + 'XX XX'
    
    xǁ__StringFormatterǁ__fix_saxon_genitive__mutmut_mutants : ClassVar[MutantDict] = { # type: ignore
    'xǁ__StringFormatterǁ__fix_saxon_genitive__mutmut_1': xǁ__StringFormatterǁ__fix_saxon_genitive__mutmut_1, 
        'xǁ__StringFormatterǁ__fix_saxon_genitive__mutmut_2': xǁ__StringFormatterǁ__fix_saxon_genitive__mutmut_2, 
        'xǁ__StringFormatterǁ__fix_saxon_genitive__mutmut_3': xǁ__StringFormatterǁ__fix_saxon_genitive__mutmut_3, 
        'xǁ__StringFormatterǁ__fix_saxon_genitive__mutmut_4': xǁ__StringFormatterǁ__fix_saxon_genitive__mutmut_4, 
        'xǁ__StringFormatterǁ__fix_saxon_genitive__mutmut_5': xǁ__StringFormatterǁ__fix_saxon_genitive__mutmut_5, 
        'xǁ__StringFormatterǁ__fix_saxon_genitive__mutmut_6': xǁ__StringFormatterǁ__fix_saxon_genitive__mutmut_6, 
        'xǁ__StringFormatterǁ__fix_saxon_genitive__mutmut_7': xǁ__StringFormatterǁ__fix_saxon_genitive__mutmut_7, 
        'xǁ__StringFormatterǁ__fix_saxon_genitive__mutmut_8': xǁ__StringFormatterǁ__fix_saxon_genitive__mutmut_8, 
        'xǁ__StringFormatterǁ__fix_saxon_genitive__mutmut_9': xǁ__StringFormatterǁ__fix_saxon_genitive__mutmut_9, 
        'xǁ__StringFormatterǁ__fix_saxon_genitive__mutmut_10': xǁ__StringFormatterǁ__fix_saxon_genitive__mutmut_10
    }
    xǁ__StringFormatterǁ__fix_saxon_genitive__mutmut_orig.__name__ = 'xǁ__StringFormatterǁ__fix_saxon_genitive'

    # generates a placeholder to inject temporary into the string, it will be replaced with the original
    # value at the end of the process
    @staticmethod
    def __placeholder_key():
        return '$' + uuid4().hex + '$'

    def format(self) -> str:
        args = []# type: ignore
        kwargs = {}# type: ignore
        return _mutmut_trampoline(object.__getattribute__(self, 'xǁ__StringFormatterǁformat__mutmut_orig'), object.__getattribute__(self, 'xǁ__StringFormatterǁformat__mutmut_mutants'), args, kwargs, self)

    def xǁ__StringFormatterǁformat__mutmut_orig(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_1(self) -> str:
        # map of temporary placeholders
        placeholders = None
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_2(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = None

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_3(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update(None)
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_4(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[1] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_5(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(None)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_6(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update(None)

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_7(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(None)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_8(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = None

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_9(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(None, p, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_10(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], None, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_11(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, None)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_12(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(p, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_13(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_14(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, )

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_15(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 2)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_16(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = None
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_17(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(None, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_18(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, None)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_19(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_20(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, )
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_21(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = PRETTIFY_RE['XXUPPERCASE_FIRST_LETTERXX'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_22(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = PRETTIFY_RE['uppercase_first_letter'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_23(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = None
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_24(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(None, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_25(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, None)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_26(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_27(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, )
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_28(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['XXDUPLICATESXX'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_29(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['duplicates'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_30(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = None
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_31(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(None, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_32(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, None)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_33(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_34(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, )
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_35(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['XXRIGHT_SPACEXX'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_36(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['right_space'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_37(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = None
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_38(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(None, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_39(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, None)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_40(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_41(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, )
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_42(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['XXLEFT_SPACEXX'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_43(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['left_space'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_44(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = None
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_45(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(None, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_46(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, None)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_47(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_48(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, )
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_49(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['XXSPACES_AROUNDXX'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_50(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['spaces_around'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_51(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = None
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_52(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(None, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_53(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, None)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_54(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_55(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, )
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_56(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['XXSPACES_INSIDEXX'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_57(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['spaces_inside'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_58(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = None
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_59(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(None, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_60(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, None)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_61(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_62(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, )
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_63(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['XXUPPERCASE_AFTER_SIGNXX'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_64(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['uppercase_after_sign'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_65(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = None
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_66(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(None, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_67(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, None)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_68(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_69(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, )
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_70(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['XXSAXON_GENITIVEXX'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_71(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['saxon_genitive'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_72(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = None

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_73(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = None

        return out

    def xǁ__StringFormatterǁformat__mutmut_74(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(None, placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_75(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, None, 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_76(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], None)

        return out

    def xǁ__StringFormatterǁformat__mutmut_77(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(placeholders[p], 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_78(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, 1)

        return out

    def xǁ__StringFormatterǁformat__mutmut_79(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], )

        return out

    def xǁ__StringFormatterǁformat__mutmut_80(self) -> str:
        # map of temporary placeholders
        placeholders = {}
        out = self.input_string

        # looks for url or email and updates placeholders map with found values
        placeholders.update({self.__placeholder_key(): m[0] for m in URLS_RE.findall(out)})
        placeholders.update({self.__placeholder_key(): m for m in EMAILS_RE.findall(out)})

        # replace original value with the placeholder key
        for p in placeholders:
            out = out.replace(placeholders[p], p, 1)

        out = PRETTIFY_RE['UPPERCASE_FIRST_LETTER'].sub(self.__uppercase_first_char, out)
        out = PRETTIFY_RE['DUPLICATES'].sub(self.__remove_duplicates, out)
        out = PRETTIFY_RE['RIGHT_SPACE'].sub(self.__ensure_right_space_only, out)
        out = PRETTIFY_RE['LEFT_SPACE'].sub(self.__ensure_left_space_only, out)
        out = PRETTIFY_RE['SPACES_AROUND'].sub(self.__ensure_spaces_around, out)
        out = PRETTIFY_RE['SPACES_INSIDE'].sub(self.__remove_internal_spaces, out)
        out = PRETTIFY_RE['UPPERCASE_AFTER_SIGN'].sub(self.__uppercase_first_letter_after_sign, out)
        out = PRETTIFY_RE['SAXON_GENITIVE'].sub(self.__fix_saxon_genitive, out)
        out = out.strip()

        # restore placeholder keys with their associated original value
        for p in placeholders:
            out = out.replace(p, placeholders[p], 2)

        return out
    
    xǁ__StringFormatterǁformat__mutmut_mutants : ClassVar[MutantDict] = { # type: ignore
    'xǁ__StringFormatterǁformat__mutmut_1': xǁ__StringFormatterǁformat__mutmut_1, 
        'xǁ__StringFormatterǁformat__mutmut_2': xǁ__StringFormatterǁformat__mutmut_2, 
        'xǁ__StringFormatterǁformat__mutmut_3': xǁ__StringFormatterǁformat__mutmut_3, 
        'xǁ__StringFormatterǁformat__mutmut_4': xǁ__StringFormatterǁformat__mutmut_4, 
        'xǁ__StringFormatterǁformat__mutmut_5': xǁ__StringFormatterǁformat__mutmut_5, 
        'xǁ__StringFormatterǁformat__mutmut_6': xǁ__StringFormatterǁformat__mutmut_6, 
        'xǁ__StringFormatterǁformat__mutmut_7': xǁ__StringFormatterǁformat__mutmut_7, 
        'xǁ__StringFormatterǁformat__mutmut_8': xǁ__StringFormatterǁformat__mutmut_8, 
        'xǁ__StringFormatterǁformat__mutmut_9': xǁ__StringFormatterǁformat__mutmut_9, 
        'xǁ__StringFormatterǁformat__mutmut_10': xǁ__StringFormatterǁformat__mutmut_10, 
        'xǁ__StringFormatterǁformat__mutmut_11': xǁ__StringFormatterǁformat__mutmut_11, 
        'xǁ__StringFormatterǁformat__mutmut_12': xǁ__StringFormatterǁformat__mutmut_12, 
        'xǁ__StringFormatterǁformat__mutmut_13': xǁ__StringFormatterǁformat__mutmut_13, 
        'xǁ__StringFormatterǁformat__mutmut_14': xǁ__StringFormatterǁformat__mutmut_14, 
        'xǁ__StringFormatterǁformat__mutmut_15': xǁ__StringFormatterǁformat__mutmut_15, 
        'xǁ__StringFormatterǁformat__mutmut_16': xǁ__StringFormatterǁformat__mutmut_16, 
        'xǁ__StringFormatterǁformat__mutmut_17': xǁ__StringFormatterǁformat__mutmut_17, 
        'xǁ__StringFormatterǁformat__mutmut_18': xǁ__StringFormatterǁformat__mutmut_18, 
        'xǁ__StringFormatterǁformat__mutmut_19': xǁ__StringFormatterǁformat__mutmut_19, 
        'xǁ__StringFormatterǁformat__mutmut_20': xǁ__StringFormatterǁformat__mutmut_20, 
        'xǁ__StringFormatterǁformat__mutmut_21': xǁ__StringFormatterǁformat__mutmut_21, 
        'xǁ__StringFormatterǁformat__mutmut_22': xǁ__StringFormatterǁformat__mutmut_22, 
        'xǁ__StringFormatterǁformat__mutmut_23': xǁ__StringFormatterǁformat__mutmut_23, 
        'xǁ__StringFormatterǁformat__mutmut_24': xǁ__StringFormatterǁformat__mutmut_24, 
        'xǁ__StringFormatterǁformat__mutmut_25': xǁ__StringFormatterǁformat__mutmut_25, 
        'xǁ__StringFormatterǁformat__mutmut_26': xǁ__StringFormatterǁformat__mutmut_26, 
        'xǁ__StringFormatterǁformat__mutmut_27': xǁ__StringFormatterǁformat__mutmut_27, 
        'xǁ__StringFormatterǁformat__mutmut_28': xǁ__StringFormatterǁformat__mutmut_28, 
        'xǁ__StringFormatterǁformat__mutmut_29': xǁ__StringFormatterǁformat__mutmut_29, 
        'xǁ__StringFormatterǁformat__mutmut_30': xǁ__StringFormatterǁformat__mutmut_30, 
        'xǁ__StringFormatterǁformat__mutmut_31': xǁ__StringFormatterǁformat__mutmut_31, 
        'xǁ__StringFormatterǁformat__mutmut_32': xǁ__StringFormatterǁformat__mutmut_32, 
        'xǁ__StringFormatterǁformat__mutmut_33': xǁ__StringFormatterǁformat__mutmut_33, 
        'xǁ__StringFormatterǁformat__mutmut_34': xǁ__StringFormatterǁformat__mutmut_34, 
        'xǁ__StringFormatterǁformat__mutmut_35': xǁ__StringFormatterǁformat__mutmut_35, 
        'xǁ__StringFormatterǁformat__mutmut_36': xǁ__StringFormatterǁformat__mutmut_36, 
        'xǁ__StringFormatterǁformat__mutmut_37': xǁ__StringFormatterǁformat__mutmut_37, 
        'xǁ__StringFormatterǁformat__mutmut_38': xǁ__StringFormatterǁformat__mutmut_38, 
        'xǁ__StringFormatterǁformat__mutmut_39': xǁ__StringFormatterǁformat__mutmut_39, 
        'xǁ__StringFormatterǁformat__mutmut_40': xǁ__StringFormatterǁformat__mutmut_40, 
        'xǁ__StringFormatterǁformat__mutmut_41': xǁ__StringFormatterǁformat__mutmut_41, 
        'xǁ__StringFormatterǁformat__mutmut_42': xǁ__StringFormatterǁformat__mutmut_42, 
        'xǁ__StringFormatterǁformat__mutmut_43': xǁ__StringFormatterǁformat__mutmut_43, 
        'xǁ__StringFormatterǁformat__mutmut_44': xǁ__StringFormatterǁformat__mutmut_44, 
        'xǁ__StringFormatterǁformat__mutmut_45': xǁ__StringFormatterǁformat__mutmut_45, 
        'xǁ__StringFormatterǁformat__mutmut_46': xǁ__StringFormatterǁformat__mutmut_46, 
        'xǁ__StringFormatterǁformat__mutmut_47': xǁ__StringFormatterǁformat__mutmut_47, 
        'xǁ__StringFormatterǁformat__mutmut_48': xǁ__StringFormatterǁformat__mutmut_48, 
        'xǁ__StringFormatterǁformat__mutmut_49': xǁ__StringFormatterǁformat__mutmut_49, 
        'xǁ__StringFormatterǁformat__mutmut_50': xǁ__StringFormatterǁformat__mutmut_50, 
        'xǁ__StringFormatterǁformat__mutmut_51': xǁ__StringFormatterǁformat__mutmut_51, 
        'xǁ__StringFormatterǁformat__mutmut_52': xǁ__StringFormatterǁformat__mutmut_52, 
        'xǁ__StringFormatterǁformat__mutmut_53': xǁ__StringFormatterǁformat__mutmut_53, 
        'xǁ__StringFormatterǁformat__mutmut_54': xǁ__StringFormatterǁformat__mutmut_54, 
        'xǁ__StringFormatterǁformat__mutmut_55': xǁ__StringFormatterǁformat__mutmut_55, 
        'xǁ__StringFormatterǁformat__mutmut_56': xǁ__StringFormatterǁformat__mutmut_56, 
        'xǁ__StringFormatterǁformat__mutmut_57': xǁ__StringFormatterǁformat__mutmut_57, 
        'xǁ__StringFormatterǁformat__mutmut_58': xǁ__StringFormatterǁformat__mutmut_58, 
        'xǁ__StringFormatterǁformat__mutmut_59': xǁ__StringFormatterǁformat__mutmut_59, 
        'xǁ__StringFormatterǁformat__mutmut_60': xǁ__StringFormatterǁformat__mutmut_60, 
        'xǁ__StringFormatterǁformat__mutmut_61': xǁ__StringFormatterǁformat__mutmut_61, 
        'xǁ__StringFormatterǁformat__mutmut_62': xǁ__StringFormatterǁformat__mutmut_62, 
        'xǁ__StringFormatterǁformat__mutmut_63': xǁ__StringFormatterǁformat__mutmut_63, 
        'xǁ__StringFormatterǁformat__mutmut_64': xǁ__StringFormatterǁformat__mutmut_64, 
        'xǁ__StringFormatterǁformat__mutmut_65': xǁ__StringFormatterǁformat__mutmut_65, 
        'xǁ__StringFormatterǁformat__mutmut_66': xǁ__StringFormatterǁformat__mutmut_66, 
        'xǁ__StringFormatterǁformat__mutmut_67': xǁ__StringFormatterǁformat__mutmut_67, 
        'xǁ__StringFormatterǁformat__mutmut_68': xǁ__StringFormatterǁformat__mutmut_68, 
        'xǁ__StringFormatterǁformat__mutmut_69': xǁ__StringFormatterǁformat__mutmut_69, 
        'xǁ__StringFormatterǁformat__mutmut_70': xǁ__StringFormatterǁformat__mutmut_70, 
        'xǁ__StringFormatterǁformat__mutmut_71': xǁ__StringFormatterǁformat__mutmut_71, 
        'xǁ__StringFormatterǁformat__mutmut_72': xǁ__StringFormatterǁformat__mutmut_72, 
        'xǁ__StringFormatterǁformat__mutmut_73': xǁ__StringFormatterǁformat__mutmut_73, 
        'xǁ__StringFormatterǁformat__mutmut_74': xǁ__StringFormatterǁformat__mutmut_74, 
        'xǁ__StringFormatterǁformat__mutmut_75': xǁ__StringFormatterǁformat__mutmut_75, 
        'xǁ__StringFormatterǁformat__mutmut_76': xǁ__StringFormatterǁformat__mutmut_76, 
        'xǁ__StringFormatterǁformat__mutmut_77': xǁ__StringFormatterǁformat__mutmut_77, 
        'xǁ__StringFormatterǁformat__mutmut_78': xǁ__StringFormatterǁformat__mutmut_78, 
        'xǁ__StringFormatterǁformat__mutmut_79': xǁ__StringFormatterǁformat__mutmut_79, 
        'xǁ__StringFormatterǁformat__mutmut_80': xǁ__StringFormatterǁformat__mutmut_80
    }
    xǁ__StringFormatterǁformat__mutmut_orig.__name__ = 'xǁ__StringFormatterǁformat'


# PUBLIC API

def reverse(input_string: str) -> str:
    args = [input_string]# type: ignore
    kwargs = {}# type: ignore
    return _mutmut_trampoline(x_reverse__mutmut_orig, x_reverse__mutmut_mutants, args, kwargs, None)


# PUBLIC API

def x_reverse__mutmut_orig(input_string: str) -> str:
    """
    Returns the string with its chars reversed.

    *Example:*

    >>> reverse('hello') # returns 'olleh'

    :param input_string: String to revert.
    :type input_string: str
    :return: Reversed string.
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    return input_string[::-1]


# PUBLIC API

def x_reverse__mutmut_1(input_string: str) -> str:
    """
    Returns the string with its chars reversed.

    *Example:*

    >>> reverse('hello') # returns 'olleh'

    :param input_string: String to revert.
    :type input_string: str
    :return: Reversed string.
    """
    if is_string(input_string):
        raise InvalidInputError(input_string)

    return input_string[::-1]


# PUBLIC API

def x_reverse__mutmut_2(input_string: str) -> str:
    """
    Returns the string with its chars reversed.

    *Example:*

    >>> reverse('hello') # returns 'olleh'

    :param input_string: String to revert.
    :type input_string: str
    :return: Reversed string.
    """
    if not is_string(None):
        raise InvalidInputError(input_string)

    return input_string[::-1]


# PUBLIC API

def x_reverse__mutmut_3(input_string: str) -> str:
    """
    Returns the string with its chars reversed.

    *Example:*

    >>> reverse('hello') # returns 'olleh'

    :param input_string: String to revert.
    :type input_string: str
    :return: Reversed string.
    """
    if not is_string(input_string):
        raise InvalidInputError(None)

    return input_string[::-1]


# PUBLIC API

def x_reverse__mutmut_4(input_string: str) -> str:
    """
    Returns the string with its chars reversed.

    *Example:*

    >>> reverse('hello') # returns 'olleh'

    :param input_string: String to revert.
    :type input_string: str
    :return: Reversed string.
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    return input_string[::+1]


# PUBLIC API

def x_reverse__mutmut_5(input_string: str) -> str:
    """
    Returns the string with its chars reversed.

    *Example:*

    >>> reverse('hello') # returns 'olleh'

    :param input_string: String to revert.
    :type input_string: str
    :return: Reversed string.
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    return input_string[::-2]

x_reverse__mutmut_mutants : ClassVar[MutantDict] = { # type: ignore
'x_reverse__mutmut_1': x_reverse__mutmut_1, 
    'x_reverse__mutmut_2': x_reverse__mutmut_2, 
    'x_reverse__mutmut_3': x_reverse__mutmut_3, 
    'x_reverse__mutmut_4': x_reverse__mutmut_4, 
    'x_reverse__mutmut_5': x_reverse__mutmut_5
}
x_reverse__mutmut_orig.__name__ = 'x_reverse'


def camel_case_to_snake(input_string, separator='_'):
    args = [input_string, separator]# type: ignore
    kwargs = {}# type: ignore
    return _mutmut_trampoline(x_camel_case_to_snake__mutmut_orig, x_camel_case_to_snake__mutmut_mutants, args, kwargs, None)


def x_camel_case_to_snake__mutmut_orig(input_string, separator='_'):
    """
    Convert a camel case string into a snake case one.
    (The original string is returned if is not a valid camel case string)

    *Example:*

    >>> camel_case_to_snake('ThisIsACamelStringTest') # returns 'this_is_a_camel_case_string_test'

    :param input_string: String to convert.
    :type input_string: str
    :param separator: Sign to use as separator.
    :type separator: str
    :return: Converted string.
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    if not is_camel_case(input_string):
        return input_string

    return CAMEL_CASE_REPLACE_RE.sub(lambda m: m.group(1) + separator, input_string).lower()


def x_camel_case_to_snake__mutmut_1(input_string, separator='XX_XX'):
    """
    Convert a camel case string into a snake case one.
    (The original string is returned if is not a valid camel case string)

    *Example:*

    >>> camel_case_to_snake('ThisIsACamelStringTest') # returns 'this_is_a_camel_case_string_test'

    :param input_string: String to convert.
    :type input_string: str
    :param separator: Sign to use as separator.
    :type separator: str
    :return: Converted string.
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    if not is_camel_case(input_string):
        return input_string

    return CAMEL_CASE_REPLACE_RE.sub(lambda m: m.group(1) + separator, input_string).lower()


def x_camel_case_to_snake__mutmut_2(input_string, separator='_'):
    """
    Convert a camel case string into a snake case one.
    (The original string is returned if is not a valid camel case string)

    *Example:*

    >>> camel_case_to_snake('ThisIsACamelStringTest') # returns 'this_is_a_camel_case_string_test'

    :param input_string: String to convert.
    :type input_string: str
    :param separator: Sign to use as separator.
    :type separator: str
    :return: Converted string.
    """
    if is_string(input_string):
        raise InvalidInputError(input_string)

    if not is_camel_case(input_string):
        return input_string

    return CAMEL_CASE_REPLACE_RE.sub(lambda m: m.group(1) + separator, input_string).lower()


def x_camel_case_to_snake__mutmut_3(input_string, separator='_'):
    """
    Convert a camel case string into a snake case one.
    (The original string is returned if is not a valid camel case string)

    *Example:*

    >>> camel_case_to_snake('ThisIsACamelStringTest') # returns 'this_is_a_camel_case_string_test'

    :param input_string: String to convert.
    :type input_string: str
    :param separator: Sign to use as separator.
    :type separator: str
    :return: Converted string.
    """
    if not is_string(None):
        raise InvalidInputError(input_string)

    if not is_camel_case(input_string):
        return input_string

    return CAMEL_CASE_REPLACE_RE.sub(lambda m: m.group(1) + separator, input_string).lower()


def x_camel_case_to_snake__mutmut_4(input_string, separator='_'):
    """
    Convert a camel case string into a snake case one.
    (The original string is returned if is not a valid camel case string)

    *Example:*

    >>> camel_case_to_snake('ThisIsACamelStringTest') # returns 'this_is_a_camel_case_string_test'

    :param input_string: String to convert.
    :type input_string: str
    :param separator: Sign to use as separator.
    :type separator: str
    :return: Converted string.
    """
    if not is_string(input_string):
        raise InvalidInputError(None)

    if not is_camel_case(input_string):
        return input_string

    return CAMEL_CASE_REPLACE_RE.sub(lambda m: m.group(1) + separator, input_string).lower()


def x_camel_case_to_snake__mutmut_5(input_string, separator='_'):
    """
    Convert a camel case string into a snake case one.
    (The original string is returned if is not a valid camel case string)

    *Example:*

    >>> camel_case_to_snake('ThisIsACamelStringTest') # returns 'this_is_a_camel_case_string_test'

    :param input_string: String to convert.
    :type input_string: str
    :param separator: Sign to use as separator.
    :type separator: str
    :return: Converted string.
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    if is_camel_case(input_string):
        return input_string

    return CAMEL_CASE_REPLACE_RE.sub(lambda m: m.group(1) + separator, input_string).lower()


def x_camel_case_to_snake__mutmut_6(input_string, separator='_'):
    """
    Convert a camel case string into a snake case one.
    (The original string is returned if is not a valid camel case string)

    *Example:*

    >>> camel_case_to_snake('ThisIsACamelStringTest') # returns 'this_is_a_camel_case_string_test'

    :param input_string: String to convert.
    :type input_string: str
    :param separator: Sign to use as separator.
    :type separator: str
    :return: Converted string.
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    if not is_camel_case(None):
        return input_string

    return CAMEL_CASE_REPLACE_RE.sub(lambda m: m.group(1) + separator, input_string).lower()


def x_camel_case_to_snake__mutmut_7(input_string, separator='_'):
    """
    Convert a camel case string into a snake case one.
    (The original string is returned if is not a valid camel case string)

    *Example:*

    >>> camel_case_to_snake('ThisIsACamelStringTest') # returns 'this_is_a_camel_case_string_test'

    :param input_string: String to convert.
    :type input_string: str
    :param separator: Sign to use as separator.
    :type separator: str
    :return: Converted string.
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    if not is_camel_case(input_string):
        return input_string

    return CAMEL_CASE_REPLACE_RE.sub(lambda m: m.group(1) + separator, input_string).upper()


def x_camel_case_to_snake__mutmut_8(input_string, separator='_'):
    """
    Convert a camel case string into a snake case one.
    (The original string is returned if is not a valid camel case string)

    *Example:*

    >>> camel_case_to_snake('ThisIsACamelStringTest') # returns 'this_is_a_camel_case_string_test'

    :param input_string: String to convert.
    :type input_string: str
    :param separator: Sign to use as separator.
    :type separator: str
    :return: Converted string.
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    if not is_camel_case(input_string):
        return input_string

    return CAMEL_CASE_REPLACE_RE.sub(None, input_string).lower()


def x_camel_case_to_snake__mutmut_9(input_string, separator='_'):
    """
    Convert a camel case string into a snake case one.
    (The original string is returned if is not a valid camel case string)

    *Example:*

    >>> camel_case_to_snake('ThisIsACamelStringTest') # returns 'this_is_a_camel_case_string_test'

    :param input_string: String to convert.
    :type input_string: str
    :param separator: Sign to use as separator.
    :type separator: str
    :return: Converted string.
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    if not is_camel_case(input_string):
        return input_string

    return CAMEL_CASE_REPLACE_RE.sub(lambda m: m.group(1) + separator, None).lower()


def x_camel_case_to_snake__mutmut_10(input_string, separator='_'):
    """
    Convert a camel case string into a snake case one.
    (The original string is returned if is not a valid camel case string)

    *Example:*

    >>> camel_case_to_snake('ThisIsACamelStringTest') # returns 'this_is_a_camel_case_string_test'

    :param input_string: String to convert.
    :type input_string: str
    :param separator: Sign to use as separator.
    :type separator: str
    :return: Converted string.
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    if not is_camel_case(input_string):
        return input_string

    return CAMEL_CASE_REPLACE_RE.sub(input_string).lower()


def x_camel_case_to_snake__mutmut_11(input_string, separator='_'):
    """
    Convert a camel case string into a snake case one.
    (The original string is returned if is not a valid camel case string)

    *Example:*

    >>> camel_case_to_snake('ThisIsACamelStringTest') # returns 'this_is_a_camel_case_string_test'

    :param input_string: String to convert.
    :type input_string: str
    :param separator: Sign to use as separator.
    :type separator: str
    :return: Converted string.
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    if not is_camel_case(input_string):
        return input_string

    return CAMEL_CASE_REPLACE_RE.sub(lambda m: m.group(1) + separator, ).lower()


def x_camel_case_to_snake__mutmut_12(input_string, separator='_'):
    """
    Convert a camel case string into a snake case one.
    (The original string is returned if is not a valid camel case string)

    *Example:*

    >>> camel_case_to_snake('ThisIsACamelStringTest') # returns 'this_is_a_camel_case_string_test'

    :param input_string: String to convert.
    :type input_string: str
    :param separator: Sign to use as separator.
    :type separator: str
    :return: Converted string.
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    if not is_camel_case(input_string):
        return input_string

    return CAMEL_CASE_REPLACE_RE.sub(lambda m: None, input_string).lower()


def x_camel_case_to_snake__mutmut_13(input_string, separator='_'):
    """
    Convert a camel case string into a snake case one.
    (The original string is returned if is not a valid camel case string)

    *Example:*

    >>> camel_case_to_snake('ThisIsACamelStringTest') # returns 'this_is_a_camel_case_string_test'

    :param input_string: String to convert.
    :type input_string: str
    :param separator: Sign to use as separator.
    :type separator: str
    :return: Converted string.
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    if not is_camel_case(input_string):
        return input_string

    return CAMEL_CASE_REPLACE_RE.sub(lambda m: m.group(1) - separator, input_string).lower()


def x_camel_case_to_snake__mutmut_14(input_string, separator='_'):
    """
    Convert a camel case string into a snake case one.
    (The original string is returned if is not a valid camel case string)

    *Example:*

    >>> camel_case_to_snake('ThisIsACamelStringTest') # returns 'this_is_a_camel_case_string_test'

    :param input_string: String to convert.
    :type input_string: str
    :param separator: Sign to use as separator.
    :type separator: str
    :return: Converted string.
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    if not is_camel_case(input_string):
        return input_string

    return CAMEL_CASE_REPLACE_RE.sub(lambda m: m.group(None) + separator, input_string).lower()


def x_camel_case_to_snake__mutmut_15(input_string, separator='_'):
    """
    Convert a camel case string into a snake case one.
    (The original string is returned if is not a valid camel case string)

    *Example:*

    >>> camel_case_to_snake('ThisIsACamelStringTest') # returns 'this_is_a_camel_case_string_test'

    :param input_string: String to convert.
    :type input_string: str
    :param separator: Sign to use as separator.
    :type separator: str
    :return: Converted string.
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    if not is_camel_case(input_string):
        return input_string

    return CAMEL_CASE_REPLACE_RE.sub(lambda m: m.group(2) + separator, input_string).lower()

x_camel_case_to_snake__mutmut_mutants : ClassVar[MutantDict] = { # type: ignore
'x_camel_case_to_snake__mutmut_1': x_camel_case_to_snake__mutmut_1, 
    'x_camel_case_to_snake__mutmut_2': x_camel_case_to_snake__mutmut_2, 
    'x_camel_case_to_snake__mutmut_3': x_camel_case_to_snake__mutmut_3, 
    'x_camel_case_to_snake__mutmut_4': x_camel_case_to_snake__mutmut_4, 
    'x_camel_case_to_snake__mutmut_5': x_camel_case_to_snake__mutmut_5, 
    'x_camel_case_to_snake__mutmut_6': x_camel_case_to_snake__mutmut_6, 
    'x_camel_case_to_snake__mutmut_7': x_camel_case_to_snake__mutmut_7, 
    'x_camel_case_to_snake__mutmut_8': x_camel_case_to_snake__mutmut_8, 
    'x_camel_case_to_snake__mutmut_9': x_camel_case_to_snake__mutmut_9, 
    'x_camel_case_to_snake__mutmut_10': x_camel_case_to_snake__mutmut_10, 
    'x_camel_case_to_snake__mutmut_11': x_camel_case_to_snake__mutmut_11, 
    'x_camel_case_to_snake__mutmut_12': x_camel_case_to_snake__mutmut_12, 
    'x_camel_case_to_snake__mutmut_13': x_camel_case_to_snake__mutmut_13, 
    'x_camel_case_to_snake__mutmut_14': x_camel_case_to_snake__mutmut_14, 
    'x_camel_case_to_snake__mutmut_15': x_camel_case_to_snake__mutmut_15
}
x_camel_case_to_snake__mutmut_orig.__name__ = 'x_camel_case_to_snake'


def snake_case_to_camel(input_string: str, upper_case_first: bool = True, separator: str = '_') -> str:
    args = [input_string, upper_case_first, separator]# type: ignore
    kwargs = {}# type: ignore
    return _mutmut_trampoline(x_snake_case_to_camel__mutmut_orig, x_snake_case_to_camel__mutmut_mutants, args, kwargs, None)


def x_snake_case_to_camel__mutmut_orig(input_string: str, upper_case_first: bool = True, separator: str = '_') -> str:
    """
    Convert a snake case string into a camel case one.
    (The original string is returned if is not a valid snake case string)

    *Example:*

    >>> snake_case_to_camel('the_snake_is_green') # returns 'TheSnakeIsGreen'

    :param input_string: String to convert.
    :type input_string: str
    :param upper_case_first: True to turn the first letter into uppercase (default).
    :type upper_case_first: bool
    :param separator: Sign to use as separator (default to "_").
    :type separator: str
    :return: Converted string
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    if not is_snake_case(input_string, separator):
        return input_string

    tokens = [s.title() for s in input_string.split(separator) if is_full_string(s)]

    if not upper_case_first:
        tokens[0] = tokens[0].lower()

    out = ''.join(tokens)

    return out


def x_snake_case_to_camel__mutmut_1(input_string: str, upper_case_first: bool = False, separator: str = '_') -> str:
    """
    Convert a snake case string into a camel case one.
    (The original string is returned if is not a valid snake case string)

    *Example:*

    >>> snake_case_to_camel('the_snake_is_green') # returns 'TheSnakeIsGreen'

    :param input_string: String to convert.
    :type input_string: str
    :param upper_case_first: True to turn the first letter into uppercase (default).
    :type upper_case_first: bool
    :param separator: Sign to use as separator (default to "_").
    :type separator: str
    :return: Converted string
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    if not is_snake_case(input_string, separator):
        return input_string

    tokens = [s.title() for s in input_string.split(separator) if is_full_string(s)]

    if not upper_case_first:
        tokens[0] = tokens[0].lower()

    out = ''.join(tokens)

    return out


def x_snake_case_to_camel__mutmut_2(input_string: str, upper_case_first: bool = True, separator: str = 'XX_XX') -> str:
    """
    Convert a snake case string into a camel case one.
    (The original string is returned if is not a valid snake case string)

    *Example:*

    >>> snake_case_to_camel('the_snake_is_green') # returns 'TheSnakeIsGreen'

    :param input_string: String to convert.
    :type input_string: str
    :param upper_case_first: True to turn the first letter into uppercase (default).
    :type upper_case_first: bool
    :param separator: Sign to use as separator (default to "_").
    :type separator: str
    :return: Converted string
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    if not is_snake_case(input_string, separator):
        return input_string

    tokens = [s.title() for s in input_string.split(separator) if is_full_string(s)]

    if not upper_case_first:
        tokens[0] = tokens[0].lower()

    out = ''.join(tokens)

    return out


def x_snake_case_to_camel__mutmut_3(input_string: str, upper_case_first: bool = True, separator: str = '_') -> str:
    """
    Convert a snake case string into a camel case one.
    (The original string is returned if is not a valid snake case string)

    *Example:*

    >>> snake_case_to_camel('the_snake_is_green') # returns 'TheSnakeIsGreen'

    :param input_string: String to convert.
    :type input_string: str
    :param upper_case_first: True to turn the first letter into uppercase (default).
    :type upper_case_first: bool
    :param separator: Sign to use as separator (default to "_").
    :type separator: str
    :return: Converted string
    """
    if is_string(input_string):
        raise InvalidInputError(input_string)

    if not is_snake_case(input_string, separator):
        return input_string

    tokens = [s.title() for s in input_string.split(separator) if is_full_string(s)]

    if not upper_case_first:
        tokens[0] = tokens[0].lower()

    out = ''.join(tokens)

    return out


def x_snake_case_to_camel__mutmut_4(input_string: str, upper_case_first: bool = True, separator: str = '_') -> str:
    """
    Convert a snake case string into a camel case one.
    (The original string is returned if is not a valid snake case string)

    *Example:*

    >>> snake_case_to_camel('the_snake_is_green') # returns 'TheSnakeIsGreen'

    :param input_string: String to convert.
    :type input_string: str
    :param upper_case_first: True to turn the first letter into uppercase (default).
    :type upper_case_first: bool
    :param separator: Sign to use as separator (default to "_").
    :type separator: str
    :return: Converted string
    """
    if not is_string(None):
        raise InvalidInputError(input_string)

    if not is_snake_case(input_string, separator):
        return input_string

    tokens = [s.title() for s in input_string.split(separator) if is_full_string(s)]

    if not upper_case_first:
        tokens[0] = tokens[0].lower()

    out = ''.join(tokens)

    return out


def x_snake_case_to_camel__mutmut_5(input_string: str, upper_case_first: bool = True, separator: str = '_') -> str:
    """
    Convert a snake case string into a camel case one.
    (The original string is returned if is not a valid snake case string)

    *Example:*

    >>> snake_case_to_camel('the_snake_is_green') # returns 'TheSnakeIsGreen'

    :param input_string: String to convert.
    :type input_string: str
    :param upper_case_first: True to turn the first letter into uppercase (default).
    :type upper_case_first: bool
    :param separator: Sign to use as separator (default to "_").
    :type separator: str
    :return: Converted string
    """
    if not is_string(input_string):
        raise InvalidInputError(None)

    if not is_snake_case(input_string, separator):
        return input_string

    tokens = [s.title() for s in input_string.split(separator) if is_full_string(s)]

    if not upper_case_first:
        tokens[0] = tokens[0].lower()

    out = ''.join(tokens)

    return out


def x_snake_case_to_camel__mutmut_6(input_string: str, upper_case_first: bool = True, separator: str = '_') -> str:
    """
    Convert a snake case string into a camel case one.
    (The original string is returned if is not a valid snake case string)

    *Example:*

    >>> snake_case_to_camel('the_snake_is_green') # returns 'TheSnakeIsGreen'

    :param input_string: String to convert.
    :type input_string: str
    :param upper_case_first: True to turn the first letter into uppercase (default).
    :type upper_case_first: bool
    :param separator: Sign to use as separator (default to "_").
    :type separator: str
    :return: Converted string
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    if is_snake_case(input_string, separator):
        return input_string

    tokens = [s.title() for s in input_string.split(separator) if is_full_string(s)]

    if not upper_case_first:
        tokens[0] = tokens[0].lower()

    out = ''.join(tokens)

    return out


def x_snake_case_to_camel__mutmut_7(input_string: str, upper_case_first: bool = True, separator: str = '_') -> str:
    """
    Convert a snake case string into a camel case one.
    (The original string is returned if is not a valid snake case string)

    *Example:*

    >>> snake_case_to_camel('the_snake_is_green') # returns 'TheSnakeIsGreen'

    :param input_string: String to convert.
    :type input_string: str
    :param upper_case_first: True to turn the first letter into uppercase (default).
    :type upper_case_first: bool
    :param separator: Sign to use as separator (default to "_").
    :type separator: str
    :return: Converted string
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    if not is_snake_case(None, separator):
        return input_string

    tokens = [s.title() for s in input_string.split(separator) if is_full_string(s)]

    if not upper_case_first:
        tokens[0] = tokens[0].lower()

    out = ''.join(tokens)

    return out


def x_snake_case_to_camel__mutmut_8(input_string: str, upper_case_first: bool = True, separator: str = '_') -> str:
    """
    Convert a snake case string into a camel case one.
    (The original string is returned if is not a valid snake case string)

    *Example:*

    >>> snake_case_to_camel('the_snake_is_green') # returns 'TheSnakeIsGreen'

    :param input_string: String to convert.
    :type input_string: str
    :param upper_case_first: True to turn the first letter into uppercase (default).
    :type upper_case_first: bool
    :param separator: Sign to use as separator (default to "_").
    :type separator: str
    :return: Converted string
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    if not is_snake_case(input_string, None):
        return input_string

    tokens = [s.title() for s in input_string.split(separator) if is_full_string(s)]

    if not upper_case_first:
        tokens[0] = tokens[0].lower()

    out = ''.join(tokens)

    return out


def x_snake_case_to_camel__mutmut_9(input_string: str, upper_case_first: bool = True, separator: str = '_') -> str:
    """
    Convert a snake case string into a camel case one.
    (The original string is returned if is not a valid snake case string)

    *Example:*

    >>> snake_case_to_camel('the_snake_is_green') # returns 'TheSnakeIsGreen'

    :param input_string: String to convert.
    :type input_string: str
    :param upper_case_first: True to turn the first letter into uppercase (default).
    :type upper_case_first: bool
    :param separator: Sign to use as separator (default to "_").
    :type separator: str
    :return: Converted string
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    if not is_snake_case(separator):
        return input_string

    tokens = [s.title() for s in input_string.split(separator) if is_full_string(s)]

    if not upper_case_first:
        tokens[0] = tokens[0].lower()

    out = ''.join(tokens)

    return out


def x_snake_case_to_camel__mutmut_10(input_string: str, upper_case_first: bool = True, separator: str = '_') -> str:
    """
    Convert a snake case string into a camel case one.
    (The original string is returned if is not a valid snake case string)

    *Example:*

    >>> snake_case_to_camel('the_snake_is_green') # returns 'TheSnakeIsGreen'

    :param input_string: String to convert.
    :type input_string: str
    :param upper_case_first: True to turn the first letter into uppercase (default).
    :type upper_case_first: bool
    :param separator: Sign to use as separator (default to "_").
    :type separator: str
    :return: Converted string
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    if not is_snake_case(input_string, ):
        return input_string

    tokens = [s.title() for s in input_string.split(separator) if is_full_string(s)]

    if not upper_case_first:
        tokens[0] = tokens[0].lower()

    out = ''.join(tokens)

    return out


def x_snake_case_to_camel__mutmut_11(input_string: str, upper_case_first: bool = True, separator: str = '_') -> str:
    """
    Convert a snake case string into a camel case one.
    (The original string is returned if is not a valid snake case string)

    *Example:*

    >>> snake_case_to_camel('the_snake_is_green') # returns 'TheSnakeIsGreen'

    :param input_string: String to convert.
    :type input_string: str
    :param upper_case_first: True to turn the first letter into uppercase (default).
    :type upper_case_first: bool
    :param separator: Sign to use as separator (default to "_").
    :type separator: str
    :return: Converted string
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    if not is_snake_case(input_string, separator):
        return input_string

    tokens = None

    if not upper_case_first:
        tokens[0] = tokens[0].lower()

    out = ''.join(tokens)

    return out


def x_snake_case_to_camel__mutmut_12(input_string: str, upper_case_first: bool = True, separator: str = '_') -> str:
    """
    Convert a snake case string into a camel case one.
    (The original string is returned if is not a valid snake case string)

    *Example:*

    >>> snake_case_to_camel('the_snake_is_green') # returns 'TheSnakeIsGreen'

    :param input_string: String to convert.
    :type input_string: str
    :param upper_case_first: True to turn the first letter into uppercase (default).
    :type upper_case_first: bool
    :param separator: Sign to use as separator (default to "_").
    :type separator: str
    :return: Converted string
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    if not is_snake_case(input_string, separator):
        return input_string

    tokens = [s.title() for s in input_string.split(None) if is_full_string(s)]

    if not upper_case_first:
        tokens[0] = tokens[0].lower()

    out = ''.join(tokens)

    return out


def x_snake_case_to_camel__mutmut_13(input_string: str, upper_case_first: bool = True, separator: str = '_') -> str:
    """
    Convert a snake case string into a camel case one.
    (The original string is returned if is not a valid snake case string)

    *Example:*

    >>> snake_case_to_camel('the_snake_is_green') # returns 'TheSnakeIsGreen'

    :param input_string: String to convert.
    :type input_string: str
    :param upper_case_first: True to turn the first letter into uppercase (default).
    :type upper_case_first: bool
    :param separator: Sign to use as separator (default to "_").
    :type separator: str
    :return: Converted string
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    if not is_snake_case(input_string, separator):
        return input_string

    tokens = [s.title() for s in input_string.split(separator) if is_full_string(None)]

    if not upper_case_first:
        tokens[0] = tokens[0].lower()

    out = ''.join(tokens)

    return out


def x_snake_case_to_camel__mutmut_14(input_string: str, upper_case_first: bool = True, separator: str = '_') -> str:
    """
    Convert a snake case string into a camel case one.
    (The original string is returned if is not a valid snake case string)

    *Example:*

    >>> snake_case_to_camel('the_snake_is_green') # returns 'TheSnakeIsGreen'

    :param input_string: String to convert.
    :type input_string: str
    :param upper_case_first: True to turn the first letter into uppercase (default).
    :type upper_case_first: bool
    :param separator: Sign to use as separator (default to "_").
    :type separator: str
    :return: Converted string
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    if not is_snake_case(input_string, separator):
        return input_string

    tokens = [s.title() for s in input_string.split(separator) if is_full_string(s)]

    if upper_case_first:
        tokens[0] = tokens[0].lower()

    out = ''.join(tokens)

    return out


def x_snake_case_to_camel__mutmut_15(input_string: str, upper_case_first: bool = True, separator: str = '_') -> str:
    """
    Convert a snake case string into a camel case one.
    (The original string is returned if is not a valid snake case string)

    *Example:*

    >>> snake_case_to_camel('the_snake_is_green') # returns 'TheSnakeIsGreen'

    :param input_string: String to convert.
    :type input_string: str
    :param upper_case_first: True to turn the first letter into uppercase (default).
    :type upper_case_first: bool
    :param separator: Sign to use as separator (default to "_").
    :type separator: str
    :return: Converted string
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    if not is_snake_case(input_string, separator):
        return input_string

    tokens = [s.title() for s in input_string.split(separator) if is_full_string(s)]

    if not upper_case_first:
        tokens[0] = None

    out = ''.join(tokens)

    return out


def x_snake_case_to_camel__mutmut_16(input_string: str, upper_case_first: bool = True, separator: str = '_') -> str:
    """
    Convert a snake case string into a camel case one.
    (The original string is returned if is not a valid snake case string)

    *Example:*

    >>> snake_case_to_camel('the_snake_is_green') # returns 'TheSnakeIsGreen'

    :param input_string: String to convert.
    :type input_string: str
    :param upper_case_first: True to turn the first letter into uppercase (default).
    :type upper_case_first: bool
    :param separator: Sign to use as separator (default to "_").
    :type separator: str
    :return: Converted string
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    if not is_snake_case(input_string, separator):
        return input_string

    tokens = [s.title() for s in input_string.split(separator) if is_full_string(s)]

    if not upper_case_first:
        tokens[1] = tokens[0].lower()

    out = ''.join(tokens)

    return out


def x_snake_case_to_camel__mutmut_17(input_string: str, upper_case_first: bool = True, separator: str = '_') -> str:
    """
    Convert a snake case string into a camel case one.
    (The original string is returned if is not a valid snake case string)

    *Example:*

    >>> snake_case_to_camel('the_snake_is_green') # returns 'TheSnakeIsGreen'

    :param input_string: String to convert.
    :type input_string: str
    :param upper_case_first: True to turn the first letter into uppercase (default).
    :type upper_case_first: bool
    :param separator: Sign to use as separator (default to "_").
    :type separator: str
    :return: Converted string
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    if not is_snake_case(input_string, separator):
        return input_string

    tokens = [s.title() for s in input_string.split(separator) if is_full_string(s)]

    if not upper_case_first:
        tokens[0] = tokens[0].upper()

    out = ''.join(tokens)

    return out


def x_snake_case_to_camel__mutmut_18(input_string: str, upper_case_first: bool = True, separator: str = '_') -> str:
    """
    Convert a snake case string into a camel case one.
    (The original string is returned if is not a valid snake case string)

    *Example:*

    >>> snake_case_to_camel('the_snake_is_green') # returns 'TheSnakeIsGreen'

    :param input_string: String to convert.
    :type input_string: str
    :param upper_case_first: True to turn the first letter into uppercase (default).
    :type upper_case_first: bool
    :param separator: Sign to use as separator (default to "_").
    :type separator: str
    :return: Converted string
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    if not is_snake_case(input_string, separator):
        return input_string

    tokens = [s.title() for s in input_string.split(separator) if is_full_string(s)]

    if not upper_case_first:
        tokens[0] = tokens[1].lower()

    out = ''.join(tokens)

    return out


def x_snake_case_to_camel__mutmut_19(input_string: str, upper_case_first: bool = True, separator: str = '_') -> str:
    """
    Convert a snake case string into a camel case one.
    (The original string is returned if is not a valid snake case string)

    *Example:*

    >>> snake_case_to_camel('the_snake_is_green') # returns 'TheSnakeIsGreen'

    :param input_string: String to convert.
    :type input_string: str
    :param upper_case_first: True to turn the first letter into uppercase (default).
    :type upper_case_first: bool
    :param separator: Sign to use as separator (default to "_").
    :type separator: str
    :return: Converted string
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    if not is_snake_case(input_string, separator):
        return input_string

    tokens = [s.title() for s in input_string.split(separator) if is_full_string(s)]

    if not upper_case_first:
        tokens[0] = tokens[0].lower()

    out = None

    return out


def x_snake_case_to_camel__mutmut_20(input_string: str, upper_case_first: bool = True, separator: str = '_') -> str:
    """
    Convert a snake case string into a camel case one.
    (The original string is returned if is not a valid snake case string)

    *Example:*

    >>> snake_case_to_camel('the_snake_is_green') # returns 'TheSnakeIsGreen'

    :param input_string: String to convert.
    :type input_string: str
    :param upper_case_first: True to turn the first letter into uppercase (default).
    :type upper_case_first: bool
    :param separator: Sign to use as separator (default to "_").
    :type separator: str
    :return: Converted string
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    if not is_snake_case(input_string, separator):
        return input_string

    tokens = [s.title() for s in input_string.split(separator) if is_full_string(s)]

    if not upper_case_first:
        tokens[0] = tokens[0].lower()

    out = ''.join(None)

    return out


def x_snake_case_to_camel__mutmut_21(input_string: str, upper_case_first: bool = True, separator: str = '_') -> str:
    """
    Convert a snake case string into a camel case one.
    (The original string is returned if is not a valid snake case string)

    *Example:*

    >>> snake_case_to_camel('the_snake_is_green') # returns 'TheSnakeIsGreen'

    :param input_string: String to convert.
    :type input_string: str
    :param upper_case_first: True to turn the first letter into uppercase (default).
    :type upper_case_first: bool
    :param separator: Sign to use as separator (default to "_").
    :type separator: str
    :return: Converted string
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    if not is_snake_case(input_string, separator):
        return input_string

    tokens = [s.title() for s in input_string.split(separator) if is_full_string(s)]

    if not upper_case_first:
        tokens[0] = tokens[0].lower()

    out = 'XXXX'.join(tokens)

    return out

x_snake_case_to_camel__mutmut_mutants : ClassVar[MutantDict] = { # type: ignore
'x_snake_case_to_camel__mutmut_1': x_snake_case_to_camel__mutmut_1, 
    'x_snake_case_to_camel__mutmut_2': x_snake_case_to_camel__mutmut_2, 
    'x_snake_case_to_camel__mutmut_3': x_snake_case_to_camel__mutmut_3, 
    'x_snake_case_to_camel__mutmut_4': x_snake_case_to_camel__mutmut_4, 
    'x_snake_case_to_camel__mutmut_5': x_snake_case_to_camel__mutmut_5, 
    'x_snake_case_to_camel__mutmut_6': x_snake_case_to_camel__mutmut_6, 
    'x_snake_case_to_camel__mutmut_7': x_snake_case_to_camel__mutmut_7, 
    'x_snake_case_to_camel__mutmut_8': x_snake_case_to_camel__mutmut_8, 
    'x_snake_case_to_camel__mutmut_9': x_snake_case_to_camel__mutmut_9, 
    'x_snake_case_to_camel__mutmut_10': x_snake_case_to_camel__mutmut_10, 
    'x_snake_case_to_camel__mutmut_11': x_snake_case_to_camel__mutmut_11, 
    'x_snake_case_to_camel__mutmut_12': x_snake_case_to_camel__mutmut_12, 
    'x_snake_case_to_camel__mutmut_13': x_snake_case_to_camel__mutmut_13, 
    'x_snake_case_to_camel__mutmut_14': x_snake_case_to_camel__mutmut_14, 
    'x_snake_case_to_camel__mutmut_15': x_snake_case_to_camel__mutmut_15, 
    'x_snake_case_to_camel__mutmut_16': x_snake_case_to_camel__mutmut_16, 
    'x_snake_case_to_camel__mutmut_17': x_snake_case_to_camel__mutmut_17, 
    'x_snake_case_to_camel__mutmut_18': x_snake_case_to_camel__mutmut_18, 
    'x_snake_case_to_camel__mutmut_19': x_snake_case_to_camel__mutmut_19, 
    'x_snake_case_to_camel__mutmut_20': x_snake_case_to_camel__mutmut_20, 
    'x_snake_case_to_camel__mutmut_21': x_snake_case_to_camel__mutmut_21
}
x_snake_case_to_camel__mutmut_orig.__name__ = 'x_snake_case_to_camel'


def shuffle(input_string: str) -> str:
    args = [input_string]# type: ignore
    kwargs = {}# type: ignore
    return _mutmut_trampoline(x_shuffle__mutmut_orig, x_shuffle__mutmut_mutants, args, kwargs, None)


def x_shuffle__mutmut_orig(input_string: str) -> str:
    """
    Return a new string containing same chars of the given one but in a randomized order.

    *Example:*

    >>> shuffle('hello world') # possible output: 'l wodheorll'

    :param input_string: String to shuffle
    :type input_string: str
    :return: Shuffled string
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    # turn the string into a list of chars
    chars = list(input_string)

    # shuffle the list
    random.shuffle(chars)

    # convert the shuffled list back to string
    return ''.join(chars)


def x_shuffle__mutmut_1(input_string: str) -> str:
    """
    Return a new string containing same chars of the given one but in a randomized order.

    *Example:*

    >>> shuffle('hello world') # possible output: 'l wodheorll'

    :param input_string: String to shuffle
    :type input_string: str
    :return: Shuffled string
    """
    if is_string(input_string):
        raise InvalidInputError(input_string)

    # turn the string into a list of chars
    chars = list(input_string)

    # shuffle the list
    random.shuffle(chars)

    # convert the shuffled list back to string
    return ''.join(chars)


def x_shuffle__mutmut_2(input_string: str) -> str:
    """
    Return a new string containing same chars of the given one but in a randomized order.

    *Example:*

    >>> shuffle('hello world') # possible output: 'l wodheorll'

    :param input_string: String to shuffle
    :type input_string: str
    :return: Shuffled string
    """
    if not is_string(None):
        raise InvalidInputError(input_string)

    # turn the string into a list of chars
    chars = list(input_string)

    # shuffle the list
    random.shuffle(chars)

    # convert the shuffled list back to string
    return ''.join(chars)


def x_shuffle__mutmut_3(input_string: str) -> str:
    """
    Return a new string containing same chars of the given one but in a randomized order.

    *Example:*

    >>> shuffle('hello world') # possible output: 'l wodheorll'

    :param input_string: String to shuffle
    :type input_string: str
    :return: Shuffled string
    """
    if not is_string(input_string):
        raise InvalidInputError(None)

    # turn the string into a list of chars
    chars = list(input_string)

    # shuffle the list
    random.shuffle(chars)

    # convert the shuffled list back to string
    return ''.join(chars)


def x_shuffle__mutmut_4(input_string: str) -> str:
    """
    Return a new string containing same chars of the given one but in a randomized order.

    *Example:*

    >>> shuffle('hello world') # possible output: 'l wodheorll'

    :param input_string: String to shuffle
    :type input_string: str
    :return: Shuffled string
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    # turn the string into a list of chars
    chars = None

    # shuffle the list
    random.shuffle(chars)

    # convert the shuffled list back to string
    return ''.join(chars)


def x_shuffle__mutmut_5(input_string: str) -> str:
    """
    Return a new string containing same chars of the given one but in a randomized order.

    *Example:*

    >>> shuffle('hello world') # possible output: 'l wodheorll'

    :param input_string: String to shuffle
    :type input_string: str
    :return: Shuffled string
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    # turn the string into a list of chars
    chars = list(None)

    # shuffle the list
    random.shuffle(chars)

    # convert the shuffled list back to string
    return ''.join(chars)


def x_shuffle__mutmut_6(input_string: str) -> str:
    """
    Return a new string containing same chars of the given one but in a randomized order.

    *Example:*

    >>> shuffle('hello world') # possible output: 'l wodheorll'

    :param input_string: String to shuffle
    :type input_string: str
    :return: Shuffled string
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    # turn the string into a list of chars
    chars = list(input_string)

    # shuffle the list
    random.shuffle(None)

    # convert the shuffled list back to string
    return ''.join(chars)


def x_shuffle__mutmut_7(input_string: str) -> str:
    """
    Return a new string containing same chars of the given one but in a randomized order.

    *Example:*

    >>> shuffle('hello world') # possible output: 'l wodheorll'

    :param input_string: String to shuffle
    :type input_string: str
    :return: Shuffled string
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    # turn the string into a list of chars
    chars = list(input_string)

    # shuffle the list
    random.shuffle(chars)

    # convert the shuffled list back to string
    return ''.join(None)


def x_shuffle__mutmut_8(input_string: str) -> str:
    """
    Return a new string containing same chars of the given one but in a randomized order.

    *Example:*

    >>> shuffle('hello world') # possible output: 'l wodheorll'

    :param input_string: String to shuffle
    :type input_string: str
    :return: Shuffled string
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    # turn the string into a list of chars
    chars = list(input_string)

    # shuffle the list
    random.shuffle(chars)

    # convert the shuffled list back to string
    return 'XXXX'.join(chars)

x_shuffle__mutmut_mutants : ClassVar[MutantDict] = { # type: ignore
'x_shuffle__mutmut_1': x_shuffle__mutmut_1, 
    'x_shuffle__mutmut_2': x_shuffle__mutmut_2, 
    'x_shuffle__mutmut_3': x_shuffle__mutmut_3, 
    'x_shuffle__mutmut_4': x_shuffle__mutmut_4, 
    'x_shuffle__mutmut_5': x_shuffle__mutmut_5, 
    'x_shuffle__mutmut_6': x_shuffle__mutmut_6, 
    'x_shuffle__mutmut_7': x_shuffle__mutmut_7, 
    'x_shuffle__mutmut_8': x_shuffle__mutmut_8
}
x_shuffle__mutmut_orig.__name__ = 'x_shuffle'


def strip_html(input_string: str, keep_tag_content: bool = False) -> str:
    args = [input_string, keep_tag_content]# type: ignore
    kwargs = {}# type: ignore
    return _mutmut_trampoline(x_strip_html__mutmut_orig, x_strip_html__mutmut_mutants, args, kwargs, None)


def x_strip_html__mutmut_orig(input_string: str, keep_tag_content: bool = False) -> str:
    """
    Remove html code contained into the given string.

    *Examples:*

    >>> strip_html('test: <a href="foo/bar">click here</a>') # returns 'test: '
    >>> strip_html('test: <a href="foo/bar">click here</a>', keep_tag_content=True) # returns 'test: click here'

    :param input_string: String to manipulate.
    :type input_string: str
    :param keep_tag_content: True to preserve tag content, False to remove tag and its content too (default).
    :type keep_tag_content: bool
    :return: String with html removed.
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    r = HTML_TAG_ONLY_RE if keep_tag_content else HTML_RE

    return r.sub('', input_string)


def x_strip_html__mutmut_1(input_string: str, keep_tag_content: bool = True) -> str:
    """
    Remove html code contained into the given string.

    *Examples:*

    >>> strip_html('test: <a href="foo/bar">click here</a>') # returns 'test: '
    >>> strip_html('test: <a href="foo/bar">click here</a>', keep_tag_content=True) # returns 'test: click here'

    :param input_string: String to manipulate.
    :type input_string: str
    :param keep_tag_content: True to preserve tag content, False to remove tag and its content too (default).
    :type keep_tag_content: bool
    :return: String with html removed.
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    r = HTML_TAG_ONLY_RE if keep_tag_content else HTML_RE

    return r.sub('', input_string)


def x_strip_html__mutmut_2(input_string: str, keep_tag_content: bool = False) -> str:
    """
    Remove html code contained into the given string.

    *Examples:*

    >>> strip_html('test: <a href="foo/bar">click here</a>') # returns 'test: '
    >>> strip_html('test: <a href="foo/bar">click here</a>', keep_tag_content=True) # returns 'test: click here'

    :param input_string: String to manipulate.
    :type input_string: str
    :param keep_tag_content: True to preserve tag content, False to remove tag and its content too (default).
    :type keep_tag_content: bool
    :return: String with html removed.
    """
    if is_string(input_string):
        raise InvalidInputError(input_string)

    r = HTML_TAG_ONLY_RE if keep_tag_content else HTML_RE

    return r.sub('', input_string)


def x_strip_html__mutmut_3(input_string: str, keep_tag_content: bool = False) -> str:
    """
    Remove html code contained into the given string.

    *Examples:*

    >>> strip_html('test: <a href="foo/bar">click here</a>') # returns 'test: '
    >>> strip_html('test: <a href="foo/bar">click here</a>', keep_tag_content=True) # returns 'test: click here'

    :param input_string: String to manipulate.
    :type input_string: str
    :param keep_tag_content: True to preserve tag content, False to remove tag and its content too (default).
    :type keep_tag_content: bool
    :return: String with html removed.
    """
    if not is_string(None):
        raise InvalidInputError(input_string)

    r = HTML_TAG_ONLY_RE if keep_tag_content else HTML_RE

    return r.sub('', input_string)


def x_strip_html__mutmut_4(input_string: str, keep_tag_content: bool = False) -> str:
    """
    Remove html code contained into the given string.

    *Examples:*

    >>> strip_html('test: <a href="foo/bar">click here</a>') # returns 'test: '
    >>> strip_html('test: <a href="foo/bar">click here</a>', keep_tag_content=True) # returns 'test: click here'

    :param input_string: String to manipulate.
    :type input_string: str
    :param keep_tag_content: True to preserve tag content, False to remove tag and its content too (default).
    :type keep_tag_content: bool
    :return: String with html removed.
    """
    if not is_string(input_string):
        raise InvalidInputError(None)

    r = HTML_TAG_ONLY_RE if keep_tag_content else HTML_RE

    return r.sub('', input_string)


def x_strip_html__mutmut_5(input_string: str, keep_tag_content: bool = False) -> str:
    """
    Remove html code contained into the given string.

    *Examples:*

    >>> strip_html('test: <a href="foo/bar">click here</a>') # returns 'test: '
    >>> strip_html('test: <a href="foo/bar">click here</a>', keep_tag_content=True) # returns 'test: click here'

    :param input_string: String to manipulate.
    :type input_string: str
    :param keep_tag_content: True to preserve tag content, False to remove tag and its content too (default).
    :type keep_tag_content: bool
    :return: String with html removed.
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    r = None

    return r.sub('', input_string)


def x_strip_html__mutmut_6(input_string: str, keep_tag_content: bool = False) -> str:
    """
    Remove html code contained into the given string.

    *Examples:*

    >>> strip_html('test: <a href="foo/bar">click here</a>') # returns 'test: '
    >>> strip_html('test: <a href="foo/bar">click here</a>', keep_tag_content=True) # returns 'test: click here'

    :param input_string: String to manipulate.
    :type input_string: str
    :param keep_tag_content: True to preserve tag content, False to remove tag and its content too (default).
    :type keep_tag_content: bool
    :return: String with html removed.
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    r = HTML_TAG_ONLY_RE if keep_tag_content else HTML_RE

    return r.sub(None, input_string)


def x_strip_html__mutmut_7(input_string: str, keep_tag_content: bool = False) -> str:
    """
    Remove html code contained into the given string.

    *Examples:*

    >>> strip_html('test: <a href="foo/bar">click here</a>') # returns 'test: '
    >>> strip_html('test: <a href="foo/bar">click here</a>', keep_tag_content=True) # returns 'test: click here'

    :param input_string: String to manipulate.
    :type input_string: str
    :param keep_tag_content: True to preserve tag content, False to remove tag and its content too (default).
    :type keep_tag_content: bool
    :return: String with html removed.
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    r = HTML_TAG_ONLY_RE if keep_tag_content else HTML_RE

    return r.sub('', None)


def x_strip_html__mutmut_8(input_string: str, keep_tag_content: bool = False) -> str:
    """
    Remove html code contained into the given string.

    *Examples:*

    >>> strip_html('test: <a href="foo/bar">click here</a>') # returns 'test: '
    >>> strip_html('test: <a href="foo/bar">click here</a>', keep_tag_content=True) # returns 'test: click here'

    :param input_string: String to manipulate.
    :type input_string: str
    :param keep_tag_content: True to preserve tag content, False to remove tag and its content too (default).
    :type keep_tag_content: bool
    :return: String with html removed.
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    r = HTML_TAG_ONLY_RE if keep_tag_content else HTML_RE

    return r.sub(input_string)


def x_strip_html__mutmut_9(input_string: str, keep_tag_content: bool = False) -> str:
    """
    Remove html code contained into the given string.

    *Examples:*

    >>> strip_html('test: <a href="foo/bar">click here</a>') # returns 'test: '
    >>> strip_html('test: <a href="foo/bar">click here</a>', keep_tag_content=True) # returns 'test: click here'

    :param input_string: String to manipulate.
    :type input_string: str
    :param keep_tag_content: True to preserve tag content, False to remove tag and its content too (default).
    :type keep_tag_content: bool
    :return: String with html removed.
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    r = HTML_TAG_ONLY_RE if keep_tag_content else HTML_RE

    return r.sub('', )


def x_strip_html__mutmut_10(input_string: str, keep_tag_content: bool = False) -> str:
    """
    Remove html code contained into the given string.

    *Examples:*

    >>> strip_html('test: <a href="foo/bar">click here</a>') # returns 'test: '
    >>> strip_html('test: <a href="foo/bar">click here</a>', keep_tag_content=True) # returns 'test: click here'

    :param input_string: String to manipulate.
    :type input_string: str
    :param keep_tag_content: True to preserve tag content, False to remove tag and its content too (default).
    :type keep_tag_content: bool
    :return: String with html removed.
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    r = HTML_TAG_ONLY_RE if keep_tag_content else HTML_RE

    return r.sub('XXXX', input_string)

x_strip_html__mutmut_mutants : ClassVar[MutantDict] = { # type: ignore
'x_strip_html__mutmut_1': x_strip_html__mutmut_1, 
    'x_strip_html__mutmut_2': x_strip_html__mutmut_2, 
    'x_strip_html__mutmut_3': x_strip_html__mutmut_3, 
    'x_strip_html__mutmut_4': x_strip_html__mutmut_4, 
    'x_strip_html__mutmut_5': x_strip_html__mutmut_5, 
    'x_strip_html__mutmut_6': x_strip_html__mutmut_6, 
    'x_strip_html__mutmut_7': x_strip_html__mutmut_7, 
    'x_strip_html__mutmut_8': x_strip_html__mutmut_8, 
    'x_strip_html__mutmut_9': x_strip_html__mutmut_9, 
    'x_strip_html__mutmut_10': x_strip_html__mutmut_10
}
x_strip_html__mutmut_orig.__name__ = 'x_strip_html'


def prettify(input_string: str) -> str:
    args = [input_string]# type: ignore
    kwargs = {}# type: ignore
    return _mutmut_trampoline(x_prettify__mutmut_orig, x_prettify__mutmut_mutants, args, kwargs, None)


def x_prettify__mutmut_orig(input_string: str) -> str:
    """
    Reformat a string by applying the following basic grammar and formatting rules:

    - String cannot start or end with spaces
    - The first letter in the string and the ones after a dot, an exclamation or a question mark must be uppercase
    - String cannot have multiple sequential spaces, empty lines or punctuation (except for "?", "!" and ".")
    - Arithmetic operators (+, -, /, \\*, =) must have one, and only one space before and after themselves
    - One, and only one space should follow a dot, a comma, an exclamation or a question mark
    - Text inside double quotes cannot start or end with spaces, but one, and only one space must come first and \
    after quotes (foo" bar"baz -> foo "bar" baz)
    - Text inside round brackets cannot start or end with spaces, but one, and only one space must come first and \
    after brackets ("foo(bar )baz" -> "foo (bar) baz")
    - Percentage sign ("%") cannot be preceded by a space if there is a number before ("100 %" -> "100%")
    - Saxon genitive is correct ("Dave' s dog" -> "Dave's dog")

    *Examples:*

    >>> prettify(' unprettified string ,, like this one,will be"prettified" .it\\' s awesome! ')
    >>> # -> 'Unprettified string, like this one, will be "prettified". It\'s awesome!'

    :param input_string: String to manipulate
    :return: Prettified string.
    """
    formatted = __StringFormatter(input_string).format()
    return formatted


def x_prettify__mutmut_1(input_string: str) -> str:
    """
    Reformat a string by applying the following basic grammar and formatting rules:

    - String cannot start or end with spaces
    - The first letter in the string and the ones after a dot, an exclamation or a question mark must be uppercase
    - String cannot have multiple sequential spaces, empty lines or punctuation (except for "?", "!" and ".")
    - Arithmetic operators (+, -, /, \\*, =) must have one, and only one space before and after themselves
    - One, and only one space should follow a dot, a comma, an exclamation or a question mark
    - Text inside double quotes cannot start or end with spaces, but one, and only one space must come first and \
    after quotes (foo" bar"baz -> foo "bar" baz)
    - Text inside round brackets cannot start or end with spaces, but one, and only one space must come first and \
    after brackets ("foo(bar )baz" -> "foo (bar) baz")
    - Percentage sign ("%") cannot be preceded by a space if there is a number before ("100 %" -> "100%")
    - Saxon genitive is correct ("Dave' s dog" -> "Dave's dog")

    *Examples:*

    >>> prettify(' unprettified string ,, like this one,will be"prettified" .it\\' s awesome! ')
    >>> # -> 'Unprettified string, like this one, will be "prettified". It\'s awesome!'

    :param input_string: String to manipulate
    :return: Prettified string.
    """
    formatted = None
    return formatted


def x_prettify__mutmut_2(input_string: str) -> str:
    """
    Reformat a string by applying the following basic grammar and formatting rules:

    - String cannot start or end with spaces
    - The first letter in the string and the ones after a dot, an exclamation or a question mark must be uppercase
    - String cannot have multiple sequential spaces, empty lines or punctuation (except for "?", "!" and ".")
    - Arithmetic operators (+, -, /, \\*, =) must have one, and only one space before and after themselves
    - One, and only one space should follow a dot, a comma, an exclamation or a question mark
    - Text inside double quotes cannot start or end with spaces, but one, and only one space must come first and \
    after quotes (foo" bar"baz -> foo "bar" baz)
    - Text inside round brackets cannot start or end with spaces, but one, and only one space must come first and \
    after brackets ("foo(bar )baz" -> "foo (bar) baz")
    - Percentage sign ("%") cannot be preceded by a space if there is a number before ("100 %" -> "100%")
    - Saxon genitive is correct ("Dave' s dog" -> "Dave's dog")

    *Examples:*

    >>> prettify(' unprettified string ,, like this one,will be"prettified" .it\\' s awesome! ')
    >>> # -> 'Unprettified string, like this one, will be "prettified". It\'s awesome!'

    :param input_string: String to manipulate
    :return: Prettified string.
    """
    formatted = __StringFormatter(None).format()
    return formatted

x_prettify__mutmut_mutants : ClassVar[MutantDict] = { # type: ignore
'x_prettify__mutmut_1': x_prettify__mutmut_1, 
    'x_prettify__mutmut_2': x_prettify__mutmut_2
}
x_prettify__mutmut_orig.__name__ = 'x_prettify'


def asciify(input_string: str) -> str:
    args = [input_string]# type: ignore
    kwargs = {}# type: ignore
    return _mutmut_trampoline(x_asciify__mutmut_orig, x_asciify__mutmut_mutants, args, kwargs, None)


def x_asciify__mutmut_orig(input_string: str) -> str:
    """
    Force string content to be ascii-only by translating all non-ascii chars into the closest possible representation
    (eg: ó -> o, Ë -> E, ç -> c...).

    **Bear in mind**: Some chars may be lost if impossible to translate.

    *Example:*

    >>> asciify('èéùúòóäåëýñÅÀÁÇÌÍÑÓË') # returns 'eeuuooaaeynAAACIINOE'

    :param input_string: String to convert
    :return: Ascii utf-8 string
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    # "NFKD" is the algorithm which is able to successfully translate the most of non-ascii chars
    normalized = unicodedata.normalize('NFKD', input_string)

    # encode string forcing ascii and ignore any errors (unrepresentable chars will be stripped out)
    ascii_bytes = normalized.encode('ascii', 'ignore')

    # turns encoded bytes into an utf-8 string
    ascii_string = ascii_bytes.decode('utf-8')

    return ascii_string


def x_asciify__mutmut_1(input_string: str) -> str:
    """
    Force string content to be ascii-only by translating all non-ascii chars into the closest possible representation
    (eg: ó -> o, Ë -> E, ç -> c...).

    **Bear in mind**: Some chars may be lost if impossible to translate.

    *Example:*

    >>> asciify('èéùúòóäåëýñÅÀÁÇÌÍÑÓË') # returns 'eeuuooaaeynAAACIINOE'

    :param input_string: String to convert
    :return: Ascii utf-8 string
    """
    if is_string(input_string):
        raise InvalidInputError(input_string)

    # "NFKD" is the algorithm which is able to successfully translate the most of non-ascii chars
    normalized = unicodedata.normalize('NFKD', input_string)

    # encode string forcing ascii and ignore any errors (unrepresentable chars will be stripped out)
    ascii_bytes = normalized.encode('ascii', 'ignore')

    # turns encoded bytes into an utf-8 string
    ascii_string = ascii_bytes.decode('utf-8')

    return ascii_string


def x_asciify__mutmut_2(input_string: str) -> str:
    """
    Force string content to be ascii-only by translating all non-ascii chars into the closest possible representation
    (eg: ó -> o, Ë -> E, ç -> c...).

    **Bear in mind**: Some chars may be lost if impossible to translate.

    *Example:*

    >>> asciify('èéùúòóäåëýñÅÀÁÇÌÍÑÓË') # returns 'eeuuooaaeynAAACIINOE'

    :param input_string: String to convert
    :return: Ascii utf-8 string
    """
    if not is_string(None):
        raise InvalidInputError(input_string)

    # "NFKD" is the algorithm which is able to successfully translate the most of non-ascii chars
    normalized = unicodedata.normalize('NFKD', input_string)

    # encode string forcing ascii and ignore any errors (unrepresentable chars will be stripped out)
    ascii_bytes = normalized.encode('ascii', 'ignore')

    # turns encoded bytes into an utf-8 string
    ascii_string = ascii_bytes.decode('utf-8')

    return ascii_string


def x_asciify__mutmut_3(input_string: str) -> str:
    """
    Force string content to be ascii-only by translating all non-ascii chars into the closest possible representation
    (eg: ó -> o, Ë -> E, ç -> c...).

    **Bear in mind**: Some chars may be lost if impossible to translate.

    *Example:*

    >>> asciify('èéùúòóäåëýñÅÀÁÇÌÍÑÓË') # returns 'eeuuooaaeynAAACIINOE'

    :param input_string: String to convert
    :return: Ascii utf-8 string
    """
    if not is_string(input_string):
        raise InvalidInputError(None)

    # "NFKD" is the algorithm which is able to successfully translate the most of non-ascii chars
    normalized = unicodedata.normalize('NFKD', input_string)

    # encode string forcing ascii and ignore any errors (unrepresentable chars will be stripped out)
    ascii_bytes = normalized.encode('ascii', 'ignore')

    # turns encoded bytes into an utf-8 string
    ascii_string = ascii_bytes.decode('utf-8')

    return ascii_string


def x_asciify__mutmut_4(input_string: str) -> str:
    """
    Force string content to be ascii-only by translating all non-ascii chars into the closest possible representation
    (eg: ó -> o, Ë -> E, ç -> c...).

    **Bear in mind**: Some chars may be lost if impossible to translate.

    *Example:*

    >>> asciify('èéùúòóäåëýñÅÀÁÇÌÍÑÓË') # returns 'eeuuooaaeynAAACIINOE'

    :param input_string: String to convert
    :return: Ascii utf-8 string
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    # "NFKD" is the algorithm which is able to successfully translate the most of non-ascii chars
    normalized = None

    # encode string forcing ascii and ignore any errors (unrepresentable chars will be stripped out)
    ascii_bytes = normalized.encode('ascii', 'ignore')

    # turns encoded bytes into an utf-8 string
    ascii_string = ascii_bytes.decode('utf-8')

    return ascii_string


def x_asciify__mutmut_5(input_string: str) -> str:
    """
    Force string content to be ascii-only by translating all non-ascii chars into the closest possible representation
    (eg: ó -> o, Ë -> E, ç -> c...).

    **Bear in mind**: Some chars may be lost if impossible to translate.

    *Example:*

    >>> asciify('èéùúòóäåëýñÅÀÁÇÌÍÑÓË') # returns 'eeuuooaaeynAAACIINOE'

    :param input_string: String to convert
    :return: Ascii utf-8 string
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    # "NFKD" is the algorithm which is able to successfully translate the most of non-ascii chars
    normalized = unicodedata.normalize(None, input_string)

    # encode string forcing ascii and ignore any errors (unrepresentable chars will be stripped out)
    ascii_bytes = normalized.encode('ascii', 'ignore')

    # turns encoded bytes into an utf-8 string
    ascii_string = ascii_bytes.decode('utf-8')

    return ascii_string


def x_asciify__mutmut_6(input_string: str) -> str:
    """
    Force string content to be ascii-only by translating all non-ascii chars into the closest possible representation
    (eg: ó -> o, Ë -> E, ç -> c...).

    **Bear in mind**: Some chars may be lost if impossible to translate.

    *Example:*

    >>> asciify('èéùúòóäåëýñÅÀÁÇÌÍÑÓË') # returns 'eeuuooaaeynAAACIINOE'

    :param input_string: String to convert
    :return: Ascii utf-8 string
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    # "NFKD" is the algorithm which is able to successfully translate the most of non-ascii chars
    normalized = unicodedata.normalize('NFKD', None)

    # encode string forcing ascii and ignore any errors (unrepresentable chars will be stripped out)
    ascii_bytes = normalized.encode('ascii', 'ignore')

    # turns encoded bytes into an utf-8 string
    ascii_string = ascii_bytes.decode('utf-8')

    return ascii_string


def x_asciify__mutmut_7(input_string: str) -> str:
    """
    Force string content to be ascii-only by translating all non-ascii chars into the closest possible representation
    (eg: ó -> o, Ë -> E, ç -> c...).

    **Bear in mind**: Some chars may be lost if impossible to translate.

    *Example:*

    >>> asciify('èéùúòóäåëýñÅÀÁÇÌÍÑÓË') # returns 'eeuuooaaeynAAACIINOE'

    :param input_string: String to convert
    :return: Ascii utf-8 string
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    # "NFKD" is the algorithm which is able to successfully translate the most of non-ascii chars
    normalized = unicodedata.normalize(input_string)

    # encode string forcing ascii and ignore any errors (unrepresentable chars will be stripped out)
    ascii_bytes = normalized.encode('ascii', 'ignore')

    # turns encoded bytes into an utf-8 string
    ascii_string = ascii_bytes.decode('utf-8')

    return ascii_string


def x_asciify__mutmut_8(input_string: str) -> str:
    """
    Force string content to be ascii-only by translating all non-ascii chars into the closest possible representation
    (eg: ó -> o, Ë -> E, ç -> c...).

    **Bear in mind**: Some chars may be lost if impossible to translate.

    *Example:*

    >>> asciify('èéùúòóäåëýñÅÀÁÇÌÍÑÓË') # returns 'eeuuooaaeynAAACIINOE'

    :param input_string: String to convert
    :return: Ascii utf-8 string
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    # "NFKD" is the algorithm which is able to successfully translate the most of non-ascii chars
    normalized = unicodedata.normalize('NFKD', )

    # encode string forcing ascii and ignore any errors (unrepresentable chars will be stripped out)
    ascii_bytes = normalized.encode('ascii', 'ignore')

    # turns encoded bytes into an utf-8 string
    ascii_string = ascii_bytes.decode('utf-8')

    return ascii_string


def x_asciify__mutmut_9(input_string: str) -> str:
    """
    Force string content to be ascii-only by translating all non-ascii chars into the closest possible representation
    (eg: ó -> o, Ë -> E, ç -> c...).

    **Bear in mind**: Some chars may be lost if impossible to translate.

    *Example:*

    >>> asciify('èéùúòóäåëýñÅÀÁÇÌÍÑÓË') # returns 'eeuuooaaeynAAACIINOE'

    :param input_string: String to convert
    :return: Ascii utf-8 string
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    # "NFKD" is the algorithm which is able to successfully translate the most of non-ascii chars
    normalized = unicodedata.normalize('XXNFKDXX', input_string)

    # encode string forcing ascii and ignore any errors (unrepresentable chars will be stripped out)
    ascii_bytes = normalized.encode('ascii', 'ignore')

    # turns encoded bytes into an utf-8 string
    ascii_string = ascii_bytes.decode('utf-8')

    return ascii_string


def x_asciify__mutmut_10(input_string: str) -> str:
    """
    Force string content to be ascii-only by translating all non-ascii chars into the closest possible representation
    (eg: ó -> o, Ë -> E, ç -> c...).

    **Bear in mind**: Some chars may be lost if impossible to translate.

    *Example:*

    >>> asciify('èéùúòóäåëýñÅÀÁÇÌÍÑÓË') # returns 'eeuuooaaeynAAACIINOE'

    :param input_string: String to convert
    :return: Ascii utf-8 string
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    # "NFKD" is the algorithm which is able to successfully translate the most of non-ascii chars
    normalized = unicodedata.normalize('nfkd', input_string)

    # encode string forcing ascii and ignore any errors (unrepresentable chars will be stripped out)
    ascii_bytes = normalized.encode('ascii', 'ignore')

    # turns encoded bytes into an utf-8 string
    ascii_string = ascii_bytes.decode('utf-8')

    return ascii_string


def x_asciify__mutmut_11(input_string: str) -> str:
    """
    Force string content to be ascii-only by translating all non-ascii chars into the closest possible representation
    (eg: ó -> o, Ë -> E, ç -> c...).

    **Bear in mind**: Some chars may be lost if impossible to translate.

    *Example:*

    >>> asciify('èéùúòóäåëýñÅÀÁÇÌÍÑÓË') # returns 'eeuuooaaeynAAACIINOE'

    :param input_string: String to convert
    :return: Ascii utf-8 string
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    # "NFKD" is the algorithm which is able to successfully translate the most of non-ascii chars
    normalized = unicodedata.normalize('NFKD', input_string)

    # encode string forcing ascii and ignore any errors (unrepresentable chars will be stripped out)
    ascii_bytes = None

    # turns encoded bytes into an utf-8 string
    ascii_string = ascii_bytes.decode('utf-8')

    return ascii_string


def x_asciify__mutmut_12(input_string: str) -> str:
    """
    Force string content to be ascii-only by translating all non-ascii chars into the closest possible representation
    (eg: ó -> o, Ë -> E, ç -> c...).

    **Bear in mind**: Some chars may be lost if impossible to translate.

    *Example:*

    >>> asciify('èéùúòóäåëýñÅÀÁÇÌÍÑÓË') # returns 'eeuuooaaeynAAACIINOE'

    :param input_string: String to convert
    :return: Ascii utf-8 string
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    # "NFKD" is the algorithm which is able to successfully translate the most of non-ascii chars
    normalized = unicodedata.normalize('NFKD', input_string)

    # encode string forcing ascii and ignore any errors (unrepresentable chars will be stripped out)
    ascii_bytes = normalized.encode(None, 'ignore')

    # turns encoded bytes into an utf-8 string
    ascii_string = ascii_bytes.decode('utf-8')

    return ascii_string


def x_asciify__mutmut_13(input_string: str) -> str:
    """
    Force string content to be ascii-only by translating all non-ascii chars into the closest possible representation
    (eg: ó -> o, Ë -> E, ç -> c...).

    **Bear in mind**: Some chars may be lost if impossible to translate.

    *Example:*

    >>> asciify('èéùúòóäåëýñÅÀÁÇÌÍÑÓË') # returns 'eeuuooaaeynAAACIINOE'

    :param input_string: String to convert
    :return: Ascii utf-8 string
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    # "NFKD" is the algorithm which is able to successfully translate the most of non-ascii chars
    normalized = unicodedata.normalize('NFKD', input_string)

    # encode string forcing ascii and ignore any errors (unrepresentable chars will be stripped out)
    ascii_bytes = normalized.encode('ascii', None)

    # turns encoded bytes into an utf-8 string
    ascii_string = ascii_bytes.decode('utf-8')

    return ascii_string


def x_asciify__mutmut_14(input_string: str) -> str:
    """
    Force string content to be ascii-only by translating all non-ascii chars into the closest possible representation
    (eg: ó -> o, Ë -> E, ç -> c...).

    **Bear in mind**: Some chars may be lost if impossible to translate.

    *Example:*

    >>> asciify('èéùúòóäåëýñÅÀÁÇÌÍÑÓË') # returns 'eeuuooaaeynAAACIINOE'

    :param input_string: String to convert
    :return: Ascii utf-8 string
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    # "NFKD" is the algorithm which is able to successfully translate the most of non-ascii chars
    normalized = unicodedata.normalize('NFKD', input_string)

    # encode string forcing ascii and ignore any errors (unrepresentable chars will be stripped out)
    ascii_bytes = normalized.encode('ignore')

    # turns encoded bytes into an utf-8 string
    ascii_string = ascii_bytes.decode('utf-8')

    return ascii_string


def x_asciify__mutmut_15(input_string: str) -> str:
    """
    Force string content to be ascii-only by translating all non-ascii chars into the closest possible representation
    (eg: ó -> o, Ë -> E, ç -> c...).

    **Bear in mind**: Some chars may be lost if impossible to translate.

    *Example:*

    >>> asciify('èéùúòóäåëýñÅÀÁÇÌÍÑÓË') # returns 'eeuuooaaeynAAACIINOE'

    :param input_string: String to convert
    :return: Ascii utf-8 string
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    # "NFKD" is the algorithm which is able to successfully translate the most of non-ascii chars
    normalized = unicodedata.normalize('NFKD', input_string)

    # encode string forcing ascii and ignore any errors (unrepresentable chars will be stripped out)
    ascii_bytes = normalized.encode('ascii', )

    # turns encoded bytes into an utf-8 string
    ascii_string = ascii_bytes.decode('utf-8')

    return ascii_string


def x_asciify__mutmut_16(input_string: str) -> str:
    """
    Force string content to be ascii-only by translating all non-ascii chars into the closest possible representation
    (eg: ó -> o, Ë -> E, ç -> c...).

    **Bear in mind**: Some chars may be lost if impossible to translate.

    *Example:*

    >>> asciify('èéùúòóäåëýñÅÀÁÇÌÍÑÓË') # returns 'eeuuooaaeynAAACIINOE'

    :param input_string: String to convert
    :return: Ascii utf-8 string
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    # "NFKD" is the algorithm which is able to successfully translate the most of non-ascii chars
    normalized = unicodedata.normalize('NFKD', input_string)

    # encode string forcing ascii and ignore any errors (unrepresentable chars will be stripped out)
    ascii_bytes = normalized.encode('XXasciiXX', 'ignore')

    # turns encoded bytes into an utf-8 string
    ascii_string = ascii_bytes.decode('utf-8')

    return ascii_string


def x_asciify__mutmut_17(input_string: str) -> str:
    """
    Force string content to be ascii-only by translating all non-ascii chars into the closest possible representation
    (eg: ó -> o, Ë -> E, ç -> c...).

    **Bear in mind**: Some chars may be lost if impossible to translate.

    *Example:*

    >>> asciify('èéùúòóäåëýñÅÀÁÇÌÍÑÓË') # returns 'eeuuooaaeynAAACIINOE'

    :param input_string: String to convert
    :return: Ascii utf-8 string
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    # "NFKD" is the algorithm which is able to successfully translate the most of non-ascii chars
    normalized = unicodedata.normalize('NFKD', input_string)

    # encode string forcing ascii and ignore any errors (unrepresentable chars will be stripped out)
    ascii_bytes = normalized.encode('ASCII', 'ignore')

    # turns encoded bytes into an utf-8 string
    ascii_string = ascii_bytes.decode('utf-8')

    return ascii_string


def x_asciify__mutmut_18(input_string: str) -> str:
    """
    Force string content to be ascii-only by translating all non-ascii chars into the closest possible representation
    (eg: ó -> o, Ë -> E, ç -> c...).

    **Bear in mind**: Some chars may be lost if impossible to translate.

    *Example:*

    >>> asciify('èéùúòóäåëýñÅÀÁÇÌÍÑÓË') # returns 'eeuuooaaeynAAACIINOE'

    :param input_string: String to convert
    :return: Ascii utf-8 string
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    # "NFKD" is the algorithm which is able to successfully translate the most of non-ascii chars
    normalized = unicodedata.normalize('NFKD', input_string)

    # encode string forcing ascii and ignore any errors (unrepresentable chars will be stripped out)
    ascii_bytes = normalized.encode('ascii', 'XXignoreXX')

    # turns encoded bytes into an utf-8 string
    ascii_string = ascii_bytes.decode('utf-8')

    return ascii_string


def x_asciify__mutmut_19(input_string: str) -> str:
    """
    Force string content to be ascii-only by translating all non-ascii chars into the closest possible representation
    (eg: ó -> o, Ë -> E, ç -> c...).

    **Bear in mind**: Some chars may be lost if impossible to translate.

    *Example:*

    >>> asciify('èéùúòóäåëýñÅÀÁÇÌÍÑÓË') # returns 'eeuuooaaeynAAACIINOE'

    :param input_string: String to convert
    :return: Ascii utf-8 string
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    # "NFKD" is the algorithm which is able to successfully translate the most of non-ascii chars
    normalized = unicodedata.normalize('NFKD', input_string)

    # encode string forcing ascii and ignore any errors (unrepresentable chars will be stripped out)
    ascii_bytes = normalized.encode('ascii', 'IGNORE')

    # turns encoded bytes into an utf-8 string
    ascii_string = ascii_bytes.decode('utf-8')

    return ascii_string


def x_asciify__mutmut_20(input_string: str) -> str:
    """
    Force string content to be ascii-only by translating all non-ascii chars into the closest possible representation
    (eg: ó -> o, Ë -> E, ç -> c...).

    **Bear in mind**: Some chars may be lost if impossible to translate.

    *Example:*

    >>> asciify('èéùúòóäåëýñÅÀÁÇÌÍÑÓË') # returns 'eeuuooaaeynAAACIINOE'

    :param input_string: String to convert
    :return: Ascii utf-8 string
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    # "NFKD" is the algorithm which is able to successfully translate the most of non-ascii chars
    normalized = unicodedata.normalize('NFKD', input_string)

    # encode string forcing ascii and ignore any errors (unrepresentable chars will be stripped out)
    ascii_bytes = normalized.encode('ascii', 'ignore')

    # turns encoded bytes into an utf-8 string
    ascii_string = None

    return ascii_string


def x_asciify__mutmut_21(input_string: str) -> str:
    """
    Force string content to be ascii-only by translating all non-ascii chars into the closest possible representation
    (eg: ó -> o, Ë -> E, ç -> c...).

    **Bear in mind**: Some chars may be lost if impossible to translate.

    *Example:*

    >>> asciify('èéùúòóäåëýñÅÀÁÇÌÍÑÓË') # returns 'eeuuooaaeynAAACIINOE'

    :param input_string: String to convert
    :return: Ascii utf-8 string
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    # "NFKD" is the algorithm which is able to successfully translate the most of non-ascii chars
    normalized = unicodedata.normalize('NFKD', input_string)

    # encode string forcing ascii and ignore any errors (unrepresentable chars will be stripped out)
    ascii_bytes = normalized.encode('ascii', 'ignore')

    # turns encoded bytes into an utf-8 string
    ascii_string = ascii_bytes.decode(None)

    return ascii_string


def x_asciify__mutmut_22(input_string: str) -> str:
    """
    Force string content to be ascii-only by translating all non-ascii chars into the closest possible representation
    (eg: ó -> o, Ë -> E, ç -> c...).

    **Bear in mind**: Some chars may be lost if impossible to translate.

    *Example:*

    >>> asciify('èéùúòóäåëýñÅÀÁÇÌÍÑÓË') # returns 'eeuuooaaeynAAACIINOE'

    :param input_string: String to convert
    :return: Ascii utf-8 string
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    # "NFKD" is the algorithm which is able to successfully translate the most of non-ascii chars
    normalized = unicodedata.normalize('NFKD', input_string)

    # encode string forcing ascii and ignore any errors (unrepresentable chars will be stripped out)
    ascii_bytes = normalized.encode('ascii', 'ignore')

    # turns encoded bytes into an utf-8 string
    ascii_string = ascii_bytes.decode('XXutf-8XX')

    return ascii_string


def x_asciify__mutmut_23(input_string: str) -> str:
    """
    Force string content to be ascii-only by translating all non-ascii chars into the closest possible representation
    (eg: ó -> o, Ë -> E, ç -> c...).

    **Bear in mind**: Some chars may be lost if impossible to translate.

    *Example:*

    >>> asciify('èéùúòóäåëýñÅÀÁÇÌÍÑÓË') # returns 'eeuuooaaeynAAACIINOE'

    :param input_string: String to convert
    :return: Ascii utf-8 string
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    # "NFKD" is the algorithm which is able to successfully translate the most of non-ascii chars
    normalized = unicodedata.normalize('NFKD', input_string)

    # encode string forcing ascii and ignore any errors (unrepresentable chars will be stripped out)
    ascii_bytes = normalized.encode('ascii', 'ignore')

    # turns encoded bytes into an utf-8 string
    ascii_string = ascii_bytes.decode('UTF-8')

    return ascii_string

x_asciify__mutmut_mutants : ClassVar[MutantDict] = { # type: ignore
'x_asciify__mutmut_1': x_asciify__mutmut_1, 
    'x_asciify__mutmut_2': x_asciify__mutmut_2, 
    'x_asciify__mutmut_3': x_asciify__mutmut_3, 
    'x_asciify__mutmut_4': x_asciify__mutmut_4, 
    'x_asciify__mutmut_5': x_asciify__mutmut_5, 
    'x_asciify__mutmut_6': x_asciify__mutmut_6, 
    'x_asciify__mutmut_7': x_asciify__mutmut_7, 
    'x_asciify__mutmut_8': x_asciify__mutmut_8, 
    'x_asciify__mutmut_9': x_asciify__mutmut_9, 
    'x_asciify__mutmut_10': x_asciify__mutmut_10, 
    'x_asciify__mutmut_11': x_asciify__mutmut_11, 
    'x_asciify__mutmut_12': x_asciify__mutmut_12, 
    'x_asciify__mutmut_13': x_asciify__mutmut_13, 
    'x_asciify__mutmut_14': x_asciify__mutmut_14, 
    'x_asciify__mutmut_15': x_asciify__mutmut_15, 
    'x_asciify__mutmut_16': x_asciify__mutmut_16, 
    'x_asciify__mutmut_17': x_asciify__mutmut_17, 
    'x_asciify__mutmut_18': x_asciify__mutmut_18, 
    'x_asciify__mutmut_19': x_asciify__mutmut_19, 
    'x_asciify__mutmut_20': x_asciify__mutmut_20, 
    'x_asciify__mutmut_21': x_asciify__mutmut_21, 
    'x_asciify__mutmut_22': x_asciify__mutmut_22, 
    'x_asciify__mutmut_23': x_asciify__mutmut_23
}
x_asciify__mutmut_orig.__name__ = 'x_asciify'


def slugify(input_string: str, separator: str = '-') -> str:
    args = [input_string, separator]# type: ignore
    kwargs = {}# type: ignore
    return _mutmut_trampoline(x_slugify__mutmut_orig, x_slugify__mutmut_mutants, args, kwargs, None)


def x_slugify__mutmut_orig(input_string: str, separator: str = '-') -> str:
    """
    Converts a string into a "slug" using provided separator.
    The returned string has the following properties:

    - it has no spaces
    - all letters are in lower case
    - all punctuation signs and non alphanumeric chars are removed
    - words are divided using provided separator
    - all chars are encoded as ascii (by using `asciify()`)
    - is safe for URL

    *Examples:*

    >>> slugify('Top 10 Reasons To Love Dogs!!!') # returns: 'top-10-reasons-to-love-dogs'
    >>> slugify('Mönstér Mägnët') # returns 'monster-magnet'

    :param input_string: String to convert.
    :type input_string: str
    :param separator: Sign used to join string tokens (default to "-").
    :type separator: str
    :return: Slug string
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    # replace any character that is NOT letter or number with spaces
    out = NO_LETTERS_OR_NUMBERS_RE.sub(' ', input_string.lower()).strip()

    # replace spaces with join sign
    out = SPACES_RE.sub(separator, out)

    # normalize joins (remove duplicates)
    out = re.sub(re.escape(separator) + r'+', separator, out)

    return asciify(out)


def x_slugify__mutmut_1(input_string: str, separator: str = 'XX-XX') -> str:
    """
    Converts a string into a "slug" using provided separator.
    The returned string has the following properties:

    - it has no spaces
    - all letters are in lower case
    - all punctuation signs and non alphanumeric chars are removed
    - words are divided using provided separator
    - all chars are encoded as ascii (by using `asciify()`)
    - is safe for URL

    *Examples:*

    >>> slugify('Top 10 Reasons To Love Dogs!!!') # returns: 'top-10-reasons-to-love-dogs'
    >>> slugify('Mönstér Mägnët') # returns 'monster-magnet'

    :param input_string: String to convert.
    :type input_string: str
    :param separator: Sign used to join string tokens (default to "-").
    :type separator: str
    :return: Slug string
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    # replace any character that is NOT letter or number with spaces
    out = NO_LETTERS_OR_NUMBERS_RE.sub(' ', input_string.lower()).strip()

    # replace spaces with join sign
    out = SPACES_RE.sub(separator, out)

    # normalize joins (remove duplicates)
    out = re.sub(re.escape(separator) + r'+', separator, out)

    return asciify(out)


def x_slugify__mutmut_2(input_string: str, separator: str = '-') -> str:
    """
    Converts a string into a "slug" using provided separator.
    The returned string has the following properties:

    - it has no spaces
    - all letters are in lower case
    - all punctuation signs and non alphanumeric chars are removed
    - words are divided using provided separator
    - all chars are encoded as ascii (by using `asciify()`)
    - is safe for URL

    *Examples:*

    >>> slugify('Top 10 Reasons To Love Dogs!!!') # returns: 'top-10-reasons-to-love-dogs'
    >>> slugify('Mönstér Mägnët') # returns 'monster-magnet'

    :param input_string: String to convert.
    :type input_string: str
    :param separator: Sign used to join string tokens (default to "-").
    :type separator: str
    :return: Slug string
    """
    if is_string(input_string):
        raise InvalidInputError(input_string)

    # replace any character that is NOT letter or number with spaces
    out = NO_LETTERS_OR_NUMBERS_RE.sub(' ', input_string.lower()).strip()

    # replace spaces with join sign
    out = SPACES_RE.sub(separator, out)

    # normalize joins (remove duplicates)
    out = re.sub(re.escape(separator) + r'+', separator, out)

    return asciify(out)


def x_slugify__mutmut_3(input_string: str, separator: str = '-') -> str:
    """
    Converts a string into a "slug" using provided separator.
    The returned string has the following properties:

    - it has no spaces
    - all letters are in lower case
    - all punctuation signs and non alphanumeric chars are removed
    - words are divided using provided separator
    - all chars are encoded as ascii (by using `asciify()`)
    - is safe for URL

    *Examples:*

    >>> slugify('Top 10 Reasons To Love Dogs!!!') # returns: 'top-10-reasons-to-love-dogs'
    >>> slugify('Mönstér Mägnët') # returns 'monster-magnet'

    :param input_string: String to convert.
    :type input_string: str
    :param separator: Sign used to join string tokens (default to "-").
    :type separator: str
    :return: Slug string
    """
    if not is_string(None):
        raise InvalidInputError(input_string)

    # replace any character that is NOT letter or number with spaces
    out = NO_LETTERS_OR_NUMBERS_RE.sub(' ', input_string.lower()).strip()

    # replace spaces with join sign
    out = SPACES_RE.sub(separator, out)

    # normalize joins (remove duplicates)
    out = re.sub(re.escape(separator) + r'+', separator, out)

    return asciify(out)


def x_slugify__mutmut_4(input_string: str, separator: str = '-') -> str:
    """
    Converts a string into a "slug" using provided separator.
    The returned string has the following properties:

    - it has no spaces
    - all letters are in lower case
    - all punctuation signs and non alphanumeric chars are removed
    - words are divided using provided separator
    - all chars are encoded as ascii (by using `asciify()`)
    - is safe for URL

    *Examples:*

    >>> slugify('Top 10 Reasons To Love Dogs!!!') # returns: 'top-10-reasons-to-love-dogs'
    >>> slugify('Mönstér Mägnët') # returns 'monster-magnet'

    :param input_string: String to convert.
    :type input_string: str
    :param separator: Sign used to join string tokens (default to "-").
    :type separator: str
    :return: Slug string
    """
    if not is_string(input_string):
        raise InvalidInputError(None)

    # replace any character that is NOT letter or number with spaces
    out = NO_LETTERS_OR_NUMBERS_RE.sub(' ', input_string.lower()).strip()

    # replace spaces with join sign
    out = SPACES_RE.sub(separator, out)

    # normalize joins (remove duplicates)
    out = re.sub(re.escape(separator) + r'+', separator, out)

    return asciify(out)


def x_slugify__mutmut_5(input_string: str, separator: str = '-') -> str:
    """
    Converts a string into a "slug" using provided separator.
    The returned string has the following properties:

    - it has no spaces
    - all letters are in lower case
    - all punctuation signs and non alphanumeric chars are removed
    - words are divided using provided separator
    - all chars are encoded as ascii (by using `asciify()`)
    - is safe for URL

    *Examples:*

    >>> slugify('Top 10 Reasons To Love Dogs!!!') # returns: 'top-10-reasons-to-love-dogs'
    >>> slugify('Mönstér Mägnët') # returns 'monster-magnet'

    :param input_string: String to convert.
    :type input_string: str
    :param separator: Sign used to join string tokens (default to "-").
    :type separator: str
    :return: Slug string
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    # replace any character that is NOT letter or number with spaces
    out = None

    # replace spaces with join sign
    out = SPACES_RE.sub(separator, out)

    # normalize joins (remove duplicates)
    out = re.sub(re.escape(separator) + r'+', separator, out)

    return asciify(out)


def x_slugify__mutmut_6(input_string: str, separator: str = '-') -> str:
    """
    Converts a string into a "slug" using provided separator.
    The returned string has the following properties:

    - it has no spaces
    - all letters are in lower case
    - all punctuation signs and non alphanumeric chars are removed
    - words are divided using provided separator
    - all chars are encoded as ascii (by using `asciify()`)
    - is safe for URL

    *Examples:*

    >>> slugify('Top 10 Reasons To Love Dogs!!!') # returns: 'top-10-reasons-to-love-dogs'
    >>> slugify('Mönstér Mägnët') # returns 'monster-magnet'

    :param input_string: String to convert.
    :type input_string: str
    :param separator: Sign used to join string tokens (default to "-").
    :type separator: str
    :return: Slug string
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    # replace any character that is NOT letter or number with spaces
    out = NO_LETTERS_OR_NUMBERS_RE.sub(None, input_string.lower()).strip()

    # replace spaces with join sign
    out = SPACES_RE.sub(separator, out)

    # normalize joins (remove duplicates)
    out = re.sub(re.escape(separator) + r'+', separator, out)

    return asciify(out)


def x_slugify__mutmut_7(input_string: str, separator: str = '-') -> str:
    """
    Converts a string into a "slug" using provided separator.
    The returned string has the following properties:

    - it has no spaces
    - all letters are in lower case
    - all punctuation signs and non alphanumeric chars are removed
    - words are divided using provided separator
    - all chars are encoded as ascii (by using `asciify()`)
    - is safe for URL

    *Examples:*

    >>> slugify('Top 10 Reasons To Love Dogs!!!') # returns: 'top-10-reasons-to-love-dogs'
    >>> slugify('Mönstér Mägnët') # returns 'monster-magnet'

    :param input_string: String to convert.
    :type input_string: str
    :param separator: Sign used to join string tokens (default to "-").
    :type separator: str
    :return: Slug string
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    # replace any character that is NOT letter or number with spaces
    out = NO_LETTERS_OR_NUMBERS_RE.sub(' ', None).strip()

    # replace spaces with join sign
    out = SPACES_RE.sub(separator, out)

    # normalize joins (remove duplicates)
    out = re.sub(re.escape(separator) + r'+', separator, out)

    return asciify(out)


def x_slugify__mutmut_8(input_string: str, separator: str = '-') -> str:
    """
    Converts a string into a "slug" using provided separator.
    The returned string has the following properties:

    - it has no spaces
    - all letters are in lower case
    - all punctuation signs and non alphanumeric chars are removed
    - words are divided using provided separator
    - all chars are encoded as ascii (by using `asciify()`)
    - is safe for URL

    *Examples:*

    >>> slugify('Top 10 Reasons To Love Dogs!!!') # returns: 'top-10-reasons-to-love-dogs'
    >>> slugify('Mönstér Mägnët') # returns 'monster-magnet'

    :param input_string: String to convert.
    :type input_string: str
    :param separator: Sign used to join string tokens (default to "-").
    :type separator: str
    :return: Slug string
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    # replace any character that is NOT letter or number with spaces
    out = NO_LETTERS_OR_NUMBERS_RE.sub(input_string.lower()).strip()

    # replace spaces with join sign
    out = SPACES_RE.sub(separator, out)

    # normalize joins (remove duplicates)
    out = re.sub(re.escape(separator) + r'+', separator, out)

    return asciify(out)


def x_slugify__mutmut_9(input_string: str, separator: str = '-') -> str:
    """
    Converts a string into a "slug" using provided separator.
    The returned string has the following properties:

    - it has no spaces
    - all letters are in lower case
    - all punctuation signs and non alphanumeric chars are removed
    - words are divided using provided separator
    - all chars are encoded as ascii (by using `asciify()`)
    - is safe for URL

    *Examples:*

    >>> slugify('Top 10 Reasons To Love Dogs!!!') # returns: 'top-10-reasons-to-love-dogs'
    >>> slugify('Mönstér Mägnët') # returns 'monster-magnet'

    :param input_string: String to convert.
    :type input_string: str
    :param separator: Sign used to join string tokens (default to "-").
    :type separator: str
    :return: Slug string
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    # replace any character that is NOT letter or number with spaces
    out = NO_LETTERS_OR_NUMBERS_RE.sub(' ', ).strip()

    # replace spaces with join sign
    out = SPACES_RE.sub(separator, out)

    # normalize joins (remove duplicates)
    out = re.sub(re.escape(separator) + r'+', separator, out)

    return asciify(out)


def x_slugify__mutmut_10(input_string: str, separator: str = '-') -> str:
    """
    Converts a string into a "slug" using provided separator.
    The returned string has the following properties:

    - it has no spaces
    - all letters are in lower case
    - all punctuation signs and non alphanumeric chars are removed
    - words are divided using provided separator
    - all chars are encoded as ascii (by using `asciify()`)
    - is safe for URL

    *Examples:*

    >>> slugify('Top 10 Reasons To Love Dogs!!!') # returns: 'top-10-reasons-to-love-dogs'
    >>> slugify('Mönstér Mägnët') # returns 'monster-magnet'

    :param input_string: String to convert.
    :type input_string: str
    :param separator: Sign used to join string tokens (default to "-").
    :type separator: str
    :return: Slug string
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    # replace any character that is NOT letter or number with spaces
    out = NO_LETTERS_OR_NUMBERS_RE.sub('XX XX', input_string.lower()).strip()

    # replace spaces with join sign
    out = SPACES_RE.sub(separator, out)

    # normalize joins (remove duplicates)
    out = re.sub(re.escape(separator) + r'+', separator, out)

    return asciify(out)


def x_slugify__mutmut_11(input_string: str, separator: str = '-') -> str:
    """
    Converts a string into a "slug" using provided separator.
    The returned string has the following properties:

    - it has no spaces
    - all letters are in lower case
    - all punctuation signs and non alphanumeric chars are removed
    - words are divided using provided separator
    - all chars are encoded as ascii (by using `asciify()`)
    - is safe for URL

    *Examples:*

    >>> slugify('Top 10 Reasons To Love Dogs!!!') # returns: 'top-10-reasons-to-love-dogs'
    >>> slugify('Mönstér Mägnët') # returns 'monster-magnet'

    :param input_string: String to convert.
    :type input_string: str
    :param separator: Sign used to join string tokens (default to "-").
    :type separator: str
    :return: Slug string
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    # replace any character that is NOT letter or number with spaces
    out = NO_LETTERS_OR_NUMBERS_RE.sub(' ', input_string.upper()).strip()

    # replace spaces with join sign
    out = SPACES_RE.sub(separator, out)

    # normalize joins (remove duplicates)
    out = re.sub(re.escape(separator) + r'+', separator, out)

    return asciify(out)


def x_slugify__mutmut_12(input_string: str, separator: str = '-') -> str:
    """
    Converts a string into a "slug" using provided separator.
    The returned string has the following properties:

    - it has no spaces
    - all letters are in lower case
    - all punctuation signs and non alphanumeric chars are removed
    - words are divided using provided separator
    - all chars are encoded as ascii (by using `asciify()`)
    - is safe for URL

    *Examples:*

    >>> slugify('Top 10 Reasons To Love Dogs!!!') # returns: 'top-10-reasons-to-love-dogs'
    >>> slugify('Mönstér Mägnët') # returns 'monster-magnet'

    :param input_string: String to convert.
    :type input_string: str
    :param separator: Sign used to join string tokens (default to "-").
    :type separator: str
    :return: Slug string
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    # replace any character that is NOT letter or number with spaces
    out = NO_LETTERS_OR_NUMBERS_RE.sub(' ', input_string.lower()).strip()

    # replace spaces with join sign
    out = None

    # normalize joins (remove duplicates)
    out = re.sub(re.escape(separator) + r'+', separator, out)

    return asciify(out)


def x_slugify__mutmut_13(input_string: str, separator: str = '-') -> str:
    """
    Converts a string into a "slug" using provided separator.
    The returned string has the following properties:

    - it has no spaces
    - all letters are in lower case
    - all punctuation signs and non alphanumeric chars are removed
    - words are divided using provided separator
    - all chars are encoded as ascii (by using `asciify()`)
    - is safe for URL

    *Examples:*

    >>> slugify('Top 10 Reasons To Love Dogs!!!') # returns: 'top-10-reasons-to-love-dogs'
    >>> slugify('Mönstér Mägnët') # returns 'monster-magnet'

    :param input_string: String to convert.
    :type input_string: str
    :param separator: Sign used to join string tokens (default to "-").
    :type separator: str
    :return: Slug string
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    # replace any character that is NOT letter or number with spaces
    out = NO_LETTERS_OR_NUMBERS_RE.sub(' ', input_string.lower()).strip()

    # replace spaces with join sign
    out = SPACES_RE.sub(None, out)

    # normalize joins (remove duplicates)
    out = re.sub(re.escape(separator) + r'+', separator, out)

    return asciify(out)


def x_slugify__mutmut_14(input_string: str, separator: str = '-') -> str:
    """
    Converts a string into a "slug" using provided separator.
    The returned string has the following properties:

    - it has no spaces
    - all letters are in lower case
    - all punctuation signs and non alphanumeric chars are removed
    - words are divided using provided separator
    - all chars are encoded as ascii (by using `asciify()`)
    - is safe for URL

    *Examples:*

    >>> slugify('Top 10 Reasons To Love Dogs!!!') # returns: 'top-10-reasons-to-love-dogs'
    >>> slugify('Mönstér Mägnët') # returns 'monster-magnet'

    :param input_string: String to convert.
    :type input_string: str
    :param separator: Sign used to join string tokens (default to "-").
    :type separator: str
    :return: Slug string
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    # replace any character that is NOT letter or number with spaces
    out = NO_LETTERS_OR_NUMBERS_RE.sub(' ', input_string.lower()).strip()

    # replace spaces with join sign
    out = SPACES_RE.sub(separator, None)

    # normalize joins (remove duplicates)
    out = re.sub(re.escape(separator) + r'+', separator, out)

    return asciify(out)


def x_slugify__mutmut_15(input_string: str, separator: str = '-') -> str:
    """
    Converts a string into a "slug" using provided separator.
    The returned string has the following properties:

    - it has no spaces
    - all letters are in lower case
    - all punctuation signs and non alphanumeric chars are removed
    - words are divided using provided separator
    - all chars are encoded as ascii (by using `asciify()`)
    - is safe for URL

    *Examples:*

    >>> slugify('Top 10 Reasons To Love Dogs!!!') # returns: 'top-10-reasons-to-love-dogs'
    >>> slugify('Mönstér Mägnët') # returns 'monster-magnet'

    :param input_string: String to convert.
    :type input_string: str
    :param separator: Sign used to join string tokens (default to "-").
    :type separator: str
    :return: Slug string
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    # replace any character that is NOT letter or number with spaces
    out = NO_LETTERS_OR_NUMBERS_RE.sub(' ', input_string.lower()).strip()

    # replace spaces with join sign
    out = SPACES_RE.sub(out)

    # normalize joins (remove duplicates)
    out = re.sub(re.escape(separator) + r'+', separator, out)

    return asciify(out)


def x_slugify__mutmut_16(input_string: str, separator: str = '-') -> str:
    """
    Converts a string into a "slug" using provided separator.
    The returned string has the following properties:

    - it has no spaces
    - all letters are in lower case
    - all punctuation signs and non alphanumeric chars are removed
    - words are divided using provided separator
    - all chars are encoded as ascii (by using `asciify()`)
    - is safe for URL

    *Examples:*

    >>> slugify('Top 10 Reasons To Love Dogs!!!') # returns: 'top-10-reasons-to-love-dogs'
    >>> slugify('Mönstér Mägnët') # returns 'monster-magnet'

    :param input_string: String to convert.
    :type input_string: str
    :param separator: Sign used to join string tokens (default to "-").
    :type separator: str
    :return: Slug string
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    # replace any character that is NOT letter or number with spaces
    out = NO_LETTERS_OR_NUMBERS_RE.sub(' ', input_string.lower()).strip()

    # replace spaces with join sign
    out = SPACES_RE.sub(separator, )

    # normalize joins (remove duplicates)
    out = re.sub(re.escape(separator) + r'+', separator, out)

    return asciify(out)


def x_slugify__mutmut_17(input_string: str, separator: str = '-') -> str:
    """
    Converts a string into a "slug" using provided separator.
    The returned string has the following properties:

    - it has no spaces
    - all letters are in lower case
    - all punctuation signs and non alphanumeric chars are removed
    - words are divided using provided separator
    - all chars are encoded as ascii (by using `asciify()`)
    - is safe for URL

    *Examples:*

    >>> slugify('Top 10 Reasons To Love Dogs!!!') # returns: 'top-10-reasons-to-love-dogs'
    >>> slugify('Mönstér Mägnët') # returns 'monster-magnet'

    :param input_string: String to convert.
    :type input_string: str
    :param separator: Sign used to join string tokens (default to "-").
    :type separator: str
    :return: Slug string
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    # replace any character that is NOT letter or number with spaces
    out = NO_LETTERS_OR_NUMBERS_RE.sub(' ', input_string.lower()).strip()

    # replace spaces with join sign
    out = SPACES_RE.sub(separator, out)

    # normalize joins (remove duplicates)
    out = None

    return asciify(out)


def x_slugify__mutmut_18(input_string: str, separator: str = '-') -> str:
    """
    Converts a string into a "slug" using provided separator.
    The returned string has the following properties:

    - it has no spaces
    - all letters are in lower case
    - all punctuation signs and non alphanumeric chars are removed
    - words are divided using provided separator
    - all chars are encoded as ascii (by using `asciify()`)
    - is safe for URL

    *Examples:*

    >>> slugify('Top 10 Reasons To Love Dogs!!!') # returns: 'top-10-reasons-to-love-dogs'
    >>> slugify('Mönstér Mägnët') # returns 'monster-magnet'

    :param input_string: String to convert.
    :type input_string: str
    :param separator: Sign used to join string tokens (default to "-").
    :type separator: str
    :return: Slug string
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    # replace any character that is NOT letter or number with spaces
    out = NO_LETTERS_OR_NUMBERS_RE.sub(' ', input_string.lower()).strip()

    # replace spaces with join sign
    out = SPACES_RE.sub(separator, out)

    # normalize joins (remove duplicates)
    out = re.sub(None, separator, out)

    return asciify(out)


def x_slugify__mutmut_19(input_string: str, separator: str = '-') -> str:
    """
    Converts a string into a "slug" using provided separator.
    The returned string has the following properties:

    - it has no spaces
    - all letters are in lower case
    - all punctuation signs and non alphanumeric chars are removed
    - words are divided using provided separator
    - all chars are encoded as ascii (by using `asciify()`)
    - is safe for URL

    *Examples:*

    >>> slugify('Top 10 Reasons To Love Dogs!!!') # returns: 'top-10-reasons-to-love-dogs'
    >>> slugify('Mönstér Mägnët') # returns 'monster-magnet'

    :param input_string: String to convert.
    :type input_string: str
    :param separator: Sign used to join string tokens (default to "-").
    :type separator: str
    :return: Slug string
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    # replace any character that is NOT letter or number with spaces
    out = NO_LETTERS_OR_NUMBERS_RE.sub(' ', input_string.lower()).strip()

    # replace spaces with join sign
    out = SPACES_RE.sub(separator, out)

    # normalize joins (remove duplicates)
    out = re.sub(re.escape(separator) + r'+', None, out)

    return asciify(out)


def x_slugify__mutmut_20(input_string: str, separator: str = '-') -> str:
    """
    Converts a string into a "slug" using provided separator.
    The returned string has the following properties:

    - it has no spaces
    - all letters are in lower case
    - all punctuation signs and non alphanumeric chars are removed
    - words are divided using provided separator
    - all chars are encoded as ascii (by using `asciify()`)
    - is safe for URL

    *Examples:*

    >>> slugify('Top 10 Reasons To Love Dogs!!!') # returns: 'top-10-reasons-to-love-dogs'
    >>> slugify('Mönstér Mägnët') # returns 'monster-magnet'

    :param input_string: String to convert.
    :type input_string: str
    :param separator: Sign used to join string tokens (default to "-").
    :type separator: str
    :return: Slug string
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    # replace any character that is NOT letter or number with spaces
    out = NO_LETTERS_OR_NUMBERS_RE.sub(' ', input_string.lower()).strip()

    # replace spaces with join sign
    out = SPACES_RE.sub(separator, out)

    # normalize joins (remove duplicates)
    out = re.sub(re.escape(separator) + r'+', separator, None)

    return asciify(out)


def x_slugify__mutmut_21(input_string: str, separator: str = '-') -> str:
    """
    Converts a string into a "slug" using provided separator.
    The returned string has the following properties:

    - it has no spaces
    - all letters are in lower case
    - all punctuation signs and non alphanumeric chars are removed
    - words are divided using provided separator
    - all chars are encoded as ascii (by using `asciify()`)
    - is safe for URL

    *Examples:*

    >>> slugify('Top 10 Reasons To Love Dogs!!!') # returns: 'top-10-reasons-to-love-dogs'
    >>> slugify('Mönstér Mägnët') # returns 'monster-magnet'

    :param input_string: String to convert.
    :type input_string: str
    :param separator: Sign used to join string tokens (default to "-").
    :type separator: str
    :return: Slug string
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    # replace any character that is NOT letter or number with spaces
    out = NO_LETTERS_OR_NUMBERS_RE.sub(' ', input_string.lower()).strip()

    # replace spaces with join sign
    out = SPACES_RE.sub(separator, out)

    # normalize joins (remove duplicates)
    out = re.sub(separator, out)

    return asciify(out)


def x_slugify__mutmut_22(input_string: str, separator: str = '-') -> str:
    """
    Converts a string into a "slug" using provided separator.
    The returned string has the following properties:

    - it has no spaces
    - all letters are in lower case
    - all punctuation signs and non alphanumeric chars are removed
    - words are divided using provided separator
    - all chars are encoded as ascii (by using `asciify()`)
    - is safe for URL

    *Examples:*

    >>> slugify('Top 10 Reasons To Love Dogs!!!') # returns: 'top-10-reasons-to-love-dogs'
    >>> slugify('Mönstér Mägnët') # returns 'monster-magnet'

    :param input_string: String to convert.
    :type input_string: str
    :param separator: Sign used to join string tokens (default to "-").
    :type separator: str
    :return: Slug string
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    # replace any character that is NOT letter or number with spaces
    out = NO_LETTERS_OR_NUMBERS_RE.sub(' ', input_string.lower()).strip()

    # replace spaces with join sign
    out = SPACES_RE.sub(separator, out)

    # normalize joins (remove duplicates)
    out = re.sub(re.escape(separator) + r'+', out)

    return asciify(out)


def x_slugify__mutmut_23(input_string: str, separator: str = '-') -> str:
    """
    Converts a string into a "slug" using provided separator.
    The returned string has the following properties:

    - it has no spaces
    - all letters are in lower case
    - all punctuation signs and non alphanumeric chars are removed
    - words are divided using provided separator
    - all chars are encoded as ascii (by using `asciify()`)
    - is safe for URL

    *Examples:*

    >>> slugify('Top 10 Reasons To Love Dogs!!!') # returns: 'top-10-reasons-to-love-dogs'
    >>> slugify('Mönstér Mägnët') # returns 'monster-magnet'

    :param input_string: String to convert.
    :type input_string: str
    :param separator: Sign used to join string tokens (default to "-").
    :type separator: str
    :return: Slug string
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    # replace any character that is NOT letter or number with spaces
    out = NO_LETTERS_OR_NUMBERS_RE.sub(' ', input_string.lower()).strip()

    # replace spaces with join sign
    out = SPACES_RE.sub(separator, out)

    # normalize joins (remove duplicates)
    out = re.sub(re.escape(separator) + r'+', separator, )

    return asciify(out)


def x_slugify__mutmut_24(input_string: str, separator: str = '-') -> str:
    """
    Converts a string into a "slug" using provided separator.
    The returned string has the following properties:

    - it has no spaces
    - all letters are in lower case
    - all punctuation signs and non alphanumeric chars are removed
    - words are divided using provided separator
    - all chars are encoded as ascii (by using `asciify()`)
    - is safe for URL

    *Examples:*

    >>> slugify('Top 10 Reasons To Love Dogs!!!') # returns: 'top-10-reasons-to-love-dogs'
    >>> slugify('Mönstér Mägnët') # returns 'monster-magnet'

    :param input_string: String to convert.
    :type input_string: str
    :param separator: Sign used to join string tokens (default to "-").
    :type separator: str
    :return: Slug string
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    # replace any character that is NOT letter or number with spaces
    out = NO_LETTERS_OR_NUMBERS_RE.sub(' ', input_string.lower()).strip()

    # replace spaces with join sign
    out = SPACES_RE.sub(separator, out)

    # normalize joins (remove duplicates)
    out = re.sub(re.escape(separator) - r'+', separator, out)

    return asciify(out)


def x_slugify__mutmut_25(input_string: str, separator: str = '-') -> str:
    """
    Converts a string into a "slug" using provided separator.
    The returned string has the following properties:

    - it has no spaces
    - all letters are in lower case
    - all punctuation signs and non alphanumeric chars are removed
    - words are divided using provided separator
    - all chars are encoded as ascii (by using `asciify()`)
    - is safe for URL

    *Examples:*

    >>> slugify('Top 10 Reasons To Love Dogs!!!') # returns: 'top-10-reasons-to-love-dogs'
    >>> slugify('Mönstér Mägnët') # returns 'monster-magnet'

    :param input_string: String to convert.
    :type input_string: str
    :param separator: Sign used to join string tokens (default to "-").
    :type separator: str
    :return: Slug string
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    # replace any character that is NOT letter or number with spaces
    out = NO_LETTERS_OR_NUMBERS_RE.sub(' ', input_string.lower()).strip()

    # replace spaces with join sign
    out = SPACES_RE.sub(separator, out)

    # normalize joins (remove duplicates)
    out = re.sub(re.escape(None) + r'+', separator, out)

    return asciify(out)


def x_slugify__mutmut_26(input_string: str, separator: str = '-') -> str:
    """
    Converts a string into a "slug" using provided separator.
    The returned string has the following properties:

    - it has no spaces
    - all letters are in lower case
    - all punctuation signs and non alphanumeric chars are removed
    - words are divided using provided separator
    - all chars are encoded as ascii (by using `asciify()`)
    - is safe for URL

    *Examples:*

    >>> slugify('Top 10 Reasons To Love Dogs!!!') # returns: 'top-10-reasons-to-love-dogs'
    >>> slugify('Mönstér Mägnët') # returns 'monster-magnet'

    :param input_string: String to convert.
    :type input_string: str
    :param separator: Sign used to join string tokens (default to "-").
    :type separator: str
    :return: Slug string
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    # replace any character that is NOT letter or number with spaces
    out = NO_LETTERS_OR_NUMBERS_RE.sub(' ', input_string.lower()).strip()

    # replace spaces with join sign
    out = SPACES_RE.sub(separator, out)

    # normalize joins (remove duplicates)
    out = re.sub(re.escape(separator) + r'XX+XX', separator, out)

    return asciify(out)


def x_slugify__mutmut_27(input_string: str, separator: str = '-') -> str:
    """
    Converts a string into a "slug" using provided separator.
    The returned string has the following properties:

    - it has no spaces
    - all letters are in lower case
    - all punctuation signs and non alphanumeric chars are removed
    - words are divided using provided separator
    - all chars are encoded as ascii (by using `asciify()`)
    - is safe for URL

    *Examples:*

    >>> slugify('Top 10 Reasons To Love Dogs!!!') # returns: 'top-10-reasons-to-love-dogs'
    >>> slugify('Mönstér Mägnët') # returns 'monster-magnet'

    :param input_string: String to convert.
    :type input_string: str
    :param separator: Sign used to join string tokens (default to "-").
    :type separator: str
    :return: Slug string
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    # replace any character that is NOT letter or number with spaces
    out = NO_LETTERS_OR_NUMBERS_RE.sub(' ', input_string.lower()).strip()

    # replace spaces with join sign
    out = SPACES_RE.sub(separator, out)

    # normalize joins (remove duplicates)
    out = re.sub(re.escape(separator) + r'+', separator, out)

    return asciify(None)

x_slugify__mutmut_mutants : ClassVar[MutantDict] = { # type: ignore
'x_slugify__mutmut_1': x_slugify__mutmut_1, 
    'x_slugify__mutmut_2': x_slugify__mutmut_2, 
    'x_slugify__mutmut_3': x_slugify__mutmut_3, 
    'x_slugify__mutmut_4': x_slugify__mutmut_4, 
    'x_slugify__mutmut_5': x_slugify__mutmut_5, 
    'x_slugify__mutmut_6': x_slugify__mutmut_6, 
    'x_slugify__mutmut_7': x_slugify__mutmut_7, 
    'x_slugify__mutmut_8': x_slugify__mutmut_8, 
    'x_slugify__mutmut_9': x_slugify__mutmut_9, 
    'x_slugify__mutmut_10': x_slugify__mutmut_10, 
    'x_slugify__mutmut_11': x_slugify__mutmut_11, 
    'x_slugify__mutmut_12': x_slugify__mutmut_12, 
    'x_slugify__mutmut_13': x_slugify__mutmut_13, 
    'x_slugify__mutmut_14': x_slugify__mutmut_14, 
    'x_slugify__mutmut_15': x_slugify__mutmut_15, 
    'x_slugify__mutmut_16': x_slugify__mutmut_16, 
    'x_slugify__mutmut_17': x_slugify__mutmut_17, 
    'x_slugify__mutmut_18': x_slugify__mutmut_18, 
    'x_slugify__mutmut_19': x_slugify__mutmut_19, 
    'x_slugify__mutmut_20': x_slugify__mutmut_20, 
    'x_slugify__mutmut_21': x_slugify__mutmut_21, 
    'x_slugify__mutmut_22': x_slugify__mutmut_22, 
    'x_slugify__mutmut_23': x_slugify__mutmut_23, 
    'x_slugify__mutmut_24': x_slugify__mutmut_24, 
    'x_slugify__mutmut_25': x_slugify__mutmut_25, 
    'x_slugify__mutmut_26': x_slugify__mutmut_26, 
    'x_slugify__mutmut_27': x_slugify__mutmut_27
}
x_slugify__mutmut_orig.__name__ = 'x_slugify'


def booleanize(input_string: str) -> bool:
    args = [input_string]# type: ignore
    kwargs = {}# type: ignore
    return _mutmut_trampoline(x_booleanize__mutmut_orig, x_booleanize__mutmut_mutants, args, kwargs, None)


def x_booleanize__mutmut_orig(input_string: str) -> bool:
    """
    Turns a string into a boolean based on its content (CASE INSENSITIVE).

    A positive boolean (True) is returned if the string value is one of the following:

    - "true"
    - "1"
    - "yes"
    - "y"

    Otherwise False is returned.

    *Examples:*

    >>> booleanize('true') # returns True
    >>> booleanize('YES') # returns True
    >>> booleanize('nope') # returns False

    :param input_string: String to convert
    :type input_string: str
    :return: True if the string contains a boolean-like positive value, false otherwise
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    return input_string.lower() in ('true', '1', 'yes', 'y')


def x_booleanize__mutmut_1(input_string: str) -> bool:
    """
    Turns a string into a boolean based on its content (CASE INSENSITIVE).

    A positive boolean (True) is returned if the string value is one of the following:

    - "true"
    - "1"
    - "yes"
    - "y"

    Otherwise False is returned.

    *Examples:*

    >>> booleanize('true') # returns True
    >>> booleanize('YES') # returns True
    >>> booleanize('nope') # returns False

    :param input_string: String to convert
    :type input_string: str
    :return: True if the string contains a boolean-like positive value, false otherwise
    """
    if is_string(input_string):
        raise InvalidInputError(input_string)

    return input_string.lower() in ('true', '1', 'yes', 'y')


def x_booleanize__mutmut_2(input_string: str) -> bool:
    """
    Turns a string into a boolean based on its content (CASE INSENSITIVE).

    A positive boolean (True) is returned if the string value is one of the following:

    - "true"
    - "1"
    - "yes"
    - "y"

    Otherwise False is returned.

    *Examples:*

    >>> booleanize('true') # returns True
    >>> booleanize('YES') # returns True
    >>> booleanize('nope') # returns False

    :param input_string: String to convert
    :type input_string: str
    :return: True if the string contains a boolean-like positive value, false otherwise
    """
    if not is_string(None):
        raise InvalidInputError(input_string)

    return input_string.lower() in ('true', '1', 'yes', 'y')


def x_booleanize__mutmut_3(input_string: str) -> bool:
    """
    Turns a string into a boolean based on its content (CASE INSENSITIVE).

    A positive boolean (True) is returned if the string value is one of the following:

    - "true"
    - "1"
    - "yes"
    - "y"

    Otherwise False is returned.

    *Examples:*

    >>> booleanize('true') # returns True
    >>> booleanize('YES') # returns True
    >>> booleanize('nope') # returns False

    :param input_string: String to convert
    :type input_string: str
    :return: True if the string contains a boolean-like positive value, false otherwise
    """
    if not is_string(input_string):
        raise InvalidInputError(None)

    return input_string.lower() in ('true', '1', 'yes', 'y')


def x_booleanize__mutmut_4(input_string: str) -> bool:
    """
    Turns a string into a boolean based on its content (CASE INSENSITIVE).

    A positive boolean (True) is returned if the string value is one of the following:

    - "true"
    - "1"
    - "yes"
    - "y"

    Otherwise False is returned.

    *Examples:*

    >>> booleanize('true') # returns True
    >>> booleanize('YES') # returns True
    >>> booleanize('nope') # returns False

    :param input_string: String to convert
    :type input_string: str
    :return: True if the string contains a boolean-like positive value, false otherwise
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    return input_string.upper() in ('true', '1', 'yes', 'y')


def x_booleanize__mutmut_5(input_string: str) -> bool:
    """
    Turns a string into a boolean based on its content (CASE INSENSITIVE).

    A positive boolean (True) is returned if the string value is one of the following:

    - "true"
    - "1"
    - "yes"
    - "y"

    Otherwise False is returned.

    *Examples:*

    >>> booleanize('true') # returns True
    >>> booleanize('YES') # returns True
    >>> booleanize('nope') # returns False

    :param input_string: String to convert
    :type input_string: str
    :return: True if the string contains a boolean-like positive value, false otherwise
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    return input_string.lower() not in ('true', '1', 'yes', 'y')


def x_booleanize__mutmut_6(input_string: str) -> bool:
    """
    Turns a string into a boolean based on its content (CASE INSENSITIVE).

    A positive boolean (True) is returned if the string value is one of the following:

    - "true"
    - "1"
    - "yes"
    - "y"

    Otherwise False is returned.

    *Examples:*

    >>> booleanize('true') # returns True
    >>> booleanize('YES') # returns True
    >>> booleanize('nope') # returns False

    :param input_string: String to convert
    :type input_string: str
    :return: True if the string contains a boolean-like positive value, false otherwise
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    return input_string.lower() in ('XXtrueXX', '1', 'yes', 'y')


def x_booleanize__mutmut_7(input_string: str) -> bool:
    """
    Turns a string into a boolean based on its content (CASE INSENSITIVE).

    A positive boolean (True) is returned if the string value is one of the following:

    - "true"
    - "1"
    - "yes"
    - "y"

    Otherwise False is returned.

    *Examples:*

    >>> booleanize('true') # returns True
    >>> booleanize('YES') # returns True
    >>> booleanize('nope') # returns False

    :param input_string: String to convert
    :type input_string: str
    :return: True if the string contains a boolean-like positive value, false otherwise
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    return input_string.lower() in ('TRUE', '1', 'yes', 'y')


def x_booleanize__mutmut_8(input_string: str) -> bool:
    """
    Turns a string into a boolean based on its content (CASE INSENSITIVE).

    A positive boolean (True) is returned if the string value is one of the following:

    - "true"
    - "1"
    - "yes"
    - "y"

    Otherwise False is returned.

    *Examples:*

    >>> booleanize('true') # returns True
    >>> booleanize('YES') # returns True
    >>> booleanize('nope') # returns False

    :param input_string: String to convert
    :type input_string: str
    :return: True if the string contains a boolean-like positive value, false otherwise
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    return input_string.lower() in ('true', 'XX1XX', 'yes', 'y')


def x_booleanize__mutmut_9(input_string: str) -> bool:
    """
    Turns a string into a boolean based on its content (CASE INSENSITIVE).

    A positive boolean (True) is returned if the string value is one of the following:

    - "true"
    - "1"
    - "yes"
    - "y"

    Otherwise False is returned.

    *Examples:*

    >>> booleanize('true') # returns True
    >>> booleanize('YES') # returns True
    >>> booleanize('nope') # returns False

    :param input_string: String to convert
    :type input_string: str
    :return: True if the string contains a boolean-like positive value, false otherwise
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    return input_string.lower() in ('true', '1', 'XXyesXX', 'y')


def x_booleanize__mutmut_10(input_string: str) -> bool:
    """
    Turns a string into a boolean based on its content (CASE INSENSITIVE).

    A positive boolean (True) is returned if the string value is one of the following:

    - "true"
    - "1"
    - "yes"
    - "y"

    Otherwise False is returned.

    *Examples:*

    >>> booleanize('true') # returns True
    >>> booleanize('YES') # returns True
    >>> booleanize('nope') # returns False

    :param input_string: String to convert
    :type input_string: str
    :return: True if the string contains a boolean-like positive value, false otherwise
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    return input_string.lower() in ('true', '1', 'YES', 'y')


def x_booleanize__mutmut_11(input_string: str) -> bool:
    """
    Turns a string into a boolean based on its content (CASE INSENSITIVE).

    A positive boolean (True) is returned if the string value is one of the following:

    - "true"
    - "1"
    - "yes"
    - "y"

    Otherwise False is returned.

    *Examples:*

    >>> booleanize('true') # returns True
    >>> booleanize('YES') # returns True
    >>> booleanize('nope') # returns False

    :param input_string: String to convert
    :type input_string: str
    :return: True if the string contains a boolean-like positive value, false otherwise
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    return input_string.lower() in ('true', '1', 'yes', 'XXyXX')


def x_booleanize__mutmut_12(input_string: str) -> bool:
    """
    Turns a string into a boolean based on its content (CASE INSENSITIVE).

    A positive boolean (True) is returned if the string value is one of the following:

    - "true"
    - "1"
    - "yes"
    - "y"

    Otherwise False is returned.

    *Examples:*

    >>> booleanize('true') # returns True
    >>> booleanize('YES') # returns True
    >>> booleanize('nope') # returns False

    :param input_string: String to convert
    :type input_string: str
    :return: True if the string contains a boolean-like positive value, false otherwise
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    return input_string.lower() in ('true', '1', 'yes', 'Y')

x_booleanize__mutmut_mutants : ClassVar[MutantDict] = { # type: ignore
'x_booleanize__mutmut_1': x_booleanize__mutmut_1, 
    'x_booleanize__mutmut_2': x_booleanize__mutmut_2, 
    'x_booleanize__mutmut_3': x_booleanize__mutmut_3, 
    'x_booleanize__mutmut_4': x_booleanize__mutmut_4, 
    'x_booleanize__mutmut_5': x_booleanize__mutmut_5, 
    'x_booleanize__mutmut_6': x_booleanize__mutmut_6, 
    'x_booleanize__mutmut_7': x_booleanize__mutmut_7, 
    'x_booleanize__mutmut_8': x_booleanize__mutmut_8, 
    'x_booleanize__mutmut_9': x_booleanize__mutmut_9, 
    'x_booleanize__mutmut_10': x_booleanize__mutmut_10, 
    'x_booleanize__mutmut_11': x_booleanize__mutmut_11, 
    'x_booleanize__mutmut_12': x_booleanize__mutmut_12
}
x_booleanize__mutmut_orig.__name__ = 'x_booleanize'


def strip_margin(input_string: str) -> str:
    args = [input_string]# type: ignore
    kwargs = {}# type: ignore
    return _mutmut_trampoline(x_strip_margin__mutmut_orig, x_strip_margin__mutmut_mutants, args, kwargs, None)


def x_strip_margin__mutmut_orig(input_string: str) -> str:
    """
    Removes tab indentation from multi line strings (inspired by analogous Scala function).

    *Example:*

    >>> strip_margin('''
    >>>                 line 1
    >>>                 line 2
    >>>                 line 3
    >>> ''')
    >>> # returns:
    >>> '''
    >>> line 1
    >>> line 2
    >>> line 3
    >>> '''

    :param input_string: String to format
    :type input_string: str
    :return: A string without left margins
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    line_separator = '\n'
    lines = [MARGIN_RE.sub('', line) for line in input_string.split(line_separator)]
    out = line_separator.join(lines)

    return out


def x_strip_margin__mutmut_1(input_string: str) -> str:
    """
    Removes tab indentation from multi line strings (inspired by analogous Scala function).

    *Example:*

    >>> strip_margin('''
    >>>                 line 1
    >>>                 line 2
    >>>                 line 3
    >>> ''')
    >>> # returns:
    >>> '''
    >>> line 1
    >>> line 2
    >>> line 3
    >>> '''

    :param input_string: String to format
    :type input_string: str
    :return: A string without left margins
    """
    if is_string(input_string):
        raise InvalidInputError(input_string)

    line_separator = '\n'
    lines = [MARGIN_RE.sub('', line) for line in input_string.split(line_separator)]
    out = line_separator.join(lines)

    return out


def x_strip_margin__mutmut_2(input_string: str) -> str:
    """
    Removes tab indentation from multi line strings (inspired by analogous Scala function).

    *Example:*

    >>> strip_margin('''
    >>>                 line 1
    >>>                 line 2
    >>>                 line 3
    >>> ''')
    >>> # returns:
    >>> '''
    >>> line 1
    >>> line 2
    >>> line 3
    >>> '''

    :param input_string: String to format
    :type input_string: str
    :return: A string without left margins
    """
    if not is_string(None):
        raise InvalidInputError(input_string)

    line_separator = '\n'
    lines = [MARGIN_RE.sub('', line) for line in input_string.split(line_separator)]
    out = line_separator.join(lines)

    return out


def x_strip_margin__mutmut_3(input_string: str) -> str:
    """
    Removes tab indentation from multi line strings (inspired by analogous Scala function).

    *Example:*

    >>> strip_margin('''
    >>>                 line 1
    >>>                 line 2
    >>>                 line 3
    >>> ''')
    >>> # returns:
    >>> '''
    >>> line 1
    >>> line 2
    >>> line 3
    >>> '''

    :param input_string: String to format
    :type input_string: str
    :return: A string without left margins
    """
    if not is_string(input_string):
        raise InvalidInputError(None)

    line_separator = '\n'
    lines = [MARGIN_RE.sub('', line) for line in input_string.split(line_separator)]
    out = line_separator.join(lines)

    return out


def x_strip_margin__mutmut_4(input_string: str) -> str:
    """
    Removes tab indentation from multi line strings (inspired by analogous Scala function).

    *Example:*

    >>> strip_margin('''
    >>>                 line 1
    >>>                 line 2
    >>>                 line 3
    >>> ''')
    >>> # returns:
    >>> '''
    >>> line 1
    >>> line 2
    >>> line 3
    >>> '''

    :param input_string: String to format
    :type input_string: str
    :return: A string without left margins
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    line_separator = None
    lines = [MARGIN_RE.sub('', line) for line in input_string.split(line_separator)]
    out = line_separator.join(lines)

    return out


def x_strip_margin__mutmut_5(input_string: str) -> str:
    """
    Removes tab indentation from multi line strings (inspired by analogous Scala function).

    *Example:*

    >>> strip_margin('''
    >>>                 line 1
    >>>                 line 2
    >>>                 line 3
    >>> ''')
    >>> # returns:
    >>> '''
    >>> line 1
    >>> line 2
    >>> line 3
    >>> '''

    :param input_string: String to format
    :type input_string: str
    :return: A string without left margins
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    line_separator = 'XX\nXX'
    lines = [MARGIN_RE.sub('', line) for line in input_string.split(line_separator)]
    out = line_separator.join(lines)

    return out


def x_strip_margin__mutmut_6(input_string: str) -> str:
    """
    Removes tab indentation from multi line strings (inspired by analogous Scala function).

    *Example:*

    >>> strip_margin('''
    >>>                 line 1
    >>>                 line 2
    >>>                 line 3
    >>> ''')
    >>> # returns:
    >>> '''
    >>> line 1
    >>> line 2
    >>> line 3
    >>> '''

    :param input_string: String to format
    :type input_string: str
    :return: A string without left margins
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    line_separator = '\n'
    lines = None
    out = line_separator.join(lines)

    return out


def x_strip_margin__mutmut_7(input_string: str) -> str:
    """
    Removes tab indentation from multi line strings (inspired by analogous Scala function).

    *Example:*

    >>> strip_margin('''
    >>>                 line 1
    >>>                 line 2
    >>>                 line 3
    >>> ''')
    >>> # returns:
    >>> '''
    >>> line 1
    >>> line 2
    >>> line 3
    >>> '''

    :param input_string: String to format
    :type input_string: str
    :return: A string without left margins
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    line_separator = '\n'
    lines = [MARGIN_RE.sub(None, line) for line in input_string.split(line_separator)]
    out = line_separator.join(lines)

    return out


def x_strip_margin__mutmut_8(input_string: str) -> str:
    """
    Removes tab indentation from multi line strings (inspired by analogous Scala function).

    *Example:*

    >>> strip_margin('''
    >>>                 line 1
    >>>                 line 2
    >>>                 line 3
    >>> ''')
    >>> # returns:
    >>> '''
    >>> line 1
    >>> line 2
    >>> line 3
    >>> '''

    :param input_string: String to format
    :type input_string: str
    :return: A string without left margins
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    line_separator = '\n'
    lines = [MARGIN_RE.sub('', None) for line in input_string.split(line_separator)]
    out = line_separator.join(lines)

    return out


def x_strip_margin__mutmut_9(input_string: str) -> str:
    """
    Removes tab indentation from multi line strings (inspired by analogous Scala function).

    *Example:*

    >>> strip_margin('''
    >>>                 line 1
    >>>                 line 2
    >>>                 line 3
    >>> ''')
    >>> # returns:
    >>> '''
    >>> line 1
    >>> line 2
    >>> line 3
    >>> '''

    :param input_string: String to format
    :type input_string: str
    :return: A string without left margins
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    line_separator = '\n'
    lines = [MARGIN_RE.sub(line) for line in input_string.split(line_separator)]
    out = line_separator.join(lines)

    return out


def x_strip_margin__mutmut_10(input_string: str) -> str:
    """
    Removes tab indentation from multi line strings (inspired by analogous Scala function).

    *Example:*

    >>> strip_margin('''
    >>>                 line 1
    >>>                 line 2
    >>>                 line 3
    >>> ''')
    >>> # returns:
    >>> '''
    >>> line 1
    >>> line 2
    >>> line 3
    >>> '''

    :param input_string: String to format
    :type input_string: str
    :return: A string without left margins
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    line_separator = '\n'
    lines = [MARGIN_RE.sub('', ) for line in input_string.split(line_separator)]
    out = line_separator.join(lines)

    return out


def x_strip_margin__mutmut_11(input_string: str) -> str:
    """
    Removes tab indentation from multi line strings (inspired by analogous Scala function).

    *Example:*

    >>> strip_margin('''
    >>>                 line 1
    >>>                 line 2
    >>>                 line 3
    >>> ''')
    >>> # returns:
    >>> '''
    >>> line 1
    >>> line 2
    >>> line 3
    >>> '''

    :param input_string: String to format
    :type input_string: str
    :return: A string without left margins
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    line_separator = '\n'
    lines = [MARGIN_RE.sub('XXXX', line) for line in input_string.split(line_separator)]
    out = line_separator.join(lines)

    return out


def x_strip_margin__mutmut_12(input_string: str) -> str:
    """
    Removes tab indentation from multi line strings (inspired by analogous Scala function).

    *Example:*

    >>> strip_margin('''
    >>>                 line 1
    >>>                 line 2
    >>>                 line 3
    >>> ''')
    >>> # returns:
    >>> '''
    >>> line 1
    >>> line 2
    >>> line 3
    >>> '''

    :param input_string: String to format
    :type input_string: str
    :return: A string without left margins
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    line_separator = '\n'
    lines = [MARGIN_RE.sub('', line) for line in input_string.split(None)]
    out = line_separator.join(lines)

    return out


def x_strip_margin__mutmut_13(input_string: str) -> str:
    """
    Removes tab indentation from multi line strings (inspired by analogous Scala function).

    *Example:*

    >>> strip_margin('''
    >>>                 line 1
    >>>                 line 2
    >>>                 line 3
    >>> ''')
    >>> # returns:
    >>> '''
    >>> line 1
    >>> line 2
    >>> line 3
    >>> '''

    :param input_string: String to format
    :type input_string: str
    :return: A string without left margins
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    line_separator = '\n'
    lines = [MARGIN_RE.sub('', line) for line in input_string.split(line_separator)]
    out = None

    return out


def x_strip_margin__mutmut_14(input_string: str) -> str:
    """
    Removes tab indentation from multi line strings (inspired by analogous Scala function).

    *Example:*

    >>> strip_margin('''
    >>>                 line 1
    >>>                 line 2
    >>>                 line 3
    >>> ''')
    >>> # returns:
    >>> '''
    >>> line 1
    >>> line 2
    >>> line 3
    >>> '''

    :param input_string: String to format
    :type input_string: str
    :return: A string without left margins
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    line_separator = '\n'
    lines = [MARGIN_RE.sub('', line) for line in input_string.split(line_separator)]
    out = line_separator.join(None)

    return out

x_strip_margin__mutmut_mutants : ClassVar[MutantDict] = { # type: ignore
'x_strip_margin__mutmut_1': x_strip_margin__mutmut_1, 
    'x_strip_margin__mutmut_2': x_strip_margin__mutmut_2, 
    'x_strip_margin__mutmut_3': x_strip_margin__mutmut_3, 
    'x_strip_margin__mutmut_4': x_strip_margin__mutmut_4, 
    'x_strip_margin__mutmut_5': x_strip_margin__mutmut_5, 
    'x_strip_margin__mutmut_6': x_strip_margin__mutmut_6, 
    'x_strip_margin__mutmut_7': x_strip_margin__mutmut_7, 
    'x_strip_margin__mutmut_8': x_strip_margin__mutmut_8, 
    'x_strip_margin__mutmut_9': x_strip_margin__mutmut_9, 
    'x_strip_margin__mutmut_10': x_strip_margin__mutmut_10, 
    'x_strip_margin__mutmut_11': x_strip_margin__mutmut_11, 
    'x_strip_margin__mutmut_12': x_strip_margin__mutmut_12, 
    'x_strip_margin__mutmut_13': x_strip_margin__mutmut_13, 
    'x_strip_margin__mutmut_14': x_strip_margin__mutmut_14
}
x_strip_margin__mutmut_orig.__name__ = 'x_strip_margin'


def compress(input_string: str, encoding: str = 'utf-8', compression_level: int = 9) -> str:
    args = [input_string, encoding, compression_level]# type: ignore
    kwargs = {}# type: ignore
    return _mutmut_trampoline(x_compress__mutmut_orig, x_compress__mutmut_mutants, args, kwargs, None)


def x_compress__mutmut_orig(input_string: str, encoding: str = 'utf-8', compression_level: int = 9) -> str:
    """
    Compress the given string by returning a shorter one that can be safely used in any context (like URL) and
    restored back to its original state using `decompress()`.

    **Bear in mind:**
    Besides the provided `compression_level`, the compression result (how much the string is actually compressed
    by resulting into a shorter string) depends on 2 factors:

    1. The amount of data (string size): short strings might not provide a significant compression result\
    or even be longer than the given input string (this is due to the fact that some bytes have to be embedded\
    into the compressed string in order to be able to restore it later on)\

    2. The content type: random sequences of chars are very unlikely to be successfully compressed, while the best\
    compression result is obtained when the string contains several recurring char sequences (like in the example).

    Behind the scenes this method makes use of the standard Python's zlib and base64 libraries.

    *Examples:*

    >>> n = 0 # <- ignore this, it's a fix for Pycharm (not fixable using ignore comments)
    >>> # "original" will be a string with 169 chars:
    >>> original = ' '.join(['word n{}'.format(n) for n in range(20)])
    >>> # "compressed" will be a string of 88 chars
    >>> compressed = compress(original)

    :param input_string: String to compress (must be not empty or a ValueError will be raised).
    :type input_string: str
    :param encoding: String encoding (default to "utf-8").
    :type encoding: str
    :param compression_level: A value between 0 (no compression) and 9 (best compression), default to 9.
    :type compression_level: int
    :return: Compressed string.
    """
    return __StringCompressor.compress(input_string, encoding, compression_level)


def x_compress__mutmut_1(input_string: str, encoding: str = 'XXutf-8XX', compression_level: int = 9) -> str:
    """
    Compress the given string by returning a shorter one that can be safely used in any context (like URL) and
    restored back to its original state using `decompress()`.

    **Bear in mind:**
    Besides the provided `compression_level`, the compression result (how much the string is actually compressed
    by resulting into a shorter string) depends on 2 factors:

    1. The amount of data (string size): short strings might not provide a significant compression result\
    or even be longer than the given input string (this is due to the fact that some bytes have to be embedded\
    into the compressed string in order to be able to restore it later on)\

    2. The content type: random sequences of chars are very unlikely to be successfully compressed, while the best\
    compression result is obtained when the string contains several recurring char sequences (like in the example).

    Behind the scenes this method makes use of the standard Python's zlib and base64 libraries.

    *Examples:*

    >>> n = 0 # <- ignore this, it's a fix for Pycharm (not fixable using ignore comments)
    >>> # "original" will be a string with 169 chars:
    >>> original = ' '.join(['word n{}'.format(n) for n in range(20)])
    >>> # "compressed" will be a string of 88 chars
    >>> compressed = compress(original)

    :param input_string: String to compress (must be not empty or a ValueError will be raised).
    :type input_string: str
    :param encoding: String encoding (default to "utf-8").
    :type encoding: str
    :param compression_level: A value between 0 (no compression) and 9 (best compression), default to 9.
    :type compression_level: int
    :return: Compressed string.
    """
    return __StringCompressor.compress(input_string, encoding, compression_level)


def x_compress__mutmut_2(input_string: str, encoding: str = 'UTF-8', compression_level: int = 9) -> str:
    """
    Compress the given string by returning a shorter one that can be safely used in any context (like URL) and
    restored back to its original state using `decompress()`.

    **Bear in mind:**
    Besides the provided `compression_level`, the compression result (how much the string is actually compressed
    by resulting into a shorter string) depends on 2 factors:

    1. The amount of data (string size): short strings might not provide a significant compression result\
    or even be longer than the given input string (this is due to the fact that some bytes have to be embedded\
    into the compressed string in order to be able to restore it later on)\

    2. The content type: random sequences of chars are very unlikely to be successfully compressed, while the best\
    compression result is obtained when the string contains several recurring char sequences (like in the example).

    Behind the scenes this method makes use of the standard Python's zlib and base64 libraries.

    *Examples:*

    >>> n = 0 # <- ignore this, it's a fix for Pycharm (not fixable using ignore comments)
    >>> # "original" will be a string with 169 chars:
    >>> original = ' '.join(['word n{}'.format(n) for n in range(20)])
    >>> # "compressed" will be a string of 88 chars
    >>> compressed = compress(original)

    :param input_string: String to compress (must be not empty or a ValueError will be raised).
    :type input_string: str
    :param encoding: String encoding (default to "utf-8").
    :type encoding: str
    :param compression_level: A value between 0 (no compression) and 9 (best compression), default to 9.
    :type compression_level: int
    :return: Compressed string.
    """
    return __StringCompressor.compress(input_string, encoding, compression_level)


def x_compress__mutmut_3(input_string: str, encoding: str = 'utf-8', compression_level: int = 10) -> str:
    """
    Compress the given string by returning a shorter one that can be safely used in any context (like URL) and
    restored back to its original state using `decompress()`.

    **Bear in mind:**
    Besides the provided `compression_level`, the compression result (how much the string is actually compressed
    by resulting into a shorter string) depends on 2 factors:

    1. The amount of data (string size): short strings might not provide a significant compression result\
    or even be longer than the given input string (this is due to the fact that some bytes have to be embedded\
    into the compressed string in order to be able to restore it later on)\

    2. The content type: random sequences of chars are very unlikely to be successfully compressed, while the best\
    compression result is obtained when the string contains several recurring char sequences (like in the example).

    Behind the scenes this method makes use of the standard Python's zlib and base64 libraries.

    *Examples:*

    >>> n = 0 # <- ignore this, it's a fix for Pycharm (not fixable using ignore comments)
    >>> # "original" will be a string with 169 chars:
    >>> original = ' '.join(['word n{}'.format(n) for n in range(20)])
    >>> # "compressed" will be a string of 88 chars
    >>> compressed = compress(original)

    :param input_string: String to compress (must be not empty or a ValueError will be raised).
    :type input_string: str
    :param encoding: String encoding (default to "utf-8").
    :type encoding: str
    :param compression_level: A value between 0 (no compression) and 9 (best compression), default to 9.
    :type compression_level: int
    :return: Compressed string.
    """
    return __StringCompressor.compress(input_string, encoding, compression_level)


def x_compress__mutmut_4(input_string: str, encoding: str = 'utf-8', compression_level: int = 9) -> str:
    """
    Compress the given string by returning a shorter one that can be safely used in any context (like URL) and
    restored back to its original state using `decompress()`.

    **Bear in mind:**
    Besides the provided `compression_level`, the compression result (how much the string is actually compressed
    by resulting into a shorter string) depends on 2 factors:

    1. The amount of data (string size): short strings might not provide a significant compression result\
    or even be longer than the given input string (this is due to the fact that some bytes have to be embedded\
    into the compressed string in order to be able to restore it later on)\

    2. The content type: random sequences of chars are very unlikely to be successfully compressed, while the best\
    compression result is obtained when the string contains several recurring char sequences (like in the example).

    Behind the scenes this method makes use of the standard Python's zlib and base64 libraries.

    *Examples:*

    >>> n = 0 # <- ignore this, it's a fix for Pycharm (not fixable using ignore comments)
    >>> # "original" will be a string with 169 chars:
    >>> original = ' '.join(['word n{}'.format(n) for n in range(20)])
    >>> # "compressed" will be a string of 88 chars
    >>> compressed = compress(original)

    :param input_string: String to compress (must be not empty or a ValueError will be raised).
    :type input_string: str
    :param encoding: String encoding (default to "utf-8").
    :type encoding: str
    :param compression_level: A value between 0 (no compression) and 9 (best compression), default to 9.
    :type compression_level: int
    :return: Compressed string.
    """
    return __StringCompressor.compress(None, encoding, compression_level)


def x_compress__mutmut_5(input_string: str, encoding: str = 'utf-8', compression_level: int = 9) -> str:
    """
    Compress the given string by returning a shorter one that can be safely used in any context (like URL) and
    restored back to its original state using `decompress()`.

    **Bear in mind:**
    Besides the provided `compression_level`, the compression result (how much the string is actually compressed
    by resulting into a shorter string) depends on 2 factors:

    1. The amount of data (string size): short strings might not provide a significant compression result\
    or even be longer than the given input string (this is due to the fact that some bytes have to be embedded\
    into the compressed string in order to be able to restore it later on)\

    2. The content type: random sequences of chars are very unlikely to be successfully compressed, while the best\
    compression result is obtained when the string contains several recurring char sequences (like in the example).

    Behind the scenes this method makes use of the standard Python's zlib and base64 libraries.

    *Examples:*

    >>> n = 0 # <- ignore this, it's a fix for Pycharm (not fixable using ignore comments)
    >>> # "original" will be a string with 169 chars:
    >>> original = ' '.join(['word n{}'.format(n) for n in range(20)])
    >>> # "compressed" will be a string of 88 chars
    >>> compressed = compress(original)

    :param input_string: String to compress (must be not empty or a ValueError will be raised).
    :type input_string: str
    :param encoding: String encoding (default to "utf-8").
    :type encoding: str
    :param compression_level: A value between 0 (no compression) and 9 (best compression), default to 9.
    :type compression_level: int
    :return: Compressed string.
    """
    return __StringCompressor.compress(input_string, None, compression_level)


def x_compress__mutmut_6(input_string: str, encoding: str = 'utf-8', compression_level: int = 9) -> str:
    """
    Compress the given string by returning a shorter one that can be safely used in any context (like URL) and
    restored back to its original state using `decompress()`.

    **Bear in mind:**
    Besides the provided `compression_level`, the compression result (how much the string is actually compressed
    by resulting into a shorter string) depends on 2 factors:

    1. The amount of data (string size): short strings might not provide a significant compression result\
    or even be longer than the given input string (this is due to the fact that some bytes have to be embedded\
    into the compressed string in order to be able to restore it later on)\

    2. The content type: random sequences of chars are very unlikely to be successfully compressed, while the best\
    compression result is obtained when the string contains several recurring char sequences (like in the example).

    Behind the scenes this method makes use of the standard Python's zlib and base64 libraries.

    *Examples:*

    >>> n = 0 # <- ignore this, it's a fix for Pycharm (not fixable using ignore comments)
    >>> # "original" will be a string with 169 chars:
    >>> original = ' '.join(['word n{}'.format(n) for n in range(20)])
    >>> # "compressed" will be a string of 88 chars
    >>> compressed = compress(original)

    :param input_string: String to compress (must be not empty or a ValueError will be raised).
    :type input_string: str
    :param encoding: String encoding (default to "utf-8").
    :type encoding: str
    :param compression_level: A value between 0 (no compression) and 9 (best compression), default to 9.
    :type compression_level: int
    :return: Compressed string.
    """
    return __StringCompressor.compress(input_string, encoding, None)


def x_compress__mutmut_7(input_string: str, encoding: str = 'utf-8', compression_level: int = 9) -> str:
    """
    Compress the given string by returning a shorter one that can be safely used in any context (like URL) and
    restored back to its original state using `decompress()`.

    **Bear in mind:**
    Besides the provided `compression_level`, the compression result (how much the string is actually compressed
    by resulting into a shorter string) depends on 2 factors:

    1. The amount of data (string size): short strings might not provide a significant compression result\
    or even be longer than the given input string (this is due to the fact that some bytes have to be embedded\
    into the compressed string in order to be able to restore it later on)\

    2. The content type: random sequences of chars are very unlikely to be successfully compressed, while the best\
    compression result is obtained when the string contains several recurring char sequences (like in the example).

    Behind the scenes this method makes use of the standard Python's zlib and base64 libraries.

    *Examples:*

    >>> n = 0 # <- ignore this, it's a fix for Pycharm (not fixable using ignore comments)
    >>> # "original" will be a string with 169 chars:
    >>> original = ' '.join(['word n{}'.format(n) for n in range(20)])
    >>> # "compressed" will be a string of 88 chars
    >>> compressed = compress(original)

    :param input_string: String to compress (must be not empty or a ValueError will be raised).
    :type input_string: str
    :param encoding: String encoding (default to "utf-8").
    :type encoding: str
    :param compression_level: A value between 0 (no compression) and 9 (best compression), default to 9.
    :type compression_level: int
    :return: Compressed string.
    """
    return __StringCompressor.compress(encoding, compression_level)


def x_compress__mutmut_8(input_string: str, encoding: str = 'utf-8', compression_level: int = 9) -> str:
    """
    Compress the given string by returning a shorter one that can be safely used in any context (like URL) and
    restored back to its original state using `decompress()`.

    **Bear in mind:**
    Besides the provided `compression_level`, the compression result (how much the string is actually compressed
    by resulting into a shorter string) depends on 2 factors:

    1. The amount of data (string size): short strings might not provide a significant compression result\
    or even be longer than the given input string (this is due to the fact that some bytes have to be embedded\
    into the compressed string in order to be able to restore it later on)\

    2. The content type: random sequences of chars are very unlikely to be successfully compressed, while the best\
    compression result is obtained when the string contains several recurring char sequences (like in the example).

    Behind the scenes this method makes use of the standard Python's zlib and base64 libraries.

    *Examples:*

    >>> n = 0 # <- ignore this, it's a fix for Pycharm (not fixable using ignore comments)
    >>> # "original" will be a string with 169 chars:
    >>> original = ' '.join(['word n{}'.format(n) for n in range(20)])
    >>> # "compressed" will be a string of 88 chars
    >>> compressed = compress(original)

    :param input_string: String to compress (must be not empty or a ValueError will be raised).
    :type input_string: str
    :param encoding: String encoding (default to "utf-8").
    :type encoding: str
    :param compression_level: A value between 0 (no compression) and 9 (best compression), default to 9.
    :type compression_level: int
    :return: Compressed string.
    """
    return __StringCompressor.compress(input_string, compression_level)


def x_compress__mutmut_9(input_string: str, encoding: str = 'utf-8', compression_level: int = 9) -> str:
    """
    Compress the given string by returning a shorter one that can be safely used in any context (like URL) and
    restored back to its original state using `decompress()`.

    **Bear in mind:**
    Besides the provided `compression_level`, the compression result (how much the string is actually compressed
    by resulting into a shorter string) depends on 2 factors:

    1. The amount of data (string size): short strings might not provide a significant compression result\
    or even be longer than the given input string (this is due to the fact that some bytes have to be embedded\
    into the compressed string in order to be able to restore it later on)\

    2. The content type: random sequences of chars are very unlikely to be successfully compressed, while the best\
    compression result is obtained when the string contains several recurring char sequences (like in the example).

    Behind the scenes this method makes use of the standard Python's zlib and base64 libraries.

    *Examples:*

    >>> n = 0 # <- ignore this, it's a fix for Pycharm (not fixable using ignore comments)
    >>> # "original" will be a string with 169 chars:
    >>> original = ' '.join(['word n{}'.format(n) for n in range(20)])
    >>> # "compressed" will be a string of 88 chars
    >>> compressed = compress(original)

    :param input_string: String to compress (must be not empty or a ValueError will be raised).
    :type input_string: str
    :param encoding: String encoding (default to "utf-8").
    :type encoding: str
    :param compression_level: A value between 0 (no compression) and 9 (best compression), default to 9.
    :type compression_level: int
    :return: Compressed string.
    """
    return __StringCompressor.compress(input_string, encoding, )

x_compress__mutmut_mutants : ClassVar[MutantDict] = { # type: ignore
'x_compress__mutmut_1': x_compress__mutmut_1, 
    'x_compress__mutmut_2': x_compress__mutmut_2, 
    'x_compress__mutmut_3': x_compress__mutmut_3, 
    'x_compress__mutmut_4': x_compress__mutmut_4, 
    'x_compress__mutmut_5': x_compress__mutmut_5, 
    'x_compress__mutmut_6': x_compress__mutmut_6, 
    'x_compress__mutmut_7': x_compress__mutmut_7, 
    'x_compress__mutmut_8': x_compress__mutmut_8, 
    'x_compress__mutmut_9': x_compress__mutmut_9
}
x_compress__mutmut_orig.__name__ = 'x_compress'


def decompress(input_string: str, encoding: str = 'utf-8') -> str:
    args = [input_string, encoding]# type: ignore
    kwargs = {}# type: ignore
    return _mutmut_trampoline(x_decompress__mutmut_orig, x_decompress__mutmut_mutants, args, kwargs, None)


def x_decompress__mutmut_orig(input_string: str, encoding: str = 'utf-8') -> str:
    """
    Restore a previously compressed string (obtained using `compress()`) back to its original state.

    :param input_string: String to restore.
    :type input_string: str
    :param encoding: Original string encoding.
    :type encoding: str
    :return: Decompressed string.
    """
    return __StringCompressor.decompress(input_string, encoding)


def x_decompress__mutmut_1(input_string: str, encoding: str = 'XXutf-8XX') -> str:
    """
    Restore a previously compressed string (obtained using `compress()`) back to its original state.

    :param input_string: String to restore.
    :type input_string: str
    :param encoding: Original string encoding.
    :type encoding: str
    :return: Decompressed string.
    """
    return __StringCompressor.decompress(input_string, encoding)


def x_decompress__mutmut_2(input_string: str, encoding: str = 'UTF-8') -> str:
    """
    Restore a previously compressed string (obtained using `compress()`) back to its original state.

    :param input_string: String to restore.
    :type input_string: str
    :param encoding: Original string encoding.
    :type encoding: str
    :return: Decompressed string.
    """
    return __StringCompressor.decompress(input_string, encoding)


def x_decompress__mutmut_3(input_string: str, encoding: str = 'utf-8') -> str:
    """
    Restore a previously compressed string (obtained using `compress()`) back to its original state.

    :param input_string: String to restore.
    :type input_string: str
    :param encoding: Original string encoding.
    :type encoding: str
    :return: Decompressed string.
    """
    return __StringCompressor.decompress(None, encoding)


def x_decompress__mutmut_4(input_string: str, encoding: str = 'utf-8') -> str:
    """
    Restore a previously compressed string (obtained using `compress()`) back to its original state.

    :param input_string: String to restore.
    :type input_string: str
    :param encoding: Original string encoding.
    :type encoding: str
    :return: Decompressed string.
    """
    return __StringCompressor.decompress(input_string, None)


def x_decompress__mutmut_5(input_string: str, encoding: str = 'utf-8') -> str:
    """
    Restore a previously compressed string (obtained using `compress()`) back to its original state.

    :param input_string: String to restore.
    :type input_string: str
    :param encoding: Original string encoding.
    :type encoding: str
    :return: Decompressed string.
    """
    return __StringCompressor.decompress(encoding)


def x_decompress__mutmut_6(input_string: str, encoding: str = 'utf-8') -> str:
    """
    Restore a previously compressed string (obtained using `compress()`) back to its original state.

    :param input_string: String to restore.
    :type input_string: str
    :param encoding: Original string encoding.
    :type encoding: str
    :return: Decompressed string.
    """
    return __StringCompressor.decompress(input_string, )

x_decompress__mutmut_mutants : ClassVar[MutantDict] = { # type: ignore
'x_decompress__mutmut_1': x_decompress__mutmut_1, 
    'x_decompress__mutmut_2': x_decompress__mutmut_2, 
    'x_decompress__mutmut_3': x_decompress__mutmut_3, 
    'x_decompress__mutmut_4': x_decompress__mutmut_4, 
    'x_decompress__mutmut_5': x_decompress__mutmut_5, 
    'x_decompress__mutmut_6': x_decompress__mutmut_6
}
x_decompress__mutmut_orig.__name__ = 'x_decompress'


def roman_encode(input_number: Union[str, int]) -> str:
    args = [input_number]# type: ignore
    kwargs = {}# type: ignore
    return _mutmut_trampoline(x_roman_encode__mutmut_orig, x_roman_encode__mutmut_mutants, args, kwargs, None)


def x_roman_encode__mutmut_orig(input_number: Union[str, int]) -> str:
    """
    Convert the given number/string into a roman number.

    The passed input must represents a positive integer in the range 1-3999 (inclusive).

    Why this limit? You may be wondering:

    1. zero is forbidden since there is no related representation in roman numbers
    2. the upper bound 3999 is due to the limitation in the ascii charset\
    (the higher quantity sign displayable in ascii is "M" which is equal to 1000, therefore based on\
    roman numbers rules we can use 3 times M to reach 3000 but we can't go any further in thousands without\
    special "boxed chars").

    *Examples:*

    >>> roman_encode(37) # returns 'XXXVIII'
    >>> roman_encode('2020') # returns 'MMXX'

    :param input_number: An integer or a string to be converted.
    :type input_number: Union[str, int]
    :return: Roman number string.
    """
    return __RomanNumbers.encode(input_number)


def x_roman_encode__mutmut_1(input_number: Union[str, int]) -> str:
    """
    Convert the given number/string into a roman number.

    The passed input must represents a positive integer in the range 1-3999 (inclusive).

    Why this limit? You may be wondering:

    1. zero is forbidden since there is no related representation in roman numbers
    2. the upper bound 3999 is due to the limitation in the ascii charset\
    (the higher quantity sign displayable in ascii is "M" which is equal to 1000, therefore based on\
    roman numbers rules we can use 3 times M to reach 3000 but we can't go any further in thousands without\
    special "boxed chars").

    *Examples:*

    >>> roman_encode(37) # returns 'XXXVIII'
    >>> roman_encode('2020') # returns 'MMXX'

    :param input_number: An integer or a string to be converted.
    :type input_number: Union[str, int]
    :return: Roman number string.
    """
    return __RomanNumbers.encode(None)

x_roman_encode__mutmut_mutants : ClassVar[MutantDict] = { # type: ignore
'x_roman_encode__mutmut_1': x_roman_encode__mutmut_1
}
x_roman_encode__mutmut_orig.__name__ = 'x_roman_encode'


def roman_decode(input_string: str) -> int:
    args = [input_string]# type: ignore
    kwargs = {}# type: ignore
    return _mutmut_trampoline(x_roman_decode__mutmut_orig, x_roman_decode__mutmut_mutants, args, kwargs, None)


def x_roman_decode__mutmut_orig(input_string: str) -> int:
    """
    Decode a roman number string into an integer if the provided string is valid.

    *Example:*

    >>> roman_decode('VII') # returns 7

    :param input_string: (Assumed) Roman number
    :type input_string: str
    :return: Integer value
    """
    return __RomanNumbers.decode(input_string)


def x_roman_decode__mutmut_1(input_string: str) -> int:
    """
    Decode a roman number string into an integer if the provided string is valid.

    *Example:*

    >>> roman_decode('VII') # returns 7

    :param input_string: (Assumed) Roman number
    :type input_string: str
    :return: Integer value
    """
    return __RomanNumbers.decode(None)

x_roman_decode__mutmut_mutants : ClassVar[MutantDict] = { # type: ignore
'x_roman_decode__mutmut_1': x_roman_decode__mutmut_1
}
x_roman_decode__mutmut_orig.__name__ = 'x_roman_decode'
