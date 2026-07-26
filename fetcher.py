import hashlib
import feedparser
import asyncio
from telethon import TelegramClient
from telethon.tl.types import Channel, User, MessageMediaPhoto
from datetime import datetime, timedelta
import re

class NewsFetcher:
    def __init__(self, client):
        # Multiple sources for football news - not just BBC!
        self.rss_feeds = {
            "BBC Football": "http://feeds.bbci.co.uk/sport/football/rss.xml",
            "ESPN Soccer": "https://www.espn.com/espn/rss/soccer/news",
            "Goal.com": "https://www.goal.com/feeds/news.rss",
            "Sky Sports": "https://www.skysports.com/rss/12040",
            "Daily Mail Football": "https://www.dailymail.co.uk/sport/football/index.rss",
            "Mirror Football": "https://www.mirror.co.uk/sport/football/rss.xml",
            "The Guardian Football": "https://www.theguardian.com/football/rss",
            "Marca English": "https://e00-marca.uecdn.es/rss/en/index.xml",
            "CaughtOffside": "https://www.caughtoffside.com/feed/",
            "Football Italia": "https://www.football-italia.net/feed",
            "Bundesliga Official": "https://www.bundesliga.com/en/rss/news.xml",
            "Ligue 1 Official": "https://www.ligue1.com/rss/news.xml",
            "Eredivisie News": "https://www.eredivisie.eu/rss/news",
            "African Football": "https://africanfootball.com/feed",
            "Soccer Ethiopia": "https://www.soccerethiopia.net/feed",
            "AS.com": "https://as.com/rss/as.xml",
            "Gol.com": "https://gol.globo.com/feed/",
            "OneFootball": "https://www.onefootball.com/en/feeds/news",
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

        print("Fetching from multiple RSS sources...")
        rss_news = self.fetch_rss_news()
        print(f"Fetched {len(rss_news)} items from RSS feeds ({len(self.rss_feeds)} sources).")
        all_news.extend(rss_news)

        print("Fetching Telegram channels...")
        tg_news = await self.fetch_telegram_news()
        print(f"Fetched {len(tg_news)} items from Telegram.")
        all_news.extend(tg_news)

        return all_news

    def fetch_rss_news(self):
        news_items = []
        successful_feeds = 0
        failed_feeds = 0

        for source, url in self.rss_feeds.items():
            try:
                feed = feedparser.parse(url)
                if feed.entries:
                    for entry in feed.entries[:5]:  # Limit per feed to avoid duplication
                        title = entry.get('title', 'No Title')
                        summary = entry.get('summary', '')
                        content = f"{title}. {summary}"
                        # Stable hash for content
                        news_id = hashlib.md5(content.encode('utf-8')).hexdigest()

                        news_items.append({
                            "id": f"rss_{news_id}",
                            "headline": title,
                            "content": content,
                            "source": source,
                            "image_url": self._extract_image(entry)
                        })
                    successful_feeds += 1
            except Exception as e:
                print(f"Error fetching RSS from {source}: {e}")
                failed_feeds += 1

        print(f"RSS Feed Status: {successful_feeds} successful, {failed_feeds} failed")
        return news_items

    def _extract_image(self, entry):
        """Extract image URL from RSS entry using multiple methods."""
        try:
            # Method 1: media_content
            if hasattr(entry, 'media_content') and entry.media_content:
                for media in entry.media_content:
                    if 'url' in media and media.get('type', '').startswith('image'):
                        return media['url']
            
            # Method 2: media_thumbnail
            if hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
                for thumb in entry.media_thumbnail:
                    if 'url' in thumb:
                        return thumb['url']
            
            # Method 3: enclosures
            if hasattr(entry, 'enclosures') and entry.enclosures:
                for enc in entry.enclosures:
                    if 'url' in enc and enc.get('type', '').startswith('image'):
                        return enc['url']
            
            # Method 4: image tag
            if hasattr(entry, 'image') and hasattr(entry.image, 'href'):
                return entry.image.href
            
            # Method 5: Parse HTML img tag from summary
            if 'summary' in entry:
                img_match = re.search(r'<img.*?src="(.*?)"', entry.summary)
                if img_match:
                    return img_match.group(1)
        except:
            pass
        
        return None

    async def fetch_telegram_news(self):
        news_items = []
        time_threshold = datetime.now() - timedelta(hours=3)

        for channel in self.telegram_channels:
            try:
                entity = await self.client.get_entity(channel)
                async for msg in self.client.iter_messages(entity, limit=50):
                    if msg.date < time_threshold:
                        break
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
