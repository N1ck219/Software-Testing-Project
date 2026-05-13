import pytest
from triangle import classify_triangle

# Test cases for Invalid Triangles (sides <= 0)
@pytest.mark.parametrize("a, b, c, expected", [
    (0, 1, 1, "Invalid"),
    (1, 0, 1, "Invalid"),
    (1, 1, 0, "Invalid"),
    (0.0, 1, 1, "Invalid"),  # Float 0
    (1, 0.0, 1, "Invalid"),
    (1, 1, 0.0, "Invalid"),
    (-1, 1, 1, "Invalid"),
    (1, -1, 1, "Invalid"),
    (1, 1, -1, "Invalid"),
    (-0.00001, 1, 1, "Invalid"),  # Small negative value (5 decimal places)
    (1, -0.00001, 1, "Invalid"),
    (1, 1, -0.00001, "Invalid"),
    (0, 0, 0, "Invalid"),
    (-1, -1, -1, "Invalid"),
    (100, 100, 0, "Invalid"),
])
def test_classify_triangle_invalid_sides(a, b, c, expected):
    assert classify_triangle(a, b, c) == expected

# Test cases for "Not a Triangle" (violates triangle inequality)
# Cases where a + b <= c, a + c <= b, or b + c <= a
@pytest.mark.parametrize("a, b, c, expected", [
    # Degenerate triangles (sum equals third side) using integers or exact floats
    (1, 1, 2, "Not a Triangle"),
    (1, 2, 1, "Not a Triangle"),
    (2, 1, 1, "Not a Triangle"),
    (500000000, 500000000, 1000000000, "Not a Triangle"),  # Large integer degenerate
    (0.00001, 0.00001, 0.00002, "Not a Triangle"),  # Small float degenerate (exact binary repr)
    
    # Non-degenerate "Not a Triangle" (sum is less than third side)
    (1, 1, 3, "Not a Triangle"),
    (1, 3, 1, "Not a Triangle"),
    (3, 1, 1, "Not a Triangle"),
    (1, 2, 4, "Not a Triangle"),
    (4, 1, 2, "Not a Triangle"),
    (2, 4, 1, "Not a Triangle"),
    (1, 1, 1000000000, "Not a Triangle"),  # One side much larger
    (0.00001, 0.00001, 0.00003, "Not a Triangle"),  # Small floats
    (0.1, 0.2, 0.5, "Not a Triangle"), # Floating point numbers (0.1+0.2 is not 0.3) but 0.3 < 0.5 is clearly true
])
def test_classify_triangle_not_a_triangle(a, b, c, expected):
    assert classify_triangle(a, b, c) == expected

# Test cases for Equilateral Triangles
@pytest.mark.parametrize("a, b, c, expected", [
    (1, 1, 1, "Equilateral"),
    (100, 100, 100, "Equilateral"),
    (0.00001, 0.00001, 0.00001, "Equilateral"),  # Small float
    (1000000000, 1000000000, 1000000000, "Equilateral"),  # Max limit
    (3.14159, 3.14159, 3.14159, "Equilateral"),  # With 5 decimal places
])
def test_classify_triangle_equilateral(a, b, c, expected):
    assert classify_triangle(a, b, c) == expected

# Test cases for Isosceles Triangles
@pytest.mark.parametrize("a, b, c, expected", [
    (2, 2, 3, "Isosceles"),
    (2, 3, 2, "Isosceles"),
    (3, 2, 2, "Isosceles"),
    (5, 5, 8, "Isosceles"),
    (5, 8, 5, "Isosceles"),
    (8, 5, 5, "Isosceles"),
    (0.00002, 0.00002, 0.00003, "Isosceles"),  # Small floats
    (0.00002, 0.00003, 0.00002, "Isosceles"),
    (0.00003, 0.00002, 0.00002, "Isosceles"),
    (1000000000, 1000000000, 999999999, "Isosceles"),  # Large, but not equilateral
    (1000000000, 999999999, 1000000000, "Isosceles"),
    (999999999, 1000000000, 1000000000, "Isosceles"),
    (1.23456, 1.23456, 2.0, "Isosceles"),  # With 5 decimal places
])
def test_classify_triangle_isosceles(a, b, c, expected):
    assert classify_triangle(a, b, c) == expected

