"""
PanganKita — Keyboards
4 menu utama sesuai state diagram Module D.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu() -> InlineKeyboardMarkup:
    """Menu utama — 4 fitur sesuai state diagram dokumen."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔍 Cari Komoditas", callback_data="cari_komoditas"),
            InlineKeyboardButton("💰 Cek Harga", callback_data="cek_harga"),
        ],
        [
            InlineKeyboardButton("🌾 Lapor Hasil Panen", callback_data="lapor_panen"),
            InlineKeyboardButton("📊 Prediksi Panen", callback_data="prediksi_panen"),
        ],
        [
            InlineKeyboardButton("🤖 Chat AI", callback_data="llm_chat"),
        ],
    ])


def user_type_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🌾 Petani", callback_data="reg_petani"),
            InlineKeyboardButton("🚛 Tengkulak", callback_data="reg_tengkulak"),
        ],
        [
            InlineKeyboardButton("🏪 Pedagang", callback_data="reg_pedagang"),
            InlineKeyboardButton("🏛️ Lembaga", callback_data="reg_lembaga"),
        ],
    ])


def region_keyboard(regions: list, page: int = 0, per_page: int = 10) -> InlineKeyboardMarkup:
    total = len(regions)
    start = page * per_page
    end = min(start + per_page, total)
    page_items = regions[start:end]
    total_pages = max(1, (total - 1) // per_page + 1)

    keyboard = []
    for i in range(0, len(page_items), 2):
        row = [
            InlineKeyboardButton(r.name, callback_data=f"reg_region_{r.id}")
            for r in page_items[i: i + 2]
        ]
        keyboard.append(row)

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️", callback_data=f"reg_rpage_{page - 1}"))
    nav.append(InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="noop"))
    if end < total:
        nav.append(InlineKeyboardButton("▶️", callback_data=f"reg_rpage_{page + 1}"))
    if nav:
        keyboard.append(nav)

    return InlineKeyboardMarkup(keyboard)


def cancel_button() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Batal", callback_data="cancel")]
    ])


def back_to_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("◀️ Menu Utama", callback_data="back_main")]
    ])


def supplier_list_keyboard(suppliers: list) -> InlineKeyboardMarkup:
    """Tombol untuk memilih supplier dari hasil rekomendasi."""
    keyboard = []
    for i, s in enumerate(suppliers[:5]):
        keyboard.append([InlineKeyboardButton(
            f"💬 {s['supplier_name']} — Rp {s['price']:,.0f}/{s['commodity_unit']}",
            callback_data=f"contact_{s['supplier_id']}_{s['sc_id']}",
        )])
    keyboard.append([InlineKeyboardButton("◀️ Menu Utama", callback_data="back_main")])
    return InlineKeyboardMarkup(keyboard)


def confirm_buttons(prefix: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Konfirmasi", callback_data=f"{prefix}_confirm"),
            InlineKeyboardButton("❌ Batal", callback_data="cancel"),
        ],
    ])


def chat_relay_button(chat_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔴 Akhiri Chat", callback_data=f"end_chat_{chat_id}")]
    ])


def llm_stop_button() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔴 Keluar Chat AI", callback_data="stop_llm")]
    ])
