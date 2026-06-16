# Fixture: HIGH blockers — hardcoded endpoint + key → verdict "no"
import openai

client = openai.OpenAI(
    api_key="sk-abcdefghijklmnopqrstuvwxyz123456",
    base_url="https://api.openai.com/v1",
)

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "hello"}],
)
print(response.choices[0].message.content)
