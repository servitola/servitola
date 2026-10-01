#!/usr/bin/env python3
import base64
import json
import os
import re
import sys
import tomllib
import urllib.request
from pathlib import Path

OWNER = "servitola"
TAP = f"{OWNER}/homebrew-tap"
ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
PROJECTS = ROOT / "projects.toml"
START, END = "<!-- catalogue:start -->", "<!-- catalogue:end -->"


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


def tap_package(entry):
    source = base64.b64decode(api(f"contents/{entry['path']}")["content"]).decode()
    version = field(source, "version")
    if not version:
        url_tag = re.search(r'/v?(\d[\w.\-]*?)\.(?:tar\.gz|zip)"', source)
        version = url_tag.group(1) if url_tag else "HEAD"
    commit = api(f"commits?path={entry['path']}&per_page=1")[0]["commit"]
    # Nightly builds are versioned <marketing>-<date>.<sha>; the date is shown separately.
    return {"version": version.split("-")[0], "date": commit["committer"]["date"][:10]}


def tap_packages():
    return {
        entry["name"].removesuffix(".rb"): tap_package(entry)
        for folder in ("Casks", "Formula")
        for entry in api(f"contents/{folder}")
        if entry["name"].endswith(".rb")
    }


def row(item, packages):
    title = f"**{item['name']}**"
    if repo := item.get("repo"):
        title = f"**[{item['name']}](https://github.com/{OWNER}/{repo}#readme)**"
    line = f"- {item['emoji']} {title} - {item['pitch']}"
    if token := item.get("tap"):
        package = packages[token]
        line += f"<br><sub>`brew install {OWNER}/tap/{token}` · {package['version']} · {package['date']}</sub>"
    return line


def render(groups, packages):
    blocks = [
        "\n".join([f"### {group['title']}", "", *(row(item, packages) for item in group["item"])])
        for group in groups
    ]
    return "\n\n".join(blocks)


def main():
    projects = tomllib.loads(PROJECTS.read_text())
    packages = tap_packages()
    listed = {item["tap"] for group in projects["group"] for item in group["item"] if "tap" in item}
    if unknown := listed - packages.keys():
        sys.exit(f"{PROJECTS.name}: not in the tap: {', '.join(sorted(unknown))}")
    if missing := packages.keys() - listed - set(projects["hidden"]):
        sys.exit(f"{PROJECTS.name}: tap packages neither listed nor hidden: {', '.join(sorted(missing))}")
    readme = README.read_text()
    if START not in readme or END not in readme:
        sys.exit(f"{README}: markers {START} / {END} not found")
    head, rest = readme.split(START, 1)
    _, tail = rest.split(END, 1)
    README.write_text(f"{head}{START}\n{render(projects['group'], packages)}\n{END}{tail}")


if __name__ == "__main__":
    main()
