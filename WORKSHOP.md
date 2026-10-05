# 自己做一個本地筆記 MCP

先用 Python client 測一次 greet，再逐節啟用 server 的功能。這份 Workshop 分成基本介紹、User Elicitation、Progress、MCP Apps 四部分。

程式都在 `src/`，命令從專案根目錄執行：

- `server.py`：實作已備妥，各節只需取消對應裝飾器前的 `#`。
- `client.py`：只測 greet，第 1 節跑過即可，後續不用修改。
- `hello.py`：獨立的打招呼範例，保持原樣。

**例如把 `# @mcp.tool` 改成 `@mcp.tool`，函式就會註冊成 MCP Tool。不用貼程式或改函式內文，保留 TODO。**
第 2 節做 C／R／U；第 4 節加入 D，刪除前請人輸入檔名。

測試已寫好，不需要另外寫。起初只有 greet 註冊；每節啟用功能後執行對應測試，全部啟用後再跑整套驗收。

## 0. 準備環境

```sh
cd fastmcp-101-demo
uv sync --locked --dev
uv run --locked python -m pytest tests/test_kb_store.py tests/test_audio_helper.py tests/test_mindmap_app.py -q
```

成功：48 個 helper 測試通過。保存、搜尋、語音處理與心智圖介面已準備好，這次練習把它們接上 MCP。

## 1. 先連線打招呼

不用貼程式，直接執行：

```sh
uv run --locked python src/client.py
uv run --locked fastmcp list src/server.py
uv run --locked python -m pytest tests/test_server.py -m lesson1 -q
```

成功：印出 `Hello, Guest! Welcome to MCP.`，測試通過。list 目前只會看到 greet。
client 啟動 server 子程序，透過 stdio 傳送 MCP 訊息；裝飾器讓函式成為 MCP 能力。

### 自己開 MCP Inspector

在專案根目錄執行：

```sh
uv run --locked python src/inspector.py
```

啟動檔會用專案的 Python 環境開啟 server.py，以 stdio 連線，並設定 Inspector 使用 modern 協定。Inspector 固定為 2.9.0；需要 Node.js／npx，第一次執行可能下載套件。
在介面選擇本專案的 server 並連線，就能列出 tools、讀 resource、取得 prompt。
每節修改 server.py 後，若 Inspector 已連線，先斷線再重新連線，載入新程式。
在這個終端機按 Ctrl+C 關閉。`fastmcp inspect` 只顯示 Server 資訊，與這個網頁 Inspector 不同。

## 2. 建立、搜尋、更新筆記

在 server.py 的 TODO 2 下方，取消三個函式的裝飾器註解：

- create_note：建立（C），提供檔名、內容與分類。
- search_notes：讀取（R），以關鍵字搜尋。
- update_note：更新（U），修改筆記內容。

將這三個函式上方的 `# @mcp.tool` 改成 `@mcp.tool`。

```sh
uv run --locked python -m pytest tests/test_server.py -m lesson2 -q
```

成功：4 個測試通過，涵蓋建立、搜尋、更新與失敗時不寫入。
先呼叫 create_note：note_id 填 `stdio.md`、category 填 `MCP 學習`，content 貼上：

```markdown
# stdio 傳輸

Client 透過 stdin/stdout 傳送 JSON-RPC 訊息。
```

再呼叫：
- search_notes：query 填 `stdio`，應找到 stdio.md。
- update_note：note_id 填 `stdio.md`、content 填新內容，再搜尋確認更新。

每篇筆記存成 `local_kb/<note_id>`，例如 `local_kb/stdio.md`；分類與版本記在 `local_kb/_catalog.json`。同名筆記會拒絕建立，修改內容請用 update_note；刪除筆記會一併刪掉該 Markdown 檔。

## 3. Resource 與 Prompt

在 server.py 取消這兩個函式上方的裝飾器註解：

- overview：`# @mcp.resource("kb://overview", mime_type="application/json")` → `@mcp.resource("kb://overview", mime_type="application/json")`。
- answer_from_notes：`# @mcp.prompt` → `@mcp.prompt`。

Resource 提供筆記目錄；Prompt 提供「先搜尋、標示來源、找不到就說不知道」的提問模板。

```sh
uv run --locked python -m pytest tests/test_server.py -m lesson3 -q
```

成功：2 個測試通過，確認 resource 的中文目錄與 prompt 的問題模板。
手動操作：先在 Inspector 建立筆記，再讀取 `kb://overview`；取得 `answer_from_notes` prompt 時，question 填 `stdio 要注意什麼？`。
取得 prompt 只回傳模板，不會自動搜尋或生成答案。

## 4. 刪除前請人輸入檔名

在 server.py 的 TODO 4 下方，取消 delete_note 上方的 `# @mcp.tool` 註解。
這個工具補上刪除（D），每次呼叫都先請使用者輸入要刪除的筆記檔名。

