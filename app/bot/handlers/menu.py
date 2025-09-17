from aiogram import Router, F, types
from app.bot.keyboards.common import main_menu_kb
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

router = Router(name="menu")


@router.message(F.text == "Сон")
async def section_sleep(message: types.Message):
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Начал спать"), KeyboardButton(text="Проснулся")],
            [KeyboardButton(text="Статистика сна"), KeyboardButton(text="Главное меню")],
        ],
        resize_keyboard=True,
    )
    await message.answer("Трекер сна.\nВыбери действие:", reply_markup=kb)


@router.message(F.text == "Кормление")
async def section_feeding(message: types.Message):
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Грудное молоко"), KeyboardButton(text="Смесь")],
            [KeyboardButton(text="Прикорм"), KeyboardButton(text="Вода")],
            [KeyboardButton(text="Статистика кормления"), KeyboardButton(text="Главное меню")],
        ],
        resize_keyboard=True,
    )
    await message.answer("Трекер кормления.\nВыбери действие:", reply_markup=kb)


@router.message(F.text == "Здоровье")
async def section_health(message: types.Message):
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Температура"), KeyboardButton(text="Лекарства")],
            [KeyboardButton(text="Визит к врачу"), KeyboardButton(text="Рост/Вес")],
            [KeyboardButton(text="Статистика здоровья"), KeyboardButton(text="Главное меню")],
        ],
        resize_keyboard=True,
    )
    await message.answer("Дневник здоровья.\nВыбери действие:", reply_markup=kb)


@router.message(F.text == "Статистика")
async def section_stats(message: types.Message):
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(text="Сон: 7 дней", callback_data="stats_sleep_7d"),
            types.InlineKeyboardButton(text="Кормление: 7 дней", callback_data="stats_feed_7d"),
        ],
    ])
    await message.answer("Выбери график:", reply_markup=kb)


@router.message(F.text == "Помощь")
async def section_help(message: types.Message):
    await message.answer("Напиши /help для списка команд.")


@router.message(F.text == "Главное меню")
async def back_to_main(message: types.Message):
    await message.answer("Главное меню. Выбери раздел:", reply_markup=main_menu_kb())
from app.bot.keyboards.common import main_menu_kb, webapp_open_kb

import os
from aiogram import Router, F, types
from app.bot.keyboards.common import main_menu_kb, webapp_open_kb

WEBAPP_URL = os.getenv("WEBAPP_URL", "").strip()

@router.message(F.text == "Мини-приложение")
async def open_mini_app(message: types.Message):
    if not WEBAPP_URL or not WEBAPP_URL.startswith("https://"):
        await message.answer("⚠️ WebApp URL не задан или не HTTPS. Укажи WEBAPP_URL в .env")
        return
    await message.answer("Открой мини-приложение 👇", reply_markup=webapp_open_kb(WEBAPP_URL))
