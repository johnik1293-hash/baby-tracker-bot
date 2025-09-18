# app/bot/runner.py
from __future__ import annotations
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

# Импорты роутеров
from app.bot.handlers.start import router as start_router
from app.bot.handlers.help import router as help_router
from app.bot.handlers.menu import router as menu_router
from app.bot.handlers.reminders import router as reminders_router
from app.bot.handlers.sleep import router as sleep_router
from app.bot.handlers.feeding import router as feeding_router
from app.bot.handlers.health import router as health_router
from app.bot.handlers.stats import router as stats_router

def build_dispatcher() -> Dispatcher:
    from aiogram.fsm.storage.memory import MemoryStorage
    dp = Dispatcher(storage=MemoryStorage())

    # Порядок важен: reminders раньше menu
    dp.include_router(start_router)
    dp.include_router(help_router)
    dp.include_router(reminders_router)
    dp.include_router(menu_router)
    dp.include_router(sleep_router)
    dp.include_router(feeding_router)
    dp.include_router(health_router)
    dp.include_router(stats_router)
    return dp

def build_bot(token: str) -> Bot:
    # aiogram >= 3.7: parse_mode через DefaultBotProperties
    return Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )
