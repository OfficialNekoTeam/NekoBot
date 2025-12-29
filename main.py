"""NekoBot 入口文件

启动基于 Quart 框架的 NekoBot 服务器
"""

from loguru import logger
import sys
import asyncio
import argparse
import getpass

logger.remove()
logger.add(
    sys.stdout,
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} <level>[{level}]</level> {message}",
    level="DEBUG",
    colorize=True,
)


async def reset_password():
    """重置用户密码"""
    from packages.backend.auth.user import reset_user_password

    print("请输入新密码：")
    password1 = getpass.getpass("密码: ")
    password2 = getpass.getpass("确认密码: ")

    if password1 != password2:
        logger.error("两次输入的密码不一致，重置失败")
        return 1

    if not password1:
        logger.error("密码不能为空，重置失败")
        return 1

    if reset_user_password("nekobot", password1):
        logger.info("密码已成功重置")
        return 0
    else:
        logger.error("密码重置失败")
        return 1


async def main():
    """主函数：启动 NekoBot 服务器或执行命令行操作"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="NekoBot 命令行工具")
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # 重置密码命令
    reset_parser = subparsers.add_parser("reset-password", help="重置用户密码")

    args = parser.parse_args()

    if args.command == "reset-password":
        # 执行密码重置
        return await reset_password()
    else:
        # 默认启动服务器
        logger.info("启动 NekoBot...")

        # 导入 Quart 应用
        from packages.backend.app import run_app

        # 启动 Quart 应用
        await run_app()


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code if exit_code is not None else 0)
    except KeyboardInterrupt:
        logger.info("收到退出信号，正在关闭服务器...")
    except Exception as e:
        logger.error(f"操作失败: {e}")
        sys.exit(1)
