from graia.ariadne.event.message import FriendMessage, GroupMessage
from graia.ariadne.message.element import At
from graia.ariadne.message.parser.twilight import Twilight, FullMatch, UnionMatch, ElementMatch, ParamMatch
from graia.ariadne.model import Friend, Member
from graia.broadcast import PropagationCancelled
from graia.saya.builtins.broadcast import ListenerSchema
from graia.saya import Channel

from starbot.utils import config

prefix = config.get("COMMAND_PREFIX")
master_qq = config.get("MASTER_QQ")
channel = Channel.current()

cmd = ["直播间总数据"]


@channel.use(
    ListenerSchema(
        listening_events=[FriendMessage],
        inline_dispatchers=[Twilight(
            FullMatch(prefix),
            FullMatch(*cmd)
        )],
        priority=15
    )
)
async def _RoomDataTotalBlockFriend(sender: Friend):
    if not master_qq:
        # 未配置MASTER_QQ则不生效
        return
    if f"{master_qq}" != f"{sender.id}":
        # 非MASTER_QQ拦截默认解析
        raise PropagationCancelled


@channel.use(
    ListenerSchema(
        listening_events=[GroupMessage],
        inline_dispatchers=[Twilight(
            ElementMatch(At, optional=True),
            FullMatch(prefix),
            FullMatch(*cmd)
        )],
        priority=15
    )
)
async def _RoomDataTotalBlockGroup(member: Member):
    if not master_qq:
        # 未配置MASTER_QQ则不生效
        return
    if f"{member.id}" != f"{master_qq}":
        # 非MASTER_QQ拦截默认解析
        raise PropagationCancelled
