"""
Flow Cari Komoditas — sesuai state diagram:
  MainMenu → CariKomoditas → InputKomoditas → InputLokasi → InputJumlah
  → ShowRecommendation → HubungkanPenjual → ChatDenganPenjual
"""

import database as db
from keyboards import back_to_menu, cancel_button, supplier_list_keyboard
from telegram import Update
from telegram.ext import ContextTypes


async def start_cari(update: Update, context: ContextTypes.DEFAULT_TYPE, entities: dict = None):
    """Entry point — bisa dari tombol menu atau dari NLP yang sudah extract entities."""
    query = update.callback_query

    # Jika NLP sudah extract semua entities, langsung ke rekomendasi
    if entities and entities.get("commodity") and entities.get("location") and entities.get("quantity"):
        context.user_data.update({
            "state": "cari_show_result",
            "cari_commodity": entities["commodity"],
            "cari_location": entities["location"],
            "cari_quantity": entities["quantity"],
        })
        await _show_recommendations(update, context, from_query=False)
        return

    # Jika NLP extract sebagian, set yang sudah ada
    if entities and entities.get("commodity"):
        context.user_data["cari_commodity"] = entities["commodity"]
        if entities.get("location"):
            context.user_data["cari_location"] = entities["location"]
            context.user_data["state"] = "cari_input_jumlah"
            text = (
                f"🔍 *Cari: {entities['commodity']}*\n"
                f"Lokasi: {entities['location']}\n\n"
                "Berapa jumlah yang dibutuhkan?\n_(contoh: 10 ton, 500 kg)_"
            )
        else:
            context.user_data["state"] = "cari_input_lokasi"
            text = (
                f"🔍 *Cari: {entities['commodity']}*\n\n"
                "Di daerah mana?\n_(contoh: Karawang, Jawa Barat, Brebes)_"
            )
    else:
        context.user_data["state"] = "cari_input_komoditas"
        text = (
            "🔍 *Cari Komoditas*\n\n"
            "Komoditas apa yang kamu cari?\n"
            "_(contoh: beras, cabai, bawang merah)_"
        )

    if query:
        await query.answer()
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=cancel_button())
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=cancel_button())


async def handle_input_komoditas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    commodity = update.message.text.strip()
    context.user_data["cari_commodity"] = commodity
    context.user_data["state"] = "cari_input_lokasi"
    await update.message.reply_text(
        f"Komoditas: *{commodity}* ✅\n\nDi daerah mana?\n_(contoh: Karawang, Bandung, Brebes)_",
        parse_mode="Markdown", reply_markup=cancel_button(),
    )


async def handle_input_lokasi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    location = update.message.text.strip()
    context.user_data["cari_location"] = location
    context.user_data["state"] = "cari_input_jumlah"
    commodity = context.user_data.get("cari_commodity", "")
    await update.message.reply_text(
        f"Komoditas: *{commodity}*\nLokasi: *{location}* ✅\n\n"
        "Berapa jumlah yang dibutuhkan?\n_(contoh: 10, 500)_\n"
        "Atau ketik *semua* untuk lihat semua yang tersedia.",
        parse_mode="Markdown", reply_markup=cancel_button(),
    )


