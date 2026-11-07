# 打包與公開發布

沿用 link 插件的 GitHub 公開倉庫＋AstrBot ZIP／插件市場方式。MIT 授權與作者為 xiangerwu。公開倉庫為 [xiangerwu/astrbot_plugin_discord_cleanup](https://github.com/xiangerwu/astrbot_plugin_discord_cleanup)。

`metadata.yaml` 的 `support_platforms` 僅包含 `discord`，`tags` 為「Discord、訊息管理、清理」。GitHub topics 用於倉庫搜尋，AstrBot 插件市場則使用提交時解析的 metadata；兩者分開管理。

根目錄包含 `main.py`、`metadata.yaml`、`_conf_schema.json`、`requirements.txt`、`logo.png`、中英文 README 與 LICENSE；保留 `core/`、`tests/`、`assets/`、`docs/` 相對位置。不要發布 `.venv/`、快取、Token、清理紀錄與任何私人日誌。`dist/` 僅放本地產物，不提交 ZIP。

測試與檔案審核完成後，將版本號及文件一併提交、推送。已提交版本可在建立 `dist/` 目錄後使用：

```bash
git archive --format=zip --output=dist/astrbot_plugin_discord_cleanup-0.1.6.zip HEAD
```

這個命令只封裝 HEAD，不包括未提交內容。打包後檢查 ZIP 項目，確認沒有執行資料或秘密。

若要加入插件市場，再按 [AstrBot 官方發布說明](https://docs.astrbot.app/dev/star/plugin-publish.html)提交公開倉庫並確認市場結果。建立 GitHub 倉庫、發布 Release 與提交插件市場是不同操作。
