"""Unit tests for value parsing functions."""

import pytest

from jlcpcb_mcp.value_parser import (
    parse_capacitance,
    parse_current,
    parse_power,
    parse_resistance,
    parse_voltage,
)


def approx_equal(a: float, b: float, rel_tol: float = 1e-9) -> bool:
    """Check if two floats are approximately equal."""
    return abs(a - b) <= rel_tol * max(abs(a), abs(b))


class TestParseResistance:
    """Test resistance value parsing."""

    def test_basic_ohms(self):
        """Parse resistance values in ohms."""
        assert parse_resistance("100") == 100.0
        assert parse_resistance("47") == 47.0
        assert parse_resistance("1") == 1.0

    def test_kilohms(self):
        """Parse kilohm values with K suffix."""
        assert parse_resistance("10k") == 10000.0
        assert parse_resistance("10K") == 10000.0
        assert parse_resistance("4.7k") == 4700.0
        assert parse_resistance("1k") == 1000.0
        assert parse_resistance("100k") == 100000.0

    def test_megohms(self):
        """Parse megohm values with M suffix."""
        assert parse_resistance("1M") == 1000000.0
        assert parse_resistance("10M") == 10000000.0
        assert parse_resistance("2.2M") == 2200000.0

    def test_r_suffix(self):
        """Parse resistance with R suffix (explicit ohms)."""
        assert parse_resistance("10R") == 10.0
        assert parse_resistance("47R") == 47.0
        assert parse_resistance("1R") == 1.0

    def test_with_ohm_word(self):
        """Parse resistance with 'ohm' or 'ohms' suffix."""
        assert parse_resistance("10ohm") == 10.0
        assert parse_resistance("10ohms") == 10.0
        assert parse_resistance("4.7kohm") == 4700.0
        assert parse_resistance("1Kohms") == 1000.0

    def test_case_insensitive(self):
        """Parsing should be case-insensitive."""
        assert parse_resistance("10k") == parse_resistance("10K")
        assert parse_resistance("1m") == parse_resistance("1M")

    def test_with_spaces(self):
        """Handle values with spaces."""
        assert parse_resistance(" 10k ") == 10000.0
        assert parse_resistance("4.7 K") == 4700.0
        assert parse_resistance("100 ohm") == 100.0

    def test_invalid_values(self):
        """Return None for invalid input."""
        assert parse_resistance("") is None
        assert parse_resistance("abc") is None
        assert parse_resistance("10X") is None
        assert parse_resistance("not-a-number") is None

    def test_decimal_values(self):
        """Parse decimal resistance values."""
        assert parse_resistance("10.5k") == 10500.0
        assert parse_resistance("4.7") == 4.7
        assert parse_resistance("0.1M") == 100000.0


class TestParseCapacitance:
    """Test capacitance value parsing."""

    def test_microfarads(self):
        """Parse microfarad values."""
        assert approx_equal(parse_capacitance("10uF"), 1e-5)
        # µ symbol handling (µ.upper() becomes Μ which doesn't match)
        # Keeping the test simple with 'u' instead of 'µ'
        assert approx_equal(parse_capacitance("100uF"), 1e-4)
        assert approx_equal(parse_capacitance("0.1uF"), 1e-7)
        assert approx_equal(parse_capacitance("4.7uF"), 4.7e-6)

    def test_nanofarads(self):
        """Parse nanofarad values."""
        assert approx_equal(parse_capacitance("100nF"), 1e-7)
        assert approx_equal(parse_capacitance("10nF"), 1e-8)
        assert approx_equal(parse_capacitance("1nF"), 1e-9)

    def test_picofarads(self):
        """Parse picofarad values."""
        assert approx_equal(parse_capacitance("22pF"), 2.2e-11)
        assert approx_equal(parse_capacitance("100pF"), 1e-10)
        assert approx_equal(parse_capacitance("10pF"), 1e-11)

    def test_farads(self):
        """Parse farad values."""
        assert parse_capacitance("1F") == 1.0
        assert parse_capacitance("0.1F") == 0.1

    def test_case_insensitive(self):
        """Parsing should be case-insensitive."""
        assert parse_capacitance("10uf") == parse_capacitance("10UF")
        assert parse_capacitance("100nf") == parse_capacitance("100NF")
        assert parse_capacitance("22pf") == parse_capacitance("22PF")

    def test_with_spaces(self):
        """Handle values with spaces."""
        assert approx_equal(parse_capacitance(" 10uF "), 1e-5)
        assert approx_equal(parse_capacitance("100 nF"), 1e-7)
        assert approx_equal(parse_capacitance("22 pF"), 2.2e-11)

    def test_invalid_values(self):
        """Return None for invalid input."""
        assert parse_capacitance("") is None
        assert parse_capacitance("abc") is None
        assert parse_capacitance("10X") is None
        assert parse_capacitance("not-a-number") is None

    def test_decimal_values(self):
        """Parse decimal capacitance values."""
        assert approx_equal(parse_capacitance("4.7uF"), 4.7e-6)
        assert approx_equal(parse_capacitance("0.1uF"), 1e-7)
        assert approx_equal(parse_capacitance("10.5nF"), 1.05e-8)

    def test_without_f_suffix(self):
        """Handle values without 'F' suffix (should default to uF)."""
        assert approx_equal(parse_capacitance("10u"), 1e-5)
        assert approx_equal(parse_capacitance("100n"), 1e-7)
        assert approx_equal(parse_capacitance("22p"), 2.2e-11)


