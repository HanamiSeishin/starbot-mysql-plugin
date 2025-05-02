from typing import List, Optional, Union
import asyncio
import uuid
from PIL import Image as PIL_Image
from io import BytesIO
import base64
import ssl

from graia.ariadne import Ariadne
from graia.ariadne.message.chain import MessageChain
from graia.ariadne.message.element import Image, At, AtAll, Quote
from graia.ariadne.model import Friend, Group, Member
from starbot.core.datasource import MySQLDataSource
from starbot.core.user import User, RelationType
from starbot.core.room import Up
from starbot.core.model import PushType
from starbot.utils import config, redis
from starbot.utils.network import request, get_session
from starbot.utils.utils import get_credential
from starbot.exception import ResponseCodeException, DataSourceException
from starbot.painter.PicGenerator import PicGenerator, Color

from loguru import logger

_version = "v1.1.3"

master_qq = config.get("MASTER_QQ")
prefix = config.get("COMMAND_PREFIX")


def check_at_object(account: int, message: MessageChain):
    for element in message.content:
        if isinstance(element, Quote) or isinstance(element, AtAll):
            # 忽略atall和引用回复消息
            return False
        if isinstance(element, At):
            if element.target != account:
                # 忽略at其他人消息
                return False
    return True


def check_not_mysql_datasource():
    if isinstance(Ariadne.options["StarBotDataSource"], MySQLDataSource):
        return False
    return True


def check_mysql_datasource():
    if isinstance(Ariadne.options["StarBotDataSource"], MySQLDataSource):
        return True
    return False


def get_logger_prefix(cmd: object, sender: object, member: Optional[Member] = None) -> object:
    if isinstance(sender, Group):
        if member is None:
            return f"群[{sender.name}]({sender.id}) 命令({cmd})"
        else:
            if master_qq == member.id:
                return f"群[{sender.name}]({sender.id})主人[{member.name}]({member.id}) 命令({cmd})"
            else:
                return f"群[{sender.name}]({sender.id})成员[{member.name}]({member.id}) 命令({cmd})"
    elif isinstance(sender, Friend):
        if master_qq == sender.id:
            return f"主人[{sender.nickname}]({sender.id}) 命令({cmd})"
        else:
            return f"好友[{sender.nickname}]({sender.id}) 命令({cmd})"
    # 不应该进入这个分支！
    return f"未知身份 命令({cmd})"


async def select_uname_and_room_id(uid):
    user_info_url = f"https://api.live.bilibili.com/live_user/v1/Master/info?uid={uid}"
    user_info = await request("GET", user_info_url)
    uname = user_info["info"]["uname"]
    room_id = user_info["room_id"]
    if user_info["room_id"] == 0:
        logger.warning(f"UP主{uname}(UID:{uid})还未开通直播间")
    return uname, room_id


def get_message_help(message_type: str):
    msg = ""
    if message_type == "news":
        msg = """专用占位符：{uname} 主播昵称，{action} 动态操作类型（发表了新动态，转发了新动态，投稿了新视频...），{url} 动态链接（若为发表视频、专栏等则为视频、专栏等对应的链接），{picture} 动态图片。
通用占位符：{next} 消息分条，{atall} @全体成员，{at114514} @指定QQ号，{urlpic=链接} 网络图片。"""
    if message_type == "live_on":
        msg = """专用占位符：{uname} 主播昵称，{title} 直播间标题，{url} 直播间链接，{cover} 直播间封面图。
通用占位符：{next} 消息分条，{atall} @全体成员，{at114514} @指定QQ号，{urlpic=链接} 网络图片。"""
    if message_type == "live_off":
        msg = """专用占位符：{uname} 主播昵称。
通用占位符：{next} 消息分条，{atall} @全体成员，{at114514} @指定QQ号，{urlpic=链接} 网络图片。"""
    return msg


def create_auto_follow_task():
    core_tasks = set()
    database = Ariadne.options["StarBotDataSource"]
    uid = config.get("LOGIN_UID")
    me = User(uid, get_credential())

    async def auto_follow_task():
        try:
            follows = set()
            page = 1
            while True:
                res = await me.get_followings(page)
                follows = follows.union(set(map(lambda x: x["mid"], res["list"])))
                if len(res["list"]) < 20:
                    break
                page += 1

            need_follow_uids = set()
            for u in database.get_up_list():
                if u.uid != uid and any(map(lambda t: t.dynamic_update.enabled, u.targets)):
                    need_follow_uids.add(u.uid)
            need_follow_uids.difference_update(follows)

            if len(need_follow_uids) == 0:
                logger.success(f"不存在打开了动态推送但未关注的 UP 主")
                return

            logger.info(f"检测到 {len(need_follow_uids)} 个打开了动态推送但未关注的 UP 主, 启动自动关注任务")
            for i, u in enumerate(need_follow_uids):
                follow_user = User(u, get_credential())
                await follow_user.modify_relation(RelationType.SUBSCRIBE)
                logger.success(f"已关注: {i + 1} / {len(need_follow_uids)}")
                if i + 1 < len(need_follow_uids):
                    await asyncio.sleep(10)
            logger.success(f"已成功关注了 {len(need_follow_uids)} 个 UP 主")
        except ResponseCodeException as e:
            if e.code == 22115 or e.code == 22007:
                logger.warning(f"读取登录账号的关注列表失败, 请检查登录凭据是否已失效, 错误信息: {e.msg}")
        except Exception as e:
            logger.exception(f"自动关注任务异常", e)

    follow_task = asyncio.create_task(auto_follow_task())
    core_tasks.add(follow_task)
    follow_task.add_done_callback(lambda t: core_tasks.remove(t))


def draw_pic(messages: Union[str, List], title: Optional[str] = None, sub_title: Optional[str] = None, width=1000,
             height=100000):
    if messages is None or len(messages) == 0:
        return None
    pic = PicGenerator(width, height)
    pic.set_pos(50, 50).draw_rounded_rectangle(0, 0, width, height, 35, Color.WHITE).copy_bottom(35)
    if title is not None and len(title) > 0:
        pic.draw_chapter(title)
        if sub_title is not None and len(title) > 0:
            pic.draw_text_multiline(50, sub_title)
        pic.draw_text("")
    if isinstance(messages, str):
        messages = messages.split("\n")
    for message in messages:
        if isinstance(message, dict):
            pic.draw_section(message.get("section"))
            for context in message.get("context"):
                pic.draw_text_multiline(50, context)
        if isinstance(message, str):
            pic.draw_text_multiline(50, message)
    # 底部版权信息，请务必保留此处
    pic.draw_text_right(25, "Designed By StarBot", Color.GRAY)
    pic.draw_text_right(25, "https://github.com/Starlwr/StarBot", Color.LINK)
    pic.draw_text_right(25, f"{__package__}.{_version}", Color.GREEN)
    pic.crop_and_paste_bottom()
    return Image(base64=pic.base64())


