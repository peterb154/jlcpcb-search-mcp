# JLCPCB Search MCP Server

A Model Context Protocol (MCP) server that provides AI assistants with powerful search capabilities for JLCPCB's electronic component catalog. Search 450,000+ components with real-time stock levels and pricing.

[![PyPI version](https://badge.fury.io/py/jlcpcb-search-mcp.svg)](https://pypi.org/project/jlcpcb-search-mcp/)

> Built on top of [yaqwsx/jlcparts](https://github.com/yaqwsx/jlcparts) - huge thanks to Jan Mrazek for doing the hard work of downloading JLCPCB XLS sheets, converting them to structured JSON, and hosting them for the community!

## Features

- **Fast Local Search**: SQLite database with 450K+ components for instant searches
- **Live Data**: Real-time stock levels and pricing from JLCPCB API
- **Smart Filtering**: Filter by package type, category, Basic/Extended parts, minimum stock
- **Detailed Information**: Full specifications, datasheets, pricing tiers, and images
- **Easy Integration**: Works with Claude Desktop, VSCode, and any MCP-compatible client

## Example Usage

Ask Claude natural questions about components:

**You:** "Can you find a good 10uF SMD capacitor that can support 10V or less?"

**Claude's Response:**

Based on my search, here are some good 10uF SMD capacitors that can support 10V or less:

**Recommended Options (Aluminum Electrolytic SMD):**

### Best Choice - C4747968 (RST10UF16V013)

- Rating: 10uF, 16V
- Package: SMD, D4xL5.4mm
- Stock: 76,080 units (excellent availability)
- Price: $0.0248 (20+), $0.0170 (600+)
- Link: https://jlcpcb.com/partdetail/C4747968

### Alternative - C970654 (RVT1C100M0405)

- Rating: 10uF, 16V
- Package: SMD, D4xL5.4mm
- Stock: 7,360 units
- Price: $0.0293 (20+), $0.0202 (600+)
- Link: https://jlcpcb.com/partdetail/C970654

All of these are aluminum electrolytic SMD capacitors rated for 16V, which gives you plenty of margin for a 10V application. The C4747968 is my top recommendation due to its excellent stock levels and lower price.

Note: These are all Extended parts (not Basic), so they will incur additional assembly fees if you're using JLCPCB assembly.

## Installation

### From PyPI

```bash
# Install for current user (recommended for Claude Desktop)
pip install --user jlcpcb-search-mcp

# Or use pipx for isolated installation (best for CLI tools)
pipx install jlcpcb-search-mcp

# Or install in a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install jlcpcb-search-mcp

# Or install with uv in a project (uv is my fav!)
uv add jlcpcb-search-mcp
```

### From Source

```bash
git clone https://github.com/peterb154/jlcpcb-search-mcp.git
cd jlcpcb-search-mcp
pip install -e .
```

**Important**: When using Claude Code, the MCP server must be accessible from your project's environment:

- **For uv projects**: Install with `uv add jlcpcb-search-mcp` and use `uv run claude` commands
- **For system-wide use**: Install with `pip install --user jlcpcb-search-mcp` or `pipx install jlcpcb-search-mcp`
- **For venv projects**: Install in your venv and activate it before starting your editor

## Quick Start

### Claude Code Configuration

#### Option 1: Automatic Setup (Recommended)

Use the setup utility to automatically configure the MCP server:

```bash
# For current workspace (creates .mcp.json)
# Uses shared database in user's application data directory - RECOMMENDED
jlcpcb-mcp-setup --workspace

# Or if using uv project
uv run jlcpcb-mcp-setup --workspace

# For development of THIS package only (uses ./data/ directory)
# This creates a separate 900MB+ database in your project - avoid unless needed
jlcpcb-mcp-setup --workspace --dev

# Globally for Claude Desktop (also uses shared database)
jlcpcb-mcp-setup --global
```

After running the setup:

1. Reload your editor window (Cmd+Shift+P → Developer: Reload Window)
2. Check that the MCP server is connected:

   ```bash
   # If using uv project:
   uv run claude mcp list
   ```

   should return something like the following - notice that the mcp server is connected:

   ```text
   Checking MCP server health...

   jlcpcb-search: jlcpcb-mcp  - ✓ Connected
   ```

   ```bash
   # Otherwise if not using uv:
   claude mcp list
   ```

3. You should see: `jlcpcb-search: jlcpcb-mcp - ✓ Connected`
4. Start searching for components!

#### Option 2: Manual Configuration

Create `.mcp.json` in your workspace root:

```json
{
  "mcpServers": {
    "jlcpcb-search": {
      "command": "jlcpcb-mcp"
    }
  }
}
```

Or for global configuration in Claude Desktop:

**macOS**: `~/Library/Application Support/Claude/mcp.json`
**Windows**: `%APPDATA%\Claude\mcp.json`
**Linux**: `~/.config/claude/mcp.json`

**Note for uv projects**: The same simple config works! When you run `uv run claude`, it automatically uses the environment where `jlcpcb-mcp` is installed. No special configuration needed.

### First Run & Database Setup

**The database will be automatically built on your first component search.** However, you can pre-download it to avoid waiting:

```bash
# Pre-download the database (recommended)
jlcpcb-mcp-setup --refresh-db

# Or with uv
uv run jlcpcb-mcp-setup --refresh-db
```

**What to expect:**

- **Download**: ~50MB compressed data (1,268 categories)
- **Final size**: ~917MB SQLite database uncompressed
- **Time**: ~3 minutes on fast internet connection (500Mbps), up to 10 minutes on slower connections
- **Progress**: Real-time updates showing download progress and category processing

If you don't pre-download, **your first Claude query will trigger the download automatically**, so expect a 3-10 minute wait.

#### Database Location

The database is **shared** across all your projects by default (recommended):

- **macOS**: `~/Library/Application Support/jlcpcb-mcp/components.sqlite`
- **Linux**: `~/.local/share/jlcpcb-mcp/components.sqlite`
- **Windows**: `%LOCALAPPDATA%\jlcpcb-mcp\components.sqlite`

**Why shared?**

- One 900MB database serves all your projects
- Saves disk space
- Faster setup for new projects
- Easier to keep updated

**Dev mode (`--dev`)**: Only use this if you're developing the jlcpcb-mcp package itself. It creates a separate database in `./data/` which is useful for testing but wastes space for normal usage.

## License

MIT License - see LICENSE file for details

## Acknowledgments

- **[yaqwsx/jlcparts](https://github.com/yaqwsx/jlcparts)** by Jan Mrazek - Component data source and inspiration
- **[JLC Parts Web Search](https://yaqwsx.github.io/jlcparts/#/)** - If you want a great search UI without AI
- [FastMCP](https://github.com/jlowin/fastmcp) - MCP server framework
- JLCPCB - Component data and API

## Support

- **Issues**: [GitHub Issues](https://github.com/peterb154/jlcpcb-search-mcp/issues)
- **Documentation**: [docs/](docs/)
- **MCP Protocol**: [Model Context Protocol](https://modelcontextprotocol.io/)
