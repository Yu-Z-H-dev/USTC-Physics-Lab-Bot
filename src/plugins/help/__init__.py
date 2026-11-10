"""统一帮助命令：/help（也接受不带斜杠的 help）。"""

from nonebot import require

from src.utils.help_text import HELP_TEXT
from src.utils.safe_send import safe_finish

require("nonebot_plugin_alconna")

from nonebot_plugin_alconna import Alconna, on_alconna

help_cmd = on_alconna(Alconna("/help"), priority=0, block=True)
help_word = on_alconna(Alconna("help"), priority=0, block=True)


@help_cmd.handle()
async def _help_with_slash() -> None:
    await safe_finish(help_cmd, HELP_TEXT, reply_message=True)


@help_word.handle()
async def _help_plain() -> None:
    await safe_finish(help_word, HELP_TEXT, reply_message=True)
