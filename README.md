# PopAI Presentation Skills

[PopAI](https://www.popai.pro) creates presentations from a topic and reference materials. Its built-in `deep_research` tool can search the web and collect information needed for a slide deck. Describe online research needs and relevant URLs in `--query`.

This repository provides three skills for generating presentations through the PopAI API. All support reference materials and deliver a PowerPoint (.pptx) file. The beta skill supports initial generation and download only.

If the slides depend on local materials, you **must upload those materials through `--files`**. PopAI cannot read the caller's local filesystem or files merely mentioned by name or path in `--query`; web research cannot supply missing local information. Without uploading the required files, PopAI will lack the source information needed to make the requested slides.

Use `--files FILE1 FILE2 ...` to upload up to **5 local reference files per request**, including mixed formats. Files can be in **any format**, including documents, images, spreadsheets, audio, video, Markdown, and source code. Quote paths containing spaces. For example: `--files "meeting notes.md" interview.mp3 demo.mp4 main.py data.xlsx`.

## Choose a Mode

- **Have a .pptx template?** Prefer **popai-powerpoint-pptx** to create a presentation using the template's layout and styles.
- **Want image-model designs with editable PowerPoint elements, and have beta access?** Use **image-pptx-slides**.
- **Otherwise, use popai-image-slides (image-slides).** This is the recommended default for creating presentations.

| Skill | How it works | Documentation |
| --- | --- | --- |
| **popai-powerpoint-pptx** | Generates a PowerPoint presentation, with support for a custom .pptx template. | [Setup and usage](skills/popai-powerpoint-pptx/SKILL.md) |
| **popai-image-slides** | Uses image models to generate slide images, then exports them to a PowerPoint file. | [Setup and usage](skills/popai-image-slides/SKILL.md) |
| **image-pptx-slides** | Uses image models and the PowerPoint SDK to create an editable PPTX on beta. Initial generation and download only. | [Setup and usage](skills/image-pptx-slides/SKILL.md) |

See each skill's documentation for its supported operations.

## Setup

The production skills use `POPAI_ACCESS_TOKEN`. **image-pptx-slides** uses the separate `POPAI_BETA_ACCESS_TOKEN` variable for a beta account with access to [the beta environment](https://beta.01ww.org). Downloading an existing PPTX URL with the beta skill does not require a token.

For the production skills:

1. Sign up or sign in at the [PopAI Skill page](https://www.popai.pro/popai-skill).
2. Copy your **Access Token**.
3. Set it in the shell where you will run the skill:

```bash
export POPAI_ACCESS_TOKEN="<your_token>"
```

Replace `<your_token>` with your access token.

For **image-pptx-slides**, set the beta token instead:

```bash
export POPAI_BETA_ACCESS_TOKEN="<beta_access_token>"
```

See [the beta skill documentation](skills/image-pptx-slides/SKILL.md) for setup and usage.

## Support

For issues or questions, contact **customerservice@popai.pro**
