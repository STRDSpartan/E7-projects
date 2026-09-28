---
name: calibrate-ocr-regions
description: Calibrer ou ajouter les zones OCR (ROI normalisées) de config/regions/*.toml à partir de captures réelles du client PC Epic Seven, vérifier visuellement, et figer le résultat dans une fixture de test. À utiliser dès qu'une zone lit mal, qu'une mise à jour du jeu change l'UI, ou pour un nouveau ratio d'écran.
---

# Calibrer les zones OCR

## Entrées nécessaires
Des captures **réelles** de la zone cliente du jeu (fiche héros + infobulle de chaque
emplacement), idéalement prises par `e7showcase scan` avec `save_captures = true`.
Sans captures : s'arrêter et les demander à l'utilisateur — ne jamais deviner des coordonnées.

## Étapes
1. **Identifier le profil** : ratio = largeur/hauteur de la capture (1.777 → `16x9`,
   1.6 → `16x10`, 2.37 → `21x9`). Nouveau ratio → copier `config/regions/16x9.toml`.
2. **Mesurer** chaque zone en pixels puis normaliser :
   `[x/W, y/H, w/W, h/H]`, 3 décimales. Laisser ~5 % de marge autour du texte.
3. **Dessiner les ROI** pour vérifier :
   ```bash
   python - <<'PY'
   from PIL import Image, ImageDraw
   from e7showcase.config import regions
   from e7showcase.vision.regions import to_pixels
   img = Image.open("CAPTURE.png").convert("RGB"); d = ImageDraw.Draw(img)
   for sec, boxes in regions("16x9").items():
       for key, box in boxes.items():
           b = to_pixels(box, img.size); d.rectangle(b, outline="red", width=3); d.text((b[0], b[1]-12), f"{sec}.{key}", fill="yellow")
   img.save("debug-roi.png")
   PY
   ```
   Ouvrir `debug-roi.png` (outil Read) et corriger jusqu'à ce que chaque cadre englobe son texte.
4. **Tester l'OCR** zone par zone (extra `[scan]` requis) :
   ```python
   from e7showcase.vision.ocr import get_engine
   from e7showcase.vision.regions import crop

   print([l.text for l in get_engine().read_lines(crop(img, box))])
   ```
5. **Figer une fixture** : copier la capture (anonymiser pseudo/UID en floutant) dans
   `tests/fixtures/captures/<profil>/` avec un JSON du `Hero` attendu, et ajouter un test
   `HeroScanner` (OCR factice ou marqué `@pytest.mark.ocr`).
6. Lancer la skill `dev-checks`.

## Pièges
- Mode plein écran exclusif / mise à l'échelle Windows ≠ 100 % : décalages → demander le fenêtré.
- La barre de titre ne doit pas être incluse (on travaille sur la zone cliente).
- Les infobulles d'objet changent de position selon l'emplacement : vérifier les 6.
