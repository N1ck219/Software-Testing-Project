from manipulation import *
import pytest
import random
import base64
import zlib
import unicodedata

class TestManipulation:

    # --- reverse ---
    def test_reverse_empty_string(self):
        assert reverse('') == ''

    def test_reverse_simple_string(self):
        assert reverse('hello') == 'olleh'

    def test_reverse_palindrome(self):
        assert reverse('madam') == 'madam'

    def test_reverse_string_with_spaces(self):
        assert reverse('hello world') == 'dlrow olleh'

    def test_reverse_unicode_string(self):
        assert reverse('안녕하세요') == '요세하녕안'

    def test_reverse_special_characters(self):
        assert reverse('!@#$%^&*()') == ')(*&^%$#@!'

    def test_reverse_invalid_input_type_raises_error(self):
        with pytest.raises(InvalidInputError):
            reverse(123)
        with pytest.raises(InvalidInputError):
            reverse(None)
        with pytest.raises(InvalidInputError):
            reverse(['a', 'b'])
        with pytest.raises(InvalidInputError):
            reverse(True)

    # --- camel_case_to_snake ---
    def test_camel_case_to_snake_basic_conversion(self):
        assert camel_case_to_snake('ThisIsACamelString') == 'this_is_a_camel_string'

    def test_camel_case_to_snake_single_word_camel(self):
        assert camel_case_to_snake('Word') == 'word'

    def test_camel_case_to_snake_single_word_lowercase_returns_original(self):
        assert camel_case_to_snake('word') == 'word'

    def test_camel_case_to_snake_already_snake_case_returns_original(self):
        assert camel_case_to_snake('already_snake_case') == 'already_snake_case'

    def test_camel_case_to_snake_with_numbers(self):
        assert camel_case_to_snake('CamelCaseWith123Numbers') == 'camel_case_with123_numbers'
        assert camel_case_to_snake('HTTPResponseCode') == 'http_response_code'
        assert camel_case_to_snake('URLPath') == 'url_path'

    def test_camel_case_to_snake_with_custom_separator(self):
        assert camel_case_to_snake('ThisIsACamelString', separator='-') == 'this-is-a-camel-string'
        assert camel_case_to_snake('AnotherExample', separator='.') == 'another.example'

    def test_camel_case_to_snake_empty_string(self):
        assert camel_case_to_snake('') == ''

    def test_camel_case_to_snake_invalid_input_type_raises_error(self):
        with pytest.raises(InvalidInputError):
            camel_case_to_snake(123)
        with pytest.raises(InvalidInputError):
            camel_case_to_snake(None)

    # --- snake_case_to_camel ---
    def test_snake_case_to_camel_basic_conversion_upper_first(self):
        assert snake_case_to_camel('the_snake_is_green') == 'TheSnakeIsGreen'

    def test_snake_case_to_camel_basic_conversion_lower_first(self):
        assert snake_case_to_camel('the_snake_is_green', upper_case_first=False) == 'theSnakeIsGreen'

    def test_snake_case_to_camel_single_word_snake(self):
        assert snake_case_to_camel('word') == 'Word'
        assert snake_case_to_camel('word', upper_case_first=False) == 'word'

    def test_snake_case_to_camel_already_camel_case_returns_original(self):
        assert snake_case_to_camel('AlreadyCamelCase') == 'AlreadyCamelCase'

    def test_snake_case_to_camel_empty_string(self):
        assert snake_case_to_camel('') == ''

    def test_snake_case_to_camel_string_with_multiple_separators(self):
        assert snake_case_to_camel('foo__bar') == 'FooBar'
        assert snake_case_to_camel('__leading_trailing__') == 'LeadingTrailing'

    def test_snake_case_to_camel_with_numbers(self):
        assert snake_case_to_camel('word_with_123_numbers') == 'WordWith123Numbers'

    def test_snake_case_to_camel_custom_separator(self):
        assert snake_case_to_camel('one-two-three', separator='-') == 'OneTwoThree'
        assert snake_case_to_camel('foo.bar', separator='.') == 'FooBar'

    def test_snake_case_to_camel_invalid_input_type_raises_error(self):
        with pytest.raises(InvalidInputError):
            snake_case_to_camel(123)
        with pytest.raises(InvalidInputError):
            snake_case_to_camel(None)

    # --- shuffle ---
    def test_shuffle_empty_string(self):
        random.seed(42)
        assert shuffle('') == ''

    def test_shuffle_single_character_string(self):
        random.seed(42)
        assert shuffle('a') == 'a'

    def test_shuffle_string_preserves_characters(self):
        original = 'hello world'
        random.seed(42)
        shuffled = shuffle(original)
        assert len(shuffled) == len(original)
        assert sorted(shuffled) == sorted(original)

    def test_shuffle_string_is_different_from_original_for_long_string(self):
        original = "The quick brown fox jumps over the lazy dog."
        random.seed(42)
        shuffled = shuffle(original)
        assert shuffled != original

    def test_shuffle_string_with_duplicates(self):
        original = 'aabbc'
        random.seed(42)
        shuffled = shuffle(original)
        assert len(shuffled) == len(original)
        assert sorted(shuffled) == sorted(original)
        assert shuffled != original

    def test_shuffle_unicode_string(self):
        original = '你好世界'
        random.seed(42)
        shuffled = shuffle(original)
        assert len(shuffled) == len(original)
        assert sorted(shuffled) == sorted(original)
        assert shuffled != original

    def test_shuffle_invalid_input_type_raises_error(self):
        with pytest.raises(InvalidInputError):
            shuffle(123)
        with pytest.raises(InvalidInputError):
            shuffle(None)
        with pytest.raises(InvalidInputError):
            shuffle(['a', 'b'])

    # --- strip_html ---
    def test_strip_html_no_html(self):
        assert strip_html('hello world') == 'hello world'

    def test_strip_html_simple_tag_remove_content(self):
        assert strip_html('test: <a href="foo/bar">click here</a>') == 'test: '

    def test_strip_html_simple_tag_keep_content(self):
        assert strip_html('test: <a href="foo/bar">click here</a>', keep_tag_content=True) == 'test: click here'

    def test_strip_html_multiple_tags_remove_content(self):
        html_string = '<h1>Title</h1><p>Some <b>bold</b> text.</p>'
        assert strip_html(html_string) == ''

    def test_strip_html_multiple_tags_keep_content(self):
        html_string = '<h1>Title</h1><p>Some <b>bold</b> text.</p>'
        assert strip_html(html_string, keep_tag_content=True) == 'TitleSome bold text.'

    def test_strip_html_nested_tags_remove_content(self):
        html_string = '<div>outer<span>inner</span></div>'
        assert strip_html(html_string) == ''

    def test_strip_html_nested_tags_keep_content(self):
        html_string = '<div>outer<span>inner</span></div>'
        assert strip_html(html_string, keep_tag_content=True) == 'outerinner'

    def test_strip_html_malformed_tags_keep_content_if_content_is_out_of_tag_reach(self):
        assert strip_html('hello <p>world', keep_tag_content=True) == 'hello world'

    def test_strip_html_empty_string(self):
        assert strip_html('') == ''

    def test_strip_html_string_with_only_tags(self):
        assert strip_html('<br><hr>') == ''
        assert strip_html('<br><hr>', keep_tag_content=True) == ''

    def test_strip_html_script_tags(self):
        assert strip_html('<script>alert("hello")</script>') == ''
        assert strip_html('<script>alert("hello")</script>', keep_tag_content=True) == 'alert("hello")'

    def test_strip_html_style_tags(self):
        assert strip_html('<style>.foo { color: red; }</style>') == ''
        assert strip_html('<style>.foo { color: red; }</style>', keep_tag_content=True) == '.foo { color: red; }'

    def test_strip_html_invalid_input_type_raises_error(self):
        with pytest.raises(InvalidInputError):
            strip_html(123)
        with pytest.raises(InvalidInputError):
            strip_html(None)

    # --- prettify ---
    def test_prettify_example_from_docstring(self):
        input_string = ' unprettified string ,, like this one,will be"prettified" .it\' s awesome! '
        expected_output = 'Unprettified string, like this one, will be "prettified". It\'s awesome!'
        assert prettify(input_string) == expected_output

    def test_prettify_empty_string(self):
        assert prettify('') == ''

    def test_prettify_multiple_spaces(self):
        assert prettify('  hello   world  ') == 'Hello world'

    def test_prettify_punctuation_spacing(self):
        assert prettify('Hello,world!How are you?') == 'Hello, world! How are you?'
        assert prettify('Hello , world ! How are you ?') == 'Hello, world! How are you?'
        assert prettify('Hello  .  world') == 'Hello. World'

    def test_prettify_quotes_and_brackets_spacing(self):
        assert prettify('foo"bar"baz') == 'foo "bar" baz'
        assert prettify('foo(bar)baz') == 'foo (bar) baz'
        assert prettify('foo" bar "baz') == 'foo "bar" baz'
        assert prettify('foo( bar )baz') == 'foo (bar) baz'
        assert prettify('foo "bar" baz') == 'foo "bar" baz'

    def test_prettify_arithmetic_operators(self):
        assert prettify('1+2-3/4*5=6') == '1 + 2 - 3 / 4 * 5 = 6'
        assert prettify('1 +  2-3 / 4 *5 =  6') == '1 + 2 - 3 / 4 * 5 = 6'

    def test_prettify_percentage_sign(self):
        assert prettify('100 %') == '100%'
        assert prettify('discount 10 % off') == 'discount 10% off'
        assert prettify('percentage % value') == 'percentage % value'

    def test_prettify_saxon_genitive(self):
        assert prettify('Dave\' s dog') == 'Dave\'s dog'
        assert prettify('Alice\'s car') == 'Alice\'s car'

    def test_prettify_first_letter_and_after_punctuation_uppercase(self):
        assert prettify('hello.world!how are you?') == 'Hello. World! How are you?'
        assert prettify('test...string') == 'Test. String'
        assert prettify('foo?!bar') == 'Foo?! Bar'
        assert prettify('foo!!bar') == 'Foo! Bar'

    def test_prettify_urls_and_emails_preserved(self):
        url = 'https://example.com/path?param=value'
        email = 'test@example.com'
        input_string = f'  Check out this {url} and email {email} for details.  '
        expected_output = f'Check out this {url} and email {email} for details.'
        assert prettify(input_string) == expected_output

        input_string_with_punctuation_around_url = f'Go to.{url}.Or email {email}!'
        expected_output_with_punctuation_around_url = f'Go to. {url}. Or email {email}!'
        assert prettify(input_string_with_punctuation_around_url) == expected_output_with_punctuation_around_url

    def test_prettify_empty_lines(self):
        assert prettify('Line1\n\n\nLine2') == 'Line1\nLine2'
        assert prettify('\n\nLine1\n\nLine2\n\n') == 'Line1\nLine2'
        assert prettify('  \n  \nLine1\n  \n  Line2\n  \n') == 'Line1\nLine2'

    def test_prettify_invalid_input_type_raises_error(self):
        with pytest.raises(InvalidInputError):
            prettify(123)
        with pytest.raises(InvalidInputError):
            prettify(None)

    # --- asciify ---
    def test_asciify_basic_conversion(self):
        assert asciify('èéùúòóäåëýñÅÀÁÇÌÍÑÓË') == 'eeuuooaaeynAAACIINOE'

    def test_asciify_empty_string(self):
        assert asciify('') == ''

    def test_asciify_already_ascii_string(self):
        assert asciify('hello world 123 !@#') == 'hello world 123 !@#'

    def test_asciify_mixed_string(self):
        assert asciify('Café au lait') == 'Cafe au lait'

    def test_asciify_characters_that_cannot_be_translated(self):
        assert asciify('你好世界') == ''
        assert asciify('This is a test with some unicode: こんにちは') == 'This is a test with some unicode: '
        assert asciify('Euro sign: €') == 'Euro sign: '
        assert asciify('Pound sign: £') == 'Pound sign: '

    def test_asciify_special_unicode_chars(self):
        assert asciify('straße') == 'strasse'
        assert asciify('Héllö Wörld') == 'Hello World'
        assert asciify('déjà vu') == 'deja vu'

    def test_asciify_invalid_input_type_raises_error(self):
        with pytest.raises(InvalidInputError):
            asciify(123)
        with pytest.raises(InvalidInputError):
            asciify(None)

    # --- slugify ---
    def test_slugify_basic_conversion(self):
        assert slugify('Top 10 Reasons To Love Dogs!!!') == 'top-10-reasons-to-love-dogs'

    def test_slugify_unicode_conversion(self):
        assert slugify('Mönstér Mägnët') == 'monster-magnet'
        assert slugify('你好世界') == ''
        assert slugify('Café au lait') == 'cafe-au-lait'

    def test_slugify_empty_string(self):
        assert slugify('') == ''

    def test_slugify_string_with_only_special_chars(self):
        assert slugify('!@#$%^&*()') == ''
        assert slugify('---') == ''

    def test_slugify_multiple_spaces_and_separators(self):
        assert slugify('  hello   world  ') == 'hello-world'
        assert slugify('hello--world') == 'hello-world'
        assert slugify('hello   ---   world') == 'hello-world'

    def test_slugify_custom_separator(self):
        assert slugify('hello world', separator='_') == 'hello_world'
        assert slugify('my string with spaces', separator='+') == 'my+string+with+spaces'
        assert slugify('Another test', separator='.') == 'another.test'

    def test_slugify_with_numbers_and_punctuation(self):
        assert slugify('String with 123 numbers & symbols!') == 'string-with-123-numbers-symbols'
        assert slugify('Version 1.0.0 Alpha') == 'version-100-alpha'

    def test_slugify_invalid_input_type_raises_error(self):
        with pytest.raises(InvalidInputError):
            slugify(123)
        with pytest.raises(InvalidInputError):
            slugify(None)

    # --- booleanize ---
    def test_booleanize_true_cases(self):
        assert booleanize('true') is True
        assert booleanize('TRUE') is True
        assert booleanize('True') is True
        assert booleanize('1') is True
        assert booleanize('yes') is True
        assert booleanize('YES') is True
        assert booleanize('y') is True
        assert booleanize('Y') is True

    def test_booleanize_false_cases(self):
        assert booleanize('false') is False
        assert booleanize('FALSE') is False
        assert booleanize('0') is False
        assert booleanize('no') is False
        assert booleanize('N') is False
        assert booleanize('') is False
        assert booleanize('anything else') is False
        assert booleanize('not a boolean') is False
        assert booleanize('2') is False
        assert booleanize('-1') is False

    def test_booleanize_string_with_spaces_is_false(self):
        assert booleanize(' true ') is False
        assert booleanize(' 1') is False

    def test_booleanize_invalid_input_type_raises_error(self):
        with pytest.raises(InvalidInputError):
            booleanize(123)
        with pytest.raises(InvalidInputError):
            booleanize(None)
        with pytest.raises(InvalidInputError):
            booleanize(True)

    # --- strip_margin ---
    def test_strip_margin_example_from_docstring(self):
        input_string = '''
                line 1
                line 2
                line 3
'''
        expected_output = '''
line 1
line 2
line 3
'''
        assert strip_margin(input_string) == expected_output

    def test_strip_margin_no_indentation(self):
        input_string = 'line 1\nline 2\nline 3'
        assert strip_margin(input_string) == input_string

    def test_strip_margin_mixed_indentation(self):
        input_string = '''
            line 1
                line 2
            line 3
'''
        expected_output = '''
line 1
line 2
line 3
'''
        assert strip_margin(input_string) == expected_output

    def test_strip_margin_empty_string(self):
        assert strip_margin('') == ''

    def test_strip_margin_string_with_only_spaces_or_tabs(self):
        assert strip_margin('   \t \n\t   ') == '\n'
        assert strip_margin('   ') == ''

    def test_strip_margin_single_line_string(self):
        assert strip_margin('    hello world') == 'hello world'

    def test_strip_margin_invalid_input_type_raises_error(self):
        with pytest.raises(InvalidInputError):
            strip_margin(123)
        with pytest.raises(InvalidInputError):
            strip_margin(None)

    # --- compress / decompress ---
    def test_compress_decompress_round_trip_basic(self):
        original = 'hello world'
        compressed = compress(original)
        decompressed = decompress(compressed)
        assert decompressed == original
        assert compressed != original

    def test_compress_decompress_round_trip_long_string(self):
        original = ' '.join(['word n{}'.format(n) for n in range(20)])
        compressed = compress(original)
        decompressed = decompress(compressed)
        assert decompressed == original
        assert len(compressed) < len(original)

    def test_compress_decompress_round_trip_unicode_string(self):
        original = '你好世界こんにちは'
        compressed = compress(original)
        decompressed = decompress(compressed)
        assert decompressed == original

    def test_compress_decompress_round_trip_with_different_encoding(self):
        original = 'Café au lait'
        compressed = compress(original, encoding='latin-1')
        decompressed = decompress(compressed, encoding='latin-1')
        assert decompressed == original

    def test_compress_decompress_round_trip_with_compression_level_0(self):
        original = 'a' * 100
        compressed = compress(original, compression_level=0)
        decompressed = decompress(compressed)
        assert decompressed == original
        assert len(compressed) > len(original) # Level 0 means no compression, but zlib adds headers.

    def test_compress_decompress_round_trip_with_compression_level_9(self):
        original = 'test string repeated multiple times for compression test ' * 50
        compressed = compress(original, compression_level=9)
        decompressed = decompress(compressed)
        assert decompressed == original
        assert len(compressed) < len(original)

    def test_compress_empty_string_raises_value_error(self):
        with pytest.raises(ValueError, match='Input string cannot be empty'):
            compress('')

    def test_compress_invalid_input_string_type_raises_invalid_input_error(self):
        with pytest.raises(InvalidInputError):
            compress(123)
        with pytest.raises(InvalidInputError):
            compress(None)

    def test_compress_invalid_encoding_type_raises_value_error(self):
        with pytest.raises(ValueError, match='Invalid encoding'):
            compress('hello', encoding=123)

    def test_compress_invalid_compression_level_type_raises_value_error(self):
        with pytest.raises(ValueError, match='Invalid compression_level'):
            compress('hello', compression_level='not_an_int')
        with pytest.raises(ValueError, match='Invalid compression_level'):
            compress('hello', compression_level=-1)
        with pytest.raises(ValueError, match='Invalid compression_level'):
            compress('hello', compression_level=10)
        with pytest.raises(ValueError, match='Invalid compression_level'):
            compress('hello', compression_level=0.5)

    def test_decompress_invalid_input_string_type_raises_invalid_input_error(self):
        with pytest.raises(InvalidInputError):
            decompress(123)
        with pytest.raises(InvalidInputError):
            decompress(None)

    def test_decompress_empty_string_raises_value_error(self):
        with pytest.raises(ValueError, match='Input string cannot be empty'):
            decompress('')

    def test_decompress_invalid_encoding_type_raises_value_error(self):
        compressed = compress('hello')
        with pytest.raises(ValueError, match='Invalid encoding'):
            decompress(compressed, encoding=123)

    def test_decompress_malformed_compressed_string_raises_error(self):
        with pytest.raises(Exception): # base64.urlsafe_b64decode can raise binascii.Error
            decompress('notavalidcompressedstring')
        with pytest.raises(zlib.error): # zlib.decompress can raise zlib.error
            decompress(base64.urlsafe_b64encode(b'some_random_bytes').decode('utf-8'))

    # --- roman_encode ---
    def test_roman_encode_basic(self):
        assert roman_encode(1) == 'I'
        assert roman_encode(5) == 'V'
        assert roman_encode(10) == 'X'
        assert roman_encode(50) == 'L'
        assert roman_encode(100) == 'C'
        assert roman_encode(500) == 'D'
        assert roman_encode(1000) == 'M'

    def test_roman_encode_combinations(self):
        assert roman_encode(2) == 'II'
        assert roman_encode(3) == 'III'
        assert roman_encode(4) == 'IV'
        assert roman_encode(6) == 'VI'
        assert roman_encode(7) == 'VII'
        assert roman_encode(8) == 'VIII'
        assert roman_encode(9) == 'IX'

    def test_roman_encode_various_numbers(self):
        assert roman_encode(37) == 'XXXVII'
        assert roman_encode(1994) == 'MCMXCIV'
        assert roman_encode(2020) == 'MMXX'
        assert roman_encode(49) == 'XLIX'
        assert roman_encode(99) == 'XCIX'
        assert roman_encode(499) == 'CDXCIX'
        assert roman_encode(999) == 'CMXCIX'

    def test_roman_encode_max_value(self):
        assert roman_encode(3999) == 'MMMCMXCIX'

    def test_roman_encode_input_as_string(self):
        assert roman_encode('1') == 'I'
        assert roman_encode('3999') == 'MMMCMXCIX'
        assert roman_encode('1994') == 'MCMXCIV'

    def test_roman_encode_value_out_of_range_low_raises_value_error(self):
        with pytest.raises(ValueError, match='Input must be >= 1 and <= 3999'):
            roman_encode(0)
        with pytest.raises(ValueError, match='Input must be >= 1 and <= 3999'):
            roman_encode(-1)

    def test_roman_encode_value_out_of_range_high_raises_value_error(self):
        with pytest.raises(ValueError, match='Input must be >= 1 and <= 3999'):
            roman_encode(4000)
        with pytest.raises(ValueError, match='Input must be >= 1 and <= 3999'):
            roman_encode(5000)

    def test_roman_encode_invalid_input_type_raises_value_error(self):
        with pytest.raises(ValueError, match='Invalid input, only strings or integers are allowed'):
            roman_encode(None)
        with pytest.raises(ValueError, match='Invalid input, only strings or integers are allowed'):
            roman_encode('invalid')
        with pytest.raises(ValueError, match='Invalid input, only strings or integers are allowed'):
            roman_encode('1.5')
        with pytest.raises(ValueError, match='Invalid input, only strings or integers are allowed'):
            roman_encode(['1'])

    # --- roman_decode ---
    def test_roman_decode_basic(self):
        assert roman_decode('I') == 1
        assert roman_decode('V') == 5
        assert roman_decode('X') == 10
        assert roman_decode('L') == 50
        assert roman_decode('C') == 100
        assert roman_decode('D') == 500
        assert roman_decode('M') == 1000

    def test_roman_decode_combinations(self):
        assert roman_decode('II') == 2
        assert roman_decode('III') == 3
        assert roman_decode('IV') == 4
        assert roman_decode('VI') == 6
        assert roman_decode('VII') == 7
        assert roman_decode('VIII') == 8
        assert roman_decode('IX') == 9

    def test_roman_decode_subtractive_notation(self):
        assert roman_decode('IV') == 4
        assert roman_decode('IX') == 9
        assert roman_decode('XL') == 40
        assert roman_decode('XC') == 90
        assert roman_decode('CD') == 400
        assert roman_decode('CM') == 900

    def test_roman_decode_complex_numbers(self):
        assert roman_decode('XXXVII') == 37
        assert roman_decode('MCMXCIV') == 1994
        assert roman_decode('MMXX') == 2020
        assert roman_decode('MMMCMXCIX') == 3999

    def test_roman_decode_uppercase_conversion(self):
        assert roman_decode('vii') == 7
        assert roman_decode('mcmxciv') == 1994
        assert roman_decode('mMcMxCiV') == 1994

    def test_roman_decode_invalid_token_raises_value_error(self):
        with pytest.raises(ValueError, match='Invalid token found: "A"'):
            roman_decode('IIA')
        with pytest.raises(ValueError, match='Invalid token found: "Z"'):
            roman_decode('MXZI')
        with pytest.raises(ValueError, match='Invalid token found: "J"'):
            roman_decode('VJ')

    def test_roman_decode_non_standard_repetition_handled_by_code_logic(self):
        # As per Rule 1: "FEDELTÀ ASSOLUTA AL CODICE", test what the code does.
        # The current implementation calculates 'IIII' as 4, 'VV' as 10, 'VX' as 5.
        assert roman_decode('IIII') == 4
        assert roman_decode('VV') == 10
        assert roman_decode('XXXX') == 40
        assert roman_decode('LL') == 100
        assert roman_decode('DD') == 1000
        assert roman_decode('VX') == 5
        assert roman_decode('IL') == 49
        assert roman_decode('IC') == 99
        assert roman_decode('XIL') == 59

    def test_roman_decode_invalid_input_string_raises_value_error(self):
        with pytest.raises(ValueError, match='Input must be a non empty string'):
            roman_decode('')
        with pytest.raises(ValueError, match='Input must be a non empty string'):
            roman_decode(None)
        with pytest.raises(ValueError, match='Input must be a non empty string'):
            roman_decode(123)
        with pytest.raises(ValueError, match='Input must be a non empty string'):
            roman_decode(['I'])