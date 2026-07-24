# GitHub Copilot Instructions

This file provides guidance to GitHub Copilot when working with code in this repository.

## Project Overview

This is the **CockroachDB Skills** repository—a curated collection of Agent Skills that encode CockroachDB operational expertise. Skills are structured, machine-executable capabilities following the [Agent Skills Specification](https://agentskills.io/specification). They enable AI agents to deliver contextually aware, production-grade CockroachDB operations.

**Core Concepts:**
- **Skills** are NOT just prompts or documentation—they encode operational reasoning and procedural knowledge
- Each skill addresses ONE specific operational task with clear boundaries
- Skills reference official CockroachDB docs rather than duplicating them
- Skills include safety guardrails for operations affecting data or availability

## Repository Structure

```
cockroachdb-skills/
├── skills/                          # Skills organized by 10 operational domains
│   ├── cockroachdb-onboarding-and-migrations/
│   ├── cockroachdb-query-and-schema-design/
│   ├── cockroachdb-application-development/
│   ├── cockroachdb-performance-and-scaling/
│   ├── cockroachdb-operations-and-lifecycle/
│   ├── cockroachdb-resilience-and-disaster-recovery/
│   ├── cockroachdb-observability-and-diagnostics/
│   ├── cockroachdb-security-and-governance/
│   ├── cockroachdb-integrations-and-ecosystem/
│   └── cockroachdb-cost-and-usage-management/
├── scripts/
│   ├── validate-spec.py             # Specification compliance validator
│   └── requirements.txt
├── docs/
│   ├── installation.md              # User installation guide
│   └── usage.md                     # User usage guide
├── .python-version                  # Pyenv Python version (3.11.15)
└── .github/
    ├── workflows/validate-skills.yml
    ├── copilot-instructions.md      # This file
    └── ISSUE_TEMPLATE/
```

## Skill Structure

Each skill is a directory under a domain containing:
- `SKILL.md` - Required file with YAML frontmatter + markdown content
- `references/` (optional) - Detailed reference material (SQL queries, examples, etc.)
- `scripts/` (optional) - Automation scripts
- `assets/` (optional) - Images, diagrams

### SKILL.md Anatomy

```markdown
---
name: skill-name-in-kebab-case
description: What it does and when to use it. Use when [trigger keywords].
compatibility: Version constraints (optional)
metadata:              # Optional key-value pairs
  author: cockroachdb
  version: "1.0"
---

# Skill Name

[Skill content following progressive disclosure principle]
```

## Common Development Tasks

### Python Environment Setup

This repository uses **pyenv** to manage Python versions. Python 3.11.15 is configured via `.python-version`.

```bash
# If pyenv not installed
brew install pyenv

# Add to shell config (~/.zshrc or ~/.bashrc)
export PYENV_ROOT="$HOME/.pyenv"
[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"

# Install Python 3.11
pyenv install 3.11.15

# Pyenv will automatically use 3.11.15 when in this directory
# Install dependencies
pip install -r scripts/requirements.txt
```

### Validate Skills Locally

```bash
# Validate all skills
python scripts/validate-spec.py skills/

# Validate specific skill (note: domain folders are prefixed with cockroachdb-)
python scripts/validate-spec.py skills/cockroachdb-security-and-governance/managing-tls-certificates/

# Strict mode (warnings become errors)
python scripts/validate-spec.py skills/ --strict
```

### CI Validation

All PRs automatically run `.github/workflows/validate-skills.yml` which:
- Validates directory structure
- Checks frontmatter compliance
- Verifies naming conventions
- Enforces character limits
- Warns about best practice violations

## Skill Authoring Guidelines

### Naming Conventions

**Skill names must:**
- Use lowercase letters, numbers, hyphens only
- Be ≤64 characters
- Match directory name exactly
- NOT contain reserved words: "anthropic", "claude", "copilot", "microsoft"
- NOT contain XML tags `<`, `>`

**Preferred naming patterns:**
- ✅ Gerund form: `analyzing-slow-queries`, `configuring-audit-logging`
- ✅ Present participle: `tuning-index-strategies`
- ❌ Imperative: `analyze-slow-queries` (works but gerund preferred)
- ❌ Nouns: `slow-query-analysis` (less clear about action)

### Description Requirements

**Descriptions must:**
- Be ≤1024 characters
- Explain WHAT the skill does (first sentence)
- Explain WHEN to use it (include "Use when..." or similar triggers)
- Use third person ("Guides...", "Diagnoses...", not "This skill...")
- Include trigger keywords agents can match on
- NOT contain XML tags

**Example:**
```yaml
description: Identifies and diagnoses slow queries using CockroachDB's built-in observability tools. Use when query performance degrades or users report slow response times.
```

### Content Principles

**Progressive Disclosure:** Start with essential context, progressively reveal details. Core concepts first, edge cases later.

**Scope Discipline:** Each skill = ONE task. If a skill tries to do multiple things, split it.

**Guardrails for Risky Operations:** Skills that modify data, affect availability, or have financial impact MUST include:
1. Prerequisites section (permissions, backups, maintenance windows)
2. Safety considerations (explicit warnings)
3. Rollback guidance
4. Validation steps

**Authoritative References:** ALWAYS link to official CockroachDB docs rather than duplicating content.

### Validation Rules

The validator (`scripts/validate-spec.py`) checks:

**Errors (will fail CI):**
- Missing SKILL.md file
- Missing required frontmatter fields (`name`, `description`)
- Invalid YAML frontmatter
- Name doesn't match directory name
- Name contains reserved words or XML tags
- Description exceeds 1024 chars
- Unexpected directories (only `scripts/`, `references/`, `assets/` allowed)

**Warnings (won't fail CI unless `--strict`):**
- Name not in gerund form
- Description missing "when to use" triggers
- Description uses first person
- Description less than 2 sentences
- SKILL.md exceeds 500 lines (consider using references/)
- Broken internal references

## Skill Domains

Skills are organized into 10 operational domains (all prefixed with `cockroachdb-`). Choose based on primary purpose:

1. **cockroachdb-onboarding-and-migrations** - Getting started, moving workloads into CockroachDB
2. **cockroachdb-query-and-schema-design** - Schema design, query generation, optimization
3. **cockroachdb-application-development** - Transactions, ORMs, connection pooling
4. **cockroachdb-performance-and-scaling** - Query optimization, index tuning, contention diagnosis
5. **cockroachdb-operations-and-lifecycle** - Cluster upgrades, node management, routine maintenance
6. **cockroachdb-resilience-and-disaster-recovery** - Backups, restores, failover, RPO/RTO planning
7. **cockroachdb-observability-and-diagnostics** - Metrics, alerts, performance troubleshooting
8. **cockroachdb-security-and-governance** - RBAC, encryption, audit logging, compliance
9. **cockroachdb-integrations-and-ecosystem** - CDC/changefeeds, third-party integrations, IaC
10. **cockroachdb-cost-and-usage-management** - Storage analysis, compute optimization, usage forecasting

**Note:** Domain folders are prefixed with `cockroachdb-` to ensure global uniqueness when skills are installed alongside other skill repositories.

If a skill spans multiple domains, choose the PRIMARY domain based on the main problem it solves.

## Contributing Workflow

1. **Propose first**: Open issue using `.github/ISSUE_TEMPLATE/new-skill.yml`
2. **Get alignment**: Discuss scope and approach with maintainers
3. **Create branch**: For example: `add-skill/<domain>/<skill-name>`
4. **Implement**: Create `skills/cockroachdb-<domain>/<skill-name>/SKILL.md`
5. **Validate locally**: Run `python scripts/validate-spec.py skills/cockroachdb-<domain>/<skill-name>/`
6. **Submit PR**: Use `.github/PULL_REQUEST_TEMPLATE.md`
7. **Iterate**: Address feedback until CI passes

## Important Architectural Notes

### What Skills Are NOT

❌ **Not a prompt library** - Skills encode operational procedures, not conversational templates
❌ **Not documentation mirrors** - Skills reference docs, don't duplicate them
❌ **Not training data** - Skills are runtime capabilities for agents/automation
❌ **Not vendor-locked** - Follow open Agent Skills Specification

### Skill Discovery and Invocation

Skills are discovered by AI agents through:
- **Description triggers** - Keywords in description that match user intent
- **Domain organization** - Contextual grouping helps agents find relevant skills
- **SKILL.md content** - "When to Use This Skill" sections

Users install skills via:
- `npx skills add cockroachlabs/cockroachdb-skills` (recommended)
- Manual copy into `.github/` for Copilot-native usage
- Direct copy (for environments without symlink support)

### Copilot-Specific Usage Notes

When GitHub Copilot is active in this repository:
- Skill descriptions serve as **intent signals** — write them with the same care as docstrings
- Copilot Chat will surface relevant skills based on `description` trigger keywords
- Keep `SKILL.md` files focused and ≤500 lines so Copilot can reason over them efficiently
- Use `references/` subdirectories for large SQL blocks or config examples to avoid context bloat

### Reference Material Strategy

Keep SKILL.md ≤500 lines. Use `references/` subdirectory for:
- Detailed SQL queries (`references/sql-queries.md`)
- Permission requirements (`references/permissions.md`)
- Configuration examples (`references/configuration-steps.md`)
- Safety guidelines (`references/safety-guide.md`)

Reference files don't need frontmatter—they're supporting documentation.

## Key Design Patterns

### Progressive Disclosure Example

```markdown
# Skill Title

Brief introduction (what and why).

## When to Use This Skill
- Clear trigger scenarios

## Prerequisites
- What you need before starting

## Steps
### 1. High-Level Step
Basic guidance

### 2. Detailed Step
More specific instructions

## Safety Considerations
⚠️ Warnings and guardrails

## References
- [Official Docs](https://...)
```

### Guardrails Pattern

```markdown
## Safety Considerations

⚠️ **This operation will [describe impact]**

- Run during off-peak hours when possible
- Monitor cluster metrics during execution
- Have a rollback plan ready

## Prerequisites

- [ ] Backup completed within last 24 hours
- [ ] Maintenance window scheduled
- [ ] Rollback plan documented and tested
```

## Testing Skills

**Manual testing:**
1. Install skill locally (see installation.md)
2. Use skill with your AI agent (Copilot Chat, Claude Code, Cursor, etc.)
3. Verify agent understands when to invoke
4. Confirm guidance is accurate and actionable
5. Test with realistic scenarios

**Automated testing:**
- CI validates spec compliance automatically
- No unit tests required (skills are declarative, not executable code)

## License

Apache 2.0 - See LICENSE file
