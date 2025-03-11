import asyncio
import openai
import json
from traffic_scraper import get_merged_data
from twikit import Client
from openai import OpenAI
from dotenv import load_dotenv
import os
import time
from pprint import pprint
from google_maps import save_map_image
from geopy.exc import GeocoderUnavailable

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

def load_data_from_file(filename="previous_data.json"):
    if os.path.exists(filename):
        with open(filename, "r") as file:
            return json.load(file)
    return []

def save_data_to_file(data, filename="previous_data.json"):
    with open(filename, "w") as file:
        json.dump(data, file, indent=4)

async def summarize_data(data):
    client_gpt = OpenAI(api_key=os.getenv("GPT_KEY"))
    prompt = (
        "Summarize the following traffic incident details for a tweet without mentioning 'drive with caution', any hashtags, or 'Traffic Alert:' type phrases:\n\n"
        f"City: {data['City']}\n"
        f"Neighborhood: {data['Neighborhood']}\n"
        f"Location: {data['Location']} - {data['Location Desc.']}\n"
        f"Type: {data['Type']}\n"
        f"Details: {', '.join(data['Details'])}\n"
    )
    response = client_gpt.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a highly intelligent traffic reporter who gives brief and neutral updates using CHP scanner data, avoiding any phrases like 'drive with caution,' hashtags, or alert-type phrases. 'No' means Northbound, 'So' means Southbound, 'OOG' means out of gas, and other abbreviations should be interpreted accordingly."},
            {"role": "user", "content": f"{prompt} Keep it brief, neutral, and without any of the mentioned phrases or hashtags. You may add related emojis."}
        ],
        max_tokens=50,
        temperature=0.4
    )
    return response.choices[0].message.content

async def tweet_data(summary, current_data):
    retries = 8  # Number of retries
    try:
        # Save and upload the image only once
        save_map_image(current_data['Longitude'], current_data['Latitude'], os.getenv("MAP_ACCESS_TOKEN"), filename='map.png')
        media_ids = [await client.upload_media("map.png")]
    except Exception as e:
        print(f"Failed to save or upload the image: {e}")
        return  # Exit if there's an error with the image upload
    
    for attempt in range(1, retries + 2):  # Attempt up to 8 times
        try:
            print(f"Attempt {attempt} to send tweet.")
            await client.create_tweet(text=summary, media_ids=media_ids)
            print("Tweet sent successfully.")
            break  # Exit loop if successful
        except KeyError as e:
            print(f"KeyError encountered on attempt {attempt}: {e}")
            if attempt == retries + 1:
                print("Failed after 8 attempts. Skipping...")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            if attempt == retries + 1:
                print("Failed after 8 attempts due to an unexpected error. Skipping...")
        await asyncio.sleep(2)  # Small delay before retrying

async def main():
    # Initial data state
    previous_data = {}  # Initialize previous_data as an empty dictionary
    all_previous_data = load_data_from_file()  # Load previous data from JSON file

    def has_data_changed(new_data, old_data):
        if new_data is None or old_data is None:
            return False
        if new_data == old_data:
            return False
        if (new_data.get('Latitude') == old_data.get('Latitude') and
                new_data.get('Longitude') == old_data.get('Longitude')):
            return False
        return True

    while True:
        try:
            current_data = get_merged_data()
            if current_data is None:
                print("Warning: get_merged_data() returned None. Skipping this iteration.")
                await asyncio.sleep(30)
                continue

            if has_data_changed(current_data, previous_data):
                pprint(current_data)  # Pretty-print the current data
                summary = await summarize_data(current_data)
                await tweet_data(summary, current_data)

                # Update previous_data and store in the all_previous_data list
                all_previous_data.append(previous_data)
                previous_data = current_data

                # Save the list to a JSON file
                save_data_to_file(all_previous_data)

        except Exception as e:
            print(f"An error occurred: {e}")
            # Optionally, you might want to add a small delay here to avoid rapid retries in case of persistent errors
            await asyncio.sleep(5)

        await asyncio.sleep(30)  # Check for changes every 30 seconds

# Run the async main function
if __name__ == "__main__":
    asyncio.run(login_and_setup())
    asyncio.run(main())