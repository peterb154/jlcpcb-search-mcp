# JLCPCB Search MCP Server

A Model Context Protocol (MCP) server that provides AI assistants with powerful search capabilities for JLCPCB's electronic component catalog. Search 450,000+ components with real-time stock levels and pricing.

[![PyPI version](https://badge.fury.io/py/jlcpcb-search-mcp.svg)](https://pypi.org/project/jlcpcb-search-mcp/)

> Built on top of [yaqwsx/jlcparts](https://github.com/yaqwsx/jlcparts) - huge thanks to Jan Mrázek for doing the hard work of downloading JLCPCB XLS sheets, converting them to structured JSON, and hosting them for the community!

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
- Link: <https://jlcpcb.com/partdetail/C4747968>

### Alternative - C970654 (RVT1C100M0405)

- Rating: 10uF, 16V
- Package: SMD, D4xL5.4mm
- Stock: 7,360 units
- Price: $0.0293 (20+), $0.0202 (600+)
- Link: <https://jlcpcb.com/partdetail/C970654>

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

## Usage Examples

Once configured, you can ask Claude to search for components:

### Basic Search

> "Find me a 10k ohm resistor in 0805 package"

```markdown
## Search Results for '10k resistor'

Found 1 components

### 1. C17724 - 0805W8F510KT5E

- **Type**: **Basic**
- **Manufacturer**: Uniroyal Elec
- **Package**: 0805
- **Category**: Resistors / Chip Resistor - Surface Mount
- **Stock**: 145,230 units
- **Pricing**:
  - 100+: $0.0008
  - 1,000+: $0.0006
  - 5,000+: $0.0005
- **Datasheet**: https://datasheet.lcsc.com/...
- **JLCPCB Link**: https://jlcpcb.com/partdetail/C17724
```

### Detailed Component Info

> "Get full details for component C17976"

Returns complete specifications, all pricing tiers, parameters, datasheet links, and component images.

### Advanced Filtering

> "Find STM32 microcontrollers with at least 1000 units in stock"
>
> "Show me basic ceramic capacitors in 0603 package"

## Database Management

### Check Database Status

```bash
# CLI
jlcpcb-mcp-setup --status

# Or with uv
uv run jlcpcb-mcp-setup --status

# Or from Claude Code
# Ask: "Check the JLCPCB database status"
```

**Example output:**

```text
📊 JLCPCB MCP Database Status
======================================================================

✅ Database found
📍 Location: ~/Library/Application Support/jlcpcb-mcp/components.sqlite
📦 Size: 917.3 MB

📄 Database Metadata:
  Downloaded: 2025-11-22 13:19 (0 days ago)
  Source: https://yaqwsx.github.io/jlcparts/data
  Categories: 1268

======================================================================

💡 To refresh the database: jlcpcb-mcp-setup --refresh-db
```

### Refresh Database

To get the latest components from JLCPCB (takes ~3-10 minutes):

```bash
# From CLI
jlcpcb-mcp-setup --refresh-db

# Or with uv
uv run jlcpcb-mcp-setup --refresh-db

# Or ask Claude directly
# "Refresh the JLCPCB component database"
```

**Example output:**

```text
🔄 Refreshing component database...

📍 Database location: ~/Library/Application Support/jlcpcb-mcp/components.sqlite
✓ Removed old database

======================================================================
🔧 FIRST RUN: Building JLCPCB Component Database
======================================================================
Location: ~/Library/Application Support/jlcpcb-mcp

This is a ONE-TIME setup that takes 5-10 minutes.
Future searches will be instant!

📥 Step 1/3: Downloading component index...
✓ Index downloaded

🔨 Step 2/3: Creating database schema...
✓ Schema created

📦 Step 3/3: Downloading and processing 1268 categories...
[1268/1268] (100.0%) Processing complete...

======================================================================
✅ Database build complete!
📊 Database size: ~917MB
📍 Location: ~/Library/Application Support/jlcpcb-mcp/components.sqlite
======================================================================
```

**When to refresh**: Monthly or when you need newly released components.

**Tip**: You can manage the database directly from Claude! Just ask:

- "Check the JLCPCB database status"
- "Refresh the JLCPCB component database"

## Available MCP Tools

### `search_components`

Search for components by keyword with optional filters.

**Parameters:**

- `query` (string): Search keywords (e.g., "10k resistor", "STM32F4")
- `category` (string, optional): Filter by category
- `package` (string, optional): Filter by package (e.g., "0805", "QFN-32")
- `basic_only` (boolean, optional): Only show Basic parts (default: false)
- `min_stock` (integer, optional): Minimum stock level
- `max_results` (integer): Maximum results to return (default: 10, max: 50)

**Returns:** Formatted list of components with live stock and pricing

### `get_component_details`

Get detailed information for a specific component.

**Parameters:**

- `lcsc` (string): JLCPCB part number (e.g., "C17976")

**Returns:** Comprehensive component details including:

- Full specifications
- Current stock and all pricing tiers
- Datasheet and image links
- Package and manufacturer info
- Category classification

## Development

### Setup Development Environment

```bash
# Clone repository
git clone https://github.com/yourusername/jlcpcb-search-mcp.git
cd jlcpcb-search-mcp

# Install dependencies
pip install -e ".[dev]"

# Enable dev mode (uses ./data directory)
export JLCPCB_DEV_MODE=1
```

### Testing

```bash
# Test database download and queries
JLCPCB_DEV_MODE=1 python test_db.py

# Test MCP server tools
JLCPCB_DEV_MODE=1 python test_server.py
```

### Project Structure

```text
jlcpcb-search-mcp/
   src/
      jlcpcb_mcp/
          __init__.py
          database.py      # Database manager
          server.py         # MCP server and tools
   docs/
      data-sources.md       # Data source documentation
   test_db.py                # Database tests
   test_server.py            # Server tests
   pyproject.toml
   README.md
```

## How It Works

### Hybrid Data Approach

1. **Local Catalog**: SQLite database with component specs, categories, packages
   - Downloaded from [yaqwsx/jlcparts](https://github.com/yaqwsx/jlcparts)
   - Updated weekly/monthly
   - Fast parametric searches

2. **Live API**: Real-time data for critical information
   - Current stock levels
   - Latest pricing tiers
   - Availability status

This hybrid approach provides:

- Fast searches (local SQLite)
- Fresh stock/pricing (JLCPCB API)
- Works offline (with cached data)

### Database Updates

The database can be manually updated:

```python
from jlcpcb_mcp.database import DatabaseManager

db = DatabaseManager()
db.update_database()  # Re-download latest data
```

## Data Sources

- **Component Catalog**: [yaqwsx/jlcparts](https://github.com/yaqwsx/jlcparts) (pre-processed JSON)
- **Live Stock/Pricing**: JLCPCB API (`wmsc.lcsc.com`)
- **Component Specs**: Extracted from JLCPCB's XLS exports

See [docs/data-sources.md](docs/data-sources.md) for detailed information about data sources and backup strategies.

## Basic vs Extended Parts

JLCPCB categorizes components as:

- **Basic Parts**: No additional assembly fees, optimized inventory
- **Extended Parts**: Small additional fee ($0.002-0.005 per component)
- **Preferred Parts**: Extended parts with high inventory

This tool clearly indicates part type in all search results.

## API Rate Limiting

The JLCPCB API has no official rate limits, but best practices:

- Results are enhanced with live data on-demand
- API calls include proper headers (User-Agent, Referer)
- Graceful degradation if API is unavailable
- Future: Optional caching layer (5-15 min TTL)

## Contributing

Contributions welcome! Areas for improvement:

- Add more MCP tools (search by specs, find alternatives, compare components)
- Implement response caching
- Add parametric search by electrical properties
- Support for other component distributors

## License

MIT License - see LICENSE file for details

## Alternative: JLC Parts Web Search

If you just want a better search interface for JLCPCB components (without AI integration), check out **[JLC Parts](https://yaqwsx.github.io/jlcparts/#/)** by Jan Mrázek.

It's an excellent web-based search tool with:

- Fast parametric search
- Advanced filtering
- Component comparisons
- Direct KiCad integration

This MCP server uses their pre-processed component data - huge thanks to Jan and contributors for maintaining that project!

## Related Projects

### KiCad Integration

**[kicad-jlc-manager](https://github.com/peterb154/kicad-jlc-manager)** - Manage JLCPCB components in your KiCad projects

This MCP server pairs perfectly with kicad-jlc-manager for a complete KiCad + JLCPCB workflow:

1. **Search components** using this MCP server with Claude
2. **Add to KiCad project** using kicad-jlc-manager to:
   - Download symbols and footprints
   - Assign LCSC part numbers
   - Generate BOM and CPL files for JLCPCB assembly

Together, these tools provide an AI-powered component search experience integrated directly into your KiCad design workflow.

## Acknowledgments

- **[yaqwsx/jlcparts](https://github.com/yaqwsx/jlcparts)** by Jan Mrázek - Component data source and inspiration
- **[JLC Parts Web Search](https://yaqwsx.github.io/jlcparts/#/)** - If you want a great search UI without AI
- [FastMCP](https://github.com/jlowin/fastmcp) - MCP server framework
- JLCPCB - Component data and API

## Support

- **Issues**: [GitHub Issues](https://github.com/peterb154/jlcpcb-search-mcp/issues)
- **Documentation**: [docs/](docs/)
- **MCP Protocol**: [Model Context Protocol](https://modelcontextprotocol.io/)
