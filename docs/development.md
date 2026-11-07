# 開發與驗證

## 結構

`main.py` 接入 AstrBot 指令與 Discord 按鈕事件，管理短效預覽。`core/cleanup.py` 負責解析目標、查詢、作者檢查、刪除與紀錄。沒有自建 HTTP client、額外 Token、資料庫、排程或 LLM 工具，沿用 AstrBot 的 Pycord client 及 rate-limit 處理。

AstrBot 4.29.4 的 Discord client 會先 acknowledge 按鈕，再轉成 AstrMessageEvent。本插件以 `View.stop()` 停止原生 Pycord callback，保留按鈕外觀，由高優先序事件處理器接手自身 `dcclean:` 前綴，並 `stop_event()`，避免另一個 callback 或 LLM 回覆。此方式亦支援沒有 `store=False` 參數的 Pycord 2.6.1。原生斜線指令已由 adapter defer，因此預覽使用它的 followup；按鈕後續編輯原訊息。

## 檢查

在插件根目錄、已具備 AstrBot 的 Pycord 依賴的環境執行：

```bash
python -m unittest discover -s tests -p 'test_*.py' -v
ruff check .
ruff format --check .
```

只跑本機測試時可安裝 `py-cord==2.6.1`、`ruff`、`PyYAML`；Python 3.13+ 另需 `audioop-lts`，AstrBot 本身已宣告這項相容依賴。這些開發環境檔案不放進發布包。

2026-11-08：Windows／Python 3.14、Pycord 2.6.1 的 **12 項測試全部通過**，Ruff 0.17.4 檢查與格式驗證通過。圖片已確認：logo 為 1254×1254 RGBA（包含透明像素），README 橫幅為 1672×941 RGB。尚未安裝到運行中的 AstrBot，也尚未做真實 Discord 按鈕與刪除驗收。

測試執行真實選取／刪除／預覽方法，只替換 AstrBot 載入邊界與 Discord 網路物件。涵蓋指定連結範圍、時間邊界、其他作者排除、確認後內容改變、只刪凍結 ID、權限／操作者隔離、單訊息翻頁、單次確認、取消及稽核寫入失敗。這不等同部署到實際伺服器的端到端驗收。

部署驗收應在測試頻道準備自身 Bot、其他 Bot 與使用者訊息，核對時間與指定 ID 兩種預覽、翻頁不增加訊息、只有原操作者確認成功、其他作者保留、舊按鈕失效及 JSONL 結果。不要拿正式群組內容當測試資料。

## 介面依據

- [AstrBot v4.29.4 Discord client](https://github.com/AstrBotDevs/AstrBot/blob/v4.29.4/astrbot/core/platform/sources/discord/client.py)
- [Discord adapter](https://github.com/AstrBotDevs/AstrBot/blob/v4.29.4/astrbot/core/platform/sources/discord/discord_platform_adapter.py)
- [Pycord UI API](https://docs.pycord.dev/en/stable/api/ui_kit.html)
- [Discord Delete Message API](https://docs.discord.com/developers/resources/message#delete-message)

API 刪除成功計入「刪除」；已不存在計入「原已不存在」；內容變更與非自身作者一律保留。HTTP 失敗會逐筆記錄，檔案寫入或中斷時停止後續工作；不自動重跑已確認清單。
