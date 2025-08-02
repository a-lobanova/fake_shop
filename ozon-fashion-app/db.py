from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import random

DATABASE_URL = "sqlite:///ozon_clothing_items.db"
Base = declarative_base()


class ClothingItem(Base):
    __tablename__ = "clothing_items"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    price = Column(String)
    description = Column(String)
    url = Column(String)
    image_url = Column(String)
    image_blob = Column(String)
    category = Column(String)


def get_db_session():
    engine = create_engine(DATABASE_URL)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


def get_item_by_id(item_id):
    session = get_db_session()
    item = session.query(ClothingItem).filter_by(id=item_id).first()
    session.close()
    return item


def find_similar_items(image_path, top_n=5, comment=""):
    """Обёртка, перенаправляющая вызов к реальной AI-модели."""
    from model.ai_model import find_similar_items as _ai_find
    return _ai_find(image_path=image_path, top_n=top_n, comment=comment)
