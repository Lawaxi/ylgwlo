import json
from pathlib import Path
import requests
from datetime import datetime


class Config:

    def __init__(self, cfg):
        self.cfg = cfg
        self.star_data_file = "star_data.json"
        self.star_data = []
        self._load_star_data()

    def get_lottery_commands(self):
        return [cmd.strip() for cmd in self.cfg.get("lottery", "").split(",")]

    def get_data_commands(self):
        return [cmd.strip() for cmd in self.cfg.get("data", "").split(",")]

    def get_wish_commands(self):
        return [cmd.strip() for cmd in self.cfg.get("wish", "").split(",")]

    def get_rank_commands(self):
        return [cmd.strip() for cmd in self.cfg.get("rank", "").split(",")]

    def get_star_data(self):
        return self.star_data
    
    def get_bring_threshold(self):
        return self.cfg.get("bring_threshold", 80)

    def _load_star_data(self):
        if Path(self.star_data_file).exists():
            with open(self.star_data_file, 'r', encoding='utf-8') as f:
                self.star_data = json.load(f)
        else:
            self.download_star_data()

    def download_star_data(self) -> str:
        api_url = "https://h5.48.cn/resource/jsonp/allmembers.php"

        headers = {
            "Host": "h5.48.cn",
            "User-Agent": "Mozilla/5.0"
        }

        try:
            original_star_data = self.star_data.copy()

            last_time = "-ori"
            try:
                stat = Path(self.star_data_file).stat()
                mtime = datetime.fromtimestamp(stat.st_mtime)
                last_time = mtime.strftime("-%Y%m%d")
            except:
                pass

            self.star_data.clear()

            initial_members = [
                {"s": "鞠婧祎", "sid": "10027", "n": "小鞠", "g": "SNH", "t": "", "p": "SNH48 二期生", "i": "0", "birthday": "06.18"},
                {"s": "李艺彤", "sid": "10031", "n": "发卡", "g": "SNH", "t": "", "p": "SNH48 二期生", "i": "0", "birthday": "12.23"},
            ]
            self.star_data.extend(initial_members)

            params = {
                "gid": "00",
                "callback": "get_members_success",
                "_": int(datetime.now().timestamp() * 1000)
            }

            response = requests.get(api_url, headers=headers, params=params, timeout=10)
            response.raise_for_status()

            text = response.text
            json_str = text[text.find("(")+1:text.rfind(")")]
            data = json.loads(json_str)

            for m in data.get("rows", []):
                self.star_data.append({
                    "s": m.get("sname", ""),
                    "sid": m.get("sid", ""),
                    "n": m.get("nickname", ""),
                    "g": m.get("gname", ""),
                    "t": m.get("tname", ""),
                    "p": m.get("pname", ""),
                    "i": m.get("pocket_id", "0"),
                    "birthday": m.get("birth_day", "")
                })

            with open(self.star_data_file, 'w', encoding='utf-8') as f:
                json.dump(self.star_data, f, ensure_ascii=False, indent=2)

            return f"已更新 {len(self.star_data)} 人"

        except Exception as e:
            return f"获取失败: {e}"