# Discord Own-Message Cleanup

[繁體中文](README.md) | [English](README.en.md)

![Own-message cleanup with a single paginated preview](assets/intro.png)

An AstrBot plugin that deletes only messages authored by the **currently connected bot** in the current Discord guild channel or thread. Select a time window or explicit message links/IDs, review the list, then confirm. Ownership uses Discord's exact author ID, including ordinary messages, interaction replies and own messages carrying webhook metadata. Human messages, other bots and webhooks with other author IDs are excluded.

## Install

Requires AstrBot 4.29.4+, Python 3.12+ and its existing Discord/Pycord adapter. No additional runtime dependencies or bot token configuration. Install a release ZIP through WebUI, or copy this directory to `data/plugins/astrbot_plugin_discord_cleanup`, then reload the plugin. Enable command registration in the Discord adapter. If `/dc_clean` is missing from Discord's command picker, disable and re-enable the Discord platform connection to synchronize commands.

After upgrading to v0.1.5, reload the plugin and select `/dc_clean` in Discord's native command picker. Existing native commands do not require an AstrBot restart or Discord reconnection. Old previews expire; create a new private preview.

You can also install from the public repository URL in AstrBot WebUI:

```text
https://github.com/xiangerwu/astrbot_plugin_discord_cleanup
```

Metadata explicitly restricts platform support to Discord and includes Discord, message-management and cleanup tags. A public GitHub repository is separate from AstrBot marketplace publication.

## Commands

```text
/dc_clean 2026-11-08T04:07 2026-11-08T04:09
/dc_clean 123456789012345678 123456789012345679
/dc_clean
```

Select the native `/dc_clean` command from Discord's command picker and enter arguments in `params`. Plain-text commands, prefixes and bot mentions are not accepted and receive no public reply, ensuring privacy from the first response. The command detects timestamps or message targets automatically. Empty input, `help`, and invalid arguments show private usage. Use real IDs in place of these examples. Message links must match the current guild/channel. Mix IDs and full `https://discord.com/channels/GUILD/CHANNEL/MESSAGE` links separated by spaces or commas.

At most **100 distinct message IDs/links** per request; duplicates count once. A 101st distinct target rejects the entire selection. Discord input length limits still apply; use shorter IDs or a narrower time window when full links do not fit.

Times are start-inclusive/end-exclusive. Naive ISO timestamps use UTC+08:00; explicit offsets and `Z` are accepted. AstrBot 4.29.4 exposes a single slash-command `params` field: enter both timestamps separated by a space, or the target list. Leave it empty for usage.

## Preview and safeguards

v0.1.2 fixes button routing through AstrBot 4.29.4's dedicated button handler. Previous is disabled on the first page, Next on the last; both are disabled for a single page. After upgrading from v0.1.1, reload the plugin and run `/dc_clean` again because old previews expire on reload. This fix does not require reconnecting Discord.

- One ephemeral preview visible only to the operator in the channel, five entries per page. All four buttons, navigation, cancellation, progress, completion counts and the audit ID update that same private response. No public completion marker, separate result message, DM, per-target notifications or LLM calls.
- The operator must be registered in AstrBot's current session configuration (`admins_id`). Discord moderator status or Manage Messages is not required and does not grant access. Only the original operator can confirm, and the current AstrBot admin list is checked again; removal after preview prevents confirmation.
- Confirmation applies to **all listed IDs**, not just the visible page. New messages are never added during confirmation.
- Re-fetch and verify the exact channel and bot author ID before deletion. Edited content, attachments or embeds are skipped. Since v0.1.4, webhook/application/interaction metadata does not disqualify a message authored by this bot. Names, avatars and the generic bot flag never grant ownership. Reload the plugin and create a new preview after updating.
- Previews expire after five minutes, on replacement by the same operator/channel, or on plugin reload. At most 100 targets and 1000 scanned messages per request; exceeding a limit rejects the selection.
- Uses individual own-message deletion rather than bulk purge. The bot does not need Manage Messages just to delete its own messages.

The bot needs access to the channel and message history, including thread access. The preview and all results are ephemeral. Any plain-text command messages posted by users are retained.

Before deletion, the plugin writes a JSONL snapshot and appends outcomes under `data/plugin_data/astrbot_plugin_discord_cleanup/`. It contains conversation text, attachment URLs and embeds, never tokens or downloaded files. No automatic retention cleanup. Discord deletion is irreversible; audit files do not restore messages or guarantee attachment availability. Keep these records private.

## Development

Follows the sibling link plugin's MIT license, bilingual README, metadata, logo and `core/`, `tests/`, `assets/`, `docs/` layout. See [testing](docs/development.md), [packaging/publication](docs/publishing.md), and [artwork prompts](docs/artwork.md).

[MIT License](LICENSE). AI-generated project artwork is unofficial. This plugin cleans up messages; it does not fix the source of a message loop.
