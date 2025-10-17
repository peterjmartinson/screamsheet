import spacy
import argostranslate.translate as translate
import re # Import the regular expression module
from typing import Dict, List, Tuple
import datetime

FROM_CODE = "fr"  # French
TO_CODE = "en"    # English

# --- Core Functions ---

def extract_and_process_words(text: str) -> Dict[str, Dict[str, str]]:
    """
    Uses spaCy to process text, extract unique base forms, part of speech
    (POS), and gender.
    
    The key structure is: {base_form: {POS: Gender}}
    """
    try:
        nlp_fr = spacy.load("fr_core_news_sm")
    except OSError:
        print("Error: French spaCy model 'fr_core_news_sm' not found. Please install it.")
        return {}
    
    doc = nlp_fr(text)
    
    unique_words_data = {}
    
    # Define a regex pattern to strip non-alphabetic/non-digit characters 
    # from the start and end of a string. This targets surrounding punctuation.
    # Note: \W includes hyphens, guillemets, etc.
    # We use a pattern that keeps characters *inside* the word (like "entre-bâillant") 
    # but removes them if they are leading or trailing (like "oncle," or "«Bon").
    punctuation_pattern = re.compile(r'^[^\w]+|[^\w]+$', re.UNICODE)
    
    for token in doc:
        # 1. Filtering: Remove stop words, punctuation, numbers, and spaces
        is_clean = (
            not token.is_stop and 
            not token.is_punct and 
            not token.like_num and 
            not token.is_space
            # Removed the length check here, as it may be applied later on the final lemma
        )

        if is_clean:
            lemma = token.lemma_.lower()
            
            # --- START MODIFICATION ---
            # 2. Clean the lemma string of leading/trailing punctuation using regex.
            cleaned_lemma = punctuation_pattern.sub('', lemma)

            # 3. Handle specific formatting errors (like the ones from the commented text)
            # This is often best handled by ensuring correct file encoding (UTF-8), 
            # but this line provides a direct cleanup if needed.
            cleaned_lemma = cleaned_lemma.replace('├⌐', 'é').replace('├â', 'â').replace('├┤', 'ô')

            # 4. Final filter check: Ensure the word still has content (e.g., length > 1) 
            # after all cleaning, and isn't just an empty string or a single letter.
            if len(cleaned_lemma.strip()) <= 1:
                continue
                
            pos = token.pos_
            gender = token.morph.get('Gender', [''])[0]

            # 5. Use the CLEANED lemma as the key
            if cleaned_lemma not in unique_words_data:
                unique_words_data[cleaned_lemma] = {}
            
            unique_words_data[cleaned_lemma][pos] = gender
            # --- END MODIFICATION ---

    print(unique_words_data)
    return unique_words_data

# ... (translate_and_format_lexicon function remains the same)
def translate_and_format_lexicon(word_data: Dict[str, Dict[str, str]]):
    """
    Translates unique words and formats the output into the final lexicon strings.
    """
    lexicon_entries: List[str] = []
    words_to_translate = list(word_data.keys())
    
    if not words_to_translate:
        print("No unique words found to translate.")
        return []
        
    print(f"\nTranslating {len(words_to_translate)} unique words...")
    
    try:
        translations: Dict[str, str] = {}
        for word in words_to_translate:
            translations[word] = translate.translate(word, FROM_CODE, TO_CODE)
            
    except Exception as e:
        print(f"Error during translation: {e}")
        print("Ensure 'argospm install fr en' was successful.")
        return []

    print(translations)
    for base_form, pos_data in word_data.items():
        translation_text = translations.get(base_form, "ERROR_TRANSLATION")
        details_list: List[str] = []
        for pos, gender in pos_data.items():
            gender_prefix = f"({gender}) " if gender else ""
            details_list.append(f"{pos.lower()}, {gender_prefix}{translation_text}")

        final_line = f"{base_form} - {'; '.join(details_list)}"
        lexicon_entries.append(final_line)
        
    return sorted(lexicon_entries)

def save_lexicon_to_file(lexicon_output: List[str], filename = None):
    """
    Saves the lexicon list to a plain text file with a datetime stamp in the name.
    """
    # Generate the timestamp string (e.g., '2025-10-01_221700')
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    
    # Construct the filename
    if not filename:
        filename = f"lexicon_output_{timestamp}.txt"
    
    print(f"\n📝 Saving lexicon to: {filename}")
    
    try:
        # Write the list of lines to the file, using UTF-8 encoding
        with open(filename, "w", encoding="utf-8") as f:
            for line in lexicon_output:
                f.write(line + "\n")
        
        print(f"✅ File saved successfully. Total lines: {len(lexicon_output)}")
        
    except Exception as e:
        print(f"❌ Error writing file: {e}")

def get_lexicon(text_list) -> List[str]:
    lexicon_output: List[str] = []
    FRENCH_TEXT = " ".join(text_list)
    # ... (FROM_CODE and TO_CODE remain the same)
    if FRENCH_TEXT:
        # 1. Process the French text to get unique, cleaned base forms
        processed_words_map = extract_and_process_words(FRENCH_TEXT)

        # 2. Translate the unique base forms and format the output
        lexicon_output = translate_and_format_lexicon(processed_words_map)
    return lexicon_output


if __name__ == "__main__":

    # --- Configuration ---
    # ... (File reading logic remains the same)
    book_text_list = []
    with open("latest_news.txt", "r") as book:
        book_text_list = book.readlines()

    FRENCH_TEXT = " ".join(book_text_list)
    # ... (FROM_CODE and TO_CODE remain the same)
    if FRENCH_TEXT:
        # 1. Process the French text to get unique, cleaned base forms
        processed_words_map = extract_and_process_words(FRENCH_TEXT)

        # 2. Translate the unique base forms and format the output
        lexicon_output = translate_and_format_lexicon(processed_words_map)

        # 3. Save the final output to a timestamped file
        if lexicon_output:
            save_lexicon_to_file(lexicon_output, "latest_news_lexicon.txt")

    print("\n----------------------------------")
    print("Lexicon Generation Workflow Complete.")

