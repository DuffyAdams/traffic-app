import logging
from openai import OpenAI


# Function to get GPT response
def get_gpt_response(client_gpt, prompt, max_tokens, GPT_MODEL, TEMPERATURE):
    try:
        response = client_gpt.chat.completions.create(
            model=GPT_MODEL,
            messages=[
                {"role": "system", "content": "You are a highly intelligent traffic reporter who gives great brief explanations of what's happening using CHP scanner data."},
                {"role": "user", "content": f"{prompt} Keep it brief, keep a neutral tone and add related emojis"}
            ],
            max_tokens=max_tokens,
            temperature=TEMPERATURE
        )
        return response.choices[0].message.content
    except Exception as e:
        logging.error(f"Error in get_gpt_response: {e}")
        return None

# Function to get updated GPT response
def get_updated_gpt_response(client_gpt, first_data, second_data, max_tokens, GPT_MODEL, TEMPERATURE):
    prompt = f"{first_data} Provide a brief update from this. Make it easy to understand and keep it one brief sentence with only important details, don't include phone numbers or any other sensitive data: {second_data}"
    return get_gpt_response(client_gpt, prompt, max_tokens, GPT_MODEL, TEMPERATURE)
