import random
import time
from typing import Dict, List
import astrbot.api.message_components as Comp
from astrbot.api import logger
from .models import WifeRecord, UserWifeReport, UserMaxSenseReport, Wish
from .utils import WifeUtil, GroupNameUtil, Chance, RankUtil


class WifeHandler:
    
    API_IMAGE = "https://www.snh48.com/images/member/zp_{}.jpg"
    
    def __init__(self, config, db, cfg=None):
        self.config = config
        self.db = db
        self.cfg = cfg
        
        self.last_time: Dict[int, int] = {}
        self.group_update: List[int] = []
        self.last_wish_target: Dict[int, str] = {}
        self.star_in_birthday: List[int] = []
    
    def _get_msg(self, key: str, default: str = "", *args) -> str:
        if not self.cfg:
            return default
        msg = self.cfg.get(key, default)
        if args:
            try:
                return msg % args
            except (TypeError, ValueError):
                return msg
        return msg
    
    def download_star_data(self) -> str:
        return self.config.download_star_data()
    
    async def lai_ge_lao_po(self, user_id: int, group_id: int, event):
        try:
            internal_user_id = self.db.get_user_id_by_numbers(group_id, user_id)
            
            chance = Chance.get_user_chance(internal_user_id)
            first = False
            use_chance = False
            
            current_time = int(time.time())
            
            if internal_user_id in self.last_time:
                time_between = current_time - self.last_time[internal_user_id]
                two_hours = 2 * 3600
                
                if time_between < two_hours:
                    if chance > 0 and Chance.reduce(internal_user_id) != -1:
                        chance -= 1
                        use_chance = True
                    else:
                        wait_msg = WifeUtil.get_changing_time_bet(self.last_time[internal_user_id])
                        yield event.chain_result([
                            Comp.At(qq=user_id),
                            Comp.Plain(f"\n{wait_msg}")
                        ])
                        return
                else:
                    self.last_time[internal_user_id] = current_time
            else:
                if group_id not in self.group_update:
                    self.group_update.append(group_id)
                    self.db.add_coins(internal_user_id, 20, 1, "每日第一！")
                    first = True
                
                self.last_time[internal_user_id] = current_time - 2 * 3600
            
            star_data = self.config.get_star_data()
            if not star_data:
                yield event.chain_result([
                    Comp.At(qq=user_id),
                    Comp.Plain(f"\n{self._get_msg('starDataNotLoadedMsg', '星数据未加载')}")
                ])
                return
            
            wife_obj = random.choice(star_data)
            wife_id = int(wife_obj.get("sid", 0))
            wife_name = wife_obj.get("s", "未知")
            
            max_sense_record = self.db.get_max_sense_record(wife_id, group_id)
            hq = max_sense_record.get("sense", 0) if max_sense_record else 0
            
            max_sense_val = 101 if hq < 100 else hq + 11
            sense = random.randint(1, max_sense_val)
            
            bring_threshold = self.cfg.get("bring_threshold", 80) if self.cfg else 80
            if sense > bring_threshold:
                self.db.add_coins(internal_user_id, 1, 4, "带走老婆")
            
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
                    wish_msg = f"\n许愿成功：本次情愫 {sense - 10}% 增加为 {sense}%！coins+20"
                    Wish.remove(internal_user_id)
                else:
                    time_last = wish.reduce()
                    if time_last == 0:
                        self.last_wish_target[internal_user_id] = target
                    wish_msg = f"\n许愿 {target} 失败，您可以重新许愿。" if time_last == 0 \
                            else f"\n当前许愿 {target} 剩余 {time_last} 次。"
            
            self.db.append_lottery_record(
                group_id, 
                internal_user_id, 
                wife_id, 
                wife_name, 
                sense, 
                wish_success
            )
            
            group_name = wife_obj.get("g", "")
            team_name = wife_obj.get("t", "")
            display_group = GroupNameUtil.get_group_name(group_name)
            
            if display_group.upper() == team_name.upper():
                location = display_group
            else:
                location = f"{display_group} Team {team_name}" if team_name else display_group
            
            hq_user_id = None
            if sense > hq:
                hq = sense
                hq_user_id = user_id
            else:
                if max_sense_record:
                    hq_user_id = max_sense_record.get("user_id")
            
            birthday = wife_id in self.star_in_birthday
            if birthday:
                self.db.add_coins(internal_user_id, 20, 3, "在成员生日时抽中")
            
            msg_parts = [
                Comp.At(qq=user_id),
                Comp.Plain(
                    (f"{self._get_msg('firstCoinMsg', '本日第一！coins+20')}\n" if first else "") +
                    f" 今日老婆：{location} {wife_name} ({wife_obj.get('n', '')}) ({wife_obj.get('p', '')})" +
                    f" | 情愫：{sense}% {WifeUtil.recommend(sense)}"
                )
            ]

            image_url = self.API_IMAGE.format(wife_id)
            try:
                import requests
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Referer": "https://www.snh48.com/"
                }
                resp = requests.get(image_url, headers=headers, timeout=5)
                if resp.status_code == 200:
                    msg_parts.append(Comp.Image.fromBytes(resp.content))
                else:
                    logger.info(f"【图片下载提示】状态码异常: {resp.status_code}，本次不插入图片")
            except Exception as img_err:
                logger.info(f"【图片下载失败】: {img_err}，已自动跳过图片展示")


            pocket_id = wife_obj.get("i", "0")
            if pocket_id != "0":
                msg_parts.append(Comp.Plain(f"\n{self._get_msg('pocketIdMsg', '口袋ID: %s', pocket_id)}"))
            
            msg_parts.append(Comp.Plain(f"\n{WifeUtil.get_changing_time(self.last_time[internal_user_id])}"))
            
            if chance > 0 or use_chance:
                if use_chance:
                    msg_parts.append(Comp.Plain(f"\n{self._get_msg('useChanceMsg', '使用 1 次，剩余可用抽奖次数 %d 次', chance)}"))
                else:
                    msg_parts.append(Comp.Plain(f"\n{self._get_msg('chanceMsg', '可用抽奖次数 %d 次', chance)}"))
            
            hq_info = "待定"
            if hq_user_id:
                hq_info = f"用户 {hq_user_id}"
            msg_parts.append(Comp.Plain(f"\n{self._get_msg('senseQueenMsg', '当前情愫王：%s [%d%%]', hq_info, hq)}"))
            
            if wish_msg:
                msg_parts.append(Comp.Plain(wish_msg))
            
            if birthday:
                msg_parts.append(Comp.Plain(f"\n{self._get_msg('birthdayMsg', '生日当天抽中成员，coins+20')}"))
            
            yield event.chain_result(msg_parts)
        
        except Exception as e:
            yield event.chain_result([
                Comp.At(qq=user_id),
                Comp.Plain(f"\n{self._get_msg('lotteryErrorMsg', '抽奖出错，请稍后再试')}")
            ])
    
    def wo_de_lao_po(self, user_id: int, group_id: int) -> str:
        try:
            internal_user_id = self.db.get_user_id_by_numbers(group_id, user_id)
            
            output = f"\nuid: {internal_user_id:05d}"
            
            all_records = self.db.get_all_records_by_user_id(internal_user_id)
            
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
            
            report = UserWifeReport(records)
            
            bring_threshold = self.cfg.get("bring_threshold", 80) if self.cfg else 80
            
            if report.get_total_bring() == 0:
                output += f"\n共抽 {report.get_total()} 次"
                output += f"\n{self._get_msg('dataVoidOut', '你还没有老婆~ 情愫达到 %d%% 才可以带走捏', bring_threshold)}"
            else:
                wives_by_count = report.get_wives()
                wives_by_sense = report.get_wives_sort_by_sense()
                
                first_sense = wives_by_sense[0] if wives_by_sense else None
                first_count = wives_by_count[0] if wives_by_count else None
                
                sense_str = f"{first_sense.name}({first_sense.sense}%)" if first_sense else "N/A"
                count_str = f"{first_count.name}({first_count.sense}%)" if first_count else "N/A"
                
                output += f"\n{self._get_msg('dataOut', '共抽 %d 次，累计带走 %d 人\n最高情愫：%s %d 次\n最多次数：%s %d 次', report.get_total(), report.get_total_bring(), sense_str, first_sense.count if first_sense else 0, count_str, first_count.count if first_count else 0)}"
            
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
                output += f"{self._get_msg('noSenseKingMsg', '您不是任何小偶像的情愫王')}"
            else:
                wives_list = max_sense_report.get_wives()[:3]
                wives_display = " | ".join([f"{w.name}({w.sense}%)" for w in wives_list])
                output += f"{self._get_msg('senseKingMsg', '您是 %d 位小偶像的情愫王：\n%s', max_sense_report.get_total(), wives_display)}"
            
            return output
        
        except Exception as e:
            return f"\n{self._get_msg('errorMsg', '系统错误，请稍后再试')}"
    
    def wish(self, user_id: int, group_id: int, target: str) -> str:
        try:
            internal_user_id = self.db.get_user_id_by_numbers(group_id, user_id)
            
            star_data = self.config.get_star_data()
            for star in star_data:
                if star.get("s") == target:
                    if Wish.contains(internal_user_id):
                        existing_wish = Wish.get(internal_user_id)
                        return f"\n您有许愿正在进行，{existing_wish.get_time_last()}次抽奖未抽中或任何一次抽中后接受新的许愿"
                    
                    Wish(internal_user_id, target)
                    self.last_wish_target.pop(internal_user_id, None)
                    return f"\n{self._get_msg('wishSuccess', '许愿成功：%s', target)}"
            
            return f"\n{self._get_msg('notFound', '许愿对象不存在')}"
        
        except Exception as e:
            return f"\n{self._get_msg('errorMsg', '系统错误，请稍后再试')}"
    
    def rank(self, user_id: int, group_id: int) -> str:
        try:
            internal_user_id = self.db.get_user_id_by_numbers(group_id, user_id)
            records = self.db.analyse_group_records(group_id)
            
            if not records:
                return f"\n{self._get_msg('rankEmptyMsg', '本群还没有成功带走老婆的用户')}"
            
            max_count = records[0].get("count", 0) if records else 0
            
            result_list = []
            for record in records[:5]:
                uid = record.get("user_id")
                count = record.get("count", 0)
                rank_line = RankUtil.get_rank_line(uid, count, max_count)
                result_list.append(rank_line)
            
            output = f"\n{self._get_msg('rankMsg', '本群带走老婆次数排名')}\n" + "\n".join(result_list)
            
            for i, record in enumerate(records):
                if record.get("user_id") == internal_user_id:
                    output += "\n---------------------------\n"
                    
                    if i == 0:
                        output += "您的排名：1"
                    else:
                        prev_count = records[i - 1].get("count", 0)
                        curr_count = record.get("count", 0)
                        diff = prev_count - curr_count
                        
                        if diff > 0:
                            output += f"\n{self._get_msg('rankingMsg', '您的排名：%d，距离上一名差(%d)', i + 1, diff)}"
                        else:
                            output += f"\n您的排名：{i + 1}"
                    
                    my_rank_line = RankUtil.get_rank_line(internal_user_id, record.get("count", 0), max_count)
                    output += f"\n{my_rank_line}"
                    break
            else:
                output += "\n---------------------------\n"
                output += f"{self._get_msg('noRankMsg', '您还没有带走过老婆')}"
            
            return output
        
        except Exception as e:
            return f"\n{self._get_msg('errorMsg', '系统错误，请稍后再试')}"
    
    def reset_daily(self):
        self.group_update.clear()
        Chance.reset_all()
    
    def reset_user(self, user_id: int):
        if user_id in self.last_time:
            del self.last_time[user_id]
    
    def reset_birthday_list(self):
        self.star_in_birthday.clear()
    
    def is_in_birthday(self, star: Dict, today: str) -> bool:
        if star.get("birthday") == today:
            self.star_in_birthday.append(int(star.get("sid", 0)))
            return True
        return False
