# FastMCP 101 學習練習

先讀 `WORKSHOP.md`。這是使用者要自己動手的練習，與 fastmcp-playground 的實作計畫分開。

- `src/server.py` 與 `src/client.py` 的 TODO 留給使用者；workshop 依使用者要求提供 copy/paste 程式，不自行填成完整解答。
- `tests/test_server.py` 的測試預先寫好，使用者只需要讀與執行；未完成功能應失敗，不用 skip 或放寬預期讓它變綠。
- 一次只引導目前一個步驟：先解釋要完成什麼，讓使用者寫，再以對應測試驗證。需要提示時先給概念或局部提示。
- 所有 Python 原始碼放在 `src/`；server.py 提供 MCP 能力，client.py 負責連線；以 `uv sync --locked --dev` 安裝依賴，直接執行 src/client.py。
- 檔案 helper、工具環境與驗證方式可以修正；不能修改預期結果或關閉測試來讓未完成步驟通過。
- 執行使用 uv，品質檢查用 Ruff 與 ty；WORKSHOP.md 放根目錄，README 留入口；本機規劃放忽略的 __spec/。日常 pytest 不外連。
- 檢查使用者既有 diff，保留其練習內容；需要人類決策時先問，不替使用者決定。未授權不 commit、push、註冊 Claude MCP 或部署。
