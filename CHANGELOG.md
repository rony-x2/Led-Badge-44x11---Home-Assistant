# Changelog

Alle nennenswerten Änderungen an diesem Projekt. Das Format folgt
[Keep a Changelog](https://keepachangelog.com/de/1.1.0/), die Versionen
[Semantic Versioning](https://semver.org/lang/de/).

## [0.2.0] – 2026-10-09

### Behoben
- Helligkeit 25 %: Das Badge erwartet `0x40`, gesendet wurde `0x30`
  (Referenz: fossasia/led-name-badge-ls32).
- Text und Icons wurden im Event-Loop gerendert (Schrift- und Bilddateien
  laden blockiert). Das passiert jetzt im Executor.
- Leerzeichen neben Icons gingen verloren, Textteile vor und nach einem Icon
  standen unterschiedlich hoch, Text mit Unterlängen wurde verzerrt.
- Transparente Bereiche eigener PNG-Icons konnten als leuchtende Pixel
  erscheinen.
- Der Zeitstempel im Protokoll nutzt die Zeitzone von Home Assistant statt
  der des Containers.

### Geändert
- **Neue Ordnerstruktur `custom_components/led_badge/`** (HACS-kompatibel).
  Bei manueller Installation den Ordner aus dem Repository oder das
  ZIP aus dem Release verwenden.
- Schrift: DejaVu Sans Bold (Fallbacks: DejaVu Sans, DejaVu Sans Mono), Größe
  automatisch so gewählt, dass Umlaute und Unterlängen in 11 px passen,
  ohne Kantenglättung.
- Die Aktion `led_badge.send` wird einmalig beim Start registriert und
  bleibt auch ohne eingerichtetes Badge erhalten.
- Sind mehrere Badges eingerichtet, muss `address` angegeben werden
  (bisher wurde stillschweigend das erste genommen).
- Eingaben sind toleranter (`speed: "5"`, `mode: "4"` als Text).
- Pfade zu eigenen Icons über die HA-Konfiguration statt fest `/config`.
- manifest: Links auf dieses Repository, `codeowners`, Bluetooth-Matcher
  `LSLED*`, keine redundanten `requirements`.

### Hinzugefügt
- Eigene Schrift über `/config/led_badge_font.ttf` (z. B. wenn keine
  DejaVu-Schrift installiert ist; die Pillow-Standardschrift kennt keine
  Umlaute).
- Prüfung auf die 8-KB-Speichergrenze des Badges mit verständlicher
  Fehlermeldung.
- Sperre je Badge, damit sich gleichzeitige Aufrufe nicht überschneiden.
- `hacs.json`, Tests (pytest-homeassistant-custom-component), `CHANGELOG.md`.

### Entfernt
- `led_badge.zip` aus dem Repository (liegt jetzt dem Release bei).

## [0.1] – 2026-05-04

- Erste Veröffentlichung.

[0.2.0]: https://github.com/rony-x2/Led-Badge-44x11---Home-Assistant/compare/0.1...0.2.0
[0.1]: https://github.com/rony-x2/Led-Badge-44x11---Home-Assistant/releases/tag/0.1
