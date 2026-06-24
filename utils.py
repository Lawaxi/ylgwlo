from datetime import datetime, timedelta
from typing import Dict

class WifeUtil:
    """老婆相关工具类"""
    
    @staticmethod
    def recommend(sense: int) -> str:
        """根据情愫值给出推荐"""
        if sense > 99:
            return "原地结婚"
        elif sense > 89:
            return "最佳拍档"
        elif sense > 79:
            return "带回家吧"
        elif sense > 69:
            return "约会去吧"
        elif sense > 19:
            return "再努努力"
        else:
            return "下辈子吧"
    
    @staticmethod
    def get_changing_time(last_timestamp: int) -> str:
        """获取下次可抽奖的时间"""
        last_time = datetime.fromtimestamp(last_timestamp)
        next_time = last_time + timedelta(hours=2)
        now = datetime.now()
        
        if now >= next_time:
            return "现在可以更换老婆了"
        
        delta = next_time - now
        hours = delta.seconds // 3600
        minutes = (delta.seconds % 3600) // 60
        
        if hours > 0:
            return f"距离下次更换还需 {hours}小时{minutes}分钟"
        else:
            return f"距离下次更换还需 {minutes}分钟"
    
    @staticmethod
    def get_changing_time_bet(last_timestamp: int) -> str:
        """获取距离上次抽奖的时间（用于判断是否可以使用特殊次数）"""
        last_time = datetime.fromtimestamp(last_timestamp)
        now = datetime.now()
        delta = now - last_time
        hours = delta.total_seconds() / 3600
        
        if hours >= 2:
            return "现在可以更换老婆了"
        
        remaining_hours = 2 - hours
        remaining_minutes = remaining_hours * 60
        
        if remaining_hours >= 1:
            minutes = int(remaining_minutes % 60)
            h = int(remaining_hours)
            return f"距离下次更换还需 {h}小时{minutes}分钟"
        else:
            return f"距离下次更换还需 {int(remaining_minutes)}分钟"

class GroupNameUtil:
    """团名称转换工具"""
    
    GROUP_MAP = {
        "SNH": "SNH48",
        "GNZ": "GNZ48",
        "BEJ": "BEJ48",
        "CKG": "CKG48",
        "CGT": "CGT48",
        "IDFT": "IDFT48",
    }
    
    @staticmethod
    def get_group_name(prefix: str) -> str:
        """获取完整团名"""
        return GroupNameUtil.GROUP_MAP.get(prefix, prefix)

class Chance:
    """特殊抽奖次数管理"""
    _chances: Dict[int, int] = {}
    
    @staticmethod
    def get_user_chance(user_id: int) -> int:
        """获取用户的特殊抽奖次数"""
        return Chance._chances.get(user_id, 0)
    
    @staticmethod
    def reduce(user_id: int) -> int:
        """扣除一次特殊抽奖次数"""
        if user_id in Chance._chances and Chance._chances[user_id] > 0:
            Chance._chances[user_id] -= 1
            return Chance._chances[user_id]
        return -1
    
    @staticmethod
    def add(user_id: int, amount: int) -> int:
        """增加特殊抽奖次数"""
        if user_id not in Chance._chances:
            Chance._chances[user_id] = 0
        Chance._chances[user_id] += amount
        return Chance._chances[user_id]
    
    @staticmethod
    def set(user_id: int, amount: int):
        """设置特殊抽奖次数"""
        Chance._chances[user_id] = amount
    
    @staticmethod
    def reset_all():
        """重置所有用户的特殊抽奖次数"""
        Chance._chances.clear()
    
    @staticmethod
    def reset(user_id: int):
        """重置单个用户的特殊抽奖次数"""
        if user_id in Chance._chances:
            del Chance._chances[user_id]

class RankUtil:
    """排名相关工具"""
    
    @staticmethod
    def get_rank_line(user_id: int, count: int, max_count: int) -> str:
        """生成排名行显示"""
        bars = min(round(count * 10.0 / max_count), count)
        
        if bars == 0 and count > 0:
            bars_str = "▍"
        else:
            bars_str = "▉" * bars
        
        return f"{user_id}: {bars_str}({count})"
