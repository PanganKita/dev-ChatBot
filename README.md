# 🌾 PanganKita - ChatBot v1.0
---

## Mengapa PanganKita?

Indonesia menghadapi tiga masalah utama di rantai pasok pangan:

| Masalah | Dampak |
|---------|--------|
| Rantai distribusi terlalu panjang (petani → tengkulak → pedagang besar → pengecer) | Margin petani tertekan, harga konsumen membengkak |
| Tidak ada sumber informasi terpusat untuk data produksi per wilayah | Keputusan pengadaan buruk, blind spot dalam perencanaan |
| Mismatch spasial-temporal — surplus di satu daerah, defisit di daerah lain | Ketahanan pangan lokal terganggu, volatilitas harga |

**PanganKita bukan marketplace.** PanganKita adalah *data intelligence platform* yang **memberdayakan** seluruh pelaku rantai pasok — termasuk tengkulak — dengan informasi yang tepat untuk membuat keputusan yang lebih baik.

---

## Fitur Utama

### 🔍 Cari Komoditas
Cari supplier terdekat dan termurah dengan sistem **scoring 4 faktor**:
```
Score = 0.35×Harga + 0.25×Jarak + 0.20×Reliabilitas + 0.20×Ketersediaan
```

### 💰 Cek Harga
Lihat harga komoditas real-time per daerah — rangkuman min/max/rata-rata dari semua supplier aktif.

### 🌾 Lapor Hasil Panen
Petani melaporkan panen via chat natural. Data otomatis masuk ke database dan ditampilkan ke pembeli potensial.

### 📊 Prediksi Panen
Estimasi waktu panen, produksi, dan window pembelian optimal berdasarkan data historis dan AI.

### 💬 Chat Relay
Setelah memilih supplier, pembeli bisa langsung chat untuk negosiasi — semua pesan di-relay oleh bot, tanpa perlu bertukar kontak atau pindah ruang chat.

### 🤖 NLP-First Interface
User tidak perlu navigasi menu. Cukup ketik pesan natural:

| User | Input | Bot Memahami |
|------|-------|-------------|
| Petani | *"Saya mau lapor panen cabai 2 ton minggu depan di Garut"* | → Langsung ke konfirmasi laporan |
| Tengkulak | *"Cariin beras 10 ton area Karawang"* | → Tampilkan ranked supplier list |
| Pedagang | *"Kapan panen cabai di Brebes?"* | → Tampilkan prediksi panen |
| Lembaga | *"Berapa harga beras di Jawa Tengah?"* | → Tampilkan rangkuman harga |

---

## Commands

| Command | Fungsi |
|---------|--------|
| `/start` | Daftar atau tampilkan menu utama |
| `/menu` | Kembali ke menu utama |
| `/cari` | Cari komoditas & supplier |
| `/harga` | Cek harga komoditas |
| `/lapor` | Lapor hasil panen |
| `/prediksi` | Prediksi panen |
| `/tanya` | Chat bebas dengan AI |
| `/help` | Tampilkan bantuan |

---
