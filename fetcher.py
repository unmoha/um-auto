import hashlib
import feedparser
import asyncio
from telethon import TelegramClient
from telethon.tl.types import Channel, User, MessageMediaPhoto
from datetime import datetime, timedelta
import re
import requests

class NewsFetcher:
    def __init__(self, client):
        # Primary RSS feeds (BBC Sport + fallback sources)
        self.rss_feeds = {
            "BBC Sport": "http://feeds.bbci.co.uk/sport/football/rss.xml",
            "BBC Sport Live": "http://feeds.bbci.co.uk/sport/football/live/rss.xml",
            "ESPN Soccer": "https://www.espn.com/espn/rss/soccer/news",
            "Goal.com": "https://www.goal.com/feeds/news.rss",
        }
        self.telegram_channels = [
            "@FabrizioRomano", "@footballinsider247", "@bisrat_sport_433et",
            "@Sport_433et", "@tikvahethsport", "@dailysportethiopia",
            "@soccer_ethiopia", "@ethiopianlea", "@Obnsports",
            "@EthiopiaWFL", "@Dirreeispoorti", "@allfootballss",
            "@transfer_news_football", "@deadlinedaylive_en", "@FootyNews",
            "@Sky_Sports_Football", "@TrollFootball", "@brfootball",
            "@GoalNews", "@SquawkaFootball", "@OptaJoe", "@EPLIndex",
            "@the_manutd_way", "@LFCNews", "@ChelseaFCNews", "@Arsenal_News",
            "@BarcaNews", "@RealMadridNews", "@BVBNews", "@PSGNews",
            "@SerieA_EN", "@LaLigaEN", "@Bundesliga_EN", "@African_Football",
            "@EthiopianFootball"
        ]
        self.client = client

    async def fetch_all_news(self):
        all_news = []

        print("Fetching RSS feeds (BBC Sport + fallbacks)...")
        rss_news = self.fetch_rss_news()
        print(f"Fetched {len(rss_news)} items from RSS.")
        all_news.extend(rss_news)

        print("Fetching Telegram channels...")
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
                    title = entry.get('title', 'No Title')
                    summary = entry.get('summary', '')
                    content = f"{title}. {summary}"
                    # Stable hash for content
                    news_id = hashlib.md5(content.encode('utf-8')).hexdigest()

                    image_url = self._extract_image(entry)

                    news_items.append({
                        "id": f"rss_{news_id}",
                        "headline": title,
                        "content": content,
                        "source": source,
                        "image_url": image_url
                    })
            except Exception as e:
                print(f"Error fetching RSS from {source}: {e}")
        return news_items

    def _extract_image(self, entry):
        """Extract image from RSS entry with multiple fallback methods"""
        try:
            # Method 1: media_content
            if hasattr(entry, 'media_content') and entry.media_content:
                for media in entry.media_content:
                    if 'url' in media and media.get('type', '').startswith('image'):
                        return media['url']
            
            # Method 2: enclosures
            if hasattr(entry, 'enclosures') and entry.enclosures:
                for enc in entry.enclosures:
                    if 'url' in enc and enc.get('type', '').startswith('image'):
                        return enc['url']
            
            # Method 3: image tag
            if hasattr(entry, 'image') and hasattr(entry.image, 'href'):
                return entry.image.href
            
            # Method 4: HTML img tag in summary
            if 'summary' in entry:
                img_match = re.search(r'<img.*?src="(.*?)"', entry.summary)
                if img_match:
                    return img_match.group(1)
            
            # Method 5: media_thumbnail
            if hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
                return entry.media_thumbnail[0]['url']
            
            # Method 6: link with image pattern
            if 'link' in entry:
                return entry['link']
                
        except Exception as e:
            print(f"Error extracting image: {e}")
        
        return None

    async def fetch_telegram_news(self):
        news_items = []
        # Focus on very fresh news (last 3 hours) for high frequency
        time_threshold = datetime.now() - timedelta(hours=3)

        for channel in self.telegram_channels:
            try:
                entity = await self.client.get_entity(channel)
                # Increased limit to fetch more messages per channel
                async for msg in self.client.iter_messages(entity, limit=50):
                    if msg.date < time_threshold:
                        break
                    # Ensure message has sufficient content
                    if msg.text and len(msg.text) > 40:
                        news_id = f"tg_{channel}_{msg.id}"
                        news_items.append({
                            "id": news_id,
                            "headline": msg.text.split('\n')[0][:100],
                            "content": msg.text,
                            "source": channel,
                            "image_url": "TELETHON_PHOTO_PLACEHOLDER" if msg.photo else None,
                            "telegram_message": msg
                        })
            except Exception as e:
                print(f"Error fetching Telegram from {channel}: {e}")
        return news_items
