import asyncio
import os
import time
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.tl.types import MessageMediaPhoto
from telethon.errors import ChannelInvalidError, ChannelPrivateError, PeerIdInvalidError, UserNotParticipantError, ChatWriteForbiddenError, MessageTooLongError, PhotoInvalidError

from fetcher import NewsFetcher
from translator import Translator
from formatter import Formatter
from storage import Storage

# Load environment variables from .env file
load_dotenv()

API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')
BOT_TOKEN = os.getenv('BOT_TOKEN')
CHANNEL_USERNAME = os.getenv('CHANNEL_USERNAME')
SESSION_NAME = os.getenv('SESSION_NAME', 'telegram_bot_session')
TELEGRAM_PHONE = os.getenv('TELEGRAM_PHONE')
TELEGRAM_PASSWORD = os.getenv('TELEGRAM_PASSWORD')

# Initialize components
fetcher = NewsFetcher(API_ID, API_HASH, SESSION_NAME, TELEGRAM_PHONE, TELEGRAM_PASSWORD)
translator = Translator()
formatter = Formatter()
storage = Storage()

async def run_bot():
    print("Bot started...")

    # Initialize Telegram client for posting
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

    try:
        print("Connecting Telegram client for posting...")
        await client.connect()
        if not await client.is_user_authorized():
            print("Client not authorized. Attempting authorization...")
            if BOT_TOKEN:
                print("Attempting to authorize with BOT_TOKEN.")
                await client.start(bot_token=BOT_TOKEN)
            elif TELEGRAM_PHONE:
                print(f"Attempting to authorize with TELEGRAM_PHONE: {TELEGRAM_PHONE}")
                await client.start(phone=TELEGRAM_PHONE, password=TELEGRAM_PASSWORD)
            else:
                print("Error: No bot token or phone number provided for authorization. Cannot proceed.")
                return
        print("Telegram client for posting connected and authorized.")
        print(f"Target CHANNEL_USERNAME: {CHANNEL_USERNAME}")

        # --- DIAGNOSTIC: Send a simple test message ---
        try:
            await client.send_message(CHANNEL_USERNAME, "Bot started successfully and is attempting to post news!")
            print("DIAGNOSTIC: Sent test message to channel.")
        except (ChannelInvalidError, ChannelPrivateError, PeerIdInvalidError, UserNotParticipantError, ChatWriteForbiddenError) as e:
            print(f"DIAGNOSTIC ERROR: Failed to send test message to channel '{CHANNEL_USERNAME}'. Please check channel username and bot/user permissions. Error: {e}")
            print("Exiting as channel access seems problematic.")
            return
        except Exception as e:
            print(f"DIAGNOSTIC ERROR: An unexpected error occurred while sending test message: {e}")
            return
        # --- END DIAGNOSTIC ---

        all_news = await fetcher.fetch_all_news()
        print(f"Fetched {len(all_news)} news items from all sources.")

        new_posts_count = 0
        for news_item in all_news:
            news_id = news_item['id']
            if storage.is_posted(news_id):
                # print(f"Skipping duplicate: {news_item['headline']}")
                continue

            # Anti-spam logic: limit posts per run
            if new_posts_count >= 5: # Max 5 posts per run to avoid flooding
                print("Reached post limit for this run. Exiting.")
                break

            try:
                # Clean content
                cleaned_content = formatter.clean_text(news_item['content'])

                # Translate content
                translated_content = translator.translate_to_amharic(cleaned_content)

                # Apply viral rewrite (optional)
                final_content = formatter.viral_rewrite(translated_content)

                # Format message
                message_text = formatter.format_news_message(
                    news_item['headline'],
                    final_content,
                    news_item['source']
                )

                # Post to Telegram channel
                print(f"Attempting to post: {news_item['headline']} from {news_item['source']}")

                if news_item['image_url'] == "TELETHON_PHOTO_PLACEHOLDER" and 'telegram_message' in news_item:
                    original_message = news_item['telegram_message']
                    if original_message.photo:
                        try:
                            photo_path = await original_message.download_media(file=bytes) # Download as bytes
                            await client.send_file(CHANNEL_USERNAME, photo_path, caption=message_text)
                            print(f"Posted with image from Telegram: {news_item['headline']}")
                        except (PhotoInvalidError, MessageTooLongError) as e:
                            print(f"Error sending Telegram image for '{news_item['headline']}': {e}. Posting text only.")
                            await client.send_message(CHANNEL_USERNAME, message_text)
                        except Exception as e:
                            print(f"Unexpected error sending Telegram image for '{news_item['headline']}': {e}. Posting text only.")
                            await client.send_message(CHANNEL_USERNAME, message_text)
                    else:
                        await client.send_message(CHANNEL_USERNAME, message_text)
                        print(f"Posted text only (no photo in original Telegram message): {news_item['headline']}")
                elif news_item['image_url']:
                    try:
                        response = requests.get(news_item['image_url'], timeout=10)
                        if response.status_code == 200:
                            await client.send_file(CHANNEL_USERNAME, response.content, caption=message_text)
                            print(f"Posted with image from RSS: {news_item['headline']}")
                        else:
                            print(f"Could not download image from {news_item['image_url']} (status {response.status_code}). Posting text only.")
                            await client.send_message(CHANNEL_USERNAME, message_text)
                    except (requests.exceptions.RequestException, PhotoInvalidError, MessageTooLongError) as e:
                        print(f"Error downloading or sending RSS image {news_item['image_url']} for '{news_item['headline']}': {e}. Posting text only.")
                        await client.send_message(CHANNEL_USERNAME, message_text)
                    except Exception as e:
                        print(f"Unexpected error with RSS image for '{news_item['headline']}': {e}. Posting text only.")
                        await client.send_message(CHANNEL_USERNAME, message_text)
                else:
                    await client.send_message(CHANNEL_USERNAME, message_text)
                    print(f"Posted text only: {news_item['headline']}")

                storage.add_posted(news_id)
                new_posts_count += 1
                print(f"Successfully posted news from {news_item['source']}. Total new posts: {new_posts_count}")

                # Delay between posts to avoid spamming
                await asyncio.sleep(10)

            except (ChannelInvalidError, ChannelPrivateError, PeerIdInvalidError, UserNotParticipantError, ChatWriteForbiddenError) as e:
                print(f"TELEGRAM POSTING ERROR for '{news_item['headline']}': Channel access issue. Error: {e}")
                print("Please ensure the bot/user has correct permissions and the channel username is correct.")
                # Don't break, try to post other news if this is a transient issue or specific to one channel
            except MessageTooLongError as e:
                print(f"TELEGRAM POSTING ERROR for '{news_item['headline']}': Message too long. Error: {e}")
                # Consider truncating message_text here if this happens often
            except Exception as e:
                print(f"An unexpected error occurred while processing or posting news item '{news_item['headline']}': {e}")
                # Continue to next news item even if one fails

    except Exception as e:
        print(f"An unhandled error occurred during bot execution: {e}")
    finally:
        print("Disconnecting Telegram client...")
        await client.disconnect()
        print("Bot finished.")

if __name__ == '__main__':
    # Ensure API_ID and API_HASH are set
    if not API_ID or not API_HASH:
        print("Error: API_ID and API_HASH must be set in the .env file.")
    elif not CHANNEL_USERNAME:
        print("Error: CHANNEL_USERNAME must be set in the .env file.")
    else:
        asyncio.run(run_bot())
