import json
from typing import List, Dict, Tuple
from dataclasses import dataclass, asdict
from collections import Counter
import anthropic
import os


@dataclass
class Book:
    """Represents a book with its metadata."""
    title: str
    author: str
    genres: List[str] = None
    themes: List[str] = None
    year: int = None
    description: str = None
    
    def __post_init__(self):
        if self.genres is None:
            self.genres = []
        if self.themes is None:
            self.themes = []


@dataclass
class TasteProfile:
    """User's reading taste profile."""
    favorite_genres: Dict[str, float]  # genre -> weight
    favorite_authors: Dict[str, int]  # author -> count
    common_themes: Dict[str, int]  # theme -> count
    era_preferences: Dict[str, int]  # era -> count
    reading_level: str  # literary, commercial, mixed
    diversity_score: float  # 0-1, how diverse their reading is
    summary: str  # natural language summary


@dataclass
class BookScore:
    """Score and reasoning for an unread book."""
    book: Book
    overall_score: float  # 0-100
    genre_match: float  # 0-100
    theme_match: float  # 0-100
    author_similarity: float  # 0-100
    novelty_score: float  # 0-100 (how different/refreshing it is)
    reasoning: str
    recommendation: str  # "highly_recommended", "recommended", "maybe", "low_priority"


class BookTasteAnalyzer:
    """Main analyzer using Claude API for intelligent book scoring."""
    
    def __init__(self, api_key: str = None):
        """
        Initialize the analyzer.
        
        Args:
            api_key: Anthropic API key. If None, reads from ANTHROPIC_API_KEY env var.
        """
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("API key required. Set ANTHROPIC_API_KEY env var or pass api_key.")
        self.client = anthropic.Anthropic(api_key=self.api_key)
    
    def analyze_reading_taste(self, read_books: List[Book]) -> TasteProfile:
        """
        Analyze user's reading taste based on books they've read.
        
        Args:
            read_books: List of books the user has read
            
        Returns:
            TasteProfile with analyzed preferences
        """
        if not read_books:
            return TasteProfile(
                favorite_genres={},
                favorite_authors={},
                common_themes={},
                era_preferences={},
                reading_level="unknown",
                diversity_score=0.0,
                summary="No books read yet."
            )
        
        # Prepare book data for LLM
        books_json = json.dumps([{
            "title": b.title,
            "author": b.author,
            "genres": b.genres,
            "themes": b.themes,
            "year": b.year,
            "description": b.description
        } for b in read_books], indent=2)
        
        prompt = f"""Analyze this user's reading taste based on the books they've read.

Books read:
{books_json}

Provide a detailed analysis in the following JSON format:
{{
  "favorite_genres": {{"genre1": weight, "genre2": weight, ...}},  // weights sum to 1.0
  "favorite_authors": {{"author1": count, "author2": count, ...}},
  "common_themes": {{"theme1": count, "theme2": count, ...}},
  "era_preferences": {{"contemporary": count, "classic": count, "modern": count}},
  "reading_level": "literary" | "commercial" | "mixed",
  "diversity_score": 0.0-1.0,  // how diverse their reading is
  "summary": "Natural language summary of their taste profile"
}}

Consider:
- Genre preferences and patterns
- Author preferences and similarities between authors
- Recurring themes and subject matter
- Time period preferences
- Literary vs commercial fiction balance
- Reading diversity (how varied their choices are)

Be specific and insightful in the summary."""

        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Parse response
        content = response.content[0].text
        
        # Extract JSON from response
        try:
            # Try to find JSON in the response
            start = content.find('{')
            end = content.rfind('}') + 1
            if start != -1 and end > start:
                json_str = content[start:end]
                data = json.loads(json_str)
            else:
                data = json.loads(content)
            
            return TasteProfile(
                favorite_genres=data.get("favorite_genres", {}),
                favorite_authors=data.get("favorite_authors", {}),
                common_themes=data.get("common_themes", {}),
                era_preferences=data.get("era_preferences", {}),
                reading_level=data.get("reading_level", "mixed"),
                diversity_score=data.get("diversity_score", 0.5),
                summary=data.get("summary", "")
            )
        except json.JSONDecodeError as e:
            print(f"Error parsing LLM response: {e}")
            print(f"Response: {content}")
            # Return basic profile as fallback
            return self._create_basic_profile(read_books)
    
    def _create_basic_profile(self, read_books: List[Book]) -> TasteProfile:
        """Create a basic taste profile without LLM (fallback)."""
        genre_counter = Counter()
        author_counter = Counter()
        theme_counter = Counter()
        
        for book in read_books:
            for genre in book.genres:
                genre_counter[genre] += 1
            author_counter[book.author] += 1
            for theme in book.themes:
                theme_counter[theme] += 1
        
        total_genres = sum(genre_counter.values()) or 1
        favorite_genres = {g: c/total_genres for g, c in genre_counter.most_common(5)}
        
        return TasteProfile(
            favorite_genres=favorite_genres,
            favorite_authors=dict(author_counter.most_common(5)),
            common_themes=dict(theme_counter.most_common(5)),
            era_preferences={},
            reading_level="mixed",
            diversity_score=len(genre_counter) / len(read_books) if read_books else 0,
            summary=f"Enjoys {', '.join(list(favorite_genres.keys())[:3])} with favorite authors including {', '.join(list(author_counter.keys())[:2])}"
        )
    
    def score_unread_books(
        self, 
        taste_profile: TasteProfile, 
        unread_books: List[Book]
    ) -> List[BookScore]:
        """
        Score unread books based on taste profile.
        
        Args:
            taste_profile: User's taste profile
            unread_books: List of unread books to score
            
        Returns:
            List of BookScore objects, sorted by overall_score descending
        """
        if not unread_books:
            return []
        
        # Prepare data for LLM
        profile_json = json.dumps({
            "favorite_genres": taste_profile.favorite_genres,
            "favorite_authors": list(taste_profile.favorite_authors.keys()),
            "common_themes": list(taste_profile.common_themes.keys()),
            "reading_level": taste_profile.reading_level,
            "summary": taste_profile.summary
        }, indent=2)
        
        books_json = json.dumps([{
            "title": b.title,
            "author": b.author,
            "genres": b.genres,
            "themes": b.themes,
            "year": b.year,
            "description": b.description
        } for b in unread_books], indent=2)
        
        prompt = f"""Score these unread books based on the user's reading taste profile.

USER'S TASTE PROFILE:
{profile_json}

UNREAD BOOKS TO SCORE:
{books_json}

For EACH book, provide scores in this JSON format:
[
  {{
    "title": "book title",
    "overall_score": 0-100,
    "genre_match": 0-100,
    "theme_match": 0-100,
    "author_similarity": 0-100,
    "novelty_score": 0-100,
    "reasoning": "detailed explanation of scores",
    "recommendation": "highly_recommended" | "recommended" | "maybe" | "low_priority"
  }},
  ...
]

Scoring criteria:
- overall_score: Holistic match to user's taste (weighted average of other scores)
- genre_match: How well genres align with preferences
- theme_match: How well themes align with common themes
- author_similarity: How similar author's style is to favorites
- novelty_score: How much this offers something new/refreshing (good books can expand horizons)
- recommendation: 
  * highly_recommended (90-100): Perfect fit
  * recommended (70-89): Strong match
  * maybe (50-69): Moderate match
  * low_priority (0-49): Weak match

Be honest and specific in reasoning. Consider both comfort-zone matches AND quality books that might expand their horizons."""

        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        content = response.content[0].text
        
        try:
            # Extract JSON array from response
            start = content.find('[')
            end = content.rfind(']') + 1
            if start != -1 and end > start:
                json_str = content[start:end]
                scores_data = json.loads(json_str)
            else:
                scores_data = json.loads(content)
            
            # Create BookScore objects
            book_scores = []
            book_lookup = {b.title: b for b in unread_books}
            
            for score_data in scores_data:
                title = score_data.get("title", "")
                book = book_lookup.get(title)
                
                if book:
                    book_score = BookScore(
                        book=book,
                        overall_score=score_data.get("overall_score", 0),
                        genre_match=score_data.get("genre_match", 0),
                        theme_match=score_data.get("theme_match", 0),
                        author_similarity=score_data.get("author_similarity", 0),
                        novelty_score=score_data.get("novelty_score", 0),
                        reasoning=score_data.get("reasoning", ""),
                        recommendation=score_data.get("recommendation", "maybe")
                    )
                    book_scores.append(book_score)
            
            # Sort by overall score
            book_scores.sort(key=lambda x: x.overall_score, reverse=True)
            return book_scores
            
        except json.JSONDecodeError as e:
            print(f"Error parsing scores: {e}")
            print(f"Response: {content}")
            return []
    
    def get_recommendations(
        self,
        read_books: List[Book],
        unread_books: List[Book],
        top_n: int = 5
    ) -> Tuple[TasteProfile, List[BookScore]]:
        """
        Complete pipeline: analyze taste and score unread books.
        
        Args:
            read_books: Books the user has read
            unread_books: Books to score
            top_n: Number of top recommendations to return (default: 5, None for all)
            
        Returns:
            Tuple of (TasteProfile, List[BookScore])
        """
        print("Analyzing reading taste...")
        taste_profile = self.analyze_reading_taste(read_books)
        
        print("Scoring unread books...")
        scored_books = self.score_unread_books(taste_profile, unread_books)
        
        if top_n is not None:
            scored_books = scored_books[:top_n]
        
        return taste_profile, scored_books


