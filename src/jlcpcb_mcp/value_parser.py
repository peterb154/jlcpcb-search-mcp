"""Utilities for parsing electrical component values."""

import re


def parse_resistance(value_str: str) -> float | None:
    """
    Parse resistance value to ohms.

    Examples:
        "10k" -> 10000.0
        "10kohm" -> 10000.0
        "4.7K" -> 4700.0
        "100" -> 100.0
        "1M" -> 1000000.0
        "10R" -> 10.0

    Returns:
        Resistance in ohms, or None if cannot parse.
    """
    if not value_str:
        return None

    value_str = value_str.strip().upper()

    # Match number followed by optional multiplier
    pattern = r"^([\d.]+)\s*([KMRΩ])?(?:OHM)?S?$"
    match = re.match(pattern, value_str)

    if not match:
        return None

    number, multiplier = match.groups()

    try:
        base_value = float(number)
    except ValueError:
        return None

    # Apply multiplier
    multipliers = {"K": 1e3, "M": 1e6, "R": 1, "Ω": 1, None: 1}

    return base_value * multipliers.get(multiplier, 1)


def parse_capacitance(value_str: str) -> float | None:
    """
    Parse capacitance value to farads.

    Examples:
        "10uF" -> 1e-5
        "10µF" -> 1e-5
        "100nF" -> 1e-7
        "22pF" -> 2.2e-11
        "0.1uF" -> 1e-7

    Returns:
        Capacitance in farads, or None if cannot parse.
    """
    if not value_str:
        return None

    value_str = value_str.strip().upper()
    value_str = value_str.replace("µ", "U")  # Handle µF -> uF

    # Match number followed by multiplier
    pattern = r"^([\d.]+)\s*([FPNUM])?F?$"
    match = re.match(pattern, value_str)

    if not match:
        return None

    number, multiplier = match.groups()

    try:
        base_value = float(number)
    except ValueError:
        return None

    # Apply multiplier
    multipliers = {
        "F": 1,
        "M": 1e-3,  # millifarads (rare)
        "U": 1e-6,  # microfarads
        "N": 1e-9,  # nanofarads
        "P": 1e-12,  # picofarads
        None: 1e-6,  # Default to microfarads if no unit
    }

    return base_value * multipliers.get(multiplier, 1e-6)


def parse_voltage(value_str: str) -> float | None:
    """
    Parse voltage value to volts.

    Examples:
        "5V" -> 5.0
        "3.3V" -> 3.3
        "12" -> 12.0
        "50v" -> 50.0

    Returns:
        Voltage in volts, or None if cannot parse.
    """
    if not value_str:
        return None

    value_str = value_str.strip().upper()

    # Match number followed by optional V
    pattern = r"^([\d.]+)\s*V?$"
    match = re.match(pattern, value_str)

    if not match:
        return None

    try:
        return float(match.group(1))
    except ValueError:
        return None


def parse_current(value_str: str) -> float | None:
    """
    Parse current value to amperes.

    Examples:
        "2A" -> 2.0
        "100mA" -> 0.1
        "500ma" -> 0.5
        "1.5" -> 1.5

    Returns:
        Current in amperes, or None if cannot parse.
    """
    if not value_str:
        return None

    value_str = value_str.strip().upper()

    # Match number followed by optional multiplier and A
    pattern = r"^([\d.]+)\s*(M)?A?$"
    match = re.match(pattern, value_str)

    if not match:
        return None

    number, multiplier = match.groups()

    try:
        base_value = float(number)
    except ValueError:
        return None

    # Apply multiplier
    if multiplier == "M":
        return base_value * 1e-3
    return base_value


def parse_power(value_str: str) -> float | None:
    """
    Parse power value to watts.

    Examples:
        "50mW" -> 0.05
        "250mW" -> 0.25
        "1W" -> 1.0

    Returns:
        Power in watts, or None if cannot parse.
    """
    if not value_str:
        return None

    value_str = value_str.strip().upper()

    # Match number followed by optional multiplier and W
    pattern = r"^([\d.]+)\s*(M)?W?$"
    match = re.match(pattern, value_str)

    if not match:
        return None

    number, multiplier = match.groups()

    try:
        base_value = float(number)
    except ValueError:
        return None

    # Apply multiplier
    if multiplier == "M":
        return base_value * 1e-3
    return base_value
