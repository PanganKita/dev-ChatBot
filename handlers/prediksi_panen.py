"""
Flow Prediksi Panen — sesuai state diagram:
  MainMenu → PrediksiPanen → InputKomoditasPrediksi → InputRegionPrediksi
  → ShowPrediksi → MainMenu

Di produksi, ini memanggil Prediction Service (Module B).
Untuk MVP/pilot, kita menggunakan LLM + data historis laporan panen.
"""

from handlers.nlp_engine import get_prediction_response
from keyboards import back_to_menu, cancel_button
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes


async def start_prediksi(update: Update, context: ContextTypes.DEFAULT_TYPE, entities: dict = None):
    query = update.callback_query

    if entities and entities.get("commodity"):
        context.user_data["pp_commodity"] = entities["commodity"]
        if entities.get("location"):
            context.user_data["pp_region"] = entities["location"]
            await _show_prediksi(update, context, from_query=bool(query))
            return
        context.user_data["state"] = "pp_input_region"
        text = (
            f"📊 *Prediksi Panen: {entities['commodity']}*\n\n"
            "Di region/daerah mana?\n_(contoh: Brebes, Jawa Barat, Garut)_"
        )
    else:
        context.user_data["state"] = "pp_input_komoditas"
        text = (
            "📊 *Prediksi Panen*\n\n"
            "Komoditas apa yang ingin diprediksi?\n"
            "_(contoh: cabai, beras, bawang merah)_"
        )

    if query:
        await query.answer()
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=cancel_button())
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=cancel_button())


async def handle_input_komoditas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["pp_commodity"] = update.message.text.strip()
    context.user_data["state"] = "pp_input_region"
    await update.message.reply_text(
        f"Komoditas: *{context.user_data['pp_commodity']}* ✅\n\n"
        "Di region mana?\n_(contoh: Brebes, Jawa Barat, Garut)_",
        parse_mode="Markdown", reply_markup=cancel_button(),
    )


async def handle_input_region(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["pp_region"] = update.message.text.strip()
    await _show_prediksi(update, context, from_query=False)


async def _show_prediksi(update: Update, context: ContextTypes.DEFAULT_TYPE, from_query: bool):
    commodity = context.user_data.get("pp_commodity", "")
    region = context.user_data.get("pp_region", "")
    _clear_state(context)

    # Kirim typing indicator
    if not from_query:
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id, action=ChatAction.TYPING
        )

    try:
        prediction = await get_prediction_response(commodity, region)
    except Exception as e:
        prediction = (
            f"Layanan prediksi sedang tidak tersedia.\n"
            f"Error: {str(e)[:100]}\n\n"
            "Pastikan layanan LLM (Ollama/dll) sudah berjalan."
        )

    text = (
        f"📊 *Prediksi Panen: {commodity} di {region}*\n\n"
        f"{prediction}"
    )

    if from_query:
        await update.callback_query.edit_message_text(
            text, parse_mode="Markdown", reply_markup=back_to_menu()
        )
    else:
        await update.message.reply_text(
            text, parse_mode="Markdown", reply_markup=back_to_menu()
        )


def _clear_state(context):
    for k in list(context.user_data.keys()):
        if k.startswith("pp_"):
            context.user_data.pop(k)
    context.user_data.pop("state", None)
