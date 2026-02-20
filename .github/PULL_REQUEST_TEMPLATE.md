## What does this PR do?

<!-- Provide a brief summary of your changes -->

## Related Issue

<!-- Link to the skill proposal or issue this PR addresses -->
Closes #

## Type of Change

<!-- Check all that apply -->

- [ ] New skill
- [ ] Skill update/improvement
- [ ] Documentation update
- [ ] Infrastructure/tooling change
- [ ] Bug fix

## Skill Compliance Checklist

<!-- If this PR adds or modifies a skill, complete this checklist -->

- [ ] SKILL.md includes required frontmatter fields (`name`, `description`)
- [ ] Skill name follows naming conventions (lowercase, hyphens, gerund form preferred)
- [ ] Skill name matches directory name exactly
- [ ] Description is specific and includes "when to use" trigger keywords
- [ ] Description is max 1024 characters
- [ ] Skill is under 500 lines (or uses `references/` for detailed content)
- [ ] References official CockroachDB documentation (not duplicate content)
- [ ] Includes safety guardrails for risky operations (if applicable)
- [ ] Tested with at least one AI agent (manual validation)
- [ ] No time-sensitive information (version numbers, dates, "currently")
- [ ] Directory structure follows specification (only `scripts/`, `references/`, `assets/` subdirs)
- [ ] No reserved words in skill name ("anthropic", "claude")
- [ ] Local validation passes: `python scripts/validate-spec.py skills/`

## Documentation Updates

<!-- List any documentation files that were updated or need updating -->

- [ ] README.md
- [ ] CONTRIBUTING.md
- [ ] Skill SKILL.md files
- [ ] Other (specify):

## Testing

<!-- Describe how you validated this change -->

**Manual testing:**
- [ ] Tested with AI agent (specify which one):
- [ ] Verified skill is discoverable with appropriate prompts
- [ ] Validated technical accuracy against CockroachDB docs
- [ ] Tested any scripts or commands included in the skill

**Automated testing:**
- [ ] Local validation script passes: `python scripts/validate-spec.py skills/`
- [ ] CI validation will run automatically on this PR

## Additional Context

<!-- Add any other relevant information, screenshots, or notes -->

## Reviewer Notes

<!-- Anything specific you want reviewers to focus on? -->

---

**By submitting this PR, I confirm:**
- [ ] I have read the [contributing guidelines](../CONTRIBUTING.md)
- [ ] I have followed the [Agent Skills Specification](https://agentskills.io/specification)
- [ ] I have tested my changes
- [ ] I am willing to address review feedback
