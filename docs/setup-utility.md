# MCP Setup Utility

The `jlcpcb-mcp-setup` command-line utility helps you quickly configure the JLCPCB MCP server for Claude Code or Claude Desktop.

## Installation

After installing the package:

```bash
pip install jlcpcb-mcp
```

The `jlcpcb-mcp-setup` command will be available in your PATH.

## Usage

### Workspace Setup (Claude Code)

Create configuration for the current workspace:

```bash
# Basic workspace setup
jlcpcb-mcp-setup --workspace

# With development mode (uses ./data for database)
jlcpcb-mcp-setup --workspace --dev
```

This creates `.code/mcp.json` in your workspace root.

### Global Setup (Claude Desktop)

Create configuration for Claude Desktop globally:

```bash
jlcpcb-mcp-setup --global
```

This creates/updates:
- **macOS**: `~/Library/Application Support/Claude/mcp.json`
- **Windows**: `%APPDATA%\Claude\mcp.json`
- **Linux**: `~/.config/claude/mcp.json`

### Custom Directory

Create configuration in a specific directory:

```bash
jlcpcb-mcp-setup --dir /path/to/config
```

## Options

### `--workspace`

Create configuration in workspace `.code` directory. The utility searches for an existing `.code` directory in the current directory or up to 3 levels up. If not found, creates `.code` in the current directory.

**Use case**: Per-project MCP configuration in Claude Code

### `--global`

Create configuration in the global Claude Desktop config directory.

**Use case**: System-wide MCP server available in all Claude Desktop conversations

### `--dir PATH`

Create configuration in a custom directory.

**Use case**: Non-standard installation paths or testing

### `--dev`

Enable development mode. Adds `JLCPCB_DEV_MODE=1` environment variable.

**Effect**:
- Database stored in `./data/components.sqlite` (relative to current directory)
- Useful for development/testing without affecting system-wide database

**Without `--dev`** (production mode):
- **macOS**: `~/Library/Application Support/jlcpcb-mcp/`
- **Windows**: `%LOCALAPPDATA%\jlcpcb-mcp\`
- **Linux**: `~/.local/share/jlcpcb-mcp/`

### `--force`

Overwrite existing configuration file.

**Use case**: Update existing configuration or fix broken config

## Examples

### Development Setup

Setting up for local development:

```bash
cd my-project
jlcpcb-mcp-setup --workspace --dev
```

Creates `.code/mcp.json`:
```json
{
  "mcpServers": {
    "jlcpcb-search": {
      "command": "python",
      "args": ["-m", "jlcpcb_mcp.server"],
      "env": {
        "JLCPCB_DEV_MODE": "1"
      }
    }
  }
}
```

### Production Setup

Setting up for production use:

```bash
jlcpcb-mcp-setup --global
```

Creates global config without dev mode, using system directories for data.

### Multiple Projects

Each project can have its own configuration:

```bash
# Project A - development database
cd ~/projects/project-a
jlcpcb-mcp-setup --workspace --dev

# Project B - shared system database
cd ~/projects/project-b
jlcpcb-mcp-setup --workspace
```

### Update Existing Config

Update an existing configuration:

```bash
jlcpcb-mcp-setup --workspace --dev --force
```

## After Setup

1. **Reload Editor**
   - VSCode/Claude Code: `Cmd+Shift+P` → "Developer: Reload Window"
   - Claude Desktop: Restart application

2. **Verify Connection**
   - Check that "jlcpcb-search" appears in MCP servers list
   - Status should show "Connected" or "Running"

3. **Test the Server**
   ```
   Search for 10k resistors using the jlcpcb-search server
   ```

## Troubleshooting

### Configuration Already Exists

**Error**: `⚠️  Configuration already exists`

**Solution**: Use `--force` to overwrite:
```bash
jlcpcb-mcp-setup --workspace --force
```

### Command Not Found

**Error**: `jlcpcb-mcp-setup: command not found`

**Solution**: Use module invocation instead:
```bash
python -m jlcpcb_mcp.setup_mcp --workspace
```

Or ensure the package is installed:
```bash
pip install -e .  # From project root
```

### Permission Denied

**Error**: Permission denied writing to config directory

**Solution**:
- Check directory permissions
- Try workspace mode instead of global: `--workspace`
- Use `--dir` with a writable path

### Server Not Appearing

After running setup, server doesn't appear in Claude Code.

**Solutions**:
1. Verify config file was created:
   ```bash
   cat .code/mcp.json  # or appropriate path
   ```

2. Check server starts manually:
   ```bash
   python -m jlcpcb_mcp.server
   ```

3. Fully restart editor/application (not just reload)

4. Check output panel for MCP connection errors

## Configuration Structure

The utility generates this configuration:

```json
{
  "mcpServers": {
    "jlcpcb-search": {
      "command": "python",
      "args": ["-m", "jlcpcb_mcp.server"],
      "env": {
        "JLCPCB_DEV_MODE": "1"  // Only if --dev flag used
      }
    }
  }
}
```

### Key Elements

- **Server name**: `jlcpcb-search` - identifier for this MCP server
- **Command**: `python` - runs Python interpreter
- **Args**: `["-m", "jlcpcb_mcp.server"]` - runs server as Python module
- **Env** (optional): Environment variables passed to server process

## Development vs Production

### Development Mode (`--dev`)

**Advantages**:
- Isolated database per project
- Won't affect system-wide installation
- Easy to delete/rebuild database
- Fast iteration during development

**Disadvantages**:
- Separate database download per project (~900MB)
- Database updates don't sync between projects

### Production Mode (no `--dev`)

**Advantages**:
- Single shared database for all projects
- One-time download and maintenance
- Consistent data across all uses

**Disadvantages**:
- Shared state between projects
- Database updates affect all projects

## Best Practices

1. **Use `--workspace --dev` for development**
   - Keeps test data separate from production
   - Easy cleanup

2. **Use `--global` for production/daily use**
   - Shared database saves disk space
   - Consistent across all Claude conversations

3. **Add `.code/` to `.gitignore`**
   - Workspace configs are user-specific
   - Already included in template `.gitignore`

4. **Document your choice**
   - Add setup instructions to project README
   - Specify which mode teammates should use

## See Also

- [README.md](../README.md) - Main documentation
- [CLAUDE_CODE_SETUP.md](../CLAUDE_CODE_SETUP.md) - Testing guide
- [TESTING.md](../TESTING.md) - Troubleshooting
