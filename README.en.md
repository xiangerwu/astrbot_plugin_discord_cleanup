# Discord Own-Message Cleanup

[繁體中文](README.md) | [English](README.en.md)

Discord only. **Registered AstrBot administrators** can delete messages authored by the current bot. **Preview first, then confirm; previews and results are visible only to the operator.** Discord moderator permissions are not required.

![Discord own-message cleanup](assets/intro.png)

## Command: `/dc_clean`

Select `/dc_clean` from Discord's **native command picker**, then enter arguments in **`params`**. Sending it as plain text does not run the command.

| Purpose | Example `params` value |
| --- | --- |
| Message IDs | `123456789012345678 123456789012345679` |
| Message link | `https://discord.com/channels/GUILD_ID/CHANNEL_ID/MESSAGE_ID` |
| Time range | `2026-11-08T04:07 2026-11-08T04:09` |
| Usage help | Leave empty or enter `help` |

- **Messages:** replace examples with actual IDs or full links. Mix them using spaces or commas. Up to **100 distinct targets**; duplicates count once. Full links remain subject to Discord's input length limit.
- **Time:** defaults to **UTC+08:00**, start-inclusive and end-exclusive. ISO timestamps with offsets or `Z` are accepted. Time queries scan at most 1000 messages; narrow the range if the limit is exceeded.
- **Scope:** current guild text channel or thread only; no DMs or cross-channel cleanup. Ordinary bot messages, interaction replies and the bot's own webhook messages are supported. Other authors are excluded.

## Preview and confirmation

Five messages per page. All four buttons operate on the same private preview:

| Button | Action |
| --- | --- |
| Previous / Next | Change pages; disabled at the corresponding boundary |
| Confirm all N messages | Delete **the entire list, not just the current page**, and replace the preview with results |
| Cancel | End the preview without deleting messages |

Only the original operator can confirm, and AstrBot administrator status is checked again. Previews last **five minutes**; a new preview by the same operator in the same channel or a plugin reload invalidates the old one.

Author and content are checked again before deletion; changed text, attachments or embeds are skipped. **Discord deletion is irreversible.** Audit files are stored at `data/plugin_data/astrbot_plugin_discord_cleanup/cleanup-ID.jsonl`. They contain message content, cannot restore messages and are not automatically removed. Keep them private.

## Install

Requires AstrBot **4.29.4+**, Python **3.12+** and a connected Discord adapter. No additional runtime dependencies or token configuration.

1. Install through AstrBot WebUI using the repository URL, or upload a plugin ZIP:

   ```text
   https://github.com/xiangerwu/astrbot_plugin_discord_cleanup
   ```

2. Add your Discord user ID to the AstrBot administrator list (`admins_id`) for the current session configuration.
3. Enable command registration in the Discord adapter. If `/dc_clean` is missing, disable and re-enable the **Discord platform connection** in WebUI to synchronize commands.

The bot needs channel access, message history, message sending and access to the target thread; Manage Messages is not required. Reload after ordinary plugin updates; an existing command does not require reconnecting Discord.

## Project

[Changelog](CHANGELOG.md) · [Development and tests](docs/development.md) · [Packaging](docs/publishing.md) · [Artwork](docs/artwork.md) · [MIT License](LICENSE)
