import json
import re
from datetime import UTC, datetime, timedelta, timezone

import discord

MAX_MESSAGES = 100
SCAN_LIMIT = 1000
DISPLAY_TZ = timezone(timedelta(hours=8))


def parse_ids(text, guild_id, channel_id):
    """Accept IDs or Discord message links, restricted to this guild/channel."""
    tokens = re.split(r"[\s,，]+", text.strip())
    ids = []
    for token in tokens:
        token = token.strip("<>")
        match = re.fullmatch(
            r"https://(?:(?:canary|ptb)\.)?discord(?:app)?\.com/channels/(\d+)/(\d+)/(\d+)",
            token,
        )
        if match:
            guild, channel, token = map(int, match.groups())
            if guild != guild_id or channel != channel_id:
                raise ValueError("訊息連結必須屬於目前伺服器及頻道／討論串。")
            token = str(token)
        if not token.isascii() or not token.isdigit() or not 0 < int(token) < 2**64:
            raise ValueError("請提供訊息 ID 或完整 Discord 訊息連結；多筆以逗號分隔。")
        if int(token) not in ids:
            ids.append(int(token))
    if not 1 <= len(ids) <= MAX_MESSAGES:
        raise ValueError(f"每次請指定 1～{MAX_MESSAGES} 則訊息。")
    return ids


def parse_time_range(start, end):
    try:
        first, last = (datetime.fromisoformat(value) for value in (start, end))
    except ValueError:
        raise ValueError("時間格式：2026-11-08T04:07；可加 +08:00 或 Z。") from None
    first, last = (
        value.replace(tzinfo=DISPLAY_TZ) if value.tzinfo is None else value
        for value in (first, last)
    )
    if first >= last:
        raise ValueError("結束時間必須晚於開始時間；未標時區時使用 UTC+08:00。")
    return first, last


def is_own(message, channel_id, bot_id):
    # The bot flag alone also matches other bots; require this client's exact ID.
    return (
        message.channel.id == channel_id
        and message.author.id == bot_id
        and (
            message.webhook_id is None
            # Interaction webhooks use the application ID. Pycord 2.6.1 does not
            # expose Message.application_id; require its webhook ID and interaction metadata.
            or (
                message.webhook_id == bot_id
                and message.interaction_metadata is not None
            )
        )
    )


def snapshot(message):
    return {
        "id": message.id,
        "channel_id": message.channel.id,
        "author_id": message.author.id,
        "created_at": message.created_at.isoformat(),
        "content": message.content,
        "attachments": [
            {"id": item.id, "filename": item.filename, "url": item.url}
            for item in message.attachments
        ],
        "embeds": [embed.to_dict() for embed in message.embeds],
    }


async def select_messages(channel, bot_id, *, ids=None, time_range=None):
    selected, skipped = [], 0
    if ids is not None:
        for message_id in ids:
            try:
                message = await channel.fetch_message(message_id)
            except discord.NotFound as exc:
                if exc.code != 10008:
                    raise
                skipped += 1
                continue
            if is_own(message, channel.id, bot_id):
                selected.append(snapshot(message))
            else:
                skipped += 1
    else:
        first, last = time_range
        # Snowflake bounds preserve the inclusive start and exclusive end.
        after = discord.Object(discord.utils.time_snowflake(first) - 1)
        before = discord.Object(discord.utils.time_snowflake(last))
        count = 0
        async for message in channel.history(
            limit=SCAN_LIMIT + 1, after=after, before=before, oldest_first=True
        ):
            count += 1
            if count > SCAN_LIMIT:
                raise ValueError(
                    "時間範圍超過 1000 則訊息，請縮小範圍；本次未建立清單。"
                )
            if first <= message.created_at < last and is_own(
                message, channel.id, bot_id
            ):
                selected.append(snapshot(message))
                if len(selected) > MAX_MESSAGES:
                    raise ValueError(
                        "超過 100 則自身訊息，請縮小範圍；不會只刪一部分。"
                    )
            else:
                skipped += 1
    return sorted(selected, key=lambda row: row["id"]), skipped


async def delete_selected(channel, bot_id, rows, operator_id, audit_path):
    """Re-fetch each fixed ID; never delete another author's or edited messages."""
    counts = {"deleted": 0, "missing": 0, "changed": 0, "refused": 0, "failed": 0}
    # Exclusive creation fails closed if the audit cannot be saved.
    with audit_path.open("x", encoding="utf-8") as audit:
        audit.write(
            json.dumps(
                {
                    "type": "snapshot",
                    "operator_id": operator_id,
                    "bot_id": bot_id,
                    "channel_id": channel.id,
                    "created_at": datetime.now(UTC).isoformat(),
                    "messages": rows,
                },
                ensure_ascii=False,
            )
            + "\n"
        )
        audit.flush()
        for row in rows:
            outcome = "failed"
            try:
                message = await channel.fetch_message(row["id"])
                if not is_own(message, channel.id, bot_id):
                    outcome = "refused"
                elif snapshot(message) != row:
                    outcome = "changed"
                else:
                    await message.delete(reason=f"Own-message cleanup by {operator_id}")
                    outcome = "deleted"
            except discord.NotFound as exc:
                outcome = "missing" if exc.code == 10008 else "failed"
            except discord.HTTPException:
                # Pycord handles rate limits; keep failures explicit, do not retry a batch.
                outcome = "failed"
            counts[outcome] += 1
            audit.write(
                json.dumps({"type": "result", "id": row["id"], "status": outcome})
                + "\n"
            )
            audit.flush()
    return counts
