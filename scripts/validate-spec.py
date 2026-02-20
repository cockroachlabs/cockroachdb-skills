#!/usr/bin/env python3
"""
Validates CockroachDB Skills against the Agent Skills Specification.

This script checks:
1. Directory structure compliance
2. SKILL.md frontmatter validation
3. Naming conventions
4. Content quality checks
5. Best practices

Usage:
    python scripts/validate-spec.py skills/
    python scripts/validate-spec.py skills/performance-and-scaling/analyzing-slow-queries/
    python scripts/validate-spec.py skills/ --strict  # Fail on warnings
"""

import argparse
import re
import sys
from pathlib import Path
from typing import List, Tuple, Optional

try:
    import yaml
except ImportError:
    print("Error: PyYAML is required. Install with: pip install PyYAML>=6.0")
    sys.exit(1)


# ANSI color codes for terminal output
class Colors:
    RED = '\033[91m'
    YELLOW = '\033[93m'
    GREEN = '\033[92m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


# Reserved words that cannot appear in skill names
RESERVED_WORDS = ['anthropic', 'claude']

# Allowed directories within a skill directory
ALLOWED_SKILL_DIRS = {'scripts', 'references', 'assets'}

# Maximum limits
MAX_NAME_LENGTH = 64
MAX_DESCRIPTION_LENGTH = 1024
MAX_SKILL_LINES = 500  # Warning threshold


class ValidationError:
    """Represents a validation error or warning."""
    def __init__(self, level: str, message: str, file_path: Optional[Path] = None):
        self.level = level  # 'error' or 'warning'
        self.message = message
        self.file_path = file_path

    def format_for_github(self) -> str:
        """Format for GitHub Actions annotations."""
        if self.file_path:
            return f"::{self.level} file={self.file_path}::{self.message}"
        return f"::{self.level}::{self.message}"

    def format_for_terminal(self) -> str:
        """Format for colorized terminal output."""
        if self.level == 'error':
            prefix = f"{Colors.RED}{Colors.BOLD}ERROR{Colors.RESET}"
        else:
            prefix = f"{Colors.YELLOW}{Colors.BOLD}WARNING{Colors.RESET}"

        location = f" ({Colors.BLUE}{self.file_path}{Colors.RESET})" if self.file_path else ""
        return f"{prefix}{location}: {self.message}"


