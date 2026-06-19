from dataclasses import dataclass
from typing import List, Dict, Any
from datetime import datetime


@dataclass
class WifeRecord:
    """单个老婆记录"""
    user_id: int
    group_id: int
    wife_id: int
    wife_name: str
    sense: int  # 情愫值
    is_wish: bool  # 是否是许愿得到
    timestamp: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'user_id': self.user_id,
            'group_id': self.group_id,
            'wife_id': self.wife_id,
            'wife_name': self.wife_name,
            'sense': self.sense,
            'is_wish': self.is_wish,
            'timestamp': self.timestamp
        }


@dataclass
class Wife:
    """老婆信息"""
    name: str
    sense: int  # 最高情愫值
    count: int  # 被抽中次数
    
    def __lt__(self, other):
        """用于排序，先按次数，再按情愫值"""
        if self.count != other.count:
            return self.count > other.count
        return self.sense > other.sense


class UserWifeReport:
    """用户的老婆统计报告"""
    
    def __init__(self, records: List[WifeRecord], bring_threshold: int = 80):
        self.records = records
        self.total = len(records)
        self.bring_threshold = bring_threshold  # 💡 保存配置的阈值
        self.wives: List[Wife] = self._analyze_wives()
        self.wives_sort_by_sense: List[Wife] = self._analyze_wives_by_sense()
        self.total_bring = sum(1 for r in records if r.sense >= self.bring_threshold)
    
    def _analyze_wives(self) -> List[Wife]:
        """分析老婆信息（按次数排序）"""
        wife_dict: Dict[str, Dict[str, Any]] = {}
        
        for record in self.records:
            wife_name = record.wife_name
            if wife_name not in wife_dict:
                wife_dict[wife_name] = {'count': 0, 'sense': 0}
            wife_dict[wife_name]['count'] += 1
            wife_dict[wife_name]['sense'] = max(wife_dict[wife_name]['sense'], record.sense)
        
        wives = [Wife(name=k, sense=v['sense'], count=v['count']) 
                for k, v in wife_dict.items()]
        wives.sort(key=lambda x: (x.count, x.sense), reverse=True)
        return wives
    
    def _analyze_wives_by_sense(self) -> List[Wife]:
        """分析老婆信息（按情愫值排序）"""
        wife_dict: Dict[str, Dict[str, Any]] = {}
        
        for record in self.records:
            wife_name = record.wife_name
            if wife_name not in wife_dict:
                wife_dict[wife_name] = {'count': 0, 'sense': 0}
            wife_dict[wife_name]['count'] += 1
            wife_dict[wife_name]['sense'] = max(wife_dict[wife_name]['sense'], record.sense)
        
        wives = [Wife(name=k, sense=v['sense'], count=v['count']) 
                for k, v in wife_dict.items()]
        wives.sort(key=lambda x: (x.sense, x.count), reverse=True)
        return wives
    
    def get_total(self) -> int:
        return self.total
    
    def get_total_bring(self) -> int:
        return self.total_bring
    
    def get_wives(self) -> List[Wife]:
        return self.wives
    
    def get_wives_sort_by_sense(self) -> List[Wife]:
        return self.wives_sort_by_sense


class UserMaxSenseReport:
    """用户的情愫王统计报告"""
    
    def __init__(self, records: List[WifeRecord]):
        self.records = records
        self.wives: List[Wife] = self._analyze_wives()
        self.total = len(self.wives)
    
    def _analyze_wives(self) -> List[Wife]:
        """分析情愫王老婆"""
        wife_dict: Dict[str, Dict[str, Any]] = {}
        
        for record in self.records:
            wife_name = record.wife_name
            if wife_name not in wife_dict:
                wife_dict[wife_name] = {'sense': 0}
            wife_dict[wife_name]['sense'] = max(wife_dict[wife_name]['sense'], record.sense)
        
        wives = [Wife(name=k, sense=v['sense'], count=1) 
                for k, v in wife_dict.items()]
        wives.sort(key=lambda x: x.sense, reverse=True)
        return wives
    
    def get_total(self) -> int:
        return self.total
    
    def get_wives(self) -> List[Wife]:
        return self.wives


class Wish:
    """许愿管理"""
    _wishes: Dict[int, 'Wish'] = {}
    
    def __init__(self, user_id: int, target: str, max_tries: int = 10):
        self.user_id = user_id
        self.target = target
        self.max_tries = max_tries
        self.remaining_tries = max_tries
        Wish._wishes[user_id] = self
    
    @staticmethod
    def contains(user_id: int) -> bool:
        return user_id in Wish._wishes
    
    @staticmethod
    def get(user_id: int) -> 'Wish':
        return Wish._wishes.get(user_id)
    
    @staticmethod
    def remove(user_id: int):
        if user_id in Wish._wishes:
            del Wish._wishes[user_id]
    
    def get_target(self) -> str:
        return self.target
    
    def get_time_last(self) -> int:
        return self.remaining_tries
    
    def match(self, wife_name: str) -> bool:
        """检查是否许愿成功"""
        return wife_name == self.target
    
    def reduce(self) -> int:
        """减少一次尝试，返回剩余次数"""
        self.remaining_tries -= 1
        if self.remaining_tries <= 0:
            Wish.remove(self.user_id)
        return self.remaining_tries
