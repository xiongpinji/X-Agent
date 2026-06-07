# Skill Curator MVP

The Skill Curator closes the Hermes-style learning loop without unsafe auto-installation.

It accepts explicit skill execution evidence, computes deterministic scores, proposes improvement actions, and drafts candidate `SKILL.md` files into `.xagent/skill-curator/drafts/`.

Current guarantees:

- No LLM dependency in scoring or proposal generation.
- No generated code is executed.
- Drafts are staged only and must be reviewed before installation.
- Low success or high error rates produce `improve` proposals.
- Repeated `manual:<name>` evidence can produce a `create` proposal.

API:

- `POST /api/v1/skill-curator/analyze`
- `POST /api/v1/skill-curator/draft`

This is not a full autonomous skill marketplace. Activation, signing, review approval, and promotion into active skill folders remain explicit future steps.
