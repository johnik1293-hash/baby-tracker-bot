from aiogram import Router, types
from aiogram.filters import Command

router = Router(name="help")

@router.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "Помощь:\n"
        "/start — главное меню\n"
        "/help — эта подсказка\n\n"
        "Нажимай кнопки на клавиатуре, чтобы перейти в разделы."
    )
