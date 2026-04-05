"""
PanganKita — NLP Engine
Menggunakan LLM untuk intent classification dan entity extraction.
Sesuai dokumen teknikal: Chatbot NLP Service → parse intent & entities.

Intents sesuai state diagram Module D:
  - cari_komoditas  : user ingin mencari/beli komoditas
  - lapor_panen     : petani ingin melaporkan hasil panen
  - cek_harga       : user ingin cek harga komoditas
  - prediksi_panen  : user ingin melihat prediksi panen
  - chat_umum       : percakapan umum / tanya jawab
"""

import json
import logging

from config import (
    LLM_BACKEND, MODEL_PATH,
    OLLAMA_HOST, OLLAMA_MODEL,
    OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL,
)

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """Kamu adalah NLP parser untuk platform PanganKita.
Tugasmu: dari pesan user, ekstrak intent dan entities dalam format JSON.

Intents yang tersedia:
- cari_komoditas: user ingin mencari atau membeli komoditas dari supplier
- lapor_panen: petani ingin melaporkan hasil panen (komoditas, jumlah, lokasi, waktu)
- cek_harga: user ingin mengecek harga komoditas di suatu lokasi
- prediksi_panen: user ingin melihat prediksi panen di suatu region
- chat_umum: percakapan umum, sapaan, atau pertanyaan lainnya

Entities yang mungkin:
- commodity: nama komoditas (beras, cabai, bawang merah, dll)
- location: nama lokasi/kota/kabupaten/provinsi
- quantity: jumlah (angka + satuan, contoh: "2 ton", "500 kg")
- date: tanggal atau waktu relatif ("minggu depan", "April 2026")

PENTING:
- Jawab HANYA dalam JSON, tanpa penjelasan
- Jika entity tidak ada, isi null
- Quantity harus angka (konversi ke float, dalam satuan asli)

Format output:
{"intent": "...", "commodity": "...", "location": "...", "quantity": ..., "date": "..."}

Contoh:
User: "Saya mau lapor panen cabai 2 ton minggu depan di Garut"
Output: {"intent": "lapor_panen", "commodity": "cabai", "location": "Garut", "quantity": 2.0, "date": "minggu depan"}

User: "Cariin beras 10 ton area Karawang"
Output: {"intent": "cari_komoditas", "commodity": "beras", "location": "Karawang", "quantity": 10.0, "date": null}

User: "Berapa harga cabai di Brebes?"
Output: {"intent": "cek_harga", "commodity": "cabai", "location": "Brebes", "quantity": null, "date": null}

User: "Kapan panen cabai di Brebes?"
Output: {"intent": "prediksi_panen", "commodity": "cabai", "location": "Brebes", "quantity": null, "date": null}

User: "Halo"
Output: {"intent": "chat_umum", "commodity": null, "location": null, "quantity": null, "date": null}
"""


async def extract_intent(user_message: str) -> dict:
    """
    Ekstrak intent dan entities dari pesan user menggunakan LLM.
    Returns dict: {intent, commodity, location, quantity, date}
    Fallback ke chat_umum jika gagal parse.
    """
    messages = [
        {"role": "system", "content": EXTRACTION_PROMPT},
        {"role": "user", "content": user_message},
    ]

    try:
        raw = await _call_llm(messages)
        # Cari JSON dalam response
        raw = raw.strip()
        # Tangani kasus di mana LLM membungkus dengan ```json
        if "```" in raw:
            start = raw.find("{")
            end = raw.rfind("}") + 1
            raw = raw[start:end]
        parsed = json.loads(raw)
        # Validate intent
        valid_intents = {
            "cari_komoditas", "lapor_panen", "cek_harga",
            "prediksi_panen", "chat_umum",
        }
        if parsed.get("intent") not in valid_intents:
            parsed["intent"] = "chat_umum"
        return parsed
    except (json.JSONDecodeError, Exception) as e:
        logger.warning(f"NLP parse gagal: {e}")
        return {
            "intent": "chat_umum",
            "commodity": None,
            "location": None,
            "quantity": None,
            "date": None,
        }


