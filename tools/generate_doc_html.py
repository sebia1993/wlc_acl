"""Generate browser-friendly HTML copies of the Korean Markdown guides.

The renderer intentionally supports only the Markdown features used in this
project's guides so it can run on an internal Windows PC without extra packages.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from html import escape
from pathlib import Path


REPO_ROOT = Path(__file__).parent.parent
DOCS_DIR = REPO_ROOT / "docs"


@dataclass(frozen=True)
class GuideDocument:
    source_name: str
    html_name: str
    title: str


GUIDES = (
    GuideDocument("USER_GUIDE_KO.md", "USER_GUIDE_KO.html", "WLC Role ACL Collector 사용자 설명서"),
    GuideDocument("DEVELOPER_GUIDE_KO.md", "DEVELOPER_GUIDE_KO.html", "WLC Role ACL Collector 개발자 설명서"),
    GuideDocument("ERROR_CODES_KO.md", "ERROR_CODES_KO.html", "WLC Role ACL Collector 오류 코드"),
    GuideDocument("DIAGNOSTIC_MODE_KO.md", "DIAGNOSTIC_MODE_KO.html", "WLC Role ACL Collector 진단 모드"),
    GuideDocument("SECURITY_MODEL_KO.md", "SECURITY_MODEL_KO.html", "WLC Role ACL Collector 보안 모델"),
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate HTML guide files from Markdown guides.")
    parser.add_argument("--source-dir", type=Path, default=DOCS_DIR)
    parser.add_argument("--output-dir", type=Path, default=DOCS_DIR)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    for guide in GUIDES:
        source = args.source_dir / guide.source_name
        target = args.output_dir / guide.html_name
        markdown = source.read_text(encoding="utf-8")
        target.write_text(render_document(markdown, guide.title), encoding="utf-8")
        print(f"Generated {target}")
    return 0


def render_document(markdown: str, title: str) -> str:
    body = render_markdown(markdown)
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>
    :root {{
      --bg: #f3f6fa;
      --panel: #ffffff;
      --text: #172033;
      --muted: #667085;
      --line: #d6dde7;
      --accent: #0f6cbd;
      --code-bg: #111827;
      --code-text: #e5edf7;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      background: var(--bg);
      color: var(--text);
      font-family: "Segoe UI", "Malgun Gothic", Arial, sans-serif;
      line-height: 1.65;
      margin: 0;
      padding: 24px;
    }}
    main {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 10px;
      box-shadow: 0 12px 30px rgba(15, 23, 42, 0.08);
      margin: 0 auto;
      max-width: 1120px;
      padding: 34px;
    }}
    h1, h2, h3 {{ line-height: 1.3; }}
    h1 {{
      border-bottom: 3px solid var(--accent);
      font-size: 28px;
      margin: 0 0 24px;
      padding-bottom: 14px;
    }}
    h2 {{
      border-top: 1px solid var(--line);
      font-size: 22px;
      margin: 34px 0 14px;
      padding-top: 24px;
    }}
    h3 {{ font-size: 18px; margin: 24px 0 10px; }}
    p {{ margin: 10px 0; }}
    a {{ color: var(--accent); }}
    ul, ol {{ padding-left: 24px; }}
    li {{ margin: 5px 0; }}
    code {{
      background: #eef3f8;
      border: 1px solid #d8e2ed;
      border-radius: 5px;
      font-family: Consolas, "Cascadia Mono", monospace;
      padding: 1px 5px;
    }}
    pre {{
      background: var(--code-bg);
      border-radius: 8px;
      color: var(--code-text);
      overflow-x: auto;
      padding: 14px 16px;
    }}
    pre code {{
      background: transparent;
      border: 0;
      color: inherit;
      padding: 0;
    }}
    table {{
      border-collapse: collapse;
      margin: 14px 0 22px;
      width: 100%;
    }}
    th, td {{
      border: 1px solid var(--line);
      padding: 9px 10px;
      text-align: left;
      vertical-align: top;
    }}
    th {{ background: #edf4fb; }}
    blockquote {{
      border-left: 4px solid var(--accent);
      color: var(--muted);
      margin: 14px 0;
      padding: 4px 0 4px 14px;
    }}
    .generated-note {{
      color: var(--muted);
      font-size: 12px;
      margin-top: 34px;
    }}
    @media print {{
      body {{ background: #ffffff; padding: 0; }}
      main {{ border: 0; box-shadow: none; max-width: none; }}
    }}
  </style>
</head>
<body>
  <main>
{body}
    <p class="generated-note">Generated from Markdown for browser viewing.</p>
  </main>
</body>
</html>
"""


