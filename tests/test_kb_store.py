from pathlib import Path

import pytest

from kb_store import NoteStore


def test_create_survives_new_store_instance(tmp_path: Path) -> None:
    store = NoteStore(tmp_path / "_catalog.json")
    note = store.create("mcp.md", "# MCP\nTools 做事，Resources 提供資料。", "學習")
    reopened = NoteStore(store.path)
    assert reopened.overview() == {
        "version": 1,
        "notes": [{"id": "mcp.md", "title": "MCP", "category": "學習"}],
    }
    assert reopened.search("Resources")[0].content == note.content


def test_search_matches_content_case_insensitively_and_excludes_others(
    tmp_path: Path,
) -> None:
    store = NoteStore(tmp_path / "_catalog.json")
    store.create("a.md", "# Tools\nFastMCP makes tools.")
    store.create("b.md", "# Lunch\nEat noodles.")
    assert [note.id for note in store.search("fastmcp")] == ["a.md"]
    assert store.search("not-present") == []


def test_update_changes_saved_content_and_version_but_keeps_category(
    tmp_path: Path,
) -> None:
    store = NoteStore(tmp_path / "_catalog.json")
    store.create("a.md", "# Before\nold", "學習")
    updated = store.update("a.md", "# After\nnew")
    assert updated.title == "After"
    assert updated.category == "學習"
    reopened = NoteStore(store.path)
    assert reopened.version == 2
    assert reopened.search("old") == []
    assert reopened.search("new")[0].content == "# After\nnew"


def test_missing_update_does_not_create_note(tmp_path: Path) -> None:
    store = NoteStore(tmp_path / "_catalog.json")
    with pytest.raises(ValueError, match="找不到"):
        store.update("missing.md", "hello")
    assert store.overview() == {"version": 0, "notes": []}
    assert not store.path.exists()


def test_empty_inputs_do_not_change_saved_data(tmp_path: Path) -> None:
    store = NoteStore(tmp_path / "_catalog.json")
    store.create("a.md", "# Note")
    before = store.path.read_bytes()
    with pytest.raises(ValueError):
        store.update("a.md", "   ")
    with pytest.raises(ValueError):
        store.search("   ")
    with pytest.raises(ValueError):
        store.create("b.md", "# Note", "   ")
    assert store.path.read_bytes() == before


def test_corrupted_file_is_not_silently_reset(tmp_path: Path) -> None:
    path = tmp_path / "_catalog.json"
    path.write_text("invalid json", encoding="utf-8")
    with pytest.raises(ValueError):
        NoteStore(path)
    assert path.read_text() == "invalid json"


def test_get_note_returns_the_requested_saved_note(tmp_path: Path) -> None:
    store = NoteStore(tmp_path / "_catalog.json")
    store.create("a.md", "# 語音筆記\n朗讀內容", "學習")
    assert store.get_note("a.md").content == "# 語音筆記\n朗讀內容"
    assert store.get_note("a.md").category == "學習"


def test_get_missing_note_does_not_create_data(tmp_path: Path) -> None:
    store = NoteStore(tmp_path / "_catalog.json")
    with pytest.raises(ValueError, match="找不到"):
        store.get_note("missing.md")
    assert not store.path.exists()


def test_duplicate_create_keeps_existing_disk_and_memory(tmp_path: Path) -> None:
    store = NoteStore(tmp_path / "_catalog.json")
    store.create("a.md", "# 原筆記", "學習")
    before = store.path.read_bytes()
    with pytest.raises(ValueError, match="已存在"):
        store.create("a.md", "# 不應覆蓋", "別的分類")
    assert store.path.read_bytes() == before
    assert store.version == 1
    assert store.get_note("a.md").content == "# 原筆記"
    assert store.get_note("a.md").category == "學習"


@pytest.mark.parametrize("note_id", ["", "../a.md", "/tmp/a.md", "a.txt", "a\\b.md"])
def test_invalid_filename_does_not_create_data(tmp_path: Path, note_id: str) -> None:
    store = NoteStore(tmp_path / "_catalog.json")
    with pytest.raises(ValueError, match="檔名"):
        store.create(note_id, "# Note")
    assert store.version == 0
    assert not store.path.exists()


