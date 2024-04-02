from sqlalchemy import create_engine, Column, Integer, String, DateTime, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

Base = declarative_base()

class Connection(Base):
    """Model for LinkedIn connections"""
    __tablename__ = 'connections'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    occupation = Column(String)
    profile_url = Column(String, unique=True)
    first_seen = Column(DateTime, default=func.now())
    last_updated = Column(DateTime, default=func.now(), onupdate=func.now())

class ScrapingHistory(Base):
    """Model for scraping history"""
    __tablename__ = 'scraping_history'

    id = Column(Integer, primary_key=True)
    scrape_date = Column(DateTime, default=func.now())
    connections_count = Column(Integer)

# Database setup function
def init_db(db_url='sqlite:///linkedin_connections.db'):
    """Initialize database and return session maker"""
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session 