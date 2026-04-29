"""Database management for JLCPCB component catalog."""

import gzip
import json
import os
import random
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

import platformdirs
import requests

# Schema definition shared by the production builder and tests so they can't
# silently drift apart. Uses CREATE ... IF NOT EXISTS throughout so it is safe
# to run against an existing DB.
COMPONENTS_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS components (
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
);
CREATE INDEX IF NOT EXISTS idx_category ON components(category);
CREATE INDEX IF NOT EXISTS idx_subcategory ON components(subcategory);
CREATE INDEX IF NOT EXISTS idx_mfr_part ON components(mfr_part);
CREATE INDEX IF NOT EXISTS idx_manufacturer ON components(manufacturer);
CREATE INDEX IF NOT EXISTS idx_basic ON components(basic);
CREATE TABLE IF NOT EXISTS prices (
    lcsc TEXT,
    qty_from INTEGER,
    qty_to INTEGER,
    price REAL,
    FOREIGN KEY (lcsc) REFERENCES components(lcsc)
);
CREATE INDEX IF NOT EXISTS idx_prices_lcsc ON prices(lcsc);
"""


class DatabaseManager:
    """Manages the local JLCPCB component database."""

    DB_BASE_URL = "https://yaqwsx.github.io/jlcparts/data"
    DB_FILENAME = "components.sqlite"
    MANIFEST_FILENAME = "manifest.json"
    ATTR_LUT_FILENAME = "attributes-lut.json.gz"
    MANIFEST_VERSION = 2

    # HTTP retry policy for upstream fetches. Connection errors and 5xx responses
    # retry with exponential backoff + jitter; 4xx responses fail fast (404 means
    # the file is gone, not transiently unavailable).
    HTTP_RETRY_ATTEMPTS = 3
    HTTP_BACKOFF_BASE = 0.5
    HTTP_BACKOFF_MAX = 4.0

    def __init__(self):
        """Initialize database manager with appropriate storage location."""
        # Priority 1: Explicit database path
        db_path_env = os.getenv("JLCPCB_DATABASE_PATH")
        if db_path_env:
            db_path = Path(db_path_env)
            # If relative path, resolve from project root
            if not db_path.is_absolute():
                project_root = Path(__file__).parent.parent.parent
                db_path = project_root / db_path
            self.db_path = db_path.resolve()
            self.data_dir = self.db_path.parent
        # Priority 2: Development mode (use project-local data directory)
        elif os.getenv("JLCPCB_DEV_MODE"):
            # Development: use ./data directory in project root
            # Use __file__ to find the package location, then go up to project root
            project_root = Path(__file__).parent.parent.parent
            self.data_dir = project_root / "data"
            self.db_path = self.data_dir / self.DB_FILENAME
        # Priority 3: Default to system config directory
        else:
            self.data_dir = Path(platformdirs.user_data_dir("jlcpcb-mcp", "fastmcp"))
            self.db_path = self.data_dir / self.DB_FILENAME

        self.version_file = self.data_dir / "version.txt"

    def ensure_database(self) -> Path:
        """
        Ensure database exists, download if needed.

        Returns:
            Path to the database file.
        """
        if not self.db_path.exists():
            self._download_database()

        # Verify database is valid
        if not self._verify_database():
            self._log("⚠️  Database corrupted, re-downloading...")
            self._download_database()

        return self.db_path

    def _log(self, message: str, end: str = "\n") -> None:
        """Log to stderr for visibility in MCP clients."""
        print(message, file=sys.stderr, end=end, flush=True)

    def _http_get_with_retry(self, url: str, timeout: int = 30) -> requests.Response:
        """GET ``url`` with exponential backoff on transient failures.

        Retries on connection errors, timeouts, and 5xx responses up to
        ``HTTP_RETRY_ATTEMPTS`` times. 4xx responses raise immediately — those
        are not transient and retrying won't help.
        """
        last_exc: Exception | None = None
        for attempt in range(self.HTTP_RETRY_ATTEMPTS):
            try:
                response = requests.get(url, timeout=timeout)
            except requests.exceptions.RequestException as e:
                last_exc = e
            else:
                if response.status_code < 500:
                    response.raise_for_status()  # raises on 4xx, no-op on 2xx/3xx
                    return response
                last_exc = requests.exceptions.HTTPError(
                    f"HTTP {response.status_code} for {url}"
                )

            if attempt + 1 < self.HTTP_RETRY_ATTEMPTS:
                backoff = min(
                    self.HTTP_BACKOFF_BASE * (2**attempt), self.HTTP_BACKOFF_MAX
                )
                # Jitter ±50% so retried clients don't synchronize against a flaky origin.
                backoff *= 0.5 + random.random()
                self._log(
                    f"\n  ⚠️  Request failed ({last_exc}); "
                    f"retrying in {backoff:.1f}s "
                    f"(attempt {attempt + 2}/{self.HTTP_RETRY_ATTEMPTS})..."
                )
                time.sleep(backoff)

        # The loop only exits without returning when last_exc was set on every
        # iteration; the `or` is belt-and-suspenders for the unreachable case so
        # `python -O` (which strips asserts) can't surface a `raise None` TypeError.
        raise last_exc or RuntimeError("retry loop exited without an exception")

    def _download_database(self) -> None:
        """Download and build the JLCPCB database from upstream manifest + shards.

        Builds into a sibling ``*.tmp`` file and atomically renames on success so
        a *process crash* never leaves a partial DB at the final path — observers
        always see either the previous DB or a fully-built new one.

        Subcategory-level errors (failed shard download, malformed shard header,
        etc.) are still logged and skipped per existing design, so a "successful"
        build can silently omit subcategories that errored. That's a separate
        concern from atomicity and is tracked via the per-subcategory warning
        log lines.
        """
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Build into a temporary path; rename to the final location only on success.
        tmp_path = self.db_path.with_name(self.db_path.name + ".tmp")
        if tmp_path.exists():
            tmp_path.unlink()

        self._log("=" * 70)
        self._log("🔧 FIRST RUN: Building JLCPCB Component Database")
        self._log("=" * 70)
        self._log(f"Location: {self.data_dir}")
        self._log("")
        self._log("This is a ONE-TIME setup that takes 5-10 minutes.")
        self._log("Future searches will be instant!")
        self._log("")

        conn: sqlite3.Connection | None = None
        try:
            # Download manifest
            self._log("📥 Step 1/4: Downloading manifest...")
            manifest_url = f"{self.DB_BASE_URL}/{self.MANIFEST_FILENAME}"
            response = self._http_get_with_retry(manifest_url, timeout=30)
            manifest = response.json()

            manifest_version = manifest.get("version")
            if manifest_version != self.MANIFEST_VERSION:
                self._log(
                    f"⚠️  Manifest version {manifest_version} differs from expected "
                    f"{self.MANIFEST_VERSION}; attempting to proceed."
                )
            self._log(
                f"✓ Manifest downloaded ({len(manifest['categories'])} subcategories, "
                f"{manifest.get('totalComponents', '?')} components)"
            )
            self._log("")

            # Download attributes LUT
            self._log("📥 Step 2/4: Downloading attributes lookup table...")
            lut_filename = manifest.get("attributesLut", self.ATTR_LUT_FILENAME)
            lut_url = f"{self.DB_BASE_URL}/{lut_filename}"
            lut_response = self._http_get_with_retry(lut_url, timeout=60)
            lut = json.loads(gzip.decompress(lut_response.content))
            self._log(f"✓ LUT downloaded ({len(lut)} entries)")
            self._log("")

            # Create schema in the tmp DB
            self._log("🔨 Step 3/4: Creating database schema...")
            self._create_database_schema(tmp_path)
            self._log("✓ Schema created")
            self._log("")

            conn = sqlite3.connect(tmp_path)
            cursor = conn.cursor()

            categories = manifest["categories"]
            total_subcats = len(categories)
            self._log(f"📦 Step 4/4: Downloading and processing {total_subcats} subcategories...")
            self._log("This is the slow part - downloading ~50MB of component data...")
            self._log("")

            for processed, subcat in enumerate(categories, start=1):
                cat_name = subcat["category"]
                subcat_name = subcat["subcategory"]
                shards = subcat.get("shards", [])

                percent = (processed / total_subcats) * 100
                self._log(
                    f"\r[{processed}/{total_subcats}] ({percent:.1f}%) {cat_name} / {subcat_name}...",
                    end="",
                )

                try:
                    for shard_filename in shards:
                        rows, schema = self._fetch_shard(shard_filename)
                        self._insert_components(
                            cursor, rows, schema, lut, cat_name, subcat_name
                        )
                    conn.commit()
                except Exception as e:
                    self._log(f"\n  ⚠️  Warning: Failed to process {subcat_name}: {e}")
                    continue

            conn.close()
            conn = None

            # Atomically swap tmp into place. Any prior DB is replaced wholesale;
            # callers that crashed mid-build never observe a half-built DB.
            tmp_path.replace(self.db_path)

            self._log("\n")
            self._log("=" * 70)
            self._log("✅ Database build complete!")
            self._log(f"📊 Database size: ~{self.db_path.stat().st_size / (1024**2):.0f}MB")
            self._log(f"📍 Location: {self.db_path}")
            self._log("=" * 70)
            self._log("")

            # Save metadata
            with open(self.version_file, "w") as f:
                f.write(f"Downloaded: {datetime.now().isoformat()}\n")
                f.write(f"Source: {self.DB_BASE_URL}\n")
                f.write(f"Manifest version: {manifest_version}\n")
                f.write(f"Subcategories: {total_subcats}\n")
                f.write(f"Total components: {manifest.get('totalComponents', 'unknown')}\n")

        except Exception as e:
            self._log(f"\n❌ Error building database: {e}")
            if tmp_path.exists():
                tmp_path.unlink()
            raise
        finally:
            if conn is not None:
                conn.close()

    def _fetch_shard(self, shard_filename: str) -> tuple[list, dict]:
        """
        Download and parse a single component shard.

        Returns:
            (rows, schema) — rows is a list of positional component arrays;
            schema maps field names ("lcsc", "stock", ...) to their integer index.
        """
        shard_url = f"{self.DB_BASE_URL}/{shard_filename}"
        response = self._http_get_with_retry(shard_url, timeout=60)

        text = gzip.decompress(response.content).decode("utf-8")
        lines = text.splitlines()
        if not lines:
            return [], {}

        schema = json.loads(lines[0])
        rows = [json.loads(line) for line in lines[1:] if line]
        return rows, schema

    def _create_database_schema(self, target_path: Path | None = None) -> None:
        """Create the SQLite database schema at ``target_path`` (defaults to ``self.db_path``)."""
        path = target_path if target_path is not None else self.db_path
        conn = sqlite3.connect(path)
        try:
            conn.executescript(COMPONENTS_SCHEMA_SQL)
        finally:
            conn.close()

    def _insert_components(
        self,
        cursor: sqlite3.Cursor,
        rows: list,
        schema: dict,
        lut: list,
        main_cat: str,
        subcat: str,
    ) -> None:
        """Insert components from one or more shard rows into the database.

        Raises ``KeyError`` if the shard schema header is missing the required
        ``lcsc`` or ``mfr`` fields — caller catches per-subcategory and skips.
        """
        # Resolve schema indices once per shard. lcsc/mfr are required; their
        # absence means the shard header is malformed and we should bail rather
        # than silently misalign positional reads.
        idx_lcsc = schema["lcsc"]
        idx_mfr = schema["mfr"]
        idx_description = schema.get("description")
        idx_datasheet = schema.get("datasheet")
        idx_price = schema.get("price")
        idx_img = schema.get("img")
        idx_attributes = schema.get("attributes")
        idx_stock = schema.get("stock")

        for row in rows:
            try:
                lcsc = row[idx_lcsc]
                mfr_part = row[idx_mfr]
                description = row[idx_description] if idx_description is not None else None
                stock = row[idx_stock] if idx_stock is not None else None
                datasheet = row[idx_datasheet] if idx_datasheet is not None else None
                price_tiers = row[idx_price] if idx_price is not None else []
                image = row[idx_img] if idx_img is not None else None
                attr_ids = row[idx_attributes] if idx_attributes is not None else []

                attributes = self._resolve_attributes(attr_ids, lut)

                basic = 0
                manufacturer = None
                package = None

                # Check if Basic or Extended
                basic_attr = attributes.get("Basic/Extended", {})
                if isinstance(basic_attr, dict):
                    values = basic_attr.get("values", {}).get("default", [])
                    if values and values[0] == "Basic":
                        basic = 1

                # Get manufacturer
                mfr_attr = attributes.get("Manufacturer", {})
                if isinstance(mfr_attr, dict):
                    values = mfr_attr.get("values", {}).get("default", [])
                    if values:
                        manufacturer = values[0]

                # Get package
                pkg_attr = attributes.get("Package", {})
                if isinstance(pkg_attr, dict):
                    values = pkg_attr.get("values", {}).get("default", [])
                    if values:
                        package = values[0]

                cursor.execute(
                    """
                    INSERT OR REPLACE INTO components
                    (lcsc, mfr_part, category, subcategory, description, stock,
                     datasheet, image, basic, manufacturer, package, attributes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        lcsc,
                        mfr_part,
                        main_cat,
                        subcat,
                        description,
                        stock,
                        datasheet,
                        image,
                        basic,
                        manufacturer,
                        package,
                        json.dumps(attributes) if attributes else None,
                    ),
                )

                if isinstance(price_tiers, list):
                    for tier in price_tiers:
                        if isinstance(tier, dict):
                            cursor.execute(
                                """
                                INSERT INTO prices (lcsc, qty_from, qty_to, price)
                                VALUES (?, ?, ?, ?)
                            """,
                                (lcsc, tier.get("qFrom"), tier.get("qTo"), tier.get("price")),
                            )

            except Exception:
                # Skip malformed components
                continue

    @staticmethod
    def _resolve_attributes(attr_ids: list, lut: list) -> dict:
        """Resolve a list of LUT integer IDs into the legacy attributes dict shape."""
        attributes: dict = {}
        if not isinstance(attr_ids, list):
            return attributes
        for aid in attr_ids:
            if not isinstance(aid, int) or aid < 0 or aid >= len(lut):
                continue
            entry = lut[aid]
            if not isinstance(entry, list) or len(entry) < 2:
                continue
            name, value = entry[0], entry[1]
            if isinstance(name, str):
                attributes[name] = value
        return attributes

    def _verify_database(self) -> bool:
        """
        Verify that the database file is valid and can be opened.

        Returns:
            True if database is valid, False otherwise.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Check that expected tables exist
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name IN ('components', 'categories', 'manufacturers')
            """)
            tables = cursor.fetchall()

            conn.close()

            # Should have at least the components table
            return len(tables) >= 1

        except Exception:
            return False

    def update_database(self) -> None:
        """Force update of the database to the latest version."""
        if self.db_path.exists():
            self.db_path.unlink()
        if self.version_file.exists():
            self.version_file.unlink()

        self._download_database()

    def get_connection(self) -> sqlite3.Connection:
        """
        Get a connection to the database.

        Returns:
            SQLite connection with row factory configured.
        """
        self.ensure_database()

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
