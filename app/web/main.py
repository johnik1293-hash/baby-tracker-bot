from __future__ import annotations
import os
from pathlib import Path

from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from aiogram.types import Update

from app.bot.runner import build_bot, build_dispatcher, setup_logging

BASE_DIR = Path(__file__).resolve().parent  # .../app/web

app = FastAPI(title="Baby Tracker WebApp")

# Статика и шаблоны по абсолютным путям
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# ---------- aiogram: bot/dispatcher ----------
setup_logging()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
WEBHOOK_URL       = os.getenv("WEBHOOK_URL", "").strip().rstrip("/")   # например: https://baby-tracker-web.onrender.com
WEBHOOK_SECRET    = os.getenv("WEBHOOK_SECRET", "").strip()            # любой секрет, необязательно

bot = build_bot(TELEGRAM_BOT_TOKEN) if TELEGRAM_BOT_TOKEN else None
dp  = build_dispatcher()

@app.on_event("startup")
async def on_startup():
    # Регистрируем вебхук в Telegram
    if not bot:
        return
    if not WEBHOOK_URL:
        return
    await bot.set_webhook(
        url=f"{WEBHOOK_URL}/webhook/telegram",
        secret_token=(WEBHOOK_SECRET or None),
        drop_pending_updates=True,
    )

@app.on_event("shutdown")
async def on_shutdown():
    if bot:
        await bot.delete_webhook(drop_pending_updates=False)

# ---------- WebApp страницы ----------
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "app_title": "Baby Tracker Mini App"}
    )

@app.get("/health")
async def health():
    return {"status": "ok"}

# ---------- Вебхук от Telegram ----------
@app.post("/webhook/telegram")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
):
    # Если задан секрет — проверяем
    if WEBHOOK_SECRET and x_telegram_bot_api_secret_token != WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="invalid secret")

    data = await request.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return JSONResponse({"ok": True})
