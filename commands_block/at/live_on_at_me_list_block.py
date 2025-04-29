from graia.ariadne.event.message import GroupMessage
from graia.ariadne.message.element import At
from graia.ariadne.message.parser.twilight import Twilight, FullMatch, UnionMatch, ElementMatch
from graia.ariadne.model import Member
from graia.broadcast import PropagationCancelled
from graia.saya.builtins.broadcast import ListenerSchema
from graia.saya import Channel

from starbot.utils import config

prefix = config.get("COMMAND_PREFIX")
master_qq = config.get("MASTER_QQ")
channel = Channel.current()

cmd = ["开播@列表", "直播@列表", "开播@名单", "直播@名单"]


@channel.use(
    ListenerSchema(
        listening_events=[GroupMessage],
        inline_dispatchers=[Twilight(
            ElementMatch(At, optional=True),
            FullMatch(prefix),
            UnionMatch(*cmd)
        )],
        priority=15
    )
)
async def _LiveOnAtMeListBlock(member: Member):
    if not master_qq:
        # 未配置MASTER_QQ则不生效
        return
    if f"{member.id}" != f"{master_qq}":
        # 非MASTER_QQ拦截默认解析
        raise PropagationCancelled