def format_output(taste_profile: TasteProfile, scored_books: List[BookScore]) -> str:
    """Format the analysis results for display."""
    output = []
    
    output.append("=" * 60)
    output.append("READING TASTE PROFILE")
    output.append("=" * 60)
    output.append(f"\n{taste_profile.summary}\n")
    
    output.append("Top Genres:")
    for genre, weight in sorted(taste_profile.favorite_genres.items(), 
                                 key=lambda x: x[1], reverse=True)[:5]:
        output.append(f"  • {genre}: {weight:.1%}")
    
    if taste_profile.favorite_authors:
        output.append("\nFavorite Authors:")
        for author, count in sorted(taste_profile.favorite_authors.items(), 
                                     key=lambda x: x[1], reverse=True)[:5]:
            output.append(f"  • {author} ({count} books)")
    
    output.append(f"\nReading Diversity: {taste_profile.diversity_score:.1%}")
    output.append(f"Reading Level: {taste_profile.reading_level}")
    
    output.append("\n" + "=" * 60)
    output.append("RECOMMENDED BOOKS")
    output.append("=" * 60)
    
    for i, score in enumerate(scored_books, 1):
        output.append(f"\n{i}. {score.book.title} by {score.book.author}")
        output.append(f"   Overall Score: {score.overall_score:.0f}/100 [{score.recommendation.upper()}]")
        output.append(f"   Genre Match: {score.genre_match:.0f} | Theme Match: {score.theme_match:.0f}")
        output.append(f"   Author Similarity: {score.author_similarity:.0f} | Novelty: {score.novelty_score:.0f}")
        output.append(f"   {score.reasoning}")
    
    return "\n".join(output)