def draw_image_pic(image_base64, title: Optional[str] = None, width=800, height=100000):
    if image_base64 is None or len(image_base64) == 0:
        return None
    top_blank = 75
    margin = 50
    pic = PicGenerator(width, height)
    pic.set_pos(margin, top_blank + margin).draw_rounded_rectangle(0, top_blank, width, height - top_blank, 35,
                                                                   Color.WHITE).copy_bottom(35)
    if title is not None and len(title) > 0:
        pic.draw_chapter(title)
        pic.draw_text("")

    logo_bytes = BytesIO(base64.b64decode(image_base64))
    logo = PIL_Image.open(logo_bytes)

    logo = logo.convert("RGBA")
    logo = logo.crop(logo.getbbox())

    logo_width = 300
    logo_height = int(logo.height * (logo_width / logo.width))
    logo = logo.resize((logo_width, logo_height))

    pic.draw_img_alpha(logo)

    # 底部版权信息，请务必保留此处
    pic.draw_text("")
    pic.draw_text_right(50, "Designed By StarBot", Color.GRAY)
    pic.draw_text_right(50, "https://github.com/Starlwr/StarBot", Color.LINK)
    pic.draw_text_right(25, f"{__package__}.{_version}", Color.GREEN)
    pic.crop_and_paste_bottom()
    return Image(base64=pic.base64())


# 默认帮助，取自starbot.commands.builtin.help，可以根据需要自行修改
async def default_help(sender: Union[Friend, Group]):
    disable_querys = ["DenyRoomData", "DenyRoomDataTotal", "DenyBind", "DenyUserData", "DenyUserDataTotal"]
    disabled = [False] * 5
    if isinstance(sender, Group):
        disabled = [await redis.exists_disable_command(x, sender.id) for x in disable_querys]

    width = 1000
    height = 100000
    pic = PicGenerator(width, height)
    pic.set_pos(50, 50).draw_rounded_rectangle(0, 0, width, height, 35, Color.WHITE).copy_bottom(35)

    pic.draw_chapter("StarBot 帮助")
    pic.draw_text("")

    pic.draw_section(f"1.{prefix}禁用命令")
    commands = "、".join([f"{prefix}{x} [命令名]" for x in ["禁用", "disable"]])
    pic.draw_text_multiline(50, ["命令: ", commands], [Color.RED, Color.BLACK])
    pic.draw_text(["示例: ", "禁用 直播间总数据"], [Color.RED, Color.BLACK])
    pic.draw_tip("此命令仅群聊可用")
    pic.draw_tip("可禁用的命令名: 绑定、直播间数据、直播间总数据、我的数据、我的总数据")
    pic.draw_tip("命令禁用只针对本群，如有多群需同时禁用命令请每个群进行一次配置")

    pic.draw_section(f"2.{prefix}启用命令")
    commands = "、".join([f"{prefix}{x} [命令名]" for x in ["启用", "enable"]])
    pic.draw_text_multiline(50, ["命令: ", commands], [Color.RED, Color.BLACK])
    pic.draw_text(["示例: ", "启用 直播间总数据"], [Color.RED, Color.BLACK])
    pic.draw_tip("此命令仅群聊可用")
    pic.draw_tip("用于禁用命令后解除禁用")

    pic.draw_section(f"3.{prefix}直播间数据")
    pic.draw_text_multiline(50, ["命令: ", f"{prefix}直播间数据"], [Color.RED, Color.BLACK])
    if disabled[0]:
        pic.draw_text("本群已禁用此命令", Color.RED)
    pic.draw_tip("查询本直播间最近一场直播的数据")

    pic.draw_section(f"4.{prefix}直播间总数据")
    pic.draw_text_multiline(50, ["命令: ", f"{prefix}直播间总数据"], [Color.RED, Color.BLACK])
    if disabled[1]:
        pic.draw_text("本群已禁用此命令", Color.RED)
    pic.draw_tip("查询本直播间自注册之日起的累计总数据")

    pic.draw_section(f"5.{prefix}绑定")
    commands = "、".join([f"{prefix}{x} [UID]" for x in ["绑定", "bind"]])
    pic.draw_text_multiline(50, ["命令: ", commands], [Color.RED, Color.BLACK])
    pic.draw_text(["示例: ", "绑定 114514"], [Color.RED, Color.BLACK])
    if disabled[2]:
        pic.draw_text("本群已禁用此命令", Color.RED)
    pic.draw_tip("将QQ号绑定至B站账号")
    pic.draw_tip("绑定成功后即可查询自己在本直播间的数据")
    pic.draw_tip("绑定后如需换绑直接使用新UID再次绑定即可")

    pic.draw_section(f"6.{prefix}我的数据")
    pic.draw_text_multiline(50, ["命令: ", f"{prefix}我的数据"], [Color.RED, Color.BLACK])
    if disabled[3]:
        pic.draw_text("本群已禁用此命令", Color.RED)
    pic.draw_tip("查询自己在本直播间最近一场直播的数据、排名")
    pic.draw_tip("需绑定B站账号后使用")

    pic.draw_section(f"7.{prefix}我的总数据")
    pic.draw_text_multiline(50, ["命令: ", f"{prefix}我的总数据"], [Color.RED, Color.BLACK])
    if disabled[4]:
        pic.draw_text("本群已禁用此命令", Color.RED)
    pic.draw_tip("查询自己在本直播间自注册之日起的累计总数据、排名、占比")
    pic.draw_tip("需绑定B站账号后使用")

    pic.draw_section(f"8.{prefix}数据排行榜")
    types = [
        "弹幕排行", "弹幕总排行",
        "盲盒排行", "盲盒总排行",
        "盲盒盈亏排行", "盲盒盈亏总排行",
        "礼物排行", "礼物总排行",
        "SC排行", "SC总排行"
    ]
    commands = "、".join([f"{prefix}{x} <页码>" for x in types])
    pic.draw_text_multiline(50, ["命令: ", commands], [Color.RED, Color.BLACK])
    pic.draw_text(["示例: ", "弹幕排行、礼物总排行 3"], [Color.RED, Color.BLACK])
    pic.draw_tip("查询本直播间的数据排行榜")
    pic.draw_tip("xx排行指本直播间最近一场直播的数据排行榜")
    pic.draw_tip("xx总排行指本直播间自注册之日起的累计总数据排行榜")
    pic.draw_tip("不输入页码参数默认查询第一页")

    pic.draw_section(f"9.{prefix}开播@我")
    commands = "、".join([f"{prefix}{x}" for x in ["开播@我", "直播@我"]])
    pic.draw_text_multiline(50, ["命令: ", commands], [Color.RED, Color.BLACK])
    pic.draw_tip("此命令仅群聊可用")
    pic.draw_tip("本直播间开播时单独@自己")
    pic.draw_tip("如配置了@全体成员会优先@全体成员")
    pic.draw_tip("当没有配置@全体成员或@全体成员失败时会单独@\"开播@我\"名单中的群成员")

    pic.draw_section(f"10.{prefix}取消开播@我")
    commands = "、".join([f"{prefix}{x}" for x in ["取消开播@我", "退出开播@我", "开播不@我", "开播别@我"]])
    pic.draw_text_multiline(50, ["命令: ", commands], [Color.RED, Color.BLACK])
    pic.draw_tip("此命令仅群聊可用")
    pic.draw_tip("退出本群的\"开播@我\"名单")

    pic.draw_section(f"11.{prefix}开播@名单")
    commands = "、".join([f"{prefix}{x}" for x in ["开播@名单", "开播@列表"]])
    pic.draw_text_multiline(50, ["命令: ", commands], [Color.RED, Color.BLACK])
    pic.draw_tip("此命令仅群聊可用")
    pic.draw_tip("查询本群的\"开播@我\"名单")

    pic.draw_section(f"12.{prefix}动态@我")
    pic.draw_text_multiline(50, ["命令: ", f"{prefix}动态@我"], [Color.RED, Color.BLACK])
    pic.draw_tip("此命令仅群聊可用")
    pic.draw_tip("主播发布新动态时单独@自己")
    pic.draw_tip("如配置了@全体成员会优先@全体成员")
    pic.draw_tip("当没有配置@全体成员或@全体成员失败时会单独@\"动态@我\"名单中的群成员")

    pic.draw_section(f"13.{prefix}取消动态@我")
    commands = "、".join([f"{prefix}{x}" for x in ["取消动态@我", "退出动态@我", "动态不@我", "动态别@我"]])
    pic.draw_text_multiline(50, ["命令: ", commands], [Color.RED, Color.BLACK])
    pic.draw_tip("此命令仅群聊可用")
    pic.draw_tip("退出本群的\"动态@我\"名单")

    pic.draw_section(f"14.{prefix}动态@名单")
    commands = "、".join([f"{prefix}{x}" for x in ["动态@名单", "动态@列表"]])
    pic.draw_text_multiline(50, ["命令: ", commands], [Color.RED, Color.BLACK])
    pic.draw_tip("此命令仅群聊可用")
    pic.draw_tip("查询本群的\"动态@我\"名单")

    # 底部版权信息，请务必保留此处
    pic.draw_text_right(25, "Designed By StarBot", Color.GRAY)
    pic.draw_text_right(25, "https://github.com/Starlwr/StarBot", Color.LINK)
    pic.draw_text_right(25, f"{__package__}.{_version}", Color.GREEN)
    pic.crop_and_paste_bottom()
    return Image(base64=pic.base64())

