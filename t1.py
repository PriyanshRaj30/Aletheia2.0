# Backend API endpoint
from fastapi import FastAPI, UploadFile, File
from pydantic import BaseModel
from typing import List
import json

app = FastAPI()

class BookInfo(BaseModel):
    id: str
    title: str
    authors: List[str]
    description: str = ""
    categories: List[str] = []
    bbox: List[float]  # Bounding box coordinates

class ShelfAnalysisRequest(BaseModel):
    read_books: List[BookInfo]
    unread_books: List[BookInfo]

@app.post("/analyze-shelf")
async def analyze_shelf(request: ShelfAnalysisRequest):
    """
    Main endpoint: analyze bookshelf and return recommendations
    """
    # Step 1: Generate taste profile from read books
    taste_profile = generate_taste_profile_from_shelf(request.read_books)
    
    # Step 2: Score unread books
    scored_books = []
    for book in request.unread_books:
        score_data = score_book_against_profile(taste_profile, book)
        scored_books.append({
            **book.dict(),
            **score_data
        })
    
    # Step 3: Sort by score
    scored_books.sort(key=lambda x: x['score'], reverse=True)
    
    return {
        "taste_profile": taste_profile,
        "recommendations": scored_books,
        "summary": generate_shelf_summary(taste_profile, scored_books)
    }

def generate_taste_profile_from_shelf(read_books):
    """
    Generate comprehensive taste profile from read books
    """
    # Format books for LLM
    books_text = "\n".join([
        f"- {book.title} by {', '.join(book.authors)}\n  {book.description[:200]}..."
        for book in read_books
    ])
    
    prompt = f"""
    Analyze this reader's bookshelf. These are books they own and have read:
    
    {books_text}
    
    Create a detailed taste profile including:
    1. Primary genres and sub-genres (with confidence 0-1)
    2. Recurring themes and topics
    3. Preferred writing styles
    4. Author preferences or patterns
    5. Complexity/sophistication level
    6. Emotional tones they gravitate toward
    7. Any clear patterns in settings, time periods, or subject matter
    
    Return as JSON:
    {{
      "genres": [{{"name": "genre", "confidence": 0.9}}],
      "themes": ["theme1", "theme2"],
      "writing_styles": ["style1", "style2"],
      "patterns": {{
        "settings": ["setting1"],
        "time_periods": ["period1"],
        "complexity": "high|medium|low"
      }},
      "emotional_tones": ["tone1", "tone2"],
      "summary": "2-3 sentence overview of reader's taste"
    }}
    """
    
    response = llm.generate(prompt, temperature=0.3)
    return parse_json(response)

def score_book_against_profile(taste_profile, book):
    """
    Score a single book against the taste profile
    """
    prompt = f"""
    Reader's Taste Profile:
    {json.dumps(taste_profile, indent=2)}
    
    Unread Book on Their Shelf:
    Title: {book.title}
    Authors: {', '.join(book.authors)}
    Description: {book.description}
    Categories: {', '.join(book.categories)}
    
    This book is already on their shelf but unread. Score how likely they are to enjoy it
    based on their reading history.
    
    Consider:
    - They already bought/received this book, so there was some initial interest
    - Does it match their demonstrated preferences?
    - Why might they have put off reading it?
    
    Return JSON:
    {{
      "score": 0-100,
      "priority_level": "must_read_next|highly_recommended|good_match|might_enjoy|low_priority",
      "reasoning": "why this score - reference specific books they've read",
      "appeal_factors": ["factor1", "factor2"],
      "why_not_read_yet": "possible reason they haven't read it",
      "similar_books_read": ["book1", "book2"],
      "recommendation": "short, encouraging message"
    }}
    """
    
    response = llm.generate(prompt, temperature=0.4)
    return parse_json(response)

def generate_shelf_summary(taste_profile, scored_books):
    """
    Generate overall summary of their shelf
    """
    top_3 = scored_books[:3]
    
    prompt = f"""
    Based on this reader's taste profile and their unread books, create a friendly,
    personalized summary.
    
    Taste Profile: {taste_profile['summary']}
    
    Top 3 Recommended Unread Books:
    1. {top_3[0]['title']} - Score: {top_3[0]['score']}
    2. {top_3[1]['title']} - Score: {top_3[1]['score']}
    3. {top_3[2]['title']} - Score: {top_3[2]['score']}
    
    Write 2-3 sentences that:
    - Acknowledge their reading taste
    - Encourage them about specific books on their shelf
    - Make it personal and engaging
    
    Return plain text only, no JSON.
    """
    
    response = llm.generate(prompt, temperature=0.7)
    return response.strip()

@app.post("/process-shelf-image")
async def process_shelf_image(file: UploadFile = File(...)):
    """
    Complete pipeline: image → detected books → identified books
    """
    # Save uploaded image
    image_path = f"temp/{file.filename}"
    with open(image_path, "wb") as f:
        f.write(await file.read())
    
    # Step 1: Detect book spines
    detected_regions = detect_book_spines(image_path)
    
    # Step 2: OCR on each region
    books = []
    for i, region in enumerate(detected_regions):
        ocr_text = extract_text_from_spine(region['image_crop'])
        
        if ocr_text:
            # Step 3: Identify book
            book_info = identify_book(ocr_text)
            
            if book_info:
                books.append({
                    'id': f"book_{i}",
                    'bbox': [region['x'], region['y'], 
                            region['width'], region['height']],
                    **book_info
                })
    
    return {
        "detected_count": len(detected_regions),
        "identified_count": len(books),
        "books": books
    }