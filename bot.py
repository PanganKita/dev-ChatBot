"""
PanganKita Bot — Conversational Interface (Module D)
Sesuai dokumen teknikal: NLP-first, 4 flow utama, chat relay.

Approach:
1. Semua pesan teks dikirim ke NLP Engine untuk intent extraction
2. Berdasarkan intent, di-route ke flow yang tepat
3. Jika user sedang di tengah flow (state), pesan masuk ke step berikutnya
4. Jika user dalam sesi chat relay, pesan di-forward ke partner
"""

import logging

import database as db
from config import BOT_TOKEN
from handlers.cari_komoditas import (
    contact_supplier, handle_input_jumlah as cari_jumlah,
    handle_input_komoditas as cari_komoditas, handle_input_lokasi as cari_lokasi,
    start_cari,
)
from handlers.cek_harga import (
    handle_input_komoditas as ch_komoditas, handle_input_lokasi as ch_lokasi,
    start_cek_harga,
)
from handlers.chat_relay import end_chat_session, relay_message
from handlers.lapor_panen import (
    confirm_laporan, handle_input_jumlah as lp_jumlah,
    handle_input_komoditas as lp_komoditas, handle_input_lokasi as lp_lokasi,
    handle_input_waktu as lp_waktu, start_lapor,
)
from handlers.nlp_engine import extract_intent, get_chat_response
from handlers.prediksi_panen import (
    handle_input_komoditas as pp_komoditas, handle_input_region as pp_region,
    start_prediksi,
)
from keyboards import (
    back_to_menu, llm_stop_button, main_menu, region_keyboard, user_type_keyboard,
)
from models import UserType
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler,
    MessageHandler, filters,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


HELP_TEXT = (
    "🌱 *PanganKita — Bantuan*\n\n"
    "*Perintah:*\n"
    "/start — Mulai bot / menu utama\n"
    "/menu  — Tampilkan menu utama\n"
    "/cari  — Cari komoditas\n"
    "/harga — Cek harga komoditas\n"
    "/lapor — Lapor hasil panen\n"
    "/prediksi — Prediksi panen\n"
    "/tanya — Chat dengan AI\n"
    "/help  — Bantuan ini\n\n"
    "*Fitur Utama:*\n"
    "🔍 *Cari Komoditas* — Cari supplier terdekat & termurah\n"
    "💰 *Cek Harga* — Lihat harga komoditas per daerah\n"
    "🌾 *Lapor Panen* — Laporkan hasil panen kamu\n"
    "📊 *Prediksi Panen* — Estimasi panen berdasarkan data\n\n"
    "*Chat Langsung 💬:*\n"
    "Setelah memilih supplier dari hasil pencarian,\n"
    "kamu bisa langsung chat untuk negosiasi — semua pesan\n"
    "di-relay oleh bot tanpa perlu ganti ruang chat.\n\n"
    "*Tips:*\n"
    "Kamu bisa langsung ketik pesan natural, contoh:\n"
    '• _"Cariin beras 10 ton area Karawang"_\n'
    '• _"Saya mau lapor panen cabai 2 ton di Garut"_\n'
    '• _"Berapa harga cabai di Brebes?"_\n'
    '• _"Kapan panen cabai di Brebes?"_\n\n'
    "Bot akan otomatis memahami maksud kamu!"
)


# ── /start — Welcome + Registration ───────────────────────────────────────────

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_user = update.effective_user
    user = db.get_user(tg_user.id)

    if not user:
        user = db.upsert_user(tg_user.id, tg_user.username or "", tg_user.first_name or "User")

    if user.registered:
        await update.message.reply_text(
            f"Selamat datang kembali, *{user.full_name}*! 🌱\n\n"
            "Apa yang ingin kamu lakukan?",
            parse_mode="Markdown",
            reply_markup=main_menu(),
        )
        return

    # Registration flow
    await update.message.reply_text(
        "🌱 *Selamat datang di PanganKita!*\n\n"
        "Platform data distribusi dan panen yang menghubungkan\n"
        "petani, tengkulak, pedagang, dan lembaga di Indonesia.\n\n"
        "Kamu bergabung sebagai apa?",
        parse_mode="Markdown",
        reply_markup=user_type_keyboard(),
    )
    context.user_data["state"] = "reg_type"


