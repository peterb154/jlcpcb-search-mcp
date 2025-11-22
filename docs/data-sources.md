# JLCPCB Data Sources

## Current Implementation

We currently use the pre-processed JSON data from the [yaqwsx/jlcparts](https://github.com/yaqwsx/jlcparts) project by Jan Mrázek.

**Important**: This project does the heavy lifting for us:

- Downloads JLCPCB's XLS spreadsheets automatically via CI
- Converts raw XLS data into clean, structured JSON
- Hosts the processed JSON files on GitHub Pages (free, reliable)
- Maintains ~450,000 component records across 1,200+ categories
- Updates regularly to keep data fresh

Without their work, we would need to implement our own XLS scraping, parsing, and hosting infrastructure. Huge thanks to Jan and all contributors!

### How it works:
1. Download `index.json` from `https://yaqwsx.github.io/jlcparts/data/`
2. For each category, download gzipped JSON: `{sourcename}.json.gz`
3. Parse JSON and build local SQLite database
4. Query SQLite for fast local searches
5. Enhance results with live JLCPCB API calls for current stock/pricing

### Advantages:
- **Fast setup**: ~50MB compressed download vs 450MB+ multi-volume ZIP
- **Reliable**: Proven format used by their web app
- **Maintained**: Active project (686 stars, regular updates)
- **Cross-platform**: Pure Python, no shell commands needed

## Alternative: Direct JLCPCB Scraping

If the yaqwsx project becomes unmaintained, we can implement direct scraping.

### How yaqwsx/jlcparts works:

From their [README](https://github.com/yaqwsx/jlcparts?tab=readme-ov-file#how-does-it-work):

1. **Data Source**: JLCPCB publishes an XLS spreadsheet of all components
2. **CI Pipeline**: Travis CI downloads the XLS on a schedule
3. **Processing**: Python script parses XLS and generates JSON files by category
4. **Hosting**: JSON files hosted on GitHub Pages (static, no backend)

### Implementation path for direct scraping:

```python
# Future enhancement: Direct JLCPCB XLS download
class DatabaseManager:
    def update_database(self, source='jlcparts'):
        if source == 'jlcparts':
            # Current: Use yaqwsx JSON (default, fast)
            self._download_from_jlcparts()
        elif source == 'jlcpcb-xls':
            # Future: Direct from JLCPCB XLS (fallback)
            self._download_jlcpcb_xls()
            self._parse_xls_to_sqlite()
```

### Required packages for XLS parsing:
- `openpyxl` or `xlrd` for Excel file parsing
- `pandas` (optional, for easier data manipulation)

### JLCPCB XLS URL:
- Check JLCPCB website for official parts list download
- Likely format: `https://jlcpcb.com/componentSearch/parts-list.xls` (TBD)
- May require authentication or have rate limits

## Data Freshness Strategy

Our hybrid approach keeps data fresh:

1. **Local catalog**: Updated weekly/monthly from yaqwsx JSON
   - Component specs (rarely change)
   - Categories, manufacturers, packages
   - Historical pricing tiers

2. **Live API calls**: Real-time for critical data
   - Current stock levels (via `https://wmsc.lcsc.com/ftps/wm/product/detail?productCode={lcsc}`)
   - Current pricing
   - Availability status

This gives us:
- Fast local searches (SQLite)
- Fresh stock/pricing (API)
- Minimal dependency on yaqwsx updates

## Dependency Risk Mitigation

**Low risk** because:
- MIT licensed (can fork if needed)
- Active community (686 stars, 59 forks)
- Simple hosting (GitHub Pages, highly reliable)
- Multiple contributors (9 people)
- Well-maintained (regular CI runs)

**If project stops:**
- We have 3-6 months before data becomes stale
- Can implement XLS scraper using above approach
- Community would likely fork/maintain
- Live API calls still provide current stock/pricing

## References

- [yaqwsx/jlcparts Repository](https://github.com/yaqwsx/jlcparts)
- [JLCPCB Component Library](https://jlcpcb.com/parts)
- [Live API Documentation](../claude.md) - See "Working API Endpoints" section
