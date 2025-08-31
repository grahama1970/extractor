```
curl -X POST http://192.168.86.49:30002/v1/completions \
-H "Content-Type: application/json" \
-d '{
    "model": "neuralmagic/Meta-Llama-3.1-8B-Instruct-FP8",
    "prompt": "What is the capital of France?",
    "max_tokens": 50,
    "temperature": 0.7
}'|jq
```