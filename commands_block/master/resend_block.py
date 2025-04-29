from graia.ariadne.event.message import FriendMessage
from graia.ariadne.message.parser.twilight import Twilight, FullMatch, UnionMatch
from graia.ariadne.model import Friend
from graia.broadcast import PropagationCancelled
from graia.saya.builtins.broadcast import ListenerSchema
from graia.saya import Channel

from starbot.utils import config

prefix = config.get("COMMAND_PREFIX")
master_qq = config.get("MASTER_QQ")
channel = Channel.current()

cmd = ["补发", "resend"]


@channel.use(
    ListenerSchema(
        listening_events=[FriendMessage],
        inline_dispatchers=[Twilight(
            FullMatch(prefix),
            UnionMatch(*cmd)
        )],
        priority=15
    )
)
async def _ResendBlock(sender: Friend):
    if not master_qq:
        # 未配置MASTER_QQ则不生效
        return
    if f"{master_qq}" != f"{sender.id}":
        # 非MASTER_QQ拦截默认解析
        raise PropagationCancelled