# bot状态，0：公开，1：私人

async def __exists_mode_status(qq_num: int) -> bool:
    return await redis.hexists(f"StarBotModeStatus", qq_num)


async def __get_mode_status(qq_num: int) -> int:
    return await redis.hgeti(f"StarBotModeStatus", qq_num)


async def __set_mode_status(qq_num: int, status: int):
    await redis.hset(f"StarBotModeStatus", qq_num, status)


async def set_bot_mode_public(qq_num: int):
    await __set_mode_status(qq_num, 0)


async def set_bot_mode_private(qq_num: int):
    await __set_mode_status(qq_num, 1)


async def check_bot_mode_public(qq_num: int) -> bool:
    """
    :param qq_num: bot qq号
    :return: False为私有状态，True为公开状态 如果键值对不存在兼容旧版本为公开状态返回True
    """
    if await __exists_mode_status(qq_num) and await __get_mode_status(qq_num) == 1:
        return False
    return True


async def element_get_bytes(image: Image):
    if image.base64:
        return base64.b64decode(image.base64)
    if not image.url:
        raise ValueError("you should offer a url.")
    # 针对multimedia.nt.qq.com.cn的ssl握手失败进行密码套件兼容
    # 修改方案来自于https://github.com/LagrangeDev/Lagrange.Core/issues/315
    ssl_context = ssl.create_default_context()
    ssl_context.set_ciphers('DEFAULT')
    ssl_context.options |= ssl.OP_NO_SSLv2
    ssl_context.options |= ssl.OP_NO_SSLv3
    ssl_context.options |= ssl.OP_NO_TLSv1
    ssl_context.options |= ssl.OP_NO_TLSv1_1
    ssl_context.options |= ssl.OP_NO_COMPRESSION
    response = await get_session().get(image.url, ssl=ssl_context)
    response.raise_for_status()
    image_data = await response.read()
    image_base64 = base64.b64encode(image_data).decode("ascii")
    image.base64 = image_base64
    return image_base64


class BotMysql:
    id: int = 0
    bot: int = 0
    uid: int = 0

    mysql_name = "bot"

    def __init__(self, bot: int, uid: int):
        self.bot = bot
        self.uid = uid

    def get_id(self) -> int:
        return self.id

    def get_uid(self) -> int:
        return self.uid

    def set_id(self, id: int):
        self.id = id

    def mysql_insert_query(self) -> str:
        return f"INSERT INTO `{self.mysql_name}` (`bot`, `uid`) VALUES ({self.bot}, {self.uid})"

    def mysql_delete_query(self) -> str:
        return f"DELETE FROM `{self.mysql_name}` WHERE `id` = '{self.id}'"

    def mysql_get_by_bot_and_uid_query(self) -> str:
        return f"SELECT * FROM `{self.mysql_name}` WHERE `bot` = {self.bot} and `uid` = {self.uid}"


class DynamicMysql:
    id: str = ""
    uid: int = 0
    enabled: bool = False
    message: str = "{uname} {action}\n{url}\n{picture}"
    _message_atall: str = "{atall}{uname} {action}\n{url}\n{picture}"
    _message_default: str = "{uname} {action}\n{url}\n{picture}"

    mysql_name = "dynamic_update"

    def __init__(self, uid: int):
        self.uid = uid

    def dict_init(self, **args):
        self.id = args.get("id")
        self.uid = args.get("uid")
        self.enabled = args.get("enabled")
        self.message = args.get("message")

    def dict_trans(self, **args):
        self.enabled = args.get("enabled")
        self.message = args.get("message")

    def set_id(self, id: str):
        self.id = id

    def set_uid(self, uid: int):
        self.uid = uid

    def enable(self):
        self.enabled = True

    def disable(self):
        self.enabled = False

    def add_atall(self):
        self.message = self._message_atall

    def del_atall(self):
        self.message = self._message_default

    def set_message(self, message: str = ""):
        if message:
            self.message = message
        else:
            self.message = self._message_default

    def mysql_insert_query(self) -> str:
        return f"INSERT INTO `{self.mysql_name}` (`id`, `uid`, `enabled`, `message`) VALUES ('{self.id}', {self.uid}, {int(self.enabled)}, '{self.message}')"

    def mysql_delete_query(self) -> str:
        return f"DELETE FROM `{self.mysql_name}` WHERE `id` = '{self.id}'"

    def mysql_update_query(self) -> str:
        return f"UPDATE `{self.mysql_name}` SET `uid` = {self.uid}, `enabled` = {int(self.enabled)}, `message` = '{self.message}' WHERE `id` = '{self.id}'"

    def mysql_get_by_id_query(self, id="") -> str:
        if id == "":
            id = self.id
        return f"SELECT * FROM `{self.mysql_name}` WHERE `id` = '{id}'"


