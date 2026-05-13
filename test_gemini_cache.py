from triangle import classify_triangle
import pytest

EPSILON = 1e-9

@pytest.mark.parametrize("a, b, c", [
    (0, 5, 5),
    (5, 0, 5),
    (5, 5, 0),
    (-1, 5, 5),
    (5, -1, 5),
    (5, 5, -1),
    (0, 0, 5),
    (0, 5, 0),
    (5, 0, 0),
    (0, 0, 0),
    (-1, -1, 5),
    (-1, 5, -1),
    (5, -1, -1),
    (-1, -1, -1),
    (0, -1, 5),
    (-1, 0, 5),
    (5, 0, -1)
])
def test_invalid_sides(a, b, c):
    assert classify_triangle(a, b, c) == "Invalid"

@pytest.mark.parametrize("a, b, c", [
    (1, 2, 3),
    (3, 1, 2),
    (2, 3, 1),
    (5, 5, 10),
    (10, 5, 5),
    (5, 10, 5),
    (100, 200, 300),
    (300, 100, 200),
    (200, 300, 100),
    (1, 2, 4),
    (4, 1, 2),
    (2, 4, 1),
    (5, 5, 11),
    (11, 5, 5),
    (5, 11, 5),
    (100, 200, 400),
    (400, 100, 200),
    (200, 400, 100),
    (1, 2, 3 + EPSILON),
    (3 + EPSILON, 1, 2),
    (2, 3 + EPSILON, 1),
    (5, 5, 10 + EPSILON),
    (10 + EPSILON, 5, 5),
    (5, 10 + EPSILON, 5),
])
def test_not_a_triangle(a, b, c):
    assert classify_triangle(a, b, c) == "Not a Triangle"

@pytest.mark.parametrize("a, b, c", [
    (1, 1, 1),
    (5, 5, 5),
    (1000, 1000, 1000),
    (1.0, 1.0, 1.0),
    (5.5, 5.5, 5.5),
])
def test_equilateral(a, b, c):
    assert classify_triangle(a, b, c) == "Equilateral"

@pytest.mark.parametrize("a, b, c", [
    (5, 5, 3),
    (5, 5, 1),
    (5, 5, 9),
    (2.5, 2.5, 4),
    (100, 100, 1),
    (3, 5, 5),
    (1, 5, 5),
    (9, 5, 5),
    (4, 2.5, 2.5),
    (1, 100, 100),
    (5, 3, 5),
    (5, 1, 5),
    (5, 9, 5),
    (2.5, 4, 2.5),
    (100, 1, 100),
    (5, 5, 5 - EPSILON),
    (5, 5 - EPSILON, 5),
    (5 - EPSILON, 5, 5),
    (5, 5, 5 + EPSILON),
    (5, 5 + EPSILON, 5),
    (5 + EPSILON, 5, 5),
    (5, 5, 10 - EPSILON),
    (10 - EPSILON, 5, 5),
    (5, 10 - EPSILON, 5),
])
def test_isosceles(a, b, c):
    assert classify_triangle(a, b, c) == "Isosceles"

@pytest.mark.parametrize("a, b, c", [
    (3, 4, 5),
    (2, 3, 4),
    (10, 11, 12),
    (100, 101, 102),
    (3.1, 4.2, 5.3),
    (1, 2, 3 - EPSILON),
    (3, 5, 4),
    (4, 3, 5),
    (4, 5, 3),
    (5, 3, 4),
    (5, 4, 3),
    (5, 6, 6 + EPSILON),
    (6 + EPSILON, 5, 6),
    (6, 6 + EPSILON, 5),
    (5, 6 + EPSILON, 6),
    (6, 5, 6 + EPSILON),
    (6 + EPSILON, 6, 5),
    (5 + EPSILON, 6, 7),
])
def test_scalene(a, b, c):
    assert classify_triangle(a, b, c) == "Scalene"

def test_boundary_not_a_triangle_and_scalene_isosceles():
    assert classify_triangle(1, 2, 3) == "Not a Triangle"
    assert classify_triangle(5, 5, 10) == "Not a Triangle"
    assert classify_triangle(1, 2, 3 + EPSILON) == "Not a Triangle"
    assert classify_triangle(5, 5, 10 + EPSILON) == "Not a Triangle"
    assert classify_triangle(1, 2, 3 - EPSILON) == "Scalene"
    assert classify_triangle(5, 5, 10 - EPSILON) == "Isosceles"

def test_float_precision_edge_cases():
    assert classify_triangle(1.0000000001, 1.0000000001, 1.0000000001) == "Equilateral"
    assert classify_triangle(1.0, 1.0, 1.0 + EPSILON) == "Isosceles"
    assert classify_triangle(1.0, 1.0 + EPSILON, 1.0 + 2*EPSILON) == "Scalene"
    assert classify_triangle(1.0, 1.0, 2.0 - EPSILON) == "Isosceles"
    assert classify_triangle(1.0, 1.0, 2.0) == "Not a Triangle"
    assert classify_triangle(1.0, 1.0, 2.0 + EPSILON) == "Not a Triangle"

def test_large_numbers():
    assert classify_triangle(1_000_000, 1_000_000, 1_000_000) == "Equilateral"
    assert classify_triangle(1_000_000, 1_000_000, 1_500_000) == "Isosceles"
    assert classify_triangle(1_000_000, 1_000_001, 1_000_002) == "Scalene"
    assert classify_triangle(1_000_000, 1_000_000, 2_000_000) == "Not a Triangle"
    assert classify_triangle(1_000_000, 1_000_000, 2_000_001) == "Not a Triangle"
    assert classify_triangle(1_000_000, 1_000_000, 0) == "Invalid"
    assert classify_triangle(1_000_000, 1_000_000, -1) == "Invalid"

def test_or_mutation_specifics():
    assert classify_triangle(0, 1, 1) == "Invalid"
    assert classify_triangle(1, 0, 1) == "Invalid"
    assert classify_triangle(1, 1, 0) == "Invalid"
    assert classify_triangle(-1, 1, 1) == "Invalid"
    assert classify_triangle(1, 2, 4) == "Not a Triangle"
    assert classify_triangle(4, 1, 2) == "Not a Triangle"
    assert classify_triangle(2, 4, 1) == "Not a Triangle"
    assert classify_triangle(5, 5, 3) == "Isosceles"
    assert classify_triangle(3, 5, 5) == "Isosceles"
    assert classify_triangle(5, 3, 5) == "Isosceles"