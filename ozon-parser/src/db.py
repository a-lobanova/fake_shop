from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "sqlite:///ozon_clothing_items.db"

Base = declarative_base()


class ClothingItem(Base):
    __tablename__ = "clothing_items"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    price = Column(String, nullable=False)
    description = Column(String)
    url = Column(String)
    image_url = Column(String)
    image_blob = Column(String)  # Для хранения base64-строки изображения
    category = Column(String)  # Новое поле для категории


def get_db_session():
    engine = create_engine(DATABASE_URL)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


def save_clothing_item(name, price, description, url, image_url, image_blob, category):
    session = get_db_session()
    new_item = ClothingItem(
        name=name,
        price=price,
        description=description,
        url=url,
        image_url=image_url,
        image_blob=image_blob,
        category=category,
    )
    session.add(new_item)
    session.commit()
    session.close()
