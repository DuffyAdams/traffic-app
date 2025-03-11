import os
from dotenv import load_dotenv
from twikit import Client
from openai import OpenAI



async def login_and_setup():
    global client
    # Load environment variables
    load_dotenv()

    # Initialize Client
    client = Client()
    
    cookies_path = 'projects/finance_bots/roadAlerts/cookies.json'
    if os.path.exists(cookies_path):
        client.load_cookies(cookies_path)
        print("Loaded Cookies")
    else:
        print("Cookies path does not exist")
        await client.login(
            auth_info_1=os.getenv('ROADALERTS_USERNAME'),
            auth_info_2=os.getenv('ROADALERTS_EMAIL'),
            password=os.getenv('ROADALERTS_PASSWORD')
        )
        print("Logged in and setup complete")
    return client
