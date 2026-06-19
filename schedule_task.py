import asyncio
from datetime import datetime, time
from typing import Callable, Optional
import threading


class ScheduleTask:
    """定时任务管理"""
    
    def __init__(self):
        self.tasks: dict = {}
        self.running = False
        self.thread: Optional[threading.Thread] = None
    
    def add_daily_task(self, task_name: str, task_func: Callable, run_time: time):
        """添加每日定时任务
        
        Args:
            task_name: 任务名称
            task_func: 异步执行函数
            run_time: 执行时间 (HH:MM)
        """
        self.tasks[task_name] = {
            'type': 'daily',
            'func': task_func,
            'time': run_time,
            'last_run': None
        }
    
    def add_interval_task(self, task_name: str, task_func: Callable, interval_seconds: int):
        """添加固定间隔任务
        
        Args:
            task_name: 任务名称
            task_func: 异步执行函数
            interval_seconds: 间隔秒数
        """
        self.tasks[task_name] = {
            'type': 'interval',
            'func': task_func,
            'interval': interval_seconds,
            'last_run': None
        }
    
    async def _check_and_run_tasks(self):
        """检查并执行任务"""
        now = datetime.now()
        
        for task_name, task_info in self.tasks.items():
            try:
                if task_info['type'] == 'daily':
                    # 每日任务
                    run_time = task_info['time']
                    current_time = now.time()
                    
                    # 检查是否到达执行时间
                    if (current_time >= run_time and 
                        (task_info['last_run'] is None or 
                         task_info['last_run'].date() != now.date())):
                        
                        await task_info['func']()
                        task_info['last_run'] = now
                        print(f"Executed daily task: {task_name}")
                
                elif task_info['type'] == 'interval':
                    # 固定间隔任务
                    interval = task_info['interval']
                    last_run = task_info['last_run']
                    
                    if last_run is None:
                        # 首次运行
                        await task_info['func']()
                        task_info['last_run'] = now
                        print(f"Executed interval task: {task_name} (first run)")
                    else:
                        elapsed = (now - last_run).total_seconds()
                        if elapsed >= interval:
                            await task_info['func']()
                            task_info['last_run'] = now
                            print(f"Executed interval task: {task_name}")
            
            except Exception as e:
                print(f"Error executing task {task_name}: {e}")
    
    async def start(self):
        """启动任务调度器"""
        self.running = True
        print("Task scheduler started")
        
        while self.running:
            try:
                await self._check_and_run_tasks()
                # 每秒检查一次任务
                await asyncio.sleep(1)
            except Exception as e:
                print(f"Error in task scheduler: {e}")
                await asyncio.sleep(1)
    
    def stop(self):
        """停止任务调度器"""
        self.running = False
        print("Task scheduler stopped")


class WifeLotterySchedule:
    """老婆抽奖的定时任务管理"""
    
    def __init__(self, handler):
        self.handler = handler
        self.scheduler = ScheduleTask()
        self._setup_tasks()
    
    def _setup_tasks(self):
        """设置所有定时任务"""
        
        # 每天凌晨0点重置每日第一标记和特殊次数
        self.scheduler.add_daily_task(
            'reset_daily',
            self._reset_daily,
            time(0, 0)
        )
        
        # 每两小时刷新一次特殊抽奖次数（无需显式处理，由客户端管理）
        # 但可以添加日志记录
        self.scheduler.add_interval_task(
            'check_lottery',
            self._check_lottery,
            7200  # 2小时
        )
    
    async def _reset_daily(self):
        """重置每日数据"""
        try:
            self.handler.reset_daily()
            print("Daily reset completed: cleared group updates and chances")
        except Exception as e:
            print(f"Error in daily reset: {e}")
    
    async def _check_lottery(self):
        """定期检查抽奖状态"""
        try:
            # 这里可以添加定期的日志、数据清理等操作
            print("Lottery status check completed")
        except Exception as e:
            print(f"Error in lottery check: {e}")
    
    async def start(self):
        """启动定时任务"""
        await self.scheduler.start()
    
    def stop(self):
        """停止定时任务"""
        self.scheduler.stop()


# 使用示例
"""
from wife_handler import WifeHandler
from schedule_task import WifeLotterySchedule

# 创建处理器
handler = WifeHandler(config, db)

# 创建并启动定时任务
schedule = WifeLotterySchedule(handler)

# 在异步事件循环中启动
asyncio.create_task(schedule.start())
"""
