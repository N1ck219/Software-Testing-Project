from triangle import classify_triangle
import pytest

class TestClassifyTriangle:

    # Test cases for Invalid triangles (sides <= 0)
    @pytest.mark.parametrize("a, b, c", [
        (0, 5, 5),          # One side exactly zero
        (5, 0, 5),
        (5, 5, 0),
        (-1, 5, 5),         # One side negative
        (5, -1, 5),
        (5, 5, -1),
        (0, 0, 5),          # Two sides exactly zero
        (0, 5, 0),
        (5, 0, 0),
        (-1, -1, 5),        # Two sides negative
        (-1, 5, -1),
        (5, -1, -1),
        (0, 0, 0),          # All sides exactly zero
        (-1, -1, -1),       # All sides negative
        (-5, 0, 5),         # Mixed zero and negative
        (0, -5, 5),
        (5, 0, -5),
        (-100, -200, -300), # Large negative values
    ])
    def test_invalid_sides(self, a, b, c):
        assert classify_triangle(a, b, c) == "Invalid"

    # Test cases for "Not a Triangle" due to triangle inequality violation
    # Sum of two sides exactly equal to the third (degenerate)
    @pytest.mark.parametrize("a, b, c", [
        (1, 2, 3),
        (3, 1, 2),
        (2, 3, 1),
        (5, 10, 15),
        (15, 5, 10),
        (10, 15, 5),
        (1, 1, 2),          # Isosceles degenerate
        (1, 2, 1),
        (2, 1, 1),
        (100, 100, 200),    # Large isosceles degenerate
        (100, 200, 100),
        (200, 100, 100),
        (1000000, 2000000, 3000000), # Very large degenerate scalene
    ])
    def test_not_a_triangle_degenerate(self, a, b, c):
        assert classify_triangle(a, b, c) == "Not a Triangle"

    # Sum of two sides less than the third (impossible)
    @pytest.mark.parametrize("a, b, c", [
        (1, 2, 4),
        (4, 1, 2),
        (2, 4, 1),
        (1, 1, 3),          # Isosceles impossible
        (1, 3, 1),
        (3, 1, 1),
        (1, 1, 100),        # Very skewed impossible
        (100, 1, 1),
        (1, 100, 1),
        (5, 5, 100),        # Large impossible isosceles
        (5, 100, 5),
        (100, 5, 5),
        (1000000, 2000000, 4000000), # Very large impossible scalene
    ])
    def test_not_a_triangle_impossible(self, a, b, c):
        assert classify_triangle(a, b, c) == "Not a Triangle"

    # Boundary cases for triangle inequality - just barely a valid triangle
    @pytest.mark.parametrize("a, b, c, expected", [
        (2, 3, 4, "Scalene"),       # Sum=5 (a+b) > 4 (c)
        (4, 3, 2, "Scalene"),
        (3, 4, 2, "Scalene"),
        (5, 5, 9, "Isosceles"),     # Sum=10 (a+b) > 9 (c)
        (5, 9, 5, "Isosceles"),
        (9, 5, 5, "Isosceles"),
        (100, 100, 199, "Isosceles"), # Sum=200 > 199
        (100, 199, 100, "Isosceles"),
        (199, 100, 100, "Isosceles"),
        (10, 11, 20, "Scalene"),    # Sum=21 > 20
        (1999999999, 1999999999, 3999999997, "Isosceles"), # Large near-degenerate
    ])
    def test_not_a_triangle_boundaries_valid(self, a, b, c, expected):
        assert classify_triangle(a, b, c) == expected

    # Test cases for Equilateral triangles
    @pytest.mark.parametrize("side", [
        1, 2, 5, 100,
        1000000,                    # Large value
        999999999                   # Very large value
    ])
    def test_equilateral(self, side):
        assert classify_triangle(side, side, side) == "Equilateral"

    # Test cases for Isosceles triangles
    @pytest.mark.parametrize("a, b, c", [
        (2, 2, 1),          # Two sides equal, third is smaller
        (2, 1, 2),
        (1, 2, 2),
        (5, 5, 3),
        (5, 3, 5),
        (3, 5, 5),
        (2, 2, 3),          # Two sides equal, third is larger
        (2, 3, 2),
        (3, 2, 2),
        (5, 5, 8),
        (5, 8, 5),
        (8, 5, 5),
        (100, 100, 1),      # Very thin isosceles
        (100, 1, 100),
        (1, 100, 100),
        (1000000, 1000000, 1), # Large side, tiny base
        (1000000, 1, 1000000),
        (1, 1000000, 1000000),
        (1000000, 1000000, 1999999), # Large side, base near sum of other two
        (1000000, 1999999, 1000000),
        (1999999, 1000000, 1000000),
    ])
    def test_isosceles(self, a, b, c):
        assert classify_triangle(a, b, c) == "Isosceles"

    # Test cases for Scalene triangles
    @pytest.mark.parametrize("a, b, c", [
        (2, 3, 4),
        (4, 2, 3),
        (3, 4, 2),
        (3, 4, 5),          # Right-angled scalene
        (5, 3, 4),
        (4, 5, 3),
        (5, 6, 7),
        (7, 5, 6),
        (6, 7, 5),
        (10, 12, 14),       # Larger scalene
        (100, 101, 102),    # Large, consecutive sides
        (100, 102, 101),
        (101, 100, 102),
        (101, 102, 100),
        (102, 100, 101),
        (102, 101, 100),
        (10, 20, 25),       # Non-consecutive large scalene
        (20, 10, 25),
        (25, 10, 20),
        (1000000, 1000001, 1000002), # Very large scalene, consecutive
        (1000000, 2000000, 2500000), # Very large scalene, non-consecutive
    ])
    def test_scalene(self, a, b, c):
        assert classify_triangle(a, b, c) == "Scalene"

    # Additional tests for very specific boundary conditions to kill mutations
    # Test for `a <= 0` vs `a < 0`
    def test_invalid_exact_zero_mutation_killer(self):
        assert classify_triangle(0, 1, 1) == "Invalid"
        assert classify_triangle(1, 0, 1) == "Invalid"
        assert classify_triangle(1, 1, 0) == "Invalid"

    # Test for `a + b <= c` vs `a + b < c`
    def test_degenerate_exact_equality_mutation_killer(self):
        assert classify_triangle(1, 2, 3) == "Not a Triangle"
        assert classify_triangle(3, 1, 2) == "Not a Triangle"
        assert classify_triangle(2, 3, 1) == "Not a Triangle"

    # Test for `or` vs `and` in invalid side check
    def test_invalid_one_side_zero_mutation_killer(self):
        # This test ensures `a <= 0 or b <= 0 or c <= 0` does not become `and`
        assert classify_triangle(0, 5, 5) == "Invalid"
        assert classify_triangle(5, 0, 5) == "Invalid"
        assert classify_triangle(5, 5, 0) == "Invalid"

    # Test for `or` vs `and` in not a triangle check
    def test_not_a_triangle_one_condition_mutation_killer(self):
        # This test ensures `a+b<=c or a+c<=b or b+c<=a` does not become `and`
        assert classify_triangle(1, 2, 3) == "Not a Triangle" # Only a+b<=c is true
        assert classify_triangle(3, 1, 2) == "Not a Triangle" # Only a+c<=b is true
        assert classify_triangle(2, 3, 1) == "Not a Triangle" # Only b+c<=a is true

    # Test for `or` vs `and` in isosceles check
    def test_isosceles_one_pair_equal_mutation_killer(self):
        # This test ensures `a==b or b==c or a==c` does not become `and`
        assert classify_triangle(2, 2, 3) == "Isosceles" # Only a==b is true
        assert classify_triangle(2, 3, 2) == "Isosceles" # Only a==c is true
        assert classify_triangle(3, 2, 2) == "Isosceles" # Only b==c is true