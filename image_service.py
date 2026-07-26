import requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import textwrap
import os

class ImageService:
    """Handles all image operations: downloading, processing, and generating placeholders."""
    
    def __init__(self):
        self.timeout = 10
        self.max_retries = 2
        self.placeholder_width = 1200
        self.placeholder_height = 630

    def download_image(self, image_url, timeout=None):
        """Download image from URL and return as bytes."""
        if not image_url:
            return None
        
        timeout = timeout or self.timeout
        
        for attempt in range(self.max_retries):
            try:
                response = requests.get(image_url, timeout=timeout)
                if response.status_code == 200:
                    # Validate it's actually an image
                    img = Image.open(BytesIO(response.content))
                    img.verify()
                    # Re-open since verify() closes the file
                    img = Image.open(BytesIO(response.content))
                    # Resize to reasonable dimensions if too large
                    img.thumbnail((1280, 720), Image.Resampling.LANCZOS)
                    # Convert to RGB if needed
                    if img.mode in ('RGBA', 'P'):
                        bg = Image.new('RGB', img.size, (255, 255, 255))
                        bg.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                        img = bg
                    # Save to bytes
                    output = BytesIO()
                    img.save(output, format='JPEG', quality=85)
                    output.seek(0)
                    return output
            except requests.exceptions.RequestException as e:
                print(f"Attempt {attempt + 1}: Failed to download image: {e}")
                continue
            except Exception as e:
                print(f"Attempt {attempt + 1}: Error processing image: {e}")
                continue
        
        return None

    async def download_telegram_photo(self, message):
        """Download photo from a Telegram message and return as bytes."""
        try:
            if not message.photo:
                return None
            
            photo_bytes = await message.download_media(file=bytes)
            
            # Validate and resize
            img = Image.open(BytesIO(photo_bytes))
            img.thumbnail((1280, 720), Image.Resampling.LANCZOS)
            
            if img.mode in ('RGBA', 'P'):
                bg = Image.new('RGB', img.size, (255, 255, 255))
                bg.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = bg
            
            output = BytesIO()
            img.save(output, format='JPEG', quality=85)
            output.seek(0)
            return output
        except Exception as e:
            print(f"Error downloading Telegram photo: {e}")
            return None

    def generate_placeholder_image(self, headline, source):
        """Generate a professional placeholder image with headline and source."""
        try:
            # Create image with gradient-like background
            img = Image.new('RGB', (self.placeholder_width, self.placeholder_height), 
                           color=(25, 50, 100))  # Dark blue background
            
            draw = ImageDraw.Draw(img)
            
            # Try to use a nice font, fallback to default
            try:
                title_font = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 54)
                source_font = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", 40)
            except:
                # Fallback to default font
                title_font = ImageFont.load_default()
                source_font = ImageFont.load_default()
            
            # Add decorative header
            draw.rectangle([(0, 0), (self.placeholder_width, 150)], fill=(0, 100, 200))
            
            # Add football emoji and title
            text = "⚽ SPORTS NEWS"
            bbox = draw.textbbox((0, 0), text, font=source_font)
            text_width = bbox[2] - bbox[0]
            x = (self.placeholder_width - text_width) // 2
            draw.text((x, 50), text, fill=(255, 255, 255), font=source_font)
            
            # Add headline (wrapped)
            margin = 60
            max_width = self.placeholder_width - (2 * margin)
            
            # Wrap text
            avg_char_width = 35
            chars_per_line = max_width // avg_char_width
            wrapped_lines = textwrap.wrap(headline, width=chars_per_line)
            
            # Draw headline
            y_position = 220
            for line in wrapped_lines[:3]:  # Limit to 3 lines
                bbox = draw.textbbox((0, 0), line, font=title_font)
                text_width = bbox[2] - bbox[0]
                x = (self.placeholder_width - text_width) // 2
                draw.text((x, y_position), line, fill=(255, 255, 255), font=title_font)
                y_position += 80
            
            # Add source at bottom
            source_text = f"Source: {source}"
            bbox = draw.textbbox((0, 0), source_text, font=source_font)
            text_width = bbox[2] - bbox[0]
            x = (self.placeholder_width - text_width) // 2
            draw.text((x, self.placeholder_height - 100), source_text, 
                     fill=(200, 200, 200), font=source_font)
            
            # Save to bytes
            output = BytesIO()
            img.save(output, format='JPEG', quality=85)
            output.seek(0)
            return output
        except Exception as e:
            print(f"Error generating placeholder image: {e}")
            return None
