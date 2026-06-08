from sqlalchemy import Column, Integer, String
from database import Base

class StudentDB(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    email = Column(String, unique=True)

from sqlalchemy import Column, Integer

class ProgressDB(Base):
    __tablename__ = "progress"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer)
    score = Column(Integer)

