from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama"  # required by the library, but Ollama ignores it
)

# Test generation
response = client.chat.completions.create(
    model="llama3.1",
    messages=[{"role": "user", "content": "Say hello in one sentence."}]
)
print("Generation test:")
print(response.choices[0].message.content)

# Test embeddings
embedding_response = client.embeddings.create(
    model="nomic-embed-text",
    input="TouchDesigner is a visual programming language."
)
print("\nEmbedding test:")
print(f"Vector length: {len(embedding_response.data[0].embedding)}")