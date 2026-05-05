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
def triangle(a: int, b: int, c: int) -> str:
    args = [a, b, c]# type: ignore
    kwargs = {}# type: ignore
    return _mutmut_trampoline(x_triangle__mutmut_orig, x_triangle__mutmut_mutants, args, kwargs, None)
def x_triangle__mutmut_orig(a: int, b: int, c: int) -> str:
    if a <= 0 or b <= 0 or c <= 0:
        return "Invalid"
    if a + b <= c or a + c <= b or b + c <= a:
        return "Invalid"
    if a == b and b == c:
        return "Equilateral"
    if a == b or b == c or a == c:
        return "Isosceles"
    return "Scalene"
def x_triangle__mutmut_1(a: int, b: int, c: int) -> str:
    if a <= 0 or b <= 0 and c <= 0:
        return "Invalid"
    if a + b <= c or a + c <= b or b + c <= a:
        return "Invalid"
    if a == b and b == c:
        return "Equilateral"
    if a == b or b == c or a == c:
        return "Isosceles"
    return "Scalene"
def x_triangle__mutmut_2(a: int, b: int, c: int) -> str:
    if a <= 0 and b <= 0 or c <= 0:
        return "Invalid"
    if a + b <= c or a + c <= b or b + c <= a:
        return "Invalid"
    if a == b and b == c:
        return "Equilateral"
    if a == b or b == c or a == c:
        return "Isosceles"
    return "Scalene"
def x_triangle__mutmut_3(a: int, b: int, c: int) -> str:
    if a < 0 or b <= 0 or c <= 0:
        return "Invalid"
    if a + b <= c or a + c <= b or b + c <= a:
        return "Invalid"
    if a == b and b == c:
        return "Equilateral"
    if a == b or b == c or a == c:
        return "Isosceles"
    return "Scalene"
def x_triangle__mutmut_4(a: int, b: int, c: int) -> str:
    if a <= 1 or b <= 0 or c <= 0:
        return "Invalid"
    if a + b <= c or a + c <= b or b + c <= a:
        return "Invalid"
    if a == b and b == c:
        return "Equilateral"
    if a == b or b == c or a == c:
        return "Isosceles"
    return "Scalene"
def x_triangle__mutmut_5(a: int, b: int, c: int) -> str:
    if a <= 0 or b < 0 or c <= 0:
        return "Invalid"
    if a + b <= c or a + c <= b or b + c <= a:
        return "Invalid"
    if a == b and b == c:
        return "Equilateral"
    if a == b or b == c or a == c:
        return "Isosceles"
    return "Scalene"
def x_triangle__mutmut_6(a: int, b: int, c: int) -> str:
    if a <= 0 or b <= 1 or c <= 0:
        return "Invalid"
    if a + b <= c or a + c <= b or b + c <= a:
        return "Invalid"
    if a == b and b == c:
        return "Equilateral"
    if a == b or b == c or a == c:
        return "Isosceles"
    return "Scalene"
def x_triangle__mutmut_7(a: int, b: int, c: int) -> str:
    if a <= 0 or b <= 0 or c < 0:
        return "Invalid"
    if a + b <= c or a + c <= b or b + c <= a:
        return "Invalid"
    if a == b and b == c:
        return "Equilateral"
    if a == b or b == c or a == c:
        return "Isosceles"
    return "Scalene"
def x_triangle__mutmut_8(a: int, b: int, c: int) -> str:
    if a <= 0 or b <= 0 or c <= 1:
        return "Invalid"
    if a + b <= c or a + c <= b or b + c <= a:
        return "Invalid"
    if a == b and b == c:
        return "Equilateral"
    if a == b or b == c or a == c:
        return "Isosceles"
    return "Scalene"
def x_triangle__mutmut_9(a: int, b: int, c: int) -> str:
    if a <= 0 or b <= 0 or c <= 0:
        return "XXInvalidXX"
    if a + b <= c or a + c <= b or b + c <= a:
        return "Invalid"
    if a == b and b == c:
        return "Equilateral"
    if a == b or b == c or a == c:
        return "Isosceles"
    return "Scalene"
def x_triangle__mutmut_10(a: int, b: int, c: int) -> str:
    if a <= 0 or b <= 0 or c <= 0:
        return "invalid"
    if a + b <= c or a + c <= b or b + c <= a:
        return "Invalid"
    if a == b and b == c:
        return "Equilateral"
    if a == b or b == c or a == c:
        return "Isosceles"
    return "Scalene"
