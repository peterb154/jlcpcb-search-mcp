# JLCPCB Parts API Research - MCP Server Design

## Executive Summary

After extensive API testing and code review, I found that **JLCPCB has no reliable public search API**. The best approach for an MCP server is a **hybrid solution**: use a local SQLite database for search capabilities, enhanced with live API calls for current stock/pricing.

## Working API Endpoints

### 1. Product Detail API (Primary)
**URL**: `https://wmsc.lcsc.com/ftps/wm/product/detail?productCode={jlc_id}`

**Example**: `https://wmsc.lcsc.com/ftps/wm/product/detail?productCode=C17976`

**Returns**:
```json
{
  "code": 200,
  "result": {
    "productCode": "C17976",
    "productModel": "1206W4F680JT5E",
    "productNameEn": "RES 68Ω ±1% 250mW 1206",
    "productIntroEn": "68Ω 250mW 200V ±200ppm/℃ Thick Film Resistor ±1% 1206 Chip Resistor",
    "stockNumber": 33900,
    "productPriceList": [
      {"ladder": 100, "usdPrice": 0.0037},
      {"ladder": 1000, "usdPrice": 0.0029},
      {"ladder": 5000, "usdPrice": 0.0023}
    ],
    "paramVOList": [
      {"paramNameEn": "Resistance", "paramValueEn": "68Ω"},
      {"paramNameEn": "Power(Watts)", "paramValueEn": "250mW"},
      {"paramNameEn": "Voltage Rating", "paramValueEn": "200V"}
    ],
    "pdfUrl": "https://datasheet.lcsc.com/...",
    "productImages": ["https://assets.lcsc.com/images/..."]
  }
}
```

**Key Data Available**:
- Stock levels (real-time)
- Pricing tiers with quantity breaks
- Full specifications/parameters
- Datasheet URL
- Product images
- Package type
- Manufacturer info

### 2. EasyEDA Component API (For KiCad Integration)
**URL**: `https://easyeda.com/api/products/{jlc_id}/components?version=6.5.50`

**Example**: `https://easyeda.com/api/products/C17976/components`

**Returns**:
```json
{
  "success": true,
  "result": {
    "uuid": "ac1e300179fe684e2e849f504d6bd28f",
    "title": "1206W4F680JT5E",
    "lcsc": {
      "number": "C17976",
      "price": 0.0031,
      "stock": 32859
    },
    "dataStr": {
      "head": {
        "c_para": {
          "name": "1206W4F680JT5E",
          "package": "R1206",
          "Value": "68Ω",
          "JLCPCB Part Class": "Extended Part"
        }
      }
    }
  }
}
```

**Key Data Available**:
- Symbol/footprint UUID for KiCad
- JLCPCB Part Class (Basic/Extended/Preferred)
- Component metadata
- Symbol rendering data

## Non-Working Endpoints

### Failed Search Attempts
❌ `https://wwwapi.lcsc.com/v1/search/global-search?keyword={query}` - Returns empty/404
❌ `https://jlcpcb.com/componentSearch/uploadComponentInfo` - Returns 404
❌ `https://lcsc.com/api/products/search` - Requires CSRF token and cookies

## The Database Solution

