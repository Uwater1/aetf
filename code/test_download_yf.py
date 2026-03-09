import pytest
import sys
import os

# Add the code directory to the sys.path to import download_yf
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from download_yf import get_yf_ticker

@pytest.mark.parametrize("input_code, expected", [
    # Shanghai stocks
    ("600000", "600000.SS"),
    ("510050", "510050.SS"),
    ("900901", "900901.SS"),
    (600000, "600000.SS"),
    (510050, "510050.SS"),
    (900901, "900901.SS"),

    # Shenzhen stocks
    ("000001", "000001.SZ"),
    ("300001", "300001.SZ"),
    ("159901", "159901.SZ"),
    ("200001", "200001.SZ"),
    (1, "1.SZ"),
    (300001, "300001.SZ"),

    # Other starting digits (defaults to .SZ according to code)
    ("400001", "400001.SZ"),
    ("888888", "888888.SZ"),

    # Edge cases: whitespace
    (" 600000 ", "600000.SS"),
    (" 000001 ", "000001.SZ"),
    ("\t600000\n", "600000.SS"),
    ("  ", ".SZ"),
])
def test_get_yf_ticker(input_code, expected):
    assert get_yf_ticker(input_code) == expected
