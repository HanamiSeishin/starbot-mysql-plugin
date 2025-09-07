import asyncio
from typing import List, Optional, Union
from creart import create
from graia.ariadne import Ariadne
from graia.ariadne.event.message import FriendMessage, GroupMessage
from graia.ariadne.message.chain import MessageChain
from graia.ariadne.message.element import At, Image, AtAll, Plain
from graia.ariadne.message.parser.twilight import Twilight, FullMatch, UnionMatch, ElementMatch, ArgumentMatch, \
    ResultValue, ParamMatch, SpacePolicy, WildcardMatch
from graia.ariadne.model import Friend, Group, Member, MemberPerm
from graia.broadcast import PropagationCancelled
from graia.saya import Channel
from graia.saya.builtins.broadcast import ListenerSchema
from graia.broadcast.interrupt import InterruptControl
from graia.broadcast.interrupt.waiter import Waiter
from loguru import logger

from starbot.utils import config
from starbot.core.model import PushType
from starbot.core.bot import StarBot

from .mysql_utils import ObjMysql, check_not_mysql_datasource, check_mysql_datasource, create_auto_follow_task, \
    draw_image_pic, draw_pic, check_at_object, get_message_help, select_uname_and_room_id, get_logger_prefix, \
    default_help, check_bot_mode_public, set_bot_mode_private, set_bot_mode_public, element_get_bytes, \
    append_report_help
from .mysql_trans import datasource_trans_to_mysql, datasource_trans_to_json

prefix = config.get("COMMAND_PREFIX")
master_qq = config.get("MASTER_QQ")

channel = Channel.current()
inc = create(InterruptControl)

add_describe = ["添加订阅", "新增订阅", "watch"]
delete_describe = ["删除订阅", "取消订阅", "unwatch"]
list_describe = ["查询订阅", "订阅内容", "list"]
reload_uid = ["重载订阅", "刷新订阅", "reloaduid"]
add_logo = ["设置立绘", "setlogo"]
clear_logo = ["清除立绘", "clearlogo"]
set_message = ["设置推送信息", "设置推送消息", "setmessage"]
set_report = ["设置直播报告", "设置推送报告", "setreport"]
quit_group = ["退出群聊", "退群", "quit"]
check_describe_abnormal = ["检测异常订阅", "checkabnormal"]
clear_describe_abnormal = ["清除异常订阅", "clearabnormal"]
trans_to_mysql = ["数据源转储", "datasourcetrans"]
save_json = ["数据源转存json"]
ping = ["ping"]
get_status = ["status"]
bot_mode = ["模式", "mode"]

help_cmd = ["订阅帮助", "帮助", "菜单", "功能", "命令", "指令", "help"]

