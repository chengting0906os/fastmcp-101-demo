"""預先寫好的 MCP 驗收：按 workshop 節次執行，未完成會失敗。"""

import json
import wave
from pathlib import Path

import pytest
from fastmcp import Client
from fastmcp.client.elicitation import ElicitResult
from fastmcp.exceptions import ToolError
from mcp.types import TextContent, TextResourceContents
from test_mindmap_app import payload

import audio_helper
import server
from kb_store import NoteStore


@pytest.fixture
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> NoteStore:
    assert hasattr(server, "store"), "先完成第 2 節：建立 store 與三個筆記 tools。"
    isolated = NoteStore(tmp_path / "_catalog.json")
    monkeypatch.setattr(server, "store", isolated)
    return isolated


@pytest.mark.lesson1
async def test_greet_returns_the_requested_name() -> None:
    async with Client(server.mcp) as client:
        result = await client.call_tool("greet", {"name": "Guest"})
    assert result.data == "Hello, Guest! Welcome to MCP."


@pytest.mark.lesson2
async def test_tools_list_contains_the_basic_tools() -> None:
    async with Client(server.mcp) as client:
        names = {tool.name for tool in await client.list_tools()}
    basic = {"greet", "create_note", "search_notes", "update_note"}
    assert basic <= names <= basic | {"delete_note", "make_audio", "show_mindmap"}, (
        "第 2 節需要四個基本 tools；第 5、6 節才加入語音和心智圖。"
    )


@pytest.mark.lesson2
async def test_create_search_and_update_work_through_mcp(store: NoteStore) -> None:
    async with Client(server.mcp) as client:
        await client.call_tool(
            "create_note",
            {
                "note_id": "stdio.md",
                "content": "# MCP 基本概念\nstdio 使用 stdin/stdout",
                "category": "學習",
            },
        )
        found = await client.call_tool("search_notes", {"query": "stdio"})
        assert [note.id for note in found.data] == ["stdio.md"]
        await client.call_tool(
            "update_note",
            {
                "note_id": "stdio.md",
                "content": "# 更新版\n新的 MCP 筆記內容",
            },
        )
        updated = await client.call_tool("search_notes", {"query": "新的 MCP"})
    assert updated.data[0].content == "# 更新版\n新的 MCP 筆記內容"
    assert NoteStore(store.path).version == 2


@pytest.mark.lesson3
async def test_resource_exposes_the_saved_catalog(store: NoteStore) -> None:
    async with Client(server.mcp) as client:
        await client.call_tool(
            "create_note",
            {
                "note_id": "stdio.md",
                "content": "# MCP 基本概念\nstdio 使用 stdin/stdout",
                "category": "學習",
            },
        )
        assert "kb://overview" in {str(r.uri) for r in await client.list_resources()}
        contents = await client.read_resource("kb://overview")
    assert isinstance(contents[0], TextResourceContents)
    assert contents[0].mime_type == "application/json"
    assert "MCP 基本概念" in contents[0].text
    assert "\\u" not in contents[0].text
    assert json.loads(contents[0].text) == store.overview()


@pytest.mark.lesson3
async def test_prompt_uses_the_question_without_creating_notes(
    store: NoteStore,
) -> None:
    async with Client(server.mcp) as client:
        assert [p.name for p in await client.list_prompts()] == ["answer_from_notes"]
        for question in ["stdio 是什麼？", "Tool 是什麼？"]:
            result = await client.get_prompt(
                "answer_from_notes", {"question": question}
            )
            content = result.messages[0].content
            assert isinstance(content, TextContent)
            assert question in content.text
    assert store.version == 0
    assert not store.path.exists()


@pytest.mark.lesson4
async def test_delete_asks_for_filename_before_removing_only_that_note(
    store: NoteStore,
) -> None:
    store.create("stdio.md", "# stdio\nstdin/stdout", "學習")
    store.create("mcp.md", "# MCP\n筆記內容", "學習")
    before = store.path.read_bytes()
    questions: list[str] = []

    async def answer(
        message: str,
        response_type: object,
        params: object,
        context: object,
    ) -> ElicitResult[dict[str, str]]:
        questions.append(message)
        assert store.path.read_bytes() == before, "收到人的回答前不能刪除。"
        assert store.version == 2
        return ElicitResult(action="accept", content={"filename": " stdio.md "})

    async with Client(server.mcp, elicitation_handler=answer, mode="auto") as client:
        result = await client.call_tool("delete_note", {})
        found = await client.call_tool("search_notes", {"query": "stdin/stdout"})
    assert len(questions) == 1
    assert "檔名" in questions[0]
    assert "已刪除" in result.data and "stdio.md" in result.data
    assert found.data == []
    reopened = NoteStore(store.path)
    assert reopened.version == 3
    assert {note.id for note in reopened.catalog.notes} == {"mcp.md"}


