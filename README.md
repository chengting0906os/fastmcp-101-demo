# FastMCP 101：本地筆記知識庫

從打招呼開始，逐步加入筆記建立、搜尋、更新，再用 User Elicitation 刪除筆記、練習語音生成的 Progress 和 MCP Apps 心智圖。
Server 與 Python client 使用本地 stdio，不需要 API key。Apps 由支援的 Host 顯示；另有 localhost HTTP 開發預覽。

從 [WORKSHOP.md](WORKSHOP.md) 開始。每一步都有 TODO、取消裝飾器註解的步驟、執行指令與成功結果。

```sh
cd fastmcp-101-demo
uv sync --locked --dev
uv run --locked python src/client.py
```

- src/hello.py 保留獨立的 greet 範例；server.py 提供 MCP 能力，client.py 負責連線與呼叫。目前只有 greet，其他功能按 workshop 完成 TODO。
- src/kb_store.py 保存筆記，每次建立、更新或刪除版本加 1；src/mindmap_app.py 與 src/mindmap.html 提供可縮放、拖曳、點選閱讀的 SVG 心智圖，並保存 HTML 到 local_kb/mindmaps/（不進 git）。
- src/audio_helper.py 用 macOS 內建 say 製作語音，使用 Meijia 聲音；音檔存 local_kb/audio/（只追蹤 .gitkeep，音檔不進 git）。
- 自己建立的筆記存在 local_kb/：每篇一個 Markdown 檔，分類與版本記在 local_kb/_catalog.json，本地資料不進 git。

環境：Python 3.13、FastMCP 4.0.11、Prefab UI 0.20.2，使用 uv、Ruff、ty。

測試已預先寫好：每節跑 workshop 指定的 `-m lessonN`；學完再跑 `uv run --locked python -m pytest -q`。完整測試在 TODO 尚未完成前會失敗，不代表已完成的 Server。

完成後有 7 個 tools：greet、create_note、search_notes、update_note、delete_note、make_audio、show_mindmap。

所有 Python 程式放在 `src/`；`uv sync --locked --dev` 會安裝練習所需依賴。

```text
src/
├── server.py       # MCP server：提供能力
├── client.py       # MCP client：連線並呼叫 server
├── hello.py        # 最小 greet 範例
├── kb_store.py
├── audio_helper.py
├── mindmap_app.py
└── mindmap.html
```

單獨跑 hello 範例：`uv run --locked python src/hello.py`。

型別檢查（ty 已包含在 dev dependencies）：

```sh
uv run --locked ty check
```
