# LED Name Badge — Home Assistant Custom Integration

Eine kleine Custom Integration für Home Assistant, die das **LSLED-LED-Namensschild**
(BLE-Variante, 11×44 Pixel, kompatibel mit der FOSSASIA `badgemagic-app`) per
Bluetooth ansteuert. Der HA-Bluetooth-Stack wird verwendet, sodass die
Verbindung automatisch über deinen **ESPHome-BT-Proxy** läuft, wenn dieser
in Reichweite und im **active mode** konfiguriert ist.

## Voraussetzungen

- Home Assistant OS (oder Container/Core) mit aktivierter Bluetooth-Integration
- Mindestens ein BT-Adapter — Stick lokal **oder** ein ESPHome-BT-Proxy:
  ```yaml
  # esphome config (Auszug)
  bluetooth_proxy:
    active: true   # WICHTIG: Schreibvorgänge brauchen active mode
  ```

## Installation auf HAOS

1. Per **Samba**, **File Editor**-Add-on oder **SSH** in dein HAOS einsteigen.
2. Den kompletten Ordner `led_badge/` nach
   ```
   /config/custom_components/led_badge/
   ```
   kopieren. Die Verzeichnisstruktur muss am Ende so aussehen:
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
2. Den oberen Knopf **nochmal** drücken — das Bluetooth-Symbol erscheint im Display.
   *Nur in diesem Modus advertised das Badge und ist verbindbar.*
3. In HA: `Einstellungen` → `Geräte & Dienste` → `Integration hinzufügen` → **LED Name Badge**.
4. Das Badge sollte in der Liste auftauchen (oder per Auto-Discovery vorgeschlagen werden). Auswählen, fertig.

> Wenn der HA-Discovery nicht greift, einfach beim Einrichtungs-Dialog manuell
> aus der Dropdown-Liste auswählen — die Liste enthält alle gerade
> sichtbaren `LSLED`-Geräte.

## Service `led_badge.send`

```yaml
service: led_badge.send
data:
  brightness: 75
  messages:
    - text: "Dennis :wifi:"
      mode: left          # scrollt — empfohlen wenn Text >44 px breit
      speed: 5
    - text: "WLAN: MyHomeNet"
      mode: fixed
    - text: "PSK: hunter2!"
      mode: left
      blink: true
```

### Felder

| Feld           | Typ          | Default  | Bedeutung |
|----------------|--------------|----------|-----------|
| `address`      | string       | optional | MAC der Badge; nur nötig wenn mehrere konfiguriert sind |
| `brightness`   | 1–100        | 100      | wird auf 25/50/75/100 % gerundet (Hardware-Stufen) |
| `messages`     | Liste 1–8    | required | siehe unten |
| → `text`       | string       | required | beliebiger Text + `:icon:`-Tokens |
| → `mode`       | name oder 0–8| `left`   | `left`, `right`, `up`, `down`, `fixed`, `anim`, `drop`, `curtain`, `laser` |
| → `speed`      | 1–8          | 4        | 1 = langsamst, 8 = schnellst |
| → `blink`      | bool         | false    | Nachricht blinkt |
| → `marquee`    | bool         | false    | Lauflicht-Rahmen um die Nachricht |

### Icon-Syntax

Im Text `:name:` schreiben, z. B. `Hi :heart: Welt`.

**Built-in:** `heart`, `wifi`, `bell`, `check`, `cross`, `warn`, `home`,
`smile`, `arrow_left`, `arrow_right`, `music`, `key`, `battery`.

**Eigene Icons:** PNG (oder BMP/GIF) nach
`/config/led_badge_icons/<name>.png` legen — wird automatisch auf 11 px Höhe
skaliert. Dann via `:<name>:` im Text einbinden.

## Typischer Workflow für deinen Use Case

`input_text`-Helper für Name + WLAN-SSID + WLAN-PSK anlegen, Skript darüber:

```yaml
# scripts.yaml
update_badge:
  alias: Badge aktualisieren
  sequence:
    - service: led_badge.send
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

Auf dem Dashboard ein Button auf das Skript binden. Workflow am Badge:
Knopf-Knopf → BT-Symbol → Button drücken → fertig.

## Bekannte Einschränkungen

- Das Badge advertised **nur im BT-Modus** — automatische Hintergrund-Updates
  ohne Tastendruck sind nicht möglich.
- Helligkeit hat firmwareseitig nur 4 Stufen.
- Bei sehr langen Nachrichten (>~150 byte-columns) kann die Hardware
  Speichergrenzen erreichen — keine harte Doku gefunden, ggf. ausprobieren.
- Der mitgelieferte Default-Font versucht zuerst **DejaVu Sans Mono** zu
  finden. Ist dieser auf HAOS nicht installiert, wird auf den Pillow-
  Default-Font zurückgefallen (ca. 10 px hoch statt 11). Optisch nicht ganz
  so randvoll, aber lesbar.

## Debugging

Im `configuration.yaml`:

```yaml
logger:
  default: warning
  logs:
    custom_components.led_badge: debug
```

Dann zeigt der Log nach jedem `led_badge.send`-Aufruf die Anzahl Bytes und
BLE-Chunks, sowie alle Connect-Fehlermeldungen.

## Spec-Quellen / Credits

- Reverse Engineering: Gautier "Nilhcem" Mechling — http://nilhcem.com/iot/reverse-engineering-bluetooth-led-name-badge
- Referenz-Implementierung (USB/HID, identisches Datenformat): https://github.com/fossasia/led-name-badge-ls32
- Original-App: https://github.com/fossasia/badgemagic-app
- Hardware-Doku & UUIDs: https://github.com/fossasia/badgemagic-firmware
