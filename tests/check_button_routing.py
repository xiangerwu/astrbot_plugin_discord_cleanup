"""Run button tests through actual AstrBot source, without starting a bot.

Usage: python tests/check_button_routing.py /path/to/AstrBot
Only imports/dependencies are substituted; upstream definitions run unchanged.
"""

import __future__

import ast
import asyncio
import importlib
import logging
import sys
import types
import unittest
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, Mock

import discord
import test_cleanup as fixtures


def load_definitions(root, relative, names, namespace, container=None):
    path = root / relative
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    if container:
        tree.body = next(
            node for node in tree.body if getattr(node, "name", None) == container
        ).body
    tree.body = [node for node in tree.body if getattr(node, "name", None) in names]
    assert len(tree.body) == len(names), f"Missing upstream definitions: {path}"
    exec(  # noqa: S102 - Execute definitions from the explicitly supplied, trusted AstrBot checkout.
        compile(tree, str(path), "exec", flags=__future__.annotations.compiler_flag),
        namespace,
    )


def main(root):
    handlers = []

    def get_handler_or_create(handler, *args, **kwargs):
        metadata = types.SimpleNamespace(
            handler=handler,
            event_filters=[],
            handler_module_path=handler.__module__,
            handler_full_name=handler.__qualname__,
        )
        handlers.append(metadata)
        return metadata

    ns = {
        "HandlerFilter": object,
        "Stage": object,
        "register_stage": lambda cls: cls,
        "get_handler_or_create": get_handler_or_create,
        "EventType": types.SimpleNamespace(AdapterMessageEvent="message"),
        "logger": logging.getLogger("routing-test"),
        "star_handlers_registry": types.SimpleNamespace(
            get_handlers_by_event_type=lambda *args, **kwargs: handlers
        ),
        "SessionPluginManager": types.SimpleNamespace(
            filter_handlers_by_session=AsyncMock(
                side_effect=lambda event, selected: selected
            )
        ),
        "FILTERS": [],
        "USER_SESSIONS": {},
    }
    for name in [
        "At",
        "AtAll",
        "Reply",
        "ButtonInteraction",
        "PermissionTypeFilter",
        "CommandGroupFilter",
    ]:
        ns[name] = type(name, (), {})
    load_definitions(
        root, "astrbot/core/star/filter/button_action.py", ["ButtonActionFilter"], ns
    )
    load_definitions(
        root,
        "astrbot/core/star/filter/event_message_type.py",
        ["EventMessageTypeFilter"],
        ns,
    )
    load_definitions(
        root,
        "astrbot/core/star/register/star_handler.py",
        ["register_button_action", "register_event_message_type"],
        ns,
    )
    load_definitions(
        root, "astrbot/core/pipeline/waking_check/stage.py", ["WakingCheckStage"], ns
    )
    ns.update(
        asyncio=asyncio,
        cast=cast,
        MessageType=types.SimpleNamespace(
            GROUP_MESSAGE="group", FRIEND_MESSAGE="friend"
        ),
        AstrBotMessage=lambda: types.SimpleNamespace(group=None),
        MessageMember=lambda **kwargs: types.SimpleNamespace(**kwargs),
        Plain=lambda **kwargs: types.SimpleNamespace(**kwargs),
    )
    load_definitions(
        root,
        "astrbot/core/platform/sources/discord/discord_platform_adapter.py",
        ["_create_dynamic_callback"],
        ns,
        container="DiscordPlatformAdapter",
    )

    filters = sys.modules["astrbot.api.event"].filter
    filters.button_action = ns["register_button_action"]
    filters.event_message_type = ns["register_event_message_type"]
    fixtures.registered_commands.clear()
    importlib.reload(fixtures.main)

    async def dispatch_button(self):
        event = self.event
        event.stop_event.reset_mock()
        event.message_str = (
            "component:" + event.message_obj.raw_message.data["custom_id"] + ":2"
        )
        event.is_wake = False
        event._extras = {}
        event.get_extra = lambda key=None, default=None: (
            event._extras if key is None else event._extras.get(key, default)
        )
        event.set_extra = event._extras.__setitem__
        button = ns["ButtonInteraction"]()
        button.action_id = event.message_obj.raw_message.data["custom_id"]
        button.callback_data = None  # Discord adapter's non-astrbot: custom-ID path.
        event.get_button_interaction = lambda: button
        event.is_button_interaction = lambda: True
        event.is_private_chat = lambda: False
        event.get_messages = lambda: [button]
        stage = ns["WakingCheckStage"]()
        stage.ctx = types.SimpleNamespace(
            astrbot_config={**self.config, "wake_prefix": ["/"]}
        )
        stage.ignore_bot_self_message = stage.ignore_at_all = (
            stage.disable_builtin_commands
        ) = False
        stage.friend_message_needs_wake_prefix = False
        stage._umo_auto_name_recorder = Mock()
        await stage.process(event)
        selected = event.get_extra("activated_handlers")
        self.assertEqual(
            [item.handler.__name__ for item in selected],
            ["handle_button"],
            "AstrBot dropped the button before the plugin handler",
        )
        for item in selected:
            await item.handler(self.plugin, event)

    fixtures.PluginTests.dispatch_button = dispatch_button

    class RoutingTests(fixtures.PluginTests):
        async def test_native_core_callback_preserves_private_ack_and_event(self):
            adapter = types.SimpleNamespace(
                bot_self_id="10",
                handle_msg=AsyncMock(),
                _get_message_type=lambda *args: "group",
                _get_channel_id=lambda channel: str(channel.id),
                _get_group_name=lambda channel: "test",
            )
            interaction = types.SimpleNamespace(
                type=discord.InteractionType.application_command,
                id=1,
                token="test",
                data={},
                _session=None,
                _state=types.SimpleNamespace(
                    http=types.SimpleNamespace(proxy=None, proxy_auth=None)
                ),
            )
            response = discord.InteractionResponse(interaction)
            ctx = types.SimpleNamespace(
                defer=response.defer,
                interaction=interaction,
                followup=object(),
                channel=types.SimpleNamespace(id=50),
                channel_id=50,
                guild_id=60,
                author=types.SimpleNamespace(id=90, display_name="owner"),
            )
            transport = types.SimpleNamespace(create_interaction_response=AsyncMock())
            from discord.interactions import async_context

            context_token = async_context.set(transport)
            try:
                callback = ns["_create_dynamic_callback"](adapter, "dc_clean")
                await fixtures.main.private_callback(callback)(ctx, "1 2")
            finally:
                async_context.reset(context_token)
            request = transport.create_interaction_response.call_args.kwargs
            self.assertEqual(request["type"], 5)
            self.assertEqual(request["data"], {"flags": 64})
            adapter.handle_msg.assert_awaited_once()
            message, followup = adapter.handle_msg.call_args.args
            self.assertEqual(message.message_str, "dc_clean 1 2")
            self.assertIs(message.raw_message, interaction)
            self.assertTrue(message.raw_message.data[fixtures.main.PRIVATE_ACK])
            self.assertIs(followup, ctx.followup)

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(RoutingTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main(Path(sys.argv[1]).resolve()))
