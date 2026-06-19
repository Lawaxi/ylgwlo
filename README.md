# YLG48 老婆抽奖系统 - Python版

一个基于AstrBot框架的QQ群随机抽奖机，支持星数据管理、许愿系统、排名统计等功能。

## 功能特性

- **随机抽奖**: 在指定群内发送"来个老婆"随机抽取48系成员
- **情愫值系统**: 每次抽奖随机生成情愫值（0-100%），根据情愫值给出推荐
  - 100% 以上: 原地结婚
  - 89-99%: 最佳拍档
  - 79-89%: 带回家吧（可以"带走"）
  - 69-79%: 约会去吧
  - 19-69%: 再努努力
  - 19% 以下: 下辈子吧

- **许愿系统**: 用户可以许愿想要的成员，抽奖时匹配则许愿成功
- **排名系统**: 查看群内带走老婆次数的排名
- **数据统计**: 查询个人的抽奖统计数据
- **星数据管理**: 从48官网自动更新成员列表
- **特殊次数**: 支持每2小时刷新一次基础抽奖次数
- **每日第一**: 每个群每日第一个抽奖的用户获得奖励
- **生日加成**: 抽中成员生日时获得额外奖励

## 系统要求

- Python 3.8+
- MySQL 5.7+ 或其他兼容数据库
- AstrBot 框架
- 互联网连接（用于获取星数据）

## 安装步骤

### 1. 复制文件到AstrBot插件目录

```bash
cp -r wife_lottery /path/to/astrbot/plugins/
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置数据库

编辑 `database.py` 中的 `DEFAULT_DATABASE_CONFIG`:

```python
DEFAULT_DATABASE_CONFIG = {
    'host': 'your_mysql_host',
    'port': 3306,
    'user': 'your_mysql_user',
    'password': 'your_mysql_password',
    'database': 'lottery'
}
```

或在运行时传入配置：

```python
from database import Database

config = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': 'password',
    'database': 'lottery'
}

db = Database(config)
```

### 4. 配置目标群号

编辑 `main.py` 中的 `target_group`:

```python
self.target_group = "764687233"  # 改为你的目标群号
```

### 5. 启动AstrBot

```bash
astrbot run
```

## 使用指令

### 基础指令

| 指令 | 功能 | 示例 |
|------|------|------|
| 来个老婆 | 随机抽取一个成员 | 来个老婆 |
| 换个老婆 | 更换已有的老婆 | 换个老婆 |
| 我的老婆 | 查询个人统计数据 | 我的老婆 |
| 许愿 [成员名] | 许愿某个成员 | 许愿 林忆宁 |
| 排名 | 查看群内排名 | 排名 |
| 我的ID | 查看用户ID | 我的ID |
| update_star_data | 更新星数据 | update_star_data |

### 指令自定义

编辑 `config.py` 的 `_default_config()` 方法修改指令：

```python
"system": {
    "lottery": "来个老婆,换个老婆",
    "data": "我的老婆",
    "wish": "许愿",
    "rank": "排名",
    ...
}
```

## 数据库表结构

### users 表
- `id`: 用户内部ID
- `group_id`: 群号
- `user_number`: QQ号
- `coins`: 用户币数量
- `lottery_entries`: 特殊抽奖次数

### logs 表
- `id`: 记录ID
- `group_id`: 群号
- `user_id`: 用户ID
- `wife_id`: 成员ID
- `wife_name`: 成员名称
- `sense`: 情愫值
- `wish`: 是否通过许愿获得
- `timestamp`: 时间戳

### coin_log 表
- `id`: 日志ID
- `user_id`: 用户ID
- `amount`: 币数量
- `reason_code`: 原因代码
- `reason_details`: 原因详情
- `timestamp`: 时间戳

### wish 表
- `id`: 许愿ID
- `user_id`: 用户ID
- `target`: 许愿目标
- `created_at`: 创建时间

## 配置文件

### lottery_config.json

自动生成，存储系统配置和指令设置。

### star_data.json

存储48系成员数据，包含：
- `s`: 成员真名
- `sid`: 成员ID
- `n`: 成员昵称
- `g`: 所属团（SNH/GNZ/BEJ等）
- `t`: 所属队伍
- `p`: 成员期数
- `i`: 口袋ID
- `birthday`: 生日（MM.DD格式）

## 特殊机制

### 每日刷新
- 每天凌晨自动重置每日第一标记
- 每两小时可抽奖一次
- 每天8点额外给予2次抽奖机会

### 情愫王
- 自动追踪每个成员的最高情愫王
- 显示用户是否是某个成员的情愫王

### 许愿系统
- 用户许愿后，10次机会内抽中目标即为成功
- 许愿成功时情愫值+10，获得20币奖励
- 许愿失败后可重新许愿

## 扩展和自定义

### 修改情愫值评分

编辑 `utils.py` 的 `WifeUtil.recommend()` 方法：

```python
@staticmethod
def recommend(sense: int) -> str:
    if sense > 99:
        return "原地结婚"
    # ... 修改阈值和文案
```

### 添加新指令

在 `main.py` 的 `on_message()` 方法中添加新的指令处理：

```python
if text == "new_command":
    result = self.handler.new_method(user_id, group_id)
    yield event.chain_result([...])
```

### 自定义数据库操作

在 `database.py` 中添加新方法，或继承 `Database` 类扩展功能。

## 故障排除

### 数据库连接失败
- 检查MySQL服务是否运行
- 验证连接配置（主机、用户名、密码、数据库名）
- 确保数据库已创建

### 星数据获取失败
- 检查网络连接
- 验证48官网API是否可用
- 查看日志中的错误信息

### 指令无响应
- 确认群号配置正确
- 检查指令拼写是否匹配
- 查看AstrBot日志是否有错误

## 原始Java版本参考

本项目基于Java版本的逻辑转换。如需了解原始设计，可参考：
- `WifeHandler.java`: 核心业务逻辑
- `database.java`: 数据库操作

## 许可证

MIT License

## 贡献

欢迎提交Issue和Pull Request！

## 联系方式

如有问题或建议，请通过GitHub提出。
