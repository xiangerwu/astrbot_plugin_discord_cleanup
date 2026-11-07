"""Make only dc_clean's initial Discord acknowledgement private."""

from functools import wraps

PRIVATE_ACK = "_discord_cleanup_private_ack"


class PrivateContext:
    def __init__(self, context):
        self.context = context

    def __getattr__(self, name):
        return getattr(self.context, name)

    async def defer(self, **kwargs):
        kwargs["ephemeral"] = True
        result = await self.context.defer(**kwargs)
        self.context.interaction.data[PRIVATE_ACK] = True
        return result


def private_callback(callback):
    @wraps(callback)
    async def invoke(context, *args, **kwargs):
        return await callback(PrivateContext(context), *args, **kwargs)

    return invoke