def x_triangle__mutmut_11(a: int, b: int, c: int) -> str:
    if a <= 0 or b <= 0 or c <= 0:
        return "INVALID"
    if a + b <= c or a + c <= b or b + c <= a:
        return "Invalid"
    if a == b and b == c:
        return "Equilateral"
    if a == b or b == c or a == c:
        return "Isosceles"
    return "Scalene"
def x_triangle__mutmut_12(a: int, b: int, c: int) -> str:
    if a <= 0 or b <= 0 or c <= 0:
        return "Invalid"
    if a + b <= c or a + c <= b and b + c <= a:
        return "Invalid"
    if a == b and b == c:
        return "Equilateral"
    if a == b or b == c or a == c:
        return "Isosceles"
    return "Scalene"
def x_triangle__mutmut_13(a: int, b: int, c: int) -> str:
    if a <= 0 or b <= 0 or c <= 0:
        return "Invalid"
    if a + b <= c and a + c <= b or b + c <= a:
        return "Invalid"
    if a == b and b == c:
        return "Equilateral"
    if a == b or b == c or a == c:
        return "Isosceles"
    return "Scalene"
def x_triangle__mutmut_14(a: int, b: int, c: int) -> str:
    if a <= 0 or b <= 0 or c <= 0:
        return "Invalid"
    if a - b <= c or a + c <= b or b + c <= a:
        return "Invalid"
    if a == b and b == c:
        return "Equilateral"
    if a == b or b == c or a == c:
        return "Isosceles"
    return "Scalene"
def x_triangle__mutmut_15(a: int, b: int, c: int) -> str:
    if a <= 0 or b <= 0 or c <= 0:
        return "Invalid"
    if a + b < c or a + c <= b or b + c <= a:
        return "Invalid"
    if a == b and b == c:
        return "Equilateral"
    if a == b or b == c or a == c:
        return "Isosceles"
    return "Scalene"
def x_triangle__mutmut_16(a: int, b: int, c: int) -> str:
    if a <= 0 or b <= 0 or c <= 0:
        return "Invalid"
    if a + b <= c or a - c <= b or b + c <= a:
        return "Invalid"
    if a == b and b == c:
        return "Equilateral"
    if a == b or b == c or a == c:
        return "Isosceles"
    return "Scalene"
def x_triangle__mutmut_17(a: int, b: int, c: int) -> str:
    if a <= 0 or b <= 0 or c <= 0:
        return "Invalid"
    if a + b <= c or a + c < b or b + c <= a:
        return "Invalid"
    if a == b and b == c:
        return "Equilateral"
    if a == b or b == c or a == c:
        return "Isosceles"
    return "Scalene"
def x_triangle__mutmut_18(a: int, b: int, c: int) -> str:
    if a <= 0 or b <= 0 or c <= 0:
        return "Invalid"
    if a + b <= c or a + c <= b or b - c <= a:
        return "Invalid"
    if a == b and b == c:
        return "Equilateral"
    if a == b or b == c or a == c:
        return "Isosceles"
    return "Scalene"
def x_triangle__mutmut_19(a: int, b: int, c: int) -> str:
    if a <= 0 or b <= 0 or c <= 0:
        return "Invalid"
    if a + b <= c or a + c <= b or b + c < a:
        return "Invalid"
    if a == b and b == c:
        return "Equilateral"
    if a == b or b == c or a == c:
        return "Isosceles"
    return "Scalene"
def x_triangle__mutmut_20(a: int, b: int, c: int) -> str:
    if a <= 0 or b <= 0 or c <= 0:
        return "Invalid"
    if a + b <= c or a + c <= b or b + c <= a:
        return "XXInvalidXX"
    if a == b and b == c:
        return "Equilateral"
    if a == b or b == c or a == c:
        return "Isosceles"
    return "Scalene"
def x_triangle__mutmut_21(a: int, b: int, c: int) -> str:
    if a <= 0 or b <= 0 or c <= 0:
        return "Invalid"
    if a + b <= c or a + c <= b or b + c <= a:
        return "invalid"
    if a == b and b == c:
        return "Equilateral"
    if a == b or b == c or a == c:
        return "Isosceles"
    return "Scalene"
def x_triangle__mutmut_22(a: int, b: int, c: int) -> str:
    if a <= 0 or b <= 0 or c <= 0:
        return "Invalid"
    if a + b <= c or a + c <= b or b + c <= a:
        return "INVALID"
    if a == b and b == c:
        return "Equilateral"
    if a == b or b == c or a == c:
        return "Isosceles"
    return "Scalene"
def x_triangle__mutmut_23(a: int, b: int, c: int) -> str:
    if a <= 0 or b <= 0 or c <= 0:
        return "Invalid"
    if a + b <= c or a + c <= b or b + c <= a:
        return "Invalid"
    if a == b or b == c:
        return "Equilateral"
    if a == b or b == c or a == c:
        return "Isosceles"
    return "Scalene"
