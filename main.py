import asyncio
from astrbot.api.star import Star, Context
from astrbot.api.event import filter, AstrMessageEvent
import astrbot.api.message_components as Comp
from astrbot.api import logger, AstrBotConfig
from .wife_handler import WifeHandler
from .config import Config
from .database import Database
from .schedule_task import WifeLotterySchedule

class WifeLotteryPlugin(Star):

    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)

        self.cfg = config
        raw_group = str(config.get("target_group", "")).strip()
        if raw_group:
            self.target_groups = [g.strip() for g in raw_group.split(",") if g.strip()]
        else:
            self.target_groups = []

        db_config = {
            "host": self.cfg.get("db_host"),
            "port": self.cfg.get("db_port"),
            "user": self.cfg.get("db_user"),
            "password": self.cfg.get("db_password"),
            "database": self.cfg.get("db_name")
        }

        self.config = Config(self.cfg)
        self.db = Database(db_config)
        self.handler = WifeHandler(self.config, self.db)
        
        # 后台定时刷新任务
        self.schedule = WifeLotterySchedule(self.handler)
        asyncio.create_task(self.schedule.start())

        logger.info("ylgwlo 插件成功加载")

    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    async def on_message(self, event: AstrMessageEvent):
        # 统一将 group_id 转换为 str
        group_id = str(getattr(event.message_obj, "group_id", ""))

        if self.target_groups and group_id not in self.target_groups:
            return
        # 不配置目标群的话则全局适用

        text = (event.message_str or "").strip()
        # 统一将 user_id 转换为 str
        user_id = str(event.get_sender_id())

        try:
            # 1. 来个老婆 / 换个老婆 (原函数包含异步逻辑，保持 async for)
            if text in self.config.get_lottery_commands():
                async for result in self.handler.lai_ge_lao_po(user_id, group_id, event):
                    yield result
                return

            # 2. 我的老婆 (内部包含 pymysql 同步阻塞，移至线程池异步执行)
            if text in self.config.get_data_commands():
                result = await asyncio.to_thread(self.handler.wo_de_lao_po, user_id, group_id)
                yield event.chain_result([
                    Comp.At(qq=user_id),
                    Comp.Plain(result)
                ])
                return

            # 3. 许愿
            for cmd in self.config.get_wish_commands():
                if text.startswith(cmd):
                    try:
                        # 使用更加健壮的方式截取许愿目标，防止切分空格报错
                        target = text[len(cmd):].strip()
                        if not target:
                            raise ValueError("许愿目标不能为空")
                        
                        # 移至线程池异步执行
                        result = await asyncio.to_thread(self.handler.wish, user_id, group_id, target)
                        yield event.chain_result([
                            Comp.At(qq=user_id),
                            Comp.Plain(f"\n{result}")
                        ])
                    except Exception:
                        yield event.chain_result([
                            Comp.At(qq=user_id),
                            Comp.Plain(f"\n{self.cfg.get('wishError', '许愿格式错误') % cmd}")
                        ])
                    return

            # 4. 排名 (内部包含较多数据库和循环计算，移至线程池异步执行)
            if text in self.config.get_rank_commands():
                result = await asyncio.to_thread(self.handler.rank, user_id, group_id)
                yield event.chain_result([
                    Comp.At(qq=user_id),
                    Comp.Plain(result)
                ])
                return

        except Exception as e:
            # 使用 logger.error 并附带 exc_info=True，这样后台能够看到具体的报错行数和调用栈
            logger.error(f"ylgwlo 插件运行异常: {e}", exc_info=True)
            yield event.chain_result([
                Comp.At(qq=user_id),
                Comp.Plain("抽奖系统似乎出了一点小状况，请稍后再试。")
            ])
