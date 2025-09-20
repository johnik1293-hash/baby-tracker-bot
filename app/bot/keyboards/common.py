from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛌 Сон"), KeyboardButton(text="🍼 Кормление")],
            [KeyboardButton(text="👶 Профиль ребёнка"), KeyboardButton(text="📅 Календарь")],
            [KeyboardButton(text="👨‍👩‍👧 Семья"), KeyboardButton(text="⚙️ Настройки")],
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

def webapp_open_kb(url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Открыть мини-приложение", web_app=WebAppInfo(url=url))
    ]])