# 由于Twilight自带的help生成器无法满足使用，例如无法分离管理员帮助和普通的私聊帮助，只能自定义help内容
describe_cmd = {
    help_cmd[0]: {
        "cmd": help_cmd,
        "describe_group": [f"{prefix}[{' | '.join(help_cmd)}]" if len(help_cmd) > 1 else f"{prefix}{help_cmd[0]}",
                           "可选参数：[-d | --default] 显示默认帮助",
                           "显示此帮助，默认帮助已被该插件覆盖",
                           f"示例: {prefix}{help_cmd[0]}"],
        "describe_friend": [f"{prefix}[{' | '.join(help_cmd)}]" if len(help_cmd) > 1 else f"{prefix}{help_cmd[0]}",
                            "可选参数：[-d | --default] 显示默认帮助",
                            "显示此帮助，默认帮助已被插件覆盖",
                            f"示例: {prefix}{help_cmd[0]}"],
        "describe_admin": [f"{prefix}[{' | '.join(help_cmd)}]" if len(help_cmd) > 1 else f"{prefix}{help_cmd[0]}",
                           "可选参数：[-d | --default] 显示默认帮助",
                           "显示此帮助，默认帮助已被插件覆盖",
                           f"示例: {prefix}{help_cmd[0]}"],
    },
    add_describe[0]: {
        "cmd": add_describe,
        "describe_group": [f"{prefix}[{' | '.join(add_describe)}] uid",
                           "可选参数：[-t | --type] [news | live | live_on | all] 订阅类型[动态，开播和下播，开播，全部推送(默认)]",
                           "可选参数：[-a | --atall] [news | live | all | no] at全体需要管理员权限[动态，开播，动态和开播，无(默认)]",
                           "可选参数：[-r | --report] [time | danmu | all] 直播报告内容[直播时长(默认)，直播时长和弹幕云词，全部信息]",
                           "注意：uid若已在本群订阅，则本次添加视为更新配置，为防止被滥用，该命令需要群管理员及以上权限可用",
                           "at全体受官方限制每日次数有限，请尽量减少开启该选项，如出现受限情况，请联系bot主人确认该情况",
                           f"示例: {prefix}{add_describe[0]} 2",
                           f"示例: {prefix}{add_describe[0]} 2 -t all -a no -r time"],
        "describe_friend": [f"{prefix}[{' | '.join(add_describe)}] uid",
                            "可选参数：[-t | --type] [news | live | live_on | all] 订阅类型[动态，开播和下播，开播，全部推送(默认)]",
                            "可选参数：[-r | --report] [time | danmu | all] 直播报告内容[直播时长(默认)，直播时长和弹幕云词，全部信息]",
                            "注意：uid若已被私聊订阅，则本次添加视为更新配置",
                            f"示例: {prefix}{add_describe[0]} 2",
                            f"示例: {prefix}{add_describe[0]} 2 -t all -r time"],
        "describe_admin": [f"{prefix}[{' | '.join(add_describe)}] uid",
                           "可选参数：[-g | --group] [group_num] 订阅发布群号",
                           "可选参数：[-t | --type] [news | live | live_on | all] 订阅类型[动态，开播和下播，开播，全部推送(默认)]",
                           "可选参数：[-a | --atall] [news | live | all | no] at全体[动态，开播，动态和开播，无(默认)]，对群监听有效",
                           "可选参数：[-r | --report] [time | danmu | all] 直播报告内容[直播时长(默认)，直播时长和弹幕云词，全部信息]",
                           "注意：uid若已被私聊订阅，则本次添加视为更新配置",
                           "at全体受官方限制每日次数有限，请尽量减少开启该选项，如出现受限情况，请联系bot主人确认该情况",
                           f"示例: {prefix}{add_describe[0]} 2 -g 456789",
                           f"示例: {prefix}{add_describe[0]} 2 -g 456789 -t all -a no -r time"]
    },
    delete_describe[0]: {
        "cmd": delete_describe,
        "describe_group": [f"{prefix}[{' | '.join(delete_describe)}] uid",
                           "为防止被滥用，该命令需要群管理员及以上权限可用",
                           f"示例: {prefix}{delete_describe[0]} 2"],
        "describe_friend": [f"{prefix}[{' | '.join(delete_describe)}] uid",
                            f"示例: {prefix}{delete_describe[0]} 2"],
        "describe_admin": [f"{prefix}[{' | '.join(delete_describe)}] uid",
                           "可选参数：[-g | --group] [group_num] 订阅所在群号",
                           f"示例: {prefix}{delete_describe[0]} 2 -g 456789"],
    },
    list_describe[0]: {
        "cmd": list_describe,
        "describe_group": [f"{prefix}[{' | '.join(list_describe)}]",
                           "可选参数：[-t | --text] 使用文字模式发送",
                           f"示例: {prefix}{list_describe[0]}"],
        "describe_friend": [f"{prefix}[{' | '.join(list_describe)}]",
                            "可选参数：[-t | --text] 使用文字模式发送",
                            "查询私聊订阅信息",
                            f"示例: {prefix}{list_describe[0]}"],
        "describe_admin": [f"{prefix}[{' | '.join(list_describe)}]",
                           "可选参数：[-t | --text] 使用文字模式发送",
                           "查询所有订阅信息",
                           f"示例: {prefix}{list_describe[0]}"],
    },
    reload_uid[0]: {
        "cmd": reload_uid,
        "describe_group": [],
        "describe_friend": [],
        "describe_admin": [f"{prefix}[{' | '.join(reload_uid)}] uid",
                           "从数据库重新载入订阅目标",
                           f"示例: {prefix}{reload_uid[0]} 2"],
    },
    add_logo[0]: {
        "cmd": add_logo,
        "describe_group": [f"{prefix}[{' | '.join(add_logo)}] uid",
                           "设置直播报告立绘，发送命令后根据命令交互完成设置，uid需要在该群被订阅才能成功",
                           "为防止被滥用，该命令需要群管理员及以上权限可用",
                           f"示例: {prefix}{add_logo[0]} 2"],
        "describe_friend": [f"{prefix}[{' | '.join(add_logo)}] uid",
                            "设置直播报告立绘，发送命令后根据命令交互完成设置，uid需要被订阅才能成功",
                            f"示例: {prefix}{add_logo[0]} 2"],
        "describe_admin": [f"{prefix}[{' | '.join(add_logo)}] uid",
                           "可选参数：[-g | --group] [group_num] 订阅所在群号",
                           "设置直播报告立绘，发送命令后根据命令交互完成设置，uid需要被订阅才能成功",
                           f"示例: {prefix}{add_logo[0]} -g 456789 2"]
    },
    clear_logo[0]: {
        "cmd": clear_logo,
        "describe_group": [f"{prefix}[{' | '.join(clear_logo)}] uid",
                           "清除直播报告立绘，uid需要在该群被订阅才能成功",
                           "为防止被滥用，该命令需要群管理员及以上权限可用",
                           f"示例: {prefix}{clear_logo[0]} 2"],
        "describe_friend": [f"{prefix}[{' | '.join(clear_logo)}] uid",
                            "清除直播报告立绘，uid需要被订阅才能成功",
                            f"示例: {prefix}{clear_logo[0]} 2"],
        "describe_admin": [f"{prefix}[{' | '.join(clear_logo)}] uid",
                           "可选参数：[-g | --group] [group_num] 订阅所在群号",
                           "清除直播报告立绘，uid需要被订阅才能成功",
                           f"示例: {prefix}{clear_logo[0]} -g 456789 2"]
    },
    set_message[0]: {
        "cmd": set_message,
        "describe_group": [f"{prefix}[{' | '.join(set_message)}] uid",
                           "必选参数：[-t | --type] [news | live_on | live_off]  类型[动态提醒，开播提醒，下播提醒]",
                           "设置动态提醒、开播提醒或下播提醒，uid需要在该群被订阅才能成功，需要管理员或群主权限",
                           f"示例: {prefix}{set_message[0]} 2 -t live_on"],
        "describe_friend": [f"{prefix}[{' | '.join(set_message)}] uid",
                            "必选参数：[-t | --type] [news | live_on | live_off]  类型[动态提醒，开播提醒，下播提醒]",
                            "设置动态提醒，开播提醒和下播提醒，uid需要被订阅才能成功",
                            f"示例: {prefix}{set_message[0]} 2 -t live_on"],
        "describe_admin": [f"{prefix}[{' | '.join(set_message)}] uid",
                           "可选参数：[-g | --group] [group_num] 订阅所在群号",
                           "必选参数：[-t | --type] [news | live_on | live_off]  类型[动态提醒，开播提醒，下播提醒]",
                           "设置动态提醒，开播提醒和下播提醒，uid需要被订阅才能成功",
                           f"示例: {prefix}{set_message[0]} -g 456789 2 -t live_on"]
    },
    set_report[0]: {
        "cmd": set_report,
        "describe_group": [f"{prefix}[{' | '.join(set_report)}] uid configuration value",
                           "可选参数：[-h | --help] 显示设置直播报告帮助，获取所有可配置参数及其可选值",
                           "设置直播报告参数，具体参数项可以根据推送姬网页配置项或者json字段设置",
                           "注意：uid需要在该群被订阅才能成功，为防止被滥用，该命令需要群管理员及以上权限可用",
                           f"示例: {prefix}{set_report[0]} 2 弹幕数据 关闭",
                           f"示例: {prefix}{set_report[0]} 2 盲盒榜 3"],
        "describe_friend": [f"{prefix}[{' | '.join(set_report)}] uid configuration value",
                            "可选参数：[-h | --help] 显示设置直播报告帮助，获取所有可配置参数及其可选值",
                            "设置直播报告参数，具体参数项可以根据推送姬网页配置项或者json字段设置，uid需要被订阅才能成功",
                            f"示例: {prefix}{set_report[0]} 2 弹幕数据 关闭",
                            f"示例: {prefix}{set_report[0]} 2 盲盒榜 3"],
        "describe_admin": [f"{prefix}[{' | '.join(set_report)}] uid configuration value",
                           "可选参数：[-g | --group] [group_num] 订阅所在群号",
                           "可选参数：[-h | --help] 显示设置直播报告帮助，获取所有可配置参数及其可选值",
                           "设置直播报告参数，具体参数项可以根据推送姬网页配置项或者json字段设置，uid需要被订阅才能成功",
                           f"示例: {prefix}{set_report[0]} 2 弹幕数据 关闭",
                           f"示例: {prefix}{set_report[0]} 2 盲盒榜 3 -g 123456"]
    },
    quit_group[0]: {
        "cmd": quit_group,
        "describe_group": [f"{prefix}[{' | '.join(quit_group)}]",
                           "bot退出当前群聊并清除订阅内容，为防止被滥用，该命令需要群主权限可用",
                           f"示例: {prefix}{quit_group[0]}"],
        "describe_friend": [],
        "describe_admin": [f"{prefix}[{' | '.join(quit_group)}] group_num",
                           "bot退出指定群聊并清除订阅内容",
                           f"示例: {prefix}{quit_group[0]} 123456"]
    },
    check_describe_abnormal[0]: {
        "cmd": check_describe_abnormal,
        "describe_group": [],
        "describe_friend": [],
        "describe_admin": [f"{prefix}[{' | '.join(check_describe_abnormal)}]",
                           "查询已经失效的订阅及其所在群聊(功能未验证，请谨慎使用)",
                           "注意：存在因为qqnt问题导致查询信息错误，请务必手动确认结果",
                           f"示例: {prefix}{check_describe_abnormal[0]}"]
    },
    clear_describe_abnormal[0]: {
        "cmd": clear_describe_abnormal,
        "describe_group": [],
        "describe_friend": [],
        "describe_admin": [f"{prefix}[{' | '.join(clear_describe_abnormal)}]",
                           "清除所有已经失效的订阅(功能未验证，请谨慎使用)",
                           f"示例: {prefix}{clear_describe_abnormal[0]}"]
    },
    trans_to_mysql[0]: {
        "cmd": trans_to_mysql,
        "describe_group": [],
        "describe_friend": [],
        "describe_admin": [f"{prefix}[{' | '.join(trans_to_mysql)}]" if len(trans_to_mysql) > 1 else f"{prefix}{trans_to_mysql[0]}",
                           "该命令可在其他数据源下使用，用处是将内存中的订阅信息插入mysql数据库中",
                           f"示例: {prefix}{trans_to_mysql[0]}"]
    },
    save_json[0]: {
        "cmd": save_json,
        "describe_group": [],
        "describe_friend": [],
        "describe_admin": [f"{prefix}[{' | '.join(save_json)}]" if len(save_json) > 1 else f"{prefix}{save_json[0]}",
                           "该命令在mysql数据源下使用，用处是将内存中的订阅信息转存为json数据源文件",
                           f"示例: {prefix}{save_json[0]}"]
    },
    ping[0]: {
        "cmd": ping,
        "describe_group": [],
        "describe_friend": [],
        "describe_admin": [f"{prefix}[{' | '.join(ping)}]" if len(ping) > 1 else f"{prefix}{ping[0]}",
                           "回复 pong",
                           f"示例: {prefix}{ping[0]}"]
    },
    get_status[0]: {
        "cmd": get_status,
        "describe_group": [],
        "describe_friend": [],
        "describe_admin": [f"{prefix}[{' | '.join(get_status)}]" if len(get_status) > 1 else f"{prefix}{get_status[0]}",
                           "展示当前starbot版本",
                           f"示例: {prefix}{get_status[0]}"]
    },
    bot_mode[0]: {
        "cmd": bot_mode,
        "describe_group": [],
        "describe_friend": [],
        "describe_admin": [f"{prefix}[{' | '.join(bot_mode)}] [mode]",
                           "若mode为公开，则设置为公开模式，若mode为私人，则设置为私人模式",
                           "若mode不填，则查询当前模式",
                           f"示例: {prefix}{bot_mode[0]}",
                           f"示例: {prefix}{bot_mode[0]} 私人"]
    }
}


@channel.use(
    ListenerSchema(
        listening_events=[GroupMessage],
        inline_dispatchers=[Twilight(
            ElementMatch(At, optional=True),
            FullMatch(prefix),
            "cmd" @ UnionMatch(*add_describe).space(SpacePolicy.FORCE),
            "uid" @ ParamMatch(),
            "type" @ ArgumentMatch("-t", "--type", type=str, choices=["news", "live", "live_on", "all"], default="all",
                                   optional=True),
            "atall" @ ArgumentMatch("-a", "--atall", type=str, choices=["news", "live", "all", "no"], default="no",
                                    optional=True),
            "report" @ ArgumentMatch("-r", "--report", type=str, choices=["time", "danmu", "all"], default="time",
                                     optional=True)
        )],
    )
)
async def _AddListenGroup(app: Ariadne, sender: Group, member: Member, message: MessageChain,
                          cmd: MessageChain = ResultValue(), uid: MessageChain = ResultValue(),
                          type: Optional[str] = ResultValue(), atall: Optional[str] = ResultValue(),
                          report: Optional[str] = ResultValue()):
    if check_not_mysql_datasource():
        return
    if check_at_object(app.account, message) is False:
        return
    uid = uid.display
    logger_prefix = get_logger_prefix(cmd.display, sender, member)
    if uid == "" or not uid.isdigit():
        logger.info(f"{logger_prefix} uid输入不合法({uid})")
        await app.send_message(sender, MessageChain(draw_pic(f"uid输入不合法({uid})，操作失败", width=800)))
        return
    uid = int(uid)
    group = sender.id
    bot = app.account
    logger.info(f"{logger_prefix} ({uid = }, {group = }, {type = }, {atall = }, {report = })")
    if master_qq == "" or f"{member.id}" != f"{master_qq}":
        person = await app.get_member(group, member.id)
        if person.permission < MemberPerm.Administrator:
            logger.info(f"{logger_prefix} 权限不足({member.id = }, {person.permission = })")
            await app.send_message(sender,
                                   MessageChain(draw_pic("权限不足，操作失败，仅群管理员和群主可操作", width=800)))
            return
    obj_mysql = ObjMysql()
    await obj_mysql.init_target(bot, uid, group)
    obj_mysql.set_report_obj(type, atall, report)
    await obj_mysql.save()
    uname, _ = obj_mysql.get_target_uname_and_roomid()
    create_auto_follow_task()
    logger.info(f"{logger_prefix} 成功 [{uname}]({uid})")
    await app.send_message(sender, MessageChain(draw_pic(f"{uname}(UID:{uid}){cmd.display}成功", width=800)))