先讀 delete_note、_request_filename 與 _delete_by_answer：第一次回傳 InputRequiredResult，client 收集檔名後重新呼叫。後端先檢查是否為單一 `.md` 檔名，再確認筆記存在才刪除。輸入「刪除」、路徑、未知檔名，或拒絕、取消、留白，都不更動資料。

```sh
uv run --locked python -m pytest tests/test_server.py -m lesson4 -q
```

成功：12 個測試通過，驗證先詢問再刪除，以及拒絕、取消、空白、無效與未知檔名。
在 Inspector 示範：

1. 先用 create_note 另外建立 `meeting.md`，內容填 `星期三分享 FastMCP。`，分類填 `MCP 學習`。
2. 呼叫 delete_note，工具本身沒有需要填的參數。
3. 在補充資訊的表單輸入 `stdio.md`，接受後刪除。
4. 讀取 kb://overview，確認 stdio.md 已移除，meeting.md 仍在。
5. 重試拒絕或取消，確認 meeting.md 仍在。

刪除後，可以用 create_note 重新建立筆記。

## 5. 語音生成與 Progress

在 server.py 取消 make_audio 上方的 `# @mcp.tool` 註解：

```python
@mcp.tool
```

讀一下函式內的 report：它把每段語音完成的進度交給 ctx.report_progress，傳回 client。

```sh
uv run --locked python -m pytest tests/test_server.py -m lesson5 -q
```

成功：3 個測試通過，驗證音檔保存、MCP Progress 與不存在的筆記。
手動示範：先用 create_note 重新建立 `stdio.md`，內容使用第 2 節的兩段文字；再呼叫 make_audio，note_id 填 `stdio.md`。應收到 Progress 1/2、2/2，最後取得音檔路徑。
生成完成後播放：

```sh
afplay local_kb/audio/stdio.wav
```

使用 macOS 內建 say 與 Meijia 聲音，不需要 API key。換一台 Mac 時先用 `say -v '?'` 確認聲音已安裝。
每完成一段才回報進度，最後一次通知在音檔保存後送出。自動測試替換 OS 語音引擎，真正的播放用上方指令確認。

## 6. MCP Apps 心智圖

在 server.py 取消 show_mindmap 上方的裝飾器註解：

```python
@mcp.tool(app=True)
```

FastMCP 會註冊 UI resource，支援 MCP Apps 的 Host 可以顯示回傳的心智圖。
每次呼叫也會保存 HTML 到 local_kb/mindmaps/：單篇使用筆記檔名（例如 stdio.html），多篇使用 overview.html。再次產生會覆蓋同一檔案；保存的是當下內容，修改筆記後需重新產生。HTML 可直接用瀏覽器開啟，檔案不進 git。

```sh
uv run --locked python -m pytest tests/test_server.py -m lesson6 -q
```

成功：3 個測試通過，驗證 Apps metadata、UI resource 與心智圖資料。

### 看見介面

使用前面建立的筆記，直接啟動預覽：

```sh
uv run --locked fastmcp dev apps src/server.py:mcp --host 127.0.0.1 --no-reload
```

打開指令印出的本機網址，選 show_mindmap，query 留空後執行：

- 顯示「本地筆記 → MCP 學習 → 你建立的筆記標題」。
- 點筆記看來源與原文；Tab、Enter 也能操作。
- ＋／－、滾輪可縮放，拖曳空白處可移動，重設回到原位。
- query 填 stdio 時只剩該篇；瀏覽不修改筆記。

這個指令另外啟動 localhost HTTP 預覽，server.py 仍維持 stdio。首次載入前端套件可能需要網路，報告前先開一次。Ctrl+C 關閉預覽。

## 7. 完成後驗收

先看 tests/test_server.py：`Client(server.mcp)` 直接測記憶體中的 Server；client.py 的 `Client(Path(...))` 則真正啟動子程序，用 stdio 連線。
`result.data` 是解析後的 Python 值，`result.content` 是 MCP content blocks。client.py 只負責第 1 節的 greet 連線示範；其餘功能由既有測試驗收，並用 Inspector 或 Apps 預覽手動操作。

**八個裝飾器的註解都取消後**，執行整套檢查：

```sh
uv run --locked ruff check --fix .
uv run --locked ruff format .
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked ty check
uv run --locked python -m pytest -q
uv run --locked fastmcp inspect src/server.py:mcp
```

成功：73 passed（48 個 helper＋25 個 MCP 案例），Ruff 與 ty 通過。inspect 顯示 7 個 tools、2 個 resources、1 個 prompt。
所有測試離線，使用暫存資料夾；不修改你的 local_kb/。不要 skip 測試或放寬預期。

報告時間：基本介紹 4 分鐘、User Elicitation 2 分鐘、Progress 2 分鐘、MCP Apps 2 分鐘。

參考：[Prefect Labs 的 FastMCP 101 Workshop](https://github.com/prefectlabs/fastmcp-101/blob/main/WORKSHOP.md)、[Elicitation](https://gofastmcp.com/servers/elicitation)、[Progress](https://gofastmcp.com/servers/progress)、[MCP Apps](https://modelcontextprotocol.io/extensions/apps/overview)。
