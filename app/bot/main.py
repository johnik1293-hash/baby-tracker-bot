import asyncio
import logging
from contextlib import suppress

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from app.bot.handlers.stats import router as stats_router
from app.bot.handlers.webapp import router as webapp_router

from app.bot.config import get_config
from app.utils.logging import setup_logging
from app.db.database import init_db

# Routers
from app.bot.handlers.start import router as start_router
from app.bot.handlers.help import router as help_router
from app.bot.handlers.menu import router as menu_router
from app.bot.handlers.profile import router as profile_router
from app.bot.handlers.sleep import router as sleep_router
from app.bot.handlers.feeding import router as feeding_router
from app.bot.handlers.health import router as health_router
from app.bot.handlers.reminders import router as reminders_router

# Reminders worker
from app.bot.reminders_worker import reminders_worker


async def _on_startup(bot: Bot):
    me = await bot.get_me()
    logging.info("Bot started as @%s", me.username)


async def _on_shutdown(bot: Bot):
    logging.info("Bot is shutting down…")


def build_dispatcher() -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(start_router)
    dp.include_router(help_router)

    # Важно: reminders раньше menu
    dp.include_router(reminders_router)

    dp.include_router(menu_router)
    dp.include_router(profile_router)
    dp.include_router(sleep_router)
    dp.include_router(feeding_router)
    dp.include_router(health_router)
    dp.include_router(stats_router)
    return dp


async def run_polling():
    setup_logging("INFO")
    cfg = get_config()

    # Инициализация БД
    await init_db()

    bot = Bot(
        token=cfg.bot.token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = build_dispatcher()

    # Фоновый воркер напоминаний
    stop_event = asyncio.Event()
    worker_task = asyncio.create_task(reminders_worker(bot, stop_event))

    dp.startup.register(_on_startup)
    dp.shutdown.register(_on_shutdown)

    with suppress(Exception):
        await bot.delete_webhook(drop_pending_updates=True)

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        stop_event.set()
        try:
            await worker_task
        except Exception:
            pass
        await bot.session.close()


def main():
    asyncio.run(run_polling())


if __name__ == "__main__":
    main()
