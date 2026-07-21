# 🎬 SolarSound v7 — Lecteur Audio & Vidéo 5.1

## Nouveautés v7

### Lecteur Vidéo (onglet 🎬)
- Formats : **MP4, MKV, AVI, MOV, WMV, DTS** + M4V, FLV, WebM, MPEG, TS
- Vitesse variable : **0.25x → 10x**
- **Image par image** : touches `.` (suivant) et `,` (précédent), ou boutons `◁|` `|▷`
- **Sous-titres** : pistes embarquées + chargement externe SRT/ASS
- **Fenêtre détachable** : bouton ⧉ pour détacher, double-clic → plein écran
- **Playlists mixtes** : audio et vidéo dans la même liste de lecture

### Paramètres (onglet ⚙)
- **Raccourcis clavier** : tous remappables, cliquer sur un champ puis appuyer
- **Couleurs** : chaque élément de l'interface personnalisable + 3 presets
- **Polices** : police principale + police monospace avec aperçu en temps réel

## Installation

### Prérequis
```
pip install -r requirements.txt
```

### VLC requis pour la vidéo
Télécharger VLC 64-bit : https://www.videolan.org/vlc/
Installer dans le répertoire par défaut (C:\Program Files\VideoLAN\VLC)
python-vlc détecte automatiquement l'installation.

### Démarrage
```
python main.py
```

### Compilation .exe
```
pyinstaller SolarSound.spec
```

## Raccourcis par défaut

| Action | Touche |
|--------|--------|
| Lecture/Pause | Espace |
| Stop | Échap |
| Suivant | → |
| Précédent | ← |
| Image suivante (vidéo) | . |
| Image précédente (vidéo) | , |
| Accélérer | Ctrl+↑ |
| Ralentir | Ctrl+↓ |
| Vitesse normale | Ctrl+0 |
| Avancer 5s | Ctrl+→ |
| Reculer 5s | Ctrl+← |
| Volume + | ↑ |
| Volume - | ↓ |
| Plein écran | F |
| Ouvrir fichier | Ctrl+O |
| Sauvegarder liste | Ctrl+S |
| Quitter | Ctrl+Q |

Tous les raccourcis sont reconfigurables dans **⚙ Paramètres → Raccourcis**.

## Associations de fichiers Windows

Lancer `register_associations.ps1` en admin pour associer :
`.mp3`, `.wav`, `.mp4`, `.mkv`, `.avi`, `.mov`, `.wmv`, `.playlist`
