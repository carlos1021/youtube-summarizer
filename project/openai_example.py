"""CODING EXAMPLE: WORKING WITH OPENAI API"""
import os
from openai import OpenAI
import time


MODEL = "gpt-4o-mini"
# client = OpenAI(api_key=os.environ['OPENAI_API_KEY'])
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

def chat_with_chatgpt(prompt, personality):
	response = client.chat.completions.create(model=MODEL,
	    messages=[
				{
					"role": "system",
					"content": f"You are a helpful assistant, that is very {personality}."
				}, 
				{
					"role": "user",
					"content": f"{prompt}"
				}
			])

	message = response.choices[0].message
	return message


# Main
print("This program will call the OpenAI API and return its response.")
print("")
time.sleep(1)
print("You have the option to ask ChatGPT a question.")
print("You will also have the option to change its personality type.")

user_prompt = input("What question do you want to ask ChatGPT? ")
personality = input("What personality type would you like? ")
time.sleep(0.5)
print("Calling ChatGPT ...")
chatbot_response = chat_with_chatgpt(user_prompt, personality)
print(chatbot_response)
