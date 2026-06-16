# Fixture: env-driven endpoint but hardcoded cloud model name → verdict "partial"
import os
import openai

client = openai.OpenAI(
    api_key=os.getenv("OPENAI_API_KEY", "dummy"),
    base_url=os.getenv("OPENAI_BASE_URL"),
)

response = client.chat.completions.create(
    model="gpt-4-turbo",
    messages=[{"role": "user", "content": "hello"}],
)
print(response.choices[0].message.content)
