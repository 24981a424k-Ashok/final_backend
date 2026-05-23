import asyncio
import logging
import sys
import os

# PATH SETUP
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.translator import NewsTranslator
from src.config import settings

async def test_translation():
    logging.basicConfig(level=logging.INFO)
    translator = NewsTranslator()
    
    test_text = "Google has announced a major breakthrough in quantum computing, achieving state-of-the-art performance."
    target_lang = "Hindi"
    
    print(f"Testing translation to {target_lang}...")
    result = await translator.translate_text(test_text, target_lang)
    
    # Safely print using sys.stdout buffer with utf-8 encoding to avoid Windows console errors
    sys.stdout.reconfigure(encoding='utf-8')
    print("Original:", test_text)
    print("Translated:", result)
    
    if result and result != test_text:
        print("SUCCESS: Translation working.")
    else:
        print("FAILURE: Translation failed or returned original text.")

if __name__ == "__main__":
    asyncio.run(test_translation())
