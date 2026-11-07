# 開發與驗證

## 結構

`main.py` 接入 AstrBot 指令與 Discord 按鈕事件，管理短效預覽。`core/cleanup.py` 負責解析目標、查詢、作者檢查、刪除與紀錄。沒有自建 HTTP client、額外 Token、資料庫、排程或 LLM 工具，沿用 AstrBot 的 Pycord client 及 rate-limit 處理。

v0.1.5 僅接受原生斜線指令。AstrBot 4.29.4 原本的動態回呼會先 `ctx.defer()`，預設為公開；此時僅在 followup 加 `ephemeral=True` 不足以保證隱私。插件在初始化／平台載入時，僅包裝 `/dc_clean` 的既有回呼及其後續建立工廠，由 `core/private_command.py` 的 context 代理將這一次 defer 設為私人，保留原 adapter 的事件建構及分派。其他指令不變，卸載還原回呼；平台尚未建立 client 時先包裝工廠。

成功私人 defer 後在原 interaction 上留下內部標記。指令處理器沒有此標記時不顯示預覽，普通文字入口也不發公開回覆。預覽用 ephemeral followup 建立，四個按鈕、取消、進度與完成結果均編輯同一則私人訊息；公開舊按鈕拒絕操作。沒有群組公開完成提示，也沒有另外一則完成回覆。

AstrBot 4.29.4 的 Discord client 會先 acknowledge 按鈕，再轉成 AstrMessageEvent。本插件以 `View.stop()` 停止原生 Pycord callback，保留按鈕外觀，使用 `@filter.button_action()` 接手自身 `dcclean:` 前綴，並 `stop_event()`，避免另一個 callback 或 LLM 回覆。其他前綴直接返回。此方式亦支援沒有 `store=False` 參數的 Pycord 2.6.1。原生斜線指令已由 adapter defer，因此預覽使用它的 followup；按鈕後續編輯原訊息。

v0.1.1 使用一般 `event_message_type(ALL)` 處理器，會被 WakingCheckStage 的按鈕專用篩選跳過，優先序無法繞過。v0.1.2 修正這個共同入口，四個按鈕沿用相同的權限與清單驗證。

## 檢查

v0.1.6 修正原生指令在重連後的身分誤判。AstrBot 的 `bot_self_id` 初始為 `None`，由 `run()` 內的 `on_received` 設定；原生 `_create_dynamic_callback` 可先執行，直接把尚未初始化的值放入事件。插件現在以互動的 `application_id` 與已登入的 `client.user.id` 核對身分，不依賴此快取；訊息選取及刪除仍核對精確作者 ID。回歸測試將原 AstrBot 回呼產生的空 self_id 事件交給真正的 `clean()`，修正前無法建立預覽，修正後建立私人預覽並排除其他作者。另驗證錯誤或缺少 application_id 仍拒絕。

2026-11-08（v0.1.6）：**22 項單元測試、13 項 AstrBot 路由／原生回呼測試通過**，包含四個按鈕；Ruff 檢查及格式驗證通過。尚未部署此修正或完成真實 Discord 操作驗收。

在插件根目錄、已具備 AstrBot 的 Pycord 依賴的環境執行：

```bash
python -m unittest discover -s tests -p 'test_*.py' -v
python tests/check_button_routing.py /path/to/AstrBot
ruff check .
ruff format --check .
```

只跑本機測試時可安裝 `py-cord==2.6.1`、`ruff`、`PyYAML`；Python 3.13+ 另需 `audioop-lts`，AstrBot 本身已宣告這項相容依賴。這些開發環境檔案不放進發布包。

2026-11-08（v0.1.5）：Windows／Python 3.14、Pycord 2.6.1 的 **21 項單元測試與 12 項 AstrBot 路由／原生回呼測試全部通過**，Ruff 0.17.4 檢查與格式驗證通過。包含實際 Pycord defer 產生 `type=5, flags=64`，以及原 AstrBot 回呼建構的事件保留私人標記。尚未將此版部署到運行中的 AstrBot，也尚未做此版的真實 Discord 點擊與刪除驗收。

