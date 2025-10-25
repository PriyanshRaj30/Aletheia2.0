import json
from typing import List, Dict, Tuple
from dataclasses import dataclass, asdict
from collections import Counter
import ollama


@dataclass
class Book:
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
    favorite_genres: Dict[str, float]
    favorite_authors: Dict[str, int]
    common_themes: Dict[str, int]
    era_preferences: Dict[str, int]
    reading_level: str
    diversity_score: float
    summary: str


@dataclass
class BookScore:
    book: Book
    overall_score: float
    genre_match: float
    theme_match: float
    author_similarity: float
    novelty_score: float
    reasoning: str
    recommendation: str


class BookTasteAnalyzer:
    def __init__(self, model: str = "llama3"):
        """
        Initialize with an Ollama model (e.g., 'llama3', 'mistral', etc.)
        """
        self.model = model
    
    def _chat(self, prompt: str) -> str:
        """Wrapper for Ollama chat calls."""
        response = ollama.chat(
            model=self.model,
            messages=[{"role": "user", "content": prompt}]
        )
        return response["message"]["content"]
    
    def analyze_reading_taste(self, read_books: List[Book]) -> TasteProfile:
        if not read_books:
            return TasteProfile({}, {}, {}, {}, "unknown", 0.0, "No books read yet.")
        
        books_json = json.dumps([asdict(b) for b in read_books], indent=2)
        prompt = f"""
            Analyze this user's reading taste based on the books they've read.

            Books read:
            {books_json}

            Provide only a detailed analysis in JSON format:
            {{
            "favorite_genres": {{"genre1": weight, "genre2": weight, ...}},
            "favorite_authors": {{"author1": count, "author2": count, ...}},
            "common_themes": {{"theme1": count, "theme2": count, ...}},
            "era_preferences": {{"contemporary": count, "classic": count, "modern": count}},
            "diversity_score": 0.0-1.0,
            "summary": "Natural language summary"
            }}
            """
        content = self._chat(prompt)

        try:
            start = content.find('{')
            end = content.rfind('}') + 1
            data = json.loads(content[start:end])
        except Exception as e:
            print(f"Error parsing taste profile: {e}\nResponse:\n{content}")
            return self._create_basic_profile(read_books)

        return TasteProfile(
            favorite_genres=data.get("favorite_genres", {}),
            favorite_authors=data.get("favorite_authors", {}),
            common_themes=data.get("common_themes", {}),
            era_preferences=data.get("era_preferences", {}),
            reading_level=data.get("reading_level", "mixed"),
            diversity_score=data.get("diversity_score", 0.5),
            summary=data.get("summary", "")
        )

    def _create_basic_profile(self, read_books: List[Book]) -> TasteProfile:
        genre_counter = Counter()
        author_counter = Counter()
        theme_counter = Counter()
        for book in read_books:
            genre_counter.update(book.genres)
            author_counter[book.author] += 1
            theme_counter.update(book.themes)
        total_genres = sum(genre_counter.values()) or 1
        favorite_genres = {g: c/total_genres for g, c in genre_counter.most_common(5)}
        return TasteProfile(
            favorite_genres=favorite_genres,
            favorite_authors=dict(author_counter.most_common(5)),
            common_themes=dict(theme_counter.most_common(5)),
            era_preferences={},
            reading_level="mixed",
            diversity_score=len(genre_counter) / len(read_books),
            summary=f"Enjoys {', '.join(list(favorite_genres.keys())[:3])}"
        )
    
    def score_unread_books(self, taste_profile: TasteProfile, unread_books: List[Book]) -> List[BookScore]:
        if not unread_books:
            return []
        
        profile_json = json.dumps(asdict(taste_profile), indent=2)
        books_json = json.dumps([asdict(b) for b in unread_books], indent=2)
        prompt = f"""
        Score these unread books based on the user's reading taste profile.

        TASTE PROFILE:
        {profile_json}

        UNREAD BOOKS:
        {books_json}

        Return a JSON array like:
        [
        {{
            "title": "book title",
            "overall_score": 0-100,
            "genre_match": 0-100,
            "theme_match": 0-100,
            "author_similarity": 0-100,
            "novelty_score": 0-100,
            "reasoning": "reasoning text",
            "recommendation": "highly_recommended" | "recommended" | "maybe" | "low_priority"
        }}
        ]
        """
        content = self._chat(prompt)
        try:
            start = content.find('[')
            end = content.rfind(']') + 1
            scores_data = json.loads(content[start:end])
        except Exception as e:
            print(f"Error parsing scores: {e}\nResponse:\n{content}")
            return []
        
        book_lookup = {b.title: b for b in unread_books}
        book_scores = []
        for score in scores_data:
            book = book_lookup.get(score.get("title", ""))
            if book:
                book_scores.append(BookScore(
                    book=book,
                    overall_score=score.get("overall_score", 0),
                    genre_match=score.get("genre_match", 0),
                    theme_match=score.get("theme_match", 0),
                    author_similarity=score.get("author_similarity", 0),
                    novelty_score=score.get("novelty_score", 0),
                    reasoning=score.get("reasoning", ""),
                    recommendation=score.get("recommendation", "maybe")
                ))
        return sorted(book_scores, key=lambda x: x.overall_score, reverse=True)
    
    def get_recommendations(self, read_books: List[Book], unread_books: List[Book], top_n: int = 5):
        print("Analyzing reading taste...")
        taste_profile = self.analyze_reading_taste(read_books)
        print("Scoring unread books...")
        scored_books = self.score_unread_books(taste_profile, unread_books)
        return taste_profile, scored_books[:top_n]