def render_markdown(markdown: str) -> str:
    lines = markdown.splitlines()
    html: list[str] = []
    paragraph: list[str] = []
    list_type: str | None = None
    in_code = False
    code_lines: list[str] = []

    def flush_paragraph() -> None:
        nonlocal paragraph
        if paragraph:
            html.append(f"    <p>{inline_format(' '.join(paragraph))}</p>")
            paragraph = []

    def close_list() -> None:
        nonlocal list_type
        if list_type:
            html.append(f"    </{list_type}>")
            list_type = None

    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()

        if stripped.startswith("```"):
            flush_paragraph()
            close_list()
            if in_code:
                html.append("    <pre><code>" + escape("\n".join(code_lines)) + "</code></pre>")
                code_lines = []
                in_code = False
            else:
                in_code = True
            index += 1
            continue

        if in_code:
            code_lines.append(line)
            index += 1
            continue

        if not stripped:
            flush_paragraph()
            close_list()
            index += 1
            continue

        if _is_table_start(lines, index):
            flush_paragraph()
            close_list()
            table_lines = [lines[index], lines[index + 1]]
            index += 2
            while index < len(lines) and lines[index].strip().startswith("|"):
                table_lines.append(lines[index])
                index += 1
            html.append(render_table(table_lines))
            continue

        heading_match = re.match(r"^(#{1,3})\s+(.+)$", stripped)
        if heading_match:
            flush_paragraph()
            close_list()
            level = len(heading_match.group(1))
            html.append(f"    <h{level}>{inline_format(heading_match.group(2))}</h{level}>")
            index += 1
            continue

        unordered_match = re.match(r"^[-*]\s+(.+)$", stripped)
        ordered_match = re.match(r"^\d+\.\s+(.+)$", stripped)
        if unordered_match or ordered_match:
            flush_paragraph()
            wanted = "ul" if unordered_match else "ol"
            if list_type != wanted:
                close_list()
                html.append(f"    <{wanted}>")
                list_type = wanted
            item_text = unordered_match.group(1) if unordered_match else ordered_match.group(1)
            html.append(f"      <li>{inline_format(item_text)}</li>")
            index += 1
            continue

        if stripped.startswith(">"):
            flush_paragraph()
            close_list()
            html.append(f"    <blockquote>{inline_format(stripped.lstrip('> ').strip())}</blockquote>")
            index += 1
            continue

        paragraph.append(stripped)
        index += 1

    flush_paragraph()
    close_list()
    if in_code:
        html.append("    <pre><code>" + escape("\n".join(code_lines)) + "</code></pre>")
    return "\n".join(html)


def render_table(lines: list[str]) -> str:
    header = _split_table_row(lines[0])
    rows = [_split_table_row(line) for line in lines[2:]]
    thead = "".join(f"<th>{inline_format(cell)}</th>" for cell in header)
    body_rows = []
    for row in rows:
        cells = "".join(f"<td>{inline_format(cell)}</td>" for cell in row)
        body_rows.append(f"      <tr>{cells}</tr>")
    return "\n".join(
        [
            "    <table>",
            f"      <thead><tr>{thead}</tr></thead>",
            "      <tbody>",
            *body_rows,
            "      </tbody>",
            "    </table>",
        ]
    )


def inline_format(value: str) -> str:
    escaped = escape(value)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    return escaped


def _is_table_start(lines: list[str], index: int) -> bool:
    if index + 1 >= len(lines):
        return False
    current = lines[index].strip()
    separator = lines[index + 1].strip()
    return current.startswith("|") and bool(re.match(r"^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$", separator))


def _split_table_row(line: str) -> list[str]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split("|")]


if __name__ == "__main__":
    raise SystemExit(main())
