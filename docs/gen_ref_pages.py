"""Generate code reference pages for mkdocstrings.

This script is executed by the mkdocs-gen-files plugin during the MkDocs build
process. It walks the source package, creates a corresponding Markdown stub for
each public module, and builds a nav.yml file so that the API reference section
is generated automatically.
"""

from pathlib import Path

import mkdocs_gen_files
import yaml

SRC_DIR = Path("pcdigitizer")
DOC_DIR = Path("api")
SKIP_MODULES = {"__main__", "__init__"}
SKIP_PREFIXES = ("_",)

nav_items: list[dict[str, str] | dict[str, list]] = []

for path in sorted(SRC_DIR.rglob("*.py")):
    module_path = path.relative_to(SRC_DIR).with_suffix("")
    doc_path = path.relative_to(SRC_DIR).with_suffix(".md")
    full_doc_path = DOC_DIR / doc_path

    parts = tuple(module_path.parts)

    if not parts:
        continue
    if parts[-1] in SKIP_MODULES:
        continue
    if any(part.startswith(prefix) for part in parts for prefix in SKIP_PREFIXES):
        continue

    qualified_name = ".".join((SRC_DIR.name, *parts))

    nav_items.append({qualified_name: doc_path.as_posix()})

    with mkdocs_gen_files.open(full_doc_path, "w") as fd:
        fd.write(f"::: {qualified_name}\n")

    mkdocs_gen_files.set_edit_path(full_doc_path, path)

with mkdocs_gen_files.open(DOC_DIR / "nav.yml", "w") as nav_fd:
    yaml.dump(nav_items, nav_fd, default_flow_style=False, sort_keys=False)
