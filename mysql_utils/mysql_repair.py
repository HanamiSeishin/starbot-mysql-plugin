import asyncio
import aiomysql
import argparse
import sys

from loguru import logger


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
    alter_sql = f"""
    ALTER TABLE `dynamic_update` MODIFY COLUMN `message` LONGTEXT;
    ALTER TABLE `live_off` MODIFY COLUMN `message` LONGTEXT;
    ALTER TABLE `live_on` MODIFY COLUMN `message` LONGTEXT;
    ALTER TABLE `live_report` MODIFY COLUMN `logo` LONGTEXT;
    ALTER TABLE `live_report` MODIFY COLUMN `logo_base64` LONGTEXT;
    ALTER TABLE `targets` MODIFY COLUMN `uname` LONGTEXT;
    """
    db_check_result = await check_db_connection(db_config)
    if not db_check_result:
        logger.error(f"数据库连接失败")
        return
    logger.info(f"数据库连接成功")
    logger.info(f"开始表结构修复")
    await execute_sql(db_config, alter_sql)
    logger.success("^_^数据库表结构修复完成")


if __name__ == "__main__":
    logger_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<level>{message}</level>"
    )
    logger.remove()
    logger.add(sys.stderr, format=logger_format, level="DEBUG")
    # 创建参数解析器
    parser = argparse.ArgumentParser(description="starbot_mysql_plugin数据库结构修复工具，用于修复表结构部分字段长度过短的问题")
    parser.add_argument("--host", type=str, help="mysql host[默认127.0.0.1]", default="127.0.0.1")
    parser.add_argument("--user", type=str, help="mysql username[默认root]", default="root")
    parser.add_argument("--password", type=str, help="mysql password[默认123456]", default="123456")
    parser.add_argument("--port", type=int, help="mysql port[默认3306]", default=3306)
    parser.add_argument("--database", type=str, help="mysql db[默认starbot]", default="starbot")

    # 解析参数并运行
    args = parser.parse_args()
    loop = asyncio.new_event_loop()
    loop.run_until_complete(main(args))
