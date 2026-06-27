import asyncio
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.utils.translator import NewsTranslator

async def test_translation():
    print("=== AI News Agent: Translation Test ===")
    translator = NewsTranslator()
    
    test_text = "The quick brown fox jumps over the lazy dog."
    target_languages = ["Telugu", "Hindi", "Tamil"]
    
    print("Original Text: " + test_text)
    
    for lang in target_languages:
        print("\n--- Testing Language: " + lang + " ---")
        try:
            # 1. Test LLM Translation (Layer 1/2)
            print("Attempting LLM translation for " + lang + "...")
            result = await translator.translate_text(test_text, lang)
            print("LLM Result Length: " + str(len(result)) + ". Result: " + result)
            
            # 2. Test NVIDIA Translate (Layer 3)
            print("Verifying NVIDIA Translate Layer for " + lang + "...")
            nvidia_result = await translator.translate_nvidia(test_text, lang)
            print("NVIDIA Result Length: " + str(len(nvidia_result)) + ". Result: " + nvidia_result)

            # 3. Test NLLB Fallback (Layer 4)
            print("Verifying NLLB Fallback for " + lang + "...")
            nllb_result = await translator.translate_nllb(test_text, lang)
            print("NLLB Result Length: " + str(len(nllb_result)))
            
            # 4. Test Skip detection
            print("Testing Skip Detection (sending back translated text to target)...")
            skip_result = await translator.translate_text(result, lang)
            if skip_result == result:
                print("SUCCESS: Skip Detection verified (translation skipped correctly)")
            else:
                print("FAILURE: Skip Detection did not bypass translation")
                
            if result != test_text:
                print("SUCCESS: LLM Translation verified for " + lang)
            if nvidia_result != test_text:
                print("SUCCESS: NVIDIA Translate verified for " + lang)
            if nllb_result != test_text:
                print("SUCCESS: NLLB Fallback verified for " + lang)
            
        except Exception as e:
            print("ERROR testing " + lang + ": " + str(e))

    # 3. Test Bulk Translation (Dashboard Simulation)
    print("\n--- Testing Bulk Translation (Dashboard Style) ---")
    mock_stories = [
        {
            "id": 9999,
            "title": "Stock market hits record high as tech earnings soar.",
            "bullets": [
                "Nvidia shares jumped 5% after hours.",
                "S&P 500 closed at a new all-time high.",
                "Analysts predict further growth in AI sector."
            ],
            "why": "Strong earnings reports from tech giants are driving market optimism.",
            "affected": "Investors, tech employees, and the global financial market."
        }
    ]
    
    node_data = {"stories": mock_stories}
    print("Translating mock dashboard to Hindi...")
    translated_node = await translator.translate_node_bulk(node_data, "Hindi")
    
    tr_story = translated_node["stories"][0]
    is_ok = tr_story.get('is_translated') or tr_story.get('is_cached')
    print("Bulk Success: " + str(is_ok))
    if is_ok:
        print("Bulk Translation verified for Hindi dashboard.")

if __name__ == "__main__":
    asyncio.run(test_translation())