@channel.use(
    ListenerSchema(
        listening_events=[FriendMessage],
        inline_dispatchers=[Twilight(
            ElementMatch(At, optional=True),
            FullMatch(prefix),
            "cmd" @ UnionMatch(*add_describe).space(SpacePolicy.FORCE),
            "uid" @ ParamMatch(),
            "group" @ ArgumentMatch("-g", "--group", type=int, default=0, optional=True),
            "type" @ ArgumentMatch("-t", "--type", type=str, choices=["news", "live", "live_on", "all"], default="all",
                                   optional=True),
            "atall" @ ArgumentMatch("-a", "--atall", type=str, choices=["news", "live", "all", "no"], default="no",
                                    optional=True),
            "report" @ ArgumentMatch("-r", "--report", type=str, choices=["time", "danmu", "all"], default="time",
                                     optional=True)
        )],
    )
)
async def _AddListenFriend(app: Ariadne, sender: Friend, cmd: MessageChain = ResultValue(),
                           uid: MessageChain = ResultValue(), group: Optional[int] = ResultValue(),
                           type: Optional[str] = ResultValue(), atall: Optional[str] = ResultValue(),
                           report: Optional[str] = ResultValue()):
    if check_not_mysql_datasource():
        return
    uid = uid.display
    logger_prefix = get_logger_prefix(cmd.display, sender)
    if uid == "" or not uid.isdigit():
        logger.info(f"{logger_prefix} uid输入不合法({uid})")
        await app.send_message(sender, MessageChain(draw_pic(f"uid输入不合法({uid})，操作失败", width=800)))
        return
    uid = int(uid)
    bot = app.account
    logger.info(f"{logger_prefix} ({uid = }, {group = }, {type = }, {atall = }, {report = })")
    if group != 0:
        if master_qq == "" or master_qq != sender.id:
            # 功能需要配置MASTER_QQ
            return
        group_check = await app.get_group(group)
        if group_check is None:
            logger.info(f"{logger_prefix} bot未加入群聊({group})")
            await app.send_message(sender, MessageChain(draw_pic(f"bot未加入群聊({group})，操作失败", width=800)))
            return
        source = group
        source_type = PushType.Group
        msg_prefix = f"群聊{group} "
    else:
        friend_check = await app.get_friend(sender.id)
        if friend_check is None:
            logger.info(f"{logger_prefix} bot未添加好友({sender.id})")
            await app.send_message(sender, MessageChain(draw_pic(f"bot未添加好友({sender.id})，操作失败", width=800)))
            return
        source = sender.id
        source_type = PushType.Friend
        msg_prefix = ""
        atall = "no"  # 好友监听不存在atall属性，直接覆写为no
    obj_mysql = ObjMysql()
    await obj_mysql.init_target(bot, uid, source, source_type)
    obj_mysql.set_report_obj(type, atall, report)
    await obj_mysql.save()
    uname, _ = obj_mysql.get_target_uname_and_roomid()
    create_auto_follow_task()
    logger.info(f"{logger_prefix} 成功 {msg_prefix}[{uname}]({uid})")
    await app.send_message(sender, MessageChain(draw_pic(f"{msg_prefix}{uname}(UID:{uid}){cmd.display}成功")))


@channel.use(
    ListenerSchema(
        listening_events=[GroupMessage],
        inline_dispatchers=[Twilight(
            ElementMatch(At, optional=True),
            FullMatch(prefix),
            "cmd" @ UnionMatch(*delete_describe).space(SpacePolicy.FORCE),
            "uid" @ ParamMatch()
        )],
    )
)
async def _DelListenGroup(app: Ariadne, sender: Group, member: Member, message: MessageChain,
                          cmd: MessageChain = ResultValue(), uid: MessageChain = ResultValue()):
    if check_not_mysql_datasource():
        return
    if check_at_object(app.account, message) is False:
        return
    uid = uid.display
    logger_prefix = get_logger_prefix(cmd.display, sender, member)
    if uid == "" or not uid.isdigit():
        logger.info(f"{logger_prefix} uid输入不合法({uid})")
        await app.send_message(sender, MessageChain(draw_pic(f"uid输入不合法({uid})，操作失败", width=800)))
        return
    uid = int(uid)
    group = sender.id
    bot = app.account
    logger.info(f"{logger_prefix} ({uid = }, {group = })")

    if master_qq == "" or f"{member.id}" != f"{master_qq}":
        person = await app.get_member(group, member.id)
        if person.permission < MemberPerm.Administrator:
            logger.info(f"{logger_prefix} 权限不足({member.id = }, {person.permission = })")
            await app.send_message(sender, MessageChain(draw_pic("权限不足，操作失败，仅群管理员和群主可操作", width=800)))
            return
    obj_mysql = ObjMysql()
    result = await obj_mysql.check_uid_exist(uid, group)
    if not result:
        logger.info(f"{logger_prefix} uid未被订阅({uid = })")
        await app.send_message(sender, MessageChain(draw_pic("uid未被订阅，操作失败", width=800)))
        return
    await obj_mysql.init_target(bot, uid, group)
    await obj_mysql.delete()
    uname, _ = obj_mysql.get_target_uname_and_roomid()
    logger.info(f"{logger_prefix} 成功{uname}({uid})")
    await app.send_message(sender, MessageChain(draw_pic(f"{uname}(UID:{uid}){cmd.display}成功", width=800)))


@channel.use(
    ListenerSchema(
        listening_events=[FriendMessage],
        inline_dispatchers=[Twilight(
            ElementMatch(At, optional=True),
            FullMatch(prefix),
            "cmd" @ UnionMatch(*delete_describe).space(SpacePolicy.FORCE),
            "uid" @ ParamMatch(),
            "group" @ ArgumentMatch("-g", "--group", type=int, default=0, optional=True)
        )],
    )
)
async def _DelListenFriend(app: Ariadne, sender: Friend, cmd: MessageChain = ResultValue(),
                           uid: MessageChain = ResultValue(), group: Optional[int] = ResultValue()):
    if check_not_mysql_datasource():
        return
    uid = uid.display
    logger_prefix = get_logger_prefix(cmd.display, sender)
    if uid == "" or not uid.isdigit():
        logger.info(f"{logger_prefix} uid输入不合法({uid})")
        await app.send_message(sender, MessageChain(draw_pic(f"uid输入不合法({uid})，操作失败", width=800)))
        return
    uid = int(uid)
    bot = app.account
    logger.info(f"{logger_prefix} ({uid = }, {group = })")

    if group != 0:
        if master_qq == "" or master_qq != sender.id:
            # 功能需要配置MASTER_QQ
            return
        source = group
        source_type = PushType.Group
        msg_prefix = f"群聊{group} "
    else:
        source = sender.id
        source_type = PushType.Friend
        msg_prefix = ""

    obj_mysql = ObjMysql()
    result = await obj_mysql.check_uid_exist(uid, source, source_type)
    if not result:
        logger.info(f"{logger_prefix} uid未被订阅({uid = })")
        await app.send_message(sender, MessageChain(draw_pic("uid未被订阅，操作失败", width=800)))
        return
    await obj_mysql.init_target(bot, uid, source, source_type)
    await obj_mysql.delete()
    uname, _ = obj_mysql.get_target_uname_and_roomid()
    logger.info(f"{logger_prefix} 成功 {msg_prefix}[{uname}]({uid})")
    await app.send_message(sender, MessageChain(draw_pic(f"{msg_prefix}{uname}(UID:{uid}){cmd.display}成功")))


@channel.use(
    ListenerSchema(
        listening_events=[FriendMessage],
        inline_dispatchers=[Twilight(
            ElementMatch(At, optional=True),
            FullMatch(prefix),
            "cmd" @ UnionMatch(*trans_to_mysql)
        )],
    )
)
async def _TransToMysql(app: Ariadne, sender: Friend, cmd: MessageChain = ResultValue()):
    if check_mysql_datasource():
        return
    if master_qq == "" or master_qq != sender.id:
        # 功能需要配置MASTER_QQ
        return
    logger_prefix = get_logger_prefix(cmd.display, sender)
    logger.info(f"{logger_prefix}")
    await app.send_message(sender, MessageChain(draw_pic(f"{cmd.display} 正在执行...", width=800)))
    result, message = await datasource_trans_to_mysql()
    if not result:
        logger.info(f"{logger_prefix} 失败，原因：{message}")
        await app.send_message(sender, MessageChain(draw_pic(f"{cmd.display} 失败，原因：{message}")))
        return
    logger.info(f"{logger_prefix} 成功")
    await app.send_message(sender, MessageChain(draw_pic(f"{cmd.display} 成功", width=800)))


