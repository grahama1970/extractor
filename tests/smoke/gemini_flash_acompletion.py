import litellm
from dotenv import load_dotenv, find_dotenv
from extractor.pipeline.utils.litellm_cache import initialize_litellm_cache

load_dotenv(find_dotenv())
initialize_litellm_cache()


def encode_image(image_path:str):
    import base64
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")

image_path = 'tests/stage07_manual/images/smoke/panda.png'  # Your local image file
base64_image = encode_image(image_path)

response = litellm.completion(
    model="gemini/gemini-2.5-flash",  # For Gemini
    messages=[
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Whats in this image?"},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": "data:image/jpeg;base64," +base64_image
                    },
                },
            ],
        }
    ],
)
print(response)