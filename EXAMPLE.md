# starbot-mysql-plugin

mysql数据库需要用户自行部署完成


#### 全新启动帮助

**以下操作预设bot的qq号为123456789，mysql数据源密码为root123456**

如果你是starbot新用户，没有已有订阅信息，搭载本插件会遇到一个已知问题场景：空mysql订阅信息下，starbot将无法启动

此时可以通过如下命令初始化mysql：

```shell
python mysql_init.py --qq 123456789 --password root123456
```

该操作将以密码为root123456的root用户连接本地mysql服务器，创建名为starbot的数据库，并在该数据库内写入starbot所需的所有表结构并内置一条无用数据以供starbot启动，启动后可以通过插件命令进行操作，请务必确保订阅信息大于一条

~~订阅信息为starbot开发者姬姬的uid和推送姬の通知群（799915082），仅用于规避starbot启动问题，不产生任何推送~~

具体main.py文件请参考代码仓内的main.py文件


#### 数据源迁移帮助

**以下操作预设bot的qq号为123456789，mysql数据源密码为root123456**

如果你是其他数据源用户（通常为json数据源）想要使用本插件并切换到mysql数据源
请使用如下命令初始化mysql：

```shell
python mysql_init.py --password root123456 --onlystruct
```

该操作将以密码为root123456的root用户连接本地mysql服务器，创建名为starbot的数据库，并在该数据库内写入starbot所需的所有表结构但不内置数据

根据已有main.py文件的位置将该仓库plugins目录拷贝到相同位置，在main.py内添加以下配置项

```shell
config.set("MASTER_QQ", 99999999) # 设置starbot超级权限用户，没有设置过则需要设置
config.set("CUSTOM_COMMANDS_PACKAGE", "plugins") # 加载自定义插件包
config.set("MYSQL_HOST", "127.0.0.1") # mysql链接信息的mysql地址
config.set("MYSQL_USERNAME", "root") # mysql链接信息的mysql用户名
config.set("MYSQL_PASSWORD", "root123456") # mysql链接信息的mysql密码
```

然后继续使用原有数据源启动，启动完毕后，使用starbot超级权限用户对bot使用命令“数据源转储”，注意自行增加配置的命令前缀
bot接收到该命令，会将内存中的所有订阅信息，根据配置项的链接信息，写入mysql数据库

该命令执行需要一段时间，根据原数据源的数量、网络通信速度以及设备运行速度有关，请耐心等待，完成后会回复“数据源转储成功”

该操作完成后，停止starbot运行，然后修改main.py数据源启动，假设原文件为

```shell
...
from starbot.core.datasource import JsonDataSource
...
config.set("MASTER_QQ", 123456789) # 设置starbot超级权限用户，没有设置过则需要设置
config.set("CUSTOM_COMMANDS_PACKAGE", "plugins") # 加载自定义插件包
config.set("MYSQL_HOST", "127.0.0.1") # mysql链接信息的mysql地址
config.set("MYSQL_USERNAME", "root") # mysql链接信息的mysql用户名
config.set("MYSQL_PASSWORD", "root123456") # mysql链接信息的mysql密码
...
datasource = JsonDataSource("推送配置.json")
bot = StarBot(datasource)
...
```

修改为

```shell
...
from starbot.core.datasource import JsonDataSource, MySQLDataSource
...
config.set("MASTER_QQ", 123456789) # 设置starbot超级权限用户，没有设置过则需要设置
config.set("CUSTOM_COMMANDS_PACKAGE", "plugins") # 加载自定义插件包
config.set("MYSQL_HOST", "127.0.0.1") # mysql链接信息的mysql地址
config.set("MYSQL_USERNAME", "root") # mysql链接信息的mysql用户名
config.set("MYSQL_PASSWORD", "root123456") # mysql链接信息的mysql密码
...
#datasource = JsonDataSource("推送配置.json")
datasource = MySQLDataSource()
bot = StarBot(datasource)
...
```

正常启动starbot即可


#### 使用插件

预设命令前缀为“/”

发送“/help”或“/帮助”则返回插件帮助，插件帮助已覆盖bot原始帮助，通过添加“-d”或“--default”来呼出原始命令帮助

如果需要增加图片版权信息，请fork代码仓或者本地自行修改代码，原始版权信息请务必保留

普通绘图函数：mysql_utils.py -> draw_pic
logo绘图函数：mysql_utils.py -> draw_image_pic
帮助绘图函数：mysql_utils.py -> default_help （默认帮助，取自starbot.commands.builtin.help，可以根据需要自行修改）


#### 设置推送报告

命令为“设置推送报告”或者“setreport”

用法为自行添加命令前缀：设置推送报告 uid 配置项 值

根据推送姬官网的json生成工具字段设置推送报告具体内容，详细配置如下

