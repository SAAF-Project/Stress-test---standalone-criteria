# Fixture: fully env-driven → verdict "yes"
import os
import openai

client = openai.OpenAI(
    api_key=os.getenv("OPENAI_API_KEY", "dummy"),
    base_url=os.getenv("OPENAI_BASE_URL", "http://localhost:11434/v1"),
)

response = client.chat.completions.create(
    model=os.getenv("MODEL", "llama3.2:3b"),
    messages=[{"role": "user", "content": "hello"}],
)
print(response.choices[0].message.content)
