import os
import requests
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
MY_ID = 1227272285

url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
data = {"chat_id": MY_ID, "text": "Богатырь проснулся. Первый вздох."}

response = requests.post(url, data=data)

if response.status_code == 200:
    print("Готово — сообщение отправлено!")
else:
    print("Что-то не так. Ответ сервера:", response.text)
