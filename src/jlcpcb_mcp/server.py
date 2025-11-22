"""JLCPCB MCP Server - Search tools for JLCPCB components."""

from typing import Any

import requests
from fastmcp import FastMCP
from pydantic import BaseModel, Field

from .database import DatabaseManager
from .value_parser import (
    parse_capacitance,
    parse_current,
    parse_power,
    parse_resistance,
    parse_voltage,
)

# Initialize FastMCP server
mcp = FastMCP("jlcpcb-search")

# Initialize database manager
db_manager = DatabaseManager()


class LiveAPIClient:
    """Client for fetching live stock and pricing data from JLCPCB."""

    API_BASE_URL = "https://wmsc.lcsc.com/ftps/wm/product/detail"

    @staticmethod
    def fetch_component_details(lcsc: str) -> dict[str, Any] | None:
        """
        Fetch live component details from JLCPCB API.

        Args:
            lcsc: JLCPCB part number (e.g., "C17976")

        Returns:
            Component details dict or None if request fails.
        """
        try:
            url = f"{LiveAPIClient.API_BASE_URL}?productCode={lcsc}"

            # Add headers to mimic browser request
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Accept": "application/json",
                "Referer": "https://jlcpcb.com/",
            }

            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            data = response.json()
            if data.get("code") == 200:
                return data.get("result", {})

            return None

        except Exception as e:
            print(f"Warning: Failed to fetch live data for {lcsc}: {e}")
            return None


class SearchQuery(BaseModel):
    """Parameters for component search."""

    query: str = Field(
        description="Search keywords (e.g., '10k resistor 0805', 'STM32F4', 'capacitor ceramic')"
    )
    category: str | None = Field(
        default=None,
        description="Filter by category (e.g., 'Resistors', 'Capacitors', 'Integrated Circuits')",
    )
    package: str | None = Field(
        default=None, description="Filter by package type (e.g., '0805', 'SOT-23', 'QFN-32')"
    )
    basic_only: bool = Field(
        default=False,
        description="Only show Basic parts (no additional fees for assembly)",
    )
    min_stock: int | None = Field(default=None, description="Minimum stock level required")
    max_results: int = Field(
        default=10, ge=1, le=50, description="Maximum number of results to return"
    )

    # Parametric search fields
    resistance: str | None = Field(
        default=None,
        description="Resistance value (e.g., '10k', '4.7K', '100ohm'). Will be parsed and matched exactly.",
    )
    capacitance: str | None = Field(
        default=None,
        description="Capacitance value (e.g., '10uF', '100nF', '22pF'). Will be parsed and matched exactly.",
    )
    voltage_rating: str | None = Field(
        default=None,
        description="Voltage rating (e.g., '50V', '16V'). For capacitors, this is the rated voltage.",
    )
    input_voltage_min: str | None = Field(
        default=None, description="Minimum input voltage for power ICs (e.g., '5V', '12V')"
    )
    input_voltage_max: str | None = Field(
        default=None, description="Maximum input voltage for power ICs (e.g., '24V', '36V')"
    )
    output_voltage: str | None = Field(
        default=None, description="Output voltage for power converters (e.g., '5V', '3.3V')"
    )
    output_current: str | None = Field(
        default=None, description="Minimum output current capability (e.g., '2A', '500mA')"
    )
    power_rating: str | None = Field(
        default=None, description="Power rating for resistors (e.g., '250mW', '1W')"
    )


class ComponentDetailsQuery(BaseModel):
    """Parameters for getting detailed component information."""

    lcsc: str = Field(description="JLCPCB part number (e.g., 'C17976', 'C1337', 'C2040')")