| 配置项      | 别名                 | 类型   | 可选值     |
|----------|--------------------|------|---------|
| 直播时长     | time               | bool | 开启 关闭   |
| 粉丝变动     | fans_change        | bool | 开启 关闭   |
| 粉丝勋章变动   | fans_medal_change  | bool | 开启 关闭   |
| 大航海变动    | guard_change       | bool | 开启 关闭   |
| 弹幕数据     | danmu              | bool | 开启 关闭   |
| 盲盒数据     | box                | bool | 开启 关闭   |
| 礼物数据     | gift               | bool | 开启 关闭   |
| sc数据     | sc                 | bool | 开启 关闭   |
| 大航海数据    | guard              | bool | 开启 关闭   |
| 弹幕榜      | danmu_ranking      | int  | 闭区间0到10 |
| 盲盒榜      | box_ranking        | int  | 闭区间0到10 |
| 盲盒盈亏榜    | box_profit_ranking | int  | 闭区间0到10 |
| 礼物榜      | gift_ranking       | int  | 闭区间0到10 |
| sc榜      | sc_ranking         | int  | 闭区间0到10 |
| 开通大航海名单  | guard_list         | bool | 开启 关闭   |
| 盲盒盈亏折线图  | box_profit_diagram | bool | 开启 关闭   |
| 弹幕互动曲线图  | danmu_diagram      | bool | 开启 关闭   |
| 盲盒互动曲线图  | box_diagram        | bool | 开启 关闭   |
| 礼物互动曲线图  | gift_diagram       | bool | 开启 关闭   |
| sc互动曲线图  | sc_diagram         | bool | 开启 关闭   |
| 大航海互动曲线图 | guard_diagram      | bool | 开启 关闭   |
| 弹幕词云     | danmu_cloud        | bool | 开启 关闭   |


#### 数据库初始化工具使用帮助
执行命令
```shell
python mysql_init.py --help
```
得到如下帮助文档
```shell
usage: mysql_init.py [-h] [--qq QQ] [--host HOST] [--user USER] [--password PASSWORD] [--port PORT] [--database DATABASE] [--onlystruct]

starbot_mysql_plugin数据库初始化工具

options:
  -h, --help           show this help message and exit
  --qq QQ              qq号，未添加--onlystruct参数时必填
  --host HOST          mysql host[默认127.0.0.1]
  --user USER          mysql username[默认root]
  --password PASSWORD  mysql password[默认123456]
  --port PORT          mysql port[默认3306]
  --database DATABASE  mysql db[默认starbot]
  --onlystruct         mysql仅初始化结构
```

该工具的作用是用户需要使用mysql数据源时，对mysql数据库进行初始化的工具脚本

用法示例：

假设mysql用户名为root密码为root123456，为本地部署的mysql，bot(qq号为123456789)全新启动，执行以下命令完成starbot数据库和表结构的初始化，可切换mysql数据源后搭载插件正常使用
```shell
python mysql_init.py --password root123456 --qq 123456789
```

假设mysql用户名为root密码为root123456，为本地部署的mysql，使用数据源迁移或已有mysql数据来源，执行以下命令完成starbot数据库和表结构的初始化但不内置占位数据，则需要完成数据源转换或其他操作后切换mysql数据源并搭载插件正常使用
```shell
python mysql_init.py --password root123456 --onlystruct
```

#### 数据库迁移工具使用帮助

执行命令
```shell
python mysql_trans_qq.py --help
```
得到如下帮助文档
```shell
usage: mysql_trans_qq.py [-h] --oldqq OLDQQ --newqq NEWQQ [--host HOST] [--user USER] [--password PASSWORD] [--port PORT] [--database DATABASE]

starbot_mysql_plugin数据库迁移工具

options:
  -h, --help           show this help message and exit
  --oldqq OLDQQ        bot旧qq号
  --newqq NEWQQ        bot新qq号
  --host HOST          mysql host[默认127.0.0.1]
  --user USER          mysql username[默认root]
  --password PASSWORD  mysql password[默认123456]
  --port PORT          mysql port[默认3306]
  --database DATABASE  mysql db[默认starbot]

```

该工具的作用是用户需要更换新bot时，执行该脚本进行数据迁移，具体为把数据库bot表中的bot列全部更新为新qq

用法示例：

假设mysql用户名为root密码为root123456，为本地部署的mysql，旧bot(qq号为123456789)已不可用，需要更换为新bot(qq号为987654321)，则可执行如下命令，则订阅数据由123456789迁移到987654321，维持可用
```shell
python mysql_trans_qq.py --password root123456 --oldqq 123456789 --newqq 987654321
```

#### 数据库备份和恢复工具帮助

执行命令
```shell
python mysql_backup.py --help
```
得到如下帮助文档
```shell
usage: mysql_backup.py [-h] [--backup] [--file FILE] [--forceall] [--host HOST] [--user USER] [--password PASSWORD] [--port PORT] [--database DATABASE]

starbot_mysql_plugin数据库备份和恢复工具

options:
  -h, --help           show this help message and exit
  --backup             备份为sql文件
  --file FILE          使用sql文件导入数据库
  --forceall           强制备份数据库下所有表，执行sql时将不保证一定成功，默认关闭时仅备份starbot所需表
  --host HOST          mysql host[默认127.0.0.1]
  --user USER          mysql username[默认root]
  --password PASSWORD  mysql password[默认123456]
  --port PORT          mysql port[默认3306]
  --database DATABASE  mysql db[默认starbot]


```

该工具的作用是用户需要备份mysql数据源为sql文件或者通过已经备份好的sql文件恢复mysql数据源

注意：**该工具生成的sql文件，包含表的强制更新语句和建表语句以及数据插入语句，会覆盖已有表，请谨慎使用**

用法示例：

假设mysql用户名为root密码为root123456，为本地部署的mysql，则可执行如下命令，备份得到sql文件starbot_xxx.sql，其中仅包含starbot所需的表
```shell
python mysql_backup.py --password root123456 --backup
```

假设mysql用户名为root密码为root123456，为本地部署的mysql，则可执行如下命令，备份得到sql文件starbot_xxx.sql，其中会包含starbot数据库下所有表
```shell
python mysql_backup.py --password root123456 --backup --forceall
```

假设mysql用户名为root密码为root123456，为本地部署的mysql，备份的sql文件starbot_xxx.sql，则可执行如下命令，可以通过该备份恢复mysql数据源
```shell
python mysql_backup.py --password root123456 --file starbot_xxx.sql
```