async def handle_input_jumlah(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()
    if text in ("semua", "all", "-"):
        qty = 0
    else:
        raw = text.replace(",", ".").split()[0]
        try:
            qty = float(raw)
        except ValueError:
            await update.message.reply_text(
                "Jumlah tidak valid. Masukkan angka atau ketik *semua*:",
                parse_mode="Markdown", reply_markup=cancel_button(),
            )
            return

    context.user_data["cari_quantity"] = qty
    context.user_data["state"] = "cari_show_result"
    await _show_recommendations(update, context, from_query=False)


async def _show_recommendations(update: Update, context: ContextTypes.DEFAULT_TYPE, from_query: bool):
    commodity = context.user_data.get("cari_commodity", "")
    location = context.user_data.get("cari_location", "")
    quantity = context.user_data.get("cari_quantity", 0)

    results = db.search_suppliers(commodity, location, quantity)

    if not results:
        text = (
            f"❌ Tidak ditemukan supplier *{commodity}* di area *{location}*.\n\n"
            "Coba:\n• Ubah kata kunci komoditas\n• Perluas area pencarian"
        )
        _clear_state(context)
        if from_query:
            await update.callback_query.edit_message_text(
                text, parse_mode="Markdown", reply_markup=back_to_menu()
            )
        else:
            await update.message.reply_text(
                text, parse_mode="Markdown", reply_markup=back_to_menu()
            )
        return

    commodity_name = results[0]["commodity_name"]
    commodity_unit = results[0]["commodity_unit"]
    medals = ["🥇", "🥈", "🥉"]

    text = (
        f"📋 *Rekomendasi Supplier: {commodity_name}*\n"
        f"Area: {location} | Jumlah: {quantity if quantity > 0 else 'semua'} {commodity_unit}\n"
        f"Ditemukan {len(results)} supplier\n\n"
    )

    for i, r in enumerate(results[:5]):
        label = medals[i] if i < 3 else f"{i + 1}."
        text += (
            f"{label} *{r['supplier_name']}* ({r['supplier_type']})\n"
            f"   📍 {r['region_name']}, {r['province']}\n"
            f"   💰 Rp {r['price']:,.0f}/{commodity_unit}\n"
            f"   📦 Stok: {r['quantity']} {commodity_unit}\n"
            f"   ⭐ Skor: {r['score']:.2f}\n\n"
        )

    text += "_Pilih supplier untuk memulai negosiasi:_"

    _clear_state(context)

    if from_query:
        await update.callback_query.edit_message_text(
            text, parse_mode="Markdown",
            reply_markup=supplier_list_keyboard(results),
        )
    else:
        await update.message.reply_text(
            text, parse_mode="Markdown",
            reply_markup=supplier_list_keyboard(results),
        )


async def contact_supplier(
    update: Update, context: ContextTypes.DEFAULT_TYPE,
    supplier_id: int, sc_id: int,
):
    """Hubungkan pembeli dengan supplier — mulai chat relay."""
    query = update.callback_query
    await query.answer()

    buyer = db.get_user(update.effective_user.id)
    supplier = db.get_supplier_by_id(supplier_id)
    if not supplier:
        await query.edit_message_text("❌ Supplier tidak ditemukan.")
        return

    supplier_user = db.get_user(0)
    # Get supplier's telegram_id via user record
    with db.SessionLocal() as session:
        from sqlalchemy import select as sel
        from models import User as UserModel
        su = session.execute(
            sel(UserModel).where(UserModel.id == supplier.user_id)
        ).scalar_one_or_none()
        if not su:
            await query.edit_message_text("❌ User supplier tidak ditemukan.")
            return
        seller_tg_id = su.telegram_id

    # Cek chat aktif
    existing = db.get_active_chat_for_tg_user(update.effective_user.id)
    if existing:
        from keyboards import chat_relay_button
        await query.edit_message_text(
            "⚠️ Kamu sudah memiliki chat aktif. Selesaikan dulu.",
            reply_markup=chat_relay_button(existing["chat_id"]),
        )
        return

    # Buat chat session
    chat = db.create_active_chat(
        buyer_tg_id=update.effective_user.id,
        seller_tg_id=seller_tg_id,
    )

    from keyboards import chat_relay_button
    end_btn = chat_relay_button(chat.id)

    await query.edit_message_text(
        f"💬 *Chat dimulai dengan {supplier.name}!*\n\n"
        "Ketik pesanmu — semua pesan akan diteruskan langsung ke supplier.\n"
        "Diskusikan harga, jumlah, dan pengiriman.\n"
        "Tekan tombol di bawah untuk mengakhiri sesi.",
        parse_mode="Markdown",
        reply_markup=end_btn,
    )

    try:
        await context.bot.send_message(
            chat_id=seller_tg_id,
            text=f"💬 *Chat dimulai dengan {buyer.full_name}!*\n\n"
                 "Pembeli ingin mendiskusikan komoditas.\n"
                 "Ketik pesanmu — semua pesan akan diteruskan.\n"
                 "Tekan tombol di bawah untuk mengakhiri.",
            parse_mode="Markdown",
            reply_markup=end_btn,
        )
    except Exception:
        pass


def _clear_state(context):
    for k in list(context.user_data.keys()):
        if k.startswith("cari_"):
            context.user_data.pop(k)
    context.user_data.pop("state", None)