class LiveOffMysql():
    id: str = ""
    uid: int = 0
    enabled: bool = False
    message: str = "{uname} 直播结束了"

    mysql_name = "live_off"

    def __init__(self, uid: int):
        self.uid = uid

    def dict_init(self, **args):
        self.id = args.get("id")
        self.uid = args.get("uid")
        self.enabled = args.get("enabled")
        self.message = args.get("message")

    def dict_trans(self, **args):
        self.enabled = args.get("enabled")
        self.message = args.get("message")

    def set_id(self, id: str):
        self.id = id

    def set_uid(self, uid: int):
        self.uid = uid

    def enable(self):
        self.enabled = True

    def disable(self):
        self.enabled = False

    def set_message(self, message: str = ""):
        if message:
            self.message = message
        else:
            self.message = self._message_default

    def mysql_insert_query(self) -> str:
        return f"INSERT INTO `{self.mysql_name}` (`id`, `uid`, `enabled`, `message`) VALUES ('{self.id}', {self.uid}, {int(self.enabled)}, '{self.message}')"

    def mysql_delete_query(self) -> str:
        return f"DELETE FROM `{self.mysql_name}` WHERE `id` = '{self.id}'"

    def mysql_update_query(self) -> str:
        return f"UPDATE `{self.mysql_name}` SET `uid` = {self.uid}, `enabled` = {int(self.enabled)}, `message` = '{self.message}' WHERE `id` = '{self.id}'"

    def mysql_get_by_id_query(self, id="") -> str:
        if id == "":
            id = self.id
        return f"SELECT * FROM `{self.mysql_name}` WHERE `id` = '{id}'"


class LiveOnMysql:
    id: str = ""
    uid: int = 0
    enabled: bool = False
    message: str = "{uname} 正在直播 {title}\n{url}\n{cover}"
    _message_atall: str = "{atall}{uname} 正在直播 {title}\n{url}\n{cover}"
    _message_default: str = "{uname} 正在直播 {title}\n{url}\n{cover}"

    mysql_name = "live_on"

    def __init__(self, uid: int):
        self.uid = uid

    def dict_init(self, **args):
        self.id = args.get("id")
        self.uid = args.get("uid")
        self.enabled = args.get("enabled")
        self.message = args.get("message")

    def dict_trans(self, **args):
        self.enabled = args.get("enabled")
        self.message = args.get("message")

    def set_id(self, id: str):
        self.id = id

    def set_uid(self, uid: int):
        self.uid = uid

    def enable(self):
        self.enabled = True

    def disable(self):
        self.enabled = False

    def add_atall(self):
        self.message = self._message_atall

    def del_atall(self):
        self.message = self._message_default

    def set_message(self, message: str = ""):
        if message:
            self.message = message
        else:
            self.message = self._message_default

    def mysql_insert_query(self) -> str:
        return f"INSERT INTO `{self.mysql_name}` (`id`, `uid`, `enabled`, `message`) VALUES ('{self.id}', {self.uid}, {int(self.enabled)}, '{self.message}')"

    def mysql_delete_query(self) -> str:
        return f"DELETE FROM `{self.mysql_name}` WHERE `id` = '{self.id}'"

    def mysql_update_query(self) -> str:
        return f"UPDATE `{self.mysql_name}` SET `uid` = {self.uid}, `enabled` = {int(self.enabled)}, `message` = '{self.message}' WHERE `id` = '{self.id}'"

    def mysql_get_by_id_query(self, id="") -> str:
        if id == "":
            id = self.id
        return f"SELECT * FROM `{self.mysql_name}` WHERE `id` = '{id}'"


