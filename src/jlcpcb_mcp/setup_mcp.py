#!/usr/bin/env python3
"""CLI utility to configure JLCPCB MCP server for Claude Code."""

import json
import os
import sys
from pathlib import Path


def create_mcp_config(target_dir: Path, dev_mode: bool = False) -> None:
    """
    Create MCP configuration file.

    Args:
        target_dir: Directory where mcp.json should be created
        dev_mode: Whether to enable development mode
    """
    config = {
        "mcpServers": {
            "jlcpcb-search": {
                "command": "python",
                "args": ["-m", "jlcpcb_mcp.server"],
            }
        }
    }

    # Add dev mode environment variable if requested
    if dev_mode:
        config["mcpServers"]["jlcpcb-search"]["env"] = {"JLCPCB_DEV_MODE": "1"}

    # Create directory if it doesn't exist
    target_dir.mkdir(parents=True, exist_ok=True)

    # Write config file
    config_path = target_dir / "mcp.json"
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

    return config_path


def get_workspace_config_dir() -> Path | None:
    """Get the .code directory for the current workspace."""
    # Try to find .code directory in current or parent directories
    current = Path.cwd()

    # Check current directory and up to 3 levels up
    for _ in range(4):
        code_dir = current / ".code"
        if code_dir.exists() or current == current.parent:
            return code_dir
        current = current.parent

    # If not found, use current directory
    return Path.cwd() / ".code"


def get_global_config_dir() -> Path:
    """Get the global Claude Desktop configuration directory."""
    if sys.platform == "darwin":  # macOS
        return Path.home() / "Library/Application Support/Claude"
    elif sys.platform == "win32":  # Windows
        appdata = os.getenv("APPDATA")
        if appdata:
            return Path(appdata) / "Claude"
        return Path.home() / "AppData/Roaming/Claude"
    else:  # Linux
        return Path.home() / ".config/claude"


def main():
    """Main CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Configure JLCPCB MCP server for Claude Code",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Setup for current workspace (creates .code/mcp.json)
  python -m jlcpcb_mcp.setup_mcp --workspace

  # Setup for current workspace in dev mode
  python -m jlcpcb_mcp.setup_mcp --workspace --dev

  # Setup globally for Claude Desktop
  python -m jlcpcb_mcp.setup_mcp --global

  # Setup in custom directory
  python -m jlcpcb_mcp.setup_mcp --dir /path/to/config

After setup:
  1. Reload your editor window (Cmd+Shift+P → Developer: Reload Window)
  2. Check that 'jlcpcb-search' MCP server is connected
  3. Ask Claude to search for components!
        """,
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--workspace",
        action="store_true",
        help="Create config in workspace .code directory",
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

    # Determine target directory
    if args.workspace:
        target_dir = get_workspace_config_dir()
        config_type = "workspace"
    elif args.global_config:
        target_dir = get_global_config_dir()
        config_type = "global"
    else:
        target_dir = args.dir
        config_type = "custom"

    config_path = target_dir / "mcp.json"

    # Check if config already exists
    if config_path.exists() and not args.force:
        print(f"⚠️  Configuration already exists at: {config_path}")
        print("   Use --force to overwrite")
        sys.exit(1)

    # Create configuration
    try:
        created_path = create_mcp_config(target_dir, dev_mode=args.dev)
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