@pytest.mark.lesson4
@pytest.mark.parametrize("action", ["cancel", "decline"])
async def test_cancelling_or_declining_delete_leaves_notes_unchanged(
    store: NoteStore,
    action: str,
) -> None:
    store.create("mcp.md", "# MCP\n筆記內容", "學習")
    before = store.path.read_bytes()
    questions: list[str] = []

    async def answer(
        message: str,
        response_type: object,
        params: object,
        context: object,
    ) -> ElicitResult[dict[str, str]]:
        questions.append(message)
        if action == "cancel":
            return ElicitResult(action="cancel")
        return ElicitResult(action="decline")

    async with Client(server.mcp, elicitation_handler=answer, mode="auto") as client:
        result = await client.call_tool("delete_note", {})
    assert len(questions) == 1
    assert ("已取消" if action == "cancel" else "已拒絕") in result.data
    assert store.path.read_bytes() == before
    assert store.version == 1


@pytest.mark.lesson5
async def test_audio_stage_exposes_five_core_tools() -> None:
    async with Client(server.mcp) as client:
        names = {tool.name for tool in await client.list_tools()}
    core = {
        "greet",
        "create_note",
        "search_notes",
        "update_note",
        "make_audio",
    }
    assert core <= names <= core | {"delete_note", "show_mindmap"}


