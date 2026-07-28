import os
from litellm import Router
from dotenv import load_dotenv, find_dotenv
from extractor.pipeline.utils.litellm_cache import initialize_litellm_cache

load_dotenv(find_dotenv())
initialize_litellm_cache()


def encode_image(image_path: str):
    """Encode image file to base64 string."""
    import base64

    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


# Set your Gemini API key in the environment
# os.environ["GEMINI_API_KEY"] = "your-gemini-api-key"

model_list = [
    {
        "model_name": "gemini-flash",
        "litellm_params": {
            "model": "gemini/gemini-2.5-flash",  # Adjust if needed
            "api_key": os.getenv("GEMINI_API_KEY"),
        },
    }
]

router = Router(model_list=model_list)

image_path = "tests/stage07_manual/images/smoke/panda.png"
base64_image = encode_image(image_path)

response = router.completion(
    model="gemini-flash",
    messages=[
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Whats in this image?"},
                {
                    "type": "image_url",
                    "image_url": {"url": "data:image/jpeg;base64," + base64_image},
                },
            ],
        }
    ],
)
print(response)
