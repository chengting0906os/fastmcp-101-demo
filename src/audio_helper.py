"""把筆記分段交給 macOS say，以真實完成的段落回報進度。"""

import asyncio
import re
import shutil
import wave
from collections.abc import Awaitable, Callable
from contextlib import suppress
from pathlib import Path
from tempfile import TemporaryDirectory

ProgressHandler = Callable[[int, int, str], Awaitable[None]]


async def _speak(text: str, path: Path) -> None:
    executable = shutil.which("say")
    if executable is None:
        raise RuntimeError("此語音練習需要 macOS 內建的 say。")
    process = await asyncio.create_subprocess_exec(
        executable,
        "-v",
        "Meijia",
        "-o",
        str(path),
        "--file-format=WAVE",
        "--data-format=LEI16@22050",
        "--channels=1",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        _, errors = await asyncio.wait_for(
            process.communicate(text.encode("utf-8")),
            timeout=30,
        )
    except (TimeoutError, asyncio.CancelledError):
        with suppress(ProcessLookupError):
            process.kill()
        await process.wait()
        raise
    if process.returncode != 0:
        detail = errors.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"語音生成失敗：{detail}")


async def render_audio(
    text: str,
    output: Path,
    on_progress: ProgressHandler,
) -> Path:
    # 支援 CRLF 與含空白的空行，只去掉 Markdown 標題標記。
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    parts = [
        "\n".join(
            re.sub(r"^ {0,3}#{1,6}(?:[ \t]+|$)", "", line)
            for line in paragraph.splitlines()
        ).strip()
        for paragraph in re.split(r"\n[ \t]*\n(?:[ \t]*\n)*", normalized)
    ]
    parts = [part for part in parts if part]
    if not parts:
        raise ValueError("筆記沒有可朗讀的文字。")
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="speech-", dir=output.parent) as temporary:
        folder = Path(temporary)
        combined = folder / "combined.wav"
        with wave.open(str(combined), "wb") as joined:
            joined.setparams((1, 2, 22050, 0, "NONE", "not compressed"))
            for completed, part in enumerate(parts, start=1):
                segment = folder / f"{completed}.wav"
                await _speak(part, segment)
                with wave.open(str(segment), "rb") as audio:
                    format_info = (
                        audio.getnchannels(),
                        audio.getsampwidth(),
                        audio.getframerate(),
                    )
                    if format_info != (1, 2, 22050):
                        raise ValueError("語音格式必須是單聲道 16-bit、22050 Hz WAV。")
                    if audio.getnframes() == 0:
                        raise ValueError("語音生成結果是空音檔。")
                    joined.writeframes(audio.readframes(audio.getnframes()))
                if completed < len(parts):
                    await on_progress(completed, len(parts), f"已完成第 {completed} 段")
        combined.replace(output)
        await on_progress(len(parts), len(parts), "音檔已保存，可以播放。")
    return output
