from __future__ import annotations

import os
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext  # <-- добавили
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo,
)

from app.bot.keyboards.common import main_menu_kb
from app.bot.handlers.family import family_menu
from app.bot.handlers.calendar import calendar_last
from app.bot.handlers.children import children_entry  # <-- используем entry

router = Router(name="menu")

# Тексты кнопок (точно как в клавиатуре)
BTN_SLEEP = "🛌 Сон"
BTN_FEED = "🍼 Кормление"
BTN_CHILD = "👶 Профиль ребёнка"
BTN_FAMILY = "👨‍👩‍👧 Семья"
BTN_CALENDAR = "📅 Календарь"
BTN_SETTINGS = "⚙️ Настройки"
BTN_MAIN = "Главное меню"

# --- Раздел «Сон» ---
@router.message(F.text.in_({BTN_SLEEP, "Сон"}))
async def section_sleep(message: types.Message):
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Начал спать"), KeyboardButton(text="Проснулся")],
            [KeyboardButton(text="Статистика сна"), KeyboardButton(text=BTN_MAIN)],
        ],
        resize_keyboard=True,
    )
    await message.answer("Трекер сна.\nВыбери действие:", reply_markup=kb)

# --- Раздел «Кормление» ---
@router.message(F.text.in_({BTN_FEED, "Кормление"}))
async def section_feeding(message: types.Message):
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Грудное молоко"), KeyboardButton(text="Смесь")],
            [KeyboardButton(text="Прикорм"), KeyboardButton(text="Вода")],
            [KeyboardButton(text="Статистика кормления"), KeyboardButton(text=BTN_MAIN)],
        ],
        resize_keyboard=True,
    )
    await message.answer("Трекер кормления.\nВыбери действие:", reply_markup=kb)

# --- Профиль ребёнка ---
@router.message(F.text.in_({BTN_CHILD, "Профиль ребёнка"}))
async def open_children_via_button(message: types.Message, state: FSMContext):  # <-- принимаем state
    await children_entry(message, state)  # <-- передаём state дальше

# --- Раздел «Здоровье» (если используешь) ---
@router.message(F.text.in_({"Здоровье"}))
async def section_health(message: types.Message):
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Температура"), KeyboardButton(text="Лекарства")],
            [KeyboardButton(text="Визит к врачу"), KeyboardButton(text="Рост/Вес")],
            [KeyboardButton(text="Статистика здоровья"), KeyboardButton(text=BTN_MAIN)],
        ],
        resize_keyboard=True,
    )
    await message.answer("Дневник здоровья.\nВыбери действие:", reply_markup=kb)

# --- Календарь (семейный журнал) ---
@router.message(F.text.in_({BTN_CALENDAR, "Календарь"}))
async def open_calendar_via_button(message: types.Message):
    await calendar_last(message)

# --- Семья (создать/присоединиться) ---
@router.message(F.text.in_({BTN_FAMILY, "Семья"}))
async def open_family_via_button(message: types.Message):
    await family_menu(message)

# --- Настройки ---
@router.message(F.text.in_({BTN_SETTINGS, "Настройки"}))
async def section_settings(message: types.Message):
    await message.answer("Здесь будут настройки напоминаний и уведомлений. ⚙️")

# --- Кнопка «Главное меню» ---
@router.message(F.text == BTN_MAIN)
async def back_to_main(message: types.Message):
    await message.answer("Главное меню. Выбери раздел:", reply_markup=main_menu_kb())

# --- (опционально) Мини-приложение ---
WEBAPP_URL = os.getenv("WEBAPP_URL", "").strip()

def webapp_open_kb(url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Открыть мини-приложение", web_app=WebAppInfo(url=url))
    ]])

@router.message(F.text == "Мини-приложение")
async def open_mini_app(message: types.Message):
    if not WEBAPP_URL or not WEBAPP_URL.startswith("https://"):
        await message.answer("⚠️ WebApp URL не задан или не HTTPS. Укажи переменную окружения WEBAPP_URL.")
        return
    await message.answer("Открой мини-приложение 👇", reply_markup=webapp_open_kb(WEBAPP_URL))