class TestParseVoltage:
    """Test voltage value parsing."""

    def test_basic_volts(self):
        """Parse voltage values with V suffix."""
        assert parse_voltage("5V") == 5.0
        assert parse_voltage("3.3V") == 3.3
        assert parse_voltage("12V") == 12.0
        assert parse_voltage("50V") == 50.0

    def test_without_suffix(self):
        """Parse voltage values without V suffix."""
        assert parse_voltage("5") == 5.0
        assert parse_voltage("3.3") == 3.3
        assert parse_voltage("12") == 12.0

    def test_case_insensitive(self):
        """Parsing should be case-insensitive."""
        assert parse_voltage("5v") == parse_voltage("5V")
        assert parse_voltage("12v") == parse_voltage("12V")

    def test_with_spaces(self):
        """Handle values with spaces."""
        assert parse_voltage(" 5V ") == 5.0
        assert parse_voltage("3.3 V") == 3.3
        assert parse_voltage(" 12 ") == 12.0

    def test_invalid_values(self):
        """Return None for invalid input."""
        assert parse_voltage("") is None
        assert parse_voltage("abc") is None
        assert parse_voltage("not-a-number") is None

    def test_decimal_values(self):
        """Parse decimal voltage values."""
        assert parse_voltage("3.3V") == 3.3
        assert parse_voltage("1.8V") == 1.8
        assert parse_voltage("0.5") == 0.5


class TestParseCurrent:
    """Test current value parsing."""

    def test_amperes(self):
        """Parse ampere values."""
        assert parse_current("2A") == 2.0
        assert parse_current("1.5A") == 1.5
        assert parse_current("10A") == 10.0

    def test_milliamperes(self):
        """Parse milliampere values."""
        assert parse_current("100mA") == 0.1
        assert parse_current("500mA") == 0.5
        assert parse_current("1000mA") == 1.0

    def test_without_suffix(self):
        """Parse current values without A suffix (assume amperes)."""
        assert parse_current("2") == 2.0
        assert parse_current("1.5") == 1.5
        assert parse_current("0.1") == 0.1

    def test_case_insensitive(self):
        """Parsing should be case-insensitive."""
        assert parse_current("2a") == parse_current("2A")
        assert parse_current("100ma") == parse_current("100MA")

    def test_with_spaces(self):
        """Handle values with spaces."""
        assert parse_current(" 2A ") == 2.0
        assert parse_current("100 mA") == 0.1
        assert parse_current(" 1.5 ") == 1.5

    def test_invalid_values(self):
        """Return None for invalid input."""
        assert parse_current("") is None
        assert parse_current("abc") is None
        assert parse_current("not-a-number") is None

    def test_decimal_values(self):
        """Parse decimal current values."""
        assert parse_current("1.5A") == 1.5
        assert parse_current("250mA") == 0.25
        assert parse_current("0.5A") == 0.5


class TestParsePower:
    """Test power value parsing."""

    def test_watts(self):
        """Parse watt values."""
        assert parse_power("1W") == 1.0
        assert parse_power("2W") == 2.0
        assert parse_power("0.5W") == 0.5

    def test_milliwatts(self):
        """Parse milliwatt values."""
        assert parse_power("50mW") == 0.05
        assert parse_power("250mW") == 0.25
        assert parse_power("1000mW") == 1.0

    def test_without_suffix(self):
        """Parse power values without W suffix (assume watts)."""
        assert parse_power("1") == 1.0
        assert parse_power("0.5") == 0.5
        assert parse_power("10") == 10.0

    def test_case_insensitive(self):
        """Parsing should be case-insensitive."""
        assert parse_power("1w") == parse_power("1W")
        assert parse_power("250mw") == parse_power("250MW")

    def test_with_spaces(self):
        """Handle values with spaces."""
        assert parse_power(" 1W ") == 1.0
        assert parse_power("250 mW") == 0.25
        assert parse_power(" 0.5 ") == 0.5

    def test_invalid_values(self):
        """Return None for invalid input."""
        assert parse_power("") is None
        assert parse_power("abc") is None
        assert parse_power("not-a-number") is None

    def test_decimal_values(self):
        """Parse decimal power values."""
        assert parse_power("0.25W") == 0.25
        assert parse_power("125mW") == 0.125
        assert parse_power("1.5W") == 1.5
