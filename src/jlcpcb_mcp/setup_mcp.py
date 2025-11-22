#!/usr/bin/env python3
"""CLI utility to configure JLCPCB MCP server for Claude Code."""

import json
import os
import sys
from pathlib import Path


def create_mcp_config(config_path: Path, dev_mode: bool = False) -> Path:
    """
    Create MCP configuration file.

    Args:
        config_path: Full path to the config file to create
        dev_mode: Whether to enable development mode

    Returns:
        Path to the created config file
    """
    # Use the installed executable script
    config = {
        "mcpServers": {
            "jlcpcb-search": {
                "command": "jlcpcb-mcp",
            }
        }
    }

    # Add dev mode environment variable if requested
    if dev_mode:
        config["mcpServers"]["jlcpcb-search"]["env"] = {"JLCPCB_DEV_MODE": "1"}

    # Create directory if it doesn't exist
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Write config file
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

    return config_path


def get_workspace_config_path() -> Path:
    """Get the .mcp.json path for the current workspace."""
    # Use current working directory as workspace root
    return Path.cwd() / ".mcp.json"


def get_global_config_path() -> Path:
    """Get the global Claude Desktop mcp.json configuration path."""
    if sys.platform == "darwin":  # macOS
        config_dir = Path.home() / "Library/Application Support/Claude"
    elif sys.platform == "win32":  # Windows
        appdata = os.getenv("APPDATA")
        if appdata:
            config_dir = Path(appdata) / "Claude"
        else:
            config_dir = Path.home() / "AppData/Roaming/Claude"
    else:  # Linux
        config_dir = Path.home() / ".config/claude"

    return config_dir / "mcp.json"


def main():
    """Main CLI entry point."""
    import argparse

    # Get version
    try:
        from importlib.metadata import version

        __version__ = version("jlcpcb-search-mcp")
    except Exception:
        __version__ = "unknown"

    parser = argparse.ArgumentParser(
        description="Configure JLCPCB MCP server for Claude Code",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Setup for current workspace (creates .mcp.json)
  jlcpcb-mcp-setup --workspace

  # Setup for current workspace in dev mode
  jlcpcb-mcp-setup --workspace --dev

  # Setup globally for Claude Desktop
  jlcpcb-mcp-setup --global

  # Setup in custom directory
  jlcpcb-mcp-setup --dir /path/to/config

  # Refresh/update the component database
  jlcpcb-mcp-setup --refresh-db

  # Show database status and age
  jlcpcb-mcp-setup --status

After setup:
  1. Reload your editor window (Cmd+Shift+P → Developer: Reload Window)
  2. Check that 'jlcpcb-search' MCP server is connected
  3. Ask Claude to search for components!
        """,
    )

    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--workspace",
        action="store_true",
        help="Create .mcp.json in current workspace directory",
    )
    group.add_argument(
        "--global",
        dest="global_config",
        action="store_true",
        help="Create config in global Claude Desktop directory",
    )
    group.add_argument(
        "--dir",
        type=Path,
        metavar="PATH",
        help="Create config in custom directory",
    )
    group.add_argument(
        "--refresh-db",
        action="store_true",
        help="Refresh/update the component database to get latest parts",
    )
    group.add_argument(
        "--status",
        action="store_true",
        help="Show database status and information",
    )

    parser.add_argument(
        "--dev",
        action="store_true",
        help="Enable development mode (uses ./data directory for database)",
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing configuration",
    )

    args = parser.parse_args()

    # Handle database status
    if args.status:
        try:
            from datetime import datetime

            from .database import DatabaseManager

            db = DatabaseManager()

            print("📊 JLCPCB MCP Database Status")
            print("=" * 70)
            print()

            # Check if database exists
            if not db.db_path.exists():
                print("❌ Database not found")
                print(f"📍 Expected location: {db.db_path}")
                print()
                print("Run 'jlcpcb-mcp-setup --workspace' to set up the database.")
                return

            # Get database info
            print("✅ Database found")
            print(f"📍 Location: {db.db_path}")
            print(f"📦 Size: {db.db_path.stat().st_size / (1024**2):.1f} MB")
            print()

            # Get version info if available
            if db.version_file.exists():
                print("📄 Database Metadata:")
                with open(db.version_file) as f:
                    for line in f:
                        if line.startswith("Downloaded:"):
                            date_str = line.split(":", 1)[1].strip()
                            try:
                                dt = datetime.fromisoformat(date_str)
                                age_days = (datetime.now() - dt).days
                                print(
                                    f"  Downloaded: {dt.strftime('%Y-%m-%d %H:%M')} ({age_days} days ago)"
                                )
                            except Exception:
                                print(f"  {line.strip()}")
                        else:
                            print(f"  {line.strip()}")
            else:
                print("⚠️  No version metadata found")

            print()
            print("=" * 70)
            print()
            print("💡 To refresh the database: jlcpcb-mcp-setup --refresh-db")

        except Exception as e:
            print(f"✗ Error checking database status: {e}", file=sys.stderr)
            sys.exit(1)

        return

    # Handle database refresh
    if args.refresh_db:
        try:
            from .database import DatabaseManager

            print("🔄 Refreshing component database...")
            print()

            db = DatabaseManager()

            # Remove existing database
            if db.db_path.exists():
                print(f"📍 Database location: {db.db_path}")
                db.db_path.unlink()
                print("✓ Removed old database")
                print()

            # Trigger download
            db.ensure_database()

            print()
            print("✅ Database refresh complete!")
            print(f"📊 Database size: ~{db.db_path.stat().st_size / (1024**2):.0f}MB")
            print()
            print("You can now search for the latest JLCPCB components!")

        except Exception as e:
            print(f"✗ Error refreshing database: {e}", file=sys.stderr)
            sys.exit(1)

        return

    # Determine target config path
    if args.workspace:
        config_path = get_workspace_config_path()
        config_type = "workspace"
    elif args.global_config:
        config_path = get_global_config_path()
        config_type = "global"
    else:
        config_path = args.dir / "mcp.json"
        config_type = "custom"

    # Check if config already exists
    if config_path.exists() and not args.force:
        print(f"⚠️  Configuration already exists at: {config_path}")
        print("   Use --force to overwrite")
        sys.exit(1)

    # Create configuration
    try:
        created_path = create_mcp_config(config_path, dev_mode=args.dev)
        print(f"✓ Created {config_type} MCP configuration")
        print(f"  Location: {created_path}")
        print()

        if args.dev:
            print("  Dev mode: ENABLED")
            print("  Database: ./data/components.sqlite")
        else:
            print("  Dev mode: DISABLED")
            if sys.platform == "darwin":
                print("  Database: ~/Library/Application Support/jlcpcb-mcp/")
            elif sys.platform == "win32":
                print("  Database: %LOCALAPPDATA%\\jlcpcb-mcp\\")
            else:
                print("  Database: ~/.local/share/jlcpcb-mcp/")

        print()
        print("Next steps:")
        print("  1. Reload your editor (Cmd+Shift+P → Developer: Reload Window)")
        print("  2. Check MCP server status in Claude Code")
        print("  3. Try: 'Search for 10k resistors using jlcpcb-search'")

    except Exception as e:
        print(f"✗ Error creating configuration: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
