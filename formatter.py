import re

class Formatter:
    def __init__(self):
        pass

    def clean_text(self, text):
        if not text:
            return ""
        # Remove URLs
        text = re.sub(r'http\S+|www\S+|https\S+', '', text, flags=re.MULTILINE)
        # Remove hashtags
        text = re.sub(r'#\w+', '', text)
        # Remove mentions
        text = re.sub(r'@\w+', '', text)
        # Remove multiple spaces
        text = re.sub(r'\s+', ' ', text).strip()
        # Remove some common Telegram artifacts
        text = text.replace('<br>', '\n').replace('&amp;', '&')
        return text

    def format_news_message(self, headline, translated_content, source_name):
        message = f"⚽️ {headline}\n\n"
        message += f"{translated_content}\n\n"
        message += f"ምንጭ: {source_name}"
        return message

    def viral_rewrite(self, text):
        # This is a placeholder for more advanced Amharic viral rewriting.
        # For now, it just cleans and slightly enhances.
        cleaned_text = self.clean_text(text)
        # Example: Add an engaging phrase if certain keywords are present
        if "ዝውውር" in cleaned_text or "ተጫዋች" in cleaned_text:
            cleaned_text = f"🚨 ሰበር ዜና: {cleaned_text}"
        return cleaned_text
