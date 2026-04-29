"""Unit tests for SQL fragments built by `server.search_components`.

These exercise the SQL builders against an in-memory SQLite that mimics the
real schema, so we catch JSON-path regressions without needing to spin up a
FastMCP context or hit the live API.
"""

import json
import sqlite3

import pytest

from jlcpcb_mcp.server import (
    VOLTAGE_RATING_ATTRIBUTE_PATHS,
    _voltage_rating_clause,
)


def _make_components_db() -> sqlite3.Connection:
    """Build a tiny in-memory components table mirroring the real schema."""
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE components (
            lcsc TEXT PRIMARY KEY,
            mfr_part TEXT,
            category TEXT,
            subcategory TEXT,
            description TEXT,
            stock INTEGER,
            datasheet TEXT,
            image TEXT,
            basic INTEGER,
            manufacturer TEXT,
            package TEXT,
            attributes TEXT
        )
    """)
    return conn


def _attr(name: str, value, vkey: str = "default", vtype: str = "string"):
    """LUT-style attribute entry, mirroring what database.py reconstructs."""
    return name, {
        "format": "${default}",
        "primary": vkey,
        "values": {vkey: [value, vtype]},
    }


def _insert_cap(conn, lcsc: str, capacitance_f: float, allowable_voltage: float):
    """Insert a representative capacitor row with the upstream attribute shape."""
    name1, val1 = _attr("Capacitance", capacitance_f, vkey="capacitance", vtype="number")
    name2, val2 = _attr("Allowable voltage", allowable_voltage, vkey="voltage", vtype="number")
    attrs = {name1: val1, name2: val2}
    conn.execute(
        "INSERT INTO components (lcsc, mfr_part, category, subcategory, attributes) "
        "VALUES (?, ?, ?, ?, ?)",
        (lcsc, f"FAKE-{lcsc}", "Capacitors",
         "Multilayer Ceramic Capacitors MLCC - SMD/SMT", json.dumps(attrs)),
    )


class TestVoltageRatingClause:
    """Regression coverage for issue #8."""

    def test_clause_includes_allowable_voltage_path(self):
        """The Allowable voltage path must be in the OR chain — caps depend on it."""
        sql, _params = _voltage_rating_clause(10.0)
        assert '"Allowable voltage".values."voltage"' in sql

    def test_clause_param_count_matches_path_count(self):
        """Each OR'd path needs its own bind parameter."""
        sql, params = _voltage_rating_clause(10.0)
        assert sql.count("?") == len(VOLTAGE_RATING_ATTRIBUTE_PATHS)
        assert params == [10.0] * len(VOLTAGE_RATING_ATTRIBUTE_PATHS)

    def test_capacitor_with_allowable_voltage_matches_filter(self):
        """A 10µF cap rated 10V should match voltage_rating=10V (regression for #8)."""
        conn = _make_components_db()
        _insert_cap(conn, "C5189822", capacitance_f=10e-6, allowable_voltage=10.0)
        _insert_cap(conn, "C18185759", capacitance_f=10e-6, allowable_voltage=25.0)
        conn.commit()

        sql_clause, params = _voltage_rating_clause(10.0)
        rows = conn.execute(
            f"SELECT lcsc FROM components WHERE {sql_clause} ORDER BY lcsc",
            params,
        ).fetchall()

        # Both caps rated >= 10V should match.
        assert [r[0] for r in rows] == ["C18185759", "C5189822"]

    def test_capacitor_below_threshold_excluded(self):
        """A cap rated 6.3V must NOT match voltage_rating=10V."""
        conn = _make_components_db()
        _insert_cap(conn, "C-low", capacitance_f=10e-6, allowable_voltage=6.3)
        _insert_cap(conn, "C-high", capacitance_f=10e-6, allowable_voltage=16.0)
        conn.commit()

        sql_clause, params = _voltage_rating_clause(10.0)
        rows = conn.execute(
            f"SELECT lcsc FROM components WHERE {sql_clause}",
            params,
        ).fetchall()

        assert [r[0] for r in rows] == ["C-high"]

    @pytest.mark.parametrize(
        "name,vkey",
        VOLTAGE_RATING_ATTRIBUTE_PATHS,
    )
    def test_each_configured_path_is_independently_queryable(self, name, vkey):
        """Every configured path should produce a working json_extract expression."""
        conn = _make_components_db()
        attrs = {
            name: {
                "format": "${default}",
                "primary": vkey,
                "values": {vkey: [25.0, "number"]},
            }
        }
        conn.execute(
            "INSERT INTO components (lcsc, attributes) VALUES (?, ?)",
            ("C-test", json.dumps(attrs)),
        )
        conn.commit()

        sql_clause, params = _voltage_rating_clause(10.0)
        rows = conn.execute(
            f"SELECT lcsc FROM components WHERE {sql_clause}", params
        ).fetchall()
        assert rows == [("C-test",)], (
            f"path ({name}, {vkey}) didn't match a row that has it set"
        )
