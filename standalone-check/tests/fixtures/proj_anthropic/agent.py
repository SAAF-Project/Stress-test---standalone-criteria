# Fixture: Anthropic SDK usage → verdict "no" (cloud_sdk_import LOW + no openai path)
# LOW only → verdict "yes" in absence of HIGH/MEDIUM. But anthropic has no
# OpenAI-compatible shim so we expect client="anthropic" and endpoint_configurable=False.
import anthropic

client = anthropic.Anthropic()

message = client.messages.create(
    model="claude-3-sonnet-20240229",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Hello"}],
)
print(message.content)
