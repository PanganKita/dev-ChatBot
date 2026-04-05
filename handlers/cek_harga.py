"""
Flow Cek Harga — sesuai state diagram:
  MainMenu → CekHarga → InputKomoditasHarga → InputLokasiHarga
  → ShowHarga → MainMenu
"""

import database as db
from keyboards import back_to_menu, cancel_button
from telegram import Update
from telegram.ext import ContextTypes


async def start_cek_harga(update: Update, context: ContextTypes.DEFAULT_TYPE, entities: dict = None):
    query = update.callback_query

    # NLP sudah extract entities
    if entities and entities.get("commodity"):
        context.user_data["ch_commodity"] = entities["commodity"]
        if entities.get("location"):
            context.user_data["ch_location"] = entities["location"]
            await _show_harga(update, context, from_query=bool(query))
            return
        context.user_data["state"] = "ch_input_lokasi"
        text = (
            f"💰 *Cek Harga: {entities['commodity']}*\n\n"
            "Di daerah mana?\n_(contoh: Brebes, Jawa Barat, Karawang)_\n"
            "Atau ketik *semua* untuk semua lokasi."
        )
    else:
        context.user_data["state"] = "ch_input_komoditas"
        text = (
            "💰 *Cek Harga Komoditas*\n\n"
            "Komoditas apa yang ingin dicek?\n"
            "_(contoh: cabai, beras, bawang merah)_"
        )

    if query:
        await query.answer()
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=cancel_button())
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=cancel_button())


async def handle_input_komoditas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["ch_commodity"] = update.message.text.strip()
    context.user_data["state"] = "ch_input_lokasi"
    await update.message.reply_text(
        f"Komoditas: *{context.user_data['ch_commodity']}* ✅\n\n"
        "Di daerah mana?\n_(contoh: Brebes, Jawa Barat)_\n"
        "Atau ketik *semua* untuk semua lokasi.",
        parse_mode="Markdown", reply_markup=cancel_button(),
    )


async def handle_input_lokasi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    location = None if text.lower() in ("semua", "all", "-") else text
    context.user_data["ch_location"] = location
    await _show_harga(update, context, from_query=False)


async def _show_harga(update: Update, context: ContextTypes.DEFAULT_TYPE, from_query: bool):
    commodity = context.user_data.get("ch_commodity", "")
    location = context.user_data.get("ch_location")

    results = db.get_price_info(commodity, location)
    _clear_state(context)

    if not results:
        loc_text = f" di *{location}*" if location else ""
        text = f"❌ Tidak ada data harga *{commodity}*{loc_text} saat ini."
        kb = back_to_menu()
    else:
        loc_text = f" — {location}" if location else ""
        text = f"💰 *Harga {results[0]['commodity']}{loc_text}*\n\n"

        # Rangkuman
        prices = [r["price"] for r in results]
        text += (
            f"📊 *Rangkuman:*\n"
            f"  Termurah: Rp {min(prices):,.0f}/{results[0]['unit']}\n"
            f"  Termahal: Rp {max(prices):,.0f}/{results[0]['unit']}\n"
            f"  Rata-rata: Rp {sum(prices) / len(prices):,.0f}/{results[0]['unit']}\n"
            f"  Jumlah supplier: {len(results)}\n\n"
        )

        text += "*Detail per supplier:*\n"
        for i, r in enumerate(results[:10]):
            text += (
                f"{i + 1}. *{r['supplier_name']}* — {r['region']}, {r['province']}\n"
                f"   💰 Rp {r['price']:,.0f}/{r['unit']} "
                f"| 📦 {r['quantity']} {r['unit']}\n"
            )

        kb = back_to_menu()

    if from_query:
        await update.callback_query.edit_message_text(
            text, parse_mode="Markdown", reply_markup=kb
        )
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)


def _clear_state(context):
    for k in list(context.user_data.keys()):
        if k.startswith("ch_"):
            context.user_data.pop(k)
    context.user_data.pop("state", None)
