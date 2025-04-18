import asyncio
import datetime
import os

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



async def execute_sql(db_config, sql_file_path):
    """执行SQL文件"""
    # 1. 读取 SQL 文件
    with open(sql_file_path, "r", encoding="utf-8") as f:
        sql_content = f.read()

    # 2. 分割并清理 SQL 语句
    statements = []
    for line in sql_content.split(';'):
        line = line.strip()
        # 过滤空行和注释
        if not line or line.startswith('--') or line.startswith('/*'):
            continue
        statements.append(line)

    # 连接到目标数据库
    conn = await aiomysql.connect(
        host=db_config["host"],
        port=db_config["port"],
        user=db_config["user"],
        password=db_config["password"],
        db=db_config["db"]
    )

    try:
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


async def export_to_sql(db_config, force_flag):
    # 连接配置
    conn = await aiomysql.connect(
        host=db_config["host"],
        port=db_config["port"],
        user=db_config["user"],
        password=db_config["password"],
        db=db_config["db"]
    )

    # 获取所有表名
    async with conn.cursor() as cursor:
        await cursor.execute("SHOW TABLES")
        tables = [row[0] for row in await cursor.fetchall()]

    # 创建备份文件（按时间戳命名）
    backup_file = f"{db_config['db']}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"

    with open(backup_file, "w", encoding="utf-8") as f:
        # 写入 SQL 文件头
        f.write("SET FOREIGN_KEY_CHECKS=0;\n")

        for table in tables:
            if not force_flag and table not in ["bot", "dynamic_update", "live_off", "live_on", "live_report", "targets"]:
                logger.debug(f"跳过处理表({table})")
                continue
            logger.debug(f"正在读取表({table})")
            # 1. 导出表结构
            async with conn.cursor() as cursor:
                await cursor.execute(f"SHOW CREATE TABLE `{table}`")
                create_table_sql = (await cursor.fetchone())[1]
                f.write(f"DROP TABLE IF EXISTS `{table}`;\n")
                f.write(f"{create_table_sql};\n")

            # 2. 导出数据（分页查询）
            page_size = 1000  # 每页数据量
            offset = 0
            while True:
                async with conn.cursor() as cursor:
                    await cursor.execute(f"SELECT * FROM `{table}` LIMIT {offset}, {page_size}")
                    rows = await cursor.fetchall()

                    if not rows:
                        break

                    # 生成 INSERT 语句
                    columns = [col[0] for col in cursor.description]
                    insert_head = f"INSERT INTO `{table}` (`{'`,`'.join(columns)}`) VALUES\n"
                    values = []

                    for row in rows:
                        # 处理特殊字符转义
                        escaped_row = [str(item).replace("'", "''") if item is not None else 'NULL' for item in row]
                        escaped_row = [f"'{item}'" if item != 'NULL' else 'NULL' for item in escaped_row]
                        values.append(f"({','.join(escaped_row)})")

                    f.write(insert_head + ",\n".join(values) + ";\n")

                    offset += page_size

        f.write("SET FOREIGN_KEY_CHECKS=1;")

    conn.close()
    return backup_file


async def main(input_args):
    db_config = {
        "host": f"{input_args.host}",
        "port": input_args.port,
        "user": f"{input_args.user}",
        "password": f"{input_args.password}",
        "db": f"{input_args.database}"
    }
    sql_file = input_args.file
    backup_flag = input_args.backup
    force_flag = input_args.forceall
    if backup_flag and sql_file:
        logger.warning(f"--backup和--file [sql]不能同时存在")
        return
    if not backup_flag and not sql_file:
        logger.warning(f"缺少--backup或--file [sql]")
        return
    if not backup_flag:
        if not os.path.exists(sql_file):
            logger.error(f"sql文件不存在")
            return
        logger.warning(f"高危操作，即将通过sql文件写入mysql数据库，请确保sql文件来源可靠且可控")

    db_check_result = await check_db_connection(db_config)
    if not db_check_result:
        logger.error(f"数据库连接失败")
        return
    logger.info(f"数据库连接成功")

    if backup_flag:
        logger.info(f"正在将数据库导出为sql文件")
        file_name = await export_to_sql(db_config, force_flag)
        logger.success(f"^_^数据库备份完成，保存为{file_name}，自带强制重新建表语句和数据插入语句，请谨慎使用")
    else:
        if force_flag:
            logger.info(f"写入数据库模式下--forceall参数不生效")
        logger.info(f"正在读取sql文件并向数据库写入数据")
        await execute_sql(db_config, sql_file)
        logger.success(f"^_^数据库写入完成")




if __name__ == "__main__":
    logger_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<level>{message}</level>"
    )
    logger.remove()
    logger.add(sys.stderr, format=logger_format, level="DEBUG")
    # 创建参数解析器
    parser = argparse.ArgumentParser(description="starbot_mysql_plugin数据库备份和恢复工具")
    parser.add_argument("--backup", action="store_true", help="备份为sql文件", default=False)
    parser.add_argument("--file", type=str, help="使用sql文件导入数据库", default="")
    parser.add_argument("--forceall", action="store_true", help="强制备份数据库下所有表，执行sql时将不保证一定成功，默认关闭时仅备份starbot所需表", default=False)
    parser.add_argument("--host", type=str, help="mysql host[默认127.0.0.1]", default="127.0.0.1")
    parser.add_argument("--user", type=str, help="mysql username[默认root]", default="root")
    parser.add_argument("--password", type=str, help="mysql password[默认123456]", default="123456")
    parser.add_argument("--port", type=int, help="mysql port[默认3306]", default=3306)
    parser.add_argument("--database", type=str, help="mysql db[默认starbot]", default="starbot")

    # 解析参数并运行
    args = parser.parse_args()
    loop = asyncio.new_event_loop()
    loop.run_until_complete(main(args))
