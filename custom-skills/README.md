# Custom Skills

This directory contains custom skills for X-Agent.

## Structure

Each skill should be in its own directory with the following structure:

```
skill-name/
├── SKILL.md          # Skill definition and documentation
├── __init__.py       # Python package initialization
└── skill.py          # Skill implementation
```

## Creating a New Skill

1. Create a new directory for your skill
2. Add a SKILL.md file describing the skill
3. Implement the skill logic in skill.py
4. Test your skill thoroughly

## Examples

See the `.claude/skills/` directory for example skill implementations.
