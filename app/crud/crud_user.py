from sqlalchemy.orm import Session
from app.models.user import User

def get_user_by_username(db: Session, username: str):
    return db.query(User).filter(User.username == username, User.active == True).first()

def get_users(db: Session):
    return db.query(User).order_by(User.role, User.username).all()
