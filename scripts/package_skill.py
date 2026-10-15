"""Build an installable skill archive from an explicit resource allowlist."""
import argparse
import hashlib
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
RESOURCES = (
    "SKILL.md", "agents/openai.yaml", "references/abc-model.md",
    "references/openalex-strategies.md", "references/research-design-brief.md",
    "scripts/openalex.py", "LICENSE", "README.md", "docs/application-guide.md",
    "examples/illustrative-brief.md", "CONTRIBUTING.md",
    "scripts/package_skill.py", "scripts/test_openalex.py",
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", default="1.0.0")
    args = parser.parse_args()
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:-[a-zA-Z0-9.-]+)?", args.version):
        parser.error("version must be a semantic version such as 1.0.0")
    for relative in RESOURCES:
        if not (ROOT / relative).is_file():
            parser.error(f"missing resource: {relative}")
    output_dir = ROOT / "dist"
    output_dir.mkdir(exist_ok=True)
    output = output_dir / f"abc-research-generator-v{args.version}.zip"
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for relative in RESOURCES:
            info = zipfile.ZipInfo(f"abc-research-generator/{relative}", (2026, 10, 15, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, (ROOT / relative).read_bytes())
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    checksum = output.with_suffix(output.suffix + ".sha256")
    checksum.write_text(f"{digest}  {output.name}\n")
    print(output)
    print(checksum)


if __name__ == "__main__":
    main()