@channel.use(
    ListenerSchema(
        listening_events=[FriendMessage],
        inline_dispatchers=[Twilight(
            ElementMatch(At, optional=True),
            FullMatch(prefix),
            "cmd" @ UnionMatch(*save_json)
        )],
    )
)
async def _TransToJson(app: Ariadne, sender: Friend, cmd: MessageChain = ResultValue()):
    if check_not_mysql_datasource():
        return
    if master_qq == "" or master_qq != sender.id:
        # 功能需要配置MASTER_QQ
        return
    logger_prefix = get_logger_prefix(cmd.display, sender)
    logger.info(f"{logger_prefix}")
    await app.send_message(sender, MessageChain(draw_pic(f"{cmd.display} 正在执行...", width=800)))
    result, message = datasource_trans_to_json()
    if not result:
        logger.info(f"{logger_prefix} 失败，原因：{message}")
        await app.send_message(sender, MessageChain(draw_pic(f"{cmd.display} 失败，原因：{message}")))
        return
    logger.info(f"{logger_prefix} 成功")
    await app.send_message(sender, MessageChain(draw_pic([f"{cmd.display} 成功",
                                                          f"文件保存在main.py同级目录下",
                                                          f"文件名：{message}"])))


@channel.use(
    ListenerSchema(
        listening_events=[GroupMessage],
        inline_dispatchers=[Twilight(
            ElementMatch(At, optional=True),
            FullMatch(prefix),
            "cmd" @ UnionMatch(*list_describe),
            "text" @ ArgumentMatch("-t", "--text", action="store_true", default=False),
        )],
    )
)
async def _GetUpList(app: Ariadne, sender: Group, message: MessageChain, cmd: MessageChain = ResultValue(),
                     text: bool = ResultValue()):
    if check_not_mysql_datasource():
        return
    if check_at_object(app.account, message) is False:
        return
    logger_prefix = get_logger_prefix(cmd.display, sender)
    logger.info(f"{logger_prefix} {text = }")
    group = sender.id
    obj_mysql = ObjMysql()
    result = await obj_mysql.get_ups_by_target_with_pic_struct(group, PushType.Group)
    if not result:
        result = ["未查询到订阅"]
    cleaned_result = "\n".join(result)
    logger.info(f"{logger_prefix} 成功 \n{cleaned_result}")
    row_cont = cleaned_result.count("\n") + 1
    str_cont = len(cleaned_result)
    row_split = 120
    if not text:
        await app.send_message(sender, MessageChain(draw_pic(result, width=1000)))
        return
    if str_cont > 4000 or row_cont > row_split:
        # 超长了，需要分段
        logger.info(f"{logger_prefix} {cmd.display}结果超长，分段发送")
        split_str = cleaned_result.split("\n")
        split_list = [split_str[i:i + row_split] for i in range(0, len(split_str), row_split)]
        for res in split_list:
            await app.send_message(sender, MessageChain("\n".join(res)))
        return
    await app.send_message(sender, MessageChain(cleaned_result))


@channel.use(
    ListenerSchema(
        listening_events=[FriendMessage],
        inline_dispatchers=[Twilight(
            ElementMatch(At, optional=True),
            FullMatch(prefix),
            "cmd" @ UnionMatch(*list_describe),
            "text" @ ArgumentMatch("-t", "--text", action="store_true", default=False),
        )],
    )
)
async def _GetUpListAll(app: Ariadne, sender: Friend, cmd: MessageChain = ResultValue(),
                        text: bool = ResultValue()):
    if check_not_mysql_datasource():
        return
    logger_prefix = get_logger_prefix(cmd.display, sender)
    logger.info(f"{logger_prefix} {text = }")
    obj_mysql = ObjMysql()
    if master_qq == "" or master_qq != sender.id:
        result = await obj_mysql.get_ups_by_target_with_pic_struct(sender.id, PushType.Friend)
        cleaned_result = "\n".join(result)
    else:
        result = await obj_mysql.get_up_list_with_pic_struct()
        res_temp = []
        for result_inner in result:
            res_temp.append("#" + result_inner.get("section"))
            res_temp.append("\n".join(result_inner.get("context")))
        cleaned_result = "\n".join(res_temp)
    if not result:
        result = ["未查询到订阅"]
        cleaned_result = "未查询到订阅"
    row_cont = cleaned_result.count("\n") + 1
    str_cont = len(cleaned_result)
    row_split = 120
    logger.info(f"{logger_prefix} 成功 \n{cleaned_result}")
    if not text:
        await app.send_message(sender, MessageChain(draw_pic(result, width=1000)))
        return
    if str_cont > 4000 or row_cont > row_split:
        # 超长了，需要分段
        logger.info(f"{logger_prefix} {cmd.display}结果超长，分段发送")
        split_str = cleaned_result.split("\n")
        split_list = [split_str[i:i + row_split] for i in range(0, len(split_str), row_split)]
        for res in split_list:
            await app.send_message(sender, MessageChain("\n".join(res)))
        return
    await app.send_message(sender, MessageChain(cleaned_result))


@channel.use(
    ListenerSchema(
        listening_events=[FriendMessage],
        inline_dispatchers=[Twilight(
            ElementMatch(At, optional=True),
            FullMatch(prefix),
            "cmd" @ UnionMatch(*reload_uid).space(SpacePolicy.FORCE),
            "uid" @ ParamMatch(),
        )],
    )
)
async def _ReloadUid(app: Ariadne, sender: Friend, cmd: MessageChain = ResultValue(),
                     uid: MessageChain = ResultValue()):
    if check_not_mysql_datasource():
        return
    uid = uid.display
    logger_prefix = get_logger_prefix(cmd.display, sender)
    logger.info(f"{logger_prefix} {uid = }")
    if uid == "" or not uid.isdigit():
        logger.info(f"{logger_prefix} uid输入不合法({uid})")
        await app.send_message(sender, MessageChain(draw_pic(f"uid输入不合法({uid})，操作失败", width=800)))
        return
    uid = int(uid)
    if master_qq == "" or master_qq != sender.id:
        return
    obj_mysql = ObjMysql()
    result = await obj_mysql.check_uid_exist_with_all(uid)
    if not result:
        logger.info(f"{logger_prefix} uid未被订阅({uid = })")
        await app.send_message(sender, MessageChain(draw_pic("uid未被订阅，操作失败", width=800)))
        return
    await obj_mysql.reload(uid)
    uname, _ = await select_uname_and_room_id(uid)
    logger.info(f"{logger_prefix} 成功 {uname}({uid})")
    await app.send_message(sender, MessageChain(draw_pic(f"{uname}(UID:{uid}){cmd.display}成功", width=800)))


@channel.use(
    ListenerSchema(
        listening_events=[GroupMessage],
        inline_dispatchers=[Twilight(
            ElementMatch(At, optional=True),
            FullMatch(prefix),
            "cmd" @ UnionMatch(*add_logo).space(SpacePolicy.FORCE),
            "uid" @ ParamMatch()
        )],
    )
)
async def _SetLogoGroup(app: Ariadne, sender: Group, member: Member, message: MessageChain,
                        cmd: MessageChain = ResultValue(), uid: MessageChain = ResultValue()):
    if check_not_mysql_datasource():
        return
    if check_at_object(app.account, message) is False:
        return
    uid = uid.display
    logger_prefix = get_logger_prefix(cmd.display, sender, member)
    if uid == "" or not uid.isdigit():
        logger.info(f"{logger_prefix} uid输入不合法({uid})")
        await app.send_message(sender, MessageChain(draw_pic(f"uid输入不合法({uid})，操作失败", width=800)))
        return
    uid = int(uid)
    group = sender.id
    bot = app.account
    logger.info(f"{logger_prefix} {uid = } {group = })")

    if master_qq == "" or f"{member.id}" != f"{master_qq}":
        person = await app.get_member(group, member.id)
        if person.permission < MemberPerm.Administrator:
            logger.info(f"{logger_prefix} 权限不足({member.id = }, {person.permission = })")
            await app.send_message(sender, MessageChain(draw_pic("权限不足，操作失败，仅群管理员和群主可操作", width=800)))
            return
    obj_mysql = ObjMysql()
    result = await obj_mysql.check_uid_exist(uid, group)
    if not result:
        logger.info(f"{logger_prefix} uid未被订阅({uid = })")
        await app.send_message(sender, MessageChain(draw_pic("uid未被订阅，操作失败", width=800)))
        return
    time_out = 60
    await app.send_message(sender, MessageChain(f"请在{time_out}秒内发送立绘图片\n发送 取消 则操作取消，无事发生"))

    @Waiter.create_using_function([GroupMessage])
    async def words_waiter(s: Group, m: Member, waiter_msg: MessageChain):
        if sender.id == s.id and member.id == m.id:
            return waiter_msg

    try:
        ret_msg = await inc.wait(words_waiter, timeout=time_out)  # 强烈建议设置超时时间否则将可能会永远等待
    except asyncio.TimeoutError:
        result = "超时自动取消"
        logger.info(f"{logger_prefix} 失败 原因：{result}")
        await app.send_message(sender, MessageChain(result))
    else:
        if ret_msg.display == "取消":
            result = "操作已取消"
            logger.info(f"{logger_prefix} 失败 原因：{result}")
            await app.send_message(sender, MessageChain(result))
            return
        image = None
        image_count = 0
        for element in ret_msg.content:
            if isinstance(element, Image):
                image = element
                image_count += 1
        if image is None or image_count > 1:
            result = "操作失败，请确认发送的图片数量为1"
            logger.info(f"{logger_prefix} 失败 原因：{result}")
            await app.send_message(sender, MessageChain(result))
            return
        await obj_mysql.init_target(bot, uid, group)
        logo_base64 = await element_get_bytes(image)
        obj_mysql.set_report_logo(logo_base64)
        await obj_mysql.save()
        uname, _ = obj_mysql.get_target_uname_and_roomid()
        logger.info(f"{logger_prefix} 成功 {uname}({uid})")
        await app.send_message(sender, MessageChain(draw_pic(f"{uname}(UID:{uid}){cmd.display}成功", width=800)))
        await app.send_message(sender, MessageChain(draw_image_pic(logo_base64, "直播报告立绘")))


