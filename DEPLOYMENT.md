# Deployment Guide

This document explains the GitHub Actions CI/CD setup for automated publishing to PyPI.

## Overview

The project uses GitHub Actions with semantic-release for automated version management and PyPI publishing. The workflow follows conventional commits to automatically determine version bumps and generate changelogs.

## Workflows

### 1. PR Checks ([.github/workflows/pr-checks.yaml](.github/workflows/pr-checks.yaml))

Runs on every pull request to `main`:
- **Lint**: Validates code style with ruff
- **Test**: Runs pytest test suite with coverage

### 2. Publish ([.github/workflows/publish.yaml](.github/workflows/publish.yaml))

Runs on every push to `main`:
1. **Lint**: Validates code style
2. **Test**: Runs full test suite
3. **Semantic Release**: Analyzes commits and determines version bump
4. **Publish to PyPI**: Publishes new version if released

## Configuration

### PyPI Publishing

The workflow uses [Trusted Publishing](https://docs.pypi.org/trusted-publishers/) (OIDC) which is more secure than API tokens.

**Setup required**:
1. Go to [PyPI Trusted Publishers](https://pypi.org/manage/account/publishing/)
2. Add a new trusted publisher for your project:
   - **PyPI Project Name**: `jlcpcb-mcp`
   - **Owner**: `peterb154`
   - **Repository**: `jlcpcb-search-mcp`
   - **Workflow name**: `publish.yaml`
   - **Environment**: (leave blank)

### Semantic Release

Configured in [pyproject.toml](pyproject.toml):

```toml
[tool.semantic_release]
version_toml = ["pyproject.toml:project.version"]
build_command = "uv build"
major_on_zero = true
tag_format = "v{version}"

[tool.semantic_release.commit_parser_options]
allowed_tags = ["feat", "fix", "docs", "style", "refactor", "perf", "test", "chore", "ci", "build"]
minor_tags = ["feat"]
patch_tags = ["fix", "perf"]
```

## Commit Conventions

Follow [Conventional Commits](https://www.conventionalcommits.org/):

### Version Bumps

- `feat:` - New feature (minor version bump: 0.1.0 → 0.2.0)
- `fix:` - Bug fix (patch version bump: 0.1.0 → 0.1.1)
- `perf:` - Performance improvement (patch version bump)
- `BREAKING CHANGE:` in footer - Major version bump (1.0.0 → 2.0.0)

### No Version Bump

- `docs:` - Documentation only
- `style:` - Code style changes
- `refactor:` - Code refactoring (no functional changes)
- `test:` - Test additions/changes
- `chore:` - Build process, dependencies
- `ci:` - CI configuration changes
- `build:` - Build system changes

### Examples

```bash
# Minor version bump (new feature)
git commit -m "feat: add support for inductor component search"

# Patch version bump (bug fix)
git commit -m "fix: correct resistance value parsing for K suffix"

# No version bump (docs)
git commit -m "docs: update API examples in README"

# Major version bump (breaking change)
git commit -m "feat: redesign search API

BREAKING CHANGE: search_components now requires category parameter"
```

## Local Development Commands

```bash
# Install dev dependencies
make dev

# Run linter (check only)
make lint

# Auto-fix lint issues
make lint-fix

# Run tests
make test

# Run tests with coverage report
make test-cov

# Preview next version (dry-run)
make version

# Create release locally (for testing)
make release

# Clean build artifacts
make clean
```

## Release Process

### Automatic (Recommended)

1. Create feature branch: `git checkout -b feature/my-feature`
2. Make changes with conventional commits
3. Push and create PR
4. Wait for PR checks to pass
5. Merge to `main`
6. GitHub Actions automatically:
   - Analyzes commits
   - Bumps version
   - Creates git tag
   - Updates CHANGELOG.md
   - Publishes to PyPI

### Manual (Local Testing)

```bash
# Preview what semantic-release will do
make version

# Create release locally (doesn't publish to PyPI)
make release

# Push tags
git push --follow-tags
```

## First Release Checklist

Before your first automated release:

- [ ] Set up PyPI Trusted Publisher (see Configuration section)
- [ ] Verify repository settings:
  - [ ] Default branch is `main`
  - [ ] Actions are enabled
  - [ ] Workflows have write permissions
- [ ] Make your first commit with `feat:` or `fix:` prefix
- [ ] Push to `main` and watch Actions tab

## Troubleshooting

### Release didn't trigger

Check that your commit message uses the correct conventional format:
```bash
git log --oneline
```

### PyPI publish failed

1. Verify Trusted Publisher is configured correctly
2. Check that the workflow has `id-token: write` permission
3. Ensure repository name matches exactly in PyPI settings

### Version didn't bump

1. Check commit message format
2. Run `make version` locally to preview
3. Verify [tool.semantic_release] configuration in pyproject.toml

## Resources

- [Conventional Commits](https://www.conventionalcommits.org/)
- [Python Semantic Release](https://python-semantic-release.readthedocs.io/)
- [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/)
- [GitHub Actions](https://docs.github.com/en/actions)
