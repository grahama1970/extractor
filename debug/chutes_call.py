import litellm  
import os  
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

models = [
'openai/Qwen/Qwen2.5-VL-7B-Instruct',
'openai/deepseek-ai/DeepSeek-V3-0324'
]



response = litellm.completion(  
 model= models[1], # "openai/deepseek-ai/DeepSeek-V3-0324", # Prefix with openai/  
 api_key= os.getenv('CHUTES_API_KEY'),
 api_base= os.getenv('CHUTES_API_BASE') or "https://llm.chutes.ai/v1", 
 messages=[  
   {  
     "role": "user",  
     "content": "Test prompt for DeepSeek-R1",  
   }  
 ],  
)  
print(response)  