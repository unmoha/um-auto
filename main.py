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

# Global client instance to reuse across all posts - FIXES ISSUE #1
_client_instance = None

async def get_client():
    """Get or create a persistent Telegram client instance.
    This ensures we only authenticate once and reuse the session for all posts."""
    global _client_instance
    if _client_instance is None:
        _client_instance = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    return _client_instance

async def authorize_client(client):
    """Authorize the client once and reuse the session.
    After first authorization, Telethon stores the session and won't ask for login code again."""
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
        print("✓ Client authorized successfully!")
    else:
        print("✓ Client is already authorized (using existing session - NO login code needed!)")

async def run_bot():
    print("Initializing bot...")

    # Get persistent client - reuses session across runs
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

        # 1. Fetch news from BBC Sport (primary) + multiple fallback sources
        all_news = await fetcher.fetch_all_news()
        print(f"Total news items gathered: {len(all_news)}")

        # 2. Process and Post
        new_posts_count = 0

        for news_item in all_news:
            if storage.is_posted(news_item['id']):
                continue

            if new_posts_count >= 5:  # Limit per run
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

                # ISSUE #3 FIX: Always get an image - either from URL or generate placeholder
                image_data = None
                if news_item.get('image_url'):
                    image_data = await image_service.get_image(
                        news_item['image_url'],
                        news_item['headline']
                    )
                else:
                    # Generate placeholder if no image available
                    image_data = image_service._generate_placeholder_image(news_item['headline'])

                # Send with image
                try:
                    if image_data:
                        await client.send_file(
                            CHANNEL_USERNAME,
                            image_data,
                            caption=message_text
                        )
                        print(f"✓ Posted with image: {news_item['headline']}")
                    else:
                        # Fallback to text only if image generation fails
                        await client.send_message(CHANNEL_USERNAME, message_text)
                        print(f"✓ Posted (text only): {news_item['headline']}")
                except (PhotoInvalidError, MessageTooLongError) as e:
                    print(f"Error sending image for '{news_item['headline']}': {e}. Posting text only.")
                    await client.send_message(CHANNEL_USERNAME, message_text)
                except FloodWaitError as e:
                    print(f"FloodWaitError: Waiting {e.seconds} seconds before retrying.")
                    await asyncio.sleep(e.seconds)
                    await client.send_message(CHANNEL_USERNAME, message_text)
                except Exception as e:
                    print(f"Error posting: {e}")
                    continue

                # Mark as posted
                storage.add_posted(news_item['id'])
                new_posts_count += 1
                await asyncio.sleep(2)  # Rate limiting between posts

            except Exception as e:
                print(f"Error processing news item: {e}")
                continue

        print(f"\nBot completed. Posted {new_posts_count} new items.")

    except Exception as e:
        print(f"Bot error: {e}")
    finally:
        print("Disconnecting client...")
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(run_bot())
