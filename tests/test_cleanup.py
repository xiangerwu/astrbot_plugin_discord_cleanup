import importlib
import json
import logging
import sys
import tempfile
import time
import types
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import discord

ROOT = Path(__file__).resolve().parents[1]
package = types.ModuleType("cleanup_under_test")
package.__path__ = [str(ROOT)]
sys.modules[package.__name__] = package
cleanup = importlib.import_module("cleanup_under_test.core.cleanup")

# Only the AstrBot loading boundary is replaced. Pycord and plugin methods are real.
for name in [
    "astrbot",
    "astrbot.api",
    "astrbot.api.event",
    "astrbot.api.star",
    "astrbot.core",
    "astrbot.core.star",
    "astrbot.core.star.filter",
    "astrbot.core.star.filter.command",
]:
    sys.modules[name] = types.ModuleType(name)
sys.modules["astrbot.core.star.filter.command"].GreedyStr = type(
    "GreedyStr", (str,), {}
)
registered_commands = []


def command(name, **kwargs):
    registered_commands.append(name)
    return lambda fn: fn


sys.modules["astrbot.api"].logger = logging.getLogger("cleanup-test")
sys.modules["astrbot.api.event"].AstrMessageEvent = object
sys.modules["astrbot.api.event"].filter = types.SimpleNamespace(
    command=command,
    button_action=lambda *a, **kw: lambda fn: fn,
    event_message_type=lambda *a, **kw: lambda fn: fn,
    EventMessageType=types.SimpleNamespace(ALL="all"),
)
sys.modules["astrbot.api.star"].Context = object
sys.modules["astrbot.api.star"].Star = type(
    "Star", (), {"__init__": lambda self, context: setattr(self, "context", context)}
)
sys.modules["astrbot.api.star"].StarTools = types.SimpleNamespace(
    get_data_dir=lambda name: ROOT
)
main = importlib.import_module("cleanup_under_test.main")


def not_found():
    return discord.NotFound(
        types.SimpleNamespace(status=404, reason="Not Found"),
        {"code": 10008, "message": "Unknown Message"},
    )


class Channel:
    id = 50

    def __init__(self):
        self.messages = {}
        self.deleted = []
        self.can_manage = True
        self.guild = types.SimpleNamespace(
            id=60, fetch_member=AsyncMock(return_value=types.SimpleNamespace(bot=False))
        )
        self.send = AsyncMock(return_value=types.SimpleNamespace(id=999))

    def permissions_for(self, member):
        return types.SimpleNamespace(manage_messages=self.can_manage)

    async def fetch_message(self, message_id):
        if message_id not in self.messages:
            raise not_found()
        return self.messages[message_id]

    def history(self, **kwargs):
        self.history_args = kwargs

        async def iterate():
            for message in list(self.messages.values())[: kwargs["limit"]]:
                yield message

        return iterate()

    def add(
        self,
        message_id,
        author=10,
        content="hello",
        webhook=None,
        created=None,
        interaction=False,
    ):
        async def delete(**kwargs):
            self.deleted.append(message_id)
            del self.messages[message_id]

        item = types.SimpleNamespace(
            id=message_id,
            author=types.SimpleNamespace(id=author),
            channel=self,
            content=content,
            webhook_id=webhook,
            interaction_metadata=types.SimpleNamespace() if interaction else None,
            attachments=[],
            embeds=[],
            created_at=created or datetime(2026, 11, 7, 20, 7, tzinfo=UTC),
            delete=AsyncMock(side_effect=delete),
        )
        self.messages[message_id] = item
        return item


