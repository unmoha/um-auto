import feedparser
import asyncio
from telethon import TelegramClient
from telethon.tl.types import Channel, User, MessageMediaPhoto
import re
import requests
from datetime import datetime, timedelta

class NewsFetcher:
    def __init__(self, api_id, api_hash, session_name, telegram_phone=None, telegram_password=None):
        self.rss_feeds = {
            "BBC Football": "http://feeds.bbci.co.uk/sport/football/rss.xml",
            "ESPN Soccer": "https://www.espn.com/espn/rss/soccer/news",
            "Goal.com": "https://www.goal.com/feeds/news.rss",
            "Sky Sports": "https://www.skysports.com/rss/12040"
        }
        self.telegram_channels = [
            "@FabrizioRomano", "@footballinsider247", "@bisrat_sport_433et",
            "@Sport_433et", "@tikvahethsport", "@dailysportethiopia",
            "@soccer_ethiopia", "@ethiopianlea", "@Obnsports",
            "@EthiopiaWFL", "@Dirreeispoorti", "@allfootballss",
            "@transfer_news_football", "@deadlinedaylive_en", "@FootyNews",
            "@Sky_Sports_Football"
        ]
        self.client = TelegramClient(session_name, api_id, api_hash)
        self.telegram_phone = telegram_phone
        self.telegram_password = telegram_password

    async def _connect_telegram(self):
        print("Connecting to Telegram...")
        try:
            await self.client.connect()
            if not await self.client.is_user_authorized():
                if self.telegram_phone:
                    await self.client.start(phone=self.telegram_phone, password=self.telegram_password)
                else:
                    print("Please run the script once interactively to authorize your Telegram account.")
                    await self.client.start()
            print("Telegram client connected.")
        except Exception as e:
            print(f"Error connecting to Telegram: {e}")
            raise

    async def fetch_all_news(self):
        all_news = []
        await self._connect_telegram()
        all_news.extend(self.fetch_rss_news())
        all_news.extend(await self.fetch_telegram_news())
        await self.client.disconnect()
        return all_news

    def fetch_rss_news(self):
        news_items = []
        for source, url in self.rss_feeds.items():
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries:
                    title = entry.title if hasattr(entry, 'title') else "No Title"
                    summary = entry.summary if hasattr(entry, 'summary') else ""
                    link = entry.link if hasattr(entry, 'link') else ""

                    # Use a combination of title and summary for content
                    content = f"{title}. {summary}"

                    # Generate a unique ID for duplicate checking
                    news_id = f"rss_{source}_{hash(title + summary)}"

                    news_items.append({
                        "id": news_id,
                        "headline": title,
                        "content": content,
                        "source": source,
                        "image_url": self._extract_image_from_rss(entry),
                        "link": link
                    })
            except Exception as e:
                print(f"Error fetching RSS from {source}: {e}")
        return news_items

    def _extract_image_from_rss(self, entry):
        # Look for common image fields in RSS entries
        if hasattr(entry, 'media_content') and entry.media_content:
            for media in entry.media_content:
                if 'url' in media and media.get('type', '').startswith('image'):
                    return media['url']
        if hasattr(entry, 'enclosures') and entry.enclosures:
            for enc in entry.enclosures:
                if 'url' in enc and enc.get('type', '').startswith('image'):
                    return enc['url']
        if hasattr(entry, 'image') and hasattr(entry.image, 'href'):
            return entry.image.href

        # Try to find image in summary/content HTML
        if hasattr(entry, 'summary'):
            match = re.search(r'<img.*?src="(.*?)"', entry.summary)
            if match:
                return match.group(1)
        return None

    async def fetch_telegram_news(self):
        news_items = []
        # Fetch messages from the last 24 hours
        yesterday = datetime.now() - timedelta(hours=24)

        for channel_username in self.telegram_channels:
            try:
                entity = await self.client.get_entity(channel_username)

                # Iterate through messages, stopping when we hit messages older than 'yesterday'
                async for message in self.client.iter_messages(entity, limit=50): # Limit to 50 messages per channel
                    if message.date < yesterday:
                        break # Stop if message is older than 24 hours

                    if message.text:
                        headline = message.text.split('\n')[0] if '\n' in message.text else message.text[:100]
                        content = message.text
                        news_id = f"tg_{channel_username}_{message.id}"

                        image_url = None
                        if message.photo:
                            # Telethon's download_media returns a file path
                            # For now, we'll just indicate presence of photo
                            # Actual download will happen when posting
                            image_url = "TELETHON_PHOTO_PLACEHOLDER"

                        news_items.append({
                            "id": news_id,
                            "headline": headline,
                            "content": content,
                            "source": channel_username,
                            "image_url": image_url,
                            "telegram_message": message # Store the full message object for later image download
                        })
            except Exception as e:
                print(f"Error fetching Telegram from {channel_username}: {e}")
        return news_items
