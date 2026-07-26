import asyncio
import os
from dotenv import load_dotenv
from telethon import TelegramClient
import requests
from telethon.errors import ChannelInvalidError, ChannelPrivateError, PeerIdInvalidError, UserNotParticipantError, ChatWriteForbiddenError, MessageTooLongError, PhotoInvalidError, AuthKeyUnregisteredError, FloodWaitError, SessionPasswordNeededError

from fetcher import NewsFetcher
from translator import Translator
from formatter import Formatter
from storage import Storage
from image_service import ImageService

load_dotenv()

API_ID = int(os.getenv('API_ID'))
API_HASH = os.getenv('API_HASH')
BOT_TOKEN = os.getenv('BOT_TOKEN')
CHANNEL_USERNAME = os.getenv('CHANNEL_USERNAME')
SESSION_NAME = os.getenv('SESSION_NAME', 'football_news_bot')
TELEGRAM_PHONE = os.getenv('TELEGRAM_PHONE')
TELEGRAM_PASSWORD = os.getenv('TELEGRAM_PASSWORD')

# Global client instance to reuse across all posts
_client_instance = None

async def get_client():
    """Get or create a persistent Telegram client instance."""
    global _client_instance
    if _client_instance is None:
        _client_instance = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    return _client_instance

async def authorize_client(client):
    """Authorize the client once and reuse the session."""
    if not await client.is_user_authorized():
        print("Client not authorized. Attempting authorization...")
        if BOT_TOKEN:
            print("Attempting to authorize with BOT_TOKEN.")
            await client.start(bot_token=BOT_TOKEN)
        elif TELEGRAM_PHONE:
            print(f"Attempting to authorize with TELEGRAM_PHONE: {TELEGRAM_PHONE}")
            try:
                await client.start(phone=TELEGRAM_PHONE, password=TELEGRAM_PASSWORD)
            except SessionPasswordNeededError:
                print("Two-factor authentication is enabled.")
                raise
        else:
            raise ValueError("No bot token or phone number provided for authorization.")
        print("Client authorized successfully!")
    else:
        print("Client is already authorized (using existing session).")

async def run_bot():
    print("Initializing bot...")

    # Get persistent client
    client = await get_client()

    # Initialize components with the shared client
    fetcher = NewsFetcher(client)
    translator = Translator()
    formatter = Formatter()
    storage = Storage()
    image_service = ImageService()

    try:
        print("Connecting Telegram client...")
        await client.connect()

        # Authorize only once per session
        await authorize_client(client)

        print("Telegram client connected and authorized.")
        print(f"Target CHANNEL_USERNAME: {CHANNEL_USERNAME}")

        # --- DIAGNOSTIC: Send a simple test message ---
        try:
            await client.send_message(CHANNEL_USERNAME, "Bot started successfully and is attempting to post news!")
            print("DIAGNOSTIC: Sent test message to channel.")
        except (ChannelInvalidError, ChannelPrivateError, PeerIdInvalidError, UserNotParticipantError, ChatWriteForbiddenError, AuthKeyUnregisteredError) as e:
            print(f"DIAGNOSTIC ERROR: Failed to send test message to channel '{CHANNEL_USERNAME}'. Error: {e}")
            return
        except FloodWaitError as e:
            print(f"DIAGNOSTIC ERROR: FloodWaitError. Waiting for {e.seconds} seconds.")
            await asyncio.sleep(e.seconds)
        except Exception as e:
            print(f"DIAGNOSTIC ERROR: An unexpected error occurred: {e}")
            return
        # --- END DIAGNOSTIC ---

        # 1. Fetch
        all_news = await fetcher.fetch_all_news()
        print(f"Total news items gathered: {len(all_news)}")

        # 2. Process and Post
        new_posts_count = 0

        for news_item in all_news:
            if storage.is_posted(news_item['id']):
                continue

            if new_posts_count >= 5:
                print("Reached post limit for this run. Skipping remaining news items.")
                break

            print(f"Processing: {news_item['headline']}")

            try:
                # Translate
                cleaned = formatter.clean_text(news_item['content'])
                amharic_text = translator.translate_to_amharic(cleaned)

                # Apply viral rewrite
                final_content = formatter.viral_rewrite(amharic_text)

                # Format
                message_text = formatter.format_news_message(
                    news_item['headline'], final_content, news_item['source']
                )

                # Get image (prioritize external URLs, then Telegram photos, then generate placeholder)
                image_data = None
                image_source = None

                if news_item.get('image_url') and news_item['image_url'] != "TELETHON_PHOTO_PLACEHOLDER":
                    # Try to download external image
                    try:
                        image_data = image_service.download_image(news_item['image_url'])
                        image_source = "external"
                        print(f"Using image from external source: {news_item['image_url']}")
                    except Exception as e:
                        print(f"Failed to download external image: {e}")
                        image_data = None

                if not image_data and 'telegram_message' in news_item and news_item['telegram_message'].photo:
                    # Try to use Telegram photo
                    try:
                        image_data = await image_service.download_telegram_photo(news_item['telegram_message'])
                        image_source = "telegram"
                        print(f"Using image from Telegram message")
                    except Exception as e:
                        print(f"Failed to download Telegram image: {e}")
                        image_data = None

                if not image_data:
                    # Generate a placeholder image with the headline
                    try:
                        image_data = image_service.generate_placeholder_image(news_item['headline'], news_item['source'])
                        image_source = "generated"
                        print(f"Generated placeholder image for: {news_item['headline']}")
                    except Exception as e:
                        print(f"Failed to generate placeholder image: {e}")

                # Send the post
                try:
                    if image_data:
                        await client.send_file(CHANNEL_USERNAME, image_data, caption=message_text)
                        print(f"Posted with image ({image_source}): {news_item['headline']}")
                    else:
                        await client.send_message(CHANNEL_USERNAME, message_text)
                        print(f"Posted text only (no image available): {news_item['headline']}")
                except MessageTooLongError:
                    print(f"Message too long. Truncating...")
                    if image_data:
                        await client.send_file(CHANNEL_USERNAME, image_data, caption=message_text[:1024])
                    else:
                        await client.send_message(CHANNEL_USERNAME, message_text[:4096])
                    storage.add_posted(news_item['id'])
                    new_posts_count += 1
                    await asyncio.sleep(5)
                    continue

                storage.add_posted(news_item['id'])
                new_posts_count += 1
                print(f"Successfully posted from {news_item['source']}. Total: {new_posts_count}")
                await asyncio.sleep(5)

            except (ChannelInvalidError, ChannelPrivateError, PeerIdInvalidError, UserNotParticipantError, ChatWriteForbiddenError, AuthKeyUnregisteredError) as e:
                print(f"TELEGRAM POSTING ERROR: Channel access issue. Error: {e}")
                break
            except FloodWaitError as e:
                print(f"TELEGRAM POSTING ERROR: FloodWaitError. Waiting for {e.seconds} seconds.")
                await asyncio.sleep(e.seconds + 5)
            except Exception as e:
                print(f"An unexpected error occurred while processing '{news_item['headline']}': {e}")
                continue

    except Exception as e:
        print(f"An unhandled error occurred: {e}")
    finally:
        print("Disconnecting Telegram client...")
        await client.disconnect()
        print("Bot finished.")

if __name__ == '__main__':
    if not API_ID or not API_HASH:
        print("Error: API_ID and API_HASH must be set in the .env file.")
    elif not CHANNEL_USERNAME:
        print("Error: CHANNEL_USERNAME must be set in the .env file.")
    else:
        asyncio.run(run_bot())
