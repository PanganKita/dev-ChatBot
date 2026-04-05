"""
PanganKita — Database layer
Sesuai dokumen teknikal: Region-based, Supplier model, Recommendation scoring.
"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from config import DATABASE_URL
from models import (
    ActiveChat, Base, Commodity, HarvestReport, Region,
    Supplier, SupplierCommodity, SupplyRecord,
    TransactionHistory, TransactionStatus, User, UserType,
)

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

# ── Seed data ──────────────────────────────────────────────────────────────────

COMMODITIES_SEED = [
    {"name": "Beras", "category": "Pangan", "unit": "ton"},
    {"name": "Jagung", "category": "Pangan", "unit": "ton"},
    {"name": "Kedelai", "category": "Pangan", "unit": "ton"},
    {"name": "Cabai Merah", "category": "Sayuran", "unit": "kg"},
    {"name": "Cabai Rawit", "category": "Sayuran", "unit": "kg"},
    {"name": "Bawang Merah", "category": "Sayuran", "unit": "kg"},
    {"name": "Bawang Putih", "category": "Sayuran", "unit": "kg"},
    {"name": "Tomat", "category": "Sayuran", "unit": "kg"},
    {"name": "Kentang", "category": "Sayuran", "unit": "kg"},
    {"name": "Wortel", "category": "Sayuran", "unit": "kg"},
    {"name": "Kacang Tanah", "category": "Pangan", "unit": "ton"},
    {"name": "Singkong", "category": "Pangan", "unit": "ton"},
]

# Pilot scope: 3 provinsi sesuai dokumen
REGIONS_SEED = [
    {"name": "Jawa Barat", "province": "Jawa Barat"},
    {"name": "Bandung", "province": "Jawa Barat", "kabupaten": "Bandung"},
    {"name": "Garut", "province": "Jawa Barat", "kabupaten": "Garut"},
    {"name": "Karawang", "province": "Jawa Barat", "kabupaten": "Karawang"},
    {"name": "Cianjur", "province": "Jawa Barat", "kabupaten": "Cianjur"},
    {"name": "Subang", "province": "Jawa Barat", "kabupaten": "Subang"},
    {"name": "Jawa Tengah", "province": "Jawa Tengah"},
    {"name": "Brebes", "province": "Jawa Tengah", "kabupaten": "Brebes"},
    {"name": "Demak", "province": "Jawa Tengah", "kabupaten": "Demak"},
    {"name": "Klaten", "province": "Jawa Tengah", "kabupaten": "Klaten"},
    {"name": "Solo", "province": "Jawa Tengah", "kabupaten": "Solo"},
    {"name": "Semarang", "province": "Jawa Tengah", "kabupaten": "Semarang"},
    {"name": "NTT", "province": "Nusa Tenggara Timur"},
    {"name": "Kupang", "province": "Nusa Tenggara Timur", "kabupaten": "Kupang"},
    {"name": "Ende", "province": "Nusa Tenggara Timur", "kabupaten": "Ende"},
]


def init_db():
    Base.metadata.create_all(engine)
    _seed_commodities()
    _seed_regions()


def _seed_commodities():
    with SessionLocal() as session:
        for data in COMMODITIES_SEED:
            exists = session.execute(
                select(Commodity).where(Commodity.name == data["name"])
            ).scalar_one_or_none()
            if not exists:
                session.add(Commodity(**data))
        session.commit()


def _seed_regions():
    with SessionLocal() as session:
        for data in REGIONS_SEED:
            exists = session.execute(
                select(Region).where(
                    Region.name == data["name"],
                    Region.province == data["province"],
                )
            ).scalar_one_or_none()
            if not exists:
                session.add(Region(**data))
        session.commit()


# ── User ──────────────────────────────────────────────────────────────────────

def get_user(telegram_id: int) -> Optional[User]:
    with SessionLocal() as session:
        user = session.execute(
            select(User).where(User.telegram_id == telegram_id)
        ).scalar_one_or_none()
        if user:
            session.expunge(user)
        return user


def upsert_user(telegram_id: int, username: str, full_name: str) -> User:
    with SessionLocal() as session:
        user = session.execute(
            select(User).where(User.telegram_id == telegram_id)
        ).scalar_one_or_none()
        if user:
            user.username = username
            user.full_name = full_name
        else:
            user = User(
                telegram_id=telegram_id, username=username, full_name=full_name
            )
            session.add(user)
        session.commit()
        session.expunge(user)
        return user


def register_user(
    telegram_id: int, user_type: UserType, region_id: int = None
) -> User:
    with SessionLocal() as session:
        user = session.execute(
            select(User).where(User.telegram_id == telegram_id)
        ).scalar_one_or_none()
        if user:
            user.user_type = user_type
            user.region_id = region_id
            user.registered = True
            session.commit()
            session.expunge(user)
        return user


# ── Region ────────────────────────────────────────────────────────────────────

def find_region(name: str) -> Optional[Region]:
    """Cari region by nama (fuzzy-ish: case-insensitive contains)."""
    with SessionLocal() as session:
        region = session.execute(
            select(Region).where(
                func.lower(Region.name).contains(name.lower())
            )
        ).scalar_one_or_none()
        if region:
            session.expunge(region)
        return region


def find_region_by_kabupaten(kabupaten: str) -> Optional[Region]:
    with SessionLocal() as session:
        region = session.execute(
            select(Region).where(
                func.lower(Region.kabupaten).contains(kabupaten.lower())
            )
        ).scalar_one_or_none()
        if region:
            session.expunge(region)
        return region


def get_all_regions() -> List[Region]:
    with SessionLocal() as session:
        regions = session.execute(
            select(Region).order_by(Region.province, Region.name)
        ).scalars().all()
        for r in regions:
            session.expunge(r)
        return regions


def get_region_by_id(region_id: int) -> Optional[Region]:
    with SessionLocal() as session:
        r = session.get(Region, region_id)
        if r:
            session.expunge(r)
        return r


# ── Commodity ─────────────────────────────────────────────────────────────────

def find_commodity(name: str) -> Optional[Commodity]:
    """Cari commodity by nama (case-insensitive contains)."""
    with SessionLocal() as session:
        commodity = session.execute(
            select(Commodity).where(
                func.lower(Commodity.name).contains(name.lower())
            )
        ).scalar_one_or_none()
        if commodity:
            session.expunge(commodity)
        return commodity


def get_all_commodities() -> List[Commodity]:
    with SessionLocal() as session:
        commodities = session.execute(
            select(Commodity).order_by(Commodity.category, Commodity.name)
        ).scalars().all()
        for c in commodities:
            session.expunge(c)
        return commodities


def get_commodity_by_id(commodity_id: int) -> Optional[Commodity]:
    with SessionLocal() as session:
        c = session.get(Commodity, commodity_id)
        if c:
            session.expunge(c)
        return c


# ── Supplier ──────────────────────────────────────────────────────────────────

def create_supplier(
    user_id: int, name: str, supplier_type: UserType, region_id: int
) -> Supplier:
    with SessionLocal() as session:
        supplier = Supplier(
            user_id=user_id, name=name,
            supplier_type=supplier_type, region_id=region_id,
        )
        session.add(supplier)
        session.commit()
        session.expunge(supplier)
        return supplier


def get_supplier_by_user(user_id: int) -> Optional[Supplier]:
    with SessionLocal() as session:
        s = session.execute(
            select(Supplier).where(Supplier.user_id == user_id)
        ).scalar_one_or_none()
        if s:
            session.expunge(s)
        return s


def get_supplier_by_id(supplier_id: int) -> Optional[Supplier]:
    with SessionLocal() as session:
        s = session.get(Supplier, supplier_id)
        if s:
            session.expunge(s)
        return s


def upsert_supplier_commodity(
    supplier_id: int, commodity_id: int, price: float, quantity: float
) -> SupplierCommodity:
    with SessionLocal() as session:
        sc = session.execute(
            select(SupplierCommodity).where(
                SupplierCommodity.supplier_id == supplier_id,
                SupplierCommodity.commodity_id == commodity_id,
            )
        ).scalar_one_or_none()
        if sc:
            sc.price_per_unit = price
            sc.available_quantity = quantity
            sc.last_updated = datetime.now()
            sc.status = "available" if quantity > 0 else "habis"
        else:
            sc = SupplierCommodity(
                supplier_id=supplier_id, commodity_id=commodity_id,
                price_per_unit=price, available_quantity=quantity,
            )
            session.add(sc)
        session.commit()
        session.expunge(sc)
        return sc


# ── Recommendation — Scoring per dokumen teknikal ─────────────────────────────
# Score = w1*PriceScore + w2*DistanceScore + w3*ReliabilityScore + w4*AvailabilityScore
# Weights: w1=0.35, w2=0.25, w3=0.20, w4=0.20

def search_suppliers(
    commodity_name: str,
    location_name: str = None,
    quantity_needed: float = 0,
) -> List[dict]:
    """Cari dan ranking supplier berdasarkan komoditas, lokasi, dan jumlah."""
    with SessionLocal() as session:
        query = (
            select(SupplierCommodity, Supplier, Commodity, Region)
            .join(Supplier, SupplierCommodity.supplier_id == Supplier.id)
            .join(Commodity, SupplierCommodity.commodity_id == Commodity.id)
            .join(Region, Supplier.region_id == Region.id)
            .where(func.lower(Commodity.name).contains(commodity_name.lower()))
            .where(SupplierCommodity.available_quantity > 0)
            .where(Supplier.is_active == True)
        )

        rows = session.execute(query).all()
        if not rows:
            return []

        # Hitung scores
        prices = [r.SupplierCommodity.price_per_unit for r in rows]
        min_price = min(prices) if prices else 1
        max_price = max(prices) if prices else 1
        price_range = max_price - min_price if max_price != min_price else 1

        target_region = None
        if location_name:
            target_region = session.execute(
                select(Region).where(
                    func.lower(Region.name).contains(location_name.lower())
                )
            ).scalar_one_or_none()

        results = []
        for r in rows:
            price_score = 1 - (r.SupplierCommodity.price_per_unit - min_price) / price_range
            reliability_score = r.Supplier.reliability_score or 0.5
            avail_score = min(
                r.SupplierCommodity.available_quantity / max(quantity_needed, 1), 1.0
            )

            # Distance score: same province = 0.8, same kabupaten = 1.0, else 0.3
            if target_region:
                if r.Region.province == target_region.province:
                    if (r.Region.kabupaten and target_region.kabupaten and
                            r.Region.kabupaten == target_region.kabupaten):
                        distance_score = 1.0
                    else:
                        distance_score = 0.7
                else:
                    distance_score = 0.3
            else:
                distance_score = 0.5

            total_score = (
                0.35 * price_score
                + 0.25 * distance_score
                + 0.20 * reliability_score
                + 0.20 * avail_score
            )

            results.append({
                "supplier_id": r.Supplier.id,
                "supplier_name": r.Supplier.name,
                "supplier_type": r.Supplier.supplier_type.value,
                "region_name": r.Region.name,
                "province": r.Region.province,
                "commodity_name": r.Commodity.name,
                "commodity_unit": r.Commodity.unit,
                "price": r.SupplierCommodity.price_per_unit,
                "quantity": r.SupplierCommodity.available_quantity,
                "reliability": reliability_score,
                "score": round(total_score, 3),
                "sc_id": r.SupplierCommodity.id,
            })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results


# ── Cek Harga ─────────────────────────────────────────────────────────────────

def get_price_info(commodity_name: str, location_name: str = None) -> List[dict]:
    """Ambil data harga komoditas, opsional filter lokasi."""
    with SessionLocal() as session:
        query = (
            select(SupplierCommodity, Supplier, Commodity, Region)
            .join(Supplier, SupplierCommodity.supplier_id == Supplier.id)
            .join(Commodity, SupplierCommodity.commodity_id == Commodity.id)
            .join(Region, Supplier.region_id == Region.id)
            .where(func.lower(Commodity.name).contains(commodity_name.lower()))
            .where(SupplierCommodity.available_quantity > 0)
            .where(Supplier.is_active == True)
            .order_by(SupplierCommodity.price_per_unit.asc())
        )
        if location_name:
            query = query.where(
                func.lower(Region.name).contains(location_name.lower())
                | func.lower(Region.province).contains(location_name.lower())
            )

        rows = session.execute(query).all()
        return [
            {
                "supplier_name": r.Supplier.name,
                "region": r.Region.name,
                "province": r.Region.province,
                "commodity": r.Commodity.name,
                "unit": r.Commodity.unit,
                "price": r.SupplierCommodity.price_per_unit,
                "quantity": r.SupplierCommodity.available_quantity,
            }
            for r in rows
        ]


# ── Harvest Report ────────────────────────────────────────────────────────────

def create_harvest_report(
    user_id: int, region_id: int, commodity_id: int,
    quantity: float, harvest_date: datetime = None, notes: str = None,
) -> HarvestReport:
    with SessionLocal() as session:
        report = HarvestReport(
            user_id=user_id, region_id=region_id, commodity_id=commodity_id,
            quantity=quantity, harvest_date=harvest_date, notes=notes,
        )
        session.add(report)

        # Otomatis update/buat supply record
        existing = session.execute(
            select(SupplyRecord).where(
                SupplyRecord.region_id == region_id,
                SupplyRecord.commodity_id == commodity_id,
            )
        ).scalar_one_or_none()
        if existing:
            existing.quantity += quantity
            existing.record_date = datetime.now()
        else:
            sr = SupplyRecord(
                region_id=region_id, commodity_id=commodity_id,
                quantity=quantity, source="crowdsourced",
            )
            session.add(sr)

        # Jika user adalah supplier, update stoknya
        supplier = session.execute(
            select(Supplier).where(Supplier.user_id == user_id)
        ).scalar_one_or_none()
        if supplier:
            sc = session.execute(
                select(SupplierCommodity).where(
                    SupplierCommodity.supplier_id == supplier.id,
                    SupplierCommodity.commodity_id == commodity_id,
                )
            ).scalar_one_or_none()
            if sc:
                sc.available_quantity += quantity
                sc.last_updated = datetime.now()

        session.commit()
        session.expunge(report)
        return report


def get_harvest_reports_for_region(
    commodity_name: str, region_name: str
) -> List[dict]:
    with SessionLocal() as session:
        query = (
            select(HarvestReport, Commodity, Region, User)
            .join(Commodity, HarvestReport.commodity_id == Commodity.id)
            .join(Region, HarvestReport.region_id == Region.id)
            .join(User, HarvestReport.user_id == User.id)
            .where(func.lower(Commodity.name).contains(commodity_name.lower()))
            .where(
                func.lower(Region.name).contains(region_name.lower())
                | func.lower(Region.province).contains(region_name.lower())
            )
            .order_by(HarvestReport.created_at.desc())
        )
        rows = session.execute(query).all()
        return [
            {
                "reporter": r.User.full_name,
                "commodity": r.Commodity.name,
                "unit": r.Commodity.unit,
                "region": r.Region.name,
                "province": r.Region.province,
                "quantity": r.HarvestReport.quantity,
                "harvest_date": r.HarvestReport.harvest_date,
                "reported_at": r.HarvestReport.created_at,
            }
            for r in rows
        ]


# ── Transaction ───────────────────────────────────────────────────────────────

def create_transaction(
    supplier_id: int, buyer_id: int, commodity_id: int,
    quantity: float, price_per_unit: float, notes: str = None,
) -> TransactionHistory:
    with SessionLocal() as session:
        tx = TransactionHistory(
            supplier_id=supplier_id, buyer_id=buyer_id,
            commodity_id=commodity_id, quantity=quantity,
            price_per_unit=price_per_unit,
            total_price=quantity * price_per_unit,
            notes=notes,
        )
        session.add(tx)
        session.commit()
        session.expunge(tx)
        return tx


def update_transaction_status(
    tx_id: int, new_status: TransactionStatus
) -> Optional[TransactionHistory]:
    with SessionLocal() as session:
        tx = session.get(TransactionHistory, tx_id)
        if not tx:
            return None
        tx.status = new_status
        if new_status == TransactionStatus.COMPLETED:
            tx.fulfilled = True
        tx.updated_at = datetime.now()
        session.commit()
        session.expunge(tx)
        return tx


def get_user_transactions(user_id: int) -> List[dict]:
    with SessionLocal() as session:
        # Sebagai buyer
        rows = session.execute(
            select(TransactionHistory, Supplier, Commodity)
            .join(Supplier, TransactionHistory.supplier_id == Supplier.id)
            .join(Commodity, TransactionHistory.commodity_id == Commodity.id)
            .where(TransactionHistory.buyer_id == user_id)
            .order_by(TransactionHistory.created_at.desc())
        ).all()
        return [
            {
                "id": r.TransactionHistory.id,
                "supplier_name": r.Supplier.name,
                "commodity": r.Commodity.name,
                "quantity": r.TransactionHistory.quantity,
                "price": r.TransactionHistory.price_per_unit,
                "total": r.TransactionHistory.total_price,
                "status": r.TransactionHistory.status.value,
                "created_at": r.TransactionHistory.created_at,
            }
            for r in rows
        ]


# ── Active Chat ───────────────────────────────────────────────────────────────

def create_active_chat(
    buyer_tg_id: int, seller_tg_id: int, transaction_id: int = None
) -> ActiveChat:
    with SessionLocal() as session:
        chat = ActiveChat(
            buyer_telegram_id=buyer_tg_id,
            seller_telegram_id=seller_tg_id,
            transaction_id=transaction_id,
        )
        session.add(chat)
        session.commit()
        session.expunge(chat)
        return chat


def get_active_chat_for_tg_user(telegram_id: int) -> Optional[dict]:
    with SessionLocal() as session:
        chat = session.execute(
            select(ActiveChat).where(
                ActiveChat.is_active == True,
                (ActiveChat.buyer_telegram_id == telegram_id)
                | (ActiveChat.seller_telegram_id == telegram_id),
            )
        ).scalar_one_or_none()
        if not chat:
            return None

        # Tentukan partner
        if chat.buyer_telegram_id == telegram_id:
            partner_tg_id = chat.seller_telegram_id
            role = "buyer"
        else:
            partner_tg_id = chat.buyer_telegram_id
            role = "seller"

        partner = session.execute(
            select(User).where(User.telegram_id == partner_tg_id)
        ).scalar_one_or_none()

        return {
            "chat_id": chat.id,
            "role": role,
            "partner_telegram_id": partner_tg_id,
            "partner_name": partner.full_name if partner else "User",
        }


def end_active_chat(chat_id: int) -> bool:
    with SessionLocal() as session:
        chat = session.get(ActiveChat, chat_id)
        if not chat:
            return False
        chat.is_active = False
        session.commit()
        return True


# ── LLM Context ───────────────────────────────────────────────────────────────

def get_database_summary() -> dict:
    with SessionLocal() as session:
        total_suppliers = session.execute(
            select(func.count(Supplier.id)).where(Supplier.is_active == True)
        ).scalar() or 0

        rows = session.execute(
            select(SupplierCommodity, Supplier, Commodity, Region)
            .join(Supplier, SupplierCommodity.supplier_id == Supplier.id)
            .join(Commodity, SupplierCommodity.commodity_id == Commodity.id)
            .join(Region, Supplier.region_id == Region.id)
            .where(SupplierCommodity.available_quantity > 0, Supplier.is_active == True)
            .order_by(Commodity.name, SupplierCommodity.price_per_unit)
        ).all()

        lines = [
            f"- {r.Commodity.name}: Rp {r.SupplierCommodity.price_per_unit:,.0f}/{r.Commodity.unit} "
            f"(stok: {r.SupplierCommodity.available_quantity} {r.Commodity.unit}, "
            f"supplier: {r.Supplier.name} [{r.Supplier.supplier_type.value}], "
            f"lokasi: {r.Region.name}, {r.Region.province})"
            for r in rows
        ]

        # Harvest reports terbaru
        recent_reports = session.execute(
            select(HarvestReport, Commodity, Region)
            .join(Commodity, HarvestReport.commodity_id == Commodity.id)
            .join(Region, HarvestReport.region_id == Region.id)
            .order_by(HarvestReport.created_at.desc())
            .limit(10)
        ).all()

        report_lines = [
            f"- {r.Commodity.name}: {r.HarvestReport.quantity} {r.Commodity.unit} "
            f"di {r.Region.name} ({r.Region.province}), "
            f"panen: {r.HarvestReport.harvest_date.strftime('%d/%m/%Y') if r.HarvestReport.harvest_date else 'belum diset'}"
            for r in recent_reports
        ]

        return {
            "total_suppliers": total_suppliers,
            "stocks_info": "\n".join(lines) if lines else "Belum ada stok tersedia.",
            "harvest_reports": "\n".join(report_lines) if report_lines else "Belum ada laporan panen.",
        }
