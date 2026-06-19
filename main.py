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
        
        # 群组多开配置
        raw_group = str(config.get("target_group", "")).strip()
        if raw_group:
            self.target_groups = [g.strip() for g in raw_group.split(",") if g.strip()]
        else:
            self.target_groups = []

        # 💡 防撤回特定成员 QQ 配置处理
        raw_anti_recall = str(config.get("anti_recall_qq", "123456")).strip()
        if raw_anti_recall:
            self.anti_recall_qqs = [q.strip() for q in raw_anti_recall.split(",") if q.strip()]
        else:
            self.anti_recall_qqs = ["123456"]

        # 💡 内存消息缓存：只储存10条，满员自动 pop
        # 结构为: {"message_id": [Comp.Plain, Comp.Image, ...]}
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
        self.handler = WifeHandler(self.config, self.db)
        
        # 后台定时刷新任务
        self.schedule = WifeLotterySchedule(self.handler)
        asyncio.create_task(self.schedule.start())

        logger.info("ylgwlo 插件成功加载 (防撤回功能已就绪)")

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

        # 💡 【核心新增】如果发送者是特定的监控成员，将消息放入内存队列中缓存
        if user_id in self.anti_recall_qqs:
            msg_id = str(getattr(event.message_obj, "message_id", ""))
            if msg_id:
                # 提取消息链中的文本组件与图片组件
                components = []
                if event.message_obj and hasattr(event.message_obj, "message"):
                    for comp in event.message_obj.message:
                        if isinstance(comp, (Comp.Plain, Comp.Image)):
                            components.append(comp)
                
                # 如果没有提取到具体组件但有纯文本，做一层保底
                if not components and text:
                    components.append(Comp.Plain(text))

                # 存入缓存，如果超过 10 条，自动将最老的 key 弹出
                if len(self.msg_id_order) >= 10:
                    old_id = self.msg_id_order.popleft()
                    self.msg_cache.pop(old_id, None)

                self.msg_cache[msg_id] = components
                self.msg_id_order.append(msg_id)

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
                        target = text[len(cmd):].strip()
                        if not target:
                            raise ValueError("许愿目标不能为空")
                        
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
            logger.error(f"ylgwlo 插件运行异常: {e}", exc_info=True)
            yield event.chain_result([
                Comp.At(qq=user_id),
                Comp.Plain("抽奖系统似乎出了一点小状况，请稍后再试。")
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

            # 精确匹配群消息撤回规范
            if post_type == "notice" and notice_type in ["group_recall", "group_msg_recall"]:
                recalled_msg_id = str(raw.get("message_id") or "").strip()
                target_user_id = str(raw.get("user_id") or "").strip()
                group_id = str(raw.get("group_id") or "").strip()

                # 验证撤回人属于监控列表，且消息仍在我们的 10 条短生命周期缓存中
                if target_user_id in self.anti_recall_qqs and recalled_msg_id in self.msg_cache:
                    cached_components = self.msg_cache.get(recalled_msg_id)
                    if cached_components:
                        # 💡 获取用户昵称/群名片核心逻辑
                        try:
                            member_info = await event.bot.get_group_member_info(
                                group_id=int(group_id), 
                                user_id=int(target_user_id)
                            )
                            # 优先群名片(card)，其次QQ昵称(nickname)
                            hq_info = member_info.get("card") or member_info.get("nickname") or f"({target_user_id})"
                        except Exception:
                            hq_info = f"({target_user_id})"

                        # 重新组装带有用户昵称的消息链
                        result_chain = [Comp.Plain(f"{hq_info}撤回消息：")]
                        result_chain.extend(cached_components)
                        
                        # 释放内存，移出队列与映射表
                        self.msg_cache.pop(recalled_msg_id, None)
                        try:
                            self.msg_id_order.remove(recalled_msg_id)
                        except ValueError:
                            pass

                        # 发送复原消息
                        await event.send(event.chain_result(result_chain))
                        
        except Exception as e:
            logger.error(f"防撤回处理器发生内部错误: {e}", exc_info=True)