class SkillValidator:
    """Validates a single skill directory."""

    def __init__(self, skill_dir: Path):
        self.skill_dir = skill_dir
        self.skill_md = skill_dir / "SKILL.md"
        self.errors: List[ValidationError] = []
        self.warnings: List[ValidationError] = []

    def error(self, message: str, file_path: Optional[Path] = None):
        """Add a validation error."""
        self.errors.append(ValidationError('error', message, file_path or self.skill_md))

    def warning(self, message: str, file_path: Optional[Path] = None):
        """Add a validation warning."""
        self.warnings.append(ValidationError('warning', message, file_path or self.skill_md))

    def validate(self) -> Tuple[List[ValidationError], List[ValidationError]]:
        """Run all validation checks. Returns (errors, warnings)."""
        # Check that SKILL.md exists
        if not self.skill_md.exists():
            self.error(f"Missing required SKILL.md file in {self.skill_dir}")
            return self.errors, self.warnings

        # Parse frontmatter
        frontmatter, body = self._parse_skill_md()
        if frontmatter is None:
            return self.errors, self.warnings

        # Run validation checks
        self._validate_directory_structure()
        self._validate_frontmatter(frontmatter)
        self._validate_content(body)

        return self.errors, self.warnings

    def _parse_skill_md(self) -> Tuple[Optional[dict], str]:
        """Parse YAML frontmatter from SKILL.md. Returns (frontmatter_dict, body_content)."""
        try:
            content = self.skill_md.read_text(encoding='utf-8')
        except Exception as e:
            self.error(f"Failed to read SKILL.md: {e}")
            return None, ""

        # Check for frontmatter delimiters
        if not content.startswith('---\n'):
            self.error("SKILL.md must start with YAML frontmatter (---)")
            return None, content

        # Find end of frontmatter
        end_delimiter = content.find('\n---\n', 4)
        if end_delimiter == -1:
            self.error("SKILL.md frontmatter not properly closed (missing closing ---)")
            return None, content

        frontmatter_text = content[4:end_delimiter]
        body = content[end_delimiter + 5:]

        # Parse YAML
        try:
            frontmatter = yaml.safe_load(frontmatter_text)
            if not isinstance(frontmatter, dict):
                self.error("SKILL.md frontmatter must be a YAML dictionary")
                return None, body
        except yaml.YAMLError as e:
            self.error(f"Invalid YAML in frontmatter: {e}")
            return None, body

        return frontmatter, body

    def _validate_directory_structure(self):
        """Validate that only allowed directories/files exist."""
        for item in self.skill_dir.iterdir():
            if item.is_dir() and item.name not in ALLOWED_SKILL_DIRS:
                self.error(f"Unexpected directory '{item.name}'. Only {ALLOWED_SKILL_DIRS} are allowed.")

    def _validate_frontmatter(self, frontmatter: dict):
        """Validate frontmatter fields."""
        # Check required fields
        if 'name' not in frontmatter:
            self.error("Missing required field 'name' in frontmatter")
            return
        if 'description' not in frontmatter:
            self.error("Missing required field 'description' in frontmatter")
            return

        name = frontmatter['name']
        description = frontmatter['description']

        # Validate name
        self._validate_name(name)

        # Validate description
        self._validate_description(description)

        # Validate optional fields if present
        if 'license' in frontmatter:
            self._validate_license(frontmatter['license'])

        if 'compatibility' in frontmatter:
            self._validate_compatibility(frontmatter['compatibility'])

        if 'metadata' in frontmatter:
            if not isinstance(frontmatter['metadata'], dict):
                self.error("'metadata' field must be a dictionary")

    def _validate_name(self, name: str):
        """Validate skill name."""
        if not isinstance(name, str):
            self.error(f"Skill name must be a string, got {type(name).__name__}")
            return

        # Check length
        if len(name) > MAX_NAME_LENGTH:
            self.error(f"Skill name exceeds maximum length of {MAX_NAME_LENGTH} characters ({len(name)} chars)")

        # Check format (lowercase, numbers, hyphens only)
        if not re.match(r'^[a-z0-9-]+$', name):
            self.error("Skill name must contain only lowercase letters, numbers, and hyphens")

        # Check for reserved words
        for reserved in RESERVED_WORDS:
            if reserved in name:
                self.error(f"Skill name cannot contain reserved word '{reserved}'")

        # Check for XML tags
        if '<' in name or '>' in name:
            self.error("Skill name cannot contain XML tags")

        # Check that name matches directory name
        if name != self.skill_dir.name:
            self.error(f"Skill name '{name}' does not match directory name '{self.skill_dir.name}'")

        # Best practice: prefer gerund form (verb-ing)
        if not name.endswith('ing') and not any(name.startswith(prefix) for prefix in ['analyzing', 'diagnosing', 'migrating', 'optimizing', 'configuring', 'implementing', 'tuning', 'validating', 'planning']):
            self.warning(f"Consider using gerund form (verb-ing) for skill name: '{name}' → '{name}ing' or 'analyzing-{name}'")

    def _validate_description(self, description: str):
        """Validate skill description."""
        if not isinstance(description, str):
            self.error(f"Skill description must be a string, got {type(description).__name__}")
            return

        # Check non-empty
        if not description.strip():
            self.error("Skill description cannot be empty")
            return

        # Check length
        if len(description) > MAX_DESCRIPTION_LENGTH:
            self.error(f"Skill description exceeds maximum length of {MAX_DESCRIPTION_LENGTH} characters ({len(description)} chars)")

        # Check for XML tags
        if '<' in description or '>' in description:
            self.error("Skill description cannot contain XML tags")

        # Best practice: should include "when to use" triggers
        trigger_keywords = ['use when', 'when', 'if you', 'for', 'helps', 'guides']
        has_trigger = any(keyword in description.lower() for keyword in trigger_keywords)
        if not has_trigger:
            self.warning("Description should include clear 'when to use' triggers (e.g., 'Use when...', 'For...')")

        # Best practice: should be third person
        first_person_words = ['i ', 'we ', 'my ', 'our ']
        if any(word in description.lower() for word in first_person_words):
            self.warning("Description should use third person (avoid 'I', 'we', 'my', 'our')")

        # Best practice: should explain WHAT and WHEN
        if len(description.split('.')) < 2:
            self.warning("Description should include both WHAT the skill does and WHEN to use it (at least 2 sentences recommended)")

    def _validate_license(self, license_value: str):
        """Validate license field (should be SPDX identifier)."""
        if not isinstance(license_value, str):
            self.error(f"'license' field must be a string, got {type(license_value).__name__}")

    def _validate_compatibility(self, compatibility: str):
        """Validate compatibility field."""
        if not isinstance(compatibility, str):
            self.error(f"'compatibility' field must be a string, got {type(compatibility).__name__}")

    def _validate_content(self, body: str):
        """Validate SKILL.md body content."""
        lines = body.split('\n')

        # Check line count (warning only)
        if len(lines) > MAX_SKILL_LINES:
            self.warning(f"SKILL.md has {len(lines)} lines (recommended: ≤{MAX_SKILL_LINES}). Consider using references/ for detailed content.")

        # Check for broken internal references (simplified check)
        # Look for references to files that don't exist
        for line in lines:
            # Match markdown links: [text](path)
            matches = re.findall(r'\[([^\]]+)\]\(([^)]+)\)', line)
            for link_text, link_path in matches:
                # Only check relative paths (not URLs)
                if not link_path.startswith(('http://', 'https://', '#', 'mailto:')):
                    # Make path relative to skill directory
                    referenced_path = self.skill_dir / link_path
                    if not referenced_path.exists():
                        self.warning(f"Broken internal reference: {link_path}")


