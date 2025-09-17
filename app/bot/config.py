import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class BotConfig:
    token: str = os.getenv("BOT_TOKEN", "")
    parse_mode: str = "HTML"

@dataclass(frozen=True)
class Config:
    bot: BotConfig = field(default_factory=BotConfig)

def get_config() -> Config:
    cfg = Config()
    if not cfg.bot.token:
        raise RuntimeError("BOT_TOKEN is empty. Put it into .env")
    return cfg