import os
import logging
import requests
import cv2
from PIL import Image
from pyrogram import Client, filters
from googleapiclient.discovery import build
import yt_dlp
import instaloader
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackContext, CallbackQueryHandler
from config import API_ID, API_HASH, BOT_TOKEN, RAPIDAPI_KEY, RAPIDAPI_HOST, YOUTUBE_API_KEY

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize Pyrogram Client and Instaloader
app_pyro = Client("media_downloader_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
loader = instaloader.Instaloader()

# YouTube Bot Functions
def search_youtube(query):
    youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
    request = youtube.search().list(
        q=query, part="snippet", type="video", maxResults=1
    )
    response = request.execute()

    if "items" in response and len(response["items"]) > 0:
        video_id = response["items"][0]["id"]["videoId"]
        return f"https://www.youtube.com/watch?v={video_id}"
    else:
        return None

def download_video(url):
    ydl_opts = {
        "format": "best",
        "outtmpl": "downloads/%(title)s.%(ext)s",
        "cookiefile": "cookies.txt",  # Path to your cookies.txt file
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return ydl.prepare_filename(info)
    except yt_dlp.utils.DownloadError as e:
        logger.error(f"Download error: {e}")
        return None

def download_audio(url):
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": "downloads/%(title)s.%(ext)s",
        "cookiefile": "cookies.txt",  # Path to your cookies.txt file
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return ydl.prepare_filename(info).replace(".webm", ".mp3").replace(".m4a", ".mp3")
    except yt_dlp.utils.DownloadError as e:
        logger.error(f"Download error: {e}")
        return None

async def start(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "Welcome to the YouTube Bot!\n\n"
        "Use /video <name> to get a video.\n"
        "Use /audio <name> to get an audio.\n"
        "Use /link <YouTube URL> to download directly as audio or video."
    )

async def send_loading_message(update: Update, context: CallbackContext):
    message = await update.message.reply_text("Loading...")
    return message

async def delete_messages(context: CallbackContext, messages):
    for msg in messages:
        try:
            await msg.delete()
        except Exception as e:
            logger.error(f"Failed to delete message: {e}")

async def video(update: Update, context: CallbackContext):
    if len(context.args) == 0:
        await update.message.reply_text("Usage: /video <video name>")
        return

    query = " ".join(context.args)
    loading_message = await send_loading_message(update, context)
    messages_to_delete = [loading_message, update.message]

    url = search_youtube(query)
    if not url:
        not_found_message = await update.message.reply_text("No results found.")
        messages_to_delete.append(not_found_message)
        await delete_messages(context, messages_to_delete)
        return

    try:
        file_path = download_video(url)
        if file_path:
            with open(file_path, "rb") as video_file:
                await update.message.reply_video(video=video_file)
            os.remove(file_path)
        else:
            error_message = await update.message.reply_text("Failed to download video. Please try again.")
            messages_to_delete.append(error_message)
    except Exception as e:
        logger.error(e)
        error_message = await update.message.reply_text("An error occurred while processing your request.")
        messages_to_delete.append(error_message)

    await delete_messages(context, messages_to_delete)

async def audio(update: Update, context: CallbackContext):
    if len(context.args) == 0:
        await update.message.reply_text("Usage: /audio <song name>")
        return

    query = " ".join(context.args)
    loading_message = await send_loading_message(update, context)
    messages_to_delete = [loading_message, update.message]

    url = search_youtube(query)
    if not url:
        not_found_message = await update.message.reply_text("No results found.")
        messages_to_delete.append(not_found_message)
        await delete_messages(context, messages_to_delete)
        return

    try:
        file_path = download_audio(url)
        if file_path:
            with open(file_path, "rb") as audio_file:
                await update.message.reply_audio(audio=audio_file)
            os.remove(file_path)
        else:
            error_message = await update.message.reply_text("Failed to download audio. Please try again.")
            messages_to_delete.append(error_message)
    except Exception as e:
        logger.error(e)
        error_message = await update.message.reply_text("An error occurred while processing your request.")
        messages_to_delete.append(error_message)

    await delete_messages(context, messages_to_delete)

async def link(update: Update, context: CallbackContext):
    if len(context.args) == 0:
        await update.message.reply_text("Usage: /link <YouTube URL>")
        return

    url = context.args[0]
    await update.message.reply_text("You provided a link. Please choose an option below:",
                                     reply_markup=InlineKeyboardMarkup([
                                         [
                                             InlineKeyboardButton("Download Audio", callback_data=f"audio|{url}"),
                                             InlineKeyboardButton("Download Video", callback_data=f"video|{url}"),
                                         ]
                                     ]))

async def button_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    action, url = query.data.split("|", 1)
    loading_message = await query.message.reply_text("Loading...")

    messages_to_delete = [loading_message, query.message]

    if action == "audio":
        try:
            file_path = download_audio(url)
            if file_path:
                with open(file_path, "rb") as audio_file:
                    await query.message.reply_audio(audio=audio_file)
                os.remove(file_path)
            else:
                error_message = await query.message.reply_text("Failed to download audio. Please try again.")
                messages_to_delete.append(error_message)
        except Exception as e:
            logger.error(e)
            error_message = await query.message.reply_text("An error occurred while processing your request.")
            messages_to_delete.append(error_message)

    elif action == "video":
        try:
            file_path = download_video(url)
            if file_path:
                with open(file_path, "rb") as video_file:
                    await query.message.reply_video(video=video_file)
                os.remove(file_path)
            else:
                error_message = await query.message.reply_text("Failed to download video. Please try again.")
                messages_to_delete.append(error_message)
        except Exception as e:
            logger.error(e)
            error_message = await query.message.reply_text("An error occurred while processing your request.")
            messages_to_delete.append(error_message)

    await delete_messages(context, messages_to_delete)

# Instagram Media Downloader Functions
class MediaProcessor:
    @staticmethod
    def process_instagram_media(url, prefix='temp'):
        try:
            post = instaloader.Post.from_shortcode(loader.context, url.split("/")[-2])
            media_type = 'video' if post.is_video else 'image'
            download_url = post.video_url if post.is_video else post.url
            ext = {'video': 'mp4', 'image': 'jpg'}.get(media_type, 'media')
            temp_filename = f"{prefix}_media.{ext}"

            with open(temp_filename, 'wb') as f:
                response = requests.get(download_url, stream=True)
                if response.status_code != 200:
                    return None
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            if media_type == 'video':
                return MediaProcessor._validate_video(temp_filename, post.caption or '📸 Instagram Media')
            elif media_type == 'image':
                return MediaProcessor._validate_image(temp_filename, post.caption or '📸 Instagram Media')
        except Exception as e:
            print(f"Error processing media: {e}")
            return None

    @staticmethod
    def _validate_video(filename, caption):
        video = cv2.VideoCapture(filename)
        width, height, fps = int(video.get(cv2.CAP_PROP_FRAME_WIDTH)), int(video.get(cv2.CAP_PROP_FRAME_HEIGHT)), video.get(cv2.CAP_PROP_FPS)
        duration = video.get(cv2.CAP_PROP_FRAME_COUNT) / fps if fps > 0 else 0
        video.release()
        if width == 0 or height == 0 or duration == 0:
            os.remove(filename)
            return None
        return {'filename': filename, 'type': 'video', 'caption': caption, 'duration': int(duration)}

    @staticmethod
    def _validate_image(filename, caption):
        try:
            img = Image.open(filename)
            img.verify()
            width, height = img.size
            if width == 0 or height == 0:
                os.remove(filename)
                return None
            return {'filename': filename, 'type': 'image', 'caption': caption}
        except:
            os.remove(filename)
            return None

@app_pyro.on_message(filters.regex(r'(instagram\.com/(reel/|p/|stories/|s/aGlnaGxpZ2h0).*?)'))
async def handle_instagram_url(client, message):
    url = message.text
    processing_msg = await message.reply_text("🔄 Downloading Media...")
    try:
        result = MediaProcessor.process_instagram_media(url)
        await processing_msg.edit_text("📤 Uploading Media...")
        if result:
            await _send_single_media(client, message, result)
        else:
            await processing_msg.edit_text("❌ Failed to process the Instagram media.")
        await processing_msg.delete()
    except Exception as e:
        await processing_msg.edit_text(f"❌ Error: {str(e)}")

async def _send_single_media(client, message, media_info):
    try:
        if media_info['type'] == 'video':
            await client.send_video(
                chat_id=message.from_user.id,
                video=media_info['filename'],
                caption=media_info['caption']
            )
        elif media_info['type'] == 'image':
            await client.send_photo(
                chat_id=message.from_user.id,
                photo=media_info['filename'],
                caption=media_info['caption']
            )
        os.remove(media_info['filename'])
    except Exception as e:
        await message.reply_text(f"❌ Could not send media: {e}")

# Main function for YouTube Bot
def main_youtube_bot():
    app_telegram = Application.builder().token(BOT_TOKEN).build()

    app_telegram.add_handler(CommandHandler("start", start))
    app_telegram.add_handler(CommandHandler("video", video))
    app_telegram.add_handler(CommandHandler("audio", audio))
    app_telegram.add_handler(CommandHandler("link", link))
    app_telegram.add_handler(CallbackQueryHandler(button_handler))

    app_telegram.run_polling()

# Start both bots
if __name__ == "__main__":
    import threading

    youtube_bot_thread = threading.Thread(target=main_youtube_bot)
    youtube_bot_thread.start()

    app_pyro.run()