class ParsingTests(unittest.TestCase):
    def test_message_link_limit_is_100_distinct_targets(self):
        links = [f"https://discord.com/channels/60/50/{i}" for i in range(1, 102)]
        self.assertEqual(len(cleanup.parse_ids(" ".join(links[:100]), 60, 50)), 100)
        self.assertEqual(
            len(cleanup.parse_ids(" ".join(links[:100] + links[:1]), 60, 50)), 100
        )
        with self.assertRaises(ValueError):
            cleanup.parse_ids(" ".join(links), 60, 50)

    def test_ids_scope_dedup_and_invalid_values(self):
        self.assertEqual(
            cleanup.parse_ids("123,https://discord.com/channels/60/50/124,123", 60, 50),
            [123, 124],
        )
        for text in [
            "",
            "0",
            "-1",
            "１２３",
            str(2**64),
            "https://evil.example/60/50/123",
            "https://discord.com/channels/60/51/123",
            "https://discord.com/channels/61/50/123",
        ]:
            with self.subTest(text=text), self.assertRaises(ValueError):
                cleanup.parse_ids(text, 60, 50)

    def test_time_offsets_and_order(self):
        start, end = cleanup.parse_time_range("2026-11-08T04:07", "2026-11-07T20:09Z")
        self.assertEqual((end - start).total_seconds(), 120)
        for pair in [("bad", "bad"), ("2026-11-08", "2026-11-07")]:
            with self.assertRaises(ValueError):
                cleanup.parse_time_range(*pair)