### yaqwsx/jlcparts Approach
The [jlcparts project](https://github.com/yaqwsx/jlcparts) solves this by:

1. **Downloading complete catalog** from JLCPCB's XLS export
2. **Converting to SQLite database** (~50MB compressed, ~500MB uncompressed)
3. **Client-side search** using IndexedDB in browser
4. **Parametric filtering** by electrical properties

**Database Schema** (from existing MCP server):
```sql
-- Categories table
CREATE TABLE categories (
  id INTEGER PRIMARY KEY,
  category TEXT,
  subcategory TEXT
);

-- Manufacturers table
CREATE TABLE manufacturers (
  id INTEGER PRIMARY KEY,
  name TEXT
);

-- Components table
CREATE TABLE components (
  lcsc INTEGER PRIMARY KEY,           -- JLCPCB part number (e.g., C17976)
  category_id INTEGER,
  manufacturer_id INTEGER,
  mfr TEXT,                           -- Manufacturer part number
  basic INTEGER,                      -- 1 if Basic part, 0 if Extended
  preferred INTEGER,                  -- 1 if Preferred part
  description TEXT,
  package TEXT,                       -- e.g., "0805", "SOT-23"
  stock INTEGER,
  price TEXT,                         -- JSON array of price tiers
  extra TEXT,                         -- JSON with attributes, images, etc.
  datasheet TEXT
);
```

**Database Source**:
- Download: `https://yaqwsx.github.io/jlcparts/data/cache.zip` (~50MB)
- Updated regularly by jlcparts project
- Contains ALL JLCPCB components with full specs

## Recommended MCP Server Architecture

### Hybrid Approach: Local DB + Live API

```
┌─────────────────────────────────────────────────┐
│  MCP Server                                     │
├─────────────────────────────────────────────────┤
│                                                 │
│  1. Search Layer (SQLite)                       │
│     - Parametric search by specs                │
│     - Filter by category, package, value        │
│     - Sort by Basic/Extended, stock, price      │
│                                                 │
│  2. Enhancement Layer (Live API)                │
│     - Fetch current stock levels                │
│     - Get latest pricing                        │
│     - Update availability status                │
│                                                 │
│  3. Cache Layer (Optional)                      │
│     - Cache API responses (5-15 min TTL)        │
│     - Reduce API load                           │
│                                                 │
└─────────────────────────────────────────────────┘
```

### Example User Flow

**User asks**: "I need a 78.6k SMD resistor for signals"

**MCP Server Process**:
```python
1. Parse intent:
   - Component type: Resistor
   - Value: 78.6kΩ (78600Ω)
   - Package: SMD (surface mount)
   - Application: signals (low power, precision)

2. SQL Query:
   SELECT * FROM components
   WHERE category_id = (SELECT id FROM categories WHERE subcategory LIKE '%Resistor%')
     AND (
       mfr LIKE '%78.6k%' OR
       mfr LIKE '%78k6%' OR
       description LIKE '%78.6k%'
     )
     AND package IN ('0402', '0603', '0805', '1206')  -- Common SMD sizes
   ORDER BY
     basic DESC,           -- Basic parts first
     stock DESC,           -- High stock preferred
     CAST(price AS REAL)   -- Lower price better
   LIMIT 10;

3. Enhance top results with live API:
   FOR EACH result:
     data = fetch_live_details(result.lcsc)
     result.stock = data.stockNumber
     result.current_price = data.productPriceList
     result.datasheet = data.pdfUrl

4. Return formatted recommendations:
   - Component specs
   - Current stock
   - Pricing tiers
   - Basic/Extended status
   - Link to JLCPCB page
```

## Proposed MCP Tools

### 1. `search_components`
Search for components by keyword, specs, or category.

**Parameters**:
- `query` (string): Free-text search
- `category` (string, optional): Filter by category
- `package` (string, optional): Filter by package type
- `basic_only` (boolean, optional): Only show Basic parts
- `min_stock` (integer, optional): Minimum stock level
- `max_results` (integer): Default 10

**Returns**: List of components with specs, stock, pricing

### 2. `get_component_details`
Get detailed information for a specific component.

**Parameters**:
- `jlc_id` (string): JLCPCB part number (e.g., "C17976")

**Returns**: Full component details including:
- Specifications
- Current stock and pricing
- Datasheet link
- Images
- Similar components

### 3. `search_by_specs`
Parametric search by electrical specifications.

**Parameters**:
- `component_type` (string): "resistor", "capacitor", "ic", etc.
- `specs` (object): Key-value pairs of specifications
  - Example: `{"resistance": "10k", "package": "0805", "tolerance": "1%"}`

**Returns**: Matching components sorted by relevance

### 4. `get_alternatives`
Find alternative/similar components for a given part.

**Parameters**:
- `jlc_id` (string): Original part number
- `prioritize_basic` (boolean): Prefer Basic parts

**Returns**: List of similar components with comparison

### 5. `compare_components`
Compare multiple components side-by-side.

**Parameters**:
- `jlc_ids` (array): List of part numbers to compare

**Returns**: Comparison table of specs, pricing, availability

## Implementation Considerations

### Database Management
- **Initial Setup**: Download and extract jlcparts cache.zip
- **Updates**: Re-download weekly/monthly to stay current
- **Size**: ~500MB uncompressed SQLite file
- **Location**: User's config directory or bundled with MCP server

### API Rate Limiting
- **No official limits documented**
- **Best practice**:
  - Cache API responses (5-15 min TTL)
  - Batch requests when possible
  - Add User-Agent header
  - Implement exponential backoff on errors

### Error Handling
- Graceful degradation if API unavailable (use cached data)
- Fallback to database pricing if live API fails
- Clear messaging about data freshness

### Data Freshness Strategy
```
Stock/Price:    Live API (critical for ordering decisions)
Specifications: Database (rarely change)
New components: Database refresh weekly/monthly
```

## Code Examples

### Basic Search Implementation
```python
import sqlite3
import requests
from typing import List, Dict

class JLCPCBSearch:
    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row

    def search_components(self, query: str, limit: int = 10) -> List[Dict]:
        """Search components in local database"""
        cursor = self.conn.execute("""
            SELECT
                lcsc,
                mfr,
                description,
                package,
                basic,
                stock
            FROM components
            WHERE
                mfr LIKE ? OR
                description LIKE ?
            ORDER BY basic DESC, stock DESC
            LIMIT ?
        """, (f'%{query}%', f'%{query}%', limit))

        results = [dict(row) for row in cursor.fetchall()]

        # Enhance with live data
        for result in results:
            live_data = self.fetch_live_details(result['lcsc'])
            if live_data:
                result['current_stock'] = live_data['stockNumber']
                result['current_price'] = live_data['productPriceList']
                result['datasheet'] = live_data.get('pdfUrl')

        return results

    def fetch_live_details(self, jlc_id: str) -> Dict:
        """Fetch current stock/pricing from API"""
        try:
            url = f"https://wmsc.lcsc.com/ftps/wm/product/detail?productCode=C{jlc_id}"
            response = requests.get(url, timeout=10)
            data = response.json()
            return data.get('result', {})
        except:
            return {}
```

### MCP Tool Definition
```python
from fastmcp import FastMCP
from pydantic import BaseModel, Field

mcp = FastMCP('jlcpcb-parts')

class SearchQuery(BaseModel):
    query: str = Field(description="Search keywords (e.g., '10k resistor 0805')")
    category: str | None = Field(default=None, description="Category filter")
    basic_only: bool = Field(default=False, description="Only show Basic parts")
    max_results: int = Field(default=10, ge=1, le=50)

@mcp.tool()
def search_components(search: SearchQuery) -> str:
    """
    Search JLCPCB components by keyword, with live stock and pricing.

    Example: "10k resistor 0805" returns matching resistors with current availability.
    """
    searcher = JLCPCBSearch(DB_PATH)
    results = searcher.search_components(
        query=search.query,
        limit=search.max_results
    )

    # Format as markdown table
    output = "| Part # | Description | Stock | Price (100+) | Type |\n"
    output += "|--------|-------------|-------|--------------|------|\n"

    for r in results:
        part_type = "Basic" if r['basic'] else "Extended"
        price = r['current_price'][0]['usdPrice'] if r.get('current_price') else 'N/A'
        output += f"| C{r['lcsc']} | {r['description'][:50]} | {r['current_stock']} | ${price} | {part_type} |\n"

    return output
```

## Next Steps

1. **Setup new project**:
   ```bash
   mkdir jlcpcb-mcp-server
   cd jlcpcb-mcp-server
   uv init
   ```

2. **Download database**:
   ```bash
   wget https://yaqwsx.github.io/jlcparts/data/cache.zip
   unzip cache.zip
   ```

3. **Install dependencies**:
   ```bash
   uv add fastmcp requests sqlite3
   ```

4. **Implement MCP tools** following the examples above

5. **Test search capabilities** with real queries

6. **Add caching layer** for API responses

## References

- **jlcparts project**: https://github.com/yaqwsx/jlcparts
- **JLC2KiCad**: https://github.com/TousstNicolas/JLC2KiCad_lib
- **kicad-jlc-manager**: ~/Projects/personal/kicad-jlc-manager
- **Existing MCP server**: https://github.com/Adrie-coder/jlcpcb-parts-mcp

## Tested API Endpoints Summary

✅ **Working**:
- `https://wmsc.lcsc.com/ftps/wm/product/detail?productCode={id}` - Full details
- `https://easyeda.com/api/products/{id}/components` - Symbol/footprint data

❌ **Not Working**:
- `https://wwwapi.lcsc.com/v1/search/global-search` - Empty results
- `https://jlcpcb.com/componentSearch/uploadComponentInfo` - 404

📦 **Database**:
- `https://yaqwsx.github.io/jlcparts/data/cache.zip` - Full catalog (~50MB)