自身訊息以 Discord 回傳的精確作者 ID 及目前頻道判定，不依 webhook 或互動資料限制訊息形式；共用 `is_own` 同時保護選取和刪除。測試包含真實 Pycord `Message` 解析互動回覆 payload、有無互動資料皆接受同一作者，以及預覽後作者變更時拒絕刪除。預覽與完成結果同屬一則私人訊息，測試確認不呼叫頻道發送，也不另發完成 followup。

路由測試需指定 AstrBot v4.29.4 原始碼目錄，讀取 `astrbot/core/pipeline/waking_check/stage.py`、`astrbot/core/star/filter/button_action.py`、`astrbot/core/star/filter/event_message_type.py`、`astrbot/core/star/register/star_handler.py`、`astrbot/core/platform/sources/discord/discord_platform_adapter.py`。以 AST 選取原始定義後原樣執行按鈕註冊、篩選、WakingCheckStage 及 `_create_dynamic_callback`，重用插件測試；不複製路由邏輯、不啟動機器人。只替換網路、資料庫與無關服務邊界。必須與單元測試分開執行，避免替換的載入邊界互相影響。

按鈕驗證包含下一頁、上一頁、首尾頁停用與頁碼界限、確認全清單且只執行一次、取消更新原預覽且保留所有訊息。四種操作均檢查錯誤操作者／頻道／預覽訊息以及撤銷 AstrBot 管理權限；也檢查其他插件按鈕不被回覆或攔截。目標數量另驗證 100 個不同連結通過、重複連結不重複計數、101 個拒絕。

`/dc_clean` 使用 AstrBot 的 `GreedyStr` 接收完整參數（不要加預設值，框架依型別接收剩餘文字，無參數時傳入空字串）。預覽與每次按鈕事件均透過 `Context.get_config(event.unified_msg_origin)` 重新核對 `admins_id`，不查詢 Discord 成員或頻道管理權限。回歸測試涵蓋 AstrBot 管理員沒有 Discord 管理權仍可清理、僅 Discord 管理員被拒、預覽後移除 AstrBot 管理權被拒，以及同指令時間／ID／連結辨識與用法提示。

測試執行真實選取／刪除／預覽方法，只替換 AstrBot 載入邊界與 Discord 網路物件。涵蓋指定連結範圍、時間邊界、其他作者排除、確認後內容改變、只刪凍結 ID、權限／操作者隔離、單訊息翻頁、單次確認、取消及稽核寫入失敗。這不等同部署到實際伺服器的端到端驗收。

部署驗收應在測試頻道準備自身 Bot、其他 Bot 與使用者訊息，核對時間與指定 ID 兩種預覽、翻頁不增加訊息、只有原操作者確認成功、其他作者保留、舊按鈕失效及 JSONL 結果。不要拿正式群組內容當測試資料。

## 介面依據

- [AstrBot v4.29.4 Discord client](https://github.com/AstrBotDevs/AstrBot/blob/v4.29.4/astrbot/core/platform/sources/discord/client.py)
- [Discord adapter](https://github.com/AstrBotDevs/AstrBot/blob/v4.29.4/astrbot/core/platform/sources/discord/discord_platform_adapter.py)
- [AstrBot 管理員判定](https://github.com/AstrBotDevs/AstrBot/blob/v4.29.4/astrbot/core/pipeline/waking_check/stage.py)
- [指令參數與 GreedyStr](https://github.com/AstrBotDevs/AstrBot/blob/v4.29.4/astrbot/core/star/filter/command.py)
- [Pycord UI API](https://docs.pycord.dev/en/stable/api/ui_kit.html)
- [Discord Delete Message API](https://docs.discord.com/developers/resources/message#delete-message)
- [Discord 互動回覆與應用程式 webhook](https://docs.discord.com/developers/interactions/receiving-and-responding#followup-messages)

API 刪除成功計入「刪除」；已不存在計入「原已不存在」；內容變更與非自身作者一律保留。HTTP 失敗會逐筆記錄，檔案寫入或中斷時停止後續工作；不自動重跑已確認清單。