class ReportMysql:
    id: str = ""
    uid: int = 0
    enabled: bool = False
    logo: str = ""
    logo_base64: str = ""
    time: bool = False  # 直播时长
    fans_change: bool = False  # 粉丝变动
    fans_medal_change: bool = False  # 粉丝勋章变动
    guard_change: bool = False  # 大航海变动
    danmu: bool = False  # 弹幕数据
    box: bool = False  # 盲盒数据
    gift: bool = False  # 礼物数据
    sc: bool = False  # SC数据
    guard: bool = False  # 大航海数据
    danmu_ranking: int = 0  # 弹幕榜
    box_ranking: int = 0  # 盲盒榜
    box_profit_ranking: int = 0  # 盲盒盈亏榜
    gift_ranking: int = 0  # 礼物榜
    sc_ranking: int = 0  # SC 榜
    guard_list: bool = False  # 开通大航海名单
    box_profit_diagram: bool = False  # 盲盒盈亏折线图
    danmu_diagram: bool = False  # 弹幕互动曲线图
    box_diagram: bool = False  # 盲盒互动曲线图
    gift_diagram: bool = False  # 礼物互动曲线图
    sc_diagram: bool = False  # SC 互动曲线图
    guard_diagram: bool = False  # 大航海互动曲线图
    danmu_cloud: bool = False  # 弹幕词云

    mysql_name = "live_report"

    def __init__(self, uid: int):
        self.uid = uid

    def dict_init(self, **args):
        self.id = args.get("id")
        self.uid = args.get("uid")
        self.enabled = args.get("enabled")
        self.logo = args.get("logo")
        self.logo_base64 = args.get("logo_base64")
        self.time = args.get("time")
        self.fans_change = args.get("fans_change")
        self.fans_medal_change = args.get("fans_medal_change")
        self.guard_change = args.get("guard_change")
        self.danmu = args.get("danmu")
        self.box = args.get("box")
        self.gift = args.get("gift")
        self.sc = args.get("sc")
        self.guard = args.get("guard")
        self.danmu_ranking = args.get("danmu_ranking")
        self.box_ranking = args.get("box_ranking")
        self.box_profit_ranking = args.get("box_profit_ranking")
        self.gift_ranking = args.get("gift_ranking")
        self.sc_ranking = args.get("sc_ranking")
        self.guard_list = args.get("guard_list")
        self.box_profit_diagram = args.get("box_profit_diagram")
        self.gift_diagram = args.get("gift_diagram")
        self.sc_diagram = args.get("sc_diagram")
        self.guard_diagram = args.get("guard_diagram")
        self.danmu_cloud = args.get("danmu_cloud")

    def dict_trans(self, **args):
        self.enabled = args.get("enabled")
        self.logo = args.get("logo")
        if args.get("logo_base64") is not None:
            self.logo_base64 = args.get("logo_base64")
        self.time = args.get("time")
        self.fans_change = args.get("fans_change")
        self.fans_medal_change = args.get("fans_medal_change")
        self.guard_change = args.get("guard_change")
        self.danmu = args.get("danmu")
        self.box = args.get("box")
        self.gift = args.get("gift")
        self.sc = args.get("sc")
        self.guard = args.get("guard")
        self.danmu_ranking = args.get("danmu_ranking")
        self.box_ranking = args.get("box_ranking")
        self.box_profit_ranking = args.get("box_profit_ranking")
        self.gift_ranking = args.get("gift_ranking")
        self.sc_ranking = args.get("sc_ranking")
        self.guard_list = args.get("guard_list")
        self.box_profit_diagram = args.get("box_profit_diagram")
        self.gift_diagram = args.get("gift_diagram")
        self.sc_diagram = args.get("sc_diagram")
        self.guard_diagram = args.get("guard_diagram")
        self.danmu_cloud = args.get("danmu_cloud")

    def set_id(self, id: str):
        self.id = id

    def set_uid(self, uid: int):
        self.uid = uid

    def enable(self):
        self.enabled = True

    def disable(self):
        self.enabled = False

    def set_time_on(self):
        self.time = True  # on
        self.fans_change = False
        self.fans_medal_change = False
        self.guard_change = False
        self.danmu = False
        self.box = False
        self.gift = False
        self.sc = False
        self.guard = False
        self.danmu_ranking = 0
        self.box_ranking = 0
        self.box_profit_ranking = 0
        self.gift_ranking = 0
        self.sc_ranking = 0
        self.guard_list = False
        self.box_profit_diagram = False
        self.danmu_diagram = False
        self.box_diagram = False
        self.gift_diagram = False
        self.sc_diagram = False
        self.guard_diagram = False
        self.danmu_cloud = False

    def set_danmucloud_on(self):
        self.time = True  # on
        self.fans_change = False
        self.fans_medal_change = False
        self.guard_change = False
        self.danmu = False
        self.box = False
        self.gift = False
        self.sc = False
        self.guard = False
        self.danmu_ranking = 0
        self.box_ranking = 0
        self.box_profit_ranking = 0
        self.gift_ranking = 0
        self.sc_ranking = 0
        self.guard_list = False
        self.box_profit_diagram = False
        self.danmu_diagram = False
        self.box_diagram = False
        self.gift_diagram = False
        self.sc_diagram = False
        self.guard_diagram = False
        self.danmu_cloud = True  # on

    def set_logo(self, logo: str):
        self.logo_base64 = logo
        if len(logo) > 0:
            self.logo = ""

    def clear_logo(self):
        self.logo_base64 = ""
        self.logo = ""

    def set_all_on(self):
        self.time = True
        self.fans_change = True
        self.fans_medal_change = True
        self.guard_change = True
        self.danmu = True
        self.box = True
        self.gift = True
        self.sc = True
        self.guard = True
        self.danmu_ranking = 10
        self.box_ranking = 10
        self.box_profit_ranking = 10
        self.gift_ranking = 10
        self.sc_ranking = 10
        self.guard_list = True
        self.box_profit_diagram = True
        self.danmu_diagram = True
        self.box_diagram = True
        self.gift_diagram = True
        self.sc_diagram = True
        self.guard_diagram = True
        self.danmu_cloud = True

    def config(self, input_arg: str, input_str: str):
        input_str = input_str.lower()
        if input_str == "on" or input_str == "enable" or input_str == "true" or input_str == "开启":
            input_type = bool
            value = True
        elif input_str == "off" or input_str == "disable" or input_str == "false" or input_str == "关闭":
            input_type = bool
            value = False
        elif input_str.isdigit() and 0 <= int(input_str) <= 10:
            input_type = int
            value = int(input_str)
        else:
            input_type = None
            return False
        conf_dict = {
            "time": lambda v=value: (setattr(self, 'time', v) or True) if input_type is bool else False,
            "直播时长": lambda v=value: (setattr(self, 'time', v) or True) if input_type is bool else False,
            "fans_change": lambda v=value: (setattr(self, 'fans_change', v) or True) if input_type is bool else False,
            "粉丝变动": lambda v=value: (setattr(self, 'fans_change', v) or True) if input_type is bool else False,
            "fans_medal_change": lambda v=value: (
                        setattr(self, 'fans_medal_change', v) or True) if input_type is bool else False,
            "粉丝勋章变动": lambda v=value: (
                        setattr(self, 'fans_medal_change', v) or True) if input_type is bool else False,
            "guard_change": lambda v=value: (setattr(self, 'guard_change', v) or True) if input_type is bool else False,
            "大航海变动": lambda v=value: (setattr(self, 'guard_change', v) or True) if input_type is bool else False,
            "danmu": lambda v=value: (setattr(self, 'danmu', v) or True) if input_type is bool else False,
            "弹幕数据": lambda v=value: (setattr(self, 'danmu', v) or True) if input_type is bool else False,
            "box": lambda v=value: (setattr(self, 'box', v) or True) if input_type is bool else False,
            "盲盒数据": lambda v=value: (setattr(self, 'box', v) or True) if input_type is bool else False,
            "gift": lambda v=value: (setattr(self, 'gift', v) or True) if input_type is bool else False,
            "礼物数据": lambda v=value: (setattr(self, 'gift', v) or True) if input_type is bool else False,
            "sc": lambda v=value: (setattr(self, 'sc', v) or True) if input_type is bool else False,
            "sc数据": lambda v=value: (setattr(self, 'sc', v) or True) if input_type is bool else False,
            "SC数据": lambda v=value: (setattr(self, 'sc', v) or True) if input_type is bool else False,
            "SC 数据": lambda v=value: (setattr(self, 'sc', v) or True) if input_type is bool else False,
            "guard": lambda v=value: (setattr(self, 'guard', v) or True) if input_type is bool else False,
            "大航海数据": lambda v=value: (setattr(self, 'guard', v) or True) if input_type is bool else False,
            "danmu_ranking": lambda v=value: (
                        setattr(self, 'danmu_ranking', v) or True) if input_type is int else False,
            "弹幕榜": lambda v=value: (setattr(self, 'danmu_ranking', v) or True) if input_type is int else False,
            "box_ranking": lambda v=value: (setattr(self, 'box_ranking', v) or True) if input_type is int else False,
            "盲盒榜": lambda v=value: (setattr(self, 'box_ranking', v) or True) if input_type is int else False,
            "box_profit_ranking": lambda v=value: (
                        setattr(self, 'box_profit_ranking', v) or True) if input_type is int else False,
            "盲盒盈亏榜": lambda v=value: (
                        setattr(self, 'box_profit_ranking', v) or True) if input_type is int else False,
            "gift_ranking": lambda v=value: (setattr(self, 'gift_ranking', v) or True) if input_type is int else False,
            "礼物榜": lambda v=value: (setattr(self, 'gift_ranking', v) or True) if input_type is int else False,
            "sc_ranking": lambda v=value: (setattr(self, 'sc_ranking', v) or True) if input_type is int else False,
            "sc榜": lambda v=value: (setattr(self, 'sc_ranking', v) or True) if input_type is int else False,
            "SC榜": lambda v=value: (setattr(self, 'sc_ranking', v) or True) if input_type is int else False,
            "guard_list": lambda v=value: (setattr(self, 'guard_list', v) or True) if input_type is bool else False,
            "开通大航海名单": lambda v=value: (setattr(self, 'guard_list', v) or True) if input_type is bool else False,
            "box_profit_diagram": lambda v=value: (
                        setattr(self, 'box_profit_diagram', v) or True) if input_type is bool else False,
            "盲盒盈亏折线图": lambda v=value: (
                        setattr(self, 'box_profit_diagram', v) or True) if input_type is bool else False,
            "danmu_diagram": lambda v=value: (
                        setattr(self, 'danmu_diagram', v) or True) if input_type is bool else False,
            "弹幕互动曲线图": lambda v=value: (
                        setattr(self, 'danmu_diagram', v) or True) if input_type is bool else False,
            "box_diagram": lambda v=value: (setattr(self, 'box_diagram', v) or True) if input_type is bool else False,
            "盲盒互动曲线图": lambda v=value: (
                        setattr(self, 'box_diagram', v) or True) if input_type is bool else False,
            "gift_diagram": lambda v=value: (setattr(self, 'gift_diagram', v) or True) if input_type is bool else False,
            "礼物互动曲线图": lambda v=value: (
                        setattr(self, 'gift_diagram', v) or True) if input_type is bool else False,
            "sc_diagram": lambda v=value: (setattr(self, 'sc_diagram', v) or True) if input_type is bool else False,
            "sc互动曲线图": lambda v=value: (setattr(self, 'sc_diagram', v) or True) if input_type is bool else False,
            "SC互动曲线图": lambda v=value: (setattr(self, 'sc_diagram', v) or True) if input_type is bool else False,
            "SC 互动曲线图": lambda v=value: (setattr(self, 'sc_diagram', v) or True) if input_type is bool else False,
            "guard_diagram": lambda v=value: (
                        setattr(self, 'guard_diagram', v) or True) if input_type is bool else False,
            "大航海互动曲线图": lambda v=value: (
                        setattr(self, 'guard_diagram', v) or True) if input_type is bool else False,
            "danmu_cloud": lambda v=value: (setattr(self, 'danmu_cloud', v) or True) if input_type is bool else False,
            "弹幕词云": lambda v=value: (setattr(self, 'danmu_cloud', v) or True) if input_type is bool else False,
        }
        func = conf_dict.get(input_arg, lambda v=value: False)
        return func()

    def mysql_insert_query(self) -> str:
        return str(
            f"INSERT INTO `{self.mysql_name}` (`id`, `uid`, `enabled`, `logo`, `logo_base64`, `time`, `fans_change`, `fans_medal_change`, `guard_change`, "
            f"`danmu`, `box`, `gift`, `sc`, `guard`, "
            f"`danmu_ranking`, `box_ranking`, `box_profit_ranking`, `gift_ranking`, `sc_ranking`, "
            f"`guard_list`, `box_profit_diagram`, `danmu_diagram`, `box_diagram`, `gift_diagram`, "
            f"`sc_diagram`, `guard_diagram`, `danmu_cloud`) VALUES ('{self.id}', {self.uid}, {int(self.enabled)}, '{self.logo}', '{self.logo_base64}', {int(self.time)}, "
            f"{int(self.fans_change)}, {int(self.fans_medal_change)}, {int(self.guard_change)}, {int(self.danmu)}, {int(self.box)}, {int(self.gift)}, "
            f"{int(self.sc)}, {int(self.guard)}, {self.danmu_ranking}, {self.box_ranking}, {self.box_profit_ranking}, {self.gift_ranking}, {self.sc_ranking}, "
            f"{int(self.guard_list)}, {int(self.box_profit_diagram)}, {int(self.danmu_diagram)}, {int(self.box_diagram)}, {int(self.gift_diagram)}, "
            f"{int(self.sc_diagram)}, {int(self.guard_diagram)}, {int(self.danmu_cloud)})")

    def mysql_delete_query(self) -> str:
        return f"DELETE FROM `{self.mysql_name}` WHERE id = '{self.id}'"

    def mysql_update_query(self) -> str:
        return str(
            f"UPDATE `{self.mysql_name}` SET `uid` = {self.uid}, `enabled` = {int(self.enabled)}, `logo` = '{self.logo}', `logo_base64` = '{self.logo_base64}', "
            f"`time` = {int(self.time)}, `fans_change` = {int(self.fans_change)}, `fans_medal_change` = {int(self.fans_medal_change)}, `guard_change` = {int(self.guard_change)}, "
            f"`danmu` = {int(self.danmu)}, `box` = {int(self.box)}, `gift` = {int(self.gift)}, `sc` = {int(self.sc)}, `guard` = {int(self.guard)}, "
            f"`danmu_ranking` = {self.danmu_ranking}, `box_ranking` = {self.box_ranking}, `box_profit_ranking` = {self.box_profit_ranking}, `gift_ranking` = {self.gift_ranking},"
            f"`sc_ranking` = {self.sc_ranking}, `guard_list` = {int(self.guard_list)}, `box_profit_diagram` = {int(self.box_profit_diagram)}, `danmu_diagram` = {int(self.danmu_diagram)}, "
            f"`box_diagram` = {int(self.box_diagram)}, `gift_diagram` = {int(self.gift_diagram)}, `sc_diagram` = {int(self.sc_diagram)}, `guard_diagram` = {int(self.guard_diagram)}, "
            f"`danmu_cloud` = {int(self.danmu_cloud)} WHERE `id` = '{self.id}'")

    def mysql_get_by_id_query(self, id="") -> str:
        if id == "":
            id = self.id
        return f"SELECT * FROM `{self.mysql_name}` WHERE `id` = '{id}'"


