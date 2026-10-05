import wave
from pathlib import Path

import pytest

import audio_helper


def write_pcm(path: Path, frames: bytes) -> None:
    with wave.open(str(path), "wb") as audio:
        audio.setparams((1, 2, 22050, 0, "NONE", "not compressed"))
        audio.writeframes(frames)


async def test_segments_are_merged_in_order_and_progress_finishes_after_saving(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spoken: list[str] = []
    events: list[tuple[int, int, str]] = []
    output = tmp_path / "notes.wav"
    frames = [b"\x01\x00" * 4, b"\x02\x00" * 6]

    async def speak(text: str, path: Path) -> None:
        spoken.append(text)
        write_pcm(path, frames[len(spoken) - 1])

    async def report(done: int, total: int, message: str) -> None:
        assert len(spoken) >= done
        if done == total:
            assert output.exists(), "最後一次完成通知前，要先保存完整音檔。"
        events.append((done, total, message))

    monkeypatch.setattr(audio_helper, "_speak", speak)
    result = await audio_helper.render_audio("# 第一段\n\n第二段", output, report)
    assert result == output
    assert spoken == ["第一段", "第二段"]
    assert [(n, total) for n, total, _ in events] == [(1, 2), (2, 2)]
    with wave.open(str(output), "rb") as audio:
        assert audio.getframerate() == 22050
        assert audio.readframes(audio.getnframes()) == b"".join(frames)
    assert list(tmp_path.iterdir()) == [output]


@pytest.mark.parametrize("text", ["   ", "#\n\n###"])
async def test_empty_text_never_invokes_the_engine(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    text: str,
) -> None:
    async def unexpected(text: str, path: Path) -> None:
        raise AssertionError("空白文字不能送去生成。")

    async def unexpected_progress(done: int, total: int, message: str) -> None:
        raise AssertionError("空白文字不能報成功。")

    monkeypatch.setattr(audio_helper, "_speak", unexpected)
    with pytest.raises(ValueError, match="沒有可朗讀"):
        await audio_helper.render_audio(
            text, tmp_path / "notes.wav", unexpected_progress
        )
    assert not list(tmp_path.iterdir())


async def test_engine_failure_preserves_previous_audio_and_cleans_parts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "notes.wav"
    output.write_bytes(b"previous audio")
    calls: list[str] = []
    progress: list[int] = []

    async def speak(text: str, path: Path) -> None:
        calls.append(text)
        if len(calls) == 2:
            raise RuntimeError("語音生成失敗")
        write_pcm(path, b"\x01\x00" * 4)

    async def report(done: int, total: int, message: str) -> None:
        progress.append(done)

    monkeypatch.setattr(audio_helper, "_speak", speak)
    with pytest.raises(RuntimeError, match="語音生成失敗"):
        await audio_helper.render_audio("第一段\n\n第二段", output, report)
    assert progress == [1]
    assert output.read_bytes() == b"previous audio"
    assert list(tmp_path.iterdir()) == [output]


async def test_invalid_wave_is_not_published_as_completed_audio(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[int] = []

    async def speak(text: str, path: Path) -> None:
        path.write_bytes(b"not a wav file")

    async def report(done: int, total: int, message: str) -> None:
        events.append(done)

    monkeypatch.setattr(audio_helper, "_speak", speak)
    with pytest.raises(wave.Error):
        await audio_helper.render_audio("Hello", tmp_path / "notes.wav", report)
    assert events == []
    assert not list(tmp_path.iterdir())


async def test_missing_say_has_a_clear_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(audio_helper.shutil, "which", lambda name: None)
    with pytest.raises(RuntimeError, match="macOS"):
        await audio_helper._speak("Hello", tmp_path / "notes.wav")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("# 標題\r\n\r\n#hashtag\r\n \t\r\n內文", ["標題", "#hashtag", "內文"]),
        ("# 標題\n \t\n第一段\n\n第二段", ["標題", "第一段", "第二段"]),
        ("# 標題\n#hashtag\n####### literal", ["標題\n#hashtag\n####### literal"]),
    ],
)
async def test_markdown_headings_and_blank_lines_are_handled_without_losing_hashes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    text: str,
    expected: list[str],
) -> None:
    spoken: list[str] = []
    events: list[int] = []

    async def speak(text: str, path: Path) -> None:
        spoken.append(text)
        write_pcm(path, b"\x01\x00" * 4)

    async def report(done: int, total: int, message: str) -> None:
        events.append(done)

    monkeypatch.setattr(audio_helper, "_speak", speak)
    await audio_helper.render_audio(text, tmp_path / "notes.wav", report)
    assert spoken == expected
    assert events == list(range(1, len(expected) + 1))
