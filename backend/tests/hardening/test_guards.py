import json
import re
from pathlib import Path

from app.main import create_app

BACKEND = Path(__file__).resolve().parents[2]
EXCLUDED = re.compile(r"\bv_?l_?(?:1_?2|2_?3|3_?1)\b", re.IGNORECASE)
RAW = re.compile(
    r"\b(?:V"
    + r"L[123]|I"
    + r"L[123]|IN"
    + r"UT|OT"
    + r"I(?:_[AT])?|WT"
    + r"I|AT"
    + r"I|OL"
    + r"I|MOG"
    + r"_A|PF"
    + r"L[123])\b",
    re.IGNORECASE,
)


def source_documents() -> list[tuple[str, str]]:
    sources = [
        path
        for folder in ("app", "alembic", "scripts")
        for path in (BACKEND / folder).rglob("*.py")
    ]
    sources += list((BACKEND / "tests" / "snapshots").glob("*.json"))
    return [
        (path.relative_to(BACKEND).as_posix(), path.read_text(encoding="utf-8")) for path in sources
    ] + [("generated OpenAPI", json.dumps(create_app().openapi(), indent=2))]


def test_source_name_guard() -> None:
    failures = []
    allowed = 0
    for name, document in source_documents():
        for number, line in enumerate(document.splitlines(), 1):
            matches = list(EXCLUDED.finditer(line)) + list(RAW.finditer(line))
            if not matches:
                continue
            # Exact allowlist: the literal membership check implementing input exclusion.
            if name == "app/schemas/common.py" and line.strip().startswith("if normalized in {"):
                assert len(list(EXCLUDED.finditer(line))) == 3 and not RAW.search(line)
                allowed += 1
                continue
            failures.append(f"{name}:{number}: {', '.join(match.group() for match in matches)}")
    assert allowed == 1
    assert not failures, "Source-name guard failures:\n" + "\n".join(failures)


def test_proxy_wording_guard() -> None:
    documents = source_documents()
    documents += [
        (path.relative_to(BACKEND).as_posix(), path.read_text(encoding="utf-8"))
        for path in (BACKEND / "docs").rglob("*.md")
    ]
    documents.append(("README.md", (BACKEND / "README.md").read_text(encoding="utf-8")))
    prohibited = ["confirmed" + " fault", "fault" + " detected", "confirmed" + " failure"]
    failures = [
        f"{name}:{number}"
        for name, body in documents
        for number, line in enumerate(body.splitlines(), 1)
        if any(term in line.casefold() for term in prohibited)
    ]
    assert not failures, "Proxy wording guard failures: " + ", ".join(failures)
