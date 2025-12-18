import asyncio
import re
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import aiohttp
import json
from urllib.parse import quote, urlparse

# Вставь сюда токен от @BotFather
BOT_TOKEN = "8410013565:AAHNYF-9HE7z7KMKxqeI_ZuMjK-W84J_0Rs"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    # Создаём клавиатуру с платформами
    keyboard = [
        [KeyboardButton("🎵 TikTok"), KeyboardButton("📺 YouTube")],
        [KeyboardButton("📷 Instagram"), KeyboardButton("🐦 Twitter/X")],
        [KeyboardButton("📘 Facebook"), KeyboardButton("📌 Pinterest")],
        [KeyboardButton("ℹ️ Помощь")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        "👋 Привет! Я универсальный бот для скачивания видео.\n\n"
        "📱 Выбери платформу кнопками ниже или просто отправь ссылку:\n\n"
        "✅ TikTok - видео/фото без водяных знаков + музыка\n"
        "✅ YouTube - видео в максимальном качестве\n"
        "✅ Instagram - посты, reels, stories\n"
        "✅ Twitter/X - видео из твитов\n"
        "✅ Facebook - видео с Facebook\n"
        "✅ Pinterest - видео и изображения\n\n"
        "Просто отправь мне ссылку!",
        reply_markup=reply_markup
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /help"""
    keyboard = [
        [KeyboardButton("🎵 TikTok"), KeyboardButton("📺 YouTube")],
        [KeyboardButton("📷 Instagram"), KeyboardButton("🐦 Twitter/X")],
        [KeyboardButton("📘 Facebook"), KeyboardButton("📌 Pinterest")],
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        "ℹ️ Как использовать бота:\n\n"
        "1️⃣ Выбери платформу кнопками или просто отправь ссылку\n"
        "2️⃣ Скопируй ссылку на видео из приложения\n"
        "3️⃣ Отправь мне ссылку\n"
        "4️⃣ Получи видео в максимальном качестве!\n\n"
        "🎵 TikTok:\n"
        "• Видео без водяного знака\n"
        "• Фото из слайдшоу группой\n"
        "• Музыка с кнопками поиска в Spotify/YouTube\n\n"
        "📺 YouTube:\n"
        "• Видео до 1080p (максимальное качество для Telegram)\n"
        "• Без сжатия качества\n"
        "• Быстрая загрузка\n\n"
        "Остальные платформы скоро будут добавлены!",
        reply_markup=reply_markup
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

def extract_youtube_url(text):
    """Извлекает ссылку YouTube из текста"""
    patterns = [
        r'https?://(?:www\.)?youtube\.com/watch\?v=[\w-]+',
        r'https?://(?:www\.)?youtube\.com/shorts/[\w-]+',
        r'https?://youtu\.be/[\w-]+',
        r'https?://(?:www\.)?youtube\.com/embed/[\w-]+',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(0)
    return None

def detect_platform(text):
    """Определяет платформу по ссылке"""
    text_lower = text.lower()
    
    if 'tiktok.com' in text_lower:
        return 'tiktok'
    elif 'youtube.com' in text_lower or 'youtu.be' in text_lower:
        return 'youtube'
    elif 'instagram.com' in text_lower:
        return 'instagram'
    elif 'twitter.com' in text_lower or 'x.com' in text_lower:
        return 'twitter'
    elif 'facebook.com' in text_lower or 'fb.watch' in text_lower:
        return 'facebook'
    elif 'pinterest.com' in text_lower or 'pin.it' in text_lower:
        return 'pinterest'
    
    return None

async def download_youtube(url):
    """Скачивает видео с YouTube через API"""
    try:
        print(f"📺 YouTube URL: {url}")
        
        # Используем бесплатный API для YouTube
        # Вариант 1: cobalt.tools API (бесплатный, без ключа)
        api_url = "https://api.cobalt.tools/api/json"
        
        payload = {
            "url": url,
            "vQuality": "1080",  # Максимальное качество до 1080p
            "filenamePattern": "basic",
            "isAudioOnly": False
        }
        
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                api_url,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    print(f"Cobalt Response: {json.dumps(result, indent=2)}")
                    
                    if result.get("status") == "success" or result.get("status") == "redirect":
                        video_url = result.get("url")
                        
                        if video_url:
                            # Получаем информацию о видео
                            title = "YouTube Video"
                            
                            return {
                                "type": "video",
                                "url": video_url,
                                "title": title,
                                "platform": "youtube"
                            }
                
                # Если Cobalt не сработал, пробуем альтернативный метод
                print("⚠️ Cobalt failed, trying alternative...")
                
                # Вариант 2: y2mate API (альтернативный)
                y2mate_url = "https://www.y2mate.com/mates/analyzeV2/ajax"
                
                video_id = None
                if 'v=' in url:
                    video_id = url.split('v=')[1].split('&')[0]
                elif 'youtu.be/' in url:
                    video_id = url.split('youtu.be/')[1].split('?')[0]
                elif '/shorts/' in url:
                    video_id = url.split('/shorts/')[1].split('?')[0]
                
                if video_id:
                    y2mate_data = {
                        "k_query": f"https://www.youtube.com/watch?v={video_id}",
                        "k_page": "home",
                        "hl": "en",
                        "q_auto": 0
                    }
                    
                    async with session.post(
                        y2mate_url,
                        data=y2mate_data,
                        timeout=aiohttp.ClientTimeout(total=30)
                    ) as y2mate_response:
                        if y2mate_response.status == 200:
                            y2mate_result = await y2mate_response.json()
                            
                            if y2mate_result.get("status") == "ok":
                                title = y2mate_result.get("title", "YouTube Video")
                                
                                # Ищем лучшее качество видео
                                links = y2mate_result.get("links", {}).get("mp4", {})
                                
                                # Приоритет качества: 1080p > 720p > 480p > 360p
                                for quality in ["1080", "720", "480", "360"]:
                                    if quality in links:
                                        k_value = links[quality].get("k")
                                        
                                        if k_value:
                                            # Получаем прямую ссылку на скачивание
                                            convert_url = "https://www.y2mate.com/mates/convertV2/index"
                                            convert_data = {
                                                "vid": video_id,
                                                "k": k_value
                                            }
                                            
                                            async with session.post(
                                                convert_url,
                                                data=convert_data,
                                                timeout=aiohttp.ClientTimeout(total=30)
                                            ) as convert_response:
                                                if convert_response.status == 200:
                                                    convert_result = await convert_response.json()
                                                    
                                                    if convert_result.get("status") == "ok":
                                                        download_url = convert_result.get("dlink")
                                                        
                                                        if download_url:
                                                            return {
                                                                "type": "video",
                                                                "url": download_url,
                                                                "title": title,
                                                                "quality": quality,
                                                                "platform": "youtube"
                                                            }
                
                print("❌ All YouTube download methods failed")
                return None
                
    except Exception as e:
        print(f"YouTube Error: {type(e).__name__} - {str(e)}")
        return None
    """Отправляет музыку из TikTok видео с кнопками поиска и Shazam распознаванием"""
    try:
        music_info = result.get("music_info")
        if not music_info:
            print("⚠️ No music info available")
            return
        
        music_url = music_info.get("play")
        music_title = music_info.get("title", "Unknown Track")
        music_author = music_info.get("author", "Unknown Artist")
        is_original = music_info.get("original", False)
        
        if not music_url:
            print("⚠️ No music URL available")
            return
        
        print(f"🎵 Extracting music: {music_title} - {music_author} (original: {is_original})")
        
        # Скачиваем аудио
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://www.tiktok.com/'
        }
        
        audio_data = None
        async with aiohttp.ClientSession() as session:
            async with session.get(
                music_url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=60)
            ) as resp:
                if resp.status in [200, 206]:
                    audio_data = await resp.read()
                    size_mb = len(audio_data) / (1024 * 1024)
                    print(f"🎵 Audio downloaded: {size_mb:.2f} MB")
                else:
                    print(f"❌ Failed to download music: HTTP {resp.status}")
                    return
        
        if not audio_data:
            return
        
        # Распознаем трек через Shazam API только если это не оригинальный звук
        shazam_result = None
        
        # Всегда пытаемся распознать, кроме явных "original sound"
        should_recognize = True
        if is_original and "original sound" in music_title.lower():
            # Проверяем, может быть это известный трек с пометкой "original sound"
            if " - " in music_title and len(music_title.split(" - ")[1]) > 3:
                should_recognize = True
            else:
                should_recognize = False
                print("⚠️ Original sound detected, skipping recognition")
        
        if should_recognize:
            shazam_result = await recognize_with_shazam(audio_data)
        
        # Определяем финальное название трека
        if shazam_result and shazam_result.get("recognized"):
            final_title = shazam_result.get("title", music_title)
            final_artist = shazam_result.get("artist", music_author)
            shazam_status = "🎯 Распознано через Shazam"
            
            spotify_url = shazam_result.get("spotify_url")
            apple_music_url = shazam_result.get("apple_music_url")
            youtube_url = shazam_result.get("youtube_url")
        else:
            # Пытаемся извлечь информацию из названия трека
            clean_title = music_title.replace("original sound - ", "").strip()
            
            final_title = clean_title
            final_artist = "Unknown Artist"
            
            # Попытка 1: "Artist - Song"
            if " - " in clean_title or " — " in clean_title:
                separator = " - " if " - " in clean_title else " — "
                parts = clean_title.split(separator, 1)
                if len(parts) == 2:
                    if not parts[0].strip().startswith("@"):
                        final_artist = parts[0].strip()
                        final_title = parts[1].strip()
            # Попытка 2: "Song (Artist)"
            elif "(" in clean_title and ")" in clean_title:
                regex_pattern = r'^(.+?)\s*\((.+?)\)$'
                match = re.match(regex_pattern, clean_title)
                if match:
                    final_title = match.group(1).strip()
                    potential_artist = match.group(2).strip()
                    if not potential_artist.startswith("@"):
                        final_artist = potential_artist
            # Попытка 3: "Song | Artist"
            elif " | " in clean_title:
                parts = clean_title.split(" | ", 1)
                if len(parts) == 2 and not parts[1].strip().startswith("@"):
                    final_title = parts[0].strip()
                    final_artist = parts[1].strip()
            
            # Если так и не нашли исполнителя
            if final_artist == "Unknown Artist" and music_author:
                if not music_author.startswith("@"):
                    final_artist = music_author
            
            if is_original and not final_artist.startswith("@"):
                shazam_status = "🎤 Оригинальный звук"
            else:
                shazam_status = "🔍 Поиск по названию"
            
            spotify_url = None
            apple_music_url = None
            youtube_url = None
        
        # Создаем кнопки для поиска трека
        if final_artist and not final_artist.startswith("@") and final_artist != "Unknown Artist":
            search_query = f"{final_artist} {final_title}"
        else:
            search_query = final_title
        
        encoded_query = quote(search_query)
        
        keyboard = []
        
        # Первая строка
        row1 = []
        if spotify_url:
            row1.append(InlineKeyboardButton("🎵 Открыть в Spotify", url=spotify_url))
        else:
            row1.append(InlineKeyboardButton("🔍 Найти в Spotify", url=f"https://open.spotify.com/search/{encoded_query}"))
        
        if apple_music_url:
            row1.append(InlineKeyboardButton("🍎 Открыть в Apple Music", url=apple_music_url))
        else:
            row1.append(InlineKeyboardButton("🔍 Найти в Apple Music", url=f"https://music.apple.com/search?term={encoded_query}"))
        
        keyboard.append(row1)
        
        # Вторая строка
        row2 = []
        if youtube_url:
            row2.append(InlineKeyboardButton("📺 Открыть в YouTube", url=youtube_url))
        else:
            row2.append(InlineKeyboardButton("🔍 Найти в YouTube", url=f"https://www.youtube.com/results?search_query={encoded_query}"))
        
        row2.append(InlineKeyboardButton("💿 Deezer", url=f"https://www.deezer.com/search/{encoded_query}"))
        
        keyboard.append(row2)
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Формируем подпись
        caption = f"{shazam_status}\n\n"
        if final_artist and not final_artist.startswith("@") and final_artist != "Unknown Artist":
            caption += f"🎤 {final_artist}\n"
        caption += f"🎼 {final_title}\n\n"
        caption += "👇 Слушать полный трек:"
        
        # Определяем performer для метаданных аудио
        audio_performer = final_artist
        if not final_artist or final_artist.startswith("@") or final_artist == "Unknown Artist":
            audio_performer = "TikTok Sound"
        
        # Отправляем аудио
        await update.message.reply_audio(
            audio=audio_data,
            title=final_title[:100],
            performer=audio_performer[:100],
            caption=caption,
            filename="tiktok_audio.mp3",
            reply_markup=reply_markup,
            read_timeout=90,
            write_timeout=90
        )
        
        print(f"✅ Music sent: {audio_performer} - {final_title}")
        if shazam_result and shazam_result.get("recognized"):
            print(f"   🎯 Recognized via Shazam")
        else:
            print(f"   🔍 Search query: {search_query}")
    
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

async def recognize_with_shazam(audio_data):
    """Распознает трек через несколько API"""
    try:
        print("🔍 Recognizing track with Shazam...")
        
        # Ограничиваем размер аудио (первые 15 секунд)
        audio_sample = audio_data[:240000] if len(audio_data) > 240000 else audio_data
        
        async with aiohttp.ClientSession() as session:
            try:
                audd_url = "https://api.audd.io/"
                
                data = aiohttp.FormData()
                data.add_field('file', audio_sample, filename='audio.mp3', content_type='audio/mpeg')
                data.add_field('return', 'spotify,apple_music,deezer')
                
                async with session.post(
                    audd_url,
                    data=data,
                    timeout=aiohttp.ClientTimeout(total=45)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        
                        if result.get("status") == "success" and result.get("result"):
                            track_data = result["result"]
                            
                            print(f"✅ AudD recognized: {track_data.get('artist')} - {track_data.get('title')}")
                            
                            spotify_url = None
                            apple_music_url = None
                            
                            if "spotify" in track_data and track_data["spotify"]:
                                spotify_url = track_data["spotify"].get("external_urls", {}).get("spotify")
                            
                            if "apple_music" in track_data and track_data["apple_music"]:
                                apple_music_url = track_data["apple_music"].get("url")
                            
                            youtube_query = quote(f"{track_data['artist']} {track_data['title']}")
                            youtube_url = f"https://www.youtube.com/results?search_query={youtube_query}"
                            
                            return {
                                "title": track_data.get("title"),
                                "artist": track_data.get("artist"),
                                "album": track_data.get("album"),
                                "release_date": track_data.get("release_date"),
                                "spotify_url": spotify_url,
                                "apple_music_url": apple_music_url,
                                "youtube_url": youtube_url,
                                "recognized": True
                            }
            except Exception as e:
                print(f"⚠️ AudD failed: {type(e).__name__}")
        
        print("⚠️ Track recognition failed - will search by title")
        return None
    
    except Exception as e:
        print(f"⚠️ Recognition error: {type(e).__name__} - {str(e)}")
        return None

async def download_with_tikwm(url):
    """Скачивает видео через TikWM API"""
    try:
        full_url = await resolve_redirect(url)
        print(f"Resolved URL: {full_url}")
        
        async with aiohttp.ClientSession() as session:
            data = {
                "url": full_url,
                "hd": 1
            }
            
            async with session.post(
                "https://www.tikwm.com/api/",
                data=data,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    print(f"TikWM Response: {json.dumps(result, indent=2)}")
                    
                    if result.get("code") == 0:
                        data = result.get("data", {})
                        
                        if "images" in data and data["images"]:
                            return {
                                "type": "images",
                                "urls": data["images"],
                                "title": data.get("title", "TikTok Images"),
                                "author": data.get("author", {}).get("nickname", "Unknown"),
                                "music_info": data.get("music_info")
                            }
                        else:
                            video_url = data.get("hdplay") or data.get("play")
                            
                            if video_url:
                                return {
                                    "type": "video",
                                    "url": video_url,
                                    "title": data.get("title", "TikTok Video"),
                                    "author": data.get("author", {}).get("nickname", "Unknown"),
                                    "duration": data.get("duration", 0),
                                    "music_info": data.get("music_info")
                                }
                
                print(f"TikWM failed with status: {response.status}")
                return None
    except Exception as e:
        print(f"TikWM Error: {e}")
        return None

async def download_tiktok(url):
    """Скачивает видео через доступные API"""
    result = await download_with_tikwm(url)
    if result:
        return result
    
    return None

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка сообщений с ссылками"""
    text = update.message.text
    
    # Обработка кнопок меню
    if text in ["🎵 TikTok", "📺 YouTube", "📷 Instagram", "🐦 Twitter/X", "📘 Facebook", "📌 Pinterest"]:
        platform_info = {
            "🎵 TikTok": "Отправь мне ссылку на TikTok видео или фото.\nПример: https://vm.tiktok.com/...",
            "📺 YouTube": "Отправь мне ссылку на YouTube видео.\nПример: https://youtube.com/watch?v=...",
            "📷 Instagram": "⚠️ Instagram скоро будет доступен!",
            "🐦 Twitter/X": "⚠️ Twitter/X скоро будет доступен!",
            "📘 Facebook": "⚠️ Facebook скоро будет доступен!",
            "📌 Pinterest": "⚠️ Pinterest скоро будет доступен!"
        }
        await update.message.reply_text(platform_info.get(text, "Выбери платформу"))
        return
    
    if text == "ℹ️ Помощь":
        await help_command(update, context)
        return
    
    # Определяем платформу по ссылке
    platform = detect_platform(text)
    
    if not platform:
        await update.message.reply_text(
            "❌ Не могу определить платформу.\n\n"
            "Поддерживаются:\n"
            "• TikTok (vm.tiktok.com, www.tiktok.com)\n"
            "• YouTube (youtube.com, youtu.be)\n"
            "• Instagram (скоро)\n"
            "• Twitter/X (скоро)\n"
            "• Facebook (скоро)\n"
            "• Pinterest (скоро)"
        )
        return
    
    status_msg = await update.message.reply_text(f"⏳ Загружаю из {platform.upper()}...")
    
    try:
        result = None
        
        if platform == 'tiktok':
            url = extract_tiktok_url(text)
            if url:
                result = await download_tiktok(url)
        
        elif platform == 'youtube':
            url = extract_youtube_url(text)
            if url:
                result = await download_youtube(url)
        
        else:
            await status_msg.edit_text(f"⚠️ {platform.upper()} пока не поддерживается.\nСкоро добавим!")
            return
        
        if not result:
            await status_msg.edit_text(
                f"❌ Не удалось скачать из {platform.upper()}.\n\n"
                "Попробуй:\n"
                "• Другую ссылку\n"
                "• Через несколько минут\n"
                "• Убедись, что видео публичное"
            )
            return
        
        # Обработка TikTok
        if platform == 'tiktok' and result["type"] == "video":
            await status_msg.edit_text("📥 Скачиваю видео...")
            
            try:
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
                            video_data = bytearray()
                            chunk_size = 1024 * 256
                            
                            async for chunk in resp.content.iter_chunked(chunk_size):
                                video_data.extend(chunk)
                            
                            video_bytes = bytes(video_data)
                            
                            size_mb = len(video_bytes) / (1024 * 1024)
                            print(f"✅ Video downloaded: {size_mb:.2f} MB")
                            
                            if size_mb > 50:
                                await status_msg.edit_text(
                                    f"❌ Видео слишком большое ({size_mb:.1f} MB)\n"
                                    "Telegram поддерживает до 50 MB"
                                )
                                return
                            
                            await status_msg.edit_text("📤 Отправляю видео...")
                            
                            caption = f"✅ {result['title'][:100]}\n"
                            caption += f"👤 {result.get('author', 'Unknown')}\n"
                            caption += f"🎬 TikTok • {size_mb:.1f} MB"
                            
                            await update.message.reply_video(
                                video=video_bytes,
                                caption=caption,
                                filename="tiktok_video.mp4",
                                supports_streaming=True,
                                read_timeout=120,
                                write_timeout=120,
                                width=720,
                                height=1280
                            )
                            await status_msg.delete()
                            print("✅ Video sent successfully")
                            
                            await send_music(update, result)
                        else:
                            await status_msg.edit_text(f"❌ Ошибка загрузки видео (HTTP {resp.status})")
            except Exception as e:
                print(f"❌ Video send error: {type(e).__name__} - {str(e)}")
                await status_msg.edit_text(f"❌ Ошибка: {type(e).__name__}")
        
        # Обработка YouTube
        elif platform == 'youtube' and result["type"] == "video":
            await status_msg.edit_text("📥 Скачиваю YouTube видео...")
            
            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Referer': 'https://www.youtube.com/'
                }
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        result["url"],
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=180)
                    ) as resp:
                        if resp.status in [200, 206]:
                            video_data = bytearray()
                            chunk_size = 1024 * 512
                            
                            downloaded = 0
                            async for chunk in resp.content.iter_chunked(chunk_size):
                                video_data.extend(chunk)
                                downloaded += len(chunk)
                                
                                # Обновляем прогресс каждые 5MB
                                if downloaded % (1024 * 1024 * 5) < chunk_size:
                                    mb = downloaded / (1024 * 1024)
                                    await status_msg.edit_text(f"📥 Скачано: {mb:.1f} MB...")
                            
                            video_bytes = bytes(video_data)
                            size_mb = len(video_bytes) / (1024 * 1024)
                            print(f"✅ YouTube video downloaded: {size_mb:.2f} MB")
                            
                            if size_mb > 50:
                                await status_msg.edit_text(
                                    f"❌ Видео слишком большое ({size_mb:.1f} MB)\n"
                                    "Telegram поддерживает до 50 MB"
                                )
                                return
                            
                            await status_msg.edit_text("📤 Отправляю видео...")
                            
                            caption = f"✅ {result['title'][:150]}\n"
                            if result.get('quality'):
                                caption += f"📺 YouTube • {result['quality']}p • {size_mb:.1f} MB"
                            else:
                                caption += f"📺 YouTube • {size_mb:.1f} MB"
                            
                            await update.message.reply_video(
                                video=video_bytes,
                                caption=caption,
                                filename="youtube_video.mp4",
                                supports_streaming=True,
                                read_timeout=180,
                                write_timeout=180
                            )
                            await status_msg.delete()
                            print("✅ YouTube video sent successfully")
                        else:
                            await status_msg.edit_text(f"❌ Ошибка загрузки (HTTP {resp.status})")
            except Exception as e:
                print(f"❌ YouTube error: {type(e).__name__} - {str(e)}")
                await status_msg.edit_text(f"❌ Ошибка: {type(e).__name__}")
        
        # Обработка TikTok фото
        elif platform == 'tiktok' and result["type"] == "images":
            images_count = len(result["urls"])
            await status_msg.edit_text(f"📥 Скачиваю {images_count} фото...")
            
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
            
            await status_msg.edit_text(f"📤 Отправляю {len(photos)} фото...")
            
            try:
                from telegram import InputMediaPhoto
                import io
                
                batch_size = 5
                sent_count = 0
                
                for batch_start in range(0, len(photos), batch_size):
                    batch = photos[batch_start:batch_start + batch_size]
                    
                    media_group = []
                    
                    for idx, photo_data in enumerate(batch):
                        caption = None
                        if batch_start == 0 and idx == 0:
                            caption = (
                                f"✅ {result['title'][:200]}\n"
                                f"👤 {result.get('author', 'Unknown')}\n"
                                f"📸 {len(photos)} фото"
                            )
                        
                        photo_io = io.BytesIO(photo_data)
                        photo_io.name = f"photo_{batch_start + idx + 1}.jpg"
                        
                        media_group.append(
                            InputMediaPhoto(
                                media=photo_io,
                                caption=caption
                            )
                        )
                    
                    await status_msg.edit_text(
                        f"📤 Отправляю фото {sent_count + 1}-{sent_count + len(batch)} из {len(photos)}..."
                    )
                    
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
                    
                    if batch_start + batch_size < len(photos):
                        await asyncio.sleep(1.5)
                
                await status_msg.delete()
                print(f"✅ All {len(photos)} photos sent successfully")
                
                await send_music(update, result)
                
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
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("⚠️ ВНИМАНИЕ! Замени YOUR_BOT_TOKEN_HERE на токен от @BotFather")
        return
    
    print("🤖 Запускаю бота...")
    print("📡 Используется TikWM API для скачивания")
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("✅ Бот запущен и готов к работе!")
    print("💡 Отправь боту ссылку на TikTok для теста")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()