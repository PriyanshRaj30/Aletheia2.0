import json
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any
import ollama


@dataclass
class OCRBookData:
    title: Optional[str] = None
    author: Optional[str] = None
    genres: Optional[list] = None
    themes: Optional[list] = None
    year: Optional[int] = None
    description: Optional[str] = None


class BookOCRFormatter:
    """
    Takes noisy OCR-extracted text from book covers/spines and formats it into a clean,
    structured JSON using an Ollama model. Must handle the incomplete, misspelled, or partial
    book titles and author names by identifying the actual book.
    """

    def __init__(self, model: str = "llama3"):
        self.model = model

    def _chat(self, prompt: str) -> str:
        """Wrapper for Ollama chat API."""
        response = ollama.chat(
            model=self.model,
            messages=[{"role": "user", "content": prompt}]
        )
        return response["message"]["content"]

    def format_ocr_text(self, ocr_text: str) -> OCRBookData:
        """
        Use LLM reasoning to identify the book from partial/noisy OCR text
        and output complete, structured JSON with corrected information.
        """
        prompt = f"""
    You are a book identification expert. The following text was extracted via OCR from a book's spine or cover.
    It may be incomplete, misspelled, or contain only partial information.

    OCR TEXT:
    \"\"\"{ocr_text}\"\"\"

    YOUR TASK:
    1. Identify the actual book based on the partial/noisy information provided
    2. If the title is incomplete (like "The Golden Fort" instead of "The Golden Fortress"), complete it
    3. If author name is misspelled or partial, correct it to the full proper name
    4. Fill in ALL missing information about this book (genres, themes, year, description)

    OUTPUT REQUIREMENTS:
    - Return ONLY a valid JSON object, no explanations or markdown
    - Use your knowledge to identify and complete the book information
    - If you recognize the book, fill in ALL fields with accurate data
    - Format:

    {{
    "title": "Complete corrected book title",
    "author": "Full corrected author name",
    "genres": ["genre1", "genre2"],
    "themes": ["theme1", "theme2"],
    "year": publication_year,
    "description": "Brief one-line description of the book"
    }}

    IMPORTANT: 
    - If you can identify the book from partial info, return the COMPLETE and CORRECT information
    - Only return null values if you genuinely cannot identify the book at all
    - Output ONLY the JSON object, nothing else
    """

        content = self._chat(prompt)

        try:
            # Extract JSON from response
            start = content.find('{')
            end = content.rfind('}') + 1
            if start == -1 or end == 0:
                raise ValueError("No JSON found in response")
            
            json_str = content[start:end]
            data = json.loads(json_str)
        except Exception as e:
            print(f"Error parsing OCR data: {e}\nResponse:\n{content}")
            return OCRBookData()

        return OCRBookData(
            title=data.get("title"),
            author=data.get("author"),
            genres=data.get("genres", []),
            themes=data.get("themes", []),
            year=data.get("year"),
            description=data.get("description")
        )

    def to_json(self, ocr_book_data: OCRBookData) -> str:
        """Convert structured data to a JSON string."""
        return json.dumps(asdict(ocr_book_data), indent=2)


if __name__ == "__main__":
    ## BELOW ARE THE TESTCASES BITCH
    # Example 1: Incomplete title
    raw_ocr_text_1 = """
    hiker's guide to the galaxy
    admams
    """

    # Example 2: Misspelled author
    raw_ocr_text_2 = """
    1984
    George Orwel
    """

    # Example 3: Very partial information
    raw_ocr_text_3 = """
    Harry Pot
    J.K. Row
    """

    formatter = BookOCRFormatter(model="llama3.2:1b")
    
    print("=" * 60)
    print("Example 1: Incomplete title")
    print("=" * 60)
    structured_data_1 = formatter.format_ocr_text(raw_ocr_text_1)
    print(formatter.to_json(structured_data_1))