# CodeCollection Registry Documentation

## Documentation Structure

This directory contains **one documentation file per major feature**. Each file is the single source of truth for that feature.

### Available Documentation

- **[chat.md](chat.md)** - Chat system architecture, follow-up detection, API, troubleshooting
- **[chat-debug.md](chat-debug.md)** - Debug console features, filtering, use cases, API endpoints

### Guidelines

**When to create a new doc:**
- You're adding a major new feature
- The feature doesn't fit into existing docs
- It needs standalone reference documentation

**When to update existing docs:**
- Fixing bugs in existing features
- Adding enhancements to existing features
- Documenting known issues
- Adding troubleshooting tips

**What NOT to create:**
- `FEATURE-FIX.md` (update the feature doc instead)
- `FEATURE-GUIDE.md` (consolidate into feature doc)
- `ISSUE-12345.md` (document in feature doc or `Agents.md`)
- `TESTING-FEATURE.md` (add testing section to feature doc)

### Documentation Template

When creating a new feature doc, include these sections:

```markdown
# Feature Name

## Overview
Brief description, user access URL

## Architecture
Components, flow, key files

## Configuration
Environment variables, setup

## API Reference
Endpoints, request/response formats

## Common Issues
Known problems and solutions

## Development
How to make changes and test

## Performance
Metrics, monitoring

Last Updated: YYYY-MM-DD
```

---

See [../Agents.md](../Agents.md) for overall project guidelines and quick references.
