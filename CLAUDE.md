# RealAI Plugin

This repo is a Claude Code marketplace plugin for RealAI, a residential real estate application.

## Structure

```
.claude-plugin/marketplace.json   # Plugin registry
plugins/analysts/
  .claude-plugin/plugin.json      # Plugin metadata
  agents/                         # Agent definitions
  skills/                         # Skill definitions
```

## Agents

Agents live in `plugins/analysts/agents/`. Each agent is a markdown file with a YAML frontmatter block (`name`, `description`, `model`) followed by a system prompt.

## Skills

Skills live in `plugins/analysts/skills/<skill-name>/SKILL.md`. Each skill is a markdown file with a YAML frontmatter block (`name`, `description`) followed by analytical workflows and output guidelines. More skills will be added over time.

Skills should:
- Define what data to gather and how to reason through the analysis
- Specify how the final output should be structured
- Avoid hard-coded baselines — let data drive conclusions
