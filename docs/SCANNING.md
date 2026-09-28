# Scan : calibration et extension

## Pré-requis côté jeu
- Client PC en **mode fenêtré**, ratio **16:9** (profil `config/regions/16x9.toml`).
- Interface à 100 %, langue identique à `game.lang`.
- Ne pas recouvrir la fenêtre pendant la capture (mss capture l'écran, pas la fenêtre).

## Calibrer les zones (ROI)
1. Scanner quelques héros avec `save_captures = true` (dossier `captures/` du répertoire de données).
2. Ouvrir une capture, relever pour chaque zone `[x, y, largeur, hauteur]` en pixels puis diviser
   par la taille de l'image → valeurs normalisées.
3. Mettre à jour le TOML, puis vérifier visuellement :
   ```python
   from PIL import ImageDraw, Image
   from e7showcase.config import regions
   from e7showcase.vision.regions import to_pixels

   img = Image.open("capture.png")
   d = ImageDraw.Draw(img)
   for section in regions().values():
       for box in section.values():
           d.rectangle(to_pixels(box, img.size), outline="red", width=3)
   img.save("debug-roi.png")
   ```
4. Ajouter la capture et le résultat attendu dans `tests/fixtures/captures/` (test de non-régression).

La skill Claude `calibrate-ocr-regions` automatise ces étapes.

## Ajouter un ratio d'écran
Copier `16x9.toml` en `16x10.toml` / `21x9.toml`, recalibrer, puis `region_profile = "16x10"`.
Une détection automatique du ratio (`WindowRect.aspect`) est prévue (ROADMAP).

## Ajouter une langue
1. Ajouter les libellés dans `data/reference/stat_aliases.json` (clés normalisées : minuscules, sans accents).
2. Ajouter les noms de sets (`sets.json`) et de héros (`heroes.json`) dans la langue.
3. Ajouter des cas dans `tests/test_stat_parser.py`.

## Erreurs OCR fréquentes
| Symptôme | Cause probable | Correctif |
|---|---|---|
| `20` lu `2O` | police du jeu | déjà corrigé par `_OCR_DIGIT_FIXES` |
| libellé + valeur sur deux lignes | OCR segmente la ligne | `_merge_rows` (tolérance verticale) |
| nom de héros inconnu | référentiel incomplet | compléter `heroes.json` |
| stat principale incohérente | mauvaise ROI / mauvais slot | recalibrer `gear_tooltip` |
