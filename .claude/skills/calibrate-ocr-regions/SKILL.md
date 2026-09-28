---
name: calibrate-ocr-regions
description: Calibrer ou ajouter les zones OCR (ROI normalisées) de config/regions/*.toml à partir de captures réelles d'Epic Seven (écrans « Infos de héros » et liste des héros), vérifier visuellement, mesurer la précision contre une vérité terrain locale. À utiliser dès qu'une zone lit mal, qu'une mise à jour du jeu change l'UI, ou pour un nouveau format d'écran (PC 16:9, tablette...).
---

# Calibrer les zones OCR

## Entrées nécessaires
Des captures **réelles** au format visé : écran « Infos de héros » et écran liste des héros
d'un même héros (paires `<nom>-list` / `<nom>-detail`), idéalement 3 héros aux sets variés.
Sans captures : s'arrêter et les demander — ne jamais deviner des coordonnées.
Les captures restent **hors dépôt** (scratchpad ou dossier de l'utilisateur).

## Schéma d'un profil (`config/regions/19_5x9.toml` fait référence)
- `aspect` : largeur/hauteur (sert au choix automatique).
- `[detail]` : boîtes `[x, y, w, h]` normalisées ; `stats_icons/labels/values` = 9 lignes égales.
- `[detail.gear]` : ancre `[x, y]` de chaque pièce = coin haut-gauche de l'icône de la stat principale.
- `[detail.gear_layout]` : boîtes **relatives à l'ancre** (valeurs, icônes, niveau, +15, set, score).
- `[hero_list]` : `title_hint`, `name`, `set_rows` (`[x_icône, y, w_icône, h, w_texte]`).
- `[navigation]` : points de clic du mode assisté.

## Étapes
1. **Point de départ** : nouveau format → `python scripts/derive_profile.py config/regions/19_5x9.toml <aspect>`.
2. **OCR brut** de la capture entière (RapidOCR) pour obtenir les positions normalisées des textes.
3. **Dessiner les ROI** sur chaque capture et vérifier (outil Read) :
   ```python
   from PIL import Image, ImageDraw
   from e7showcase.config import regions

   r = regions("19_5x9")
   d = r["detail"]
   L = d["gear_layout"]
   img = Image.open("capture.jpg").convert("RGB")
   W, H = img.size
   dr = ImageDraw.Draw(img)
   box = lambda b, c: dr.rectangle(
       (b[0] * W, b[1] * H, (b[0] + b[2]) * W, (b[1] + b[3]) * H), outline=c, width=3
   )
   for v in d.values():
       if isinstance(v, list):
           box(v, "red")
   for ax, ay in d["gear"].values():
       for dy, h in zip(L["line_dy"], L["line_h"]):
           box([ax, ay + dy, L["icon_w"], h], "yellow")
           box([ax + L["values_dx"], ay + dy, L["values_w"], h], "cyan")
   img.save("debug-roi.png")
   ```
   Contrôler en particulier : pas de bord d'icône dans les boîtes de valeurs (« 7% » lu « 17% »),
   chiffres du niveau non coupés, icône de set entière.
4. **Vérité terrain** : transcrire `expected.json` (format dans `scripts/evaluate_captures.py`).
5. **Mesurer** : `python scripts/evaluate_captures.py <dossier>` ; itérer jusqu'à ≥ 95 %.
   `E7_TEST_CAPTURES=<dossier> pytest tests/test_real_captures.py` doit passer.
6. Documenter la précision obtenue dans `docs/SCANNING.md`, puis skill `dev-checks`.

## Pièges
- Mise à l'échelle Windows ≠ 100 % ou plein écran exclusif : décalages → fenêtré 100 %.
- Travailler sur la zone cliente (sans barre de titre).
- Sur la liste des héros, les stats portent un bonus « ▲ » : ne jamais les lire là.
