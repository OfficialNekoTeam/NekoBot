"""NekoBot 入口文件

启动基于 Quart 框架的 NekoBot 服务器
"""

from loguru import logger
import sys
import asyncio
import argparse

logger.remove()
logger.add(
    sys.stdout,
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} <level>[{level}]</level> {message}",
    level="DEBUG",
    colorize=True,
)


async def reset_password(username: str, new_password: str):
    """重置用户密码"""
    from packages.backend.auth.user import reset_user_password

    if reset_user_password(username, new_password):
        logger.info(f"用户 {username} 的密码已成功重置")
        return 0
    else:
        logger.error(f"重置用户 {username} 的密码失败")
        return 1


async def main():
    """主函数：启动 NekoBot 服务器或执行命令行操作"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="NekoBot 命令行工具")
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # 启动服务器命令
    start_parser = subparsers.add_parser("start", help="启动 NekoBot 服务器")

    # 重置密码命令
    reset_parser = subparsers.add_parser("reset-password", help="重置用户密码")
    reset_parser.add_argument("username", help="要重置密码的用户名")
    reset_parser.add_argument("new_password", help="新密码")

    args = parser.parse_args()

    if args.command == "reset-password":
        # 执行密码重置
        return await reset_password(args.username, args.new_password)
    else:
        # 启动服务器
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