class TargetMysql:
    id: str = ""
    uid: int = 0
    num: int = 0
    type: PushType = PushType.Group
    uname: str = ""
    room_id: int = 0

    mysql_name = "targets"

    def __init__(self, uid: int, num: int, type: PushType = PushType.Group):
        self.uid = uid
        self.num = num
        if isinstance(type, PushType):
            self.type = type
        else:
            self.type = PushType(type)

    def dict_init(self, **args):
        self.id = args.get("id")
        self.uid = args.get("uid")
        self.num = args.get("num")
        self.type = PushType(args.get("type"))
        self.uname = args.get("uname")
        self.room_id = args.get("room_id")

    def dict_trans(self, **args):
        self.num = args.get("id")
        self.type = PushType(args.get("type"))

    def set_id(self, id: str):
        self.id = id

    def set_uid(self, uid: int):
        self.uid = uid

    async def set_uname_and_room_id(self):
        self.uname, self.room_id = await select_uname_and_room_id(self.uid)

    def get_uname_and_room_id(self):
        return self.uname, self.room_id

    def mysql_insert_query(self) -> str:
        return f"INSERT INTO `{self.mysql_name}` (`id`, `uid`, `num`, `type`, `uname`, `room_id`) VALUES ('{self.id}', {self.uid}, {self.num}, {self.type.value}, '{self.uname}', {self.room_id})"

    def mysql_delete_query(self) -> str:
        return f"DELETE FROM `{self.mysql_name}` WHERE `id` = '{self.id}'"

    def mysql_get_by_uid_and_num_query(self) -> str:
        return f"SELECT * FROM `{self.mysql_name}` WHERE `uid` = {self.uid} and `num` = {self.num} and `type` = {self.type.value}"

    def mysql_get_by_uid_query(self) -> str:
        return f"SELECT * FROM `{self.mysql_name}` WHERE `uid` = {self.uid}"


