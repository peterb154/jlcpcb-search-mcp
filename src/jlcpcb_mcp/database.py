"""Database management for JLCPCB component catalog."""

import gzip
import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import platformdirs
import requests


class DatabaseManager:
    """Manages the local JLCPCB component database."""

    DB_BASE_URL = "https://yaqwsx.github.io/jlcparts/data"
    DB_FILENAME = "components.sqlite"
    MANIFEST_FILENAME = "manifest.json"
    ATTR_LUT_FILENAME = "attributes-lut.json.gz"
    MANIFEST_VERSION = 2

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

    def _download_database(self) -> None:
        """Download and build the JLCPCB database from upstream manifest + shards."""
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self._log("=" * 70)
        self._log("🔧 FIRST RUN: Building JLCPCB Component Database")
        self._log("=" * 70)
        self._log(f"Location: {self.data_dir}")
        self._log("")
        self._log("This is a ONE-TIME setup that takes 5-10 minutes.")
        self._log("Future searches will be instant!")
        self._log("")

        try:
            # Download manifest
            self._log("📥 Step 1/4: Downloading manifest...")
            manifest_url = f"{self.DB_BASE_URL}/{self.MANIFEST_FILENAME}"
            response = requests.get(manifest_url, timeout=30)
            response.raise_for_status()
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
            lut_response = requests.get(lut_url, timeout=60)
            lut_response.raise_for_status()
            lut = json.loads(gzip.decompress(lut_response.content))
            self._log(f"✓ LUT downloaded ({len(lut)} entries)")
            self._log("")

            # Create database
            self._log("🔨 Step 3/4: Creating database schema...")
            self._create_database_schema()
            self._log("✓ Schema created")
            self._log("")

            conn = sqlite3.connect(self.db_path)
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
                    # Commit per subcategory so a mid-build crash leaves a partial-but-valid DB.
                    conn.commit()
                except Exception as e:
                    self._log(f"\n  ⚠️  Warning: Failed to process {subcat_name}: {e}")
                    continue

            conn.close()

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
            if self.db_path.exists():
                self.db_path.unlink()
            raise

    def _fetch_shard(self, shard_filename: str) -> tuple[list, dict]:
        """
        Download and parse a single component shard.

        Returns:
            (rows, schema) — rows is a list of positional component arrays;
            schema maps field names ("lcsc", "stock", ...) to their integer index.
        """
        shard_url = f"{self.DB_BASE_URL}/{shard_filename}"
        response = requests.get(shard_url, timeout=60)
        response.raise_for_status()

        text = gzip.decompress(response.content).decode("utf-8")
        lines = text.splitlines()
        if not lines:
            return [], {}

        schema = json.loads(lines[0])
        rows = [json.loads(line) for line in lines[1:] if line]
        return rows, schema

    def _create_database_schema(self) -> None:
        """Create the SQLite database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Components table
        cursor.execute("""
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
            )
        """)

        # Create indexes for common queries
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_category ON components(category)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_subcategory ON components(subcategory)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_mfr_part ON components(mfr_part)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_manufacturer ON components(manufacturer)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_basic ON components(basic)")

        # Price table (separate for normalization)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS prices (
                lcsc TEXT,
                qty_from INTEGER,
                qty_to INTEGER,
                price REAL,
                FOREIGN KEY (lcsc) REFERENCES components(lcsc)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_prices_lcsc ON prices(lcsc)")

        conn.commit()
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
        """Insert components from one or more shard rows into the database."""
        # Resolve schema indices once per shard.
        idx_lcsc = schema.get("lcsc", 0)
        idx_mfr = schema.get("mfr", 1)
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