def format_output(taste_profile: TasteProfile, scored_books: List[BookScore]) -> str:
    output = ["=" * 60, "READING TASTE PROFILE", "=" * 60, f"\n{taste_profile.summary}\n"]
    output.append("Top Genres:")
    for genre, weight in taste_profile.favorite_genres.items():
        output.append(f"  • {genre}: {weight:.1%}")
    if taste_profile.favorite_authors:
        output.append("\nFavorite Authors:")
        for author, count in taste_profile.favorite_authors.items():
            output.append(f"  • {author} ({count})")
    output.append(f"\nReading Diversity: {taste_profile.diversity_score:.1%}")
    output.append(f"Reading Level: {taste_profile.reading_level}")
    output.append("\n" + "=" * 60)
    output.append("RECOMMENDED BOOKS")
    output.append("=" * 60)
    for i, score in enumerate(scored_books, 1):
        output.append(f"\n{i}. {score.book.title} by {score.book.author}")
        output.append(f"   Overall Score: {score.overall_score:.0f}/100 [{score.recommendation.upper()}]")
        output.append(f"   {score.reasoning}")
    return "\n".join(output)


if __name__ == "__main__":
    read_books = [
        Book("1984", "George Orwell", ["Dystopian", "Political Fiction"], ["Totalitarianism", "Surveillance"], 1949),
        Book("Brave New World", "Aldous Huxley", ["Dystopian"], ["Technology", "Control"], 1932),
        Book("The Handmaid's Tale", "Margaret Atwood", ["Dystopian"], ["Oppression", "Gender"], 1985)
    ]
    unread_books = [
        Book("Fahrenheit 451", "Ray Bradbury", ["Dystopian"], ["Censorship", "Knowledge"], 1953),
        Book("The Road", "Cormac McCarthy", ["Post-Apocalyptic"], ["Survival", "Hope"], 2006),
        Book("Harry Potter and the Philosopher's Stone", "J.K. Rowling", ["Fantasy"], ["Magic", "Friendship"], 1997)
    ]
    
    analyzer = BookTasteAnalyzer(model="llama3.2:1b")  # change to any model you want
    profile, recs = analyzer.get_recommendations(read_books, unread_books)
    print(format_output(profile, recs))
