from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from fastapi import FastAPI, Request, Header, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from aiogram.types import Update
from sqlalchemy.exc import SQLAlchemyError

from app.bot.runner import build_bot, build_dispatcher, setup_logging
from app.db.database import async_engine  # см. свои пути, если отличаются
from app.db.models import Base            # здесь metadata всех таблиц

# ---------------------- Базовая настройка FastAPI ----------------------
BASE_DIR = Path(__file__).resolve().parent  # .../app/web
app = FastAPI(title="Baby Tracker WebApp")

# Статика и шаблоны по абсолютным путям
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# ---------------------- Логирование ----------------------
setup_logging()
logger = logging.getLogger(__name__)

# ---------------------- Переменные окружения ----------------------
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").strip()              # БЕЗ завершающего '/'
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "").strip()

# ---------------------- aiogram: Bot & Dispatcher ----------------------
bot = build_bot(TELEGRAM_BOT_TOKEN) if TELEGRAM_BOT_TOKEN else None
dp = build_dispatcher()

# Целевой URL вебхука (заполним на старте)
TARGET_WEBHOOK: str | None = None


# ---------------------- Вспомогательные функции ----------------------
async def set_webhook_with_retry() -> None:
    """
    Ставит (или пере-ставляет) вебхук с повторами.
    Работает и если хук уже стоит — тогда просто ничего не меняет.
    """
    assert bot is not None and TARGET_WEBHOOK
    delay = 1
    for attempt in range(1, 6):  # до 5 попыток: 1, 2, 4, 8, 16 сек
        try:
            info = await bot.get_webhook_info()
            if info.url != TARGET_WEBHOOK:
                await bot.set_webhook(
                    url=TARGET_WEBHOOK,
                    secret_token=(WEBHOOK_SECRET or None),
                    drop_pending_updates=False,  # не теряем ожидающие апдейты
                    allowed_updates=["message", "callback_query"],
                )
                logger.info("Webhook set to %s", TARGET_WEBHOOK)
            else:
                logger.info("Webhook already ok: %s", TARGET_WEBHOOK)
            return
        except Exception as e:  # noqa: BLE001
            logger.exception("set_webhook attempt %s failed: %s", attempt, e)
            await asyncio.sleep(delay)
            delay *= 2
    logger.error("Failed to set webhook after retries")


async def webhook_keeper() -> None:
    """
    Фоновая задача: каждые 10 минут проверяет и чинит вебхук.
    Нужна на бесплатных хостингах, где инстанс может перезапускаться.
    """
    while True:
        try:
            await set_webhook_with_retry()
        except Exception as e:  # noqa: BLE001
            logger.exception("webhook_keeper error: %s", e)
        await asyncio.sleep(600)  # 10 минут


# ---------------------- Хуки жизненного цикла ----------------------
@app.on_event("startup")
async def on_startup() -> None:
    # 1) Создаём таблицы в БД (SQLite/Postgres) если их ещё нет
    try:
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("DB schema is ready.")
    except SQLAlchemyError:
        logger.exception("DB init failed")
        raise

    # 2) Ставим вебхук + запускаем сторожа
    if bot and WEBHOOK_URL:
        global TARGET_WEBHOOK
        TARGET_WEBHOOK = f"{WEBHOOK_URL.rstrip('/')}/webhook/telegram"
        await set_webhook_with_retry()
        app.state.webhook_task = asyncio.create_task(webhook_keeper())
    else:
        logger.warning("Bot token or WEBHOOK_URL is empty; webhook will not be set.")


@app.on_event("shutdown")
async def on_shutdown() -> None:
    # НИЧЕГО НЕ УДАЛЯЕМ: не трогаем webhook на выключении,
    # чтобы он не очищался при перезапусках на хостинге.
    pass


# ---------------------- Маршруты WebApp ----------------------
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "app_title": "Baby Tracker Mini App"},
    )


@app.get("/health")
async def health():
    return {"status": "ok"}


# ---------------------- Вебхук Telegram ----------------------
@app.post("/webhook/telegram")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
):
    # Проверка секрета (если задан)
    if WEBHOOK_SECRET and x_telegram_bot_api_secret_token != WEBHOOK_SECRET:
        # Если нужно диагностировать — можно заменить на warning и пропуск,
        # но в продакшене лучше 403:
        raise HTTPException(status_code=403, detail="invalid secret")

    data = await request.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return JSONResponse({"ok": True})


# ---------------------- Вспомогательный debug-эндпойнт (опционально) ----------------------
@app.get("/debug/ping")
async def debug_ping(chat_id: int = Query(...), text: str = Query("ping")):
    """
    Быстрый тест отправки сообщения ботом.
    УДАЛИТЕ в проде или защитите авторизацией.
    """
    if not bot:
        raise HTTPException(status_code=500, detail="Bot is not configured")
    from aiogram.exceptions import TelegramBadRequest
    try:
        await bot.send_message(chat_id=chat_id, text=f"🔔 {text}")
        return {"ok": True}
    except TelegramBadRequest as e:
        logger.exception("send_message failed")
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------- Ручной сброс вебхука (опционально) ----------------------
@app.post("/admin/reset-webhook")
async def reset_webhook(authorization: str | None = Header(None)):
    """
    Позволяет вручную переустановить вебхук:
    curl -X POST https://<домен>/admin/reset-webhook \
      -H "Authorization: Bearer <WEBHOOK_SECRET>"
    """
    if not WEBHOOK_SECRET or authorization != f"Bearer {WEBHOOK_SECRET}":
        raise HTTPException(status_code=403, detail="forbidden")
    if not bot or not TARGET_WEBHOOK:
        raise HTTPException(status_code=500, detail="bot or webhook url is not ready")
    await set_webhook_with_retry()
    return {"ok": True, "url": TARGET_WEBHOOK}
