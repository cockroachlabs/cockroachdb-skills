# CockroachDB Skills

![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)
![CI Status](https://github.com/cockroachlabs/cockroachdb-skills/workflows/Validate%20Skills/badge.svg)
![Agent Skills Spec](https://img.shields.io/badge/spec-agentskills.io-orange)

A curated collection of **Agent Skills** for CockroachDB—structured, machine-executable capabilities that encode CockroachDB expertise. This repository enables AI agents, automation systems, and developer tools to deliver contextually aware, production-grade CockroachDB operations.

## What Is a CockroachDB Skill?

A **CockroachDB Skill** is a structured capability that:

- **Encodes operational expertise** - How experienced CockroachDB practitioners solve specific challenges
- **Follows the Agent Skills Specification** - Structured according to [agentskills.io/specification](https://agentskills.io/specification)
- **Is machine-executable** - Can be invoked by AI agents, automation platforms, and developer tools
- **Has clear boundaries** - Focused scope with explicit inputs, outputs, and safety guardrails
- **References authoritative sources** - Links directly to official CockroachDB documentation

Skills live in the `skills/` directory, organized by operational domain. Each skill is a directory containing a `SKILL.md` file with frontmatter and structured content.

## Quick Start

1. Review the [Agent Skills Specification](https://agentskills.io/specification)
2. Read our [Contributing Guidelines](CONTRIBUTING.md)
3. Browse existing skills in the `skills/` directory
4. Propose a new skill using our [issue template](.github/ISSUE_TEMPLATE/new-skill.yml)

## What This Repository Is NOT

❌ **Not a prompt library** - Skills are not just conversational prompts
❌ **Not LLM training data** - Skills are runtime capabilities, not training material
❌ **Not documentation mirrors** - Skills encode operational reasoning, not docs copies
❌ **Not vendor-locked** - Skills are protocol-agnostic and specification-based
❌ **Not a chat interface** - Skills are structured capabilities for agents/automation

## Skill Domains

Skills are organized into **9 operational domains** that cover the full CockroachDB lifecycle:

### 1. Onboarding and Migrations
Getting started with CockroachDB and moving workloads into the system.

### 2. Application Development
Building applications that use CockroachDB effectively.

### 3. Performance and Scaling
Optimizing query performance and scaling CockroachDB clusters.

### 4. Operations and Lifecycle
Day-to-day cluster operations and version management.

### 5. Resilience and Disaster Recovery
Ensuring high availability and preparing for failures.

### 6. Observability and Diagnostics
Monitoring, alerting, and diagnosing issues.

### 7. Security and Governance
Access control, compliance, and data protection.

### 8. Integrations and Ecosystem
Connecting CockroachDB to external tools and platforms.

### 9. Cost and Usage Management
Understanding and optimizing resource consumption.

## Contributing

We welcome contributions from the community! To contribute:

1. **Propose a skill**: Open an issue using the [new skill template](.github/ISSUE_TEMPLATE/new-skill.yml)
2. **Get alignment**: Discuss scope, domain, and approach with maintainers
3. **Implement**: Follow the [Agent Skills Specification](https://agentskills.io/specification)
4. **Submit PR**: Use our [pull request template](.github/PULL_REQUEST_TEMPLATE.md)
5. **Iterate**: Address feedback and ensure CI passes

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

## Design Principles

### Scope Discipline
Each skill addresses **one specific task** with clear boundaries. Skills that try to do too much are harder to maintain, test, and compose.

### Progressive Disclosure
Skills start with essential context and progressively reveal details. Core concepts come first, edge cases and troubleshooting come later.

### Guardrails by Default
Skills that can modify data or affect availability include explicit safety checks, confirmation prompts, and rollback guidance.

### Authoritative References
Skills link to official CockroachDB documentation rather than duplicating it. When docs change, skills remain accurate.

### Trigger Clarity
Skill descriptions include clear "when to use" signals so agents can discover and invoke them contextually.

## Validation and Quality

All skills are automatically validated against the Agent Skills Specification via GitHub Actions:

- ✅ Directory structure compliance
- ✅ Required SKILL.md frontmatter fields
- ✅ Naming conventions (lowercase, hyphens, no reserved words)
- ✅ Character limits (name ≤64 chars, description ≤1024 chars)
- ✅ Best practices (progressive disclosure, clear triggers)

Run validation locally:

```bash
python scripts/validate-spec.py skills/
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed requirements.

## Repository Structure

```
cockroachdb-skills/
├── skills/                          # All skills organized by domain
│   ├── onboarding-and-migrations/
│   ├── application-development/
│   ├── performance-and-scaling/
│   ├── operations-and-lifecycle/
│   ├── resilience-and-disaster-recovery/
│   ├── observability-and-diagnostics/
│   ├── security-and-governance/
│   ├── integrations-and-ecosystem/
│   └── cost-and-usage-management/
├── scripts/                         # Validation and tooling scripts
│   ├── validate-spec.py             # Specification compliance validator
│   └── requirements.txt             # Python dependencies
├── .github/                         # GitHub Actions and templates
│   ├── workflows/
│   │   └── validate-skills.yml      # CI validation workflow
│   ├── ISSUE_TEMPLATE/              # Issue templates for proposals
│   └── PULL_REQUEST_TEMPLATE.md     # PR template with checklist
├── CONTRIBUTING.md                  # Contribution guidelines
├── LICENSE                          # Apache 2.0 license
└── README.md                        # This file
```

## License

This repository is licensed under the Apache License 2.0. See [LICENSE](LICENSE) for details.

## Resources

- [Agent Skills Specification](https://agentskills.io/specification)
- [CockroachDB Documentation](https://www.cockroachlabs.com/docs/)
- [CockroachDB Community](https://www.cockroachlabs.com/community/)
- [Contributing Guidelines](CONTRIBUTING.md)

---

**Maintained by [Cockroach Labs](https://www.cockroachlabs.com/)**
