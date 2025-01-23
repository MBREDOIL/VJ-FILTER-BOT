import os
from pdf2image import convert_from_path
from PIL import Image, ImageDraw, ImageFont
from pyrogram import Client, filters
from pyrogram.types import Message



# Function to convert PDF to images and add watermark
def pdf_to_images_with_watermark(pdf_path, output_folder, watermark_text):
    try:
        images = convert_from_path(pdf_path)
        image_paths = []
        for i, image in enumerate(images):
            image_path = os.path.join(output_folder, f"page_{i + 1}.png")
            draw = ImageDraw.Draw(image)
            font = ImageFont.load_default()
            text_width, text_height = draw.textsize(watermark_text, font)
            width, height = image.size
            x = width - text_width - 10
            y = height - text_height - 10
            draw.text((x, y), watermark_text, font=font, fill=(255, 255, 255, 128))
            image.save(image_path, "PNG")
            image_paths.append(image_path)
        return image_paths
    except Exception as e:
        print(f"Error converting PDF to images with watermark: {e}")
        return []

@Client.on_message(filters.command('convertpdf'))
async def run_bot(Client, message: Message):
    try:
        await message.reply_text("Please send the PDF file you want to convert to images with a watermark.")
        input_msg = await client.listen(message.chat.id)
        pdf_file = await input_msg.download()
        await input_msg.delete()

        watermark_text = "Your Watermark Text"
        output_folder = "pdf_images"
        os.makedirs(output_folder, exist_ok=True)
        image_paths = pdf_to_images_with_watermark(pdf_file, output_folder, watermark_text)

        if image_paths:
            for image_path in image_paths:
                await message.reply_document(document=image_path)
                os.remove(image_path)
            os.remove(pdf_file)
        else:
            await message.reply_text("Failed to convert the PDF to images with a watermark. Please try again.")
    except Exception as e:
        print(f"Error in run_bot: {e}")
        await message.reply_text("An error occurred while processing your request. Please try again.")













