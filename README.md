# ABC Research Generator

A research design coach that applies Johannes Cronjé’s ABC framework to align aims, beliefs, and methods into a coherent brief.

Researchers often struggle to bridge the gap between a vague topic and a defensible, framework-aligned study design. This skill applies Cronjé’s Aim–Belief–Concern (ABC) framework to move you from a seed idea or paper to a coherent research brief. It checks for mismatches between your intended contribution, philosophical assumptions, questions, and methods.

## Get started

1. Download **abc-research-generator-v1.0.0.zip** from the [v1.0.0 release](https://github.com/carlbadenhorst42/abc-research-generator/releases/tag/v1.0.0).
2. Follow the [application guide](docs/application-guide.md) for **ChatGPT, Claude, Claude Code, Codex, or Gemini**.
3. Bring a DOI, paper, or topic, and begin a guided conversation. No API key is needed for coaching with supplied material.

The release ZIP contains the installable `abc-research-generator/` skill folder. GitHub’s automatically generated “Source code” ZIP contains the entire repository and is not the same installation package.

## What it does

- **Seed analysis** extracts aims, methods, and limitations from a DOI, title, or uploaded paper to anchor your new study. Claims depend on the text available.
- **ABC profiling** guides you through identifying your study’s Aim, Belief (subjective/objective), and Concern (abstract/concrete).
- **Question pairing** generates specific, answerable research questions mapped to one of four outcome quadrants: Map, Explanation, Solution, or Model.
- **Literature refinement** uses OpenAlex, when accessible, to challenge your proposed questions with an initial selection of 8–12 relevant works, grounding your contribution.
- **Feasibility checking** checks whether your proposed evidence and methods can support the claims you intend to make.

## How it works

1. Supply a research seed such as a DOI, a PDF paper, or a specific topic of interest.
2. Engage in a targeted dialogue to define your study’s philosophical stance using the ABC framework.
3. Review and refine a pair of research questions generated to match your specific quadrant.
4. Run a literature-based stress test to identify competing work or needed revisions.
5. Receive a research brief connecting the confirmed questions to evidence, methods, scope, and remaining decisions.

The coach asks one or two consequential questions at a time. It keeps confirmed choices, provisional interpretations, and unresolved decisions distinct.

## The ABC quadrants

| Aim | Belief | Concern | Question pair | Expected output |
|---|---|---|---|---|
| Explore | Subjective | Abstract | What…? + How does…? | Map |
| Explain | Subjective | Concrete | How does…? + Why…? | Explanation |
| Develop | Objective | Concrete | Why…? + How should…? | Solution |
| Describe | Objective | Abstract | What…? + How should…? | Model |

These are the model’s distinctions, not a qualitative/quantitative split or a recipe for selecting methods. Question meaning matters more than its opening words. Multiple aims can use sequential ABC cycles.

## Frameworks & tools

This skill uses Cronjé’s Aim–Belief–Concern framework and integrates with OpenAlex through a standard-library Python helper for metadata enrichment and graph discovery. It supports Consensus for complementary paper discovery when that connector is available. Literature refinement and method-alignment checks extend the original framework; they are not attributed to Cronjé.

See the [framework interpretation](references/abc-model.md), [research strategies](references/openalex-strategies.md), and [brief template](references/research-design-brief.md).

## Why this beats prompting it yourself

Generic prompts can lose internal consistency as a research conversation develops. This skill makes the ABC mappings explicit and repeatedly checks whether the proposed questions, beliefs, evidence, and methods fit the intended contribution. It treats the model’s mappings as constraints within an ABC session, while keeping your philosophical choices visible and open to correction.

Alignment does not guarantee a valid study. Mixed methods, pragmatism, and other approaches are not inherently incoherent; a departure from ABC should be explained rather than forced into a quadrant.

## Use cases

- Drafting the research design section for a thesis or dissertation proposal.
- Repairing a research focus criticised for being “too broad” or “unclear.”
- Translating a theoretical interest into a concrete intervention or solution.
- Checking alignment between an intended outcome and a chosen methodology.

## Example prompts

After installation, use the appropriate invocation for your application:

**Topic:** “Use ABC Research Generator to help me scope a study of how first-year students use peer feedback in an online design studio. Start by clarifying the contribution I want to make.”

**DOI:** “Use ABC Research Generator with DOI 10.3102/0013189X032001005 as a possible seed. Verify its identity and access level before analysing it; help me choose a distinct contribution.”

**Uploaded paper:** “Read the attached paper as my research seed. Separate the authors’ claims from your interpretation, then coach me toward my own ABC profile.”

**Repair:** “My supervisor says my proposal is too broad. I want to understand students’ experiences and design an intervention in one semester. Help me decide whether I need sequential ABC cycles and narrow the questions.”

See the [annotated illustrative brief](examples/illustrative-brief.md). It contains no claimed research findings or completed literature search.

## Known limitations

This skill does not conduct full systematic reviews or write complete study protocols. Analysis without full-text access is provisional and relies on metadata or abstracts. Sparse search results do not establish novelty; citation counts do not establish validity. The framework’s educational-technology and social-science origins limit automatic generalisation to other fields.

Uploading the files does not automatically enable Python, network access, OpenAlex, or Consensus. Tool availability and account policies vary. Without those tools, continue with supplied text and clearly labelled unexecuted search suggestions.

## Development

Python 3.10+ is the supported baseline for this repository; the helper has no third-party dependencies.

```sh
python3 -m unittest discover -s scripts -v
python3 scripts/openalex.py --help
python3 scripts/package_skill.py
```

The packaging command creates the release ZIP and its SHA-256 checksum in `dist/`. See [CONTRIBUTING.md](CONTRIBUTING.md) for maintenance and release steps.

## Reference and attribution

Cronjé, J. C. (n.d.). *The ABC (Aim, Belief, Concern) instant research question generator*. [Read the manuscript](https://www.learndev.org/dl/BtSM2011/Cronj%E9-The_ABC_Instant_research_question_generator.pdf).

The publication date and venue have not been verified; the `BtSM2011` URL directory alone is not treated as publication evidence. This repository includes an attributed paraphrase, not the manuscript PDF. No endorsement by Cronjé is implied.

## License

The skill, original supporting documentation, and helper code are distributed under the [MIT License](LICENSE), copyright © 2026 Carl Badenhorst. Cronjé’s manuscript and third-party papers retain their own rights; this license does not grant permission to redistribute them.
