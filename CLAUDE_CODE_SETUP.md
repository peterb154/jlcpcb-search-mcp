# Testing JLCPCB MCP Server with Claude Code

## Quick Start

The MCP server is now ready to test with Claude Code in this workspace!

### 1. Verify Setup

Run the verification script:

```bash
JLCPCB_DEV_MODE=1 python test_mcp_tools.py
```

Expected output:
```
✓ MCP server has 2 tools registered
   - search_components
   - get_component_details
```

### 2. Reload Claude Code

1. Open Command Palette: `Cmd+Shift+P` (Mac) or `Ctrl+Shift+P` (Windows/Linux)
2. Type: `Developer: Reload Window`
3. Press Enter

This loads the MCP configuration from `.code/mcp.json`

### 3. Verify MCP Server Connection

After reloading, check that:
- The "jlcpcb-search" MCP server appears in Claude Code's server list
- Server status shows as "Connected" or "Running"

### 4. Test the Tools

Now you can ask me (Claude) to use the tools! Try these queries:

#### Basic Search
```
Search for 10k resistors in 0805 package using the jlcpcb-search MCP server
```

#### Filtered Search
```
Find STM32 microcontrollers with at least 500 units in stock
```

#### Component Details
```
Get full details for JLCPCB component C17976
```

## Configuration Details

### MCP Server Config (`.code/mcp.json`)

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

**Key Points:**
- **Server name**: `jlcpcb-search`
- **Command**: Runs the server as a Python module
- **Dev mode**: Uses `./data` directory for database (not system-wide)

### Available Tools

#### 1. `search_components`

Search the component catalog with filters.

**Parameters:**
- `query`: Search terms (e.g., "10k resistor", "STM32F4")
- `category`: Optional category filter
- `package`: Optional package filter (e.g., "0805", "QFN-32")
- `basic_only`: Only show Basic parts (default: false)
- `min_stock`: Minimum stock level
- `max_results`: Max results (default: 10, max: 50)

**Returns:** Markdown-formatted component list with:
- JLCPCB part numbers
- **Live stock levels** from API
- **Current pricing** from API
- Package and manufacturer info
- Direct JLCPCB links

#### 2. `get_component_details`

Get comprehensive details for a specific part.

**Parameters:**
- `lcsc`: JLCPCB part number (e.g., "C17976")

**Returns:** Full specifications including:
- All electrical parameters
- Complete pricing tiers
- Real-time stock
- Datasheet URL
- Component images

## Troubleshooting

### MCP Server Not Appearing

**Symptom:** jlcpcb-search server doesn't show in Claude Code

**Solutions:**
1. Check `.code/mcp.json` exists:
   ```bash
   cat .code/mcp.json
   ```

2. Verify server starts manually:
   ```bash
   JLCPCB_DEV_MODE=1 python -m src.jlcpcb_mcp.server
   ```
   Should show FastMCP banner without errors.

3. Check Claude Code output panel for errors

4. Try fully restarting VSCode (not just reload window)

### Database Not Found

**Symptom:** "Database not found" errors

**Solution:** Build the database first:
```bash
JLCPCB_DEV_MODE=1 python test_db.py
```

This downloads ~50MB compressed data and builds ~900MB SQLite database in `./data/`

### Live API Failing

**Symptom:** No pricing/stock data in results

**Possible causes:**
- No internet connection
- JLCPCB API temporarily unavailable
- Rate limiting (rare)

**Note:** Server gracefully falls back to cached database data if API fails

### Import Errors

**Symptom:** "ModuleNotFoundError: No module named 'src.jlcpcb_mcp'"

**Solutions:**
1. Ensure you're in the project root directory
2. Check Python can find the module:
   ```bash
   python -c "from src.jlcpcb_mcp import server; print('OK')"
   ```
3. Install dependencies:
   ```bash
   pip install -e .
   ```

## Example Queries

### Search Examples

**Resistors:**
> "Find me a 10kΩ resistor in 0805 package"
>
> "Search for basic 100Ω resistors with at least 1000 units"

**Capacitors:**
> "Find ceramic capacitors, 100nF, 0603 package"
>
> "Show me basic 10µF capacitors"

**ICs:**
> "Search for STM32F4 microcontrollers"
>
> "Find ATMEGA328P in DIP package"

**With Filters:**
> "Search for 0805 resistors, basic parts only, minimum 5000 units"
>
> "Find QFN-48 microcontrollers with stock over 100"

### Detail Examples

> "Get full details for component C17976"
>
> "Show me specifications and pricing for C1337"
>
> "What's the datasheet for C17724?"

## Behind the Scenes

When you make a request:

1. **Claude parses your query** and determines which tool to use
2. **MCP server receives the request** via stdio transport
3. **Database search executes** (fast SQLite query)
4. **Live API calls enhance results** (real-time stock/pricing)
5. **Formatted response returns** to Claude
6. **Claude presents the results** to you

## Performance Notes

- **Database queries**: < 100ms (local SQLite)
- **API enhancement**: ~200-500ms per component (parallel requests)
- **Total search time**: Usually < 2 seconds for 10 results

## Data Freshness

- **Component specs**: Updated when database refreshes (weekly/monthly)
- **Stock levels**: Real-time from JLCPCB API
- **Pricing**: Real-time from JLCPCB API
- **Availability**: Real-time from JLCPCB API

## Next Steps

After successful testing:

1. **Document any issues** you encounter
2. **Test edge cases** (no results, malformed queries, etc.)
3. **Consider additional tools** (parametric search, alternatives, etc.)
4. **Prepare for PyPI release** if everything works well

## Questions?

If you run into issues:
1. Check [TESTING.md](TESTING.md) for detailed troubleshooting
2. Review server logs in Claude Code output panel
3. Test components individually with test scripts
4. Check GitHub issues for similar problems

Happy testing! 🎉