@channel.use(
    ListenerSchema(
        listening_events=[FriendMessage],
        inline_dispatchers=[Twilight(
            ElementMatch(At, optional=True),
            FullMatch(prefix),
            "cmd" @ UnionMatch(*add_logo).space(SpacePolicy.FORCE),
            "uid" @ ParamMatch(),
            "group" @ ArgumentMatch("-g", "--group", type=int, default=0, optional=True)
        )],
    )
)
async def _SetLogoFriend(app: Ariadne, sender: Friend, cmd: MessageChain = ResultValue(),
                         uid: MessageChain = ResultValue(), group: Optional[int] = ResultValue()):
    if check_not_mysql_datasource():
        return
    uid = uid.display
    logger_prefix = get_logger_prefix(cmd.display, sender)
    if uid == "" or not uid.isdigit():
        logger.info(f"{logger_prefix} uid输入不合法({uid})")
        await app.send_message(sender, MessageChain(draw_pic(f"uid输入不合法({uid})，操作失败", width=800)))
        return
    uid = int(uid)
    bot = app.account
    logger.info(f"{logger_prefix} ({uid = }, {group = })")

    if group != 0:
        if master_qq == "" or master_qq != sender.id:
            # 功能需要配置MASTER_QQ
            return
        source = group
        source_type = PushType.Group
        msg_prefix = f"群聊{group} "
    else:
        source = sender.id
        source_type = PushType.Friend
        msg_prefix = ""

    obj_mysql = ObjMysql()
    result = await obj_mysql.check_uid_exist(uid, source, source_type)
    if not result:
        logger.info(f"{logger_prefix} uid未被订阅({uid = })")
        await app.send_message(sender, MessageChain(draw_pic("uid未被订阅，操作失败", width=800)))
        return
    time_out = 60
    await app.send_message(sender, MessageChain(f"请在{time_out}秒内发送立绘图片\n发送 取消 则操作取消，无事发生"))

    @Waiter.create_using_function([FriendMessage])
    async def words_waiter(s: Friend, waiter_msg: MessageChain):
        if sender.id == s.id:
            return waiter_msg

    try:
        ret_msg = await inc.wait(words_waiter, timeout=time_out)  # 强烈建议设置超时时间否则将可能会永远等待
    except asyncio.TimeoutError:
        result = "超时自动取消"
        logger.info(f"{logger_prefix} 失败 原因：{result}")
        await app.send_message(sender, MessageChain(result))
    else:
        if ret_msg.display == "取消":
            result = "操作已取消"
            logger.info(f"{logger_prefix} 失败 原因：{result}")
            await app.send_message(sender, MessageChain(result))
            return
        image = None
        image_count = 0
        for element in ret_msg.content:
            if isinstance(element, Image):
                image = element
                image_count += 1
        if image is None or image_count > 1:
            result = "操作失败，请确认发送的图片数量为1"
            logger.info(f"{logger_prefix}失败 原因：{result}")
            await app.send_message(sender, MessageChain(result))
            return
        await obj_mysql.init_target(bot, uid, source, source_type)
        logo_base64 = await element_get_bytes(image)
        obj_mysql.set_report_logo(logo_base64)
        await obj_mysql.save()
        uname, _ = obj_mysql.get_target_uname_and_roomid()
        logger.info(f"{logger_prefix} 成功 {msg_prefix}[{uname}]({uid})")
        await app.send_message(sender, MessageChain(draw_pic(f"{msg_prefix}{uname}(UID:{uid}){cmd.display}成功")))
        await app.send_message(sender, MessageChain(draw_image_pic(logo_base64, "直播报告立绘")))


@channel.use(
    ListenerSchema(
        listening_events=[GroupMessage],
        inline_dispatchers=[Twilight(
            ElementMatch(At, optional=True),
            FullMatch(prefix),
            "cmd" @ UnionMatch(*clear_logo).space(SpacePolicy.FORCE),
            "uid" @ ParamMatch()
        )],
    )
)
async def _ClearLogoGroup(app: Ariadne, sender: Group, member: Member, message: MessageChain,
                          cmd: MessageChain = ResultValue(), uid: MessageChain = ResultValue()):
    if check_not_mysql_datasource():
        return
    if check_at_object(app.account, message) is False:
        return
    uid = uid.display
    logger_prefix = get_logger_prefix(cmd.display, sender, member)
    if uid == "" or not uid.isdigit():
        logger.info(f"{logger_prefix} uid输入不合法({uid})")
        await app.send_message(sender, MessageChain(draw_pic(f"uid输入不合法({uid})，操作失败", width=800)))
        return
    uid = int(uid)
    group = sender.id
    bot = app.account
    logger.info(f"{logger_prefix} {uid = } {group = })")

    if master_qq == "" or f"{member.id}" != f"{master_qq}":
        person = await app.get_member(group, member.id)
        if person.permission < MemberPerm.Administrator:
            logger.info(f"{logger_prefix} 权限不足({member.id = }, {person.permission = })")
            await app.send_message(sender, MessageChain(draw_pic("权限不足，操作失败，仅群管理员和群主可操作", width=800)))
            return
    obj_mysql = ObjMysql()
    result = await obj_mysql.check_uid_exist(uid, group)
    if not result:
        logger.info(f"{logger_prefix} uid未被订阅({uid = })")
        await app.send_message(sender, MessageChain(draw_pic("uid未被订阅，操作失败", width=800)))
        return
    await obj_mysql.init_target(bot, uid, group)
    obj_mysql.clear_report_logo()
    await obj_mysql.save()
    uname, _ = obj_mysql.get_target_uname_and_roomid()
    logger.info(f"{logger_prefix} 成功{uname}({uid})")
    await app.send_message(sender, MessageChain(draw_pic(f"{uname}(UID:{uid}){cmd.display}成功", width=800)))


@channel.use(
    ListenerSchema(
        listening_events=[FriendMessage],
        inline_dispatchers=[Twilight(
            ElementMatch(At, optional=True),
            FullMatch(prefix),
            "cmd" @ UnionMatch(*clear_logo).space(SpacePolicy.FORCE),
            "uid" @ ParamMatch(),
            "group" @ ArgumentMatch("-g", "--group", type=int, default=0, optional=True)
        )],
    )
)
async def _ClearLogoFriend(app: Ariadne, sender: Friend, cmd: MessageChain = ResultValue(),
                           uid: MessageChain = ResultValue(), group: Optional[int] = ResultValue()):
    if check_not_mysql_datasource():
        return
    uid = uid.display
    logger_prefix = get_logger_prefix(cmd.display, sender)
    if uid == "" or not uid.isdigit():
        logger.info(f"{logger_prefix} uid输入不合法({uid})")
        await app.send_message(sender, MessageChain(draw_pic(f"uid输入不合法({uid})，操作失败", width=800)))
        return
    uid = int(uid)
    bot = app.account
    logger.info(f"{logger_prefix} ({uid = }, {group = })")
    if group != 0:
        if master_qq == "" or master_qq != sender.id:
            # 功能需要配置MASTER_QQ
            return
        source = group
        source_type = PushType.Group
        msg_prefix = f"群聊{group} "
    else:
        source = sender.id
        source_type = PushType.Friend
        msg_prefix = ""
    obj_mysql = ObjMysql()
    result = await obj_mysql.check_uid_exist(uid, source, source_type)
    if not result:
        logger.info(f"{logger_prefix} uid未被订阅({uid = })")
        await app.send_message(sender, MessageChain(draw_pic("uid未被订阅，操作失败", width=800)))
        return
    await obj_mysql.init_target(bot, uid, source, source_type)
    obj_mysql.clear_report_logo()
    await obj_mysql.save()
    uname, _ = obj_mysql.get_target_uname_and_roomid()
    logger.info(f"{logger_prefix} 成功 {msg_prefix}[{uname}]({uid})")
    await app.send_message(sender, MessageChain(draw_pic(f"{msg_prefix}{uname}(UID:{uid}){cmd.display}成功")))


