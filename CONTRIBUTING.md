# Contributing and maintenance

Discuss substantial framework or tool changes in an issue before implementing them. Small documentation corrections can go straight to a pull request. Do not upload confidential proposals, participant data, API keys, or copyrighted paper PDFs.

## Preserve framework fidelity

Check all quadrant changes against [the model reference](references/abc-model.md). Keep Cronjé’s original framework separate from this skill’s discovery and feasibility extensions. Do not invent a publication date, treat question stems as sufficient classification, equate paradigms with methods, or present mixed methods as inherently incoherent.

`SKILL.md`, its references, and `agents/openai.yaml` are the canonical skill resources. Application adaptations must preserve researcher confirmation, evidence limits, and honest tool reporting. Update the application guide’s verification date and official links when platform behaviour changes.

## Validate changes

Use Python 3.10+ and run from the repository root:

```sh
python3 -m unittest discover -s scripts -v
python3 scripts/openalex.py --help
python3 scripts/package_skill.py
```

Existing helper tests run offline. Add behavioural coverage when changing retrieval, authentication, limits, error reporting, or content validation. Do not require live credentials for CI. Review documentation links, archive layout, and all examples. Keep the helper’s command-line interfaces stable unless a release explicitly documents a breaking change.

## Release

1. Run the validation commands and inspect the packaged files. The packaging script uses an explicit allowlist and excludes caches, source archives, and research downloads.
2. Update version-specific download links if releasing a new version. Build with `python3 scripts/package_skill.py --version VERSION`.
3. Commit the source changes. Publish a GitHub release tagged `vVERSION` at the tested commit, attaching `dist/abc-research-generator-vVERSION.zip` and its `.sha256` file.
4. Download the published asset, compare its SHA-256 checksum, and verify the skill root folder and CI result.

GitHub’s generated source archives are for repository development. The separately attached ZIP is for installing the skill. MIT licensing covers this project’s original material; external manuscripts and papers retain their own rights.