@pytest.mark.parametrize("content", ["", "   "])
def test_blank_content_does_not_create_data(tmp_path: Path, content: str) -> None:
    store = NoteStore(tmp_path / "_catalog.json")
    with pytest.raises(ValueError, match="筆記不能空白"):
        store.create("a.md", content)
    assert store.version == 0
    assert not store.path.exists()


def test_create_trims_filename_and_category(tmp_path: Path) -> None:
    store = NoteStore(tmp_path / "_catalog.json")
    note = store.create(" a.md ", "# Note", " 學習 ")
    assert note.id == "a.md"
    assert note.category == "學習"
    assert NoteStore(store.path).get_note("a.md").content == "# Note"


def test_delete_persists_only_requested_note(tmp_path: Path) -> None:
    store = NoteStore(tmp_path / "_catalog.json")
    store.create("a.md", "# a\n第一篇")
    store.create("b.md", "# b\n第二篇")
    store.delete("a.md")
    reopened = NoteStore(store.path)
    assert reopened.version == 3
    assert [note.id for note in reopened.catalog.notes] == ["b.md"]
    assert reopened.get_note("b.md").content == "# b\n第二篇"


def test_unknown_delete_does_not_change_disk_or_memory(tmp_path: Path) -> None:
    store = NoteStore(tmp_path / "_catalog.json")
    store.create("a.md", "# 原筆記")
    before = store.path.read_bytes()
    with pytest.raises(ValueError, match="找不到筆記"):
        store.delete("missing.md")
    assert store.path.read_bytes() == before
    assert store.version == 1
    assert [note.id for note in store.catalog.notes] == ["a.md"]


def test_note_content_is_saved_as_markdown_next_to_catalog(tmp_path: Path) -> None:
    store = NoteStore(tmp_path / "_catalog.json")
    content = "# stdio 傳輸\nClient 透過 stdin/stdout 溝通。"
    store.create("stdio.md", content, "MCP 學習")
    assert (tmp_path / "stdio.md").read_text(encoding="utf-8") == content
    assert "stdin/stdout" not in store.path.read_text(encoding="utf-8")


def test_update_rewrites_the_markdown_file(tmp_path: Path) -> None:
    store = NoteStore(tmp_path / "_catalog.json")
    store.create("a.md", "# Before\nold")
    store.update("a.md", "# After\nnew")
    assert (tmp_path / "a.md").read_text(encoding="utf-8") == "# After\nnew"


def test_delete_removes_only_that_markdown_file(tmp_path: Path) -> None:
    store = NoteStore(tmp_path / "_catalog.json")
    store.create("a.md", "# a")
    store.create("b.md", "# b")
    store.delete("a.md")
    assert not (tmp_path / "a.md").exists()
    assert (tmp_path / "b.md").read_text(encoding="utf-8") == "# b"


def test_catalog_pointing_outside_folder_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "_catalog.json"
    path.write_text(
        '{"version": 1, "notes": [{"id": "../a.md", "title": "a", "category": "x"}]}',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="檔名"):
        NoteStore(path)


@pytest.mark.parametrize(
    "note_id", ["刪除", "delete", "adler", "adler.txt", "../adler.md"]
)
def test_invalid_delete_input_keeps_catalog_and_markdown(
    tmp_path: Path,
    note_id: str,
) -> None:
    store = NoteStore(tmp_path / "_catalog.json")
    store.create("adler.md", "# 阿德勒\n個體心理學")
    before_catalog = store.path.read_bytes()
    before_note = (tmp_path / "adler.md").read_bytes()
    with pytest.raises(ValueError, match="檔名必須"):
        store.delete(note_id)
    assert store.path.read_bytes() == before_catalog
    assert (tmp_path / "adler.md").read_bytes() == before_note
    assert store.version == 1
    assert store.get_note("adler.md").content == "# 阿德勒\n個體心理學"
