import json
import os

class Storage:
    def __init__(self, file_path='posted.json'):
        self.file_path = file_path
        self.posted_ids = self._load()

    def _load(self):
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    return set(json.load(f))
            except (json.JSONDecodeError, IOError):
                return set()
        return set()

    def save(self):
        try:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(list(self.posted_ids), f, ensure_ascii=False, indent=4)
        except IOError as e:
            print(f"Error saving storage: {e}")

    def is_posted(self, news_id):
        return str(news_id) in self.posted_ids

    def add_posted(self, news_id):
        self.posted_ids.add(str(news_id))
        # Keep only the last 1000 items to prevent file from growing indefinitely
        if len(self.posted_ids) > 1000:
            self.posted_ids = set(list(self.posted_ids)[-1000:])
        self.save()
