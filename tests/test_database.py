"""Unit tests for DatabaseManager."""

import gzip
import json
import sqlite3
from unittest.mock import MagicMock, patch

import pytest

from jlcpcb_mcp.database import DatabaseManager

# Reusable shard schema header — line 1 of every upstream JSONL shard.
SHARD_SCHEMA = {
    "lcsc": 0,
    "mfr": 1,
    "joints": 2,
    "description": 3,
    "datasheet": 4,
    "price": 5,
    "img": 6,
    "url": 7,
    "attributes": 8,
    "stock": 9,
    "subcategory": 10,
}


def _attr(name: str, value: str) -> list:
    """Build a single LUT entry in the upstream shape."""
    return [
        name,
        {
            "format": "${default}",
            "primary": "default",
            "values": {"default": [value, "string"]},
        },
    ]


class TestDatabaseManager:
    """Test DatabaseManager class."""

    def test_init_with_env_path(self, monkeypatch, tmp_path):
        """Test initialization with JLCPCB_DATABASE_PATH environment variable."""
        db_path = tmp_path / "custom.sqlite"
        monkeypatch.setenv("JLCPCB_DATABASE_PATH", str(db_path))

        manager = DatabaseManager()

        assert manager.db_path == db_path
        assert manager.data_dir == tmp_path

    def test_init_with_dev_mode(self, monkeypatch, tmp_path):
        """Test initialization in development mode."""
        monkeypatch.setenv("JLCPCB_DEV_MODE", "1")
        monkeypatch.delenv("JLCPCB_DATABASE_PATH", raising=False)

        manager = DatabaseManager()

        # In dev mode, should use ./data relative to project root
        assert manager.db_path.name == "components.sqlite"
        assert "data" in str(manager.db_path)

    def test_init_default_mode(self, monkeypatch):
        """Test initialization in default mode (no env vars)."""
        monkeypatch.delenv("JLCPCB_DATABASE_PATH", raising=False)
        monkeypatch.delenv("JLCPCB_DEV_MODE", raising=False)

        manager = DatabaseManager()

        # Should use platformdirs location
        assert manager.db_path.name == "components.sqlite"
        assert "jlcpcb-mcp" in str(manager.db_path)

    def test_verify_database_valid(self, tmp_path):
        """Test database verification with valid database."""
        db_path = tmp_path / "components.sqlite"

        # Create valid database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE components (lcsc TEXT PRIMARY KEY)")
        conn.commit()
        conn.close()

        # Create manager with this path
        manager = DatabaseManager()
        manager.db_path = db_path

        assert manager._verify_database() is True

    def test_verify_database_missing_tables(self, tmp_path):
        """Test database verification with missing tables."""
        db_path = tmp_path / "components.sqlite"

        # Create database without required tables
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE wrong_table (id INTEGER)")
        conn.commit()
        conn.close()

        manager = DatabaseManager()
        manager.db_path = db_path

        assert manager._verify_database() is False

    def test_verify_database_corrupted(self, tmp_path):
        """Test database verification with corrupted file."""
        db_path = tmp_path / "components.sqlite"

        # Create corrupted database file
        with open(db_path, "w") as f:
            f.write("This is not a valid SQLite database")

        manager = DatabaseManager()
        manager.db_path = db_path

        assert manager._verify_database() is False

    def test_verify_database_nonexistent(self, tmp_path):
        """Test database verification with nonexistent file."""
        db_path = tmp_path / "nonexistent.sqlite"

        manager = DatabaseManager()
        manager.db_path = db_path

        # Should handle gracefully
        result = manager._verify_database()
        assert result is False

    def test_create_database_schema(self, tmp_path):
        """Test database schema creation."""
        db_path = tmp_path / "components.sqlite"

        manager = DatabaseManager()
        manager.db_path = db_path
        manager.data_dir = tmp_path
        manager._create_database_schema()

        # Verify tables exist
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [row[0] for row in cursor.fetchall()]

        assert "components" in tables
        assert "prices" in tables

        # Verify components table schema
        cursor.execute("PRAGMA table_info(components)")
        columns = {row[1] for row in cursor.fetchall()}

        expected_columns = {
            "lcsc",
            "mfr_part",
            "category",
            "subcategory",
            "description",
            "stock",
            "datasheet",
            "image",
            "basic",
            "manufacturer",
            "package",
            "attributes",
        }
        assert expected_columns.issubset(columns)

        # Verify indexes exist
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='components'"
        )
        indexes = [row[0] for row in cursor.fetchall()]

        assert any("idx_category" in idx for idx in indexes)
        assert any("idx_mfr_part" in idx for idx in indexes)
        assert any("idx_basic" in idx for idx in indexes)

        conn.close()

    def test_insert_components_basic_part(self, tmp_path):
        """Test inserting a basic part."""
        db_path = tmp_path / "components.sqlite"

        manager = DatabaseManager()
        manager.db_path = db_path
        manager.data_dir = tmp_path
        manager._create_database_schema()

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        lut = [
            _attr("Basic/Extended", "Basic"),
            _attr("Manufacturer", "Uniroyal Elec"),
            _attr("Package", "1206"),
        ]
        rows = [
            [
                "C17976",  # lcsc
                "1206W4F680JT5E",  # mfr
                2,  # joints
                "68Ω 250mW 1206 Chip Resistor",  # description
                "https://datasheet.lcsc.com/test.pdf",  # datasheet
                [  # price tiers
                    {"qFrom": 1, "qTo": 99, "price": 0.005},
                    {"qFrom": 100, "qTo": 999, "price": 0.0037},
                ],
                "https://assets.lcsc.com/image.jpg",  # img
                "products/C17976",  # url
                [0, 1, 2],  # attribute LUT ids
                33900,  # stock
                1,  # subcategory id
            ]
        ]

        manager._insert_components(
            cursor, rows, SHARD_SCHEMA, lut, "Resistors", "Chip Resistor"
        )
        conn.commit()

        cursor.execute("SELECT * FROM components WHERE lcsc = ?", ("C17976",))
        row = cursor.fetchone()

        assert row is not None
        assert row[0] == "C17976"  # lcsc
        assert row[1] == "1206W4F680JT5E"  # mfr_part
        assert row[2] == "Resistors"  # category
        assert row[3] == "Chip Resistor"  # subcategory
        assert row[4] == "68Ω 250mW 1206 Chip Resistor"  # description (now populated)
        assert row[5] == 33900  # stock
        assert row[8] == 1  # basic flag
        assert row[9] == "Uniroyal Elec"  # manufacturer
        assert row[10] == "1206"  # package

        cursor.execute("SELECT * FROM prices WHERE lcsc = ?", ("C17976",))
        prices = cursor.fetchall()
        assert len(prices) == 2
        assert prices[0][1] == 1  # qty_from
        assert prices[0][3] == 0.005  # price

        conn.close()

    def test_insert_components_extended_part(self, tmp_path):
        """Test inserting an extended part."""
        db_path = tmp_path / "components.sqlite"

        manager = DatabaseManager()
        manager.db_path = db_path
        manager.data_dir = tmp_path
        manager._create_database_schema()

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        lut = [_attr("Basic/Extended", "Extended")]
        rows = [
            [
                "C123456",
                "TEST123",
                3,
                "Test MCU",
                None,
                [],
                None,
                None,
                [0],
                1000,
                42,
            ]
        ]

        manager._insert_components(cursor, rows, SHARD_SCHEMA, lut, "ICs", "MCU")
        conn.commit()

        cursor.execute("SELECT basic FROM components WHERE lcsc = ?", ("C123456",))
        row = cursor.fetchone()

        assert row is not None
        assert row[0] == 0  # Extended parts have basic = 0

        conn.close()

    def test_insert_components_malformed(self, tmp_path):
        """Test that malformed components are skipped gracefully."""
        db_path = tmp_path / "components.sqlite"

        manager = DatabaseManager()
        manager.db_path = db_path
        manager.data_dir = tmp_path
        manager._create_database_schema()

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        rows = [
            ["C123"],  # Too few fields — IndexError on access
            None,  # Invalid type — TypeError on subscript
            [],  # Empty array — IndexError on access
        ]

        # Should not raise
        manager._insert_components(cursor, rows, SHARD_SCHEMA, [], "Test", "Test")
        conn.commit()

        cursor.execute("SELECT COUNT(*) FROM components")
        count = cursor.fetchone()[0]
        assert count == 0

        conn.close()

    def test_get_connection(self, tmp_path):
        """Test getting a database connection."""
        db_path = tmp_path / "components.sqlite"

        manager = DatabaseManager()
        manager.db_path = db_path
        manager.data_dir = tmp_path

        # Create database first
        manager._create_database_schema()

        # Get connection
        conn = manager.get_connection()

        # Should return valid connection with row factory
        assert isinstance(conn, sqlite3.Connection)
        assert conn.row_factory == sqlite3.Row

        # Test that row factory works
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO components (lcsc, mfr_part) VALUES (?, ?)",
            ("C123", "TEST"),
        )
        conn.commit()

        cursor.execute("SELECT * FROM components WHERE lcsc = ?", ("C123",))
        row = cursor.fetchone()

        # Can access by column name
        assert row["lcsc"] == "C123"
        assert row["mfr_part"] == "TEST"

        conn.close()

    def test_update_database(self, tmp_path, monkeypatch):
        """Test force updating the database."""
        db_path = tmp_path / "components.sqlite"
        version_file = tmp_path / "version.txt"

        manager = DatabaseManager()
        manager.db_path = db_path
        manager.data_dir = tmp_path
        manager.version_file = version_file

        # Create existing database and version file
        manager._create_database_schema()
        with open(version_file, "w") as f:
            f.write("Old version\n")

        assert db_path.exists()
        assert version_file.exists()

        # Mock the download to avoid actual network call
        with patch.object(manager, "_download_database"):
            manager.update_database()

        # Should have deleted old files
        assert not version_file.exists()

    @patch("jlcpcb_mcp.database.requests.get")
    def test_download_database_network_error(self, mock_get, tmp_path):
        """Test handling of network errors during download."""
        mock_get.side_effect = Exception("Network error")

        manager = DatabaseManager()
        manager.db_path = tmp_path / "components.sqlite"
        manager.data_dir = tmp_path
        manager.version_file = tmp_path / "version.txt"

        with pytest.raises(Exception):
            manager._download_database()

        # Database should be cleaned up on error
        assert not manager.db_path.exists()

    def test_insert_components_with_attributes_json(self, tmp_path):
        """Test that attributes are reconstructed from the LUT and stored as JSON."""
        db_path = tmp_path / "components.sqlite"

        manager = DatabaseManager()
        manager.db_path = db_path
        manager.data_dir = tmp_path
        manager._create_database_schema()

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # LUT entries preserve nested value-dict shape, including non-default keys
        # (e.g. "resistance") that server.py's json_extract relies on.
        lut = [
            ["Resistance", {"values": {"resistance": [10000, "number"]}}],
            ["Tolerance", {"values": {"default": ["±1%", "string"]}}],
        ]
        rows = [
            [
                "C17976",
                "TEST",
                2,
                "10kΩ ±1%",
                None,
                [],
                None,
                None,
                [0, 1],
                1000,
                1,
            ]
        ]

        manager._insert_components(cursor, rows, SHARD_SCHEMA, lut, "Test", "Test")
        conn.commit()

        cursor.execute("SELECT attributes FROM components WHERE lcsc = ?", ("C17976",))
        row = cursor.fetchone()

        stored_attributes = json.loads(row[0])
        assert stored_attributes["Resistance"]["values"]["resistance"][0] == 10000
        assert stored_attributes["Tolerance"]["values"]["default"][0] == "±1%"

        conn.close()

    def test_resolve_attributes_skips_invalid_ids(self):
        """Out-of-range and non-int IDs should be silently dropped, not raise."""
        lut = [["Package", {"values": {"default": ["0805", "string"]}}]]

        result = DatabaseManager._resolve_attributes(
            [0, 999, -1, "not-an-int", None], lut
        )

        assert "Package" in result
        assert len(result) == 1

    def test_download_database_parses_manifest_and_shards(self, tmp_path, monkeypatch):
        """End-to-end test of the new manifest+LUT+shard ingest pipeline (mocked HTTP)."""
        manifest = {
            "version": 2,
            "totalComponents": 1,
            "attributesLut": "attributes-lut.json.gz",
            "categories": [
                {
                    "id": 1,
                    "category": "Resistors",
                    "subcategory": "Chip Resistor",
                    "componentCount": 1,
                    "shards": ["components-resistors__abcd1234-001.jsonl.gz"],
                }
            ],
        }

        lut = [
            _attr("Basic/Extended", "Basic"),
            _attr("Manufacturer", "Uniroyal Elec"),
            _attr("Package", "1206"),
        ]

        shard_lines = [
            json.dumps(SHARD_SCHEMA),
            json.dumps(
                [
                    "C17976",
                    "1206W4F680JT5E",
                    2,
                    "68Ω 1206",
                    "http://example/ds.pdf",
                    [{"qFrom": 1, "qTo": 99, "price": 0.005}],
                    "http://example/img.jpg",
                    "products/C17976",
                    [0, 1, 2],
                    33900,
                    1,
                ]
            ),
        ]
        shard_bytes = gzip.compress(("\n".join(shard_lines)).encode("utf-8"))
        lut_bytes = gzip.compress(json.dumps(lut).encode("utf-8"))

        def fake_get(url, timeout=None):
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            if url.endswith("/manifest.json"):
                resp.json = MagicMock(return_value=manifest)
            elif url.endswith("/attributes-lut.json.gz"):
                resp.content = lut_bytes
            elif url.endswith("/components-resistors__abcd1234-001.jsonl.gz"):
                resp.content = shard_bytes
            else:
                raise AssertionError(f"unexpected URL {url}")
            return resp

        monkeypatch.setattr("jlcpcb_mcp.database.requests.get", fake_get)

        manager = DatabaseManager()
        manager.db_path = tmp_path / "components.sqlite"
        manager.data_dir = tmp_path
        manager.version_file = tmp_path / "version.txt"

        manager._download_database()

        conn = sqlite3.connect(manager.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT lcsc, mfr_part, category, subcategory, description, stock, "
            "basic, manufacturer, package FROM components"
        )
        rows = cursor.fetchall()
        assert rows == [
            (
                "C17976",
                "1206W4F680JT5E",
                "Resistors",
                "Chip Resistor",
                "68Ω 1206",
                33900,
                1,
                "Uniroyal Elec",
                "1206",
            )
        ]

        cursor.execute("SELECT qty_from, qty_to, price FROM prices WHERE lcsc=?", ("C17976",))
        assert cursor.fetchall() == [(1, 99, 0.005)]
        conn.close()

        # Version metadata should record the manifest version.
        assert "Manifest version: 2" in manager.version_file.read_text()
