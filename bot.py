import asyncio
import re
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import aiohttp
import json
from urllib.parse import quote

# Вставь сюда токен от @BotFather
BOT_TOKEN = "8410013565:AAHNYF-9HE7z7KMKxqeI_ZuMjK-W84J_0Rs"

# Альтернативные API для скачивания TikTok
APIS = [
    {
        "name": "TikWM",
        "url": "https://www.tikwm.com/api/",
        "method": "POST"
    },
    {
        "name": "SSSTik",
        "url": "https://ssstik.io/abc",
        "method": "POST"
    }
]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    await update.message.reply_text(
        "👋 Привет! Я бот для скачивания видео из TikTok.\n\n"
        "📱 Просто отправь мне ссылку на TikTok видео, и я:\n"
        "• Скачаю видео в максимальном качестве без водяных знаков\n"
        "• Скачаю все фото из слайдшоу одной группой\n"
        "• Извлеку музыку и дам возможность найти полный трек\n\n"
        "Поддерживаются форматы:\n"
        "• vm.tiktok.com/...\n"
        "• vt.tiktok.com/...\n"
        "• www.tiktok.com/@.../video/..."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /help"""
    await update.message.reply_text(
        "ℹ️ Как использовать:\n\n"
        "1. Открой TikTok\n"
        "2. Нажми 'Поделиться' на видео\n"
        "3. Скопируй ссылку\n"
        "4. Отправь её мне\n\n"
        "Я автоматически:\n"
        "✅ Скачаю видео без водяного знака\n"
        "✅ Скачаю все фото группой\n"
        "✅ Извлеку музыку с кнопками для поиска трека"
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

async def send_music(update: Update, result: dict):
    """Отправляет музыку из TikTok видео с кнопками поиска"""
    try:
        music_info = result.get("music_info")
        if not music_info:
            print("⚠️ No music info available")
            return
        
        music_url = music_info.get("play")
        music_title = music_info.get("title", "Unknown Track")
        music_author = music_info.get("author", "Unknown Artist")
        
        if not music_url:
            print("⚠️ No music URL available")
            return
        
        print(f"🎵 Extracting music: {music_title} - {music_author}")
        
        # Скачиваем аудио
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://www.tiktok.com/'
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                music_url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=60)
            ) as resp:
                if resp.status in [200, 206]:
                    audio_data = await resp.read()
                    
                    # Проверяем размер
                    size_mb = len(audio_data) / (1024 * 1024)
                    print(f"🎵 Audio downloaded: {size_mb:.2f} MB")
                    
                    # Создаем кнопки для поиска трека
                    search_query = f"{music_title} {music_author}".replace("original sound - ", "")
                    encoded_query = quote(search_query)
                    
                    keyboard = [
                        [
                            InlineKeyboardButton("🔍 Найти в Spotify", url=f"https://open.spotify.com/search/{encoded_query}"),
                            InlineKeyboardButton("📺 Найти в YouTube", url=f"https://www.youtube.com/results?search_query={encoded_query}")
                        ],
                        [
                            InlineKeyboardButton("🎵 Найти в Apple Music", url=f"https://music.apple.com/search?term={encoded_query}"),
                            InlineKeyboardButton("🔊 Shazam", url=f"https://www.shazam.com/search?query={encoded_query}")
                        ]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    # Отправляем аудио
                    await update.message.reply_audio(
                        audio=audio_data,
                        title=music_title[:100],
                        performer=music_author[:100],
                        caption=f"🎵 Музыка из видео\n\n🎤 {music_author}\n🎼 {music_title}\n\n👇 Найти полный трек:",
                        filename="tiktok_audio.mp3",
                        reply_markup=reply_markup,
                        read_timeout=90,
                        write_timeout=90
                    )
                    
                    print("✅ Music sent successfully")
                else:
                    print(f"❌ Failed to download music: HTTP {resp.status}")
    
    except Exception as e:
        print(f"❌ Error sending music: {type(e).__name__} - {str(e)}")


async def resolve_redirect(url):
    """Разворачивает короткую ссылку в полную"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, allow_redirects=True, timeout=aiohttp.ClientTimeout(total=10)) as response:
                return str(response.url)
    except Exception as e:
        print(f"Error resolving redirect: {e}")
        return url

async def download_with_tikwm(url):
    """Скачивает видео через TikWM API"""
    try:
        # Разворачиваем короткую ссылку
        full_url = await resolve_redirect(url)
        print(f"Resolved URL: {full_url}")
        
        async with aiohttp.ClientSession() as session:
            # Запрос к TikWM API
            data = {
                "url": full_url,
                "hd": 1  # Максимальное качество
            }
            
            async with session.post(
                "https://www.tikwm.com/api/",
                data=data,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    print(f"TikWM Response: {json.dumps(result, indent=2)}")
                    
                    if result.get("code") == 0:  # Успех
                        data = result.get("data", {})
                        
                        # Проверяем тип контента
                        if "images" in data and data["images"]:
                            # Это слайдшоу с фото
                            return {
                                "type": "images",
                                "urls": data["images"],
                                "title": data.get("title", "TikTok Images"),
                                "author": data.get("author", {}).get("nickname", "Unknown")
                            }
                        else:
                            # Это видео
                            # Пробуем HD версию, если нет - обычную
                            video_url = data.get("hdplay") or data.get("play")
                            
                            if video_url:
                                return {
                                    "type": "video",
                                    "url": video_url,
                                    "title": data.get("title", "TikTok Video"),
                                    "author": data.get("author", {}).get("nickname", "Unknown"),
                                    "duration": data.get("duration", 0)
                                }
                
                print(f"TikWM failed with status: {response.status}")
                return None
    except Exception as e:
        print(f"TikWM Error: {e}")
        return None

async def download_tiktok(url):
    """Скачивает видео через доступные API"""
    # Пробуем TikWM API
    result = await download_with_tikwm(url)
    if result:
        return result
    
    # Если не удалось - возвращаем None
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
    status_msg = await update.message.reply_text("⏳ Загружаю...\nЭто может занять до 30 секунд")
    
    try:
        # Скачиваем
        result = await download_tiktok(url)
        
        if not result:
            await status_msg.edit_text(
                "❌ Не удалось скачать видео.\n\n"
                "Возможные причины:\n"
                "• Видео удалено или приватное\n"
                "• API временно недоступен\n"
                "• Неправильная ссылка\n\n"
                "Попробуй:\n"
                "1. Другую ссылку\n"
                "2. Через несколько минут\n"
                "3. Отправить прямую ссылку (не короткую)"
            )
            return
        
        if result["type"] == "video":
            # Отправляем видео
            await status_msg.edit_text("📥 Скачиваю видео...")
            
            try:
                # Специальные заголовки для TikTok CDN
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Referer': 'https://www.tiktok.com/',
                    'Accept': '*/*',
                    'Accept-Encoding': 'identity',
                    'Range': 'bytes=0-'
                }
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        result["url"], 
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=120)
                    ) as resp:
                        if resp.status in [200, 206]:
                            # Скачиваем видео по частям
                            video_data = bytearray()
                            chunk_size = 1024 * 256  # 256 KB за раз
                            
                            async for chunk in resp.content.iter_chunked(chunk_size):
                                video_data.extend(chunk)
                            
                            video_bytes = bytes(video_data)
                            
                            # Проверяем размер (Telegram лимит ~50MB)
                            size_mb = len(video_bytes) / (1024 * 1024)
                            print(f"✅ Video downloaded: {size_mb:.2f} MB")
                            
                            if size_mb > 50:
                                await status_msg.edit_text(
                                    f"❌ Видео слишком большое ({size_mb:.1f} MB)\n"
                                    "Telegram поддерживает до 50 MB\n\n"
                                    f"💾 Прямая ссылка для скачивания:\n{result['url']}"
                                )
                                return
                            
                            # Отправляем пользователю
                            await status_msg.edit_text("📤 Отправляю видео...")
                            
                            caption = f"✅ {result['title'][:100]}\n"
                            caption += f"👤 {result.get('author', 'Unknown')}\n"
                            caption += f"🎬 Без водяного знака"
                            
                            await update.message.reply_video(
                                video=video_bytes,
                                caption=caption,
                                filename="tiktok_video.mp4",
                                supports_streaming=True,
                                read_timeout=120,
                                write_timeout=120
                            )
                            await status_msg.delete()
                            print("✅ Video sent successfully")
                            
                            # Отправляем музыку, если есть
                            await send_music(update, result)
                        else:
                            await status_msg.edit_text(
                                f"❌ Ошибка загрузки видео (HTTP {resp.status})\n\n"
                                f"💾 Попробуй скачать напрямую:\n{result['url']}"
                            )
            except asyncio.TimeoutError:
                await status_msg.edit_text(
                    "⏱ Превышено время ожидания\n"
                    "Видео слишком большое или медленное соединение\n\n"
                    f"💾 Скачай напрямую:\n{result['url']}"
                )
            except Exception as e:
                error_type = type(e).__name__
                print(f"❌ Video send error: {error_type} - {str(e)}")
                await status_msg.edit_text(
                    f"❌ Ошибка: {error_type}\n\n"
                    f"💾 Прямая ссылка для скачивания:\n{result['url']}"
                )
        
        elif result["type"] == "images":
            # Отправляем фото
            images_count = len(result["urls"])
            await status_msg.edit_text(f"📥 Скачиваю {images_count} фото...")
            
            # Скачиваем все фото сначала
            photos = []
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://www.tiktok.com/'
            }
            
            async with aiohttp.ClientSession() as session:
                for i, img_url in enumerate(result["urls"], 1):
                    try:
                        await status_msg.edit_text(f"📥 Скачиваю фото {i}/{images_count}...")
                        
                        async with session.get(
                            img_url, 
                            headers=headers,
                            timeout=aiohttp.ClientTimeout(total=30)
                        ) as resp:
                            if resp.status == 200:
                                img_data = await resp.read()
                                photos.append(img_data)
                                print(f"✅ Downloaded photo {i}/{images_count} ({len(img_data) / 1024:.1f} KB)")
                            else:
                                print(f"❌ Failed to download photo {i}: HTTP {resp.status}")
                    except Exception as e:
                        print(f"❌ Error downloading photo {i}: {e}")
                        continue
            
            if not photos:
                await status_msg.edit_text("❌ Не удалось скачать фото")
                return
            
            # Отправляем фото меньшими батчами (по 5 за раз для стабильности)
            await status_msg.edit_text(f"📤 Отправляю {len(photos)} фото...")
            
            try:
                from telegram import InputMediaPhoto
                import io
                
                batch_size = 5  # Меньше батч = стабильнее
                sent_count = 0
                
                for batch_start in range(0, len(photos), batch_size):
                    batch = photos[batch_start:batch_start + batch_size]
                    
                    # Создаем медиагруппу с BytesIO объектами
                    media_group = []
                    
                    for idx, photo_data in enumerate(batch):
                        # Подпись только к первому фото в самом первом батче
                        caption = None
                        if batch_start == 0 and idx == 0:
                            caption = (
                                f"✅ {result['title'][:200]}\n"
                                f"👤 {result.get('author', 'Unknown')}\n"
                                f"📸 {len(photos)} фото"
                            )
                        
                        # Используем BytesIO для корректной отправки
                        photo_io = io.BytesIO(photo_data)
                        photo_io.name = f"photo_{batch_start + idx + 1}.jpg"
                        
                        media_group.append(
                            InputMediaPhoto(
                                media=photo_io,
                                caption=caption
                            )
                        )
                    
                    # Обновляем статус
                    await status_msg.edit_text(
                        f"📤 Отправляю фото {sent_count + 1}-{sent_count + len(batch)} из {len(photos)}..."
                    )
                    
                    # Пытаемся отправить с retry
                    max_retries = 3
                    for attempt in range(max_retries):
                        try:
                            await update.message.reply_media_group(
                                media=media_group,
                                read_timeout=90,
                                write_timeout=90,
                                connect_timeout=30,
                                pool_timeout=30
                            )
                            
                            sent_count += len(batch)
                            print(f"✅ Sent batch {batch_start // batch_size + 1}: {len(batch)} photos (total: {sent_count}/{len(photos)})")
                            break
                            
                        except Exception as e:
                            if attempt < max_retries - 1:
                                print(f"⚠️ Retry {attempt + 1}/{max_retries} for batch {batch_start // batch_size + 1}: {e}")
                                await asyncio.sleep(2)
                            else:
                                raise e
                    
                    # Задержка между батчами
                    if batch_start + batch_size < len(photos):
                        await asyncio.sleep(1.5)
                
                await status_msg.delete()
                print(f"✅ All {len(photos)} photos sent successfully")
                
            except Exception as e:
                error_type = type(e).__name__
                print(f"❌ Error sending media group: {error_type} - {str(e)}")
                await status_msg.edit_text(
                    f"❌ Ошибка отправки: {error_type}\n\n"
                    f"✅ Скачано: {len(photos)} из {images_count}\n"
                    f"📤 Отправлено: {sent_count} из {len(photos)}\n\n"
                    "Попробуй еще раз - обычно помогает!"
                )
    
    except Exception as e:
        error_msg = str(e)
        print(f"Handler error: {error_msg}")
        await status_msg.edit_text(
            f"❌ Произошла ошибка:\n{error_msg}\n\n"
            "Попробуй еще раз или отправь другую ссылку."
        )

def main():
    """Запуск бота"""
    # Проверка токена
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("⚠️ ВНИМАНИЕ! Замени YOUR_BOT_TOKEN_HERE на токен от @BotFather")
        return
    
    print("🤖 Запускаю бота...")
    print("📡 Используется TikWM API для скачивания")
    
    # Создаем приложение
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Регистрируем обработчики
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Запускаем
    print("✅ Бот запущен и готов к работе!")
    print("💡 Отправь боту ссылку на TikTok для теста")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()