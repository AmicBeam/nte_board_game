
import asyncio
import time
from typing import Optional
from nonebot.adapters.onebot.v11 import MessageEvent, Bot, Message
from src.plugins.utils.logger import Logger

report_type = "text"

class MessageUtils:
    """消息处理工具类"""
    
    # 全局最后发送时间
    _last_send_time = 0
    _min_interval = 2.0  # 最小发送间隔（秒）
    
    @staticmethod
    def gen_at_message(event: MessageEvent, user_id: int) -> str:
        """生成@消息
        
        Args:
            event: 消息事件
            user_id: 用户QQ号
            
        Returns:
            str: 格式化的@消息
        """
        return f"[CQ:at,qq={user_id}] " if event.message_type != "private" else ""

    @staticmethod
    async def send_message(bot: Optional[Bot], event: Optional[MessageEvent], message: str):
        """发送消息（带全局频率限制，每2秒最多一条）
        
        Args:
            bot: Bot实例
            event: 消息事件
            message: 要发送的消息
        """
        if bot is None or event is None or len(message)==0:
            Logger().warning(f"Message not sent: bot={bot is not None}, event={event is not None}, message_length={len(message) if message else 0}")
            return
        current_time = time.time()
        
        # 检查是否需要等待
        time_since_last = current_time - MessageUtils._last_send_time
        if time_since_last < MessageUtils._min_interval:
            # 需要等待的时间
            wait_time = MessageUtils._min_interval - time_since_last
            Logger().info(f"Global rate limiting: waiting {wait_time:.2f}s before sending message")
            await asyncio.sleep(wait_time)
        
        # 更新最后发送时间
        MessageUtils._last_send_time = time.time()
        
        # 发送消息
        try:
            await bot.send(event, Message(message))
            Logger().info("Message sent successfully")
        except Exception as e:
            Logger().error(f"Failed to send message: {str(e)}")
            raise
