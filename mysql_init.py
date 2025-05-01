import asyncio
import aiomysql
import argparse
import sys

from loguru import logger

starbot_sql = """
SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS `bot`;
CREATE TABLE `bot`  (
  `id` bigint(0) NOT NULL AUTO_INCREMENT,
  `bot` bigint(0) NULL DEFAULT NULL,
  `uid` bigint(0) NULL DEFAULT NULL,
  PRIMARY KEY (`id`) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 12 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci ROW_FORMAT = Dynamic;
DROP TABLE IF EXISTS `dynamic_update`;
CREATE TABLE `dynamic_update`  (
  `id` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  `uid` bigint(0) NOT NULL COMMENT 'B站id',
  `enabled` tinyint(1) NULL DEFAULT NULL,
  `message` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL,
  PRIMARY KEY (`id`) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci ROW_FORMAT = Dynamic;
DROP TABLE IF EXISTS `live_off`;
CREATE TABLE `live_off`  (
  `id` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  `uid` bigint(0) NOT NULL COMMENT 'B站id',
  `enabled` tinyint(1) NULL DEFAULT NULL,
  `message` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL,
  PRIMARY KEY (`id`) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci ROW_FORMAT = Dynamic;
DROP TABLE IF EXISTS `live_on`;
CREATE TABLE `live_on`  (
  `id` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  `uid` bigint(0) NOT NULL COMMENT 'B站id',
  `enabled` tinyint(1) NULL DEFAULT NULL,
  `message` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL,
  PRIMARY KEY (`id`) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci ROW_FORMAT = Dynamic;
DROP TABLE IF EXISTS `live_report`;
CREATE TABLE `live_report`  (
  `id` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  `uid` bigint(0) NOT NULL COMMENT 'b站id',
  `enabled` tinyint(1) NULL DEFAULT NULL,
  `logo` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL,
  `logo_base64` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL,
  `time` tinyint(1) NULL DEFAULT NULL,
  `fans_change` tinyint(1) NULL DEFAULT NULL,
  `fans_medal_change` tinyint(1) NULL DEFAULT NULL,
  `guard_change` tinyint(1) NULL DEFAULT NULL,
  `danmu` tinyint(1) NULL DEFAULT NULL,
  `box` tinyint(1) NULL DEFAULT NULL,
  `gift` tinyint(1) NULL DEFAULT NULL,
  `sc` tinyint(1) NULL DEFAULT NULL,
  `guard` tinyint(1) NULL DEFAULT NULL,
  `danmu_ranking` int(0) NULL DEFAULT NULL,
  `box_ranking` int(0) NULL DEFAULT NULL,
  `box_profit_ranking` int(0) NULL DEFAULT NULL,
  `gift_ranking` int(0) NULL DEFAULT NULL,
  `sc_ranking` int(0) NULL DEFAULT NULL,
  `guard_list` tinyint(1) NULL DEFAULT NULL,
  `box_profit_diagram` tinyint(1) NULL DEFAULT NULL,
  `danmu_diagram` tinyint(1) NULL DEFAULT NULL,
  `box_diagram` tinyint(1) NULL DEFAULT NULL,
  `gift_diagram` tinyint(1) NULL DEFAULT NULL,
  `sc_diagram` tinyint(1) NULL DEFAULT NULL,
  `guard_diagram` tinyint(1) NULL DEFAULT NULL,
  `danmu_cloud` tinyint(1) NULL DEFAULT NULL,
  PRIMARY KEY (`id`) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci ROW_FORMAT = Dynamic;
DROP TABLE IF EXISTS `targets`;
CREATE TABLE `targets`  (
  `id` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  `uid` bigint(0) NOT NULL COMMENT 'B站id',
  `num` bigint(0) NULL DEFAULT NULL COMMENT '需要推送的推送目标 QQ 号或群号',
  `type` int(10) UNSIGNED ZEROFILL NULL DEFAULT NULL COMMENT '推送类型，0 为私聊推送，1 为群聊推送',
  `uname` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL,
  `room_id` bigint(0) NULL DEFAULT NULL,
  PRIMARY KEY (`id`) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci ROW_FORMAT = Dynamic;
SET FOREIGN_KEY_CHECKS = 1;
"""


async def check_db_connection(db_config: dict):
    """
    检查数据库连接是否有效
    :param db_config: 数据库连接配置字典
    :return: 是否成功
    """
    try:
        # 尝试建立连接
        conn = await aiomysql.connect(
            host=db_config["host"],
            port=db_config["port"],
            user=db_config["user"],
            password=db_config["password"],
            connect_timeout=5  # 设置连接超时时间（秒）
        )

        conn.close()
        return True

    except aiomysql.OperationalError as e:
        error_msg = f"连接失败: {e}"
        # 常见错误类型细分提示
        if "Access denied" in str(e):
            error_msg = "用户名或密码错误，请检查连接配置"
        elif "Can't connect to MySQL server" in str(e):
            error_msg = "无法连接到数据库服务器，请检查主机/端口或网络"
        logger.error(error_msg)
        return False

    except Exception:
        logger.exception("未知错误\n")
        return False