def x_triangle__mutmut_24(a: int, b: int, c: int) -> str:
    if a <= 0 or b <= 0 or c <= 0:
        return "Invalid"
    if a + b <= c or a + c <= b or b + c <= a:
        return "Invalid"
    if a != b and b == c:
        return "Equilateral"
    if a == b or b == c or a == c:
        return "Isosceles"
    return "Scalene"
def x_triangle__mutmut_25(a: int, b: int, c: int) -> str:
    if a <= 0 or b <= 0 or c <= 0:
        return "Invalid"
    if a + b <= c or a + c <= b or b + c <= a:
        return "Invalid"
    if a == b and b != c:
        return "Equilateral"
    if a == b or b == c or a == c:
        return "Isosceles"
    return "Scalene"
def x_triangle__mutmut_26(a: int, b: int, c: int) -> str:
    if a <= 0 or b <= 0 or c <= 0:
        return "Invalid"
    if a + b <= c or a + c <= b or b + c <= a:
        return "Invalid"
    if a == b and b == c:
        return "XXEquilateralXX"
    if a == b or b == c or a == c:
        return "Isosceles"
    return "Scalene"
def x_triangle__mutmut_27(a: int, b: int, c: int) -> str:
    if a <= 0 or b <= 0 or c <= 0:
        return "Invalid"
    if a + b <= c or a + c <= b or b + c <= a:
        return "Invalid"
    if a == b and b == c:
        return "equilateral"
    if a == b or b == c or a == c:
        return "Isosceles"
    return "Scalene"
def x_triangle__mutmut_28(a: int, b: int, c: int) -> str:
    if a <= 0 or b <= 0 or c <= 0:
        return "Invalid"
    if a + b <= c or a + c <= b or b + c <= a:
        return "Invalid"
    if a == b and b == c:
        return "EQUILATERAL"
    if a == b or b == c or a == c:
        return "Isosceles"
    return "Scalene"
def x_triangle__mutmut_29(a: int, b: int, c: int) -> str:
    if a <= 0 or b <= 0 or c <= 0:
        return "Invalid"
    if a + b <= c or a + c <= b or b + c <= a:
        return "Invalid"
    if a == b and b == c:
        return "Equilateral"
    if a == b or b == c and a == c:
        return "Isosceles"
    return "Scalene"
def x_triangle__mutmut_30(a: int, b: int, c: int) -> str:
    if a <= 0 or b <= 0 or c <= 0:
        return "Invalid"
    if a + b <= c or a + c <= b or b + c <= a:
        return "Invalid"
    if a == b and b == c:
        return "Equilateral"
    if a == b and b == c or a == c:
        return "Isosceles"
    return "Scalene"
def x_triangle__mutmut_31(a: int, b: int, c: int) -> str:
    if a <= 0 or b <= 0 or c <= 0:
        return "Invalid"
    if a + b <= c or a + c <= b or b + c <= a:
        return "Invalid"
    if a == b and b == c:
        return "Equilateral"
    if a != b or b == c or a == c:
        return "Isosceles"
    return "Scalene"
def x_triangle__mutmut_32(a: int, b: int, c: int) -> str:
    if a <= 0 or b <= 0 or c <= 0:
        return "Invalid"
    if a + b <= c or a + c <= b or b + c <= a:
        return "Invalid"
    if a == b and b == c:
        return "Equilateral"
    if a == b or b != c or a == c:
        return "Isosceles"
    return "Scalene"
def x_triangle__mutmut_33(a: int, b: int, c: int) -> str:
    if a <= 0 or b <= 0 or c <= 0:
        return "Invalid"
    if a + b <= c or a + c <= b or b + c <= a:
        return "Invalid"
    if a == b and b == c:
        return "Equilateral"
    if a == b or b == c or a != c:
        return "Isosceles"
    return "Scalene"
def x_triangle__mutmut_34(a: int, b: int, c: int) -> str:
    if a <= 0 or b <= 0 or c <= 0:
        return "Invalid"
    if a + b <= c or a + c <= b or b + c <= a:
        return "Invalid"
    if a == b and b == c:
        return "Equilateral"
    if a == b or b == c or a == c:
        return "XXIsoscelesXX"
    return "Scalene"
def x_triangle__mutmut_35(a: int, b: int, c: int) -> str:
    if a <= 0 or b <= 0 or c <= 0:
        return "Invalid"
    if a + b <= c or a + c <= b or b + c <= a:
        return "Invalid"
    if a == b and b == c:
        return "Equilateral"
    if a == b or b == c or a == c:
        return "isosceles"
    return "Scalene"
