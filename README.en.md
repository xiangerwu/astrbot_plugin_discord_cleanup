# Discord Own-Message Cleanup

[繁體中文](README.md) | [English](README.en.md)

![Own-message cleanup with a single paginated preview](assets/intro.png)

An AstrBot plugin that deletes only messages authored by the **currently connected bot** in the current Discord guild channel or thread. Select a time window or explicit message links/IDs, review the list, then confirm. Human messages, other bots and webhooks are excluded.

## Install

Requires AstrBot 4.29.4+, Python 3.12+ and its existing Discord/Pycord adapter. No additional runtime dependencies or bot token configuration. Install a release ZIP through WebUI, or copy this directory to `data/plugins/astrbot_plugin_discord_cleanup`, then reload the plugin. Slash-command visibility depends on the adapter's command synchronization; configured AstrBot text prefixes or a bot mention can be used meanwhile.

You can also install from the public repository URL in AstrBot WebUI:

```text
https://github.com/xiangerwu/astrbot_plugin_discord_cleanup
```

Metadata explicitly restricts platform support to Discord and includes Discord, message-management and cleanup tags. A public GitHub repository is separate from AstrBot marketplace publication.

## Commands

```text
/dc_clean_time 2026-11-08T04:07 2026-11-08T04:09
/dc_clean_messages 123456789012345678,123456789012345679
```

Use real IDs in place of these examples. Message links must match the current guild/channel. Mix IDs and full `https://discord.com/channels/GUILD/CHANNEL/MESSAGE` links separated by commas, without spaces.

Times are start-inclusive/end-exclusive. Naive ISO timestamps use UTC+08:00; explicit offsets and `Z` are accepted. AstrBot 4.29.4 exposes a single slash-command `params` field: enter both timestamps separated by a space, or the comma-separated target list.

## Preview and safeguards

- One public preview message, five entries per page. Navigation, cancellation, progress and results edit the same message. No per-target notifications or LLM calls.
- The operator must have Manage Messages in the channel. Only the original operator can confirm, and permissions are rechecked.
- Confirmation applies to **all listed IDs**, not just the visible page. New messages are never added during confirmation.
- Re-fetch and verify each author's exact bot ID before deletion. Edited content, attachments or embeds are skipped. Webhooks are excluded even when they resemble the bot.
- Previews expire after five minutes, on replacement by the same operator/channel, or on plugin reload. At most 100 targets and 1000 scanned messages per request; exceeding a limit rejects the selection.
- Uses individual own-message deletion rather than bulk purge. The bot does not need Manage Messages just to delete its own messages; the human permission requirement is a plugin rule.

The bot needs channel/history access and permission to send the preview (including thread permissions). The preview is public, not promised to be ephemeral. User command messages are retained.

Before deletion, the plugin writes a JSONL snapshot and appends outcomes under `data/plugin_data/astrbot_plugin_discord_cleanup/`. It contains conversation text, attachment URLs and embeds, never tokens or downloaded files. No automatic retention cleanup. Discord deletion is irreversible; audit files do not restore messages or guarantee attachment availability. Keep these records private.

## Development

Follows the sibling link plugin's MIT license, bilingual README, metadata, logo and `core/`, `tests/`, `assets/`, `docs/` layout. See [testing](docs/development.md), [packaging/publication](docs/publishing.md), and [artwork prompts](docs/artwork.md).

[MIT License](LICENSE). AI-generated project artwork is unofficial. This plugin cleans up messages; it does not fix the source of a message loop.
