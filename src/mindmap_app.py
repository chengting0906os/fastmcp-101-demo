"""將筆記組成唯讀心智圖；MCP Apps 的公開接線留給學習者。"""

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from html import escape
from pathlib import Path

from prefab_ui.app import PrefabApp
from prefab_ui.components import Embed

from kb_store import Note

# svg 以外（標題列、詳情區）佔用的 Embed 高度。
_CHROME_HEIGHT = 280
_MIN_CANVAS_HEIGHT = 360
_HEADING = re.compile(r"^(#{2,3})\s+(.+?)\s*#*\s*$")


@dataclass
class _Section:
    title: str
    topics: list[str] = field(default_factory=list)


def _node(x: int, y: float, label: str, kind: str, note_id: str = "") -> str:
    width = 200 if kind in ("root", "category") else 280
    attributes = (
        f' tabindex="0" role="button" data-note-id="{escape(note_id, quote=True)}"'
        if kind == "note"
        else ""
    )
    short_label = label if len(label) <= 18 else label[:17] + "…"
    return (
        f'<g class="{kind}" transform="translate({x},{y})"{attributes}>'
        f"<title>{escape(label)}</title>"
        f'<rect x="{-width / 2}" y="-24" width="{width}" height="48" rx="16"/>'
        f'<text text-anchor="middle" dominant-baseline="middle">'
        f"{escape(short_label)}</text></g>"
    )


def _edge(x: int, y: float, end_x: int, end_y: float) -> str:
    middle = (x + end_x) / 2
    return f'<path d="M {x} {y} C {middle} {y}, {middle} {end_y}, {end_x} {end_y}"/>'


def _sections(content: str) -> list[_Section]:
    """`##` 成為分支、`###` 掛在前一個 `##` 下；沒有上層的 `###` 自己成為分支。"""
    sections: list[_Section] = []
    is_in_code_block = False
    for line in content.splitlines():
        if line.lstrip().startswith("```"):
            is_in_code_block = not is_in_code_block
            continue
        match = None if is_in_code_block else _HEADING.match(line)
        if match is None:
            continue
        level, title = match.groups()
        if level == "###" and sections:
            sections[-1].topics.append(title)
        else:
            sections.append(_Section(title))
    return sections


def _catalog_diagram(notes: list[Note]) -> tuple[list[str], float]:
    groups: dict[str, list[Note]] = defaultdict(list)
    for note in notes:
        groups[note.category].append(note)
    height = max(360, sum(len(items) * 68 + 40 for items in groups.values()) + 70)
    root_y = height / 2
    edges: list[str] = []
    nodes = [_node(150, root_y, "本地筆記", "root")]
    cursor = 70.0
    for category, items in sorted(groups.items()):
        category_y = cursor + (len(items) - 1) * 34
        edges.append(_edge(250, root_y, 350, category_y))
        nodes.append(_node(450, category_y, category, "category"))
        for note in items:
            edges.append(_edge(550, category_y, 650, cursor))
            nodes.append(_node(790, cursor, note.title, "note", note.id))
            cursor += 68
        cursor += 40
    return edges + nodes, height


def _note_diagram(note: Note, sections: list[_Section]) -> tuple[list[str], float]:
    """單篇筆記以自己為根，往右展開章節與小節。"""
    rows = sum(max(1, len(section.topics)) for section in sections)
    height = max(360, rows * 60 + (len(sections) - 1) * 16 + 60)
    root_y = height / 2
    edges: list[str] = []
    nodes = [_node(160, root_y, note.title, "note", note.id)]
    cursor = 60.0
    for section in sections:
        section_y = cursor + (max(1, len(section.topics)) - 1) * 30
        edges.append(_edge(300, root_y, 340, section_y))
        nodes.append(_node(480, section_y, section.title, "section"))
        for topic in section.topics:
            edges.append(_edge(620, section_y, 650, cursor))
            nodes.append(_node(790, cursor, topic, "topic"))
            cursor += 60
        if not section.topics:
            cursor += 60
        cursor += 16
    return edges + nodes, height


def _render(notes: list[Note]) -> tuple[str, int]:
    """回傳 HTML 與 svg 的顯示高度，讓 Embed 跟著長高。"""
    sections = _sections(notes[0].content) if len(notes) == 1 else []
    if sections:
        elements, height = _note_diagram(notes[0], sections)
    else:
        elements, height = _catalog_diagram(notes)
    canvas_height = max(_MIN_CANVAS_HEIGHT, round(height * 0.75))
    diagram = (
        f'<svg id="diagram" viewBox="0 0 960 {height}" '
        f'style="height: {canvas_height}px" '
        'aria-label="本地筆記心智圖">' + "".join(elements) + "</svg>"
    )
    # JSON 仍能解析回原文，但不能終止 script 或插入 HTML。
    data = json.dumps([note.model_dump() for note in notes], ensure_ascii=False)
    for character, escaped in [("<", "\\u003c"), (">", "\\u003e"), ("&", "\\u0026")]:
        data = data.replace(character, escaped)
    template = Path(__file__).with_name("mindmap.html").read_text(encoding="utf-8")
    html = template.replace("__DIAGRAM__", diagram).replace("__NOTES_DATA__", data)
    return html, canvas_height


def build_mindmap_html(notes: list[Note]) -> str:
    return _render(notes)[0]


def build_mindmap(notes: list[Note], save_path: Path | None = None) -> PrefabApp:
    html, canvas_height = _render(notes)
    if save_path is not None:
        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_path.write_text(html, encoding="utf-8")
    with PrefabApp(title="本地筆記心智圖") as app:
        Embed(
            html=html,
            width="100%",
            height=f"{_CHROME_HEIGHT + canvas_height}px",
            sandbox="allow-scripts",
        )
    return app
