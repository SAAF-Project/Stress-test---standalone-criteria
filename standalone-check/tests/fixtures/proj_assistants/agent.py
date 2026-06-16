# Fixture: cloud-only Assistants API → verdict "no"
import os
import openai

client = openai.OpenAI(
    api_key=os.getenv("OPENAI_API_KEY", "dummy"),
    base_url=os.getenv("OPENAI_BASE_URL"),
)

assistant = client.beta.assistants.create(
    name="Demo",
    instructions="You are a helpful assistant.",
    model="gpt-4o",
)
thread = client.beta.threads.create()
print(assistant.id, thread.id)
