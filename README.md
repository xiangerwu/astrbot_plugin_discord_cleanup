# Discord 精準清理

[繁體中文](README.md) | [English](README.en.md)

僅限 Discord。讓 **AstrBot 登記的管理員**清理目前機器人自己發出的訊息；**先預覽、再確認，預覽與結果只有操作者可見**。不需要 Discord 頻道管理員權限。

![Discord 精準清理](assets/intro.png)

## 指令：`/dc_clean`

在 Discord **原生指令選單**選擇 `/dc_clean`，將參數填入 **`params`** 欄位。直接傳送普通文字指令不會執行。

| 用途 | `params` 填寫範例 |
| --- | --- |
| 指定訊息 ID | `123456789012345678 123456789012345679` |
| 指定訊息連結 | `https://discord.com/channels/伺服器ID/頻道ID/訊息ID` |
| 指定時間範圍 | `2026-11-08T04:07 2026-11-08T04:09` |
| 查看用法 | 留空或填 `help` |

- **訊息**：換成實際 ID／完整連結，可混合使用，以空格或逗號分隔。每次最多 **100 個不同目標**，重複只計一次；完整連結仍受 Discord 輸入長度限制。
- **時間**：預設 **UTC+08:00**，包含開始、不含結束；也接受帶時區偏移或 `Z` 的 ISO 時間。時間查詢最多掃描 1000 則訊息，超限需縮小範圍。
- **範圍**：僅目前伺服器文字頻道或討論串，不支援私訊或跨頻道。支援機器人的一般訊息、斜線指令回覆及自身 webhook 訊息；其他作者一律排除。

## 預覽與確認

每頁 5 則，四個按鈕都操作同一則私人預覽：

| 按鈕 | 作用 |
| --- | --- |
| 上一頁／下一頁 | 翻頁；到首尾頁時停用對應按鈕 |
| 確認刪除全部 N 則 | 刪除**整份清單，不只本頁**，原預覽改為完成統計 |
| 取消 | 結束預覽，不刪除訊息 |

只有原操作者能確認，且會重新檢查 AstrBot 管理員資格。預覽 **5 分鐘有效**；同一人於同頻道重新預覽或重載插件，舊清單即失效。

刪除前再次核對作者及內容；內容、附件或嵌入資料已變更的訊息會跳過。**Discord 刪除不可復原**。清理紀錄保存於 `data/plugin_data/astrbot_plugin_discord_cleanup/cleanup-編號.jsonl`，包含訊息內容，不是還原備份，也不會自動清除，請妥善保管。

## 安裝

需要 AstrBot **4.29.4+**、Python **3.12+** 及已連線的 Discord adapter。無額外執行依賴或 Token 設定。

1. 在 AstrBot WebUI 以倉庫網址安裝，或上傳插件 ZIP：

   ```text
   https://github.com/xiangerwu/astrbot_plugin_discord_cleanup
   ```

2. 將你的 Discord 使用者 ID 加入目前會話配置的 AstrBot 管理員名單（`admins_id`）。
3. 開啟 Discord adapter 的「指令註冊」。若選單沒有 `/dc_clean`，在 WebUI 停用再啟用 **Discord 平台連線**以同步。

機器人需能檢視頻道、讀取歷史、發送訊息及存取目標討論串；不需「管理訊息」權限。一般插件更新後重載即可，已有指令不需重新連線。

## 專案資訊

[更新紀錄](CHANGELOG.md) · [開發與測試](docs/development.md) · [打包與發布](docs/publishing.md) · [圖片說明](docs/artwork.md) · [MIT 授權](LICENSE)
