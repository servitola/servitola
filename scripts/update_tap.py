#!/usr/bin/env python3
import base64
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

TAP = "servitola/homebrew-tap"
README = Path(__file__).resolve().parent.parent / "README.md"
START, END = "<!-- tap:start -->", "<!-- tap:end -->"
HIDDEN = {"glasswings"}
LIMIT = 8


def api(path):
    request = urllib.request.Request(f"https://api.github.com/repos/{TAP}/{path}")
    request.add_header("Accept", "application/vnd.github+json")
    if token := os.environ.get("GITHUB_TOKEN"):
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def field(source, name):
    match = re.search(rf'^\s*{name} "([^"]+)"', source, re.M)
    return match.group(1) if match else None


def package(entry):
    source = base64.b64decode(api(f"contents/{entry['path']}")["content"]).decode()
    version = field(source, "version")
    if not version:
        url_tag = re.search(r'/v?(\d[\w.\-]*?)\.(?:tar\.gz|zip)"', source)
        version = url_tag.group(1) if url_tag else "HEAD"
    commit = api(f"commits?path={entry['path']}&per_page=1")[0]["commit"]
    return {
        "name": entry["name"].removesuffix(".rb"),
        "path": entry["path"],
        "version": version,
        "desc": field(source, "desc") or "",
        "date": commit["committer"]["date"][:10],
    }


def render(packages):
    rows = [
        f"| [`{p['name']}`](https://github.com/{TAP}/blob/main/{p['path']}) "
        f"| `{p['version']}` | {p['desc']} | {p['date']} |"
        for p in packages
    ]
    return "\n".join(["| Package | Version | What | Updated |", "| --- | --- | --- | --- |", *rows])


def main():
    entries = [
        entry
        for folder in ("Casks", "Formula")
        for entry in api(f"contents/{folder}")
        if entry["name"].endswith(".rb") and entry["name"].removesuffix(".rb") not in HIDDEN
    ]
    packages = sorted(map(package, entries), key=lambda p: p["date"], reverse=True)[:LIMIT]
    readme = README.read_text()
    if START not in readme or END not in readme:
        sys.exit(f"{README}: markers {START} / {END} not found")
    head, rest = readme.split(START, 1)
    _, tail = rest.split(END, 1)
    README.write_text(f"{head}{START}\n{render(packages)}\n{END}{tail}")


if __name__ == "__main__":
    main()
