# SPDX-License-Identifier: GPL-3.0-only
from nonebot import get_driver, on_command
from nonebot.typing import T_State
from nonebot.adapters.onebot.v11 import Bot, Message, PrivateMessageEvent

from .nte_account_db import issue_account_register_code, publish_shaft_character
from .utils.logger import Logger


register_account = on_command('注册账号')
reset_password = on_command('重置密码')
publish_character = on_command('公开角色', aliases={'解除角色未公开'})


def _build_password_reply(event: PrivateMessageEvent, action_label: str, nickname: str = '') -> str:
    user_id = int(event.get_user_id())
    code, created = issue_account_register_code(str(user_id), nickname)
    if action_label == 'register':
        if created:
            reply = f"账号注册成功，网页登录密码为：{code}。"
        else:
            reply = f"已生成新的网页登录密码：{code}。"
        reply += "\n你的 QQ 号就是账号。若填写了用户名，系统会自动截取前 8 个字保存。"
    else:
        reply = f"密码已重置，新的网页登录密码为：{code}。"
    reply += "\n该密码永久有效，请在 NTE 网页中使用该密码登录，登录后也可以在网页里修改用户名和密码。"
    return reply


@register_account.handle()
async def h_register_account(bot: Bot, event: PrivateMessageEvent, state: T_State):
    try:
        nickname = str(event.get_message()).replace('注册账号', '', 1).strip()
        reply = _build_password_reply(event, 'register', nickname)
    except Exception as e:
        Logger().error(f"Error in register_account: {str(e)}")
        await register_account.finish(Message("注册账号过程中发生错误，请稍后重试"))
    else:
        await register_account.finish(Message(reply))


@reset_password.handle()
async def h_reset_password(bot: Bot, event: PrivateMessageEvent, state: T_State):
    try:
        reply = _build_password_reply(event, 'reset')
    except Exception as e:
        Logger().error(f"Error in reset_password: {str(e)}")
        await reset_password.finish(Message("重置密码过程中发生错误，请稍后重试"))
    else:
        await reset_password.finish(Message(reply))


def _is_superuser(event: PrivateMessageEvent) -> bool:
    user_id = str(event.get_user_id())
    configured = getattr(get_driver().config, 'superusers', set())
    return user_id in {str(item) for item in configured}


@publish_character.handle()
async def h_publish_character(bot: Bot, event: PrivateMessageEvent, state: T_State):
    if not _is_superuser(event):
        await publish_character.finish(Message("只有机器人管理员可以公开角色。"))

    character_name = str(event.get_message())
    for command_name in ('解除角色未公开', '公开角色'):
        character_name = character_name.replace(command_name, '', 1).strip()
    if not character_name:
        await publish_character.finish(Message("请使用“公开角色 角色名”，例如：公开角色 伊洛伊。"))

    try:
        result = publish_shaft_character(character_name)
    except Exception as e:
        Logger().error(f"Error in publish_character: {str(e)}")
        await publish_character.finish(Message("公开角色过程中发生错误，请稍后重试。"))

    if result == 'not_found':
        await publish_character.finish(Message(f"未找到处于未公开状态的角色：{character_name}。"))
    if result == 'already_published':
        await publish_character.finish(Message(f"{character_name} 已经是公开角色。"))
    await publish_character.finish(Message(f"已将 {character_name} 移出未公开角色列表。"))
