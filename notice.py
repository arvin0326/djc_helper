import json
import os.path
from typing import List
from datetime import timedelta

import win32con

from data_struct import ConfigInterface, to_raw_type
from log import logger
from upload_lanzouyun import Uploader
from util import *

NOTICE_SHOW_TYPE_ONCE = "once"
NOTICE_SHOW_TYPE_DAILY = "daily"
NOTICE_SHOW_TYPE_WEEKLY = "weekly"
NOTICE_SHOW_TYPE_MONTHLY = "monthly"
NOTICE_SHOW_TYPE_ALWAYS = "always"
NOTICE_SHOW_TYPE_DEPRECATED = "deprecated"

valid_notice_show_type = set(v for k, v in locals().items() if k.startswith("NOTICE_SHOW_TYPE_"))


class Notice(ConfigInterface):
    def __init__(self):
        self.sender = "风之凌殇"
        self.title = "测试消息标题"
        self.message = "测试消息内容"
        self.send_at = "2021-05-11 00:00:00"
        self.show_type = NOTICE_SHOW_TYPE_ONCE
        self.open_url = ""  # 若填入，在展示对应公告时会弹出该网页
        self.expire_at = "2121-05-11 00:00:00"

    def __lt__(self, other):
        return parse_time(self.send_at) < parse_time(other.send_at)

    def need_show(self) -> bool:
        key = f"notice_need_show_{self.title}_{self.send_at}"

        # 判断是否过期
        if get_now() > parse_time(self.expire_at):
            return False

        # 根据显示类型判断
        if self.show_type == NOTICE_SHOW_TYPE_ONCE:
            return is_first_run(key)
        elif self.show_type == NOTICE_SHOW_TYPE_DAILY:
            return is_daily_first_run(key)
        elif self.show_type == NOTICE_SHOW_TYPE_WEEKLY:
            return is_weekly_first_run(key)
        elif self.show_type == NOTICE_SHOW_TYPE_MONTHLY:
            return is_monthly_first_run(key)
        elif self.show_type == NOTICE_SHOW_TYPE_ALWAYS:
            return True
        elif self.show_type == NOTICE_SHOW_TYPE_DEPRECATED:
            return False
        else:
            return False


class NoticeManager:
    def __init__(self, load_from_remote=True):
        self.notices = []  # type: List[Notice]

        self.file_name = "notices.txt"
        self.cache_path = f".cached/{self.file_name}"
        self.save_path = f"utils/{self.file_name}"

        self.load(load_from_remote)

    @try_except()
    def load(self, from_remote=True):
        if from_remote:
            path = self.cache_path
            # 下载最新公告
            self.download_latest_notices()
        else:
            path = self.save_path

        if not os.path.isfile(path):
            return

        # 读取公告
        with open(path, 'r', encoding='utf-8') as save_file:
            for raw_notice in json.load(save_file):
                notice = Notice().auto_update_config(raw_notice)
                self.notices.append(notice)

        self.notices = sorted(self.notices)
        logger.info("公告读取完毕")

    def download_latest_notices(self):
        uploader = Uploader()

        dirpath, filename = os.path.dirname(self.cache_path), os.path.basename(self.cache_path)
        uploader.download_file_in_folder(uploader.folder_online_files, filename, dirpath, try_compressed_version_first=True)

    @try_except()
    def save(self):
        # 本地存盘
        with open(self.save_path, 'w', encoding='utf-8') as save_file:
            json.dump(to_raw_type(self.notices), save_file, ensure_ascii=False, indent=2)
            logger.info("公告存盘完毕")

        # 上传到网盘
        uploader = Uploader()
        with open("upload_cookie.json") as fp:
            cookie = json.load(fp)
        uploader.login(cookie)
        uploader.upload_to_lanzouyun(self.save_path, uploader.folder_online_files, also_upload_compressed_version=True)

    @try_except()
    def show_notices(self):
        valid_notices = list(filter(lambda notice: notice.need_show(), self.notices))

        logger.info(f"发现 {len(valid_notices)} 个新公告")
        for idx, notice in enumerate(valid_notices):
            # 展示公告
            message_box(notice.message, f"公告({idx+1}/{len(valid_notices)}) - {notice.title}", icon=win32con.MB_ICONINFORMATION, open_url=notice.open_url)

        logger.info("所有需要展示的公告均已展示完毕")

    def add_notice(self, title, message, sender="风之凌殇", send_at=format_now(), show_type=NOTICE_SHOW_TYPE_ONCE, open_url="", valid_duration=timedelta(days=7)):
        if show_type not in valid_notice_show_type:
            logger.error(f"无效的show_type={show_type}，有效值为{valid_notice_show_type}")
            return

        for old_notice in self.notices:
            if old_notice.title == title and old_notice.message == message and old_notice.sender == sender:
                logger.error(f"发现内容完全一致的公告，请确定是否是误操作，若非误操作请去文本直接修改。\n{old_notice}")
                return

        notice = Notice()
        notice.title = title
        notice.message = message
        notice.sender = sender
        notice.send_at = send_at
        notice.show_type = show_type
        notice.open_url = open_url
        notice.expire_at = format_time(get_now() + valid_duration)

        self.notices.append(notice)
        logger.info(f"添加公告：{notice}")


def main():
    # 初始化
    nm = NoticeManager(load_from_remote=False)

    # note: 在这里添加公告
    title = "关于集卡活动只增加次数不抽卡的情况说明"
    message = """部分朋友反馈集卡活动只增加次数，不抽卡，经排查，应该是你的集卡配置中的 幸运勇士角色ID 配置成了角色的名称
这个字段要配置的是角色ID，形如 1282822 ，是一串若干长度的数字，而不是填写角色名称。
请清空这个字段，参照提示去填写id，如果填不来可以不填，最多少几次抽卡次数。
"""
    nm.add_notice(title, message,
                  send_at=format_now(),
                  show_type=NOTICE_SHOW_TYPE_ONCE, open_url="", valid_duration=timedelta(days=7))

    nm.save()


if __name__ == '__main__':
    main()
