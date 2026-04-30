import asyncio
import os
from dotenv import load_dotenv
from telethon import TelegramClient
import requests
from telethon.errors import ChannelInvalidError, ChannelPrivateError, PeerIdInvalidError, UserNotParticipantError, ChatWriteForbiddenError, MessageTooLongError, PhotoInvalidError, AuthKeyUnregisteredError, SessionPasswordNeededError, FloodWaitError

from fetcher import NewsFetcher
from translator import Translator
from formatter import Formatter
from storage import Storage

load_dotenv()

API_ID = int(os.getenv('API_ID')) # Ensure API_ID is an integer
API_HASH = os.getenv('API_HASH')
BOT_TOKEN = os.getenv('BOT_TOKEN')
CHANNEL_USERNAME = os.getenv('CHANNEL_USERNAME')
SESSION_NAME = os.getenv('SESSION_NAME', 'football_news_bot')
TELEGRAM_PHONE = os.getenv('TELEGRAM_PHONE')
TELEGRAM_PASSWORD = os.getenv('TELEGRAM_PASSWORD')

async def run_bot():
    print("Initializing bot...")

    # Initialize Telegram client
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

    # Initialize components with the shared client
    fetcher = NewsFetcher(client)
    translator = Translator()
    formatter = Formatter()
    storage = Storage()

    try:
        print("Connecting Telegram client...")
        await client.connect()

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
                    print("Two-factor authentication is enabled. Please run the script locally once to enter the password.")
                    return
                except Exception as e:
                    print(f"Error during user authorization: {e}")
                    return
            else:
                print("Error: No bot token or phone number provided for authorization. Cannot proceed.")
                return

        print("Telegram client connected and authorized.")
        print(f"Target CHANNEL_USERNAME: {CHANNEL_USERNAME}")

        # --- DIAGNOSTIC: Send a simple test message ---
        try:
            await client.send_message(CHANNEL_USERNAME, "Bot started successfully and is attempting to post news!")
            print("DIAGNOSTIC: Sent test message to channel.")
        except (ChannelInvalidError, ChannelPrivateError, PeerIdInvalidError, UserNotParticipantError, ChatWriteForbiddenError, AuthKeyUnregisteredError) as e:
            print(f"DIAGNOSTIC ERROR: Failed to send test message to channel '{CHANNEL_USERNAME}'. Please check channel username and bot/user permissions. Error: {e}")
            print("Exiting as channel access seems problematic.")
            return
        except FloodWaitError as e:
            print(f"DIAGNOSTIC ERROR: FloodWaitError while sending test message. Waiting for {e.seconds} seconds.")
            await asyncio.sleep(e.seconds)
            try:
                await client.send_message(CHANNEL_USERNAME, "Bot started successfully and is attempting to post news! (Retry after FloodWait)")
                print("DIAGNOSTIC: Sent test message to channel after FloodWait.")
            except Exception as retry_e:
                print(f"DIAGNOSTIC ERROR: Failed to send test message after FloodWait: {retry_e}")
                return
        except Exception as e:
            print(f"DIAGNOSTIC ERROR: An unexpected error occurred while sending test message: {e}")
            return
        # --- END DIAGNOSTIC ---

        # 1. Fetch
        all_news = await fetcher.fetch_all_news()
        print(f"Total news items gathered: {len(all_news)}")

        # 2. Process and Post
        new_posts_count = 0

        for news_item in all_news:
            if storage.is_posted(news_item['id']):
                # print(f"Skipping duplicate: {news_item['headline']}")
                continue

            if new_posts_count >= 5: # Limit per run
                print("Reached post limit for this run. Skipping remaining news items.")
                break

            print(f"Processing: {news_item['headline']}")

            try:
                # Translate
                cleaned = formatter.clean_text(news_item['content'])
                amharic_text = translator.translate_to_amharic(cleaned)

                # Apply viral rewrite (optional)
                final_content = formatter.viral_rewrite(amharic_text) # Apply to translated text

                # Format
                message_text = formatter.format_news_message(
                    news_item['headline'], final_content, news_item['source']
                )

                # Send
                if news_item['image_url'] == "TELETHON_PHOTO_PLACEHOLDER" and 'telegram_message' in news_item:
                    original_message = news_item['telegram_message']
                    if original_message.photo:
                        try:
                            # Download as bytes for send_file
                            photo_bytes = await original_message.download_media(file=bytes)
                            await client.send_file(CHANNEL_USERNAME, photo_bytes, caption=message_text)
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
                            # Send image bytes directly
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

                storage.add_posted(news_item['id'])
                new_posts_count += 1
                print(f"Successfully posted news from {news_item['source']}. Total new posts: {new_posts_count}")
                await asyncio.sleep(5) # Delay to avoid flood limits

            except (ChannelInvalidError, ChannelPrivateError, PeerIdInvalidError, UserNotParticipantError, ChatWriteForbiddenError, AuthKeyUnregisteredError) as e:
                print(f"TELEGRAM POSTING ERROR for '{news_item['headline']}': Channel access issue. Error: {e}")
                print("Please ensure the bot/user has correct permissions and the channel username is correct.")
                # This is a critical error for the channel, might as well stop trying to post to it
                break
            except MessageTooLongError as e:
                print(f"TELEGRAM POSTING ERROR for '{news_item['headline']}': Message too long. Error: {e}")
                # Try to send without image or truncate message if this happens often
                await client.send_message(CHANNEL_USERNAME, message_text[:4000]) # Telegram message limit is 4096 characters
                storage.add_posted(news_item['id']) # Mark as posted even if truncated
                new_posts_count += 1
                await asyncio.sleep(5)
            except FloodWaitError as e:
                print(f"TELEGRAM POSTING ERROR for '{news_item['headline']}': FloodWaitError. Waiting for {e.seconds} seconds.")
                await asyncio.sleep(e.seconds + 5) # Add a buffer
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
