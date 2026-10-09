# LED Name Badge – Home Assistant Custom Integration

Eine kleine Custom Integration für Home Assistant, die das **LSLED-LED-Namensschild**
(BLE-Variante, 11×44 Pixel, kompatibel mit der FOSSASIA `badgemagic-app`) per
Bluetooth ansteuert. Der HA-Bluetooth-Stack wird verwendet, sodass die
Verbindung automatisch über deinen **ESPHome-BT-Proxy** läuft, wenn dieser
in Reichweite und im **active mode** konfiguriert ist.

Für die Bedienung im Dashboard gibt es eine passende Karte:
[Led-Badge – Home Assistant Lovelace Card](https://github.com/rony-x2/Led-Badge---Home-Assistant-Lovelace-Card-).

## Voraussetzungen

- Home Assistant 2024.4 oder neuer mit aktivierter Bluetooth-Integration (für die `action:`-Schreibweise in den Beispielen: 2024.8)
- Mindestens ein BT-Adapter – Stick lokal **oder** ein ESPHome-BT-Proxy:
  ```yaml
  # esphome config (Auszug)
  bluetooth_proxy:
    active: true   # WICHTIG: Schreibvorgänge brauchen active mode
  ```

## Installation

### Über HACS (empfohlen)

1. HACS → Menü (⋮) → **Benutzerdefinierte Repositories**
2. URL `https://github.com/rony-x2/Led-Badge-44x11---Home-Assistant`
   eintragen, Typ **Integration**, hinzufügen.
3. „LED Name Badge (LSLED)“ in HACS herunterladen.
4. **Home Assistant neu starten**.

### Manuell

1. Per **Samba**, **File Editor**-Add-on oder **SSH** auf deine HA-Konfiguration zugreifen.
2. Den Ordner `custom_components/led_badge/` aus diesem Repository nach
   `/config/custom_components/led_badge/` kopieren. Die Struktur muss am Ende so aussehen:
   ```
   /config/custom_components/led_badge/
   ├── __init__.py
   ├── config_flow.py
   ├── const.py
   ├── icons.py
   ├── manifest.json
   ├── protocol.py
   ├── renderer.py
   ├── services.yaml
   ├── strings.json
   └── translations/
       ├── de.json
       └── en.json
   ```
3. **Home Assistant neu starten** (`Einstellungen` → `System` → `Neustart`).

## Einrichtung

1. Das Badge einschalten (oberer Knopf 1×).
2. Den oberen Knopf **nochmal** drücken – das Bluetooth-Symbol erscheint im Display.
   *Nur in diesem Modus sendet das Badge Advertisements und ist verbindbar.*
3. In HA: `Einstellungen` → `Geräte & Dienste` → `Integration hinzufügen` → **LED Name Badge**.
4. Das Badge sollte in der Liste auftauchen (oder per Auto-Discovery vorgeschlagen werden). Auswählen, fertig.

> Wenn die automatische Erkennung nicht greift, einfach im Einrichtungsdialog
> manuell aus der Dropdown-Liste auswählen – die Liste enthält alle gerade
> sichtbaren `LSLED`-Geräte.

## Aktion `led_badge.send`

```yaml
action: led_badge.send
data:
  brightness: 75
  messages:
    - text: "Dennis :wifi:"
      mode: left          # scrollt – empfohlen, wenn der Text breiter als 44 px ist
      speed: 5
    - text: "WLAN: MyHomeNet"
      mode: fixed
    - text: "PSK: hunter2!"
      mode: left
      blink: true
```

### Felder

| Feld           | Typ           | Default  | Bedeutung |
|----------------|---------------|----------|-----------|
| `address`      | string        | optional | MAC-Adresse des Badges; Pflicht, sobald mehrere Badges eingerichtet sind |
| `brightness`   | 1–100         | 100      | wird auf 25/50/75/100 % gerundet (Hardware-Stufen) |
| `messages`     | Liste 1–8     | required | siehe unten |
| → `text`       | string        | required | beliebiger Text + `:icon:`-Tokens |
| → `mode`       | Name oder 0–8 | `left`   | `left`, `right`, `up`, `down`, `fixed`, `anim`, `drop`, `curtain`, `laser` |
| → `speed`      | 1–8           | 4        | 1 = am langsamsten, 8 = am schnellsten |
| → `blink`      | bool          | false    | Nachricht blinkt |
| → `marquee`    | bool          | false    | Lauflicht-Rahmen um die Nachricht |

### Icon-Syntax

Im Text `:name:` schreiben, z. B. `Hi :heart: Welt`.

**Built-in:** `heart`, `wifi`, `bell`, `check`, `cross`, `warn`, `home`,
`smile`, `arrow_left`, `arrow_right`, `music`, `key`, `battery`.

**Eigene Icons:** PNG (oder BMP/GIF) nach `/config/led_badge_icons/<name>.png`
legen und via `:<name>:` im Text einbinden. Bilder, die höher als 11 px sind,
werden auf 11 px verkleinert, niedrigere vertikal zentriert. Helle Pixel
leuchten, dunkle und transparente bleiben aus. Unbekannte Icon-Namen werden
als Text angezeigt, damit Tippfehler auffallen.

### Schrift

Der Text wird mit **DejaVu Sans Bold** gerendert (Fallback: DejaVu Sans,
DejaVu Sans Mono), die Schriftgröße wird automatisch so gewählt, dass
Umlaute und Unterlängen in die 11 Pixel passen.

Ist keine DejaVu-Schrift installiert, fällt die Integration auf die
Standardschrift von Pillow zurück – die kennt allerdings **keine Umlaute**.
In dem Fall eine beliebige TrueType-Schrift als
`/config/led_badge_font.ttf` ablegen und Home Assistant neu starten.

## Beispiel: Name und WLAN-Zugang anzeigen

`input_text`-Helfer für Name, WLAN-SSID und WLAN-Passwort anlegen, Skript darüber:

```yaml
# scripts.yaml
update_badge:
  alias: Badge aktualisieren
  sequence:
    - action: led_badge.send
      data:
        brightness: 75
        messages:
          - text: "{{ states('input_text.badge_name') }}"
            mode: fixed
            speed: 6
          - text: ":wifi: {{ states('input_text.wlan_ssid') }}"
            mode: left
            speed: 5
          - text: ":key: {{ states('input_text.wlan_psk') }}"
            mode: left
            speed: 5
```

Auf dem Dashboard einen Button auf das Skript legen. Ablauf am Badge:
Knopf, Knopf → BT-Symbol → Button drücken → fertig.

## Bekannte Einschränkungen

- Das Badge ist **nur im BT-Modus** erreichbar – automatische
  Hintergrund-Updates ohne Tastendruck sind nicht möglich.
- Die Helligkeit hat firmwareseitig nur 4 Stufen.
- Der Speicher des Badges fasst insgesamt 8 KB. Alle Nachrichten zusammen
  dürfen daher höchstens etwa 5.900 Pixel breit sein; längere Texte lehnt
  die Aktion mit einer Fehlermeldung ab.

## Debugging

In der `configuration.yaml`:

```yaml
logger:
  default: warning
  logs:
    custom_components.led_badge: debug
```

Dann zeigt das Log nach jedem `led_badge.send`-Aufruf die Anzahl Bytes und
BLE-Chunks, die verwendete Schrift sowie alle Verbindungsfehler.

## Entwicklung

```bash
pip install -r requirements_test.txt
pytest
```

## Spec-Quellen / Credits

- Reverse Engineering: Gautier „Nilhcem“ Mechling – http://nilhcem.com/iot/reverse-engineering-bluetooth-led-name-badge
- Referenz-Implementierung (USB/HID, identisches Datenformat): https://github.com/fossasia/led-name-badge-ls32
- Original-App: https://github.com/fossasia/badgemagic-app
- Hardware-Doku & UUIDs: https://github.com/fossasia/badgemagic-firmware

## Lizenz

GPL-3.0 – siehe [LICENSE](LICENSE). © 2026 Dennis Deutschkämer