async def get_chat_response(user_message: str, context_data: str = "") -> str:
    """
    Response untuk chat_umum — percakapan bebas dengan konteks data PanganKita.
    """
    import database as db
    summary = db.get_database_summary()

    system = (
        "Kamu adalah asisten AI untuk platform PanganKita, "
        "platform data distribusi dan panen yang menghubungkan "
        "petani, tengkulak, pedagang, dan lembaga di Indonesia.\n\n"
        f"Data stok saat ini:\n{summary['stocks_info']}\n\n"
        f"Laporan panen terbaru:\n{summary['harvest_reports']}\n\n"
        f"Total supplier aktif: {summary['total_suppliers']}\n\n"
        f"{context_data}\n\n"
        "Tugasmu:\n"
        "1. Jawab pertanyaan tentang harga, ketersediaan, dan prediksi komoditas\n"
        "2. Bantu user menggunakan platform (cari komoditas, lapor panen, cek harga)\n"
        "3. Berikan saran pertanian jika ditanya\n\n"
        "Jawab dalam Bahasa Indonesia, singkat dan ramah. "
        "Jika user ingin melakukan aksi (cari/lapor/cek), sarankan gunakan menu utama."
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_message},
    ]
    try:
        return await _call_llm(messages)
    except Exception as e:
        return f"Maaf, layanan AI sedang tidak tersedia: {str(e)[:100]}"


async def get_prediction_response(commodity: str, region: str) -> str:
    """
    Prediksi panen — LLM memberi estimasi berdasarkan data kontekstual.
    Di produksi, ini akan memanggil Prediction Service (Module B).
    """
    import database as db
    reports = db.get_harvest_reports_for_region(commodity, region)
    summary = db.get_database_summary()

    report_text = ""
    if reports:
        for r in reports[:5]:
            report_text += (
                f"- {r['commodity']}: {r['quantity']} {r['unit']} di {r['region']}, "
                f"dilaporkan {r['reported_at'].strftime('%d/%m/%Y')}\n"
            )

    system = (
        "Kamu adalah Harvest Prediction Engine untuk PanganKita.\n"
        "Berikan PREDIKSI realistis berdasarkan data yang ada.\n\n"
        f"Data stok saat ini:\n{summary['stocks_info']}\n\n"
        f"Laporan panen terkait {commodity} di {region}:\n"
        f"{report_text if report_text else 'Belum ada data laporan.'}\n\n"
        "Tugasmu: Berikan prediksi meliputi:\n"
        "1. Estimasi waktu panen berikutnya\n"
        "2. Estimasi produksi (ton)\n"
        "3. Waktu optimal untuk membeli\n"
        "4. Faktor yang mempengaruhi (cuaca, musim, dll)\n\n"
        "Jika data kurang, berikan estimasi berdasarkan pola umum pertanian Indonesia. "
        "Sebutkan bahwa ini adalah estimasi dan perlu validasi data lapangan. "
        "Jawab dalam Bahasa Indonesia, format rapi."
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": f"Prediksi panen {commodity} di {region}"},
    ]
    try:
        return await _call_llm(messages)
    except Exception as e:
        return f"Maaf, layanan prediksi sedang tidak tersedia: {str(e)[:100]}"


# ── LLM Call dispatcher ────────────────────────────────────────────────────────

async def _call_llm(messages: list) -> str:
    if LLM_BACKEND == "openai_compatible":
        return await _call_openai(messages)
    elif LLM_BACKEND == "llamacpp":
        return await _call_llamacpp(messages)
    else:
        return await _call_ollama(messages)


async def _call_ollama(messages: list) -> str:
    import ollama
    client = ollama.AsyncClient(host=OLLAMA_HOST)
    response = await client.chat(
        model=OLLAMA_MODEL, messages=messages,
        options={"temperature": 0.3, "num_predict": 512},
    )
    return response.message.content


async def _call_openai(messages: list) -> str:
    from openai import AsyncOpenAI
    client = AsyncOpenAI(base_url=OPENAI_BASE_URL, api_key=OPENAI_API_KEY or "none")
    response = await client.chat.completions.create(
        model=OPENAI_MODEL, messages=messages,
        max_tokens=512, temperature=0.3,
    )
    return response.choices[0].message.content


async def _call_llamacpp(messages: list) -> str:
    import asyncio
    from llama_cpp import Llama

    global _llama_instance
    if "_llama_instance" not in globals() or globals().get("_llama_instance") is None:
        globals()["_llama_instance"] = Llama(
            model_path=MODEL_PATH, n_ctx=2048, n_threads=4, verbose=False,
        )

    def _sync():
        resp = globals()["_llama_instance"].create_chat_completion(
            messages=messages, max_tokens=512, temperature=0.3,
        )
        return resp["choices"][0]["message"]["content"]

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _sync)
