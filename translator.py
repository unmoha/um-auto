import time
from googletrans import Translator as GoogleTranslator

class Translator:
    def __init__(self):
        self.translator = GoogleTranslator()

    def translate_to_amharic(self, text, retries=3):
        if not text:
            return ""

        for i in range(retries):
            try:
                # Basic cleaning of input text
                text = text.strip()
                if not text:
                    return ""

                result = self.translator.translate(text, src='auto', dest='am')
                translated_text = result.text

                # Simple post-processing to make it slightly more natural
                translated_text = self._post_process(translated_text)
                return translated_text
            except Exception as e:
                print(f"Translation error (attempt {i+1}): {e}")
                if i < retries - 1:
                    time.sleep(2)
        return text # Return original text if translation fails

    def _post_process(self, text):
        # Basic Amharic formatting fixes if any
        # This is where 'viral rewrite' logic can be expanded
        text = text.replace("...", "...")
        return text
