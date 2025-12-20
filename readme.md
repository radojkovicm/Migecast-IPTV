# 📺 MigeCast IPTV

**Profesionalna Windows desktop IPTV aplikacija**

MigeCast IPTV je moderna, stabilna i optimizovana IPTV aplikacija dizajnirana za Windows 11, sa fokusom na jednostavnost korišćenja i profesionalan izgled.

---

## ✨ Karakteristike

### 🎯 Osnovne Funkcionalnosti
- **M3U i Xtream Codes podrška** - Učitavanje playlista iz lokalnih M3U fajlova ili Xtream Codes API-ja
- **Live TV kanali** - Brza navigacija, automatsko grupisanje po kategorijama, EPG integracija
- **Video on Demand (VOD)** - Filmovi i serije sa posterima, IMDB ocenama, opisima
- **Timeshift/Catch-up** - Gledanje programa unazad (ako kanal podržava)
- **Favorites** - Dodavanje omiljenih kanala i VOD sadržaja
- **Watched tracking** - Praćenje gledanih filmova i serija

### 🎬 Video Player
- **LibVLC engine** - Stabilna reprodukcija sa hardverskom akceleracijom
- **Zero buffering** - Optimizovan buffer za glatko gledanje
- **Auto-reconnect** - Automatsko ponovno povezivanje pri gubitku signala (do 3 pokušaja)
- **Subtitle support** - Podrška za titlove ako stream sadrži

### 🖥️ Korisnički Interfejs
- **Senior-friendly dizajn** - Veliki, čitljivi elementi (minimum 16pt font)
- **Visok kontrast** - Tamni tekst na svetloj pozadini
- **Intuitivna navigacija** - Jednostavna upotreba mišem i tastaturom
- **Keyboard shortcuts** - Brza kontrola aplikacije

---

## 📦 Instalacija

### Zahtevi
- **Operativni sistem**: Windows 11 (ili Windows 10)
- **Python**: 3.11 ili noviji
- **VLC Media Player**: Instaliran (za LibVLC)

### Koraci

1. **Klonirajte repozitorijum ili preuzmite fajlove**
```bash
git clone https://github.com/yourname/migecast-iptv.git
cd migecast-iptv

Kreirajte virtuelno okruženje (opcionalno ali preporučeno)

python -m venv venv
venv\Scripts\activate

Instalirajte zavisnosti

pip install -r requirements.txt

Pokrenite aplikaciju

python main.py

🎮 Korišćenje
Dodavanje Playlista
M3U Fajl
Kliknite na ⚙ Podešavanja
Idite na tab 📋 Upravljanje Listama
Kliknite 📁 Pretraži i izaberite M3U fajl
Kliknite ✓ Učitaj
Xtream Codes
Kliknite na ⚙ Podešavanja
Idite na tab 📋 Upravljanje Listama
Unesite Server URL, Username i Password
Kliknite ✓ Učitaj Xtream
Gledanje Live TV
Idite na tab 📺 Live TV
Izaberite kategoriju (Sve, Sport, Filmovi, itd.)
Kliknite na kanal u listi
Uživajte u gledanju!
Gledanje VOD
Idite na tab 🎬 Filmovi & Serije
Pretražite ili sortirajte sadržaj
Kliknite na poster filma/serije
Kliknite ▶ GLEDAJ
Keyboard Shortcuts
F - Fullscreen toggle
Esc - Izlaz iz fullscreen-a
Space - Play/Pause
↑/↓ - Prethodni/Sledeći kanal
←/→ - Seek unazad/napred (10s)
Ctrl+↑/↓ - Volume gore/dole
⚙️ Podešavanja
Player Settings
Timeshift buffer veličina: 2GB / 5GB / 10GB
Auto-reconnect pokušaji: 1-10
Hardverska akceleracija: Omogući/Onemogući
Display Settings
Maksimalan broj kanala: 50 / 100 / 200 / Sve
Maksimalan broj VOD: 50 / 100 / 200 / Sve
🐛 Troubleshooting
Stream se ne reprodukuje
Proverite internet konekciju
Proverite da li je M3U/Xtream Codes validan
Proverite VLC instalaciju
Nema logoa/postera
Proverite internet konekciju
Cache će se popuniti postepeno
Aplikacija se sporo učitava
Povećajte cache veličinu
Smanjite broj prikazanih kanala/VOD stavki
📝 Licenca
© 2025 Mige. Sva prava zadržana.

📧 Kontakt
Za podršku ili pitanja, kontaktirajte: your-email@example.com

Uživajte u MigeCast IPTV! 🎉