# Test cases for Scalene Triangles
@pytest.mark.parametrize("a, b, c, expected", [
    (3, 4, 5, "Scalene"),  # Right triangle, classic scalene
    (2, 3, 4, "Scalene"),
    (5, 12, 13, "Scalene"),
    (10, 11, 12, "Scalene"),
    (0.1, 0.2, 0.25, "Scalene"),  # Small floats (all distinct, triangle inequality holds)
    (1000000000 - 2, 1000000000 - 1, 1000000000, "Scalene"),  # Large values, all different
    (2.1, 3.2, 4.3, "Scalene"),  # Floats with one decimal place
    (1.00001, 1.00002, 1.00003, "Scalene"),  # Floats with 5 decimal places, distinct
    (100, 101, 102, "Scalene"),
])
def test_classify_triangle_scalene(a, b, c, expected):
    assert classify_triangle(a, b, c) == expected

# Specific boundary and mutation-killing tests for comparison operators and logic
# Test `a <= 0 or b <= 0 or c <= 0`
@pytest.mark.parametrize("a, b, c, expected", [
    (0, 1, 1, "Invalid"),  # Exactly 0
    (1, 1, 0, "Invalid"),
    (0.00001, 1, 1, "Isosceles"),  # Just above 0 (should not be Invalid)
    (1, 0.00001, 1, "Isosceles"),
    (1, 1, 0.00001, "Isosceles"),
    (-0.00001, 1, 1, "Invalid"),  # Just below 0
])
def test_classify_triangle_boundary_zero_or_less(a, b, c, expected):
    assert classify_triangle(a, b, c) == expected

# Test `a + b <= c or a + c <= b or b + c <= a`
# Focus on the strict boundary between "Not a Triangle" and valid triangles
@pytest.mark.parametrize("a, b, c, expected", [
    # a + b == c (degenerate case)
    (1, 2, 3, "Not a Triangle"),
    (500000000, 500000000, 1000000000, "Not a Triangle"),
    (0.00001, 0.00001, 0.00002, "Not a Triangle"), # Console confirms exact equality for these floats
    
    # a + b is just slightly greater than c (should be a valid triangle)
    # This specifically targets mutations of `<=` to `<` or `==`
    (1, 2, 2.99999, "Scalene"),  # 1+2 = 3, which is > 2.99999. Valid triangle.
    (0.1, 0.2, 0.29999, "Scalene"), # (0.1+0.2 is approx 0.30000000000000004), which is > 0.29999. Valid triangle.
    
    # a + b is clearly less than c
    (1, 2, 4, "Not a Triangle"),
])
def test_classify_triangle_boundary_inequality(a, b, c, expected):
    assert classify_triangle(a, b, c) == expected

# Test `a == b == c` and `elif a == b or b == c or a == c` logic
# Ensures correct branching and operator usage (`and`/`or` and `==`/`!=`)
@pytest.mark.parametrize("a, b, c, expected", [
    # Equilateral: Ensures 'a == b == c' is correctly identified
    (7, 7, 7, "Equilateral"),
    
    # Isosceles: Ensures 'or' logic and exact two-side equality
    (8, 8, 9, "Isosceles"),  # a==b, c!=a
    (8, 9, 8, "Isosceles"),  # a==c, b!=a
    (9, 8, 8, "Isosceles"),  # b==c, a!=b
    (7.12345, 7.12345, 8.0, "Isosceles"), # float isosceles
    
    # Scalene: Ensures no two sides are equal
    (10, 11, 12, "Scalene"),
    (10.00001, 11.00002, 12.00003, "Scalene"), # Floats with 5 decimal places, distinct
])
def test_classify_triangle_equality_logic(a, b, c, expected):
    assert classify_triangle(a, b, c) == expected