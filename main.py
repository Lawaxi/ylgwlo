import asyncio
from collections import deque
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
        self.target_groups = [g.strip() for g in raw_group.split(",") if g.strip()] if raw_group else []

        raw_anti_recall = str(config.get("anti_recall_qq", "")).strip()
        self.anti_recall_qqs = [q.strip() for q in raw_anti_recall.split(",") if q.strip()] if raw_anti_recall else []

        self.msg_cache = {}
        self.msg_id_order = deque(maxlen=10)

        db_config = {
            "host": self.cfg.get("db_host"),
            "port": self.cfg.get("db_port"),
            "user": self.cfg.get("db_user"),
            "password": self.cfg.get("db_password"),
            "database": self.cfg.get("db_name")
        }

        self.config = Config(self.cfg)
        self.db = Database(db_config)
        self.handler = WifeHandler(self.config, self.db, self.cfg)
        
        self.schedule = WifeLotterySchedule(self.handler)
        asyncio.create_task(self.schedule.start())

        logger.info("YLG48 Wife Lottery 插件已加载")

    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    async def on_message(self, event: AstrMessageEvent):
        group_id = str(getattr(event.message_obj, "group_id", ""))

        if self.target_groups and group_id not in self.target_groups:
            return

        text = (event.message_str or "").strip()
        user_id = str(event.get_sender_id())

        if user_id in self.anti_recall_qqs:
            msg_id = str(getattr(event.message_obj, "message_id", ""))
            if msg_id:
                components = []
                if event.message_obj and hasattr(event.message_obj, "message"):
                    for comp in event.message_obj.message:
                        if isinstance(comp, (Comp.Plain, Comp.Image)):
                            components.append(comp)
                
                if not components and text:
                    components.append(Comp.Plain(text))

                if len(self.msg_id_order) >= 10:
                    old_id = self.msg_id_order.popleft()
                    self.msg_cache.pop(old_id, None)

                self.msg_cache[msg_id] = components
                self.msg_id_order.append(msg_id)

        try:
            if text in self.config.get_lottery_commands():
                async for result in self.handler.lai_ge_lao_po(user_id, group_id, event):
                    yield result
                return

            if text in self.config.get_data_commands():
                result = await asyncio.to_thread(self.handler.wo_de_lao_po, user_id, group_id)
                yield event.chain_result([
                    Comp.At(qq=user_id),
                    Comp.Plain(result)
                ])
                return

            for cmd in self.config.get_wish_commands():
                if text.startswith(cmd):
                    try:
                        target = text[len(cmd):].strip()
                        if not target:
                            raise ValueError()
                        
                        result = await asyncio.to_thread(self.handler.wish, user_id, group_id, target)
                        yield event.chain_result([
                            Comp.At(qq=user_id),
                            Comp.Plain(f"\n{result}")
                        ])
                    except Exception:
                        wish_error = self.cfg.get("wishError", "许愿格式错误，例：%s 林忆宁")
                        yield event.chain_result([
                            Comp.At(qq=user_id),
                            Comp.Plain(f"\n{wish_error % cmd}")
                        ])
                    return

            if text in self.config.get_rank_commands():
                result = await asyncio.to_thread(self.handler.rank, user_id, group_id)
                yield event.chain_result([
                    Comp.At(qq=user_id),
                    Comp.Plain(result)
                ])
                return

        except Exception as e:
            logger.error(f"YLG48 插件错误: {e}", exc_info=True)
            error_msg = self.cfg.get("errorMsg", "系统错误，请稍后再试")
            yield event.chain_result([
                Comp.At(qq=user_id),
                Comp.Plain(f"\n{error_msg}")
            ])


    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_group_notice(self, event: AstrMessageEvent):
        try:
            msg_obj = event.message_obj
            raw = getattr(msg_obj, "raw_message", None) if msg_obj else None
            if not isinstance(raw, dict):
                return

            post_type = raw.get("post_type")
            notice_type = raw.get("notice_type")

            if post_type == "notice" and notice_type in ["group_recall", "group_msg_recall"]:
                recalled_msg_id = str(raw.get("message_id") or "").strip()
                target_user_id = str(raw.get("user_id") or "").strip()
                group_id = str(raw.get("group_id") or "").strip()

                if target_user_id in self.anti_recall_qqs and recalled_msg_id in self.msg_cache:
                    cached_components = self.msg_cache.get(recalled_msg_id)
                    if cached_components:
                        try:
                            member_info = await event.bot.get_group_member_info(
                                group_id=int(group_id), 
                                user_id=int(target_user_id)
                            )
                            hq_info = member_info.get("card") or member_info.get("nickname") or f"({target_user_id})"
                        except Exception:
                            hq_info = f"({target_user_id})"

                        recall_format = self.cfg.get("recallMsg", "%s撤回消息：")
                        result_chain = [Comp.Plain(recall_format % hq_info)]
                        result_chain.extend(cached_components)
                        
                        self.msg_cache.pop(recalled_msg_id, None)
                        try:
                            self.msg_id_order.remove(recalled_msg_id)
                        except ValueError:
                            pass

                        await event.send(event.chain_result(result_chain))
                        
        except Exception as e:
            logger.error(f"防撤回处理错误: {e}", exc_info=True)