@mcp.tool()
def search_components(search: SearchQuery) -> str:
    """
    Search JLCPCB components by keyword with live stock and pricing.

    This tool searches the local component database and enhances results
    with real-time stock levels and pricing from JLCPCB's API.

    Examples:
    - "10k resistor 0805" - Find 10kΩ resistors in 0805 package
    - "STM32F4" - Find STM32F4 microcontrollers
    - "capacitor ceramic 10uF" - Find 10µF ceramic capacitors

    Results include:
    - JLCPCB part number and manufacturer part number
    - Current stock levels and pricing tiers
    - Package type and specifications
    - Basic vs Extended part classification
    - Direct link to JLCPCB product page
    """
    # Get database connection
    conn = db_manager.get_connection()

    # Build SQL query
    conditions = []
    params = []

    # Search in multiple fields - split query into terms for better matching
    search_terms = search.query.split()
    if search_terms:
        # Each term should match at least one field
        term_conditions = []
        for term in search_terms:
            search_term = f"%{term}%"
            term_conditions.append(
                "(mfr_part LIKE ? OR category LIKE ? OR subcategory LIKE ? OR manufacturer LIKE ?)"
            )
            params.extend([search_term, search_term, search_term, search_term])

        # All terms must match (AND logic)
        conditions.append("(" + " AND ".join(term_conditions) + ")")

    # Apply filters
    if search.category:
        conditions.append("(category LIKE ? OR subcategory LIKE ?)")
        cat_term = f"%{search.category}%"
        params.extend([cat_term, cat_term])

    if search.package:
        conditions.append("package LIKE ?")
        params.append(f"%{search.package}%")

    if search.basic_only:
        conditions.append("basic = 1")

    if search.min_stock is not None:
        conditions.append("stock >= ?")
        params.append(search.min_stock)

    # Parametric search - resistance
    if search.resistance:
        resistance_ohms = parse_resistance(search.resistance)
        if resistance_ohms:
            # Allow 5% tolerance in matching
            tolerance = 0.05
            min_r = resistance_ohms * (1 - tolerance)
            max_r = resistance_ohms * (1 + tolerance)
            conditions.append(
                "json_extract(attributes, '$.Resistance.values.resistance[0]') BETWEEN ? AND ?"
            )
            params.extend([min_r, max_r])

    # Parametric search - capacitance
    if search.capacitance:
        capacitance_f = parse_capacitance(search.capacitance)
        if capacitance_f:
            # Allow 10% tolerance in matching
            tolerance = 0.10
            min_c = capacitance_f * (1 - tolerance)
            max_c = capacitance_f * (1 + tolerance)
            conditions.append(
                "json_extract(attributes, '$.Capacitance.values.capacitance[0]') BETWEEN ? AND ?"
            )
            params.extend([min_c, max_c])

    # Parametric search - voltage rating
    if search.voltage_rating:
        voltage_v = parse_voltage(search.voltage_rating)
        if voltage_v:
            # Match voltage ratings >= requested (for safety margin)
            conditions.append(
                '(json_extract(attributes, \'$."Voltage Rated".values."voltage rated"[0]\') >= ? OR '
                'json_extract(attributes, \'$."Voltage Rating".values."voltage rating"[0]\') >= ?)'
            )
            params.extend([voltage_v, voltage_v])

    # Parametric search - power rating
    if search.power_rating:
        power_w = parse_power(search.power_rating)
        if power_w:
            # Match power ratings >= requested
            conditions.append("json_extract(attributes, '$.Power.values.power[0]') >= ?")
            params.append(power_w)

    # Parametric search - input voltage range (for power ICs)
    if search.input_voltage_min:
        voltage_v = parse_voltage(search.input_voltage_min)
        if voltage_v:
            # Input voltage range should contain the specified minimum
            conditions.append(
                "attributes LIKE ? AND json_extract(attributes, '$.\"Input voltage\".values.default[0]') LIKE ?"
            )
            params.extend(["%Input voltage%", f"%{voltage_v}V%"])

    # Parametric search - output voltage (for power converters)
    if search.output_voltage:
        voltage_v = parse_voltage(search.output_voltage)
        if voltage_v:
            tolerance = 0.10
            min_v = voltage_v * (1 - tolerance)
            max_v = voltage_v * (1 + tolerance)
            conditions.append(
                "json_extract(attributes, '$.\"Output voltage\".values.voltage[0]') BETWEEN ? AND ?"
            )
            params.extend([min_v, max_v])

    # Parametric search - output current (for power converters)
    if search.output_current:
        current_a = parse_current(search.output_current)
        if current_a:
            # Output current should be >= requested
            conditions.append(
                "(json_extract(attributes, '$.\"Output current (max)\".values.current[0]') >= ? OR "
                "json_extract(attributes, '$.\"Output current (max)\".values.current2[0]') >= ?)"
            )
            params.extend([current_a, current_a])

    # Build final query with intelligent ranking
    where_clause = " AND ".join(conditions)

    # Calculate match score for ranking results
    # Priority: exact value match > Basic parts > high stock > low price
    select_columns = """
        lcsc,
        mfr_part,
        category,
        subcategory,
        manufacturer,
        package,
        basic,
        stock,
        attributes
    """

    # Build scoring expression
    score_parts = []

    # Score 1: Basic parts get priority (10 points)
    score_parts.append("(CASE WHEN basic = 1 THEN 10 ELSE 0 END)")

    # Score 2: Stock level (logarithmic scale, max 5 points)
    score_parts.append("(CASE WHEN stock > 0 THEN MIN(5, LOG10(stock + 1)) ELSE 0 END)")

    # Score 3: Exact value match (if searching by resistance/capacitance)
    if search.resistance:
        resistance_ohms = parse_resistance(search.resistance)
        if resistance_ohms:
            score_parts.append(
                f"(CASE WHEN ABS(json_extract(attributes, '$.Resistance.values.resistance[0]') - {resistance_ohms}) < {resistance_ohms * 0.01} THEN 5 ELSE 0 END)"
            )

    if search.capacitance:
        capacitance_f = parse_capacitance(search.capacitance)
        if capacitance_f:
            score_parts.append(
                f"(CASE WHEN ABS(json_extract(attributes, '$.Capacitance.values.capacitance[0]') - {capacitance_f}) < {capacitance_f * 0.01} THEN 5 ELSE 0 END)"
            )

    # Combine scores
    score_expr = " + ".join(score_parts) if score_parts else "0"

    sql = f"""
        SELECT
            {select_columns},
            ({score_expr}) as match_score
        FROM components
        WHERE {where_clause}
        ORDER BY
            match_score DESC,
            basic DESC,
            stock DESC
        LIMIT ?
    """
    params.append(search.max_results * 2)  # Fetch 2x results for price filtering

    # Execute query
    cursor = conn.execute(sql, params)
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()

    if not results:
        return f"No components found matching '{search.query}'"

    # Enhance with live data
    enhanced_results = []
    for result in results:
        live_data = LiveAPIClient.fetch_component_details(result["lcsc"])

        if live_data:
            # Update with live stock
            result["current_stock"] = live_data.get("stockNumber", result["stock"])

            # Get pricing tiers
            price_list = live_data.get("productPriceList", [])
            if price_list:
                result["pricing"] = [
                    {
                        "qty": tier.get("ladder", 0),
                        "price": tier.get("usdPrice", 0),
                    }
                    for tier in price_list[:3]  # Show first 3 tiers
                ]
            else:
                result["pricing"] = []

            # Get datasheet
            result["datasheet"] = live_data.get("pdfUrl")
        else:
            result["current_stock"] = result["stock"]
            result["pricing"] = []
            result["datasheet"] = None

        enhanced_results.append(result)

    # Final sorting by price (prioritize low cost)
    # Sort by: has pricing > unit price (100+ qty) > match score
    def sort_key(r):
        has_pricing = len(r.get("pricing", [])) > 0
        unit_price = r["pricing"][0]["price"] if has_pricing else 999999
        match_score = r.get("match_score", 0)
        return (-has_pricing, unit_price, -match_score)

    enhanced_results.sort(key=sort_key)

    # Limit to requested max_results
    enhanced_results = enhanced_results[: search.max_results]

    # Format as markdown
    output = f"## Search Results for '{search.query}'\n\n"
    output += f"Found {len(enhanced_results)} components\n\n"

    for i, r in enumerate(enhanced_results, 1):
        part_type = "**Basic**" if r["basic"] else "Extended"
        output += f"### {i}. {r['lcsc']} - {r.get('mfr_part', 'N/A')}\n\n"
        output += f"- **Type**: {part_type}\n"
        output += f"- **Manufacturer**: {r.get('manufacturer', 'N/A')}\n"
        output += f"- **Package**: {r.get('package', 'N/A')}\n"
        output += f"- **Category**: {r['category']} / {r['subcategory']}\n"
        output += f"- **Stock**: {r['current_stock']:,} units\n"

        if r["pricing"]:
            output += "- **Pricing**:\n"
            for tier in r["pricing"]:
                output += f"  - {tier['qty']:,}+: ${tier['price']:.4f}\n"

        if r["datasheet"]:
            output += f"- **Datasheet**: {r['datasheet']}\n"

        output += f"- **JLCPCB Link**: https://jlcpcb.com/partdetail/{r['lcsc']}\n\n"

    return output


