import asyncio
import os
import time
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.tl.types import MessageMediaPhoto

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
            print("Client not authorized. Please ensure TELEGRAM_PHONE and TELEGRAM_PASSWORD are set for initial login.")
            # This part might require interactive login if not already authorized.
            # For GitHub Actions, it's expected to be authorized already or use bot token.
            # If using bot token, client.start(bot_token=BOT_TOKEN) is used.
            # For user account, it needs phone and password.
            # For simplicity in GH Actions, we assume session is already created or bot token is used.
            if BOT_TOKEN:
                await client.start(bot_token=BOT_TOKEN)
            elif TELEGRAM_PHONE:
                await client.start(phone=TELEGRAM_PHONE, password=TELEGRAM_PASSWORD)
            else:
                print("No bot token or phone number provided for authorization.")
                return
        print("Telegram client for posting connected.")

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
                    # Download photo from original Telegram message
                    original_message = news_item['telegram_message']
                    if original_message.photo:
                        photo_path = await original_message.download_media(file=bytes) # Download as bytes
                        await client.send_file(CHANNEL_USERNAME, photo_path, caption=message_text)
                    else:
                        await client.send_message(CHANNEL_USERNAME, message_text)
                elif news_item['image_url']:
                    # For RSS images, download and send
                    try:
                        response = requests.get(news_item['image_url'], timeout=10)
                        if response.status_code == 200:
                            await client.send_file(CHANNEL_USERNAME, response.content, caption=message_text)
                        else:
                            print(f"Could not download image from {news_item['image_url']}. Posting text only.")
                            await client.send_message(CHANNEL_USERNAME, message_text)
                    except Exception as img_e:
                        print(f"Error downloading or sending image {news_item['image_url']}: {img_e}. Posting text only.")
                        await client.send_message(CHANNEL_USERNAME, message_text)
                else:
                    await client.send_message(CHANNEL_USERNAME, message_text)

                storage.add_posted(news_id)
                new_posts_count += 1
                print(f"Successfully posted news from {news_item['source']}. Total new posts: {new_posts_count}")

                # Delay between posts to avoid spamming
                await asyncio.sleep(10)

            except Exception as e:
                print(f"Error processing or posting news item {news_item['headline']}: {e}")
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
