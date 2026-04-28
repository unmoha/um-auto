import feedparser
import asyncio
from telethon import TelegramClient
from telethon.tl.types import Channel, User, MessageMediaPhoto
import re
import requests
from datetime import datetime, timedelta
import hashlib

class NewsFetcher:
    def __init__(self, client):
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
        self.client = client

    async def fetch_all_news(self):
        all_news = []

        print("Starting RSS news fetch...")
        rss_news = self.fetch_rss_news()
        print(f"Fetched {len(rss_news)} items from RSS.")
        all_news.extend(rss_news)

        print("Starting Telegram news fetch...")
        tg_news = await self.fetch_telegram_news()
        print(f"Fetched {len(tg_news)} items from Telegram.")
        all_news.extend(tg_news)

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

                    content = f"{title}. {summary}"
                    # Use MD5 for a stable ID across different runs
                    news_id = hashlib.md5(content.encode('utf-8')).hexdigest()

                    news_items.append({
                        "id": f"rss_{news_id}",
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
        if hasattr(entry, 'summary'):
            match = re.search(r'<img.*?src="(.*?)"', entry.summary)
            if match:
                return match.group(1)
        return None

    async def fetch_telegram_news(self):
        news_items = []
        yesterday = datetime.now() - timedelta(hours=24)

        for channel_username in self.telegram_channels:
            try:
                entity = await self.client.get_entity(channel_username)
                async for message in self.client.iter_messages(entity, limit=10):
                    if message.date < yesterday:
                        break

                    if message.text and len(message.text) > 20:
                        headline = message.text.split('\n')[0][:100]
                        news_id = f"tg_{channel_username}_{message.id}"

                        image_url = "TELETHON_PHOTO_PLACEHOLDER" if message.photo else None

                        news_items.append({
                            "id": news_id,
                            "headline": headline,
                            "content": message.text,
                            "source": channel_username,
                            "image_url": image_url,
                            "telegram_message": message
                        })
            except Exception as e:
                print(f"Error fetching Telegram from {channel_username}: {e}")
        return news_items
