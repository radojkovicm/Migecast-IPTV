# Vodič za Debugovanje - MigeCast IPTV

## Problem: Program se pokreće ali brzo se gasi

### Što je ispravljeno u ovoj verziji:

1. **QMessageBox.exec() blokiranje** - Dodao sam `QTimer.singleShot()` da izbegnem da dva modalna dijaloga budu aktivna istovremeno
2. **Error handling** - Dodao sam try/except u sve kritične funkcije
3. **Validacija podataka** - Proveravamo da li su kanali/VOD/serije učitani
4. **Null pointer zaštita** - Hvatamo sve slučajeve gdje su atributi None/Null

### Kako debugovati problem:

1. **Pogledaj logove:**
   ```
   migecast.log
   ```
   
   Otvori log fajl i pogledaj koji je zadnji log message pre nego što se program zatvorio.

2. **Pokreni sa debug módom:**
   ```bash
   python main.py
   ```
   
   Pogledaj konzolu za error poruke.

3. **Česti uzroci problema:**

   a) **Playlista je prazna ili ne postoji:**
      - Logovanje će pokazati: `"Playlist loaded but contains no data"`
      - Rešenje: Dodaj IPTV listu iz podešavanja

   b) **M3U fajl nije pronađen:**
      - Logovanje će pokazati: `"M3U file path is empty"`
      - Rešenje: Proverite da li je putanja do fajla ispravna

   c) **Xtream kredencijali nisu ispravni:**
      - Logovanje će pokazati: `"Xtream credentials are incomplete"`
      - Rešenje: Proverite korisničko ime, lozinku i URL servera

   d) **Greška pri parsiranju M3U:**
      - Logovanje će pokazati: `"Failed to parse M3U file: ..."`
      - Rešenje: Proverite format M3U fajla

### Testiranje:

1. **Sa test M3U fajlom:**
   - Kreiraj `test.m3u` sa sledećom sadržajem:
   ```
   #EXTM3U
   #EXTINF:-1 tvg-id="ch1" tvg-name="Test Channel" group-title="Test" tvg-logo="https://example.com/logo.png",Test Channel
   http://example.com/stream.m3u8
   ```

2. **Prati logove u realnom vremenu:**
   ```bash
   tail -f migecast.log
   ```

### Modifikacije u kodu:

**main_window.py:**
- `load_saved_playlist()` - Dodao validaciju i error handling
- `show_settings()` - Dodao try/except
- `show_welcome_dialog()` - Koristi QTimer za odbacivanje modala

**settings_dialog.py:**
- `PlaylistLoaderThread.run()` - Validira sve inpute
- `load_m3u_file()` - Dodao try/except
- `load_xtream_codes()` - Dodao try/except
- `on_playlist_loaded()` - Validira podatke pre nego što prosledi dalje

**live_tv_widget.py:**
- `load_channels()` - Proverava da li je lista prazna
- `filter_channels()` - Hvata greške pri pretrazi favorita

**vod_widget.py, series_widget.py:**
- `load_vod_items()`, `load_series_items()` - Iste zaštite kao channels

