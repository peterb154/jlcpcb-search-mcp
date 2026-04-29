"""Unit tests for DatabaseManager."""

import gzip
import json
import sqlite3
from unittest.mock import MagicMock, patch

import pytest
import requests

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
    def test_download_database_network_error(self, mock_get, tmp_path, monkeypatch):
        """A persistent network failure propagates and leaves no database behind."""
        # Make retries instant so the test doesn't actually sleep.
        monkeypatch.setattr("jlcpcb_mcp.database.time.sleep", lambda *_: None)
        mock_get.side_effect = requests.exceptions.ConnectionError("Network error")

        manager = DatabaseManager()
        manager.db_path = tmp_path / "components.sqlite"
        manager.data_dir = tmp_path
        manager.version_file = tmp_path / "version.txt"

        with pytest.raises(requests.exceptions.RequestException):
            manager._download_database()

        # Neither the final DB nor the temp scratch file should remain.
        assert not manager.db_path.exists()
        assert not (tmp_path / "components.sqlite.tmp").exists()

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
            resp.status_code = 200
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

        # Tmp scratch file should not be left behind after a successful build.
        assert not (tmp_path / "components.sqlite.tmp").exists()

    def test_download_database_multi_shard_subcategory(self, tmp_path, monkeypatch):
        """A single subcategory split across multiple shards ingests all components."""
        manifest = {
            "version": 2,
            "totalComponents": 2,
            "attributesLut": "attributes-lut.json.gz",
            "categories": [
                {
                    "id": 1,
                    "category": "Resistors",
                    "subcategory": "Chip Resistor",
                    "componentCount": 2,
                    "shards": [
                        "components-resistors__abcd1234-001.jsonl.gz",
                        "components-resistors__abcd1234-002.jsonl.gz",
                    ],
                }
            ],
        }
        lut = [_attr("Basic/Extended", "Basic")]

        def make_shard(lcsc: str) -> bytes:
            lines = [
                json.dumps(SHARD_SCHEMA),
                json.dumps(
                    [lcsc, f"MFR-{lcsc}", 2, "desc", None, [], None, None, [0], 100, 1]
                ),
            ]
            return gzip.compress(("\n".join(lines)).encode("utf-8"))

        shard_a = make_shard("C100")
        shard_b = make_shard("C200")
        lut_bytes = gzip.compress(json.dumps(lut).encode("utf-8"))

        def fake_get(url, timeout=None):
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            resp.status_code = 200
            if url.endswith("/manifest.json"):
                resp.json = MagicMock(return_value=manifest)
            elif url.endswith("/attributes-lut.json.gz"):
                resp.content = lut_bytes
            elif url.endswith("-001.jsonl.gz"):
                resp.content = shard_a
            elif url.endswith("-002.jsonl.gz"):
                resp.content = shard_b
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
        cursor.execute("SELECT lcsc FROM components ORDER BY lcsc")
        assert [row[0] for row in cursor.fetchall()] == ["C100", "C200"]
        conn.close()

    def test_download_database_proceeds_on_unknown_manifest_version(
        self, tmp_path, monkeypatch, capsys
    ):
        """A manifest with an unexpected version logs a warning but still builds."""
        manifest = {
            "version": 99,  # not MANIFEST_VERSION
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
        lut = [_attr("Basic/Extended", "Basic")]
        shard_lines = [
            json.dumps(SHARD_SCHEMA),
            json.dumps(["C1", "M1", 2, "d", None, [], None, None, [0], 1, 1]),
        ]
        shard_bytes = gzip.compress(("\n".join(shard_lines)).encode("utf-8"))
        lut_bytes = gzip.compress(json.dumps(lut).encode("utf-8"))

        def fake_get(url, timeout=None):
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            resp.status_code = 200
            if url.endswith("/manifest.json"):
                resp.json = MagicMock(return_value=manifest)
            elif url.endswith("/attributes-lut.json.gz"):
                resp.content = lut_bytes
            else:
                resp.content = shard_bytes
            return resp

        monkeypatch.setattr("jlcpcb_mcp.database.requests.get", fake_get)

        manager = DatabaseManager()
        manager.db_path = tmp_path / "components.sqlite"
        manager.data_dir = tmp_path
        manager.version_file = tmp_path / "version.txt"

        manager._download_database()

        # Build proceeded.
        conn = sqlite3.connect(manager.db_path)
        assert conn.execute("SELECT COUNT(*) FROM components").fetchone()[0] == 1
        conn.close()

        # Warning was logged to stderr.
        captured = capsys.readouterr()
        assert "Manifest version 99" in captured.err

    def test_insert_components_raises_on_missing_lcsc_in_schema(self, tmp_path):
        """A shard header missing the required `lcsc` field bails immediately."""
        db_path = tmp_path / "components.sqlite"
        manager = DatabaseManager()
        manager.db_path = db_path
        manager.data_dir = tmp_path
        manager._create_database_schema()

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        bad_schema = {"mfr": 0, "stock": 1}  # no "lcsc"
        rows = [["does", "not", "matter"]]

        with pytest.raises(KeyError):
            manager._insert_components(cursor, rows, bad_schema, [], "Cat", "Sub")

        conn.close()

    def test_download_database_skips_subcategory_with_malformed_shard_header(
        self, tmp_path, monkeypatch
    ):
        """A bad shard header skips its subcategory but does not abort the build."""
        monkeypatch.setattr("jlcpcb_mcp.database.time.sleep", lambda *_: None)
        manifest = {
            "version": 2,
            "totalComponents": 1,
            "attributesLut": "attributes-lut.json.gz",
            "categories": [
                {
                    "id": 1,
                    "category": "Good",
                    "subcategory": "Subcat-A",
                    "componentCount": 1,
                    "shards": ["good.jsonl.gz"],
                },
                {
                    "id": 2,
                    "category": "Bad",
                    "subcategory": "Subcat-B",
                    "componentCount": 1,
                    "shards": ["bad.jsonl.gz"],
                },
            ],
        }
        lut = [_attr("Basic/Extended", "Basic")]
        good_shard = gzip.compress(
            (
                json.dumps(SHARD_SCHEMA)
                + "\n"
                + json.dumps(["C1", "M1", 2, "d", None, [], None, None, [0], 1, 1])
            ).encode("utf-8")
        )
        # Header lacks the required `lcsc` field.
        bad_schema = dict(SHARD_SCHEMA)
        bad_schema.pop("lcsc")
        bad_shard = gzip.compress(
            (json.dumps(bad_schema) + "\n" + json.dumps(["x"] * 11)).encode("utf-8")
        )
        lut_bytes = gzip.compress(json.dumps(lut).encode("utf-8"))

        def fake_get(url, timeout=None):
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            resp.status_code = 200
            if url.endswith("/manifest.json"):
                resp.json = MagicMock(return_value=manifest)
            elif url.endswith("/attributes-lut.json.gz"):
                resp.content = lut_bytes
            elif url.endswith("/good.jsonl.gz"):
                resp.content = good_shard
            elif url.endswith("/bad.jsonl.gz"):
                resp.content = bad_shard
            else:
                raise AssertionError(f"unexpected URL {url}")
            return resp

        monkeypatch.setattr("jlcpcb_mcp.database.requests.get", fake_get)

        manager = DatabaseManager()
        manager.db_path = tmp_path / "components.sqlite"
        manager.data_dir = tmp_path
        manager.version_file = tmp_path / "version.txt"

        manager._download_database()

        # Good shard ingested; bad shard skipped silently (per design).
        conn = sqlite3.connect(manager.db_path)
        assert [r[0] for r in conn.execute("SELECT lcsc FROM components")] == ["C1"]
        conn.close()

    def test_download_database_closes_connection_on_failure(
        self, tmp_path, monkeypatch
    ):
        """An exception after the build connection opens still closes it via the finally."""
        monkeypatch.setattr("jlcpcb_mcp.database.time.sleep", lambda *_: None)

        # Manifest contains a malformed category — `subcat["category"]` is accessed
        # outside the inner per-subcategory try, so the KeyError propagates and we
        # rely on the outer try/finally to close the build connection.
        manifest = {
            "version": 2,
            "totalComponents": 0,
            "attributesLut": "attributes-lut.json.gz",
            "categories": [{"id": 1, "componentCount": 0, "shards": []}],  # no "category" key
        }
        lut_bytes = gzip.compress(json.dumps([]).encode("utf-8"))

        def fake_get(url, timeout=None):
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            resp.status_code = 200
            if url.endswith("/manifest.json"):
                resp.json = MagicMock(return_value=manifest)
            elif url.endswith("/attributes-lut.json.gz"):
                resp.content = lut_bytes
            else:
                raise AssertionError(f"unexpected URL {url}")
            return resp

        monkeypatch.setattr("jlcpcb_mcp.database.requests.get", fake_get)

        # Wrap sqlite3.connect so we can observe close() calls. sqlite3.Connection
        # itself doesn't allow attribute assignment, so we use a delegating proxy.
        closed_paths: list[str] = []
        real_connect = sqlite3.connect

        class TrackingConn:
            def __init__(self, real_conn, path):
                object.__setattr__(self, "_real_conn", real_conn)
                object.__setattr__(self, "_path", str(path))

            def close(self):
                closed_paths.append(self._path)
                return self._real_conn.close()

            def __getattr__(self, name):
                return getattr(self._real_conn, name)

        def tracking_connect(path, *args, **kwargs):
            return TrackingConn(real_connect(path, *args, **kwargs), path)

        monkeypatch.setattr("jlcpcb_mcp.database.sqlite3.connect", tracking_connect)

        manager = DatabaseManager()
        manager.db_path = tmp_path / "components.sqlite"
        manager.data_dir = tmp_path
        manager.version_file = tmp_path / "version.txt"

        with pytest.raises(KeyError):
            manager._download_database()

        # The build conn opened on the tmp path must have been closed before cleanup.
        assert any(p.endswith("components.sqlite.tmp") for p in closed_paths)
        # And the tmp file should be gone.
        assert not (tmp_path / "components.sqlite.tmp").exists()

    # ---- HTTP retry/backoff (issue #6) ----

    def test_http_get_with_retry_succeeds_after_transient_5xx(self, monkeypatch):
        """Two 503s followed by a 200 should produce a successful response."""
        sleeps: list[float] = []
        monkeypatch.setattr("jlcpcb_mcp.database.time.sleep", lambda s: sleeps.append(s))

        attempts = []

        def fake_get(url, timeout=None):
            attempts.append(url)
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            if len(attempts) < 3:
                resp.status_code = 503
            else:
                resp.status_code = 200
            return resp

        monkeypatch.setattr("jlcpcb_mcp.database.requests.get", fake_get)

        manager = DatabaseManager()
        result = manager._http_get_with_retry("http://example/foo", timeout=5)

        assert result.status_code == 200
        assert len(attempts) == 3
        assert len(sleeps) == 2  # slept between attempts 1→2 and 2→3, not after 3

    def test_http_get_with_retry_fails_fast_on_4xx(self, monkeypatch):
        """A 404 raises immediately without retrying — it's not transient."""
        sleeps: list[float] = []
        monkeypatch.setattr("jlcpcb_mcp.database.time.sleep", lambda s: sleeps.append(s))

        attempts = []

        def fake_get(url, timeout=None):
            attempts.append(url)
            resp = MagicMock()
            resp.status_code = 404
            resp.raise_for_status = MagicMock(
                side_effect=requests.exceptions.HTTPError("404 Not Found")
            )
            return resp

        monkeypatch.setattr("jlcpcb_mcp.database.requests.get", fake_get)

        manager = DatabaseManager()
        with pytest.raises(requests.exceptions.HTTPError):
            manager._http_get_with_retry("http://example/missing", timeout=5)

        assert len(attempts) == 1
        assert sleeps == []

    def test_http_get_with_retry_exhausts_attempts(self, monkeypatch):
        """Persistent connection errors raise after HTTP_RETRY_ATTEMPTS tries."""
        monkeypatch.setattr("jlcpcb_mcp.database.time.sleep", lambda *_: None)

        attempts = []

        def fake_get(url, timeout=None):
            attempts.append(url)
            raise requests.exceptions.ConnectionError("boom")

        monkeypatch.setattr("jlcpcb_mcp.database.requests.get", fake_get)

        manager = DatabaseManager()
        with pytest.raises(requests.exceptions.ConnectionError):
            manager._http_get_with_retry("http://example/down", timeout=5)

        assert len(attempts) == DatabaseManager.HTTP_RETRY_ATTEMPTS

    def test_http_get_with_retry_fails_fast_on_4xx_after_5xx(self, monkeypatch):
        """A 404 mid-retry-sequence aborts immediately — non-retryable interrupts retry."""
        monkeypatch.setattr("jlcpcb_mcp.database.time.sleep", lambda *_: None)

        attempts = []

        def fake_get(url, timeout=None):
            attempts.append(url)
            resp = MagicMock()
            if len(attempts) == 1:
                resp.status_code = 503
                resp.raise_for_status = MagicMock()
            else:
                resp.status_code = 404
                resp.raise_for_status = MagicMock(
                    side_effect=requests.exceptions.HTTPError("404 Not Found")
                )
            return resp

        monkeypatch.setattr("jlcpcb_mcp.database.requests.get", fake_get)

        manager = DatabaseManager()
        with pytest.raises(requests.exceptions.HTTPError):
            manager._http_get_with_retry("http://example/x", timeout=5)

        # One retry happened (after the 503), then the 404 aborted the loop.
        assert len(attempts) == 2