class ObjMysql:
    bot: Optional[BotMysql] = None
    target: Optional[TargetMysql] = None
    dynamic: Optional[DynamicMysql] = None
    live_on: Optional[LiveOnMysql] = None
    live_off: Optional[LiveOffMysql] = None
    report: Optional[ReportMysql] = None

    datasource: MySQLDataSource = None
    sql_str: List[str] = []

    target_create_flag = False

    def init_obj(self):
        self.bot = None
        self.target = None
        self.dynamic = None
        self.live_on = None
        self.live_off = None
        self.report = None
        self.datasource = Ariadne.options["StarBotDataSource"]
        self.sql_str = []
        self.target_create_flag = False

    def __init__(self, mysql: Optional[MySQLDataSource] = None):
        self.init_obj()
        if mysql is not None:
            self.datasource = mysql

    def get_target_uid(self):
        return self.bot.get_uid()

    async def connect(self):
        if not self.datasource._MySQLDataSource__pool:
            await self.datasource._MySQLDataSource__connect()

    async def query(self, sql_str):
        # logger.info(f"执行sql语句:{sql_str};")
        return await self.datasource._MySQLDataSource__query(sql_str + ";")

    async def query_batch(self, str_list):
        sql_str = ";".join(str_list) + ";"
        # sql_debug_str = '\n'.join(str_list)
        # logger.info(f"执行sql语句:{sql_debug_str}")
        return await self.datasource._MySQLDataSource__query(sql_str)

    async def reload(self, uid):
        up = self.get_up_by_uid(uid)
        if up is None:
            raise DataSourceException(f"不存在的 UID: {uid}")
        # 强制刷新内存中uname以解决内存中昵称不会同步更新的问题
        if self.target is not None:
            up.uname, _ = self.target.get_uname_and_room_id()
        else:
            up.uname, _ = await select_uname_and_room_id(uid)
        await self.datasource.reload_targets(up)

    async def remove_up(self, uid):
        up = self.get_up_by_uid(uid)
        if up is None:
            raise DataSourceException(f"不存在的 UID: {uid}")
        await up.disconnect()
        self.datasource.remove_up(uid)

    async def load_new(self, uid):
        await self.datasource.load_new(uid)

    def get_uid_list(self) -> List[int]:
        return self.datasource.get_uid_list()

    def get_all_groups_and_friends(self):
        ups: List[Up] = self.datasource.get_up_list()
        group_set = set()
        friend_set = set()
        for up in ups:
            for target in up.targets:
                if target.type == PushType.Group:
                    group_set.add(target.id)
                if target.type == PushType.Friend:
                    friend_set.add(target.id)
        return group_set, friend_set

    def get_up_list_by_num_origin(self, num: int, push_type: PushType = PushType.Group) -> List:
        ups: List[Up] = self.datasource.get_ups_by_target(num, push_type)
        return ups

    async def get_up_list_with_pic_struct(self) -> List:
        ups: List[Up] = self.datasource.get_up_list()
        up_list = []
        target_map = {}
        for up in ups:
            for target in up.targets:
                push_target = f"{'群' if target.type == PushType.Group else '好友'}({target.id})"
                if not target_map.get(push_target):
                    target_map[push_target] = []
                push_type = []
                living_flag = False
                if target.dynamic_update.enabled:
                    push_type.append("news")
                if target.live_on.enabled:
                    push_type.append("live_on")
                    if up.room_id and await redis.get_live_status(up.room_id) == 1:
                        living_flag = True
                if target.live_off.enabled:
                    push_type.append("live_off")
                uname_uid = f"{up.uname} {up.uid} {'/'.join(push_type)}"
                if living_flag:
                    uname_uid = uname_uid + " ※直播中※"
                target_map[push_target].append(uname_uid)
        for t, u in target_map.items():
            up_target = {"section": t, "context": []}
            for target in u:
                up_target["context"].append(target)
            up_list.append(up_target)
        return up_list

    async def get_ups_by_target_with_pic_struct(self, num: int, p_type: PushType = PushType.Group) -> List:
        ups: List[Up] = self.datasource.get_ups_by_target(num, p_type)
        up_list = []
        for up in ups:
            push_type = []
            living_flag = False
            for target in up.targets:
                if target.id == num and target.type == p_type:
                    if target.dynamic_update.enabled:
                        push_type.append("news")
                    if target.live_on.enabled:
                        push_type.append("live_on")
                        if up.room_id and await redis.get_live_status(up.room_id) == 1:
                            living_flag = True
                    if target.live_off.enabled:
                        push_type.append("live_off")
                    break
            uname_uid = f"{up.uname} {up.uid} {'/'.join(push_type)}"
            if living_flag:
                uname_uid = uname_uid + " ※直播中※"
            up_list.append(uname_uid)
        return up_list

    def get_ups_by_targets(self, friend_set: set, group_set: set) -> List:
        up_list = []
        for f in friend_set:
            ups: List[Up] = self.datasource.get_ups_by_target(f, PushType.Friend)
            for up in ups:
                up_list.append((up.uid, f))
        for g in group_set:
            ups: List[Up] = self.datasource.get_ups_by_target(g, PushType.Group)
            for up in ups:
                up_list.append((up.uid, g))
        return up_list

    def get_up_by_uid(self, uid: int) -> Optional[Up]:
        ups: List[Up] = self.datasource.get_up_list()
        for up in ups:
            if f"{up.uid}" == f"{uid}":  # 用int值直接比较无法得到预期结果，通过转换为字符串比较规避问题，根因暂未找到
                return up
        return None

    def get_target_uname_and_roomid(self):
        return self.target.get_uname_and_room_id()

    def set_message_inner(self, message_type: str, message: str = ""):
        message = message.replace('\\', '\\\\')
        if message_type == "news":
            self.dynamic.set_message(message)
            return
        if message_type == "live_on":
            self.live_on.set_message(message)
            return
        if message_type == "live_off":
            self.live_off.set_message(message)
            return
        return

    # 对应enabled字段
    def set_report_type(self, type: str):
        if type == "news":
            self.dynamic.enable()
            self.live_on.disable()
            self.live_off.disable()
            self.report.disable()
            return
        if type == "live":
            self.dynamic.disable()
            self.live_on.enable()
            self.live_off.enable()
            self.report.enable()
            return
        if type == "live_on":
            self.dynamic.disable()
            self.live_on.enable()
            self.live_off.disable()
            self.report.disable()
            return
        if type == "all":
            self.dynamic.enable()
            self.live_on.enable()
            self.live_off.enable()
            self.report.enable()
            return
        return

    # 对应message字段atall标记
    def set_report_message(self, atall: str):
        if atall == "news":
            self.dynamic.add_atall()
            self.live_on.del_atall()
            return
        if atall == "live":
            self.dynamic.del_atall()
            self.live_on.add_atall()
            return
        if atall == "all":
            self.dynamic.add_atall()
            self.live_on.add_atall()
            return
        if atall == "no":
            self.dynamic.del_atall()
            self.live_on.del_atall()
            return
        return

    # 对应report对象
    def set_report_inner(self, report: str):
        if report == "time":
            self.report.set_time_on()
            return
        if report == "danmu":
            self.report.set_danmucloud_on()
            return
        if report == "all":
            self.report.set_all_on()
            return
        return

    def set_report_obj(self, type: str, atall: str, report: str):
        self.set_report_type(type)
        self.set_report_message(atall)
        self.set_report_inner(report)

    async def set_bot_id(self):
        bots = await self.query(self.bot.mysql_get_by_bot_and_uid_query())
        if len(bots) > 0:
            self.bot.set_id(bots[0].get("id"))
        else:
            self.bot.set_id(0)

    def set_report_logo(self, logo: str):
        self.report.set_logo(logo)

    def clear_report_logo(self):
        self.report.clear_logo()

    def config_report(self, input_arg: str, input_str: str):
        return self.report.config(input_arg, input_str)

    async def query_targets(self):
        target = await self.query(self.target.mysql_get_by_uid_and_num_query())
        if len(target) > 0:
            id = target[0].get("id")
            self.target.dict_init(**target[0])
            dynamic = await self.query(self.dynamic.mysql_get_by_id_query(id))
            live_on = await self.query(self.live_on.mysql_get_by_id_query(id))
            live_off = await self.query(self.live_off.mysql_get_by_id_query(id))
            report = await self.query(self.report.mysql_get_by_id_query(id))
            self.dynamic.dict_init(**dynamic[0])
            self.live_on.dict_init(**live_on[0])
            self.live_off.dict_init(**live_off[0])
            self.report.dict_init(**report[0])
        else:
            id = uuid.uuid1()
            self.target_create_flag = True
            self.target.set_id(id)
            self.dynamic.set_id(id)
            self.live_on.set_id(id)
            self.live_off.set_id(id)
            self.report.set_id(id)

    async def init_target(self, bot: int, uid: int, num: int, type: PushType = PushType.Group):
        await self.connect()
        self.bot = BotMysql(bot, uid)
        await self.set_bot_id()
        self.target = TargetMysql(uid, num, type)
        self.dynamic = DynamicMysql(uid)
        self.live_on = LiveOnMysql(uid)
        self.live_off = LiveOffMysql(uid)
        self.report = ReportMysql(uid)
        await self.target.set_uname_and_room_id()
        await self.query_targets()

    async def trans_targets(self, bot, uid, num, target):
        dynamic = target.get("dynamic_update")
        live_on = target.get("live_on")
        live_off = target.get("live_off")
        report = target.get("live_report")
        type = target.get("type")
        await self.connect()
        self.bot = BotMysql(bot, uid)
        await self.set_bot_id()
        self.target = TargetMysql(uid, num, type)
        self.dynamic = DynamicMysql(uid)
        self.live_on = LiveOnMysql(uid)
        self.live_off = LiveOffMysql(uid)
        self.report = ReportMysql(uid)
        await self.target.set_uname_and_room_id()
        target_mysql = await self.query(self.target.mysql_get_by_uid_and_num_query())
        if len(target_mysql) > 0:
            id = target_mysql[0].get("id")
        else:
            id = uuid.uuid1()  # 使用uuid1确保表主键不重复
            self.target_create_flag = True
        self.target.dict_trans(**target)
        self.target.set_id(id)
        self.target.set_uid(uid)
        self.dynamic.dict_trans(**dynamic)
        self.dynamic.set_id(id)
        self.dynamic.set_uid(uid)
        self.live_on.dict_trans(**live_on)
        self.live_on.set_id(id)
        self.live_on.set_uid(uid)
        self.live_off.dict_trans(**live_off)
        self.live_off.set_id(id)
        self.live_off.set_uid(uid)
        self.report.dict_trans(**report)
        self.report.set_id(id)
        self.report.set_uid(uid)

    async def check_uid_exist(self, uid: int, num: int, type: PushType = PushType.Group):
        target = TargetMysql(uid, num, type)
        target_mysql = await self.query(target.mysql_get_by_uid_and_num_query())
        if len(target_mysql) == 0:
            return False
        return True

    async def check_uid_exist_with_all(self, uid: int):
        target = TargetMysql(uid, 0, PushType.Group)
        target_mysql = await self.query(target.mysql_get_by_uid_query())
        if len(target_mysql) == 0:
            return False
        return True

    async def clean_describe(self, bot: int, num: int, push_type: PushType = PushType.Group):
        ups: List[Up] = self.get_up_list_by_num_origin(num, push_type)
        for up in ups:
            await self.init_target(bot, up.uid, num, push_type)
            await self.delete()

    # insert and update
    async def save(self):
        uid: int = self.get_target_uid()
        if self.bot.get_id() == 0:
            self.sql_str.append(self.bot.mysql_insert_query())
        if self.target_create_flag is True:
            self.sql_str.append(self.target.mysql_insert_query())
            self.sql_str.append(self.dynamic.mysql_insert_query())
            self.sql_str.append(self.live_on.mysql_insert_query())
            self.sql_str.append(self.live_off.mysql_insert_query())
            self.sql_str.append(self.report.mysql_insert_query())
        else:
            self.sql_str.append(self.dynamic.mysql_update_query())
            self.sql_str.append(self.live_on.mysql_update_query())
            self.sql_str.append(self.live_off.mysql_update_query())
            self.sql_str.append(self.report.mysql_update_query())
        await self.query_batch(self.sql_str)
        if self.bot.get_id() == 0:
            await self.load_new(uid)
        else:
            await self.reload(uid)

    async def trans_save(self):
        if self.bot.get_id() == 0:
            self.sql_str.append(self.bot.mysql_insert_query())
        if self.target_create_flag is True:
            self.sql_str.append(self.target.mysql_insert_query())
            self.sql_str.append(self.dynamic.mysql_insert_query())
            self.sql_str.append(self.live_on.mysql_insert_query())
            self.sql_str.append(self.live_off.mysql_insert_query())
            self.sql_str.append(self.report.mysql_insert_query())
            await self.query_batch(self.sql_str)
        else:
            self.sql_str.append(self.dynamic.mysql_update_query())
            self.sql_str.append(self.live_on.mysql_update_query())
            self.sql_str.append(self.live_off.mysql_update_query())
            self.sql_str.append(self.report.mysql_update_query())
            await self.query_batch(self.sql_str)

    # delete
    async def delete(self):
        uid: int = self.get_target_uid()
        self.sql_str.append(self.target.mysql_delete_query())
        self.sql_str.append(self.dynamic.mysql_delete_query())
        self.sql_str.append(self.live_on.mysql_delete_query())
        self.sql_str.append(self.live_off.mysql_delete_query())
        self.sql_str.append(self.report.mysql_delete_query())
        targets = await self.query(self.target.mysql_get_by_uid_query())
        if targets is not None and len(targets) <= 1:
            self.sql_str.append(self.bot.mysql_delete_query())
            await self.query_batch(self.sql_str)
            await self.remove_up(uid)
            uname, room_id = self.get_target_uname_and_roomid()
            try:
                unfollow_user = User(uid, get_credential())
                await unfollow_user.modify_relation(RelationType.UNSUBSCRIBE)
                logger.success(f"自动取消关注成功 {uname} (UID: {uid} 房间号: {room_id})")
            except ResponseCodeException as e:
                if e.code == 22115 or e.code == 22007:
                    logger.warning(f"读取登录账号的关注列表失败, 请检查登录凭据是否已失效, 错误信息: {e.msg}")
            except Exception as e:
                logger.exception(f"取消关注异常 {uid = }\n", e)
        else:
            await self.query_batch(self.sql_str)
            await self.reload(uid)
