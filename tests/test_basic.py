"""Basic tests for jlcpcb-mcp package."""


def test_import():
    """Test that the package can be imported."""
    import jlcpcb_mcp

    assert jlcpcb_mcp is not None


def test_database_module():
    """Test that the database module can be imported."""
    from jlcpcb_mcp import database

    assert database is not None


def test_server_module():
    """Test that the server module can be imported."""
    from jlcpcb_mcp import server

    assert server is not None


def test_value_parser_module():
    """Test that the value_parser module can be imported."""
    from jlcpcb_mcp import value_parser

    assert value_parser is not None
