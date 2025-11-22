"""Database management for JLCPCB component catalog."""

import gzip
import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path

import platformdirs
import requests


class DatabaseManager:
    """Manages the local JLCPCB component database."""

    DB_BASE_URL = "https://yaqwsx.github.io/jlcparts/data"
    DB_FILENAME = "components.sqlite"
    INDEX_FILENAME = "index.json"

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
            print("Database corrupted, re-downloading...")
            self._download_database()

        return self.db_path

    def _download_database(self) -> None:
        """Download and build the JLCPCB database from JSON sources."""
        self.data_dir.mkdir(parents=True, exist_ok=True)

        print(f"Building JLCPCB database at {self.data_dir}...")
        print("This may take a few minutes on first run.")

        try:
            # Download index
            print("\nDownloading component index...")
            index_url = f"{self.DB_BASE_URL}/{self.INDEX_FILENAME}"
            response = requests.get(index_url, timeout=30)
            response.raise_for_status()
            index = response.json()

            # Create database
            print("Creating database...")
            self._create_database_schema()

            # Get connection
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Process categories
            categories = index.get("categories", {})
            total_categories = sum(len(subcats) for subcats in categories.values())
            processed = 0

            print(f"\nProcessing {total_categories} categories...")

            for main_cat, subcategories in categories.items():
                for subcat_name, subcat_info in subcategories.items():
                    processed += 1
                    sourcename = subcat_info["sourcename"]

                    print(
                        f"\r[{processed}/{total_categories}] {main_cat} / {subcat_name}...",
                        end="",
                        flush=True,
                    )

                    # Download category JSON (gzipped)
                    cat_url = f"{self.DB_BASE_URL}/{sourcename}.json.gz"
                    try:
                        response = requests.get(cat_url, timeout=30)
                        response.raise_for_status()

                        # Decompress and parse JSON
                        data = json.loads(gzip.decompress(response.content))

                        # Insert components
                        self._insert_components(cursor, data, main_cat, subcat_name)

                    except Exception as e:
                        print(f"\n  Warning: Failed to process {subcat_name}: {e}")
                        continue

            # Commit and close
            conn.commit()
            conn.close()

            print(f"\n\nDatabase ready at {self.db_path}")

            # Save metadata
            with open(self.version_file, "w") as f:
                f.write(f"Downloaded: {datetime.now().isoformat()}\n")
                f.write(f"Source: {self.DB_BASE_URL}\n")
                f.write(f"Categories: {total_categories}\n")

        except Exception as e:
            print(f"\nError building database: {e}")
            # Clean up failed database
            if self.db_path.exists():
                self.db_path.unlink()
            raise

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
        self, cursor: sqlite3.Cursor, data: dict, main_cat: str, subcat: str
    ) -> None:
        """Insert components from a category JSON into the database."""
        components = data.get("components", [])

        for comp in components:
            try:
                # Parse component array
                # [lcsc, mfr_part, stock, ?, datasheet, price_tiers, image, ?, attributes]
                lcsc = comp[0]
                mfr_part = comp[1]
                stock = comp[2]
                datasheet = comp[4] if len(comp) > 4 else None
                price_tiers = comp[5] if len(comp) > 5 else []
                image = comp[6] if len(comp) > 6 else None
                attributes = comp[8] if len(comp) > 8 else {}

                # Extract useful attributes
                basic = 0
                manufacturer = None
                package = None
                description = None

                if isinstance(attributes, dict):
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

                # Insert component
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

                # Insert price tiers
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
