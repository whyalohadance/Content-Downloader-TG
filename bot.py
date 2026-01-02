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

# Временное хранилище для выбора качества YouTube
user_quality_choice = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    keyboard = [
        [KeyboardButton("🎵 TikTok"), KeyboardButton("📺 YouTube")],
        [KeyboardButton("ℹ️ Помощь")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        "👋 Привет! Я бот для скачивания видео.\n\n"
        "✅ TikTok - видео/фото без водяных знаков + музыка\n"
        "✅ YouTube - качество зависит от длины видео\n\n"
        "📊 YouTube лимиты:\n"
        "• Короткие видео (до 5 мин): 1080p/720p\n"
        "• Средние (5-15 мин): 720p/480p\n"
        "• Длинные (15-30 мин): 480p/360p\n"
        "• Лимит Telegram: 50 MB на файл\n\n"
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
        "• Качество: зависит от длины видео\n"
        "  - Короткие (до 5 мин): до 1080p\n"
        "  - Средние (5-15 мин): до 720p\n"
        "  - Длинные (15-30 мин): до 480p\n"
        "• Лимит Telegram: 50 MB\n"
        "• Максимум: 30 минут",
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

def get_youtube_streams(url):
    """Получает список доступных потоков YouTube"""
    try:
        yt = YouTube(url)
        
        # Получаем adaptive видео потоки (без аудио, но высокое качество)
        video_streams = yt.streams.filter(
            adaptive=True,
            file_extension='mp4',
            only_video=True
        ).order_by('resolution').desc()
        
        # Получаем лучший аудио поток
        audio_stream = yt.streams.filter(
            only_audio=True,
            file_extension='mp4'
        ).order_by('abr').desc().first()
        
        audio_size = audio_stream.filesize / (1024 * 1024) if audio_stream else 0
        
        result = []
        seen_resolutions = set()
        
        for stream in video_streams:
            # Получаем высоту видео (для портретных и горизонтальных)
            height = stream.resolution.replace('p', '') if stream.resolution else '0'
            
            try:
                height_int = int(height)
            except:
                continue
            
            # Ограничиваем максимум до 1080p (по высоте)
            if height_int > 1080:
                continue
            
            # Пропускаем дубликаты разрешений
            resolution_key = f"{stream.width}x{stream.height}"
            if resolution_key in seen_resolutions:
                continue
            
            video_size = stream.filesize / (1024 * 1024)
            total_size = video_size + audio_size
            
            # После re-encoding размер уменьшится примерно на 15-25%
            # Поэтому используем более щедрый лимит при фильтрации
            estimated_final_size = total_size * 0.80  # Предполагаем 20% сжатие
            
            # Telegram bot API limit is 50MB
            # Разрешаем потоки до 60MB, т.к. после re-encoding они станут ~48MB
            if total_size <= 60:
                result.append({
                    'itag': stream.itag,
                    'resolution': stream.resolution,
                    'fps': stream.fps,
                    'size_mb': round(estimated_final_size, 1),  # Показываем примерный размер после сжатия
                    'raw_size_mb': total_size,  # Храним реальный размер для логов
                    'width': stream.width,
                    'height': stream.height,
                    'audio_itag': audio_stream.itag if audio_stream else None
                })
                seen_resolutions.add(resolution_key)
        
        # Сортируем по высоте (для правильного отображения портретных и горизонтальных)
        result.sort(key=lambda x: x['height'], reverse=True)
        
        print(f"📊 Available streams for {yt.video_id}:")
        for s in result:
            print(f"   {s['resolution']} ({s['width']}x{s['height']}) - Raw: {s['raw_size_mb']:.1f} MB → Estimated: {s['size_mb']:.1f} MB")
        
        return {
            'title': yt.title,
            'duration': yt.length,
            'video_id': yt.video_id,
            'streams': result
        }
    except Exception as e:
        print(f"Error getting streams: {e}")
        return None

def download_youtube_with_quality(url, itag, audio_itag=None):
    """Скачивает YouTube с конкретным качеством и объединяет видео с аудио"""
    try:
        print(f"📺 Downloading YouTube with video itag={itag}, audio itag={audio_itag}")
        
        yt = YouTube(url, on_progress_callback=on_progress)
        video_stream = yt.streams.get_by_itag(itag)
        
        if not video_stream:
            return None
        
        video_id = yt.video_id
        
        # Скачиваем видео
        print(f"📥 Downloading video: {video_stream.resolution} ({video_stream.width}x{video_stream.height})")
        video_path = video_stream.download(output_path='/tmp', filename=f'{video_id}_video.mp4')
        
        # Если есть отдельное аудио, скачиваем и объединяем
        if audio_itag:
            audio_stream = yt.streams.get_by_itag(audio_itag)
            if audio_stream:
                print(f"📥 Downloading audio...")
                audio_path = audio_stream.download(output_path='/tmp', filename=f'{video_id}_audio.mp4')
                
                # Объединяем видео и аудио с помощью ffmpeg
                output_path = f'/tmp/{video_id}_final.mp4'
                
                print(f"🔧 Merging video and audio with ffmpeg...")
                import subprocess
                
                # ВАЖНО: Перекодируем видео в H.264 для совместимости с Telegram
                # Используем libx264 вместо copy для гарантии работы видео
                result = subprocess.run([
                    'ffmpeg', '-i', video_path, '-i', audio_path,
                    '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
                    '-c:a', 'aac', '-b:a', '128k',
                    '-pix_fmt', 'yuv420p',  # Формат пикселей для совместимости
                    '-movflags', '+faststart',
                    output_path, '-y', '-loglevel', 'error'
                ], capture_output=True, text=True)
                
                if result.returncode != 0:
                    print(f"⚠️ ffmpeg error: {result.stderr}")
                    # Если ffmpeg не сработал, пробуем без перекодирования
                    result2 = subprocess.run([
                        'ffmpeg', '-i', video_path, '-i', audio_path,
                        '-c:v', 'copy', '-c:a', 'aac', '-b:a', '128k',
                        '-movflags', '+faststart',
                        output_path, '-y', '-loglevel', 'error'
                    ], capture_output=True, text=True)
                    
                    if result2.returncode != 0:
                        print(f"⚠️ Second attempt failed, using video only")
                        final_path = video_path
                        if os.path.exists(audio_path):
                            os.remove(audio_path)
                    else:
                        print(f"✅ Merged with copy codec")
                        os.remove(video_path)
                        os.remove(audio_path)
                        final_path = output_path
                else:
                    print(f"✅ Merged and re-encoded successfully")
                    # Удаляем временные файлы
                    os.remove(video_path)
                    os.remove(audio_path)
                    final_path = output_path
            else:
                final_path = video_path
        else:
            final_path = video_path
        
        # Получаем размер финального файла
        file_size_mb = os.path.getsize(final_path) / (1024 * 1024)
        
        print(f"✅ Final file: {file_size_mb:.1f} MB at {final_path}")
        
        # Telegram bot API limit is 50MB
        if file_size_mb > 50:
            print(f"⚠️ File too large ({file_size_mb:.1f} MB), compressing...")
            compressed_path = f'/tmp/{video_id}_compressed.mp4'
            
            # Сжимаем видео до 45MB
            import subprocess
            result = subprocess.run([
                'ffmpeg', '-i', final_path,
                '-c:v', 'libx264', '-preset', 'fast', '-crf', '28',
                '-c:a', 'aac', '-b:a', '96k',
                '-pix_fmt', 'yuv420p',
                '-movflags', '+faststart',
                '-fs', '45M',  # Limit file size to 45MB
                compressed_path, '-y', '-loglevel', 'error'
            ], capture_output=True, text=True)
            
            if result.returncode == 0 and os.path.exists(compressed_path):
                os.remove(final_path)
                final_path = compressed_path
                file_size_mb = os.path.getsize(final_path) / (1024 * 1024)
                print(f"✅ Compressed to: {file_size_mb:.1f} MB")
            else:
                print(f"⚠️ Compression failed: {result.stderr}")
                return None
        
        return {
            "type": "video",
            "path": final_path,
            "title": yt.title,
            "duration": yt.length,
            "size_mb": file_size_mb,
            "resolution": video_stream.resolution,
            "width": video_stream.width,
            "height": video_stream.height,
            "platform": "youtube"
        }
    except Exception as e:
        print(f"Download error: {e}")
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

async def handle_quality_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора качества через callback"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = query.from_user.id
    
    if data.startswith('yt_quality_'):
        # Формат: yt_quality_ITAG_AUDIITAG_VIDEOID (audio_itag может быть None)
        parts = data.split('_')
        itag = int(parts[2])
        audio_itag = int(parts[3]) if parts[3] != 'None' else None
        video_id = parts[4]
        
        # Получаем сохранённый URL
        url = user_quality_choice.get(user_id, {}).get('url')
        
        if not url:
            await query.edit_message_text("❌ Ссылка устарела. Отправь ссылку заново.")
            return
        
        status_msg = await query.edit_message_text("⏳ Скачиваю выбранное качество...")
        
        try:
            # Скачиваем с выбранным качеством
            result = await asyncio.to_thread(download_youtube_with_quality, url, itag, audio_itag)
            
            if not result:
                await status_msg.edit_text("❌ Не удалось скачать")
                return
            
            # Проверяем размер перед отправкой
            if result["size_mb"] > 50:
                await status_msg.edit_text(
                    f"❌ Видео слишком большое ({result['size_mb']:.1f} MB)\n\n"
                    f"📊 Telegram bot API limit: 50 MB\n"
                    f"💡 Попробуй выбрать качество пониже"
                )
                # Удаляем файл
                if os.path.exists(result["path"]):
                    os.remove(result["path"])
                return
            
            await status_msg.edit_text("📤 Отправляю видео...")
            
            video_path = result["path"]
            
            with open(video_path, 'rb') as video_file:
                video_bytes = video_file.read()
            
            mins = result['duration'] // 60
            secs = result['duration'] % 60
            
            caption = f"✅ {result['title'][:150]}\n"
            caption += f"📺 YouTube • {result['resolution']} • {result['size_mb']:.1f} MB • {mins}:{secs:02d}"
            
            print(f"📤 Sending: {result['width']}x{result['height']}")
            
            await query.message.reply_video(
                video=video_bytes,
                caption=caption,
                filename="youtube_video.mp4",
                supports_streaming=True,
                width=result['width'],
                height=result['height'],
                read_timeout=300,
                write_timeout=300,
                connect_timeout=60,
                pool_timeout=60
            )
            
            os.remove(video_path)
            await status_msg.delete()
            
            # Очищаем выбор
            if user_id in user_quality_choice:
                del user_quality_choice[user_id]
            
            print("✅ YouTube video sent successfully")
            
        except Exception as e:
            print(f"❌ Error: {type(e).__name__} - {str(e)}")
            error_msg = str(e)
            
            # Более понятные сообщения об ошибках
            if "Request Entity Too Large" in error_msg or "File too large" in error_msg:
                await status_msg.edit_text(
                    f"❌ Файл слишком большой для Telegram\n\n"
                    f"📊 Лимит: 50 MB\n"
                    f"💡 Выбери качество пониже"
                )
            elif "NetworkError" in error_msg or "TimedOut" in error_msg:
                await status_msg.edit_text(
                    f"❌ Ошибка сети при отправке\n\n"
                    f"💡 Попробуй еще раз или выбери качество пониже"
                )
            else:
                await status_msg.edit_text(f"❌ Ошибка: {type(e).__name__}")
            
            # Удаляем файл если есть
            if 'result' in locals() and result and os.path.exists(result.get("path", "")):
                os.remove(result["path"])


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка сообщений с ссылками"""
    text = update.message.text
    user_id = update.message.from_user.id
    
    if text in ["🎵 TikTok", "📺 YouTube", "📷 Instagram", "🐦 Twitter/X", "📘 Facebook", "📌 Pinterest"]:
        platform_info = {
            "🎵 TikTok": "Отправь мне ссылку на TikTok видео или фото.\n\n✅ Без водяных знаков\n✅ Оригинальное качество\n✅ Музыка с распознаванием\n\nПример:\nhttps://vm.tiktok.com/...\nhttps://www.tiktok.com/@user/video/...",
            "📺 YouTube": "Отправь мне ссылку на YouTube видео.\n\n📊 Ограничения:\n• Длительность: до 30 минут\n• Размер файла: до 50 MB (лимит Telegram)\n• Качество: зависит от длины\n  - Короткие (до 5 мин): 1080p\n  - Средние (5-15 мин): 720p\n  - Длинные (15-30 мин): 480p\n\nПример:\nhttps://youtube.com/watch?v=...\nhttps://youtu.be/...",
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
                # Получаем доступные качества
                await status_msg.edit_text("⏳ Анализирую видео...")
                
                streams_data = await asyncio.to_thread(get_youtube_streams, url)
                
                if not streams_data or not streams_data['streams']:
                    await status_msg.edit_text(
                        "❌ Нет доступных качеств для скачивания\n\n"
                        "Возможные причины:\n"
                        "• Видео слишком длинное для любого качества\n"
                        "• Все версии превышают 50 MB (лимит Telegram)\n"
                        "• Видео недоступно или ограничено\n\n"
                        "💡 Попробуй более короткое видео (до 10 минут)"
                    )
                    return
                
                # Проверяем длительность
                if streams_data['duration'] > 1800:
                    await status_msg.edit_text(
                        f"❌ Видео слишком длинное: {streams_data['duration'] // 60} мин\n\n⏱ Максимум: 30 минут"
                    )
                    return
                
                # Сохраняем URL для пользователя
                user_quality_choice[user_id] = {
                    'url': url,
                    'video_id': streams_data['video_id']
                }
                
                # Создаём кнопки с качествами
                keyboard = []
                for stream in streams_data['streams']:
                    button_text = f"{stream['resolution']} • {stream['width']}x{stream['height']} • {stream['size_mb']:.1f} MB"
                    audio_itag_str = str(stream['audio_itag']) if stream.get('audio_itag') else 'None'
                    callback_data = f"yt_quality_{stream['itag']}_{audio_itag_str}_{streams_data['video_id']}"
                    keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                mins = streams_data['duration'] // 60
                secs = streams_data['duration'] % 60
                
                await status_msg.edit_text(
                    f"📺 {streams_data['title'][:100]}\n"
                    f"⏱ Длительность: {mins}:{secs:02d}\n\n"
                    f"🎬 Выбери качество:\n"
                    f"💡 Чем выше качество, тем больше размер файла",
                    reply_markup=reply_markup
                )
                return  # Выходим, ждём выбора качества
        
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
    print("📡 TikTok (без водяных знаков) | YouTube (качество зависит от длины)")
    print("⚠️ Telegram bot API limit: 50 MB per file")
    print("📊 YouTube quality guide:")
    print("   • Short videos (< 5 min): up to 1080p")
    print("   • Medium videos (5-15 min): up to 720p")
    print("   • Long videos (15-30 min): up to 480p")
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_quality_selection))
    
    print("✅ Бот запущен и готов к работе!")
    print("💡 Отправь боту ссылку на TikTok или YouTube для теста")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()