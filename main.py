import re
import secrets
import time
from dataclasses import dataclass
from datetime import datetime
from sys import maxsize

import discord
from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, StarTools
from astrbot.core.star.filter.command import GreedyStr

from .core.cleanup import (
    DISPLAY_TZ,
    delete_selected,
    parse_ids,
    parse_time_range,
    select_messages,
)

PREFIX = "dcclean:"
PAGE_SIZE = 5
PREVIEW_SECONDS = 300
USAGE = (
    "用法（僅 AstrBot 登記的管理員）：\n"
    "時間：`/dc_clean 2026-11-08T04:07 2026-11-08T04:09`\n"
    "訊息：`/dc_clean 訊息ID或完整連結`，多筆用空格或逗號分隔。\n"
    "時間預設 UTC+08:00，包含開始、不含結束；只預覽本頻道的自身訊息，確認後才刪除。"
)


@dataclass
class Preview:
    owner_id: int
    channel_id: int
    bot_id: int
    rows: list
    skipped: int
    expires: float
    page: int = 0
    message_id: int = 0


class DiscordCleanupPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.data_dir = StarTools.get_data_dir("astrbot_plugin_discord_cleanup")
        # ponytail: previews live in memory for five minutes; reload cancels them.
        self.pending = {}

    @filter.command("dc_clean", priority=maxsize + 1)
    async def clean(self, event: AstrMessageEvent, targets: GreedyStr):
        """清理自身訊息：兩個 ISO 時間或訊息 ID／連結；不填顯示用法。"""
        event.stop_event()
        if event.get_platform_name() != "discord":
            await event.send(
                event.plain_result("此插件只支援 Discord 伺服器頻道／討論串。")
            )
            return
        raw = event.message_obj.raw_message
        channel = raw.channel
        try:
            bot_id = event.client.user.id
            if str(bot_id) != str(event.get_self_id()):
                raise ValueError("機器人身分不一致，已停止。")
            owner_id = int(event.get_sender_id())
            self.check_operator(event, channel)
            self.pending = {
                key: item
                for key, item in self.pending.items()
                if item.expires > time.monotonic()
            }
            # Replace this operator's previous preview in this channel, even on invalid input.
            self.pending = {
                key: item
                for key, item in self.pending.items()
                if (item.owner_id, item.channel_id, item.bot_id)
                != (owner_id, channel.id, bot_id)
            }
            targets = targets.strip()
            if not targets or targets.lower() in {"help", "幫助", "說明"}:
                await self.reply(event, USAGE)
                return
            ids = time_range = None
            try:
                if re.match(r"\d{4}-", targets):
                    parts = targets.split()
                    if len(parts) != 2:
                        raise ValueError("請提供開始與結束兩個時間。")
                    time_range = parse_time_range(*parts)
                else:
                    ids = parse_ids(targets, channel.guild.id, channel.id)
            except ValueError as exc:
                raise ValueError(f"{exc}\n\n{USAGE}") from exc
            if ids is not None:
                rows, skipped = await select_messages(channel, bot_id, ids=ids)
            else:
                rows, skipped = await select_messages(
                    channel, bot_id, time_range=time_range
                )
            if not rows:
                await self.reply(
                    event,
                    f"沒有可刪除的自身訊息；已略過 {skipped} 則非自身或不存在的訊息。",
                )
                return
            token = secrets.token_hex(8)
            pending = Preview(
                owner_id,
                channel.id,
                bot_id,
                rows,
                skipped,
                time.monotonic() + PREVIEW_SECONDS,
            )
            message = await self.reply(
                event, self.render(pending), view=self.controls(token, pending)
            )
            pending.message_id = message.id
            self.pending[token] = pending
        except ValueError as exc:
            await self.reply(event, str(exc))
        except discord.HTTPException as exc:
            logger.warning(
                "[discord_cleanup] Preview HTTP failure: %s", type(exc).__name__
            )
            await self.reply(
                event,
                "無法讀取或顯示清單，沒有執行刪除。請檢查頻道讀取歷史與發送訊息權限。",
            )

    # AstrBot routes components only to ButtonActionFilter handlers, even at high priority.
    @filter.button_action(priority=maxsize + 2)
    async def handle_button(self, event: AstrMessageEvent):
        if event.get_platform_name() != "discord":
            return
        interaction = event.message_obj.raw_message
        if not isinstance(interaction, discord.Interaction):
            return
        custom_id = (interaction.data or {}).get("custom_id", "")
        if not custom_id.startswith(PREFIX):
            return
        event.stop_event()
        parts = custom_id.split(":")
        if len(parts) != 3:
            return
        _, token, action = parts
        pending = self.pending.get(token)
        if pending is None or pending.expires <= time.monotonic():
            self.pending.pop(token, None)
            await interaction.followup.send(
                "此清單已過期、取消或使用過，請重新預覽。", ephemeral=True
            )
            return
        if (
            interaction.user.id != pending.owner_id
            or interaction.channel_id != pending.channel_id
            or event.client.user.id != pending.bot_id
            or interaction.message.id != pending.message_id
        ):
            await interaction.followup.send(
                "只有原操作者能在原頻道操作這份清單。", ephemeral=True
            )
            return
        try:
            self.check_operator(event, interaction.channel)
            if action in {"prev", "next"}:
                last_page = (len(pending.rows) - 1) // PAGE_SIZE
                pending.page = max(
                    0, min(last_page, pending.page + (1 if action == "next" else -1))
                )
                await interaction.edit_original_response(
                    content=self.render(pending),
                    view=self.controls(token, pending),
                    allowed_mentions=discord.AllowedMentions.none(),
                )
            elif action == "cancel":
                self.pending.pop(token, None)
                await interaction.edit_original_response(
                    content="已取消清理，沒有刪除任何訊息。", view=None
                )
            elif action == "confirm":
                # Consume before any I/O so the same preview cannot execute twice.
                if self.pending.pop(token, None) is None:
                    return
                await interaction.edit_original_response(
                    content=f"正在清理已確認的 {len(pending.rows)} 則自身訊息…",
                    view=None,
                )
                audit_path = self.data_dir / f"cleanup-{token}.jsonl"
                counts = await delete_selected(
                    interaction.channel,
                    pending.bot_id,
                    pending.rows,
                    pending.owner_id,
                    audit_path,
                )
                summary = (
                    f"清理完成：刪除 {counts['deleted']} 則；原已不存在 {counts['missing']} 則；"
                    f"內容已變更 {counts['changed']} 則；非自身 {counts['refused']} 則；失敗 {counts['failed']} 則。\n"
                    "未刪除項目均保留。紀錄編號：" + token
                )
                await interaction.edit_original_response(content=summary, view=None)
        except ValueError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
        except (discord.HTTPException, OSError) as exc:
            logger.error(
                "[discord_cleanup] Cleanup interrupted: %s; audit=%s",
                type(exc).__name__,
                token,
            )
            await interaction.edit_original_response(
                content=f"操作中斷，未自動重試。請重新預覽剩餘訊息；紀錄編號：{token}。",
                view=None,
            )

    def check_operator(self, event, channel):
        if getattr(channel, "guild", None) is None:
            raise ValueError("請在 Discord 伺服器的文字頻道／討論串使用，私訊不支援。")
        # Read the current session's admin list again for every button interaction.
        config = self.context.get_config(event.unified_msg_origin)
        if str(event.get_sender_id()) not in config.get("admins_id", []):
            raise ValueError(
                "只有 AstrBot 登記的管理員可以清理，請在 AstrBot 管理員設定中加入你的 Discord 使用者 ID。"
            )

    async def reply(self, event, content, **kwargs):
        kwargs["allowed_mentions"] = discord.AllowedMentions.none()
        if event.interaction_followup_webhook:
            return await event.interaction_followup_webhook.send(
                content, wait=True, **kwargs
            )
        return await event.message_obj.raw_message.channel.send(content, **kwargs)

    def render(self, pending):
        start = pending.page * PAGE_SIZE
        lines = [
            f"**自身訊息清理預覽：共 {len(pending.rows)} 則**",
            f"第 {pending.page + 1}/{(len(pending.rows) - 1) // PAGE_SIZE + 1} 頁 · 已略過 {pending.skipped} 則 · 時間 UTC+08:00",
            "確認會刪除整份清單，不只本頁。5 分鐘內有效；翻頁只更新本訊息。",
        ]
        for row in pending.rows[start : start + PAGE_SIZE]:
            stamp = (
                datetime.fromisoformat(row["created_at"])
                .astimezone(DISPLAY_TZ)
                .strftime("%m-%d %H:%M:%S")
            )
            excerpt = " ".join(row["content"].split())[:70] or "（附件或嵌入訊息）"
            # Inline code prevents copied links from expanding into more previews.
            excerpt = discord.utils.escape_mentions(excerpt).replace("`", "ˋ")
            lines.append(f"`{row['id']}` · {stamp}\n`{excerpt}`")
        return "\n\n".join(lines)

    def controls(self, token, pending):
        # AstrBot owns component dispatch and acknowledgement; no second Pycord callback.
        view = discord.ui.View(timeout=None)
        view.stop()
        for action, label, style, disabled in [
            ("prev", "上一頁", discord.ButtonStyle.secondary, pending.page == 0),
            (
                "next",
                "下一頁",
                discord.ButtonStyle.secondary,
                (pending.page + 1) * PAGE_SIZE >= len(pending.rows),
            ),
            (
                "confirm",
                f"確認刪除全部 {len(pending.rows)} 則",
                discord.ButtonStyle.danger,
                False,
            ),
            ("cancel", "取消", discord.ButtonStyle.secondary, False),
        ]:
            view.add_item(
                discord.ui.Button(
                    label=label,
                    style=style,
                    disabled=disabled,
                    custom_id=f"{PREFIX}{token}:{action}",
                )
            )
        return view

    async def terminate(self):
        self.pending.clear()
