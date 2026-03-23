# Installation Guide

This guide shows you how to install CockroachDB Skills for use with Claude Code.

## Prerequisites

**For Option 1 (npx):**
- **Node.js 18+** - [Download from nodejs.org](https://nodejs.org/)

**For manual installation (Options 2-4):**
- **Claude Code** (or another supported agent) - [Download and install Claude Code](https://claude.ai/download)
- **Git** - For cloning the repository

## Installation Options

Choose the approach that fits your workflow:

### Option 1: Quick Install with npx (Recommended)

**The easiest way to get started.** This interactive installer works with Claude Code, Cursor, Windsurf, OpenHands, and 40+ other agents.

**Prerequisites:**
- Node.js 18+ (for npx command)

**Installation:**
```bash
npx skills add cockroachlabs/cockroachdb-skills
```

**What this does:**
1. Fetches available skills from the repository
2. Shows you a list of all 29+ CockroachDB skills
3. Lets you select which skills to install (or install all with `--all`)
4. Detects your installed AI agents automatically
5. Installs skills to the appropriate directories with symlinks
6. Works project-level (default) or user-level with `--global`

**Interactive Mode:**
The installer will:
- Detect which agents you have installed (Claude Code, Cursor, etc.)
- Let you choose which skills to install
- Ask whether to install project-level or user-level
- Handle all directory creation and symlinking automatically

**Non-Interactive Mode:**
For automated setups or CI/CD:
```bash
# Install all skills for Claude Code, skip prompts
npx skills add cockroachlabs/cockroachdb-skills --agent claude-code --skill '*' --yes

# Install specific skills globally
npx skills add cockroachlabs/cockroachdb-skills --global --skill reviewing-cluster-health --yes
```

**Supported Agents:**
Works with 43+ agents including Claude Code, Cursor, Windsurf, Cline, OpenHands, Roo Code, GitHub Copilot, and more.

**When to use this option:**
- ✅ You want the simplest installation experience
- ✅ You have Node.js installed
- ✅ You want skills across multiple agents
- ✅ You prefer automated setup

---

### Option 2: Project-Level Manual Installation

Skills are available only within a specific project directory.

**When to use:** Working on a CockroachDB project and want these skills available only in that context.

```bash
# 1. Clone the repository
git clone https://github.com/cockroachlabs/cockroachdb-skills.git

# 2. Navigate to your project directory
cd /path/to/your-cockroachdb-project

# 3. Create the skills directory
mkdir -p .claude/skills

# 4. Create a symlink to the skills
ln -s /path/to/cockroachdb-skills/skills .claude/skills/cockroachdb-skills
```

### Option 3: User-Level Manual Installation (Global Access)

Skills are available in all Claude Code sessions, across all projects.

**When to use:** You work with CockroachDB frequently and want these skills always available.

```bash
# 1. Clone the repository
git clone https://github.com/cockroachlabs/cockroachdb-skills.git

# 2. Create the user-level skills directory
mkdir -p ~/.claude/skills

# 3. Create a symlink to the skills
ln -s /path/to/cockroachdb-skills/skills ~/.claude/skills/cockroachdb-skills
```

### Option 4: Direct Copy (Without Symlinks)

For environments where symbolic links aren't supported (some Windows configurations).

**Project-level:**
```bash
# Clone and copy to project
git clone https://github.com/cockroachlabs/cockroachdb-skills.git
mkdir -p /path/to/your-project/.claude/skills
cp -r cockroachdb-skills/skills /path/to/your-project/.claude/skills/cockroachdb-skills
```

**User-level:**
```bash
# Clone and copy to user directory
git clone https://github.com/cockroachlabs/cockroachdb-skills.git
mkdir -p ~/.claude/skills
cp -r cockroachdb-skills/skills ~/.claude/skills/cockroachdb-skills
```

**Note:** When using the copy method, you'll need to manually update the skills when the repository is updated.

## Verification

After installation, verify that Claude Code can discover the skills:

### 1. Start Claude Code

Start Claude Code in a terminal or open it in your IDE.

### 2. Ask Claude to List Skills

```
What CockroachDB skills are available?
```

**Expected response:**
Claude should list the skills grouped by domain, such as:
- Onboarding and Migrations (molt-fetch, molt-verify, molt-replicator)
- Performance and Scaling (analyzing-range-distribution, profiling-statement-fingerprints)
- Security and Governance (configuring-sso-and-scim, managing-tls-certificates)
- Operations and Lifecycle (reviewing-cluster-health, upgrading-cluster-version)
- And more...

### 3. Test a Skill

Try invoking a skill by describing a task:

```
Help me check if my CockroachDB cluster is healthy
```

Claude should use the `reviewing-cluster-health` skill to provide guidance.

## Troubleshooting

### npx Command Not Found

**Problem:** `npx: command not found`

**Solutions:**
1. Install Node.js 18+ from [nodejs.org](https://nodejs.org/)
2. Verify installation: `node --version && npx --version`
3. Restart your terminal after installation

### npx Installation Fails

**Problem:** Installation fails or hangs.

**Solutions:**
1. **Check network connectivity** - The CLI needs to fetch from GitHub
2. **Verify repository is public** - Ensure you can access https://github.com/cockroachlabs/cockroachdb-skills
3. **Try with verbose logging:**
   ```bash
   npx skills add cockroachlabs/cockroachdb-skills --verbose
   ```
4. **Clear npm cache:**
   ```bash
   npm cache clean --force
   npx skills add cockroachlabs/cockroachdb-skills
   ```

### No Agents Detected

**Problem:** npx installer says "No agents detected"

**Solutions:**
1. **Install an AI agent first** (Claude Code, Cursor, etc.)
2. **Manually specify the agent:**
   ```bash
   npx skills add cockroachlabs/cockroachdb-skills --agent claude-code
   ```
3. **Check agent-specific directories exist:**
   - Claude Code: `~/.claude/` or `.claude/`
   - Cursor: `~/.cursor/` or `.cursor/`

### Skills Not Discovered

**Problem:** Claude doesn't recognize the CockroachDB skills.

**Solutions:**
1. **Check directory structure:**
   ```bash
   # For project-level
   ls -la .claude/skills/cockroachdb-skills/

   # For user-level
   ls -la ~/.claude/skills/cockroachdb-skills/
   ```

   You should see skill directories like `onboarding-and-migrations/`, `security-and-governance/`, etc.

2. **Verify SKILL.md files exist:**
   ```bash
   find .claude/skills/cockroachdb-skills -name "SKILL.md"
   ```

   This should return multiple SKILL.md files.

3. **Restart Claude Code** - Sometimes a restart is needed for skill discovery.

4. **Check symlink:**
   ```bash
   # Verify symlink points to correct location
   ls -l .claude/skills/cockroachdb-skills
   ```

### Permission Errors

**Problem:** Permission denied when creating symlinks or directories.

**Solutions:**
- On macOS/Linux: Use `sudo` if needed for user-level installation
- On Windows: Run terminal as Administrator
- Check file permissions: `chmod` and `chown` as needed

### Symlink Not Supported

**Problem:** Your environment doesn't support symbolic links.

**Solution:** Use [Option 4: Direct Copy](#option-4-direct-copy-without-symlinks) instead.

### Skills Appear Outdated

**Problem:** Skills don't reflect recent repository updates.

**Solutions:**

**If using symlinks:**
```bash
# Navigate to the cloned repository
cd /path/to/cockroachdb-skills

# Pull latest changes
git pull origin main
```

**If using direct copy:**
```bash
# Pull latest changes
cd /path/to/cockroachdb-skills
git pull origin main

# Re-copy to installation location
# For project-level:
cp -r skills /path/to/your-project/.claude/skills/cockroachdb-skills

# For user-level:
cp -r skills ~/.claude/skills/cockroachdb-skills
```

## Updating Skills

### With npx (Option 1)

Simply run the installation command again to get the latest skills:

```bash
npx skills add cockroachlabs/cockroachdb-skills --yes
```

### With Symlinks (Options 2 & 3)

Simply pull the latest changes from the repository:

```bash
cd /path/to/cockroachdb-skills
git pull origin main
```

The symlink ensures Claude Code automatically uses the updated skills.

### With Direct Copy (Option 4)

After pulling updates, re-copy the skills:

```bash
cd /path/to/cockroachdb-skills
git pull origin main

# Then copy to your installation location (see Option 4 above)
```

## Uninstalling

### Remove Project-Level Skills

```bash
rm .claude/skills/cockroachdb-skills
```

### Remove User-Level Skills

```bash
rm ~/.claude/skills/cockroachdb-skills
```

Or if you used direct copy:

```bash
rm -rf ~/.claude/skills/cockroachdb-skills
```

## Next Steps

- **[Usage Guide](usage.md)** - Learn how to discover and invoke skills
- **[Browse Skills](../skills/)** - Explore available skills by domain
- **[Contributing](../CONTRIBUTING.md)** - Help improve these skills

## Getting Help

- **[CockroachDB Documentation](https://www.cockroachlabs.com/docs/)** - Official CockroachDB docs
- **[Claude Code Documentation](https://claude.ai/docs)** - Claude Code features and usage
- **[GitHub Issues](https://github.com/cockroachlabs/cockroachdb-skills/issues)** - Report problems or request features
