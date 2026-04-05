"""
Chat Relay — sesuai state diagram:
  ShowRecommendation → HubungkanPenjual → ChatDenganPenjual
  → Negosiasi → Transaksi → SelesaiTransaksi → KembaliKeBot → MainMenu

Bot menjadi jembatan: semua pesan di-relay dua arah.
"""

import database as db
from keyboards import back_to_menu, chat_relay_button
from telegram import Update
from telegram.ext import ContextTypes


async def relay_message(update: Update, context: ContextTypes.DEFAULT_TYPE, active_chat: dict):
    """Forward pesan teks dari satu pihak ke pihak lain."""
    message_text = update.message.text
    sender_name = update.effective_user.first_name or "User"
    partner_tg_id = active_chat["partner_telegram_id"]
    chat_id = active_chat["chat_id"]

    if not partner_tg_id:
        await update.message.reply_text(
            "⚠️ Tidak dapat menghubungi lawan bicara.",
            reply_markup=chat_relay_button(chat_id),
        )
        return

    try:
        await context.bot.send_message(
            chat_id=partner_tg_id,
            text=f"💬 *{sender_name}*: {message_text}",
            parse_mode="Markdown",
            reply_markup=chat_relay_button(chat_id),
        )
    except Exception as e:
        await update.message.reply_text(
            f"⚠️ Pesan gagal dikirim: {str(e)[:80]}"
        )


async def end_chat_session(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """Akhiri sesi relay, beri tahu kedua pihak, kembali ke mode bot."""
    query = update.callback_query
    await query.answer()

    # Ambil info chat
    active = db.get_active_chat_for_tg_user(update.effective_user.id)
    if not active or active["chat_id"] != chat_id:
        await query.edit_message_text(
            "Sesi chat sudah berakhir.", reply_markup=back_to_menu()
        )
        return

    partner_tg_id = active["partner_telegram_id"]
    ender_name = update.effective_user.first_name or "User"

    db.end_active_chat(chat_id)

    # Notifikasi yang mengakhiri
    await query.edit_message_text(
        f"🔴 *Chat diakhiri.*\nKembali ke menu utama.",
        parse_mode="Markdown",
        reply_markup=back_to_menu(),
    )

    # Notifikasi partner
    if partner_tg_id:
        try:
            await context.bot.send_message(
                chat_id=partner_tg_id,
                text=f"🔴 *Chat telah diakhiri oleh {ender_name}.*\nKembali ke menu utama.",
                parse_mode="Markdown",
                reply_markup=back_to_menu(),
            )
        except Exception:
            pass
