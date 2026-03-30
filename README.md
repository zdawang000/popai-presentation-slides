# PopAI Presentation Skills

This repository contains reusable Cursor-style skills for generating and refining presentations with PopAI.

## Project Structure

- `skills/popai-powerpoint-pptx/SKILL.md`: skill definition and runtime instructions
- `skills/popai-powerpoint-pptx/generate_ppt.py`: CLI script used by the skill

## Quick Start

1. Get your access token from PopAI:
   - Sign up / sign in at [https://www.popai.pro/popai-skill](https://www.popai.pro/popai-skill)
   - Copy your Access Token from the PopAI Skill page
2. Export your access token:
   - `export POPAI_ACCESS_TOKEN=<your_token>`
3. Run the generator script:
   - `python3 skills/popai-powerpoint-pptx/generate_ppt.py --query "AI Development Trends Report"`

## Skill Catalog

### `popai-powerpoint-pptx`

Use this skill when you need to:

- Generate a new presentation from a topic
- Generate with reference files (`--file`)
- Generate using a custom `.pptx` template (`--tpl`)
- Modify an existing generated deck with a known `--channel-id`

See `skills/popai-powerpoint-pptx/SKILL.md` for full agent workflow and output schema.
