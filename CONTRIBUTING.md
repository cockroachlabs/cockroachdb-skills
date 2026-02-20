# Contributing to CockroachDB Skills

Thank you for your interest in contributing to the CockroachDB Skills repository! This guide will help you create high-quality Agent Skills that encode CockroachDB expertise in a structured, machine-executable format.

## Table of Contents

1. [Welcome and Overview](#welcome-and-overview)
2. [Before You Start](#before-you-start)
3. [Proposing a New Skill](#proposing-a-new-skill)
4. [Development Workflow](#development-workflow)
5. [Skill Requirements](#skill-requirements)
6. [Quality Standards](#quality-standards)
7. [Testing and Validation](#testing-and-validation)
8. [Review Process](#review-process)
9. [Domain Structure](#domain-structure)
10. [Getting Help](#getting-help)

## Welcome and Overview

CockroachDB Skills are structured capabilities that AI agents, automation systems, and developer tools can invoke to perform CockroachDB operations. Each skill follows the [Agent Skills Specification](https://agentskills.io/specification) and encodes expertise from experienced CockroachDB practitioners.

**What makes a good contribution:**
- Solves a specific, well-defined CockroachDB operational challenge
- Provides clear guidance on when and how to use the skill
- Includes safety guardrails for operations that can affect data or availability
- References official CockroachDB documentation rather than duplicating it
- Can be easily discovered and invoked by AI agents

## Before You Start

1. **Review existing skills** - Browse the `skills/` directory to understand the style and scope
2. **Check the specification** - Read the [Agent Skills Specification](https://agentskills.io/specification)
3. **Understand domain boundaries** - Review the [Domain Structure](#domain-structure) section below
4. **Search existing issues** - Make sure your idea hasn't already been proposed

## Proposing a New Skill

Before implementing a skill, open an issue using the [new skill proposal template](.github/ISSUE_TEMPLATE/new-skill.yml). This ensures:

- Alignment on scope and domain placement
- No duplication of effort
- Feedback on approach before significant work
- Opportunity to collaborate with maintainers

**In your proposal, include:**
- **Skill name** - Following naming conventions (lowercase, hyphens, gerund form preferred)
- **Domain** - Which of the 9 domains this skill belongs to
- **Description** - What the skill does and when to use it (include trigger keywords)
- **Scope and boundaries** - What's included and what's explicitly out of scope
- **Expected inputs/outputs** - What information the skill needs and provides
- **Safety considerations** - Any risks or guardrails needed
- **References** - Links to relevant CockroachDB documentation
- **Use case** - Why this skill is needed and who will benefit

## Development Workflow

### 1. Fork and Clone

```bash
git clone https://github.com/YOUR-USERNAME/cockroachdb-skills.git
cd cockroachdb-skills
```

### 2. Create a Feature Branch

Use the naming convention: `skill/domain/skill-name`

```bash
git checkout -b skill/performance-and-scaling/analyzing-slow-queries
```

### 3. Create Skill Directory

```bash
mkdir -p skills/performance-and-scaling/analyzing-slow-queries
```

### 4. Write SKILL.md

Create `skills/domain/skill-name/SKILL.md` with required frontmatter and content.

**Minimal example:**

```markdown
---
name: analyzing-slow-queries
description: Identifies and diagnoses slow queries using CockroachDB's built-in observability tools. Use when query performance degrades or users report slow response times.
---

# Analyzing Slow Queries

This skill guides you through identifying, diagnosing, and resolving slow query performance in CockroachDB.

## When to Use This Skill

- Application users report slow response times
- Monitoring alerts indicate high query latency
- You need to understand which queries are consuming the most resources
- You're investigating performance regressions after schema changes

## Prerequisites

- Access to CockroachDB DB Console or SQL shell
- Appropriate permissions to view system tables
- Basic understanding of SQL query execution

## Steps

### 1. Identify Slow Queries

[Detailed step-by-step guidance...]

### 2. Analyze Execution Plans

[Detailed analysis guidance...]

## Safety Considerations

- Avoid running `EXPLAIN ANALYZE` on production queries that modify data
- Be cautious when adding indexes to high-traffic tables during peak hours

## References

- [CockroachDB Docs: Troubleshoot SQL Performance](https://www.cockroachlabs.com/docs/stable/query-performance-best-practices.html)
- [CockroachDB Docs: EXPLAIN Statement](https://www.cockroachlabs.com/docs/stable/explain.html)
```

### 5. Commit and Push

```bash
git add skills/performance-and-scaling/analyzing-slow-queries/
git commit -m "Add analyzing-slow-queries skill

This skill helps users identify and diagnose slow queries using
CockroachDB's built-in observability tools.

git push origin skill/performance-and-scaling/analyzing-slow-queries
```

### 6. Open a Pull Request

Use the [pull request template](.github/PULL_REQUEST_TEMPLATE.md) and reference your proposal issue.

## Skill Requirements

### Required Frontmatter Fields

Every `SKILL.md` must include YAML frontmatter with:

- **`name`** (required) - Lowercase, hyphens only, max 64 characters, matches directory name
- **`description`** (required) - Max 1024 characters, third person, includes "when to use" triggers

**Example:**

```yaml
---
name: migrating-from-postgres
description: Guides migration from PostgreSQL to CockroachDB, addressing schema compatibility, data transfer, and application changes. Use when planning or executing a Postgres to CockroachDB migration.
---
```

### Optional Frontmatter Fields

- **`license`** - SPDX identifier (defaults to repository license)
- **`compatibility`** - Version constraints (e.g., "CockroachDB >=22.1")
- **`metadata`** - Arbitrary key-value pairs for tooling

### Naming Conventions

**Skill names must:**
- Use lowercase letters, numbers, and hyphens only
- Be max 64 characters
- Not include reserved words: "anthropic", "claude"
- Not include XML tags like `<`, `>`
- Match the parent directory name exactly

**Preferred forms:**
- ✅ Gerund (verb-ing): `analyzing-slow-queries`, `migrating-from-postgres`
- ✅ Present participle: `tuning-index-strategies`
- ❌ Imperative: `analyze-slow-queries` (works but gerund is preferred)
- ❌ Nouns: `slow-query-analysis` (less clear about action)

### Description Best Practices

**Good descriptions:**
- Explain WHAT the skill does (first sentence)
- Explain WHEN to use it (second sentence or "Use when..." clause)
- Include trigger keywords agents can match on
- Are concise (max 1024 chars)
- Use third person ("Guides...", "Diagnoses...", not "This skill guides...")

**Examples:**

✅ **Good**: "Identifies and diagnoses slow queries using CockroachDB's built-in observability tools. Use when query performance degrades or users report slow response times."

❌ **Too vague**: "Helps with query performance."

❌ **Missing trigger**: "Analyzes query execution plans and suggests optimizations." (When should this be used?)

❌ **Too long**: Descriptions exceeding 1024 characters

## Quality Standards

### Scope Discipline

Each skill should address **one specific task**. If your skill tries to do multiple things, consider splitting it.

**Good scope:**
- ✅ `diagnosing-contention-hotspots` - Focused on one problem
- ✅ `validating-backup-integrity` - Single verification task

**Too broad:**
- ❌ `database-performance-tuning` - Many different tasks
- ❌ `cockroachdb-administration` - Entire operational domain

### Guardrails for Risky Operations

Skills that can modify data, affect availability, or have financial impact **must include:**

1. **Prerequisites section** - Required permissions, backups, maintenance windows
2. **Safety considerations** - Explicit warnings about risks
3. **Rollback guidance** - How to undo changes if something goes wrong
4. **Validation steps** - How to verify the operation succeeded

**Example guardrails:**

```markdown
## Safety Considerations

⚠️ **This operation will temporarily increase cluster load**

- Run during off-peak hours when possible
- Monitor cluster metrics during execution
- Have a rollback plan ready

## Prerequisites

- [ ] Backup completed within last 24 hours
- [ ] Maintenance window scheduled
- [ ] Rollback plan documented and tested
```

### Authoritative References

**Always link to official CockroachDB documentation** rather than duplicating content. This ensures:
- Skills stay accurate as documentation evolves
- Users get the most up-to-date information
- Skills remain concise and focused

**Good references:**

```markdown
## References

- [CockroachDB Docs: Multi-Region Overview](https://www.cockroachlabs.com/docs/stable/multiregion-overview.html)
- [CockroachDB Docs: Backup and Restore](https://www.cockroachlabs.com/docs/stable/backup-and-restore-overview.html)
```

### Clear Inputs and Outputs

Skills should clearly define:

- **What information is needed** - Cluster topology, workload characteristics, error messages
- **What the skill provides** - Diagnostic reports, configuration recommendations, action plans

**Example:**

```markdown
## Inputs

- Current cluster topology (number of nodes, regions)
- Query performance metrics (p50, p99 latencies)
- Application access patterns (read/write ratios)

## Outputs

- Recommended multi-region configuration
- Expected latency improvements
- Migration plan with rollback steps
```

## Testing and Validation

### Local Validation

Before opening a PR, validate your skill locally:

```bash
# Install dependencies
pip install -r scripts/requirements.txt

# Run validation
python scripts/validate-spec.py skills/

# Validate specific skill
python scripts/validate-spec.py skills/performance-and-scaling/analyzing-slow-queries/
```

### CI Validation

All pull requests are automatically validated via GitHub Actions. The CI checks:

- ✅ Directory structure compliance
- ✅ Required SKILL.md frontmatter fields
- ✅ Naming conventions
- ✅ Character limits
- ✅ Best practices (warnings for improvements)

**If CI fails:**
1. Review the error messages in the GitHub Actions log
2. Fix the issues locally
3. Commit and push the fixes
4. CI will re-run automatically

### Manual Testing

**Recommended testing approach:**
1. Use the skill with an AI agent (Claude, GPT, or other LLM)
2. Verify the agent can understand when to invoke the skill
3. Confirm the guidance provided is accurate and actionable
4. Test with realistic scenarios from your own experience

## Review Process

### What Reviewers Look For

1. **Specification compliance** - Follows Agent Skills Specification requirements
2. **Scope discipline** - Focused on one specific task
3. **Clear triggers** - Description makes it obvious when to use the skill
4. **Accurate guidance** - Technical content is correct and up-to-date
5. **Safety** - Appropriate guardrails for risky operations
6. **References** - Links to official CockroachDB docs
7. **Writing quality** - Clear, concise, well-organized

### Incorporating Feedback

- Address all reviewer comments (or explain why you disagree)
- Push new commits rather than force-pushing (preserves review history)
- Mark conversations as resolved once addressed
- Re-request review after making changes

## Domain Structure

Skills are organized into **9 operational domains**. Choose the domain that best matches your skill's primary purpose:

### 1. **Onboarding and Migrations**
Getting started with CockroachDB and moving workloads into the system.
- Migration planning and execution
- Data ingestion strategies
- Initial cluster setup
- PostgreSQL compatibility handling

### 2. **Application Development**
Building applications that use CockroachDB effectively.
- Schema design patterns
- Transaction handling
- ORM configuration
- Connection pooling

### 3. **Performance and Scaling**
Optimizing query performance and scaling clusters.
- Query optimization
- Index tuning
- Contention diagnosis
- Throughput scaling

### 4. **Operations and Lifecycle**
Day-to-day cluster operations and version management.
- Cluster upgrades
- Node management
- Configuration changes
- Routine maintenance

### 5. **Resilience and Disaster Recovery**
Ensuring high availability and preparing for failures.
- Backup strategies
- Restore procedures
- Failover testing
- RPO/RTO planning

### 6. **Observability and Diagnostics**
Monitoring, alerting, and diagnosing health issues.
- Metrics interpretation
- Alert configuration
- Issue diagnosis
- Performance troubleshooting

### 7. **Security and Governance**
Access control, compliance, and data protection.
- RBAC configuration
- Encryption setup
- Audit logging
- Compliance controls

### 8. **Integrations and Ecosystem**
Connecting CockroachDB to external tools and platforms.
- CDC/changefeed setup
- Third-party integrations
- Infrastructure-as-code
- Monitoring integration

### 9. **Cost and Usage Management**
Understanding and optimizing resource consumption.
- Storage analysis
- Compute optimization
- Usage forecasting
- Cost attribution

**If your skill spans multiple domains**, choose the **primary** domain based on the main problem it solves.

## Getting Help

### Questions About Contributing

- **Open a discussion** - Use GitHub Discussions for general questions
- **File an issue** - Use the [documentation improvement template](.github/ISSUE_TEMPLATE/documentation.yml) for unclear guidelines
- **Ask in your proposal** - Clarify scope and approach in your skill proposal issue

### Questions About CockroachDB

- [CockroachDB Documentation](https://www.cockroachlabs.com/docs/)
- [CockroachDB Community](https://www.cockroachlabs.com/community/)
- [CockroachDB Forum](https://forum.cockroachlabs.com/)

### Reporting Issues

- **Skill bugs** - Use the [bug report template](.github/ISSUE_TEMPLATE/bug-report.yml)
- **Documentation issues** - Use the [documentation improvement template](.github/ISSUE_TEMPLATE/documentation.yml)

---

Thank you for contributing to CockroachDB Skills! Your expertise helps make CockroachDB more accessible to developers, operators, and AI agents worldwide.
