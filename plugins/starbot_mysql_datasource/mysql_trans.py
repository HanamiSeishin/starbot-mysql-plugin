import json
import os
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel
from graia.ariadne import Ariadne
from starbot.core.datasource import MySQLDataSource
from starbot.utils import config

from .mysql_utils import ObjMysql


class LiveOn(BaseModel):
    enabled: Optional[bool] = False
    """是否启用开播推送。默认：False"""

    message: Optional[str] = "{uname} 正在直播 {title}\n{url}\n{cover}"
    """
    开播推送内容模板。
    专用占位符：{uname} 主播昵称，{title} 直播间标题，{url} 直播间链接，{cover} 直播间封面图。
    通用占位符：{next} 消息分条，{atall} @全体成员，{at114514} @指定QQ号，{urlpic=链接} 网络图片，{pathpic=路径} 本地图片，{base64pic=base64字符串} base64图片。
    默认：""
    """


class LiveOff(BaseModel):
    enabled: Optional[bool] = False
    """是否启用下播推送。默认：False"""

    message: Optional[str] = "{uname} 直播结束了"
    """
    下播推送内容模板。
    专用占位符：{uname} 主播昵称。
    通用占位符：{next} 消息分条，{atall} @全体成员，{at114514} @指定QQ号，{urlpic=链接} 网络图片，{pathpic=路径} 本地图片，{base64pic=base64字符串} base64图片。
    默认：""
    """


class LiveReport(BaseModel):
    enabled: Optional[bool] = False
    """是否启用直播报告。默认：False"""

    logo: Optional[str] = ""
    """主播立绘的路径，会绘制在直播报告右上角合适位置。默认：None"""

    logo_base64: Optional[str] = ""
    """主播立绘的 Base64 字符串，会绘制在直播报告右上角合适位置，立绘路径不为空时优先使用路径。默认：None"""

    time: Optional[bool] = False
    """是否展示本场直播直播时间段和直播时长。默认：False"""

    fans_change: Optional[bool] = False
    """是否展示本场直播粉丝变动。默认：False"""

    fans_medal_change: Optional[bool] = False
    """是否展示本场直播粉丝团（粉丝勋章数）变动。默认：False"""

    guard_change: Optional[bool] = False
    """是否展示本场直播大航海变动。默认：False"""

    danmu: Optional[bool] = False
    """是否展示本场直播收到弹幕数、发送弹幕人数。默认：False"""

    box: Optional[bool] = False
    """是否展示本场直播收到盲盒数、送出盲盒人数、盲盒盈亏。默认：False"""

    gift: Optional[bool] = False
    """是否展示本场直播礼物收益、送礼物人数。默认：False"""

    sc: Optional[bool] = False
    """是否展示本场直播 SC（醒目留言）收益、发送 SC（醒目留言）人数。默认：False"""

    guard: Optional[bool] = False
    """是否展示本场直播开通大航海数。默认：False"""

    danmu_ranking = 0
    """展示本场直播弹幕排行榜的前多少名，0 为不展示。默认：0"""

    box_ranking = 0
    """展示本场直播盲盒数量排行榜的前多少名，0 为不展示。默认：0"""

    box_profit_ranking = 0
    """展示本场直播盲盒盈亏排行榜的前多少名，0 为不展示。默认：0"""

    gift_ranking = 0
    """展示本场直播礼物排行榜的前多少名，0 为不展示。默认：0"""

    sc_ranking = 0
    """展示本场直播 SC（醒目留言）排行榜的前多少名，0 为不展示。默认：0"""

    guard_list = False
    """是否展示本场直播开通大航海观众列表。默认：False"""

    box_profit_diagram = False
    """是否展示本场直播的盲盒盈亏曲线图。默认：False"""

    danmu_diagram = False
    """是否展示本场直播的弹幕互动曲线图。默认：False"""

    box_diagram = False
    """是否展示本场直播的盲盒互动曲线图。默认：False"""

    gift_diagram = False
    """是否展示本场直播的礼物互动曲线图。默认：False"""

    sc_diagram = False
    """是否展示本场直播的 SC（醒目留言）互动曲线图。默认：False"""

    guard_diagram = False
    """是否展示本场直播的开通大航海互动曲线图。默认：False"""

    danmu_cloud: Optional[bool] = False
    """是否生成本场直播弹幕词云。默认：False。默认：False"""


class Dynamic(BaseModel):
    enabled: Optional[bool] = False
    """是否启用动态推送。默认：False"""

    message: Optional[str] = "{uname} {action}\n{url}\n{picture}"
    """
    动态推送内容模板。
    专用占位符：{uname} 主播昵称，{action} 动态操作类型（发表了新动态，转发了新动态，投稿了新视频...），{url} 动态链接（若为发表视频、专栏等则为视频、专栏等对应的链接），{picture} 动态图片。
    通用占位符：{next} 消息分条，{atall} @全体成员，{at114514} @指定QQ号，{urlpic=链接} 网络图片，{pathpic=路径} 本地图片，{base64pic=base64字符串} base64图片。
    默认：""
    """


class Target(BaseModel):
    id: int
    """QQ 号或群号"""

    type: int = 1
    """推送类型，可选 QQ 好友或 QQ 群推送。默认：PushType.Group"""

    live_on: Optional[LiveOn] = LiveOn()
    """开播推送配置。默认：LiveOn()"""

    live_off: Optional[LiveOff] = LiveOff()
    """下播推送配置。默认：LiveOff()"""

    live_report: Optional[LiveReport] = LiveReport()
    """直播报告配置。默认：LiveReport()"""

    dynamic_update: Optional[Dynamic] = Dynamic()
    """动态推送配置。默认：DynamicUpdate()"""


class Up(BaseModel):
    uid: int
    """主播 UID"""

    targets: List[Target]
    """主播所需推送的所有好友或群"""


class Bot(BaseModel):
    qq: int
    """Bot 的 QQ 号"""

    ups: List[Up]
    """Bot 账号下运行的 UP 主列表"""

mysql_datasource: Optional[MySQLDataSource] = None


async def datasource_trans_to_mysql():
    datasource = Ariadne.options["StarBotDataSource"]
    if isinstance(datasource, MySQLDataSource):
        return False, "已经是MYSQL数据源，无需转储"
    bots: List[Bot] = datasource.bots

    username = config.get("MYSQL_USERNAME")
    password = config.get("MYSQL_PASSWORD")
    host = config.get("MYSQL_HOST")
    port = config.get("MYSQL_PORT")
    db = config.get("MYSQL_DB")
    global mysql_datasource
    if mysql_datasource is None:
        mysql_datasource = MySQLDataSource(username, password, host, port, db)
    for bot in bots:
        for up in bot.ups:
            for target in up.targets:
                obj_mysql = ObjMysql(mysql_datasource)
                target_dict: dict = target.dict()
                await obj_mysql.trans_targets(bot.qq, up.uid, target.id, target_dict)
                await obj_mysql.trans_save()
    return True, ""


def datasource_trans_to_json():
    datasource = Ariadne.options["StarBotDataSource"]

    json_file = f"推送配置_{datetime.now().strftime('%Y%m%d%H%M%S')}.json"

    try:
        with open(json_file, "w", encoding="utf-8") as f:
            bot_list_json = []
            for bot in datasource.bots:
                bot_list_json.append(bot.json(ensure_ascii=False))
            f.write("[" + ",".join(bot_list_json) + "]")
    except Exception as ex:
        if os.path.exists(json_file):
            os.remove(json_file)
        return False, f"发生错误： {ex}"
    return True, json_file
