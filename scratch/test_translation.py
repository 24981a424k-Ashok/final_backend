import asyncio
import logging
import sys
import os

# PATH SETUP
sys.path.insert(0, os.getcwd())

from src.utils.translator import NewsTranslator
from src.config import settings

async def test_translation():
    logging.basicConfig(level=logging.INFO)
    translator = NewsTranslator()
    
    test_text = "Google has announced a major breakthrough in quantum computing, achieving state-of-the-art performance."
    target_lang = "Hindi"
    
    print(f"Testing translation to {target_lang}...")
    result = await translator.translate_text(test_text, target_lang)
    print(f"Original: {test_text}")
    print(f"Translated: {result}")
    
    if result and result != test_text:
        print("SUCCESS: Translation working.")
    else:
        print("FAILURE: Translation failed or returned original text.")

if __name__ == "__main__":
    asyncio.run(test_translation())
