import requests
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import os
from datetime import datetime

class ImageService:
    def __init__(self, cache_dir='image_cache'):
        self.cache_dir = cache_dir
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
    
    async def get_image(self, image_url, headline):
        """
        Get image from URL or generate one if not available.
        Returns bytes or file path.
        """
        # Try to fetch image from URL
        if image_url:
            try:
                image_bytes = await self._download_image(image_url)
                if image_bytes:
                    return image_bytes
            except Exception as e:
                print(f"Failed to download image from {image_url}: {e}")
        
        # Fallback: Generate professional placeholder with headline
        return self._generate_placeholder_image(headline)
    
    async def _download_image(self, image_url, timeout=10):
        """Download image from URL with timeout"""
        try:
            response = requests.get(image_url, timeout=timeout)
            response.raise_for_status()
            
            # Validate it's actually an image
            img = Image.open(BytesIO(response.content))
            img.verify()  # Verify image integrity
            
            # Re-open after verify
            img = Image.open(BytesIO(response.content))
            return response.content
        except Exception as e:
            print(f"Error downloading image: {e}")
            return None
    
    def _generate_placeholder_image(self, headline):
        """Generate professional placeholder image with headline"""
        try:
            # Create image with football/sports theme colors
            width, height = 1200, 630
            background_color = (15, 76, 129)  # Dark blue - BBC Sport color
            text_color = (255, 255, 255)  # White
            accent_color = (255, 153, 0)  # Orange accent
            
            img = Image.new('RGB', (width, height), background_color)
            draw = ImageDraw.Draw(img)
            
            # Try to use a system font, fallback to default
            try:
                # Try multiple font paths for different systems
                font_paths = [
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                    "/System/Library/Fonts/Arial.ttf",
                    "C:\\Windows\\Fonts\\arial.ttf",
                ]
                font_size = 60
                font = None
                for path in font_paths:
                    if os.path.exists(path):
                        font = ImageFont.truetype(path, font_size)
                        break
                if font is None:
                    font = ImageFont.load_default()
            except:
                font = ImageFont.load_default()
            
            # Add sports emoji
            emoji_text = "⚽"
            draw.text((50, 50), emoji_text, font=font, fill=accent_color)
            
            # Add headline with text wrapping
            headline_short = headline[:60] + "..." if len(headline) > 60 else headline
            lines = self._wrap_text(headline_short, 40)
            
            y_offset = 150
            for line in lines:
                draw.text((50, y_offset), line, font=font, fill=text_color)
                y_offset += 80
            
            # Add footer
            footer_font = ImageFont.load_default()
            draw.text((50, height - 60), "Football News • BBC Sport", font=footer_font, fill=accent_color)
            
            # Save to bytes
            img_bytes = BytesIO()
            img.save(img_bytes, format='JPEG', quality=85)
            img_bytes.seek(0)
            return img_bytes.getvalue()
        except Exception as e:
            print(f"Error generating placeholder image: {e}")
            return None
    
    def _wrap_text(self, text, char_per_line=40):
        """Simple text wrapping"""
        lines = []
        current_line = ""
        for word in text.split():
            if len(current_line) + len(word) + 1 <= char_per_line:
                current_line += word + " "
            else:
                if current_line:
                    lines.append(current_line.strip())
                current_line = word + " "
        if current_line:
            lines.append(current_line.strip())
        return lines
