# starbot-mysql-plugin
![1f36b87beb59d8b49881204b497ee87b](https://github.com/user-attachments/assets/580c0838-45b7-4cba-9217-1a61ef77ab47)
#### 介绍

starbot自定义命令包，包含如下功能

1. 递归加载plugins下的所有文件，报错则打印日志并跳过
2. 设置公开模式可拉群自动通过（需要配置MASTER_QQ）
3. 设置公开模式可好友申请自动通过（需要配置MASTER_QQ）
4. mysql数据源下的机器人的动态订阅功能和当前内存数据源到mysql的转储能力（需要配置MASTER_QQ）
5. 覆盖starbot原始帮助

当前版本 v1.1.0

更新日志查阅[更新日志](./UPDATE_LOG.md)

#### 软件架构

通过plugins目录下的__init__.py使用require导入内部所有插件包

#### 安装教程

将目录置于starbot的启动文件位置，添加config.set("CUSTOM_COMMANDS_PACKAGE", "plugins")即可

功能依赖MASTER_QQ配置项，需要添加config.set("MASTER_QQ", qq号)，例如config.set("MASTER_QQ", 123456)

部分功能需要starbot启用mysql数据源而并非使用json数据源，需要配置对应config.set("MYSQL_HOST", "mysqladdr") config.set("MYSQL_USERNAME", "username") config.set("MYSQL_PASSWORD", "password"),并且通过datasource = MySQLDataSource()启用mysql数据源
 _[而不要使用datasource = JsonDataSource("推送配置.json")]_ 

数据源转储功能仅当非mysql数据源生效，仍需要配置对应config.set("MYSQL_HOST", "mysqladdr") config.set("MYSQL_USERNAME", "username") config.set("MYSQL_PASSWORD", "password") 以写入mysql数据库

根目录__init__.py递归加载全部不为_开头的文件夹及内部.py文件，只需要放置相应插件即可被导入

部署指南和部分命令帮助请查阅[详细示例](./EXAMPLE.md)

#### 使用说明

命令包提供了启动starbot的main.py的demo文件

可以新增插件，放入plugins文件夹中并重启starbot，即可被自动导入

插件需要用户自行部署mysql服务，mysql默认数据库为starbot，表结构已生成sql文件starbot.sql

注意：starbot自身逻辑不接受空mysql表启动，即订阅信息为空的状态无法启动starbot，因此需要先进行订阅信息的写入才能正常启动

mysql_init.py为数据库初始化工具，可以使用python mysql_init.py -h查询使用帮助

mysql_trans_qq.py为数据库迁移工具，可以使用python mysql_trans_qq.py -h查询使用帮助

具体参阅[详细示例](./EXAMPLE.md)

命令示例[部分命令展示](./MENU.md)

#### 引用

starbot项目地址 https://github.com/Starlwr/StarBot

命令参考ddbot https://github.com/cnxysoft/DDBOT-WSa

#### 其他说明

作者作为曾经ddbot的使用者编写该starbot插件，目的是增强starbot功能，因此该仓库下的所有插件均可在starbot原仓库下使用

该插件的部署需要一定代码基础和运维技巧的支撑，若没有能力，请使用官方文档推荐的json数据源进行部署

插件仅在linux平台进行了测试，理论无平台相关性，但不确保不出问题

插件相关问题可以加入starbot官方群聊【推送姬の通知群（799915082）】，请注意提问技巧，部署相关问题请靠自己能力解决
