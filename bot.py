import asyncio
import re
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import aiohttp

# Вставь сюда токен от @BotFather
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"

# API для скачивания TikTok (бесплатный сервис)
TIKTOK_API = "https://api.tiklydown.eu.org/api/download"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    await update.message.reply_text(
        "👋 Привет! Я бот для скачивания видео из TikTok.\n\n"
        "📱 Просто отправь мне ссылку на TikTok видео, и я скачаю его в максимальном качестве!\n\n"
        "Поддерживаются форматы:\n"
        "• vm.tiktok.com/...\n"
        "• vt.tiktok.com/...\n"
        "• www.tiktok.com/@.../video/...\n\n"
        "Работают видео и фото (слайдшоу)!"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /help"""
    await update.message.reply_text(
        "ℹ️ Как использовать:\n\n"
        "1. Открой TikTok\n"
        "2. Нажми 'Поделиться' на видео\n"
        "3. Скопируй ссылку\n"
        "4. Отправь её мне\n\n"
        "Я автоматически скачаю видео без водяного знака!"
    )

def extract_tiktok_url(text):
    """Извлекает ссылку TikTok из текста"""
    patterns = [
        r'https?://(?:vm|vt|www)\.tiktok\.com/\S+',
        r'https?://(?:www\.)?tiktok\.com/@[\w.-]+/video/\d+',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(0)
    return None

async def download_tiktok(url):
    """Скачивает видео через API"""
    try:
        async with aiohttp.ClientSession() as session:
            # Запрос к API
            params = {"url": url}
            async with session.get(TIKTOK_API, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Проверяем успешность
                    if data.get("status") == "success":
                        result = data.get("result", {})
                        
                        # Тип контента
                        content_type = result.get("type")
                        
                        if content_type == "video":
                            # Видео без водяного знака
                            video_url = result.get("video")
                            return {
                                "type": "video",
                                "url": video_url,
                                "title": result.get("title", "TikTok Video")
                            }
                        elif content_type == "image":
                            # Слайдшоу (фото)
                            images = result.get("images", [])
                            return {
                                "type": "images",
                                "urls": images,
                                "title": result.get("title", "TikTok Images")
                            }
                
                return None
    except Exception as e:
        print(f"Error: {e}")
        return None

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка сообщений с ссылками"""
    text = update.message.text
    url = extract_tiktok_url(text)
    
    if not url:
        await update.message.reply_text(
            "❌ Не нашел ссылку на TikTok.\n"
            "Отправь корректную ссылку!"
        )
        return
    
    # Уведомление о начале загрузки
    status_msg = await update.message.reply_text("⏳ Загружаю...")
    
    try:
        # Скачиваем
        result = await download_tiktok(url)
        
        if not result:
            await status_msg.edit_text(
                "❌ Не удалось скачать видео.\n"
                "Проверь ссылку или попробуй позже."
            )
            return
        
        if result["type"] == "video":
            # Отправляем видео
            await status_msg.edit_text("📤 Отправляю видео...")
            
            async with aiohttp.ClientSession() as session:
                async with session.get(result["url"]) as resp:
                    if resp.status == 200:
                        video_data = await resp.read()
                        
                        await update.message.reply_video(
                            video=video_data,
                            caption=f"✅ {result['title']}\n\n🎬 Без водяного знака",
                            filename="tiktok_video.mp4"
                        )
                        await status_msg.delete()
                    else:
                        await status_msg.edit_text("❌ Ошибка загрузки видео")
        
        elif result["type"] == "images":
            # Отправляем фото
            await status_msg.edit_text(f"📤 Отправляю {len(result['urls'])} фото...")
            
            async with aiohttp.ClientSession() as session:
                for i, img_url in enumerate(result["urls"][:10], 1):  # Максимум 10 фото
                    async with session.get(img_url) as resp:
                        if resp.status == 200:
                            img_data = await resp.read()
                            await update.message.reply_photo(
                                photo=img_data,
                                caption=f"📸 Фото {i}/{len(result['urls'])}"
                            )
            
            await status_msg.delete()
    
    except Exception as e:
        await status_msg.edit_text(
            f"❌ Произошла ошибка: {str(e)}\n"
            "Попробуй еще раз или отправь другую ссылку."
        )

def main():
    """Запуск бота"""
    # Проверка токена
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("⚠️ ВНИМАНИЕ! Замени YOUR_BOT_TOKEN_HERE на токен от @BotFather")
        return
    
    print("🤖 Запускаю бота...")
    
    # Создаем приложение
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Регистрируем обработчики
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Запускаем
    print("✅ Бот запущен!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