async def handle_reg_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    type_map = {
        "reg_petani": UserType.PETANI,
        "reg_tengkulak": UserType.TENGKULAK,
        "reg_pedagang": UserType.PEDAGANG,
        "reg_lembaga": UserType.LEMBAGA,
    }
    user_type = type_map.get(query.data)
    if not user_type:
        return

    context.user_data["reg_user_type"] = user_type

    regions = db.get_all_regions()
    context.user_data["state"] = "reg_region"

    await query.edit_message_text(
        f"Tipe: *{user_type.value.title()}* ✅\n\nPilih lokasi/daerah kamu:",
        parse_mode="Markdown",
        reply_markup=region_keyboard(regions),
    )


async def handle_reg_region(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    region_id = int(query.data.split("_")[2])
    user_type = context.user_data.get("reg_user_type")

    tg_user = update.effective_user
    db.register_user(tg_user.id, user_type, region_id)

    # Jika petani/tengkulak, buat supplier profile
    user = db.get_user(tg_user.id)
    if user_type in (UserType.PETANI, UserType.TENGKULAK):
        existing_supplier = db.get_supplier_by_user(user.id)
        if not existing_supplier:
            db.create_supplier(
                user_id=user.id,
                name=user.full_name,
                supplier_type=user_type,
                region_id=region_id,
            )

    region = db.get_region_by_id(region_id)
    context.user_data.clear()

    await query.edit_message_text(
        f"✅ *Registrasi berhasil!*\n\n"
        f"Nama: {user.full_name}\n"
        f"Tipe: {user_type.value.title()}\n"
        f"Lokasi: {region.name if region else '-'}, {region.province if region else ''}\n\n"
        "Selamat menggunakan PanganKita!",
        parse_mode="Markdown",
        reply_markup=main_menu(),
    )


async def handle_reg_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    page = int(query.data.split("_")[2])
    regions = db.get_all_regions()
    await query.edit_message_reply_markup(reply_markup=region_keyboard(regions, page))


# ── Menu commands ──────────────────────────────────────────────────────────────

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "🌱 *Menu Utama PanganKita*\n\nPilih fitur atau ketik pesan langsung:",
        parse_mode="Markdown",
        reply_markup=main_menu(),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT, parse_mode="Markdown")


# ── Shortcut commands ─────────────────────────────────────────────────────────

async def cari_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await start_cari(update, context)


async def harga_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await start_cek_harga(update, context)


async def lapor_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await start_lapor(update, context)


async def prediksi_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await start_prediksi(update, context)


async def tanya_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["state"] = "llm_chat"
    await update.message.reply_text(
        "🤖 *Chat dengan AI PanganKita*\n\n"
        "Tanyakan apa saja tentang komoditas, harga, atau pertanian.\n"
        "Ketik pesanmu:",
        parse_mode="Markdown",
        reply_markup=llm_stop_button(),
    )


# ── Callback router ────────────────────────────────────────────────────────────

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    if data == "noop":
        await query.answer()
        return

    # ── Navigation ─────────────────────────────────────────────
    if data == "back_main" or data == "cancel":
        context.user_data.clear()
        await query.answer()
        await query.edit_message_text(
            "🌱 *Menu Utama PanganKita*\n\nPilih fitur atau ketik pesan langsung:",
            parse_mode="Markdown",
            reply_markup=main_menu(),
        )
        return

    # ── Registration ───────────────────────────────────────────
    if data.startswith("reg_") and data in ("reg_petani", "reg_tengkulak", "reg_pedagang", "reg_lembaga"):
        await handle_reg_type(update, context)
        return
    if data.startswith("reg_region_"):
        await handle_reg_region(update, context)
        return
    if data.startswith("reg_rpage_"):
        await handle_reg_page(update, context)
        return

    # ── 4 Main Menu Flows ─────────────────────────────────────
    if data == "cari_komoditas":
        await query.answer()
        context.user_data.clear()
        await start_cari(update, context)
        return

    if data == "cek_harga":
        await query.answer()
        context.user_data.clear()
        await start_cek_harga(update, context)
        return

    if data == "lapor_panen":
        await query.answer()
        context.user_data.clear()
        await start_lapor(update, context)
        return

    if data == "prediksi_panen":
        await query.answer()
        context.user_data.clear()
        await start_prediksi(update, context)
        return

    # ── LLM Chat ──────────────────────────────────────────────
    if data == "llm_chat":
        await query.answer()
        context.user_data["state"] = "llm_chat"
        await query.edit_message_text(
            "🤖 *Chat dengan AI PanganKita*\n\n"
            "Tanyakan apa saja. Ketik pesanmu:",
            parse_mode="Markdown",
            reply_markup=llm_stop_button(),
        )
        return

    if data == "stop_llm":
        await query.answer()
        context.user_data.pop("state", None)
        await query.edit_message_text(
            "Chat AI selesai.", reply_markup=main_menu()
        )
        return

    # ── Supplier Contact ──────────────────────────────────────
    if data.startswith("contact_"):
        parts = data.split("_")
        await contact_supplier(update, context, int(parts[1]), int(parts[2]))
        return

    # ── Chat Relay ────────────────────────────────────────────
    if data.startswith("end_chat_"):
        await end_chat_session(update, context, int(data.split("_")[2]))
        return

    # ── Lapor Panen Confirm ───────────────────────────────────
    if data == "lp_confirm":
        await confirm_laporan(update, context)
        return

    await query.answer("Perintah tidak dikenal.")


