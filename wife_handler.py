import random
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import astrbot.api.message_components as Comp

from .config import Config
from .database import Database
from .models import WifeRecord, UserWifeReport, UserMaxSenseReport, Wish
from .utils import WifeUtil, GroupNameUtil, Chance, RankUtil


class WifeHandler:
    """老婆抽奖处理器"""
    
    API_IMAGE = "https://www.snh48.com/images/member/zp_{}.jpg"
    
    def __init__(self, config: Config, db: Database):
        self.config = config
        self.db = db
        
        # 临时存储# 临时存储 - 统一采用 str 作为主键
        self.last_time: Dict[str, int] = {} 
        self.group_update: List[str] = []
        self.last_wish_target: Dict[str, str] = {}
        self.star_in_birthday: List[str] = []
    
    def download_star_data(self) -> str:
        """下载星数据"""
        return self.config.download_star_data()
    
    async def lai_ge_lao_po(self, user_id: str, group_id: str, event):
        """来个老婆 - 主要抽奖逻辑"""
        try:
            internal_user_id = self.db.get_user_id_by_numbers(group_id, user_id)
            
            # 判断资格和抽奖次数
            chance = Chance.get_user_chance(internal_user_id)
            first = False
            use_chance = False
            
            current_time = int(time.time())
            
            if internal_user_id in self.last_time:
                time_between = current_time - self.last_time[internal_user_id]
                two_hours = 2 * 3600  # 2小时的秒数
                
                if time_between < two_hours:
                    # 尝试使用特殊次数
                    if chance > 0 and Chance.reduce(internal_user_id) != -1:
                        chance -= 1
                        use_chance = True
                    else:
                        # 没有次数可用，返回等待时间
                        wait_msg = WifeUtil.get_changing_time_bet(self.last_time[internal_user_id])
                        yield event.chain_result([
                            Comp.At(qq=user_id),
                            Comp.Plain(f"\n{wait_msg}")
                        ])
                        return
                else:
                    # 已经过了2小时，可以继续
                    self.last_time[internal_user_id] = current_time
            else:
                # 首次抽奖
                if group_id not in self.group_update:
                    self.group_update.append(group_id)
                    self.db.add_coins(internal_user_id, 20, 1, "每日第一！")
                    first = True
                
                # 设置为距离现在2小时前
                self.last_time[internal_user_id] = current_time - 2 * 3600
            
            # 随机抽取老婆
            star_data = self.config.get_star_data()
            if not star_data:
                yield event.chain_result([
                    Comp.At(qq=user_id),
                    Comp.Plain("\n星数据未加载")
                ])
                return
            
            wife_obj = random.choice(star_data)
            wife_id = int(wife_obj.get("sid", 0))
            wife_name = wife_obj.get("s", "未知")
            
            # 获取该老婆的最高情愫记录
            max_sense_record = self.db.get_max_sense_record(wife_id, group_id)
            hq = max_sense_record.get("sense", 0) if max_sense_record else 0
            
            # 抽取情愫值
            max_sense_val = 101 if hq < 100 else hq + 11
            sense = random.randint(1, max_sense_val)
            
            # 如果情愫值 > 79，加币
            if sense > 79:
                self.db.add_coins(internal_user_id, 1, 4, "带走老婆")
            
            # 处理许愿
            wish_msg = ""
            wish_success = False
            
            if Wish.contains(internal_user_id):
                wish = Wish.get(internal_user_id)
                target = wish.get_target()
                wish_success = wish.match(wife_name)
                
                if wish_success:
                    self.db.add_coins(internal_user_id, 20, 2, "许愿成功")
                    self.last_wish_target[internal_user_id] = target
                    sense = min(sense + 10, 100)
                    wish_msg = f"\n许愿成功：本次情愫 {sense - 10}% 增加为 {sense}%！coins+20. 扣1继续相同的许愿。"
                    
                    # 💡 内存移除的同时，同步从数据库中删除已完成的许愿记录
                    Wish.remove(internal_user_id)
                    self.db.remove_wish(group_id=group_id, qq=user_id)
                else:
                    time_last = wish.reduce()
                    if time_last == 0:
                        self.last_wish_target[internal_user_id] = target
                        
                        # 💡 次数用尽：同步从数据库中删除这条许愿记录
                        self.db.remove_wish(group_id=group_id, qq=user_id)
                    else:
                        # 💡 次数减少：同步更新数据库中的剩余次数
                        self.db.add_or_update_wish(group_id=group_id, qq=user_id, target=target, remaining_tries=time_last)
                        
                    wish_msg = f"\n许愿 {target} 失败，您可以重新许愿。扣1继续相同的许愿。" if time_last == 0 \
                            else f"\n当前许愿 {target} 剩余 {time_last} 次。"
            
            # 保存抽奖记录
            self.db.append_lottery_record(
                internal_user_id=internal_user_id,
                group_id=group_id,
                wife_id=str(wife_id),
                wife_name=wife_name,
                sense=sense,
                is_wish=wish_success
            )
            
            # 获取团名和队名
            group_name = wife_obj.get("g", "")
            team_name = wife_obj.get("t", "")
            display_group = GroupNameUtil.get_group_name(group_name)
            
            if display_group.upper() == team_name.upper():
                location = display_group
            else:
                location = f"{display_group} Team {team_name}" if team_name else display_group
            
            # 获取情愫王信息
            hq_user_id = None
            if sense > hq:
                hq = sense
                hq_user_id = user_id
            else:
                if max_sense_record:
                    hq_user_id = max_sense_record.get("user_id")
            
            # 检查生日
            birthday = wife_id in self.star_in_birthday
            if birthday:
                self.db.add_coins(internal_user_id, 20, 3, "在成员生日时抽中")
                
            # 1. 拼接精美的图片路径
            image_url = self.API_IMAGE.format(wife_id)
            
            # 2. 初始化消息链（先把 At 和基础文字放进去）
            msg_parts = [
                Comp.At(qq=user_id),
                Comp.Plain(
                    (f"本日第一！coins+20\n" if first else "") +
                    f" 今日老婆：{location} {wife_name} ({wife_obj.get('n', '')}) ({wife_obj.get('p', '')})" +
                    f" | 情愫：{sense}% {WifeUtil.recommend(sense)}"
                )
            ]
            
            # 3. 预先在后台拉取图片流（防盗链 & 如果失败则不插入）
            try:
                import requests
                # 模拟正常浏览器请求，绕过官网潜在的防盗链
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Referer": "https://www.snh48.com/"
                }
                resp = requests.get(image_url, headers=headers, timeout=5)
                if resp.status_code == 200:
                    # 💡 成功下载：使用 fromBytes 传递字节流，QQ 客户端不需再去公网下载，100% 发送成功
                    msg_parts.append(Comp.Image.fromBytes(resp.content))
                else:
                    print(f"【图片下载提示】状态码异常: {resp.status_code}，本次不插入图片")
            except Exception as img_err:
                # 💡 下载失败：静默捕获异常，打印日志，不向 msg_parts 插入图片
                print(f"【图片下载失败】: {img_err}，已自动跳过图片展示")
            
            '''
            # 添加口袋ID（如果有）
            pocket_id = wife_obj.get("i", "0")
            if pocket_id != "0":
                msg_parts.append(Comp.Plain(f"\n口袋ID: {pocket_id}"))
            '''
            
            # 添加下次更换时间
            msg_parts.append(Comp.Plain(f"\n{WifeUtil.get_changing_time(self.last_time[internal_user_id])}"))
            
            # 添加可用次数
            if chance > 0 or use_chance:
                if use_chance:
                    msg_parts.append(Comp.Plain(f"\n使用 1 次，剩余可用抽奖次数 {chance} 次"))
                else:
                    msg_parts.append(Comp.Plain(f"\n可用抽奖次数 {chance} 次"))
            
            # 添加情愫王信息
            hq_info = ""
            if hq_user_id:
                try:
                    # 关键修改：必须使用关键字参数传参 group_id 和 user_id
                    member_info = await event.bot.get_group_member_info(
                        group_id=int(group_id), 
                        user_id=int(hq_user_id)
                    )
                    # 优先群名片(card)，其次QQ昵称(nickname)
                    hq_info = member_info.get("card") or member_info.get("nickname") or f"({hq_user_id})"
                except Exception:
                    hq_info = f"({hq_user_id})"
            msg_parts.append(Comp.Plain(f"\n当前情愫王：{hq_info} [{hq}%]"))
            
            # 添加许愿信息
            if wish_msg:
                msg_parts.append(Comp.Plain(wish_msg))
            
            # 添加生日提示
            if birthday:
                msg_parts.append(Comp.Plain("\n生日当天抽中成员，coins+20"))
            
            yield event.chain_result(msg_parts)
        
        except Exception as e:
            yield event.chain_result([
                Comp.At(qq=user_id),
                Comp.Plain(f"\n抽奖出错: {str(e)}")
            ])
    
    def wo_de_lao_po(self, user_id: str, group_id: str) -> str:
        """我的老婆 - 查询用户统计"""
        try:
            internal_user_id = self.db.get_user_id_by_numbers(group_id, user_id)
            
            output = f"\nuid: {internal_user_id:05d}"
            
            # 获取用户的所有记录
            all_records = self.db.get_user_records(internal_user_id)
            
            # 转换为WifeRecord对象
            records = [
                WifeRecord(
                    user_id=r.get("user_id"),
                    group_id=r.get("group_id"),
                    wife_id=r.get("wife_id"),
                    wife_name=r.get("wife_name"),
                    sense=r.get("sense"),
                    is_wish=r.get("is_wish", False),
                    timestamp=r.get("timestamp", 0)
                )
                for r in all_records
            ]
            
            bring_threshold = self.config.get_bring_threshold()
            report = UserWifeReport(records, bring_threshold=bring_threshold)
            
            if report.get_total_bring() == 0:
                output += f"\n共抽 {report.get_total()} 次\n你还没有老婆~ 情愫达到{bring_threshold}%才可以带走捏"
            else:
                wives_by_count = report.get_wives()
                wives_by_sense = report.get_wives_sort_by_sense()
                
                output += f"\n共抽 {report.get_total()} 次，累计带走 {report.get_total_bring()} 人"
                
                if wives_by_sense:
                    first_sense = wives_by_sense[0]
                    output += f"\n最高情愫：{first_sense.name}({first_sense.sense}%) {first_sense.count} 次"
                
                if wives_by_count:
                    first_count = wives_by_count[0]
                    output += f"\n最多次数：{first_count.name}({first_count.sense}%) {first_count.count} 次"
            
            # 获取用户的情愫王信息
            output += "\n---------------------------\n"
            max_sense_records = self.db.get_all_records_that_max_sense(internal_user_id, group_id)
            
            sense_records = [
                WifeRecord(
                    user_id=r.get("user_id"),
                    group_id=r.get("group_id"),
                    wife_id=r.get("wife_id"),
                    wife_name=r.get("wife_name"),
                    sense=r.get("sense"),
                    is_wish=r.get("is_wish", False),
                    timestamp=r.get("timestamp", 0)
                )
                for r in max_sense_records
            ]
            
            max_sense_report = UserMaxSenseReport(sense_records)
            
            if max_sense_report.get_total() == 0:
                output += "您不是任何小偶像的情愫王"
            else:
                output += f"您是 {max_sense_report.get_total()} 位小偶像的情愫王：\n"
                wives_list = max_sense_report.get_wives()[:3]
                wives_display = [f"{w.name}({w.sense}%)" for w in wives_list]
                output += " | ".join(wives_display)
            
            return output
        
        except Exception as e:
            return f"\n查询出错: {str(e)}"
    
    def wish(self, user_id: str, group_id: str, target: str) -> str:
        """许愿逻辑"""
        try:
            internal_user_id = self.db.get_user_id_by_numbers(group_id, user_id)
            
            # 检查许愿对象是否存在
            star_data = self.config.get_star_data()
            for star in star_data:
                if star.get("s") == target:
                    # 检查是否已有未完成的许愿
                    if Wish.contains(internal_user_id):
                        existing_wish = Wish.get(internal_user_id)
                        return f"\n您有许愿正在进行，{existing_wish.get_time_last()}次抽奖未抽中或任何一次抽中后接受新的随愿"
                    
                    # 1. 创建内存新许愿
                    Wish(internal_user_id, target)
                    self.last_wish_target.pop(internal_user_id, None)
                    
                    # 2. 💡 同步写入数据库保存（剩余次数默认为 10）
                    self.db.add_or_update_wish(group_id=group_id, qq=user_id, target=target, remaining_tries=10)
                    
                    return f"\n许愿成功：{target}"
            
            return f"\n许愿对象不存在"
        
        except Exception as e:
            return f"\n许愿功能出错: {str(e)}"
    
    def rank(self, user_id: str, group_id: str) -> str:
        """排名查询"""
        bring_threshold = self.config.get_bring_threshold()
        try:
            internal_user_id = self.db.get_user_id_by_numbers(group_id, user_id)
            records = self.db.get_group_rank(group_id, bring_threshold)
            
            if not records:
                return f"\n本群还没有成功带走老婆的用户"
            
            max_count = records[0].get("count", 0) if records else 0
            
            # 生成排名列表（前5名）
            result_list = []
            for record in records[:5]:
                uid = record.get("user_id")
                count = record.get("count", 0)
                rank_line = RankUtil.get_rank_line(uid, count, max_count)
                result_list.append(rank_line)
            
            output = "本群带走老婆次数排名/uid: \n" + "\n".join(result_list)
            
            # 查找当前用户的排名
            user_found = False
            for i, record in enumerate(records):
                if record.get("user_id") == internal_user_id:
                    user_found = True
                    output += "\n---------------------------\n"
                    
                    if i == 0:
                        output += "您的排名：1"
                    else:
                        # 计算距离上一名的差距
                        prev_count = records[i - 1].get("count", 0)
                        curr_count = record.get("count", 0)
                        diff = prev_count - curr_count
                        
                        if diff > 0:
                            output += f"您的排名：{i + 1}，距离上一名差({diff})"
                        else:
                            output += f"您的排名：{i + 1}"
                    
                    my_rank_line = RankUtil.get_rank_line(internal_user_id, record.get("count", 0), max_count)
                    output += f"\n{my_rank_line}"
                    break
            
            if not user_found:
                output += "\n---------------------------\n您还没有带走过老婆"
            
            return output
        
        except Exception as e:
            return f"\n排名查询出错: {str(e)}"
    
    def reset_daily(self):
        """每日重置"""
        self.group_update.clear()
        Chance.reset_all()
    
    def reset_user(self, user_id: str):
        """重置单个用户的每日限制"""
        if user_id in self.last_time:
            del self.last_time[user_id]
    
    def reset_birthday_list(self):
        """重置生日列表"""
        self.star_in_birthday.clear()
    
    def is_in_birthday(self, star: Dict, today: str) -> bool:
        """检查星是否是生日"""
        if star.get("birthday") == today:
            self.star_in_birthday.append(int(star.get("sid", 0)))
            return True
        return False