class CleanupTests(unittest.IsolatedAsyncioTestCase):
    async def test_own_application_replies_and_identity_recheck(self):
        channel = Channel()
        channel.add(1, webhook=10, interaction=True)
        channel.add(2, webhook=10, interaction=True)
        channel.add(3, author=20, webhook=10, interaction=True)
        channel.add(4, webhook=20, interaction=True)
        channel.add(5, author=20)
        channel.add(6, webhook=10)
        rows, skipped = await cleanup.select_messages(
            channel, 10, ids=list(range(1, 7))
        )
        self.assertEqual([row["id"] for row in rows], [1, 2])
        self.assertEqual(skipped, 4)
        channel.messages[2].webhook_id = 20
        with tempfile.TemporaryDirectory() as directory:
            counts = await cleanup.delete_selected(
                channel, 10, rows, 90, Path(directory) / "audit.jsonl"
            )
        self.assertEqual(channel.deleted, [1])
        self.assertEqual(counts["deleted"], 1)
        self.assertEqual(counts["refused"], 1)

    async def test_actual_pycord_interaction_message_ownership(self):
        client = discord.Client(intents=discord.Intents.none())
        data = {
            "id": "1",
            "type": 20,
            "webhook_id": "10",
            "application_id": "10",
            "author": {
                "id": "10",
                "username": "bot",
                "discriminator": "0",
                "avatar": None,
                "bot": True,
            },
            "content": "registered",
            "attachments": [],
            "embeds": [],
            "edited_timestamp": None,
            "pinned": False,
            "mention_everyone": False,
            "tts": False,
            "interaction_metadata": {
                "id": "2",
                "type": 2,
                "user": {
                    "id": "90",
                    "username": "owner",
                    "discriminator": "0",
                    "avatar": None,
                },
                "authorizing_integration_owners": {"0": "60"},
            },
        }
        message = discord.Message(
            state=client._connection,
            channel=client.get_partial_messageable(50),
            data=data,
        )
        self.assertTrue(cleanup.is_own(message, 50, 10))
        message.interaction_metadata = None
        self.assertFalse(cleanup.is_own(message, 50, 10))

    async def test_exact_ids_filter_other_people_bots_and_webhooks(self):
        channel = Channel()
        channel.add(1)
        channel.add(2, author=20)
        channel.add(3, author=30)
        channel.add(4, webhook=10)
        rows, skipped = await cleanup.select_messages(channel, 10, ids=[1, 2, 3, 4, 5])
        self.assertEqual([row["id"] for row in rows], [1])
        self.assertEqual(skipped, 4)
        self.assertEqual(channel.deleted, [])

    async def test_time_boundaries_and_scan_limits(self):
        channel = Channel()
        start, end = cleanup.parse_time_range("2026-11-08T04:07", "2026-11-08T04:09")
        channel.add(1, created=start)
        channel.add(2, created=end)
        rows, _ = await cleanup.select_messages(channel, 10, time_range=(start, end))
        self.assertEqual([row["id"] for row in rows], [1])
        self.assertEqual(
            channel.history_args["after"].id, discord.utils.time_snowflake(start) - 1
        )
        with patch.object(cleanup, "SCAN_LIMIT", 1), self.assertRaises(ValueError):
            await cleanup.select_messages(channel, 10, time_range=(start, end))
        channel.add(3, created=start)
        with patch.object(cleanup, "MAX_MESSAGES", 1), self.assertRaises(ValueError):
            await cleanup.select_messages(channel, 10, time_range=(start, end))

    async def test_recheck_ownership_edits_missing_and_fixed_selection(self):
        channel = Channel()
        for number in range(1, 6):
            channel.add(number)
        rows, _ = await cleanup.select_messages(channel, 10, ids=[1, 2, 3, 4, 5])
        channel.messages[2].author.id = 20
        channel.messages[3].content = "edited after preview"
        del channel.messages[4]
        channel.messages[5].delete.side_effect = discord.Forbidden(
            types.SimpleNamespace(status=403, reason="Forbidden"),
            {"code": 50013, "message": "Missing Permissions"},
        )
        channel.add(6)  # Arrived after the preview; must never be added to deletion.
        with tempfile.TemporaryDirectory() as directory:
            audit = Path(directory) / "audit.jsonl"
            counts = await cleanup.delete_selected(channel, 10, rows, 90, audit)
            saved = [
                json.loads(line)
                for line in audit.read_text(encoding="utf-8").splitlines()
            ]
        self.assertEqual(
            counts,
            {"deleted": 1, "missing": 1, "changed": 1, "refused": 1, "failed": 1},
        )
        self.assertEqual(channel.deleted, [1])
        self.assertIn(6, channel.messages)
        self.assertEqual(len(saved), 6)
        self.assertEqual(saved[0]["messages"], rows)

    async def test_unwritable_audit_stops_before_deletion(self):
        channel = Channel()
        channel.add(1)
        rows, _ = await cleanup.select_messages(channel, 10, ids=[1])
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(OSError):
            await cleanup.delete_selected(
                channel, 10, rows, 90, Path(directory) / "absent" / "audit.jsonl"
            )
        self.assertEqual(channel.deleted, [])

    async def test_missing_channel_is_failure_not_missing_message(self):
        channel = Channel()
        channel.add(1)
        rows, _ = await cleanup.select_messages(channel, 10, ids=[1])
        channel.fetch_message = AsyncMock(
            side_effect=discord.NotFound(
                types.SimpleNamespace(status=404, reason="Not Found"),
                {"code": 10003, "message": "Unknown Channel"},
            )
        )
        with self.assertRaises(discord.NotFound):
            await cleanup.select_messages(channel, 10, ids=[1])
        with tempfile.TemporaryDirectory() as directory:
            counts = await cleanup.delete_selected(
                channel, 10, rows, 90, Path(directory) / "audit.jsonl"
            )
        self.assertEqual(counts["failed"], 1)
        self.assertEqual(counts["missing"], 0)
        self.assertEqual(channel.deleted, [])


