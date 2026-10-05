"""先確認心智圖呈現實際筆記，再驗證 HTML 資料不會變成指令。"""

import re
from html.parser import HTMLParser
from pathlib import Path
from typing import override

from pydantic import TypeAdapter

from kb_store import Note
from mindmap_app import build_mindmap, build_mindmap_html


class DiagramParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.note_ids: list[str] = []
        self.category_count = 0
        self.sections: list[str] = []
        self.topics: list[str] = []
        self.svg_style = ""
        self._labels: list[str] | None = None
        self._in_title = False

    @override
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "svg":
            self.svg_style = values.get("style") or ""
        if tag == "g" and values.get("class") == "note":
            value = values.get("data-note-id")
            assert value is not None
            self.note_ids.append(value)
        if tag == "g" and values.get("class") == "category":
            self.category_count += 1
        if tag == "g" and values.get("class") == "section":
            self._labels = self.sections
        if tag == "g" and values.get("class") == "topic":
            self._labels = self.topics
        if tag == "title" and self._labels is not None:
            self._in_title = True

    @override
    def handle_data(self, data: str) -> None:
        if self._in_title and self._labels is not None:
            self._labels.append(data)
            self._labels = None
            self._in_title = False


def payload(html: str) -> list[dict[str, str]]:
    match = re.search(
        r'<script id="notes-data" type="application/json">(.*?)</script>', html, re.S
    )
    assert match is not None
    return TypeAdapter(list[dict[str, str]]).validate_json(match.group(1))


def test_diagram_groups_and_preserves_the_supplied_notes() -> None:
    notes = [
        Note(id="one.md", title="stdio", category="MCP", content="log 寫 stderr"),
        Note(id="two.md", title="Tools", category="MCP", content="工具有 schema"),
        Note(id="three.md", title="Python", category="語言", content="async await"),
    ]
    html = build_mindmap_html(notes)
    parser = DiagramParser()
    parser.feed(html)
    assert sorted(parser.note_ids) == ["one.md", "three.md", "two.md"]
    assert parser.category_count == 2
    assert payload(html) == [note.model_dump() for note in notes]
    assert "log 寫 stderr" in html
    assert "本地筆記" in html


def test_empty_diagram_explains_how_to_create_notes() -> None:
    html = build_mindmap_html([])
    parser = DiagramParser()
    parser.feed(html)
    assert parser.note_ids == []
    assert payload(html) == []
    assert "先建立筆記" in html


def test_note_content_cannot_break_out_of_the_json_script() -> None:
    malicious = '</script><script>alert("x")</script><img src=x onerror=alert(1)>'
    note = Note(
        id="unsafe.md", title="<img> & 標題", category="<分類>", content=malicious
    )
    html = build_mindmap_html([note])
    assert malicious not in html
    assert "</script><script>" not in html
    assert "<img> & 標題" not in html
    assert payload(html)[0]["content"] == malicious
    assert payload(html)[0]["title"] == note.title


def test_diagram_has_no_external_scripts_or_note_html_rendering() -> None:
    html = build_mindmap_html([Note(id="a.md", title="a", category="b", content="c")])
    assert "<script src=" not in html
    assert "<link " not in html
    assert ".innerHTML" not in html
    assert "textContent" in html


ADLER = """# 阿德勒
## 人物
- 個體心理學
## 核心概念
### 目的論
### 課題分離
## 延伸閱讀
"""


def test_single_note_expands_its_headings_into_branches() -> None:
    note = Note(id="adler.md", title="阿德勒", category="筆記", content=ADLER)
    parser = DiagramParser()
    parser.feed(build_mindmap_html([note]))
    assert parser.note_ids == ["adler.md"]
    assert parser.sections == ["人物", "核心概念", "延伸閱讀"]
    assert parser.topics == ["目的論", "課題分離"]
    assert parser.category_count == 0


def test_headings_inside_code_blocks_are_not_branches() -> None:
    content = "## 範例\n```python\n## 這是註解\n```\n## 結論\n"
    note = Note(id="code.md", title="code", category="筆記", content=content)
    parser = DiagramParser()
    parser.feed(build_mindmap_html([note]))
    assert parser.sections == ["範例", "結論"]


def test_single_note_without_subheadings_keeps_the_catalog_layout() -> None:
    note = Note(id="a.md", title="a", category="筆記", content="# 標題\n內文")
    parser = DiagramParser()
    parser.feed(build_mindmap_html([note]))
    assert parser.category_count == 1
    assert parser.sections == []


def test_multiple_notes_are_not_expanded() -> None:
    notes = [
        Note(id="a.md", title="a", category="筆記", content="## 一\n## 二"),
        Note(id="b.md", title="b", category="筆記", content="## 三"),
    ]
    parser = DiagramParser()
    parser.feed(build_mindmap_html(notes))
    assert parser.category_count == 1
    assert parser.sections == []


def test_heading_text_cannot_inject_html() -> None:
    heading = "<img src=x onerror=alert(1)> & 標題"
    note = Note(id="x.md", title="x", category="筆記", content=f"## {heading}\n")
    html = build_mindmap_html([note])
    parser = DiagramParser()
    parser.feed(html)
    assert "<img src=x" not in html
    assert parser.sections == [heading]


def test_canvas_grows_with_the_number_of_branches() -> None:
    topics = "".join(f"### 概念 {index}\n" for index in range(12))
    short = Note(id="s.md", title="s", category="筆記", content="## 一\n")
    tall = Note(id="t.md", title="t", category="筆記", content="## 核心\n" + topics)

    def canvas(note: Note) -> tuple[int, int]:
        parser = DiagramParser()
        parser.feed(build_mindmap_html([note]))
        match = re.search(r"height: (\d+)px", parser.svg_style)
        assert match is not None
        embed = build_mindmap([note]).to_json()["view"]["children"][0]
        return int(match.group(1)), int(embed["height"].removesuffix("px"))

    short_svg, short_embed = canvas(short)
    tall_svg, tall_embed = canvas(tall)
    assert short_svg == 360
    assert short_embed == 640
    assert tall_svg > short_svg
    assert tall_embed - short_embed == tall_svg - short_svg


def test_saved_mindmap_preserves_notes_and_updates_the_same_file(
    tmp_path: Path,
) -> None:
    note = Note(id="a.md", title="標題", category="筆記", content="## 初版")
    output = tmp_path / "mindmaps" / "a.html"
    app = build_mindmap([note], save_path=output)
    saved = output.read_text(encoding="utf-8")
    assert payload(saved) == [note.model_dump()]
    assert app.to_json()["view"]["children"][0]["html"] == saved

    updated = note.model_copy(update={"content": "## 新版"})
    build_mindmap([updated], save_path=output)
    assert payload(output.read_text(encoding="utf-8")) == [updated.model_dump()]
    assert list(output.parent.iterdir()) == [output]
