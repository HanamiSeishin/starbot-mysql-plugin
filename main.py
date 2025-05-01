from starbot.core.bot import StarBot
from starbot.core.datasource import JsonDataSource, MySQLDataSource
from starbot.utils import config

config.set("MYSQL_HOST", "localhost")  # 默认部署在本地，若是其他ip地址，请修改为对应ip
config.set("MYSQL_PORT", 3306)  # mysql端口默认值
config.set("MYSQL_USERNAME", "root")  # 默认值，请替换成你的mysql username
config.set("MYSQL_PASSWORD", "123456")  # 默认值，请替换成你的mysql password
config.set("MYSQL_DB", "starbot")  # 数据库名称默认值，可以根据自己情况修改
config.set("MASTER_QQ", your_qq_number)  # 替换成你的qq号
config.set("COMMAND_PREFIX", "/")  # 替换成你的前缀，若不需要前缀请删除这一行
config.set("CUSTOM_COMMANDS_PACKAGE", "plugins")  # 载入自定义命令集
# 填写你的B站cookie，如果通过credential.json载入B站cookie，请删除这一行
config.set_credential(sessdata="B站账号的sessdata", bili_jct="B站账号的bili_jct", buvid3="B站账号的buvid3")
# 其他项目请自行填写

# datasource = JsonDataSource("推送配置.json")
datasource = MySQLDataSource()  # 使用mysql数据源启动
bot = StarBot(datasource)
bot.run()