# ── Text handler — NLP-first routing ──────────────────────────────────────────

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = db.get_user(update.effective_user.id)
    if not user:
        db.upsert_user(
            update.effective_user.id,
            update.effective_user.username or "",
            update.effective_user.first_name or "User",
        )
        await update.message.reply_text(
            "Ketik /start untuk mendaftar terlebih dahulu."
        )
        return

    # ── Prioritas 1: Chat relay aktif ──────────────────────────
    active_chat = db.get_active_chat_for_tg_user(update.effective_user.id)
    if active_chat:
        await relay_message(update, context, active_chat)
        return

    # ── Prioritas 2: State machine (user di tengah flow) ───────
    state = context.user_data.get("state")

    # Cari Komoditas flow
    if state == "cari_input_komoditas":
        await cari_komoditas(update, context)
        return
    if state == "cari_input_lokasi":
        await cari_lokasi(update, context)
        return
    if state == "cari_input_jumlah":
        await cari_jumlah(update, context)
        return

    # Lapor Panen flow
    if state == "lp_input_komoditas":
        await lp_komoditas(update, context)
        return
    if state == "lp_input_jumlah":
        await lp_jumlah(update, context)
        return
    if state == "lp_input_lokasi":
        await lp_lokasi(update, context)
        return
    if state == "lp_input_waktu":
        await lp_waktu(update, context)
        return

    # Cek Harga flow
    if state == "ch_input_komoditas":
        await ch_komoditas(update, context)
        return
    if state == "ch_input_lokasi":
        await ch_lokasi(update, context)
        return

    # Prediksi Panen flow
    if state == "pp_input_komoditas":
        await pp_komoditas(update, context)
        return
    if state == "pp_input_region":
        await pp_region(update, context)
        return

    # LLM Chat mode
    if state == "llm_chat":
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id, action=ChatAction.TYPING,
        )
        response = await get_chat_response(update.message.text)
        await update.message.reply_text(
            f"🤖 {response}", reply_markup=llm_stop_button()
        )
        return

    # ── Prioritas 3: NLP intent extraction ─────────────────────
    # Kirim ke LLM untuk klasifikasi intent
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action=ChatAction.TYPING,
    )

    try:
        parsed = await extract_intent(update.message.text)
    except Exception:
        # Fallback: tampilkan menu
        await update.message.reply_text(
            "Maaf, saya tidak mengerti. Gunakan menu di bawah:",
            reply_markup=main_menu(),
        )
        return

    intent = parsed.get("intent", "chat_umum")

    if intent == "cari_komoditas":
        await start_cari(update, context, entities=parsed)
    elif intent == "lapor_panen":
        await start_lapor(update, context, entities=parsed)
    elif intent == "cek_harga":
        await start_cek_harga(update, context, entities=parsed)
    elif intent == "prediksi_panen":
        await start_prediksi(update, context, entities=parsed)
    elif intent == "chat_umum":
        response = await get_chat_response(update.message.text)
        await update.message.reply_text(
            f"🤖 {response}\n\n_Gunakan menu untuk fitur spesifik:_",
            parse_mode="Markdown",
            reply_markup=main_menu(),
        )
    else:
        await update.message.reply_text(
            "Gunakan menu di bawah:", reply_markup=main_menu()
        )


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN belum diset di file .env")

    db.init_db()
    logger.info("Database PanganKita siap.")

    app = Application.builder().token(BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("menu", menu_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("cari", cari_command))
    app.add_handler(CommandHandler("harga", harga_command))
    app.add_handler(CommandHandler("lapor", lapor_command))
    app.add_handler(CommandHandler("prediksi", prediksi_command))
    app.add_handler(CommandHandler("tanya", tanya_command))

    # Callbacks
    app.add_handler(CallbackQueryHandler(handle_callback))

    # Text — NLP-first
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("Bot PanganKita sedang berjalan... Tekan Ctrl+C untuk berhenti.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
