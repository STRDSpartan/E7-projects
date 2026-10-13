# Zealot mobile (Android, iOS)

## Choix technique
**BeeWare / Briefcase** : l'app mobile embarque **le même cœur Python** que l'application PC
(`src/e7showcase`, profils, vitrines `.e7v`, simulateurs, guilde, GvG) et **la même interface**
(`app/ui.html`), affichée dans une WebView plein écran. L'app démarre le serveur local
(`e7showcase.app.server`, `127.0.0.1`) puis ouvre `ui.html#mobile`.
Une seule base de code : chaque évolution de l'app PC profite au mobile.

- Point d'entrée : `mobile/zealot/__main__.py` → `e7showcase.mobile.app` (Toga `MainWindow` + `WebView`).
- Données : dossier de données de l'app (`App.paths.data`), comme `E7_DATA_DIR`.
- Pas de sous-processus sur mobile : le simulateur calcule dans le processus de l'app
  (`calc.battle.MOBILE_PLATFORMS`, `E7_NO_PROCESSES`).
- Interface : sous 760 px, en-tête compact, tiroir des profils (☰), barre d'onglets en bas,
  zones sûres (encoche) respectées. Le bouton « Rechercher une mise à jour » est masqué
  (mises à jour par les stores).
- Android : trafic HTTP local autorisé (`usesCleartextTraffic`) ; iOS : `NSAllowsLocalNetworking`.

## Construire
```bash
pip install briefcase==0.4.6
python scripts/prepare_mobile.py      # sources avec données intégrées + icônes depuis le logo
briefcase create android && briefcase build android    # APK de test
briefcase create iOS && briefcase build iOS            # macOS + Xcode, simulateur
```
La CI `.github/workflows/mobile.yml` construit l'APK Android (artefact « Zealot-Android ») et
vérifie la construction iOS sur macOS.

## Feuille de route
1. **Socle** (fait) : app native, serveur local, interface tactile, CI Android et iOS.
2. **Lecture des captures sur mobile** : RapidOCR/onnxruntime n'existe pas pour Android/iOS.
   Prévu : moteur OCR natif (ML Kit sur Android, Vision sur iOS) derrière l'interface
   `vision.ocr.OcrEngine`, plus sélection de captures depuis la galerie et le partage système
   (« Partager vers Zealot »). En attendant, la vitrine, les simulateurs, la guilde et la GvG
   fonctionnent ; l'import de captures affiche un message clair.
3. **Ouverture des `.e7v`** depuis Discord (association de fichiers / intent Android, type UTI iOS).
4. **Publication** : Play Store (compte Google Play, 25 $ une fois) et App Store (Apple Developer
   Program, 99 $/an, signature et TestFlight) — à créer par l'éditeur ; la CI signera ensuite.

## État de la construction (CI)
- Android : la construction Gradle tourne ; **bloquant : `pydantic-core`** (cœur binaire de
  pydantic, écrit en Rust) n'existe ni dans le dépôt Chaquopy ni sur PyPI pour Android.
- iOS : même blocage (`pydantic-core` sans version iOS).
- `rapidfuzz` : réglé (repli pur Python `e7showcase.fuzzy`, rapidfuzz devenu optionnel).
- Prochaine étape : compiler `pydantic-core` pour Android et iOS dans la CI (cibuildwheel +
  maturin, cibles Rust `aarch64-linux-android`, `x86_64-linux-android`, `aarch64-apple-ios`,
  `aarch64-apple-ios-sim`) et le fournir à Briefcase (`--find-links`).

## Limites connues
- Dépendances binaires (pydantic-core, rapidfuzz, numpy, Pillow) : elles doivent exister en
  version mobile ; la CI le vérifie à chaque construction.
- Les décors GvG et la vidéo du bandeau sont inclus comme sur PC.
