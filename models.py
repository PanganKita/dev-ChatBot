"""
PanganKita — Data Models
Sesuai dokumen teknikal Module D (Conversational Interface) +
Module C (Sourcing Recommendation) data model.
"""

import enum
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Enum as SQLEnum,
    Float, ForeignKey, Integer, String, Text,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class UserType(str, enum.Enum):
    PETANI = "petani"
    TENGKULAK = "tengkulak"
    PEDAGANG = "pedagang"
    LEMBAGA = "lembaga"


class TransactionStatus(str, enum.Enum):
    PENDING = "pending"
    NEGOTIATING = "negotiating"
    ACCEPTED = "accepted"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


# ── Region ─────────────────────────────────────────────────────────────────────

class Region(Base):
    __tablename__ = "regions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    province = Column(String(100), nullable=False)
    kabupaten = Column(String(100), nullable=True)
    kecamatan = Column(String(100), nullable=True)

    suppliers = relationship("Supplier", back_populates="region")
    supply_records = relationship("SupplyRecord", back_populates="region")
    harvest_reports = relationship("HarvestReport", back_populates="region")


# ── User ───────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(Integer, unique=True, nullable=False, index=True)
    username = Column(String(100), nullable=True)
    full_name = Column(String(200), nullable=False)
    user_type = Column(SQLEnum(UserType), nullable=True)
    region_id = Column(Integer, ForeignKey("regions.id"), nullable=True)
    registered = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)

    region = relationship("Region")
    supplier = relationship("Supplier", back_populates="user", uselist=False)


# ── Commodity ──────────────────────────────────────────────────────────────────

class Commodity(Base):
    __tablename__ = "commodities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False, unique=True)
    category = Column(String(100), nullable=True)
    unit = Column(String(50), default="kg")


# ── Supplier & Stock ───────────────────────────────────────────────────────────

class Supplier(Base):
    """Petani atau tengkulak yang menyuplai komoditas."""
    __tablename__ = "suppliers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    name = Column(String(200), nullable=False)
    supplier_type = Column(SQLEnum(UserType), nullable=False)
    region_id = Column(Integer, ForeignKey("regions.id"), nullable=False)
    reliability_score = Column(Float, default=0.5)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)

    user = relationship("User", back_populates="supplier")
    region = relationship("Region", back_populates="suppliers")
    commodities = relationship(
        "SupplierCommodity", back_populates="supplier", cascade="all, delete-orphan"
    )
    transactions_as_seller = relationship(
        "TransactionHistory",
        foreign_keys="TransactionHistory.supplier_id",
        back_populates="supplier",
    )


class SupplierCommodity(Base):
    """Stok komoditas yang tersedia dari supplier."""
    __tablename__ = "supplier_commodities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    commodity_id = Column(Integer, ForeignKey("commodities.id"), nullable=False)
    available_quantity = Column(Float, nullable=False, default=0)
    price_per_unit = Column(Float, nullable=False)
    status = Column(String(50), default="available")
    last_updated = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    supplier = relationship("Supplier", back_populates="commodities")
    commodity = relationship("Commodity")


# ── Supply Record (data stok terkonsolidasi per region) ────────────────────────

class SupplyRecord(Base):
    __tablename__ = "supply_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    region_id = Column(Integer, ForeignKey("regions.id"), nullable=False)
    commodity_id = Column(Integer, ForeignKey("commodities.id"), nullable=False)
    quantity = Column(Float, nullable=False)
    price_per_unit = Column(Float, nullable=True)
    record_date = Column(DateTime, default=datetime.now)
    source = Column(String(100), default="crowdsourced")

    region = relationship("Region", back_populates="supply_records")
    commodity = relationship("Commodity")


# ── Harvest Report (laporan panen dari petani via bot) ─────────────────────────

class HarvestReport(Base):
    __tablename__ = "harvest_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    region_id = Column(Integer, ForeignKey("regions.id"), nullable=False)
    commodity_id = Column(Integer, ForeignKey("commodities.id"), nullable=False)
    quantity = Column(Float, nullable=False)
    harvest_date = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now)

    user = relationship("User")
    region = relationship("Region", back_populates="harvest_reports")
    commodity = relationship("Commodity")


# ── Transaction History ────────────────────────────────────────────────────────

class TransactionHistory(Base):
    __tablename__ = "transaction_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    buyer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    commodity_id = Column(Integer, ForeignKey("commodities.id"), nullable=False)
    quantity = Column(Float, nullable=False)
    price_per_unit = Column(Float, nullable=False)
    total_price = Column(Float, nullable=False)
    status = Column(SQLEnum(TransactionStatus), default=TransactionStatus.PENDING)
    fulfilled = Column(Boolean, default=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    supplier = relationship("Supplier", back_populates="transactions_as_seller")
    buyer = relationship("User")
    commodity = relationship("Commodity")


# ── Active Chat (relay percakapan) ─────────────────────────────────────────────

class ActiveChat(Base):
    __tablename__ = "active_chats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    buyer_telegram_id = Column(Integer, nullable=False)
    seller_telegram_id = Column(Integer, nullable=False)
    transaction_id = Column(Integer, ForeignKey("transaction_history.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)
