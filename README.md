# Discord 精準清理

[繁體中文](README.md) | [English](README.en.md)

![Discord 精準清理：只刪自身訊息，單則分頁預覽](assets/intro.png)

只清理**目前這隻 AstrBot 機器人自己發出的訊息**。選好時間範圍或訊息 ID／連結，查看清單，再由原操作者按下確認。群友、其他機器人與 webhook 訊息均排除。

- 每次預覽只發 **一則訊息**，每頁最多 5 筆；翻頁、取消、進度與完成結果都編輯同一則。
- 支援 Discord 伺服器文字頻道與討論串，限定目前頻道；不支援私訊或跨頻道清理。
- 操作者必須在該頻道具備「管理訊息」權限，確認時再次檢查。機器人使用現有登入連線，不需要再填 Token。
- 確認鎖定預覽中的 ID；刪除前重新讀取並比對作者、內容、附件與嵌入資訊，已變更者跳過。
- 不提供 LLM 工具、不呼叫模型、不自動清理，也不會停止其他插件的刷屏來源。

## 安裝

需要 AstrBot **4.29.4+**、Python **3.12+** 及已連線的 Discord adapter。使用 AstrBot 現有 Pycord，沒有額外執行依賴。

將發布 ZIP 透過 WebUI 安裝，或將本目錄放到 `data/plugins/astrbot_plugin_discord_cleanup`，重載插件。原生斜線指令是否顯示取決於 Discord adapter 的指令同步；尚未同步時可使用 AstrBot 已設定的喚醒前綴或 @ Bot 加文字指令。不需更動或重新輸入機器人 Token。

也可在 AstrBot WebUI 透過公開倉庫網址安裝：

```text
https://github.com/xiangerwu/astrbot_plugin_discord_cleanup
```

`metadata.yaml` 已標註僅支援 Discord，標籤為「Discord、訊息管理、清理」。公開 GitHub 倉庫與插件市場上架是不同步驟；市場發布方式見[發布說明](docs/publishing.md)。

## 使用

### 指定時間

```text
/dc_clean_time 2026-11-08T04:07 2026-11-08T04:09
```

開始時間包含在內，結束時間不包含在內；未填時區以 **UTC+08:00** 解讀。也可使用 `2026-11-07T20:07:00Z` 或帶時區偏移的 ISO 時間。請填完整日期，避免把凌晨訊息選到錯的一天。

### 指定訊息

```text
/dc_clean_messages 123456789012345678,123456789012345679
/dc_clean_messages https://discord.com/channels/伺服器ID/目前頻道ID/訊息ID
```

以上數字是格式示例，使用時換成實際 ID。多筆 ID／完整連結可混合，用逗號分隔且不要加空格。Discord 右鍵訊息可「複製訊息連結」；複製 ID 需開啟開發者模式。

AstrBot 4.29.4 將插件斜線指令的參數放在單一 `params` 欄位：`dc_clean_time` 填兩個時間，以空格分隔；`dc_clean_messages` 填一個逗號分隔的清單。

### 預覽與確認

1. 預覽顯示總數、略過數、訊息 ID、時間及內容摘要。每頁 5 筆，按上一頁／下一頁只更新原訊息。
2. 只有原操作者能按「確認刪除全部 N 則」或「取消」。**確認會刪整份清單，不只是本頁。**
3. 清單 5 分鐘後失效；重新預覽會取代自己在同一頻道的舊清單。重載插件也會取消待確認清單。
4. 完成後同一則預覽改為統計結果；若 API 或紀錄寫入失敗會顯示中斷，請重新預覽剩餘訊息。

預覽是**頻道內可見**的管理訊息，不承諾私密／ephemeral 顯示。無權使用按鈕的提示僅對點擊者可見。指令本身由使用者發送，插件不會刪除使用者的指令訊息。

## 範圍與紀錄

每次最多 100 則目標；時間查詢最多讀取 1000 則頻道訊息，超限就要求縮小範圍，不會悄悄刪除部分清單。逐則刪除自己的訊息，不使用「清空最近 N 則」或批次刪除端點，亦不受批次端點的兩週限制。

機器人需能檢視頻道、讀取歷史、發送訊息及使用討論串；只刪自己的訊息不要求它具有「管理訊息」權限。人的管理權限是本插件額外的操作門檻。

確認後、第一次刪除前，資料目錄會保存 `data/plugin_data/astrbot_plugin_discord_cleanup/cleanup-編號.jsonl`：操作者、作者、頻道、訊息 ID、文字、附件名稱／URL、嵌入資料及逐筆結果。紀錄不含 Token、不下載附件，附件 URL 可能失效，**不是可復原訊息的備份**。Discord 刪除不可復原。紀錄不自動清除，請由管理員依自己的保留需求處理，勿放入公開倉庫。

## 開發與開源

沿用相鄰 `astrbot_plugin_link_context` 的 MIT 授權、根目錄 metadata／logo、中英文 README、`core/`、`tests/`、`assets/` 與 `docs/` 形式，依本插件規模精簡。

- [開發、測試與限制](docs/development.md)
- [打包與發布](docs/publishing.md)
- [圖片來源及提示詞](docs/artwork.md)

程式碼採 [MIT License](LICENSE)。圖像使用內建 ImageGen 生成，是非官方專案插畫，不代表 Discord 或 AstrBot 官方背書。回報問題時請提供版本及去識別化錯誤資訊，勿公開 Token 或清理紀錄中的群聊內容。