@channel.use(
    ListenerSchema(
        listening_events=[GroupMessage],
        inline_dispatchers=[Twilight(
            ElementMatch(At, optional=True),
            FullMatch(prefix),
            "cmd" @ UnionMatch(*set_message).space(SpacePolicy.FORCE),
            "uid" @ ParamMatch(),
            "message_type" @ ArgumentMatch("-t", "--type", type=str, choices=["news", "live_on", "live_off"]),
        )],
    )
)
async def _SetMessageGroup(app: Ariadne, sender: Group, member: Member, message: MessageChain,
                           cmd: MessageChain = ResultValue(), uid: MessageChain = ResultValue(),
                           message_type: Optional[str] = ResultValue()):
    if check_not_mysql_datasource():
        return
    if check_at_object(app.account, message) is False:
        return
    uid = uid.display
    logger_prefix = get_logger_prefix(cmd.display, sender, member)
    if uid == "" or not uid.isdigit():
        logger.info(f"{logger_prefix} uid输入不合法({uid})")
        await app.send_message(sender, MessageChain(draw_pic(f"uid输入不合法({uid})，操作失败", width=800)))
        return
    uid = int(uid)
    group = sender.id
    bot = app.account
    logger.info(f"{logger_prefix} {uid = } {group = } {message_type = })")

    if master_qq == "" or f"{member.id}" != f"{master_qq}":
        person = await app.get_member(group, member.id)
        if person.permission < MemberPerm.Administrator:
            logger.info(f"{logger_prefix} 权限不足({member.id = }, {person.permission = })")
            await app.send_message(sender, MessageChain(draw_pic("权限不足，操作失败，仅群管理员和群主可操作", width=800)))
            return
    obj_mysql = ObjMysql()
    result = await obj_mysql.check_uid_exist(uid, group)
    if not result:
        logger.info(f"{logger_prefix} uid未被订阅({uid = })")
        await app.send_message(sender, MessageChain(draw_pic("uid未被订阅，操作失败", width=800)))
        return
    timeout_s = 600
    await app.send_message(sender, MessageChain(get_message_help(
        message_type) + f"\nat元素和图片能够被正确识别\n请在{timeout_s}秒内发送内容\n发送 取消 则操作取消，无事发生"))

    @Waiter.create_using_function([GroupMessage])
    async def words_waiter(s: Group, m: Member, waiter_msg: MessageChain):
        if sender.id == s.id and member.id == m.id:
            return waiter_msg

    try:
        ret_msg = await inc.wait(words_waiter, timeout=timeout_s)  # 强烈建议设置超时时间否则将可能会永远等待
    except asyncio.TimeoutError:
        result = "超时自动取消"
        logger.info(f"{logger_prefix} 失败 原因：{result}")
        await app.send_message(sender, MessageChain(result))
    else:
        if ret_msg.display == "取消":
            result = "操作已取消"
            logger.info(f"{logger_prefix} 失败 原因：{result}")
            await app.send_message(sender, MessageChain(result))
            return
        msg = ""
        for element in ret_msg.content:
            if isinstance(element, Image):
                msg += "{base64pic=" + await element_get_bytes(element) + "}"
            if isinstance(element, At):
                msg += "{at" + f"{element.target}" + "}"
            if isinstance(element, AtAll):
                msg += "{atall}"
            if isinstance(element, Plain):
                msg += element.text
        await obj_mysql.init_target(bot, uid, group)
        obj_mysql.set_message_inner(message_type, msg)
        await obj_mysql.save()
        uname, _ = obj_mysql.get_target_uname_and_roomid()
        logger.info(f"{logger_prefix} 成功 {uname}({uid})")
        await app.send_message(sender, MessageChain(draw_pic(f"{uname}(UID:{uid}){cmd.display}成功", width=800)))


@channel.use(
    ListenerSchema(
        listening_events=[FriendMessage],
        inline_dispatchers=[Twilight(
            ElementMatch(At, optional=True),
            FullMatch(prefix),
            "cmd" @ UnionMatch(*set_message).space(SpacePolicy.FORCE),
            "uid" @ ParamMatch(),
            "message_type" @ ArgumentMatch("-t", "--type", type=str, choices=["news", "live_on", "live_off"]),
            "group" @ ArgumentMatch("-g", "--group", type=int, default=0, optional=True)
        )],
    )
)
async def _SetMessageFriend(app: Ariadne, sender: Friend, cmd: MessageChain = ResultValue(),
                            uid: MessageChain = ResultValue(),
                            message_type: Optional[str] = ResultValue(), group: Optional[int] = ResultValue()):
    if check_not_mysql_datasource():
        return
    uid = uid.display
    logger_prefix = get_logger_prefix(cmd.display, sender)
    if uid == "" or not uid.isdigit():
        logger.info(f"{logger_prefix} uid输入不合法({uid})")
        await app.send_message(sender, MessageChain(draw_pic(f"uid输入不合法({uid})，操作失败", width=800)))
        return
    uid = int(uid)
    bot = app.account
    logger.info(f"{logger_prefix} ({uid = }, {group = })")

    if group != 0:
        if master_qq == "" or master_qq != sender.id:
            # 功能需要配置MASTER_QQ
            return
        source = group
        source_type = PushType.Group
        msg_prefix = f"群聊{group} "
    else:
        source = sender.id
        source_type = PushType.Friend
        msg_prefix = ""

    obj_mysql = ObjMysql()
    result = await obj_mysql.check_uid_exist(uid, source, source_type)
    if not result:
        logger.info(f"{logger_prefix} uid未被订阅({uid = })")
        await app.send_message(sender, MessageChain(draw_pic("uid未被订阅，操作失败", width=800)))
        return
    timeout_s = 600
    await app.send_message(sender, MessageChain(get_message_help(
        message_type) + f"\n图片能够被正确识别\n请在{timeout_s}秒内发送内容\n发送 取消 则操作取消，无事发生"))

    @Waiter.create_using_function([FriendMessage])
    async def words_waiter(s: Friend, waiter_msg: MessageChain):
        if sender.id == s.id:
            return waiter_msg

    try:
        ret_msg = await inc.wait(words_waiter, timeout=timeout_s)  # 强烈建议设置超时时间否则将可能会永远等待
    except asyncio.TimeoutError:
        result = "超时自动取消"
        logger.info(f"{logger_prefix} 失败 原因：{result}")
        await app.send_message(sender, MessageChain(result))
    else:
        if ret_msg.display == "取消":
            result = "操作已取消"
            logger.info(f"{logger_prefix} 失败 原因：{result}")
            await app.send_message(sender, MessageChain(result))
            return
        msg = ""
        for element in ret_msg.content:
            if isinstance(element, Image):
                msg += "{base64pic=" + await element_get_bytes(element) + "}"
            if isinstance(element, Plain):
                msg += element.text
        await obj_mysql.init_target(bot, uid, source, source_type)
        obj_mysql.set_message_inner(message_type, msg)
        await obj_mysql.save()
        uname, _ = obj_mysql.get_target_uname_and_roomid()
        logger.info(f"{logger_prefix} 成功 {msg_prefix}[{uname}]({uid})")
        await app.send_message(sender, MessageChain(draw_pic(f"{msg_prefix}{uname}(UID:{uid}){cmd.display}成功")))


@channel.use(
    ListenerSchema(
        listening_events=[GroupMessage],
        inline_dispatchers=[Twilight(
            ElementMatch(At, optional=True),
            FullMatch(prefix),
            "cmd" @ UnionMatch(*set_report),
            "cmd_help" @ ArgumentMatch("-h", "--help", action="store_true", default=False),
            WildcardMatch()
        )],
        priority=12
    )
)
async def _SetReportHelpGroup(app: Ariadne, sender: Group, message: MessageChain,
                              cmd: MessageChain = ResultValue(), cmd_help: bool = ResultValue()):
    if check_not_mysql_datasource():
        return
    if check_at_object(app.account, message) is False:
        return
    logger_prefix = get_logger_prefix(cmd.display, sender)
    if cmd_help:
        logger.info(f"{logger_prefix} 帮助")
        help_str = [
            f"用法示例：{prefix}{cmd.display} uid 配置项 值",
            "注意：当前不支持批量配置",
            f"示例：{prefix}{cmd.display} 2 粉丝变动 开启",
            f"示例：{prefix}{cmd.display} 2 礼物榜 10",
            " "
        ]
        help_str = append_report_help(help_str)
        await app.send_message(sender, MessageChain(draw_pic(help_str, title=f"{cmd.display} 帮助", width=700)))
        raise PropagationCancelled


@channel.use(
    ListenerSchema(
        listening_events=[FriendMessage],
        inline_dispatchers=[Twilight(
            FullMatch(prefix),
            "cmd" @ UnionMatch(*set_report),
            "cmd_help" @ ArgumentMatch("-h", "--help", action="store_true", default=False),
            WildcardMatch()
        )],
        priority=12
    )
)
async def _SetReportHelpFriend(app: Ariadne, sender: Friend, cmd: MessageChain = ResultValue(),
                               cmd_help: bool = ResultValue()):
    if check_not_mysql_datasource():
        return
    logger_prefix = get_logger_prefix(cmd.display, sender)
    if cmd_help:
        logger.info(f"{logger_prefix} 帮助")
        help_str = []
        if master_qq == sender.id:
            help_str.append(f"用法：{prefix}{cmd.display} (-g 群号) uid 配置项 值")
        else:
            help_str.append(f"用法：{prefix}{cmd.display} uid 配置项 值")
        help_str.append("注意：当前不支持批量配置")
        help_str.append(f"示例：{prefix}{cmd.display} 2 粉丝变动 开启")
        help_str.append(f"示例：{prefix}{cmd.display} 2 礼物榜 10")
        if master_qq == sender.id:
            help_str.append(f"示例：{prefix}{cmd.display} -g 123456789 2 sc榜 3")
        help_str.append(" ")
        help_str = append_report_help(help_str)
        await app.send_message(sender, MessageChain(draw_pic(help_str, title=f"{cmd.display} 帮助", width=700)))
        raise PropagationCancelled


