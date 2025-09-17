from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)

def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text='Сон'), KeyboardButton(text='Кормление')],
            [KeyboardButton(text='Здоровье'), KeyboardButton(text='Статистика')],
            [KeyboardButton(text='Профиль ребёнка'), KeyboardButton(text='Настройки')],
            [KeyboardButton(text='Помощь')],
            [KeyboardButton(text='Мини-приложение')],

        ],
        resize_keyboard=True,
    )

def sleep_inline_quality_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Отлично 😴", callback_data="quality_good"),
            InlineKeyboardButton(text="Нормально 🙂", callback_data="quality_ok"),
            InlineKeyboardButton(text="Беспокойно 😕", callback_data="quality_bad"),
        ]
    ])
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

def webapp_open_kb(url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Открыть мини-приложение", web_app=WebAppInfo(url=url))
    ]])
