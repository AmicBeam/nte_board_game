# SPDX-License-Identifier: GPL-3.0-only
from nonebot import on_command
from nonebot.typing import T_State
from nonebot.adapters.onebot.v11 import Bot, MessageEvent

from .nte_account_db import issue_account_register_code
from .utils.logger import Logger, log_function_call
from .utils.message_util import MessageUtils


register_account = on_command('注册账号')
reset_password = on_command('重置密码')


async def _issue_password_reply(bot: Bot, event: MessageEvent, action_label: str, nickname: str = ''):
    user_id = int(event.get_user_id())
    msg = MessageUtils.gen_at_message(event, user_id)
    code, created = issue_account_register_code(str(user_id), nickname)
    if action_label == 'register':
        if created:
            reply = f"账户注册成功，网页登录密码为：{code}。"
        else:
            reply = f"已生成新的网页登录密码：{code}。"
        reply += "\n你的 QQ 号就是账户。若填写了用户名，系统会自动截取前 8 个字保存。"
    else:
        reply = f"密码已重置，新的网页登录密码为：{code}。"
    reply += "\n该密码永久有效，请在 NTE 网页中使用该密码登录，登录后也可以在网页里修改用户名和密码。"
    await MessageUtils.send_message(bot, event, msg + reply)


@register_account.handle()
@log_function_call
async def h_register_account(bot: Bot, event: MessageEvent, state: T_State):
    try:
        nickname = str(event.get_message()).replace('注册账户', '', 1).strip()
        await _issue_password_reply(bot, event, 'register', nickname)
    except Exception as e:
        user_id = int(event.get_user_id())
        msg = MessageUtils.gen_at_message(event, user_id)
        Logger().error(f"Error in register_account: {str(e)}")
        await MessageUtils.send_message(bot, event, msg + "注册账户过程中发生错误，请稍后重试")


@reset_password.handle()
@log_function_call
async def h_reset_password(bot: Bot, event: MessageEvent, state: T_State):
    try:
        await _issue_password_reply(bot, event, 'reset')
    except Exception as e:
        user_id = int(event.get_user_id())
        msg = MessageUtils.gen_at_message(event, user_id)
        Logger().error(f"Error in reset_password: {str(e)}")
        await MessageUtils.send_message(bot, event, msg + "重置密码过程中发生错误，请稍后重试")