@channel.use(
    ListenerSchema(
        listening_events=[GroupMessage],
        inline_dispatchers=[Twilight(
            ElementMatch(At, optional=True),
            FullMatch(prefix),
            "cmd" @ UnionMatch(*set_report).space(SpacePolicy.FORCE),
            "uid" @ ParamMatch().space(SpacePolicy.FORCE),
            "configuration" @ ParamMatch().space(SpacePolicy.FORCE),
            "value" @ ParamMatch(),
        )],
    )
)
async def _SetReportGroup(app: Ariadne, sender: Group, member: Member, message: MessageChain,
                          cmd: MessageChain = ResultValue(), uid: MessageChain = ResultValue(),
                          configuration: MessageChain = ResultValue(), value: MessageChain = ResultValue()):
    if check_not_mysql_datasource():
        return
    if check_at_object(app.account, message) is False:
        return
    uid = uid.display
    logger_prefix = get_logger_prefix(cmd.display, sender, member)
    if uid == "" or not uid.isdigit():
        logger.info(f"{logger_prefix} uid输入不合法({uid})")
        await app.send_message(sender, MessageChain(draw_pic(f"uid输入不合法({uid})，操作失败", width=800)))
        return
    uid = int(uid)
    group = sender.id
    bot = app.account
    configuration = configuration.display
    value = value.display
    logger.info(f"{logger_prefix} ({uid = }, {group = }, {configuration = }, {value = })")

    if master_qq == "" or f"{member.id}" != f"{master_qq}":
        person = await app.get_member(group, member.id)
        if person.permission < MemberPerm.Administrator:
            logger.info(f"{logger_prefix} 权限不足({member.id = }, {person.permission = })")
            await app.send_message(sender, MessageChain(draw_pic("权限不足，操作失败，仅群管理员和群主可操作", width=800)))
            return
    obj_mysql = ObjMysql()
    result = await obj_mysql.check_uid_exist(uid, group)
    if not result:
        logger.info(f"{logger_prefix} uid未被订阅({uid = })")
        await app.send_message(sender, MessageChain(draw_pic("uid未被订阅，操作失败", width=800)))
        return
    await obj_mysql.init_target(bot, uid, group)
    res = obj_mysql.config_report(configuration, value)
    uname, _ = obj_mysql.get_target_uname_and_roomid()
    if not res:
        logger.info(f"{logger_prefix} 失败[{uname}]({uid})")
        await app.send_message(sender, MessageChain(
            draw_pic(f"{uname}({uid}){cmd.display}失败，请检查参数是否正确", width=1000)))
        return
    await obj_mysql.save()
    logger.info(f"{logger_prefix} 成功[{uname}]({uid})")
    await app.send_message(sender, MessageChain(draw_pic(f"{uname}(UID:{uid}){cmd.display}成功")))


@channel.use(
    ListenerSchema(
        listening_events=[FriendMessage],
        inline_dispatchers=[Twilight(
            ElementMatch(At, optional=True),
            FullMatch(prefix),
            "cmd" @ UnionMatch(*set_report).space(SpacePolicy.FORCE),
            "uid" @ ParamMatch().space(SpacePolicy.FORCE),
            "configuration" @ ParamMatch().space(SpacePolicy.FORCE),
            "value" @ ParamMatch(),
            "group" @ ArgumentMatch("-g", "--group", type=int, default=0, optional=True)
        )],
    )
)
async def _SetReportFriend(app: Ariadne, sender: Friend, cmd: MessageChain = ResultValue(),
                           uid: MessageChain = ResultValue(), configuration: MessageChain = ResultValue(),
                           value: MessageChain = ResultValue(), group: Optional[int] = ResultValue()):
    if check_not_mysql_datasource():
        return
    uid = uid.display
    logger_prefix = get_logger_prefix(cmd.display, sender)
    if uid == "" or not uid.isdigit():
        logger.info(f"{logger_prefix} uid输入不合法({uid})")
        await app.send_message(sender, MessageChain(draw_pic(f"uid输入不合法({uid})，操作失败", width=800)))
        return
    uid = int(uid)
    configuration = configuration.display
    value = value.display
    bot = app.account
    logger.info(f"{logger_prefix} ({uid = }, {group = }, {configuration = }, {value = })")

    if group != 0:
        if master_qq == "" or master_qq != sender.id:
            # 功能需要配置MASTER_QQ
            return
        source = group
        source_type = PushType.Group
        msg_prefix = f"群聊{group} "
    else:
        source = sender.id
        source_type = PushType.Friend
        msg_prefix = ""

    obj_mysql = ObjMysql()
    result = await obj_mysql.check_uid_exist(uid, source, source_type)
    if not result:
        logger.info(f"{logger_prefix} uid未被订阅({uid = })")
        await app.send_message(sender, MessageChain(draw_pic("uid未被订阅，操作失败", width=800)))
        return
    await obj_mysql.init_target(bot, uid, source, source_type)
    res = obj_mysql.config_report(configuration, value)
    uname, _ = obj_mysql.get_target_uname_and_roomid()
    if not res:
        logger.info(f"{logger_prefix} 失败[{uname}]({uid})")
        await app.send_message(sender, MessageChain(
            draw_pic(f"{msg_prefix}{uname}({uid}){cmd.display}失败，请检查参数是否正确")))
        return
    await obj_mysql.save()
    logger.info(f"{logger_prefix} 成功 {msg_prefix}[{uname}]({uid})")
    await app.send_message(sender, MessageChain(draw_pic(f"{msg_prefix}{uname}(UID:{uid}){cmd.display}成功")))


@channel.use(
    ListenerSchema(
        listening_events=[GroupMessage],
        inline_dispatchers=[Twilight(
            ElementMatch(At, optional=True),
            FullMatch(prefix),
            "cmd" @ UnionMatch(*quit_group)
        )],
    )
)
async def _QuitGroup(app: Ariadne, sender: Group, member: Member, message: MessageChain,
                     cmd: MessageChain = ResultValue()):
    if check_not_mysql_datasource():
        return
    if check_at_object(app.account, message) is False:
        return
    group = sender.id
    bot = app.account
    logger_prefix = get_logger_prefix(cmd.display, sender, member)
    logger.info(f"{logger_prefix}")

    if master_qq == "" or f"{member.id}" != f"{master_qq}":
        person = await app.get_member(group, member.id)
        if person.permission < MemberPerm.Administrator:
            logger.info(f"{logger_prefix} 权限不足({member.id = }, {person.permission = })")
            await app.send_message(sender, MessageChain(draw_pic("权限不足，操作失败，仅群管理员和群主可操作", width=800)))
            return
    await app.send_message(sender, MessageChain(draw_pic(f"{cmd.display}成功", width=800)))
    await app.quit_group(sender)
    obj_mysql = ObjMysql()
    await obj_mysql.clean_describe(bot, sender.id, PushType.Group)
    logger.info(f"{logger_prefix} 成功")


@channel.use(
    ListenerSchema(
        listening_events=[FriendMessage],
        inline_dispatchers=[Twilight(
            ElementMatch(At, optional=True),
            FullMatch(prefix),
            "cmd" @ UnionMatch(*quit_group).space(SpacePolicy.FORCE),
            "group_num" @ ParamMatch()
        )],
    )
)
async def _QuitGroupPrivate(app: Ariadne, sender: Friend, group_num: MessageChain = ResultValue(),
                            cmd: MessageChain = ResultValue()):
    if check_not_mysql_datasource():
        return
    if master_qq == "" or master_qq != sender.id:
        # 功能需要配置MASTER_QQ
        return
    group_num = group_num.display
    logger_prefix = get_logger_prefix(cmd.display, sender)
    if group_num == "" or not group_num.isdigit():
        logger.info(f"{logger_prefix} group_num输入不合法({group_num})")
        await app.send_message(sender, MessageChain(draw_pic(f"group_num输入不合法({group_num})，操作失败", width=800)))
        return
    group_num = int(group_num)
    logger.info(f"{logger_prefix} ({group_num = })")
    group_check = await app.get_group(group_num)
    if group_check is None:
        logger.warning(f"{logger_prefix} bot未加入群聊({group_num})")
    else:
        await app.quit_group(group_num)
    bot = app.account
    obj_mysql = ObjMysql()
    await obj_mysql.clean_describe(bot, group_num, PushType.Group)
    logger.info(f"{logger_prefix} 成功")
    await app.send_message(sender, MessageChain(draw_pic(f"{cmd.display}成功", width=800)))


@channel.use(
    ListenerSchema(
        listening_events=[FriendMessage],
        inline_dispatchers=[Twilight(
            ElementMatch(At, optional=True),
            FullMatch(prefix),
            "cmd" @ UnionMatch(*check_describe_abnormal)
        )],
    )
)
async def _CheckDescribeAbnormal(app: Ariadne, sender: Friend, cmd: MessageChain = ResultValue()):
    if check_not_mysql_datasource():
        return
    if master_qq == "" or master_qq != sender.id:
        # 功能需要配置MASTER_QQ
        return
    logger_prefix = get_logger_prefix(cmd.display, sender)
    logger.info(f"{logger_prefix}")
    obj_mysql = ObjMysql()
    group_set, friend_set = obj_mysql.get_all_groups_and_friends()
    bot_group_list: List[Group] = await app.get_group_list()
    bot_group_set = {x.id for x in bot_group_list}
    bot_friend_list: List[Friend] = await app.get_friend_list()
    bot_friend_set = {x.id for x in bot_friend_list}
    group_abnormal_describe = group_set - bot_group_set
    friend_abnormal_describe = friend_set - bot_friend_set
    if len(group_abnormal_describe) < 1 or len(friend_abnormal_describe) < 1:
        result = "无异常订阅"
        logger.info(f"{logger_prefix} 成功 \n{result}")
        image = draw_pic(result)
        await app.send_message(sender, MessageChain(image))
        return
    abnormal_list = []
    if len(group_abnormal_describe) > 1:
        group_abnormal = {"section": "异常订阅群号", "context": list(group_abnormal_describe)}
        abnormal_list.append(group_abnormal)
    if len(friend_abnormal_describe) > 1:
        friend_abnormal = {"section": "异常订阅好友", "context": list(friend_abnormal_describe)}
        abnormal_list.append(friend_abnormal)
    result = f"异常订阅群号: {group_abnormal_describe}\n异常订阅好友: {friend_abnormal_describe}"
    logger.info(f"{logger_prefix} 成功 \n{result}")
    image = draw_pic(abnormal_list)
    await app.send_message(sender, MessageChain(image))