# Example usage
if __name__ == "__main__":
    # Example data
    read_books = [
        Book(
            title="1984",
            author="George Orwell",
            genres=["Dystopian", "Political Fiction", "Science Fiction"],
            themes=["Totalitarianism", "Surveillance", "Control"],
            year=1949,
            description="A dystopian novel about totalitarian control"
        ),
        Book(
            title="Brave New World",
            author="Aldous Huxley",
            genres=["Dystopian", "Science Fiction"],
            themes=["Technology", "Control", "Society"],
            year=1932
        ),
        Book(
            title="The Handmaid's Tale",
            author="Margaret Atwood",
            genres=["Dystopian", "Feminist Fiction"],
            themes=["Oppression", "Gender", "Religion"],
            year=1985
        )
    ]
    
    unread_books = [
        Book(
            title="Fahrenheit 451",
            author="Ray Bradbury",
            genres=["Dystopian", "Science Fiction"],
            themes=["Censorship", "Knowledge", "Technology"],
            year=1953,
            description="A dystopian novel about book burning"
        ),
        Book(
            title="The Road",
            author="Cormac McCarthy",
            genres=["Post-Apocalyptic", "Literary Fiction"],
            themes=["Survival", "Father-Son", "Hope"],
            year=2006
        ),
        Book(
            title="Harry Potter and the Philosopher's Stone",
            author="J.K. Rowling",
            genres=["Fantasy", "Young Adult"],
            themes=["Magic", "Coming of Age", "Friendship"],
            year=1997
        ),
        Book(
            title="Never Let Me Go",
            author="Kazuo Ishiguro",
            genres=["Dystopian", "Literary Fiction", "Science Fiction"],
            themes=["Identity", "Ethics", "Memory"],
            year=2005
        )
    ]
    
    # Initialize analyzer (requires ANTHROPIC_API_KEY environment variable)
    try:
        analyzer = BookTasteAnalyzer()
        
        # Get recommendations
        taste_profile, recommendations = analyzer.get_recommendations(
            read_books=read_books,
            unread_books=unread_books,
            top_n=None  # Get all scored books
        )
        
        # Display results
        print(format_output(taste_profile, recommendations))
        
    except ValueError as e:
        print(f"Error: {e}")
        print("\nTo use this analyzer, set your Anthropic API key:")
        print("export ANTHROPIC_API_KEY='your-api-key-here'")