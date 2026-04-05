"""
Flow Lapor Hasil Panen — sesuai state diagram:
  MainMenu → LaporPanen → InputKomoditasPanen → InputJumlahPanen
  → InputWaktuPanen → ConfirmLaporan → Saved → MainMenu
"""

from datetime import datetime, timedelta

import database as db
from keyboards import back_to_menu, cancel_button, confirm_buttons
from telegram import Update
from telegram.ext import ContextTypes


async def start_lapor(update: Update, context: ContextTypes.DEFAULT_TYPE, entities: dict = None):
    """Entry point — bisa dari tombol menu atau NLP."""
    query = update.callback_query

    # Jika NLP sudah extract semua entities, langsung ke konfirmasi
    if entities and entities.get("commodity") and entities.get("quantity"):
        context.user_data.update({
            "lp_commodity": entities["commodity"],
            "lp_quantity": entities["quantity"],
            "lp_location": entities.get("location"),
            "lp_date_text": entities.get("date"),
        })
        if entities.get("location"):
            context.user_data["state"] = "lp_input_waktu"
            if entities.get("date"):
                context.user_data["state"] = "lp_confirm"
                await _show_confirm(update, context, from_query=bool(query))
                return
            text = (
                f"🌾 *Lapor Panen*\n\n"
                f"Komoditas: {entities['commodity']}\n"
                f"Jumlah: {entities['quantity']}\n"
                f"Lokasi: {entities['location']}\n\n"
                "Kapan waktu panen?\n_(contoh: minggu depan, 20 April 2026)_"
            )
        else:
            context.user_data["state"] = "lp_input_lokasi"
            text = (
                f"🌾 *Lapor Panen*\n\n"
                f"Komoditas: {entities['commodity']}\n"
                f"Jumlah: {entities['quantity']}\n\n"
                "Di daerah mana?\n_(contoh: Garut, Brebes, Karawang)_"
            )
    elif entities and entities.get("commodity"):
        context.user_data["lp_commodity"] = entities["commodity"]
        context.user_data["state"] = "lp_input_jumlah"
        text = (
            f"🌾 *Lapor Panen: {entities['commodity']}*\n\n"
            "Berapa jumlah panen?\n_(contoh: 2 ton, 500 kg)_"
        )
    else:
        context.user_data["state"] = "lp_input_komoditas"
        text = (
            "🌾 *Lapor Hasil Panen*\n\n"
            "Komoditas apa yang dipanen?\n"
            "_(contoh: cabai, beras, bawang merah)_"
        )

    if query:
        await query.answer()
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=cancel_button())
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=cancel_button())


async def handle_input_komoditas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["lp_commodity"] = update.message.text.strip()
    context.user_data["state"] = "lp_input_jumlah"
    await update.message.reply_text(
        f"Komoditas: *{context.user_data['lp_commodity']}* ✅\n\n"
        "Berapa jumlah panen?\n_(contoh: 2, 500)_",
        parse_mode="Markdown", reply_markup=cancel_button(),
    )


async def handle_input_jumlah(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = update.message.text.strip().replace(",", ".").split()[0]
    try:
        qty = float(raw)
        if qty <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text(
            "Jumlah tidak valid. Masukkan angka:", reply_markup=cancel_button()
        )
        return

    context.user_data["lp_quantity"] = qty
    context.user_data["state"] = "lp_input_lokasi"
    await update.message.reply_text(
        f"Jumlah: *{qty}* ✅\n\nDi daerah mana?\n_(contoh: Garut, Brebes)_",
        parse_mode="Markdown", reply_markup=cancel_button(),
    )


async def handle_input_lokasi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["lp_location"] = update.message.text.strip()
    context.user_data["state"] = "lp_input_waktu"
    await update.message.reply_text(
        f"Lokasi: *{context.user_data['lp_location']}* ✅\n\n"
        "Kapan waktu panen?\n"
        "_(contoh: minggu depan, sudah panen, 20 April 2026)_\n"
        "Atau ketik *sekarang* jika sudah dipanen.",
        parse_mode="Markdown", reply_markup=cancel_button(),
    )


async def handle_input_waktu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["lp_date_text"] = update.message.text.strip()
    context.user_data["state"] = "lp_confirm"
    await _show_confirm(update, context, from_query=False)


async def _show_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE, from_query: bool):
    d = context.user_data
    text = (
        "📋 *Konfirmasi Laporan Panen*\n\n"
        f"Komoditas: {d.get('lp_commodity', '-')}\n"
        f"Jumlah: {d.get('lp_quantity', '-')}\n"
        f"Lokasi: {d.get('lp_location', '-')}\n"
        f"Waktu Panen: {d.get('lp_date_text', '-')}\n\n"
        "Apakah data sudah benar?"
    )
    kb = confirm_buttons("lp")
    if from_query:
        await update.callback_query.edit_message_text(
            text, parse_mode="Markdown", reply_markup=kb
        )
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)


async def confirm_laporan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    d = context.user_data
    user = db.get_user(update.effective_user.id)

    # Resolve region
    location_name = d.get("lp_location", "")
    region = db.find_region(location_name)
    if not region:
        region = db.find_region_by_kabupaten(location_name)

    if not region:
        await query.edit_message_text(
            f"⚠️ Lokasi *{location_name}* tidak ditemukan di database.\n"
            "Pastikan nama kota/kabupaten benar dan termasuk dalam area pilot "
            "(Jawa Barat, Jawa Tengah, NTT).",
            parse_mode="Markdown", reply_markup=back_to_menu(),
        )
        _clear_state(context)
        return

    # Resolve commodity
    commodity = db.find_commodity(d.get("lp_commodity", ""))
    if not commodity:
        await query.edit_message_text(
            f"⚠️ Komoditas *{d.get('lp_commodity')}* tidak ditemukan.",
            parse_mode="Markdown", reply_markup=back_to_menu(),
        )
        _clear_state(context)
        return

    # Parse date
    harvest_dt = _parse_date(d.get("lp_date_text", ""))

    # Simpan laporan
    report = db.create_harvest_report(
        user_id=user.id,
        region_id=region.id,
        commodity_id=commodity.id,
        quantity=d.get("lp_quantity", 0),
        harvest_date=harvest_dt,
    )

    _clear_state(context)

    await query.edit_message_text(
        f"✅ *Laporan Panen Berhasil Disimpan!*\n\n"
        f"Komoditas: {commodity.name}\n"
        f"Jumlah: {d.get('lp_quantity', 0)} {commodity.unit}\n"
        f"Lokasi: {region.name}, {region.province}\n"
        f"Waktu: {d.get('lp_date_text', '-')}\n\n"
        "Terima kasih! Data panen ini akan ditampilkan ke pembeli potensial di sekitar Anda.",
        parse_mode="Markdown",
        reply_markup=back_to_menu(),
    )


def _parse_date(text: str) -> datetime:
    """Parse tanggal sederhana dari teks."""
    text = text.lower().strip()
    now = datetime.now()

    if "sekarang" in text or "sudah" in text or "hari ini" in text:
        return now
    elif "besok" in text:
        return now + timedelta(days=1)
    elif "minggu depan" in text:
        return now + timedelta(weeks=1)
    elif "bulan depan" in text:
        return now + timedelta(days=30)
    else:
        # Coba parse format umum
        for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%d %B %Y", "%d %b %Y"):
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                continue
        return now  # fallback


def _clear_state(context):
    for k in list(context.user_data.keys()):
        if k.startswith("lp_"):
            context.user_data.pop(k)
    context.user_data.pop("state", None)
