import asyncio
import re
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import aiohttp
import json
from urllib.parse import quote, urlparse
from pytubefix import YouTube
from pytubefix.cli import on_progress
import tempfile

# Вставь сюда токен от @BotFather
BOT_TOKEN = "8410013565:AAHNYF-9HE7z7KMKxqeI_ZuMjK-W84J_0Rs"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    keyboard = [
        [KeyboardButton("🎵 TikTok"), KeyboardButton("📺 YouTube")],
        [KeyboardButton("ℹ️ Помощь")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        "👋 Привет! Я стабильный бот для скачивания видео.\n\n"
        "✅ TikTok - видео/фото без водяных знаков + музыка\n"
        "✅ YouTube - видео до 1080p (до 150 MB)\n\n"
        "Просто отправь мне ссылку!",
        reply_markup=reply_markup
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /help"""
    keyboard = [
        [KeyboardButton("🎵 TikTok"), KeyboardButton("📺 YouTube")],
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        "ℹ️ Как использовать:\n\n"
        "Просто отправь ссылку на видео!\n\n"
        "🎵 TikTok:\n"
        "• Видео без водяного знака\n"
        "• Фото из слайдшоу группой\n"
        "• Музыка с Shazam + кнопки поиска\n"
        "• Оригинальное соотношение сторон\n\n"
        "📺 YouTube:\n"
        "• Качество: до 1080p\n"
        "• Длительность: до 30 минут\n"
        "• Размер: до 150 MB\n"
        "• Без сжатия качества",
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

def extract_instagram_url(text):
    """Извлекает ссылку Instagram из текста"""
    patterns = [
        r'https?://(?:www\.)?instagram\.com/stories/[\w.]+/\d+',
        r'https?://(?:www\.)?instagram\.com/p/[\w-]+',
        r'https?://(?:www\.)?instagram\.com/reel/[\w-]+',
        r'https?://(?:www\.)?instagram\.com/[\w.]+',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(0)
    return None

def extract_pinterest_url(text):
    """Извлекает ссылку Pinterest из текста"""
    patterns = [
        r'https?://(?:www\.)?pinterest\.com/pin/\d+',
        r'https?://(?:www\.)?pinterest\.[a-z]+/pin/\d+',
        r'https?://pin\.it/[\w]+',
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
    
    return None

def download_youtube_sync(url):
    """Синхронная функция для скачивания YouTube через pytubefix"""
    try:
        print(f"📺 YouTube URL: {url}")
        
        yt = YouTube(url, on_progress_callback=on_progress)
        
        title = yt.title
        duration = yt.length
        video_id = yt.video_id
        
        print(f"📺 Title: {title}")
        print(f"⏱ Duration: {duration}s ({duration // 60}m {duration % 60}s)")
        
        if duration > 1800:  # 30 минут
            print(f"⚠️ Video too long: {duration}s")
            return {
                "type": "error",
                "message": f"❌ Видео слишком длинное: {duration // 60} мин\n\n⏱ Максимум: 30 минут"
            }
        
        print("⬇️ Downloading...")
        
        # Получаем все progressive потоки (видео+аудио)
        progressive_streams = yt.streams.filter(
            progressive=True, 
            file_extension='mp4'
        ).order_by('resolution').desc()
        
        print(f"Available progressive streams:")
        for s in progressive_streams:
            print(f"  - {s.resolution} ({s.filesize / (1024*1024):.1f} MB)")
        
        # Выбираем лучшее качество, которое помещается в 150MB
        stream = None
        for s in progressive_streams:
            size_mb = s.filesize / (1024 * 1024)
            if size_mb <= 150:
                stream = s
                break
        
        # Если progressive нет или все слишком большие, пробуем adaptive
        if not stream:
            print("No suitable progressive stream, trying adaptive...")
            adaptive_streams = yt.streams.filter(
                adaptive=True,
                file_extension='mp4',
                only_video=False
            ).order_by('resolution').desc()
            
            for s in adaptive_streams:
                size_mb = s.filesize / (1024 * 1024)
                if size_mb <= 150:
                    stream = s
                    break
        
        if not stream:
            return {
                "type": "error",
                "message": "❌ Не удалось найти подходящий формат\n\nВозможно видео слишком большое даже в низком качестве"
            }
        
        resolution = stream.resolution or "Unknown"
        size_mb = stream.filesize / (1024 * 1024)
        
        print(f"📥 Selected: {resolution} - {size_mb:.1f} MB")
        
        video_path = stream.download(output_path='/tmp', filename=f'{video_id}.mp4')
        
        print(f"✅ Downloaded: {resolution} - {size_mb:.2f} MB at {video_path}")
        
        # Получаем реальные размеры видео из потока
        width = getattr(stream, 'width', None)
        height = getattr(stream, 'height', None)
        
        print(f"📐 Dimensions: {width}x{height}")
        
        return {
            "type": "video",
            "path": video_path,
            "title": title,
            "duration": duration,
            "size_mb": size_mb,
            "resolution": resolution,
            "width": width,
            "height": height,
            "platform": "youtube"
        }
        
    except Exception as e:
        error_msg = str(e)
        print(f"YouTube Error: {type(e).__name__} - {error_msg}")
        
        if "Video unavailable" in error_msg or "Private video" in error_msg:
            return {
                "type": "error",
                "message": "❌ Видео недоступно\n\n• Видео приватное или удалено\n• Возрастные ограничения\n• Географические ограничения"
            }
        
        return {
            "type": "error",
            "message": f"❌ Ошибка загрузки"
        }

async def download_pinterest(url):
    """Скачивает контент из Pinterest"""
    try:
        print(f"📌 Pinterest URL: {url}")
        
        # Разворачиваем короткую ссылку pin.it
        if 'pin.it' in url:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, allow_redirects=True, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    url = str(response.url)
                    print(f"Resolved to: {url}")
        
        # Извлекаем PIN ID
        pin_match = re.search(r'/pin/(\d+)', url)
        if not pin_match:
            return {
                "type": "error",
                "message": "❌ Неправильная ссылка Pinterest"
            }
        
        pin_id = pin_match.group(1)
        print(f"📌 Pin ID: {pin_id}")
        
        # Используем публичный API Pinterest
        api_url = f"https://www.pinterest.com/resource/PinResource/get/?data=%7B%22options%22%3A%7B%22field_set_key%22%3A%22unauth_react_main_pin%22%2C%22id%22%3A%22{pin_id}%22%7D%7D"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                api_url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    resource_data = data.get('resource_response', {}).get('data', {})
                    
                    if not resource_data:
                        return {
                            "type": "error",
                            "message": "❌ Не удалось получить данные пина"
                        }
                    
                    title = resource_data.get('title', 'Pinterest')
                    description = resource_data.get('description', '')
                    caption = f"{title} - {description}"[:200] if description else title[:200]
                    
                    # Проверяем наличие видео
                    videos = resource_data.get('videos')
                    if videos and videos.get('video_list'):
                        # Берем лучшее качество видео
                        video_formats = videos['video_list']
                        best_video = None
                        max_width = 0
                        
                        for fmt_key, fmt_data in video_formats.items():
                            if fmt_data.get('width', 0) > max_width:
                                max_width = fmt_data['width']
                                best_video = fmt_data
                        
                        if best_video:
                            video_url = best_video['url']
                            
                            print(f"✅ Found video: {max_width}p")
                            
                            return {
                                "type": "video",
                                "url": video_url,
                                "title": caption,
                                "platform": "pinterest"
                            }
                    
                    # Если нет видео, берем изображение
                    images = resource_data.get('images')
                    if images and images.get('orig'):
                        image_url = images['orig']['url']
                        
                        print(f"✅ Found image")
                        
                        return {
                            "type": "image_url",
                            "url": image_url,
                            "title": caption,
                            "platform": "pinterest"
                        }
        
        return {
            "type": "error",
            "message": "❌ Не удалось загрузить контент из Pinterest"
        }
        
    except Exception as e:
        print(f"Pinterest Error: {type(e).__name__} - {str(e)}")
        return {
            "type": "error",
            "message": f"❌ Ошибка Pinterest: {type(e).__name__}"
        }
    """Скачивает контент из Instagram через публичный API"""
    try:
        print(f"📷 Instagram URL: {url}")
        
        # Используем публичный API для Instagram
        # Альтернатива 1: DownloadGram API
        api_url = "https://downloadgram.org/reel-downloader.php"
        
        # Извлекаем shortcode
        shortcode = None
        if '/stories/' in url:
            return {
                "type": "error",
                "message": "❌ Stories недоступны\n\n💡 Попробуй:\n• Пост: instagram.com/p/ABC\n• Reel: instagram.com/reel/ABC"
            }
        
        post_match = re.search(r'/(p|reel|reels)/([\w-]+)', url)
        if post_match:
            shortcode = post_match.group(2)
        elif platform == 'instagram':
            url = extract_instagram_url(text)
            if url:
                result = await download_instagram(url)
        
        else:
            return {
                "type": "error", 
                "message": "❌ Неправильная ссылка"
            }
        
        print(f"📷 Shortcode: {shortcode}")
        
        # Используем rapidapi instagram downloader
        # Это бесплатный метод через scraping
        
        scrape_url = f"https://www.instagram.com/p/{shortcode}/?__a=1&__d=dis"
        
        headers = {
            'User-Agent': 'Instagram 76.0.0.15.395 Android (24/7.0; 640dpi; 1440x2560; samsung; SM-G930F; herolte; samsungexynos8890; en_US)',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'X-IG-App-ID': '936619743392459',
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                scrape_url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    items = data.get('items', [])
                    if not items:
                        return {
                            "type": "error",
                            "message": "❌ Не удалось получить данные поста"
                        }
                    
                    item = items[0]
                    
                    # Проверяем тип контента
                    if item.get('video_versions'):
                        # Это видео/reel
                        video_url = item['video_versions'][0]['url']
                        caption = item.get('caption', {}).get('text', 'Instagram Video')
                        
                        return {
                            "type": "video",
                            "url": video_url,
                            "title": caption[:100],
                            "platform": "instagram"
                        }
                    
                    elif item.get('carousel_media'):
                        # Несколько фото/видео
                        media_urls = []
                        for media in item['carousel_media']:
                            if media.get('image_versions2'):
                                media_urls.append(media['image_versions2']['candidates'][0]['url'])
                        
                        caption = item.get('caption', {}).get('text', 'Instagram Post')
                        
                        return {
                            "type": "images_urls",
                            "urls": media_urls,
                            "title": caption[:100],
                            "platform": "instagram"
                        }
                    
                    elif item.get('image_versions2'):
                        # Одно фото
                        photo_url = item['image_versions2']['candidates'][0]['url']
                        caption = item.get('caption', {}).get('text', 'Instagram Photo')
                        
                        return {
                            "type": "image_url",
                            "url": photo_url,
                            "title": caption[:100],
                            "platform": "instagram"
                        }
        
        # Если не сработало, возвращаем ошибку
        return {
            "type": "error",
            "message": "❌ Instagram временно недоступен\n\n💡 Возможные причины:\n• IP адрес заблокирован Instagram\n• Приватный аккаунт\n• Пост удалён\n\n⏳ Попробуй через 10-15 минут"
        }
        
    except Exception as e:
        print(f"Instagram Error: {type(e).__name__} - {str(e)}")
        return {
            "type": "error",
            "message": "❌ Instagram временно недоступен\n\n⏳ Попробуй через несколько минут"
        }

async def send_music(update: Update, result: dict):
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
        
        shazam_result = None
        
        should_recognize = True
        if is_original and "original sound" in music_title.lower():
            if " - " in music_title and len(music_title.split(" - ")[1]) > 3:
                should_recognize = True
            else:
                should_recognize = False
                print("⚠️ Original sound detected, skipping recognition")
        
        if should_recognize:
            shazam_result = await recognize_with_shazam(audio_data)
        
        if shazam_result and shazam_result.get("recognized"):
            final_title = shazam_result.get("title", music_title)
            final_artist = shazam_result.get("artist", music_author)
            shazam_status = "🎯 Распознано через Shazam"
            
            spotify_url = shazam_result.get("spotify_url")
            apple_music_url = shazam_result.get("apple_music_url")
            youtube_url = shazam_result.get("youtube_url")
        else:
            clean_title = music_title.replace("original sound - ", "").strip()
            
            final_title = clean_title
            final_artist = "Unknown Artist"
            
            if " - " in clean_title or " — " in clean_title:
                separator = " - " if " - " in clean_title else " — "
                parts = clean_title.split(separator, 1)
                if len(parts) == 2:
                    if not parts[0].strip().startswith("@"):
                        final_artist = parts[0].strip()
                        final_title = parts[1].strip()
            elif "(" in clean_title and ")" in clean_title:
                regex_pattern = r'^(.+?)\s*\((.+?)\)$'
                match = re.match(regex_pattern, clean_title)
                if match:
                    final_title = match.group(1).strip()
                    potential_artist = match.group(2).strip()
                    if not potential_artist.startswith("@"):
                        final_artist = potential_artist
            elif " | " in clean_title:
                parts = clean_title.split(" | ", 1)
                if len(parts) == 2 and not parts[1].strip().startswith("@"):
                    final_title = parts[0].strip()
                    final_artist = parts[1].strip()
            
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
        
        if final_artist and not final_artist.startswith("@") and final_artist != "Unknown Artist":
            search_query = f"{final_artist} {final_title}"
        else:
            search_query = final_title
        
        encoded_query = quote(search_query)
        
        keyboard = []
        
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
        
        row2 = []
        if youtube_url:
            row2.append(InlineKeyboardButton("📺 Открыть в YouTube", url=youtube_url))
        else:
            row2.append(InlineKeyboardButton("🔍 Найти в YouTube", url=f"https://www.youtube.com/results?search_query={encoded_query}"))
        
        row2.append(InlineKeyboardButton("💿 Deezer", url=f"https://www.deezer.com/search/{encoded_query}"))
        
        keyboard.append(row2)
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        caption = f"{shazam_status}\n\n"
        if final_artist and not final_artist.startswith("@") and final_artist != "Unknown Artist":
            caption += f"🎤 {final_artist}\n"
        caption += f"🎼 {final_title}\n\n"
        caption += "👇 Слушать полный трек:"
        
        audio_performer = final_artist
        if not final_artist or final_artist.startswith("@") or final_artist == "Unknown Artist":
            audio_performer = "TikTok Sound"
        
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
    
    if text in ["🎵 TikTok", "📺 YouTube", "📷 Instagram", "🐦 Twitter/X", "📘 Facebook", "📌 Pinterest"]:
        platform_info = {
            "🎵 TikTok": "Отправь мне ссылку на TikTok видео или фото.\n\nПример:\nhttps://vm.tiktok.com/...\nhttps://www.tiktok.com/@user/video/...",
            "📺 YouTube": "Отправь мне ссылку на YouTube видео.\n\n⏱ Ограничение: до 20 минут\n💾 Размер: до 45 MB\n🎬 Качество: до 1080p\n\nПример:\nhttps://youtube.com/watch?v=...\nhttps://youtu.be/...",
            "📷 Instagram": "Отправь мне ссылку на Instagram пост или Reel.\n\nПример:\n• Пост: instagram.com/p/ABC123\n• Reel: instagram.com/reel/ABC123\n\n💡 Только публичные аккаунты",
            "🐦 Twitter/X": "⚠️ Twitter/X скоро будет доступен!",
            "📘 Facebook": "⚠️ Facebook скоро будет доступен!",
            "📌 Pinterest": "⚠️ Pinterest скоро будет доступен!"
        }
        await update.message.reply_text(platform_info.get(text, "Выбери платформу"))
        return
    
    if text == "ℹ️ Помощь":
        await help_command(update, context)
        return
    
    platform = detect_platform(text)
    
    if not platform:
        await update.message.reply_text(
            "❌ Не могу определить платформу\n\n"
            "Поддерживаются:\n"
            "🎵 TikTok - vm.tiktok.com, www.tiktok.com\n"
            "📺 YouTube - youtube.com, youtu.be"
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
                result = await asyncio.to_thread(download_youtube_sync, url)
        
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
        
        if result.get("type") == "error":
            await status_msg.edit_text(f"{result.get('message', '❌ Ошибка загрузки')}")
            return
        
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
                            
                            # Не указываем width и height - Telegram сам определит правильное соотношение
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
                            
                            await send_music(update, result)
                        else:
                            await status_msg.edit_text(f"❌ Ошибка загрузки видео (HTTP {resp.status})")
            except Exception as e:
                print(f"❌ Video send error: {type(e).__name__} - {str(e)}")
                await status_msg.edit_text(f"❌ Ошибка: {type(e).__name__}")
        
        elif platform == 'youtube' and result.get("type") == "video":
            await status_msg.edit_text("📤 Отправляю YouTube видео...")
            
            try:
                video_path = result["path"]
                
                with open(video_path, 'rb') as video_file:
                    video_bytes = video_file.read()
                
                caption = f"✅ {result['title'][:150]}\n"
                caption += f"📺 YouTube • {result['size_mb']:.1f} MB"
                if result.get('duration'):
                    mins = result['duration'] // 60
                    secs = result['duration'] % 60
                    caption += f" • {mins}:{secs:02d}"
                
                await update.message.reply_video(
                    video=video_bytes,
                    caption=caption,
                    filename="youtube_video.mp4",
                    supports_streaming=True,
                    read_timeout=180,
                    write_timeout=180
                )
                
                os.remove(video_path)
                
                await status_msg.delete()
                print("✅ YouTube video sent successfully")
                
            except Exception as e:
                print(f"❌ YouTube send error: {type(e).__name__} - {str(e)}")
                
                if 'video_path' in locals() and os.path.exists(video_path):
                    os.remove(video_path)
                
                await status_msg.edit_text(f"❌ Ошибка отправки: {type(e).__name__}")
        
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
        else:
            await status_msg.edit_text(f"❌ Неизвестный тип контента")
                
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
    print("📡 TikTok (видео/фото/музыка) | YouTube (1080p, 30 мин, 150MB)")
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("✅ Бот запущен и готов к работе!")
    print("💡 Отправь боту ссылку на TikTok или YouTube для теста")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()