@mcp.tool()
def get_component_details(query: ComponentDetailsQuery) -> str:
    """
    Get detailed information for a specific JLCPCB component.

    This tool fetches comprehensive details including specifications,
    current stock, pricing tiers, datasheet, and images.

    Example: lcsc="C17976" returns full details for that specific component.
    """
    # Normalize LCSC number (remove 'C' prefix if present)
    lcsc = query.lcsc.upper()
    if not lcsc.startswith("C"):
        lcsc = f"C{lcsc}"

    # Get from database
    conn = db_manager.get_connection()
    cursor = conn.execute(
        """
        SELECT
            lcsc,
            mfr_part,
            category,
            subcategory,
            manufacturer,
            package,
            basic,
            stock,
            datasheet,
            attributes
        FROM components
        WHERE lcsc = ?
    """,
        (lcsc,),
    )

    result = cursor.fetchone()
    conn.close()

    if not result:
        return f"Component {lcsc} not found in database"

    result = dict(result)

    # Fetch live data
    live_data = LiveAPIClient.fetch_component_details(lcsc)

    output = f"## {lcsc} - {result.get('mfr_part', 'N/A')}\n\n"

    # Basic info
    part_type = "**Basic Part**" if result["basic"] else "**Extended Part**"
    output += f"### {part_type}\n\n"

    output += "### General Information\n\n"
    output += f"- **Manufacturer**: {result.get('manufacturer', 'N/A')}\n"
    output += f"- **Package**: {result.get('package', 'N/A')}\n"
    output += f"- **Category**: {result['category']} / {result['subcategory']}\n\n"

    # Stock and pricing
    if live_data:
        current_stock = live_data.get("stockNumber", result["stock"])
        output += "### Availability\n\n"
        output += f"- **Current Stock**: {current_stock:,} units\n\n"

        price_list = live_data.get("productPriceList", [])
        if price_list:
            output += "### Pricing Tiers\n\n"
            output += "| Quantity | Unit Price (USD) |\n"
            output += "|----------|------------------|\n"
            for tier in price_list:
                qty = tier.get("ladder", 0)
                price = tier.get("usdPrice", 0)
                output += f"| {qty:,}+ | ${price:.4f} |\n"
            output += "\n"

        # Specifications
        params = live_data.get("paramVOList", [])
        if params:
            output += "### Specifications\n\n"
            for param in params:
                name = param.get("paramNameEn", "")
                value = param.get("paramValueEn", "")
                if name and value:
                    output += f"- **{name}**: {value}\n"
            output += "\n"

        # Datasheet and images
        datasheet_url = live_data.get("pdfUrl")
        if datasheet_url:
            output += "### Documentation\n\n"
            output += f"- **Datasheet**: {datasheet_url}\n\n"

        images = live_data.get("productImages", [])
        if images:
            output += "### Images\n\n"
            for img_url in images[:3]:  # Show first 3 images
                output += f"![Component Image]({img_url})\n\n"

    else:
        output += "### Availability\n\n"
        output += f"- **Catalog Stock**: {result['stock']:,} units\n"
        output += "- *Live data unavailable*\n\n"

    output += "### Links\n\n"
    output += f"- **JLCPCB**: https://jlcpcb.com/partdetail/{lcsc}\n"

    if result.get("datasheet"):
        output += f"- **Datasheet**: {result['datasheet']}\n"

    return output


if __name__ == "__main__":
    # Run the MCP server
    mcp.run()