@channel.use(
    ListenerSchema(
        listening_events=[FriendMessage],
        inline_dispatchers=[Twilight(
            ElementMatch(At, optional=True),
            FullMatch(prefix),
            "cmd" @ UnionMatch(*clear_describe_abnormal)
        )],
    )
)
async def _ClearDescribeAbnormal(app: Ariadne, sender: Friend, cmd: MessageChain = ResultValue()):
    if check_not_mysql_datasource():
        return
    if master_qq == "" or master_qq != sender.id:
        # 功能需要配置MASTER_QQ
        return
    logger_prefix = get_logger_prefix(cmd.display, sender)
    logger.info(f"{logger_prefix}")
    obj_mysql = ObjMysql()
    group_set, friend_set = obj_mysql.get_all_groups_and_friends()
    bot_group_list: List[Group] = await app.get_group_list()
    bot_group_set = {x.id for x in bot_group_list}
    bot_friend_list: List[Friend] = await app.get_friend_list()
    bot_friend_set = {x.id for x in bot_friend_list}
    group_abnormal_describe = group_set - bot_group_set
    friend_abnormal_describe = friend_set - bot_friend_set
    if len(group_abnormal_describe) < 1 or len(friend_abnormal_describe) < 1:
        result = "无异常订阅"
        logger.info(f"{logger_prefix} 成功 \n{result}")
        image = draw_pic(result)
        await app.send_message(sender, MessageChain(image))
        return
    abnormal_list = []
    if len(group_abnormal_describe) > 1:
        group_abnormal = {"section": "清除异常订阅群号", "context": list(group_abnormal_describe)}
        abnormal_list.append(group_abnormal)
    if len(friend_abnormal_describe) > 1:
        friend_abnormal = {"section": "清除异常订阅好友", "context": list(friend_abnormal_describe)}
        abnormal_list.append(friend_abnormal)
    bot = app.account
    up_list = obj_mysql.get_ups_by_targets(friend_abnormal_describe, group_abnormal_describe)
    for up in up_list:
        obj_mysql = ObjMysql()
        await obj_mysql.init_target(bot, up[0], up[1])
        await obj_mysql.delete()
    result = f"清除异常订阅群号: {group_abnormal_describe}\n清除异常订阅好友: {friend_abnormal_describe}"
    logger.info(f"{logger_prefix} 成功 \n{result}")
    abnormal_list.append("清除异常订阅成功")
    image = draw_pic(abnormal_list)
    await app.send_message(sender, MessageChain(image))


@channel.use(
    ListenerSchema(
        listening_events=[GroupMessage, FriendMessage],
        inline_dispatchers=[Twilight(
            ElementMatch(At, optional=True),
            FullMatch(prefix),
            "cmd" @ UnionMatch(*help_cmd),
            "default" @ ArgumentMatch("-d", "--default", action="store_true", default=False),
        )],
        # 优先级高于原始帮助触发器，拦截后续低优先级解析需要raise PropagationCancelled，直接return则会继续触发低优先级解析
        priority=10
    )
)
async def _MysqlHelp(app: Ariadne, sender: Union[Friend, Group], message: MessageChain,
                     cmd: MessageChain = ResultValue(), default: bool = ResultValue()):
    if check_at_object(app.account, message) is False:
        raise PropagationCancelled
    logger_prefix = get_logger_prefix(cmd.display, sender)
    logger.info(f"{logger_prefix} {default = }")
    if check_not_mysql_datasource() or default:
        # 若需要使用原始帮助触发，该分支直接return即可
        await app.send_message(sender, MessageChain(await default_help(sender)))
        # 拦截默认解析
        raise PropagationCancelled

    if isinstance(sender, Group):
        context_type = "describe_group"
        help_cmd_sub_title = "群聊命令帮助"
    else:
        if master_qq == sender.id:
            context_type = "describe_admin"
            help_cmd_sub_title = "主人命令帮助"
        else:
            context_type = "describe_friend"
            help_cmd_sub_title = "私聊命令帮助"
    pic_context = []
    for key, value in describe_cmd.items():
        # 组装绘图结构
        if len(value.get(context_type)) > 0:
            cmd_inner = {
                "section": key,
                "context": value.get(context_type)
            }
            pic_context.append(cmd_inner)
    image = draw_pic(pic_context, cmd.display, help_cmd_sub_title, width=1700)
    await app.send_message(sender, MessageChain(image))
    # 拦截默认解析
    raise PropagationCancelled


@channel.use(
    ListenerSchema(
        listening_events=[FriendMessage],
        inline_dispatchers=[Twilight(
            FullMatch(prefix),
            "cmd" @ UnionMatch(*ping)
        )],
    )
)
async def _Ping(app: Ariadne, sender: Friend, cmd: MessageChain = ResultValue()):
    if master_qq == "" or master_qq != sender.id:
        return
    logger_prefix = get_logger_prefix(cmd.display, sender)
    logger.info(f"{logger_prefix}")
    await app.send_message(sender, MessageChain("pong"))


@channel.use(
    ListenerSchema(
        listening_events=[GroupMessage],
        inline_dispatchers=[Twilight(
            ElementMatch(At, optional=True),
            FullMatch(prefix),
            "cmd" @ UnionMatch(*get_status)
        )],
    )
)
async def _GetStatusGroup(app: Ariadne, sender: Group, member: Member, message: MessageChain,
                          cmd: MessageChain = ResultValue()):
    if check_at_object(app.account, message) is False:
        return
    logger_prefix = get_logger_prefix(cmd.display, sender, member)
    logger.info(f"{logger_prefix}")
    status_result = "Running on StarBot v" + StarBot.VERSION

    await app.send_message(sender, MessageChain(status_result), quote=message)
    logger.info(f"{logger_prefix} {status_result}")


@channel.use(
    ListenerSchema(
        listening_events=[FriendMessage],
        inline_dispatchers=[Twilight(
            FullMatch(prefix),
            "cmd" @ UnionMatch(*get_status)
        )],
    )
)
async def _GetStatusPrivate(app: Ariadne, sender: Friend, cmd: MessageChain = ResultValue()):
    if master_qq == "" or master_qq != sender.id:
        return
    logger_prefix = get_logger_prefix(cmd.display, sender)
    logger.info(f"{logger_prefix}")
    status_result = "Running on StarBot v" + StarBot.VERSION
    await app.send_message(sender, MessageChain(status_result))
    logger.info(f"{logger_prefix} {status_result}")


@channel.use(
    ListenerSchema(
        listening_events=[FriendMessage],
        inline_dispatchers=[Twilight(
            FullMatch(prefix),
            "cmd" @ UnionMatch(*bot_mode)
        )],
    )
)
async def _GetBotMode(app: Ariadne, sender: Friend, cmd: MessageChain = ResultValue()):
    logger_prefix = get_logger_prefix(cmd.display, sender)
    logger.info(f"{logger_prefix}")
    if master_qq == "" or master_qq != sender.id:
        await app.send_message(sender, MessageChain(draw_pic(f"权限不够", width=800)))
        return
    qq = app.account
    if await check_bot_mode_public(qq):
        await app.send_message(sender, MessageChain(draw_pic(f"公开模式", width=800)))
        return
    else:
        await app.send_message(sender, MessageChain(draw_pic(f"私人模式", width=800)))
        return


@channel.use(
    ListenerSchema(
        listening_events=[FriendMessage],
        inline_dispatchers=[Twilight(
            FullMatch(prefix),
            "cmd" @ UnionMatch(*bot_mode).space(SpacePolicy.FORCE),
            "value" @ ParamMatch()
        )],
    )
)
async def _SetBotMode(app: Ariadne, sender: Friend,
                      cmd: MessageChain = ResultValue(), value: MessageChain = ResultValue()):
    value = value.display
    logger_prefix = get_logger_prefix(cmd.display, sender)
    logger.info(f"{logger_prefix} {value = }")
    if master_qq == "" or master_qq != sender.id:
        await app.send_message(sender, MessageChain(draw_pic(f"权限不够", width=800)))
        return
    qq = app.account
    if value == "公开":
        await set_bot_mode_public(qq)
        await app.send_message(sender, MessageChain(draw_pic(f"已设置为公开模式，将自动通过好友申请和群聊邀请")))
        return
    elif value == "私人":
        await set_bot_mode_private(qq)
        await app.send_message(sender, MessageChain(draw_pic(f"已设置为私人模式，自动拒绝除主人外好友申请和群聊邀请")))
        return
    else:
        await app.send_message(sender, MessageChain("输入有误，有效输入为 公开 或 私人"))
        return
