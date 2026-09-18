"""Thin Telegram bot: /start + Menu Web App button."""

import asyncio
import logging

from aiogram import Bot, Dispatcher, Router
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.filters import CommandStart
from aiogram.types import MenuButtonWebApp, Message, WebAppInfo

from app.core.config import settings
from app.core.proxy import apply_internal_no_proxy, get_outbound_proxy_url

logger = logging.getLogger(__name__)
router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    logger.info("Received /start from telegram_user_id=%s", message.from_user.id if message.from_user else None)
    webapp_url = settings.telegram_web_app_url.strip()
    lines = [
        "Prompt DJ — опиши настроение, плейлист появится в Яндекс Музыке.",
        "Вход через Яндекс (Device Flow), как на сайте.",
    ]
    if webapp_url:
        lines.append("")
        lines.append(f"Mini App: {webapp_url}")
    await message.answer("\n".join(lines))


async def _configure_menu(bot: Bot) -> None:
    webapp_url = settings.telegram_web_app_url.strip()
    if not webapp_url:
        logger.warning("TELEGRAM_WEB_APP_URL is empty; menu Web App button not set")
        return
    try:
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(text="Prompt DJ", web_app=WebAppInfo(url=webapp_url)),
        )
    except Exception as exc:
        logger.warning("set_chat_menu_button failed (%s); polling will still start", exc)


def _bot_session() -> AiohttpSession:
    if settings.telegram_bot_use_proxy:
        proxy = get_outbound_proxy_url()
        if proxy:
            logger.info("Telegram bot using outbound proxy")
            return AiohttpSession(proxy=proxy)
    else:
        logger.info("Telegram bot: proxy disabled (TELEGRAM_BOT_USE_PROXY=false)")
    return AiohttpSession()


async def run_bot() -> None:
    apply_internal_no_proxy()
    token = settings.tg_bot_token.strip()
    if not token:
        logger.error("TG_BOT_TOKEN is not set; bot process exiting")
        return

    logging.basicConfig(level=logging.INFO)
    session = _bot_session()
    bot = Bot(token=token, session=session)
    dp = Dispatcher()
    dp.include_router(router)
    try:
        try:
            me = await bot.get_me()
            logger.info("Telegram API ok, bot @%s (id=%s)", me.username, me.id)
        except Exception as exc:
            logger.error(
                "Cannot reach Telegram API (%s). "
                "If proxy times out, set TELEGRAM_BOT_USE_PROXY=false or run bot outside Docker.",
                exc,
            )
            return
        asyncio.create_task(_configure_menu(bot))
        logger.info("Telegram bot polling started")
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


def main() -> None:
    asyncio.run(run_bot())


if __name__ == "__main__":
    main()