async def create_database(db_config):
    """创建数据库"""
    conn = await aiomysql.connect(
        host=db_config["host"],
        port=db_config["port"],
        user=db_config["user"],
        password=db_config["password"]
    )

    async with conn.cursor() as cursor:
        try:
            await cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS {db_config['db']} "
                f"DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
            logger.debug(f"Database {db_config['db']} created")
        except aiomysql.Error as e:
            logger.error(f"Error creating database: {e}")
        finally:
            conn.close()


async def execute_sql(db_config, starbot_sql):
    """执行SQL文件"""
    # 连接到目标数据库
    conn = await aiomysql.connect(
        host=db_config["host"],
        port=db_config["port"],
        user=db_config["user"],
        password=db_config["password"],
        db=db_config["db"]
    )
    try:
        # 分割SQL语句（简单分号分割，实际需要更复杂的解析）
        statements = [stmt.strip() for stmt in starbot_sql.split(';') if stmt.strip()]

        async with conn.cursor() as cursor:
            for stmt in statements:
                if stmt.upper().startswith("DELIMITER"):
                    continue  # 跳过DELIMITER指令
                try:
                    await cursor.execute(stmt)
                    logger.debug(f"Executed: {stmt[:50]}...")  # 显示前50个字符
                except aiomysql.Error as e:
                    logger.error(f"Error executing statement: {e}\nStatement: {stmt}")
                    await conn.rollback()  # 回滚当前事务
                    break
            await conn.commit()
    except Exception as e:
        logger.error(f"Error executing SQL file: {e}")
    finally:
        conn.close()


async def main(input_args):
    db_config = {
        "host": f"{input_args.host}",
        "port": input_args.port,
        "user": f"{input_args.user}",
        "password": f"{input_args.password}",
        "db": f"{input_args.database}"
    }
    insert_sql = f"""
    INSERT INTO `bot` VALUES (1, {input_args.qq}, 180864557);
    INSERT INTO `dynamic_update` VALUES ('00000000-0000-0000-0000-000000000000', 180864557, 0, '冷月丶残星丶发送了动态');
    INSERT INTO `live_off` VALUES ('00000000-0000-0000-0000-000000000000', 180864557, 0, '冷月丶残星丶直播结束了');
    INSERT INTO `live_on` VALUES ('00000000-0000-0000-0000-000000000000', 180864557, 0, '冷月丶残星丶正在直播');
    INSERT INTO `live_report` VALUES ('00000000-0000-0000-0000-000000000000', 180864557, 0, '', '', 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0);
    INSERT INTO `targets` VALUES ('00000000-0000-0000-0000-000000000000', 180864557, 799915082, 0000000001, '冷月丶残星丶', 7260744);
    """
    if not input_args.onlystruct and input_args.qq == 0:
        logger.warning("需要QQ号，请添加--qq参数指定qq号，例如--qq 123456789")
        return
    db_check_result = await check_db_connection(db_config)
    if not db_check_result:
        logger.error(f"数据库连接失败")
        return
    logger.info(f"数据库连接成功")
    logger.info(f"若不存在数据库 {input_args.database} 则创建...")
    await create_database(db_config)
    logger.info(f"开始表结构初始化...")
    await execute_sql(db_config, starbot_sql)
    if not input_args.onlystruct:
        logger.info(f"写入占位数据...")
        await execute_sql(db_config, insert_sql)
    else:
        logger.info(f"添加了--onlystruct标记，跳过写入占位数据")
    if input_args.onlystruct:
        logger.success("^_^数据库初始化已完成，当前mysql订阅源为空")
    else:
        logger.success(f"^_^数据库初始化已完成，已基于botqq号{input_args.qq}写入一条占位数据")


if __name__ == "__main__":
    logger_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<level>{message}</level>"
    )
    logger.remove()
    logger.add(sys.stderr, format=logger_format, level="DEBUG")
    # 创建参数解析器
    parser = argparse.ArgumentParser(description="starbot_mysql_plugin数据库初始化工具")
    parser.add_argument("--qq", type=int, help="qq号，未添加--onlystruct参数时必填", default=0)
    parser.add_argument("--host", type=str, help="mysql host[默认127.0.0.1]", default="127.0.0.1")
    parser.add_argument("--user", type=str, help="mysql username[默认root]", default="root")
    parser.add_argument("--password", type=str, help="mysql password[默认123456]", default="123456")
    parser.add_argument("--port", type=int, help="mysql port[默认3306]", default=3306)
    parser.add_argument("--database", type=str, help="mysql db[默认starbot]", default="starbot")
    parser.add_argument("--onlystruct", action="store_true", help="mysql仅初始化结构", default=False)

    # 解析参数并运行
    args = parser.parse_args()
    loop = asyncio.new_event_loop()
    loop.run_until_complete(main(args))
