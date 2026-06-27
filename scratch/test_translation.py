import sys
import os
import asyncio

# Configure terminal stdout/stderr to support Unicode characters on Windows
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

# Setup path so we can import src
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from src.utils.translator import NewsTranslator

async def main():
    print("Initializing NewsTranslator...")
    translator = NewsTranslator()
    
    print("\nAPI Keys registered:")
    print(f"Total keys: {len(translator.all_keys)}")
    print(f"OpenAI keys: {len(translator.openai_keys)}")
    print(f"Groq keys: {len(translator.groq_keys)}")
    print(f"NVIDIA keys: {len(translator.nvidia_keys)}")
    
    test_text = "The quick brown fox jumps over the lazy dog."
    target_languages = ["Hindi", "Telugu", "Spanish"]
    
    print(f"\nTesting translation of: '{test_text}'")
    results = {}
    for lang in target_languages:
        try:
            print(f"Translating to {lang}...")
            result = await translator.translate_text(test_text, lang)
            print(f"Result in {lang}: '{result}'")
            results[lang] = result
            if result == test_text:
                print(f"Warning: Result is identical to input (translation might have fallen back/skipped).")
            else:
                print(f"Success!")
        except Exception as e:
            print(f"Failed to translate to {lang}: {e}")
            
    # Write translation output to a log file to verify contents
    output_path = os.path.join(BACKEND_DIR, "scratch", "translation_results.txt")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("=== Translation Verification Output ===\n")
        f.write(f"Source text: {test_text}\n\n")
        for lang, val in results.items():
            f.write(f"Language: {lang}\n")
            f.write(f"Translated: {val}\n\n")
    print(f"\nResults successfully written to: {output_path}")

if __name__ == "__main__":
    asyncio.run(main())
