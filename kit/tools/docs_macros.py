"""The docs site's macros (Zensical's macros, configured in mkdocs.yml, as mkdocs-macros had them): pages that
are rendered from their sources when the site is built, so no copy of them is committed and none can go stale.

    .venv/bin/zensical serve      # the site at http://127.0.0.1:8000
    .venv/bin/zensical build      # into site/

A page opts in with `render_macros: true` in its front matter, so text that merely looks like a template in
any other page is left alone.
"""
import json
import sys
from pathlib import Path

# Zensical imports this file rather than running it, so its own folder (kit/tools: build_docs, model_appendix) is not
# on the path by itself; kit/ is, for camkit
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent)]
import build_docs  # noqa: E402
import model_appendix  # noqa: E402
from camkit import definitions  # noqa: E402

ROOT = HERE.parents[1]


def every() -> list:
    """Every definition (editor/definitions/<model>_fw<fw>.json), by file name."""
    return [doc for _, doc in definitions.every(evidence=False)]


def page_definition(page_path: str) -> dict:
    """The definition whose layout names this page (layouts[0].doc), else the reference one."""
    for doc in every():
        if page_path and (doc["layouts"][0].get("doc") or "").removeprefix("docs/") == page_path:
            return doc
    return definitions.load_public(definitions.REFERENCE)


def define_env(env):
    @env.macro
    def status_md() -> str:
        """docs/STATUS.md: per definition, counts, the file's bytes by state, what is left."""
        return "\n".join(build_docs.status_md(doc) for doc in every())

    @env.macro
    def memory_map_md() -> str:
        """docs/MEMORY_MAP.md: per definition with a sample, every record of it and what it holds."""
        return "\n".join(build_docs.memory_map_md(doc) for doc in every() if definitions.sample(doc))

    @env.macro
    def appendix_measured() -> str:
        """A model page's measured block (identity, volatile records, the reset test), from the definition whose
        layout names the page."""
        doc = page_definition(getattr(getattr(env, "page", None), "path", "") or "")
        return model_appendix.measured(doc, doc["layouts"][0]).replace(model_appendix.START, "").replace(model_appendix.END, "")

    @env.macro
    def schema_fields(name: str, part: str = "") -> str:
        """The fields a JSON Schema in schemas/ describes, as a table: its own words, so no list of them is kept by hand."""
        s = json.loads((ROOT / "schemas" / f"{name}.schema.json").read_text(encoding="utf-8"))
        node = s
        for step in [p for p in part.split("/") if p]:
            node = node[step]
        req = set(node.get("required") or [])
        rows = ["| Field | Type | Required | Holds |", "|---|---|---|---|"]
        for k, v in (node.get("properties") or {}).items():
            t = v.get("type") or ("one of " + ", ".join(map(str, v["enum"])) if "enum" in v else v.get("$ref", "").split("/")[-1])
            t = " or ".join(t) if isinstance(t, list) else t
            rows.append(f"| `{k}` | {t} | {'yes' if k in req else ''} | {build_docs.esc(v.get('description', ''))} |")
        return "\n".join(rows)