def x_triangle__mutmut_36(a: int, b: int, c: int) -> str:
    if a <= 0 or b <= 0 or c <= 0:
        return "Invalid"
    if a + b <= c or a + c <= b or b + c <= a:
        return "Invalid"
    if a == b and b == c:
        return "Equilateral"
    if a == b or b == c or a == c:
        return "ISOSCELES"
    return "Scalene"
def x_triangle__mutmut_37(a: int, b: int, c: int) -> str:
    if a <= 0 or b <= 0 or c <= 0:
        return "Invalid"
    if a + b <= c or a + c <= b or b + c <= a:
        return "Invalid"
    if a == b and b == c:
        return "Equilateral"
    if a == b or b == c or a == c:
        return "Isosceles"
    return "XXScaleneXX"
def x_triangle__mutmut_38(a: int, b: int, c: int) -> str:
    if a <= 0 or b <= 0 or c <= 0:
        return "Invalid"
    if a + b <= c or a + c <= b or b + c <= a:
        return "Invalid"
    if a == b and b == c:
        return "Equilateral"
    if a == b or b == c or a == c:
        return "Isosceles"
    return "scalene"
def x_triangle__mutmut_39(a: int, b: int, c: int) -> str:
    if a <= 0 or b <= 0 or c <= 0:
        return "Invalid"
    if a + b <= c or a + c <= b or b + c <= a:
        return "Invalid"
    if a == b and b == c:
        return "Equilateral"
    if a == b or b == c or a == c:
        return "Isosceles"
    return "SCALENE"

x_triangle__mutmut_mutants : ClassVar[MutantDict] = { # type: ignore
'x_triangle__mutmut_1': x_triangle__mutmut_1, 
    'x_triangle__mutmut_2': x_triangle__mutmut_2, 
    'x_triangle__mutmut_3': x_triangle__mutmut_3, 
    'x_triangle__mutmut_4': x_triangle__mutmut_4, 
    'x_triangle__mutmut_5': x_triangle__mutmut_5, 
    'x_triangle__mutmut_6': x_triangle__mutmut_6, 
    'x_triangle__mutmut_7': x_triangle__mutmut_7, 
    'x_triangle__mutmut_8': x_triangle__mutmut_8, 
    'x_triangle__mutmut_9': x_triangle__mutmut_9, 
    'x_triangle__mutmut_10': x_triangle__mutmut_10, 
    'x_triangle__mutmut_11': x_triangle__mutmut_11, 
    'x_triangle__mutmut_12': x_triangle__mutmut_12, 
    'x_triangle__mutmut_13': x_triangle__mutmut_13, 
    'x_triangle__mutmut_14': x_triangle__mutmut_14, 
    'x_triangle__mutmut_15': x_triangle__mutmut_15, 
    'x_triangle__mutmut_16': x_triangle__mutmut_16, 
    'x_triangle__mutmut_17': x_triangle__mutmut_17, 
    'x_triangle__mutmut_18': x_triangle__mutmut_18, 
    'x_triangle__mutmut_19': x_triangle__mutmut_19, 
    'x_triangle__mutmut_20': x_triangle__mutmut_20, 
    'x_triangle__mutmut_21': x_triangle__mutmut_21, 
    'x_triangle__mutmut_22': x_triangle__mutmut_22, 
    'x_triangle__mutmut_23': x_triangle__mutmut_23, 
    'x_triangle__mutmut_24': x_triangle__mutmut_24, 
    'x_triangle__mutmut_25': x_triangle__mutmut_25, 
    'x_triangle__mutmut_26': x_triangle__mutmut_26, 
    'x_triangle__mutmut_27': x_triangle__mutmut_27, 
    'x_triangle__mutmut_28': x_triangle__mutmut_28, 
    'x_triangle__mutmut_29': x_triangle__mutmut_29, 
    'x_triangle__mutmut_30': x_triangle__mutmut_30, 
    'x_triangle__mutmut_31': x_triangle__mutmut_31, 
    'x_triangle__mutmut_32': x_triangle__mutmut_32, 
    'x_triangle__mutmut_33': x_triangle__mutmut_33, 
    'x_triangle__mutmut_34': x_triangle__mutmut_34, 
    'x_triangle__mutmut_35': x_triangle__mutmut_35, 
    'x_triangle__mutmut_36': x_triangle__mutmut_36, 
    'x_triangle__mutmut_37': x_triangle__mutmut_37, 
    'x_triangle__mutmut_38': x_triangle__mutmut_38, 
    'x_triangle__mutmut_39': x_triangle__mutmut_39
}
x_triangle__mutmut_orig.__name__ = 'x_triangle'
