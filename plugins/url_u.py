import os
import requests
from pyrogram import Client, filters
from pyrogram.types import Message



# Function to download a file from a URL
def download_file(url, filename):
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        with open(filename, 'wb') as file:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)
        return filename
    except requests.RequestException as e:
        print(f"Error downloading the file: {e}")
        return None

@Client.on_message(filters.command('download'))
async def run_bot(client: Client, message: Message):
    try:
        await message.reply_text("Please send the URL of the file you want to download.")
        input_msg = await client.listen(message.chat.id)
        file_url = input_msg.text
        await input_msg.delete()

        filename = os.path.basename(file_url)
        downloaded_file = download_file(file_url, filename)
        
        if downloaded_file:
            await message.reply_document(document=downloaded_file, caption="Here is your downloaded file.")
            os.remove(downloaded_file)
        else:
            await message.reply_text("Failed to download the file. Please check the URL and try again.")
    except Exception as e:
        print(f"Error in run_bot: {e}")
        await message.reply_text("An error occurred while processing your request. Please try again.")

