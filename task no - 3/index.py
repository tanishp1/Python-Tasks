"""
Task 3: Database ORM Integration (SQLAlchemy)
------------------------------------------------
A relational database layer for a bookstore inventory system.
"""

from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import declarative_base, relationship, sessionmaker, joinedload

# --------------------------------------------------------------------------
# 1. Engine & Session setup
# --------------------------------------------------------------------------
# DATABASE_URL = "postgresql://postgres:<password>@localhost:5432/bookstore"  # PostgreSQL
DATABASE_URL = "sqlite:///bookstore.db"   # SQLite (active)
engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

Base = declarative_base()

# --------------------------------------------------------------------------
# 2. Models: Author (One) -> Book (Many)
# --------------------------------------------------------------------------
class Author(Base):
    __tablename__ = "authors"

    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False, unique=True)
    country = Column(String(80))

    # One-to-Many: one Author has many Books.
    # back_populates keeps both sides of the relationship in sync.
    # cascade ensures books are deleted if their author is deleted.
    books = relationship(
        "Book",
        back_populates="author",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<Author id={self.id} name={self.name!r}>"


class Book(Base):
    __tablename__ = "books"

    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    price = Column(Float, nullable=False)
    isbn = Column(String(20), unique=True)

    # Foreign Key -> the "Many" side of the relationship
    author_id = Column(Integer, ForeignKey("authors.id"), nullable=False)

    # Many-to-One back reference
    author = relationship("Author", back_populates="books")

    def __repr__(self):
        return f"<Book id={self.id} title={self.title!r}>"


# --------------------------------------------------------------------------
# 3. Populate the database
# --------------------------------------------------------------------------
def populate_db(session):
    """Seed the database with authors and books (idempotent-ish for demo)."""

    # Wipe existing data so the script can be re-run cleanly for a demo.
    session.query(Book).delete()
    session.query(Author).delete()
    session.commit()

    author_data = [
        {
            "name": "George Orwell",
            "country": "UK",
            "books": [
                {"title": "1984", "price": 9.99, "isbn": "9780451524935"},
                {"title": "Animal Farm", "price": 7.99, "isbn": "9780451526342"},
            ],
        },
        {
            "name": "Agatha Christie",
            "country": "UK",
            "books": [
                {"title": "Murder on the Orient Express", "price": 8.50, "isbn": "9780062693662"},
                {"title": "And Then There Were None", "price": 8.99, "isbn": "9780062073488"},
                {"title": "The Murder of Roger Ackroyd", "price": 7.50, "isbn": "9780062073568"},
            ],
        },
        {
            "name": "Haruki Murakami",
            "country": "Japan",
            "books": [
                {"title": "Norwegian Wood", "price": 10.99, "isbn": "9780375704024"},
            ],
        },
    ]

    for entry in author_data:
        author = Author(name=entry["name"], country=entry["country"])
        # Building Book objects and assigning via the relationship lets
        # SQLAlchemy handle the author_id foreign key automatically.
        author.books = [Book(**b) for b in entry["books"]]
        session.add(author)

    session.commit()
    print(f"Seeded {len(author_data)} authors and "
          f"{sum(len(a['books']) for a in author_data)} books.")


# --------------------------------------------------------------------------
# 4. Query books by author — N+1 safe
# --------------------------------------------------------------------------
def get_books_by_author(session, author_name: str):

    author = (
        session.query(Author)
        .options(joinedload(Author.books))   # <-- single JOIN query
        .filter(Author.name == author_name)
        .first()
    )
    return author


def get_all_authors_with_books(session):
    
    return (
        session.query(Author)
        .options(joinedload(Author.books))
        .all()
    )


# --------------------------------------------------------------------------
# 5. Demo / entry point
# --------------------------------------------------------------------------
if __name__ == "__main__":
    Base.metadata.create_all(engine)   # create tables if they don't exist
    session = SessionLocal()

    try:
        populate_db(session)

        print("\n--- Query: books by a single author (optimized JOIN) ---")
        author = get_books_by_author(session, "Agatha Christie")
        if author:
            print(f"{author.name} ({author.country})")
            for book in author.books:
                print(f"  - {book.title}  (${book.price})  ISBN: {book.isbn}")

        print("\n--- Query: all authors with books, single query ---")
        for a in get_all_authors_with_books(session):
            titles = ", ".join(b.title for b in a.books)
            print(f"{a.name}: {titles}")

        # Show the actual SQL executed for the optimized query (proof of 1 JOIN)
        print("\n--- SQL generated for get_books_by_author (verification) ---")
        q = (
            session.query(Author)
            .options(joinedload(Author.books))
            .filter(Author.name == "Agatha Christie")
        )
        print(q.statement.compile(engine, compile_kwargs={"literal_binds": True}))

    finally:
        session.close()