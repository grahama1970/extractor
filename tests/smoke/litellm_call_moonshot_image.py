import base64
import os
import asyncio

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

from extractor.pipeline.utils.litellm_call import litellm_call
from extractor.pipeline.utils.litellm_cache import initialize_litellm_cache

initialize_litellm_cache()

def encode_image(image_path: str) -> str:
    with open(image_path, 'rb') as f:
        return base64.b64encode(f.read()).decode('utf-8')


async def main():
    image_path = os.getenv('SMOKE_IMAGE_PATH', 'tests/stage07_manual/images/smoke/panda.png')
    b64 = encode_image(image_path)
    # model = os.getenv('LITELLM_VLM_MODEL', 'gemini/gemini-2.5-flash')
    model = "moonshot/kimi-k2-turbo-preview"
    params = {
        'model': model,
        'messages': [
            {'role': 'user', 'content': [
                {'type': 'text', 'text': 'Describe this image.'},
                {'type': 'image_url', 'image_url': {'url': f'data:image/png;base64,{b64}'}},
            ]}
        ],
        'timeout': 30,
        'max_tokens': 128,
    }
    sid = os.getenv('LITELLM_SESSION_ID')
    result = await litellm_call(params, desc='smoke_moonshot_image', session_id=sid)
    print(repr(result))


if __name__ == '__main__':
    asyncio.run(main())