@pytest.mark.lesson5
async def test_audio_tool_saves_wave_and_reports_real_mcp_progress(
    store: NoteStore,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store.create("voice.md", "# 語音筆記\n\n第一段內容\n\n第二段內容", "學習")
    monkeypatch.setattr(server, "ROOT", tmp_path)
    before = store.path.read_bytes()
    spoken: list[str] = []
    events: list[tuple[float, float | None, str | None]] = []

    async def speak(text: str, path: Path) -> None:
        spoken.append(text)
        with wave.open(str(path), "wb") as audio:
            audio.setparams((1, 2, 22050, 0, "NONE", "not compressed"))
            audio.writeframes(b"\x01\x00" * 20)

    async def progress(
        current: float,
        total: float | None,
        message: str | None,
    ) -> None:
        assert len(spoken) >= current
        events.append((current, total, message))

    # 只替換作業系統的語音引擎；tool、分段、合併、保存與 MCP 通知都實際執行。
    monkeypatch.setattr(audio_helper, "_speak", speak)
    async with Client(server.mcp, progress_handler=progress) as client:
        result = await client.call_tool("make_audio", {"note_id": "voice.md"})
    output = Path(result.data)
    assert output == tmp_path / "local_kb/audio/voice.wav"
    assert spoken == ["語音筆記", "第一段內容", "第二段內容"]
    assert [(n, total) for n, total, _ in events] == [(1, 3), (2, 3), (3, 3)]
    assert "已保存" in (events[-1][2] or "")
    with wave.open(str(output), "rb") as audio:
        assert audio.getnframes() == 60
    assert store.version == 1, "製作音檔不更動筆記目錄。"
    assert store.path.read_bytes() == before


@pytest.mark.lesson5
async def test_unknown_note_is_rejected_before_audio_generation(
    store: NoteStore,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(server, "ROOT", tmp_path)

    async def unexpected(text: str, path: Path) -> None:
        raise AssertionError("不存在的筆記不能送去合成。")

    monkeypatch.setattr(audio_helper, "_speak", unexpected)
    async with Client(server.mcp) as client:
        with pytest.raises(ToolError, match="找不到筆記"):
            await client.call_tool("make_audio", {"note_id": "missing.md"})
    assert not (tmp_path / "local_kb" / "audio").exists()


@pytest.mark.lesson4
@pytest.mark.parametrize("content", [{}, {"filename": ""}, {"filename": "   "}])
async def test_blank_delete_filename_keeps_existing_notes(
    store: NoteStore,
    content: dict[str, str],
) -> None:
    store.create("mcp.md", "# MCP\n筆記內容", "學習")
    before = store.path.read_bytes()

    async def answer(
        message: str,
        response_type: object,
        params: object,
        context: object,
    ) -> ElicitResult[dict[str, str]]:
        return ElicitResult(action="accept", content=content)

    async with Client(server.mcp, elicitation_handler=answer, mode="auto") as client:
        with pytest.raises(ToolError, match="檔名不能空白"):
            await client.call_tool("delete_note", {})
    assert store.path.read_bytes() == before
    assert store.version == 1


@pytest.mark.lesson2
async def test_failed_update_leaves_catalog_unchanged(store: NoteStore) -> None:
    async with Client(server.mcp) as client:
        await client.call_tool(
            "create_note",
            {
                "note_id": "stdio.md",
                "content": "# MCP 基本概念\nstdio 使用 stdin/stdout",
                "category": "學習",
            },
        )
        before = store.path.read_bytes()
        with pytest.raises(ToolError, match="找不到筆記"):
            await client.call_tool(
                "update_note", {"note_id": "missing.md", "content": "不存在的筆記"}
            )
    assert store.path.read_bytes() == before
    assert store.version == 1


@pytest.mark.lesson2
async def test_duplicate_create_does_not_overwrite_saved_note(store: NoteStore) -> None:
    async with Client(server.mcp) as client:
        await client.call_tool(
            "create_note",
            {"note_id": "a.md", "content": "# 原筆記", "category": "學習"},
        )
        before = store.path.read_bytes()
        with pytest.raises(ToolError, match="已存在"):
            await client.call_tool(
                "create_note", {"note_id": "a.md", "content": "# 不應覆蓋"}
            )
    assert store.path.read_bytes() == before
    assert store.get_note("a.md").content == "# 原筆記"
    assert store.version == 1


@pytest.mark.lesson6
async def test_apps_tool_declares_a_readable_ui_resource() -> None:
    async with Client(server.mcp) as client:
        tools = await client.list_tools()
        assert {tool.name for tool in tools} == {
            "greet",
            "create_note",
            "search_notes",
            "update_note",
            "delete_note",
            "make_audio",
            "show_mindmap",
        }
        tool = next(tool for tool in tools if tool.name == "show_mindmap")
        assert tool.meta is not None
        uri = tool.meta["ui"]["resourceUri"]
        assert uri.startswith("ui://")
        resources = await client.list_resources()
        assert {str(resource.uri) for resource in resources} == {"kb://overview", uri}
        contents = await client.read_resource(uri)
    assert isinstance(contents[0], TextResourceContents)
    assert contents[0].mime_type == "text/html;profile=mcp-app"
    assert "<html" in contents[0].text.lower()


@pytest.mark.lesson6
async def test_mindmap_filters_notes_without_changing_the_catalog(
    store: NoteStore,
) -> None:
    async with Client(server.mcp) as client:
        await client.call_tool(
            "create_note",
            {
                "note_id": "stdio.md",
                "content": "# MCP 基本概念\nstdio 使用 stdin/stdout",
                "category": "學習",
            },
        )
        await client.call_tool(
            "create_note", {"note_id": "meeting.md", "content": "# 會議\n星期三分享"}
        )
        before = store.path.read_bytes()
        result = await client.call_tool("show_mindmap", {"query": "stdio"})
    assert result.structured_content is not None
    component = result.structured_content["view"]["children"][0]
    assert component["type"] == "Embed"
    assert component["sandbox"] == "allow-scripts"
    assert payload(component["html"]) == [store.get_note("stdio.md").model_dump()]
    assert store.path.read_bytes() == before
    assert store.version == 2


@pytest.mark.lesson6
async def test_empty_mindmap_does_not_create_a_catalog(
    store: NoteStore,
) -> None:
    async with Client(server.mcp) as client:
        result = await client.call_tool("show_mindmap", {})
    assert result.structured_content is not None
    html = result.structured_content["view"]["children"][0]["html"]
    assert payload(html) == []
    assert "先建立筆記" in html
    assert store.version == 0
    assert not store.path.exists()


@pytest.mark.lesson4
@pytest.mark.parametrize(
    ("filename", "error"),
    [("missing.md", "找不到筆記"), ("../mcp.md", "檔名必須")],
)
async def test_unknown_delete_filename_keeps_existing_notes(
    store: NoteStore,
    filename: str,
    error: str,
) -> None:
    store.create("mcp.md", "# MCP\n筆記內容", "學習")
    before = store.path.read_bytes()

    async def answer(
        message: str,
        response_type: object,
        params: object,
        context: object,
    ) -> ElicitResult[dict[str, str]]:
        return ElicitResult(action="accept", content={"filename": filename})

    async with Client(server.mcp, elicitation_handler=answer, mode="auto") as client:
        with pytest.raises(ToolError, match=error):
            await client.call_tool("delete_note", {})
    assert store.path.read_bytes() == before
    assert store.get_note("mcp.md").content == "# MCP\n筆記內容"
    assert store.version == 1


@pytest.mark.lesson4
@pytest.mark.parametrize("filename", ["刪除", "delete", "adler", "adler.txt"])
async def test_delete_rejects_human_input_that_is_not_a_markdown_filename(
    store: NoteStore,
    filename: str,
) -> None:
    store.create("adler.md", "# 阿德勒\n個體心理學")
    before_catalog = store.path.read_bytes()
    note_path = store.path.parent / "adler.md"
    before_note = note_path.read_bytes()
    questions: list[str] = []

    async def answer(
        message: str,
        response_type: object,
        params: object,
        context: object,
    ) -> ElicitResult[dict[str, str]]:
        questions.append(message)
        return ElicitResult(action="accept", content={"filename": filename})

    async with Client(server.mcp, elicitation_handler=answer, mode="auto") as client:
        with pytest.raises(ToolError, match="檔名必須"):
            await client.call_tool("delete_note", {})
    assert len(questions) == 1
    assert store.path.read_bytes() == before_catalog
    assert note_path.read_bytes() == before_note
    assert store.version == 1
    assert store.get_note("adler.md").content == "# 阿德勒\n個體心理學"
