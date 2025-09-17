from aiogram import Router, types
from aiogram.filters import CommandStart
from app.bot.keyboards.common import main_menu_kb

router = Router(name="start")

@router.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer(
        "Привет! 👋\n\n"
        "Это Baby Tracker — помогу вести режим малыша:\n"
        "• Сон и кормления\n• Здоровье и лекарства\n• Аналитика и напоминания\n\n"
        "Выбери раздел из меню ниже:",
        reply_markup=main_menu_kb()
    )
