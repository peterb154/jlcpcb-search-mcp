# Testing the JLCPCB MCP Server

This guide explains how to test the MCP server locally with Claude Code.

## Setup

The MCP server configuration is already set up in `.code/mcp.json` for this workspace.

### Prerequisites

1. Ensure the database is built:
   ```bash
   JLCPCB_DEV_MODE=1 python test_db.py
   ```

2. Verify the MCP server starts:
   ```bash
   JLCPCB_DEV_MODE=1 python -m src.jlcpcb_mcp.server
   ```
   You should see the FastMCP banner.

## Testing with Claude Code

### Method 1: Use the MCP Server Directly

1. **Reload Claude Code** to pick up the `.code/mcp.json` configuration
   - In VSCode: Use Command Palette (`Cmd+Shift+P`) → "Developer: Reload Window"

2. **Check MCP Server Status**
   - Look for "jlcpcb-search" in the Claude Code MCP servers list
   - The server should show as connected

3. **Test the Search Tool**
   Ask Claude:
   ```
   Search for 10k resistors in 0805 package using the jlcpcb-search MCP server
   ```

4. **Test Component Details**
   Ask Claude:
   ```
   Get details for JLCPCB component C17976
   ```

### Method 2: Direct Python Testing

Run the test scripts:

```bash
# Test database queries
JLCPCB_DEV_MODE=1 python test_db.py

# Test search and live API
JLCPCB_DEV_MODE=1 python test_server.py
```

## Sample Queries to Test

### Basic Search
- "Find me a 10kΩ resistor in 0805 package"
- "Search for STM32F4 microcontrollers"
- "Show me ceramic capacitors"

### Filtered Search
- "Find Basic parts only for 100nF capacitors"
- "Search for 0603 resistors with at least 1000 units in stock"
- "Find QFN-32 microcontrollers"

### Component Details
- "Get full details for C17976"
- "Show me specifications for component C1337"
- "What's the pricing for C17724"

## Expected Behavior

### `search_components` Tool

**Input:**
```json
{
  "query": "10k resistor",
  "package": "0805",
  "basic_only": true,
  "max_results": 3
}
```

**Output:**
- Markdown-formatted list of components
- Each component shows:
  - JLCPCB part number and MFR part number
  - Basic/Extended classification
  - Package type and manufacturer
  - **Live stock levels** (real-time from API)
  - **Pricing tiers** (real-time from API)
  - Direct link to JLCPCB product page

### `get_component_details` Tool

**Input:**
```json
{
  "lcsc": "C17976"
}
```

**Output:**
- Comprehensive component details including:
  - Full specifications (resistance, power, voltage, etc.)
  - All pricing tiers with quantity breaks
  - Current stock level
  - Datasheet URL
  - Component images
  - Category and package info

## Troubleshooting

### MCP Server Not Showing
- Check that `.code/mcp.json` exists
- Reload VSCode/Claude Code window
- Check Claude Code output panel for errors

### Database Not Found
- Ensure `JLCPCB_DEV_MODE=1` is set
- Run `JLCPCB_DEV_MODE=1 python test_db.py` to build database
- Database should be at `./data/components.sqlite`

### Live API Failing (403 Errors)
- Check internet connection
- API may be rate-limited (rare)
- Server falls back to cached stock/pricing from database

### Import Errors
- Ensure you're in the project directory
- Try: `python -m src.jlcpcb_mcp.server` instead of direct import

## Development Tips

### Watch Server Logs
```bash
JLCPCB_DEV_MODE=1 python -m src.jlcpcb_mcp.server 2>&1 | tee mcp-server.log
```

### Test Individual Functions
```python
import os
os.environ["JLCPCB_DEV_MODE"] = "1"

from src.jlcpcb_mcp.database import DatabaseManager
from src.jlcpcb_mcp.server import LiveAPIClient

# Test database query
db = DatabaseManager()
conn = db.get_connection()
cursor = conn.execute("SELECT * FROM components LIMIT 5")
print(cursor.fetchall())

# Test live API
details = LiveAPIClient.fetch_component_details("C17976")
print(details)
```

### Update Database
```python
from src.jlcpcb_mcp.database import DatabaseManager

db = DatabaseManager()
db.update_database()  # Re-download latest data
```

## MCP Configuration Reference

The `.code/mcp.json` file configures the MCP server:

```json
{
  "mcpServers": {
    "jlcpcb-search": {
      "command": "python",
      "args": ["-m", "src.jlcpcb_mcp.server"],
      "env": {
        "JLCPCB_DEV_MODE": "1"
      }
    }
  }
}
```

- **command**: Python executable
- **args**: Run server as Python module
- **env**: Set dev mode to use `./data` directory

## Success Criteria

✅ Database built successfully (446K+ components)
✅ MCP server starts without errors
✅ Claude Code recognizes the server
✅ Search queries return results with live data
✅ Component details show specifications and pricing
✅ Links to JLCPCB website work correctly

## Next Steps

After successful testing:
1. Update documentation based on findings
2. Consider adding more MCP tools
3. Prepare for PyPI publication
4. Create Docker container (optional)