class RepositoryValidator:
    """Validates the entire skills repository."""

    def __init__(self, skills_dir: Path):
        self.skills_dir = skills_dir
        self.errors: List[ValidationError] = []
        self.warnings: List[ValidationError] = []

    def validate(self) -> Tuple[List[ValidationError], List[ValidationError]]:
        """Validate all skills in the repository."""
        if not self.skills_dir.exists():
            error = ValidationError('error', f"Skills directory not found: {self.skills_dir}")
            return [error], []

        if not self.skills_dir.is_dir():
            error = ValidationError('error', f"Path is not a directory: {self.skills_dir}")
            return [error], []

        # Find all skill directories
        skill_dirs = self._find_skill_directories()

        if not skill_dirs:
            # This is OK - repository might be empty
            return [], []

        # Validate each skill
        for skill_dir in skill_dirs:
            validator = SkillValidator(skill_dir)
            errors, warnings = validator.validate()
            self.errors.extend(errors)
            self.warnings.extend(warnings)

        return self.errors, self.warnings

    def _find_skill_directories(self) -> List[Path]:
        """Find all skill directories (directories containing SKILL.md)."""
        skill_dirs = []

        # Check if this is a single skill directory
        if (self.skills_dir / "SKILL.md").exists():
            return [self.skills_dir]

        # Otherwise, look for skills in domain subdirectories
        for domain_dir in self.skills_dir.iterdir():
            if not domain_dir.is_dir():
                continue
            if domain_dir.name.startswith('.'):
                continue

            # Check for skills in this domain
            for potential_skill_dir in domain_dir.iterdir():
                if not potential_skill_dir.is_dir():
                    continue
                if potential_skill_dir.name.startswith('.'):
                    continue

                if (potential_skill_dir / "SKILL.md").exists():
                    skill_dirs.append(potential_skill_dir)

        return skill_dirs


def main():
    parser = argparse.ArgumentParser(
        description='Validate CockroachDB Skills against the Agent Skills Specification'
    )
    parser.add_argument(
        'path',
        type=Path,
        help='Path to skills directory or specific skill directory'
    )
    parser.add_argument(
        '--strict',
        action='store_true',
        help='Treat warnings as errors (fail if any warnings)'
    )
    parser.add_argument(
        '--github',
        action='store_true',
        help='Output in GitHub Actions format'
    )

    args = parser.parse_args()

    # Validate
    validator = RepositoryValidator(args.path)
    errors, warnings = validator.validate()

    # Determine if running in GitHub Actions
    is_github_actions = args.github or 'GITHUB_ACTIONS' in sys.argv

    # Output results
    if errors:
        print(f"\n{Colors.RED}{Colors.BOLD}Found {len(errors)} error(s):{Colors.RESET}\n")
        for error in errors:
            if is_github_actions:
                print(error.format_for_github())
            else:
                print(error.format_for_terminal())

    if warnings:
        print(f"\n{Colors.YELLOW}{Colors.BOLD}Found {len(warnings)} warning(s):{Colors.RESET}\n")
        for warning in warnings:
            if is_github_actions:
                print(warning.format_for_github())
            else:
                print(warning.format_for_terminal())

    # Summary
    if not errors and not warnings:
        print(f"\n{Colors.GREEN}{Colors.BOLD}✓ All validations passed!{Colors.RESET}\n")
        return 0

    # Exit code
    if errors:
        return 1
    if args.strict and warnings:
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
