from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from core.database import Base


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), unique=True, nullable=False)
    display_order = Column(Integer, default=0, nullable=False)


class Menu(Base):
    __tablename__ = "menus"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    category = Column(String(50), ForeignKey("categories.name"), nullable=False)
    price = Column(Integer, nullable=False)
    emoji = Column(String(10), nullable=True)
    cal = Column(Integer, nullable=True)
    temp = Column(String(20), nullable=True)  # hot, cold, both
    description = Column(String(255), nullable=True)
    image_url = Column(String(500), nullable=True)
    is_available = Column(Boolean, default=True, nullable=False)


class OptionGroup(Base):
    __tablename__ = "option_groups"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False)       # "온도", "사이즈", "당도" 등
    is_required = Column(Boolean, default=True, nullable=False)
    min_select = Column(Integer, default=1, nullable=False)
    max_select = Column(Integer, default=1, nullable=False)


class OptionItem(Base):
    __tablename__ = "option_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    group_id = Column(Integer, ForeignKey("option_groups.id"), nullable=False)
    name = Column(String(50), nullable=False)        # "핫", "아이스", "Regular", "Large"
    extra_price = Column(Integer, default=0, nullable=False)
    is_default = Column(Boolean, default=False, nullable=False)
    is_available = Column(Boolean, default=True, nullable=False)


class MenuOptionGroup(Base):
    """메뉴 - 옵션 그룹 연결 테이블"""
    __tablename__ = "menu_option_groups"

    id = Column(Integer, primary_key=True, autoincrement=True)
    menu_id = Column(Integer, ForeignKey("menus.id"), nullable=False)
    option_group_id = Column(Integer, ForeignKey("option_groups.id"), nullable=False)
    display_order = Column(Integer, default=0, nullable=False)
