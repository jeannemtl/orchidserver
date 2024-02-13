import requests

BOT_TOKEN = "6235350336:AAEYV5ZknQJzfMOHuHa6rt0EIj6zEexO6i8"
WEBHOOK_URL = "https://4c91-173-178-162-164.ngrok-free.app"
response = requests.post(
    f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook",
    json={"url": f"{WEBHOOK_URL}/webhook"},
)

print(response.json())
