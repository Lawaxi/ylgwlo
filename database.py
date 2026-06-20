import pymysql
from dbutils.pooled_db import PooledDB
from typing import List, Dict, Any, Optional

DEFAULT_DATABASE_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'ylgwlo',
    'password': '48Z6arYWSyxRzYPp',
    'database': 'ylgwlo'
}

class Database:
    """数据库操作类"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        if config is None:
            config = DEFAULT_DATABASE_CONFIG.copy()
        
        self.config = config
        self.pool = self._create_pool()
        self._init_tables()
    
    def _create_pool(self) -> Optional[PooledDB]:
        """创建数据库连接池"""
        try:
            pool = PooledDB(
                creator=pymysql,
                maxconnections=5,
                mincached=2,
                maxcached=3,
                maxshared=0,
                blocking=True,
                maxusage=None,
                setsession=[],
                ping=0,
                host=self.config['host'],
                port=self.config['port'],
                user=self.config['user'],
                password=self.config['password'],
                database=self.config['database'],
                autocommit=True,
                charset='utf8mb4'
            )
            return pool
        except Exception as e:
            print(f"Error creating connection pool: {e}")
            return None

    def _execute_query(self, query: str, args: tuple = ()) -> List[Dict[str, Any]]:
        """执行查询语句"""
        if not self.pool:
            raise RuntimeError("【错误】数据库连接池未初始化，请检查数据库服务是否开启或配置是否正确！")
        conn = self.pool.connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        try:
            cursor.execute(query, args)
            result = cursor.fetchall()
            return result
        except Exception as e:
            raise RuntimeError(f"【MySQL 查询异常】语句: {query} 错误信息: {e}")
        finally:
            cursor.close()
            conn.close()

    def _execute_update(self, query: str, args: tuple = ()) -> int:
        if not self.pool:
            raise RuntimeError("【错误】数据库连接池未初始化，请检查数据库服务是否开启或配置是否正确！")
        conn = self.pool.connection()
        cursor = conn.cursor()
        try:
            affected_rows = cursor.execute(query, args)
            conn.commit()  # 显式提交事务
            return affected_rows
        except Exception as e:
            try:
                conn.rollback()
            except:
                pass
            raise RuntimeError(f"【MySQL 更新异常】语句: {query} 错误信息: {e}")
        finally:
            cursor.close()
            conn.close()

    def _init_tables(self):
        """初始化表结构 - 增加自动创建数据库逻辑"""
        try:
            temp_conn = pymysql.connect(
                host=self.config['host'],
                port=int(self.config['port']),
                user=self.config['user'],
                password=self.config['password'],
                charset='utf8mb4'
            )
            with temp_conn.cursor() as t_cursor:
                t_cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{self.config['database']}` CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;")
            temp_conn.close()
        except Exception as db_e:
            print(f"【警告】尝试创建或检查数据库失败，可能权限不足: {db_e}")

        user_table = """
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            group_id VARCHAR(64) NOT NULL,
            qq VARCHAR(64) NOT NULL,
            coins INT DEFAULT 0,
            UNIQUE KEY group_qq (group_id, qq)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
        
        record_table = """
        CREATE TABLE IF NOT EXISTS lottery_records (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            group_id VARCHAR(64) NOT NULL,
            wife_id VARCHAR(64) NOT NULL,
            wife_name VARCHAR(128) NOT NULL,
            sense INT DEFAULT 0,
            is_wish TINYINT DEFAULT 0,
            timestamp BIGINT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
        
        wish_table = """
        CREATE TABLE IF NOT EXISTS wishes (
            id INT AUTO_INCREMENT PRIMARY KEY,
            group_id VARCHAR(64) NOT NULL,
            qq VARCHAR(64) NOT NULL,
            target VARCHAR(128) NOT NULL,
            remaining_tries INT DEFAULT 10,
            UNIQUE KEY group_qq_wish (group_id, qq)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """

        self._execute_update(user_table)
        self._execute_update(record_table)
        self._execute_update(wish_table)
        print("【成功】所有数据库表结构检查/初始化顺利完成！")

    def get_user_id_by_numbers(self, group_id: str, qq: str) -> int:
        group_id_str = str(group_id)
        qq_str = str(qq)
        
        sql = "SELECT id FROM users WHERE group_id = %s AND qq = %s"
        res = self._execute_query(sql, (group_id_str, qq_str))
        if res:
            return int(res[0]['id'])
        
        insert_sql = "INSERT INTO users (group_id, qq, coins) VALUES (%s, %s, 0)"
        self._execute_update(insert_sql, (group_id_str, qq_str))
        
        res = self._execute_query(sql, (group_id_str, qq_str))
        if res:
            return int(res[0]['id'])
            
        return 0

    def add_coins(self, internal_user_id: int, amount: int, reason_type: int = 0, desc: str = "") -> bool:
        """为用户增减积分"""
        sql = "UPDATE users SET coins = coins + %s WHERE id = %s"
        return self._execute_update(sql, (amount, internal_user_id)) > 0

    def get_coins(self, internal_user_id: int) -> int:
        """获取用户积分"""
        sql = "SELECT coins FROM users WHERE id = %s"
        res = self._execute_query(sql, (internal_user_id,))
        return res[0]['coins'] if res else 0

    def append_lottery_record(self, internal_user_id: int, group_id: str, wife_id: str, wife_name: str, sense: int, is_wish: bool = False) -> bool:
        """添加抽奖结果记录"""
        sql = """
        INSERT INTO lottery_records (user_id, group_id, wife_id, wife_name, sense, is_wish, timestamp) 
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        import time
        now = int(time.time())
        return self._execute_update(sql, (internal_user_id, str(group_id), str(wife_id), wife_name, sense, 1 if is_wish else 0, now)) > 0

    def get_user_records(self, internal_user_id: int) -> List[Dict[str, Any]]:
        """获取特定用户的抽奖历史记录"""
        sql = "SELECT * FROM lottery_records WHERE user_id = %s ORDER BY timestamp DESC"
        return self._execute_query(sql, (internal_user_id,))

    def get_group_rank(self, group_id: str, bring_threshold: int = 80) -> List[Dict[str, Any]]:
        """获取群内带走总数排行（只筛选情愫大于等于阈值的记录）"""
        sql = """
        SELECT r.user_id, u.qq, COUNT(*) as count 
        FROM lottery_records r
        JOIN users u ON r.user_id = u.id
        WHERE r.group_id = %s AND r.sense >= %s
        GROUP BY r.user_id, u.qq
        ORDER BY count DESC, MAX(r.timestamp) ASC
        """
        return self._execute_query(sql, (str(group_id), bring_threshold))
    
    def get_max_sense_record(self, group_id: str, wife_name: str) -> Optional[Dict[str, Any]]:
        sql = """
        SELECT r.*, u.qq FROM lottery_records r
        JOIN users u ON r.user_id = u.id
        WHERE r.group_id = %s AND r.wife_name = %s
        ORDER BY r.sense DESC, r.timestamp ASC LIMIT 1
        """
        res = self._execute_query(sql, (str(group_id), wife_name))
        return res[0] if res else None

    def get_all_records_that_max_sense(self, group_id: str, wife_id: Any = None) -> List[Dict[str, Any]]:
        """获取群内最高情愫的所有记录"""
        if wife_id is not None and str(wife_id).strip() != "":
            sql = """
            SELECT r.*, u.qq FROM lottery_records r
            JOIN users u ON r.user_id = u.id
            WHERE r.group_id = %s AND r.wife_id = %s
            ORDER BY r.sense DESC
            """
            return self._execute_query(sql, (str(group_id), str(wife_id)))
        else:
            sql = """
            SELECT r.*, u.qq FROM lottery_records r
            JOIN users u ON r.user_id = u.id
            WHERE r.group_id = %s
            ORDER BY r.sense DESC
            """
            return self._execute_query(sql, (str(group_id),))
        
    def add_or_update_wish(self, group_id: str, qq: str, target: str, remaining_tries: int = 10) -> bool:
        """保存或更新用户的许愿状态到数据库"""
        sql = """
        INSERT INTO wishes (group_id, qq, target, remaining_tries)
        VALUES (%s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE target = VALUES(target), remaining_tries = VALUES(remaining_tries)
        """
        return self._execute_update(sql, (str(group_id), str(qq), target, remaining_tries)) > 0

    def remove_wish(self, group_id: str, qq: str) -> bool:
        """当许愿完成或次数用尽时，从数据库中删除"""
        sql = "DELETE FROM wishes WHERE group_id = %s AND qq = %s"
        return self._execute_update(sql, (str(group_id), str(qq))) > 0
    
    def close(self):
        """关闭数据库连接池"""
        if self.pool:
            try:
                self.pool.close()
            except:
                pass