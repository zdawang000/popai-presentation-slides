# PopAI Presentation Skills

[PopAI](https://www.popai.pro) creates presentations from a topic and optional reference materials. Its built-in research capabilities help search, collect, and organize content into a slide deck.

This repository provides two skills for generating presentations through the PopAI API. Both support reference materials and follow-up revisions, and deliver a PowerPoint (.pptx) file.

## Choose a Mode

- **Have a .pptx template?** Prefer **popai-powerpoint-pptx** to create a presentation using the template's layout and styles.
- **For all other cases, use popai-image-slides (image-slides).** This is the recommended default for creating presentations.

| Skill | How it works | Documentation |
| --- | --- | --- |
| **popai-powerpoint-pptx** | Generates a PowerPoint presentation, with support for a custom .pptx template. | [Setup and usage](skills/popai-powerpoint-pptx/SKILL.md) |
| **popai-image-slides** | Uses image models to generate slide images, then exports them to a PowerPoint file. | [Setup and usage](skills/popai-image-slides/SKILL.md) |

See each skill's documentation for generation and revision instructions.

## Setup

Both skills require the `POPAI_ACCESS_TOKEN` environment variable.

1. Sign up or sign in at the [PopAI Skill page](https://www.popai.pro/popai-skill).
2. Copy your **Access Token**.
3. Set it in the shell where you will run the skill:

```bash
export POPAI_ACCESS_TOKEN="<your_token>"
```

Replace `<your_token>` with your access token.

## Support

For issues or questions, contact **customerservice@popai.pro**
