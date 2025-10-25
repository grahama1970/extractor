curl -X POST \
		https://llm.chutes.ai/v1/chat/completions \
		-H "Authorization: Bearer $CHUTES_API_KEY" \
	-H "Content-Type: application/json" \
	-d '  {
    "model": "Qwen/Qwen3-VL-235B-A22B-Instruct",
    "messages": [
      {
        "role": "user",
        "content": "Tell me a 250 word story."
      }
    ],
    "stream": false,
    "max_tokens": 1024,
    "temperature": 0.7
  }'