class PluginTests(unittest.IsolatedAsyncioTestCase):
    def setup_event(self):
        self.channel = Channel()
        self.config = {"admins_id": ["90"]}
        self.context = types.SimpleNamespace(get_config=Mock(return_value=self.config))
        self.plugin = main.DiscordCleanupPlugin(self.context)
        self.event = types.SimpleNamespace(
            get_platform_name=lambda: "discord",
            get_self_id=lambda: "10",
            get_sender_id=lambda: "90",
            unified_msg_origin="discord:GroupMessage:50",
            stop_event=Mock(),
            client=types.SimpleNamespace(user=types.SimpleNamespace(id=10)),
            interaction_followup_webhook=None,
            message_obj=types.SimpleNamespace(
                raw_message=types.SimpleNamespace(channel=self.channel)
            ),
        )

    def button_event(self, token, action, owner=90, channel_id=50, message_id=999):
        raw = Mock(spec=discord.Interaction)
        raw.data = {"custom_id": f"dcclean:{token}:{action}"}
        raw.channel = self.channel
        raw.channel_id = channel_id
        raw.user = types.SimpleNamespace(id=owner)
        raw.message = types.SimpleNamespace(id=message_id)
        raw.followup = types.SimpleNamespace(send=AsyncMock())
        raw.edit_original_response = AsyncMock()
        self.event.message_obj.raw_message = raw
        return raw

    async def dispatch_button(self):
        await self.plugin.handle_button(self.event)

    async def test_single_preview_pagination_and_one_time_confirmation(self):
        self.setup_event()
        self.channel.can_manage = (
            False  # AstrBot owner need not be a Discord moderator.
        )
        for number in range(1, 7):
            self.channel.add(number)
        await self.plugin.clean(self.event, "1,2,3,4,5,6")
        self.event.stop_event.assert_called()
        self.channel.send.assert_awaited_once()
        self.assertEqual(self.channel.deleted, [])
        token, pending = next(iter(self.plugin.pending.items()))
        self.assertLess(len(self.plugin.render(pending)), 2000)
        raw = self.button_event(token, "next")
        await self.dispatch_button()
        raw.edit_original_response.assert_awaited_once()
        self.channel.send.assert_awaited_once()
        self.assertEqual(pending.page, 1)
        view = raw.edit_original_response.call_args.kwargs["view"]
        self.assertEqual(
            [item.disabled for item in view.children], [False, True, False, False]
        )
        raw = self.button_event(token, "prev")
        await self.dispatch_button()
        self.assertEqual(pending.page, 0)
        view = raw.edit_original_response.call_args.kwargs["view"]
        self.assertEqual(
            [item.disabled for item in view.children], [True, False, False, False]
        )
        self.assertEqual(
            [item.label for item in view.children],
            ["上一頁", "下一頁", "確認刪除全部 6 則", "取消"],
        )
        for action, expected_page in [("prev", 0), ("next", 1), ("next", 1)]:
            self.button_event(token, action)
            await self.dispatch_button()
            self.assertEqual(pending.page, expected_page)
        with tempfile.TemporaryDirectory() as directory:
            self.plugin.data_dir = Path(directory)
            raw = self.button_event(token, "confirm")
            await self.dispatch_button()
            self.assertEqual(raw.edit_original_response.await_count, 2)
            self.assertEqual(self.channel.deleted, list(range(1, 7)))
            raw.followup.send.assert_awaited_once()
            private_result = raw.followup.send.call_args
            self.assertTrue(private_result.kwargs["ephemeral"])
            self.assertIn("刪除 6 則", private_result.args[0])
            self.assertIn(token, private_result.args[0])
            public_result = raw.edit_original_response.call_args.kwargs["content"]
            self.assertNotIn("刪除 6 則", public_result)
            self.assertNotIn(token, public_result)
            await self.dispatch_button()
            self.assertEqual(self.channel.deleted, list(range(1, 7)))
            self.assertEqual(raw.followup.send.await_count, 2)
        self.channel.send.assert_awaited_once()
        self.channel.guild.fetch_member.assert_not_awaited()

    async def test_wrong_operator_channel_message_and_revoked_permission(self):
        self.setup_event()
        self.channel.add(1)
        await self.plugin.clean(self.event, "1")
        token = next(iter(self.plugin.pending))
        for action in ["prev", "next", "confirm", "cancel"]:
            for kwargs in [{"owner": 91}, {"channel_id": 51}, {"message_id": 1000}]:
                raw = self.button_event(token, action, **kwargs)
                await self.dispatch_button()
                raw.followup.send.assert_awaited_once()
                raw.edit_original_response.assert_not_awaited()
        self.config["admins_id"] = []
        for action in ["prev", "next", "confirm", "cancel"]:
            raw = self.button_event(token, action)
            await self.dispatch_button()
            raw.followup.send.assert_awaited_once()
            raw.edit_original_response.assert_not_awaited()
        self.assertEqual(self.channel.deleted, [])

    async def test_cancel_expiry_and_reload_never_delete(self):
        for mode in ["cancel", "expiry", "reload"]:
            self.setup_event()
            self.channel.add(1)
            await self.plugin.clean(self.event, "1")
            token = next(iter(self.plugin.pending))
            if mode == "expiry":
                self.plugin.pending[token].expires = time.monotonic() - 1
            elif mode == "reload":
                await self.plugin.terminate()
            raw = self.button_event(token, "cancel" if mode == "cancel" else "confirm")
            await self.dispatch_button()
            self.assertEqual(self.channel.deleted, [])
            self.assertNotIn(token, self.plugin.pending)
            if mode == "cancel":
                raw.edit_original_response.assert_awaited_once_with(
                    content="已取消清理，沒有刪除任何訊息。", view=None
                )
                await self.dispatch_button()
                raw.followup.send.assert_awaited_once()

    async def test_other_plugins_buttons_are_untouched(self):
        self.setup_event()
        raw = self.button_event("unrelated", "confirm")
        raw.data["custom_id"] = "another-plugin:confirm"
        await self.dispatch_button()
        self.event.stop_event.assert_not_called()
        raw.edit_original_response.assert_not_awaited()
        raw.followup.send.assert_not_awaited()

    async def test_discord_moderator_without_astrbot_admin_is_denied(self):
        self.setup_event()
        self.config["admins_id"] = []
        self.channel.add(1)
        await self.plugin.clean(self.event, "1")
        self.assertEqual(self.plugin.pending, {})
        self.assertEqual(self.channel.deleted, [])
        self.channel.send.assert_awaited_once()
        self.assertIn("AstrBot", self.channel.send.call_args.args[0])

    async def test_unified_command_detects_targets_time_and_shows_usage(self):
        self.assertEqual(registered_commands, ["dc_clean"])
        for arguments in [
            "1 https://discord.com/channels/60/50/2",
            "1, 2",
            "2026-11-08T04:07 2026-11-08T04:08",
        ]:
            with self.subTest(arguments=arguments):
                self.setup_event()
                self.channel.add(1)
                self.channel.add(2)
                await self.plugin.clean(self.event, arguments)
                pending = next(iter(self.plugin.pending.values()))
                self.assertEqual([row["id"] for row in pending.rows], [1, 2])
                self.context.get_config.assert_called_with(
                    self.event.unified_msg_origin
                )
                self.assertEqual(self.channel.deleted, [])
        for arguments in ["", "help", "bad", "2026-11-08T04:07", "1 invalid"]:
            with self.subTest(arguments=arguments):
                self.setup_event()
                self.channel.add(1)
                await self.plugin.clean(self.event, arguments)
                self.assertEqual(self.plugin.pending, {})
                self.channel.send.assert_awaited_once()
                self.assertIn("/dc_clean", self.channel.send.call_args.args[0])
                self.assertEqual(self.channel.deleted, [])

    async def test_slash_followup_and_markdown_size(self):
        self.setup_event()
        for number in range(1, 6):
            self.channel.add(
                number, content="@everyone https://example.com/ " + "*_~`" * 1000
            )
        webhook = types.SimpleNamespace(
            send=AsyncMock(return_value=types.SimpleNamespace(id=999))
        )
        self.event.interaction_followup_webhook = webhook
        await self.plugin.clean(self.event, "1,2,3,4,5")
        webhook.send.assert_awaited_once()
        self.channel.send.assert_not_awaited()
        args, kwargs = webhook.send.call_args
        self.assertLess(len(args[0]), 2000)
        self.assertNotIn("@everyone", args[0])
        self.assertIn("https://example.com/", args[0])
        self.assertEqual(
            sum(
                line.startswith("`") and line.endswith("`")
                for line in args[0].splitlines()
            ),
            5,
        )
        self.assertFalse(kwargs["allowed_mentions"].everyone)
        self.assertTrue(kwargs["view"].is_finished())


if __name__ == "__main__":
    unittest.main()
