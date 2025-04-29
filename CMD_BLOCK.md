# starbot-mysql-plugin

#### 命令阻断帮助

命令阻断工具本质也是一个插件包，如需启用，可以仅保留需要的命令阻断文件，将commands_block文件夹放置于plugins目录中随starbot启动载入即可

例如，我不允许其他用户触发绑定、禁用、启用、直播报告，则保留如下文件夹及文件
```
commands_block
  -|disable_block.py
  -|enable_block.py
  -|data
     -|bind_block.py
     -|report_block.py
```
将这个commands_block文件夹放入plugins目录中，按照文档加载该自定义插件，即可启用这部分命令阻断，配置master_qq后非master_qq用户则不会响应这部分命令
 
_[将这些.py文件随手扔在plugins根目录下也是可以正常加载]_ 

命令和对应文件的关系如下表所示

|   命令   |              文件名              |  文件子目录  |               备注                |
|--------|-------------------------------|---------|---------------------------------|
|   帮助   |         help_block.py         |    /    |                                 |
|   启用   |        enable_block.py        |    /    |                                 |
|   禁用   |       disable_block.py        |    /    |                                 |
|  动态@我  |    dynamic_at_me_block.py     |   at    |                                 |
| 取消动态@我 | dynamic_at_me_cancel_block.py |   at    |                                 |
| 动态@列表  |  dynamic_at_me_list_block.py  |   at    |                                 |
|  直播@我  |    live_on_at_me_block.py     |   at    |                                 |
| 取消直播@我 | live_on_at_me_cancel_block.py |   at    |                                 |
| 直播@列表  |  live_on_at_me_list_block.py  |   at    |                                 |
|   绑定   |         bind_block.py         |  data   |                                 |
|  直播报告  |        report_block.py        |  data   |                                 |
| 直播间数据  |      room_data_block.py       |  data   |                                 |
| 直播间总数据 |   room_data_total_block.py    |  data   |                                 |
|  我的数据  |      user_data_block.py       |  data   |                                 |
| 我的总数据  |   user_data_total_block.py    |  data   |                                 |
|  排行榜1  |       ranking_block.py        | ranking |                                 |
|  排行榜2  |    ranking_double_block.py    | ranking | 当前该文件和ranking_block.py作用一致，暂时无用 |
|   补发   |        resend_block.py        | master  |      命令本身只有master可以触发，暂时无用      |
| 清空补发队列 |  resend_clear_queue_block.py  | master  |      命令本身只有master可以触发，暂时无用      |

