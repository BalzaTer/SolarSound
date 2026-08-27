# 🎬 SolarSound — Lecteur Audio & Vidéo 5.1

Tout est en Python, et tout est généré par IA, mais ça marche plutôt bien donc soyons heureux 😀. J'ai créé ce logiciel dans le but de pouvoir écouter de la musique en surround sur mon PC avec les options dont j'avais besoin car je n'ai rien trouvé d'nteressant et de pratique sur VLC permettant le réglage d'un système 5.1. C'est donc un besoin à la base personnel, mais qui pourrait servir à d'autres ! Disposez de ce logiciel comme vous le voulez pour un usage personnel, mais interdit à la vente !

## Fonctionnalités

### Lecteur Audio

- Lit de nombreux formats audios dont WAV, MP3 etc...
- La musique en cours est affichée en gros avec son titre, l'interprète et l'album. La vignette n'est actuellement pas prise en charge ais son emplacement est déjà là !
- La barre de lecture permet de choisir et de visualiser l'avancement de la lecture du fichier audio. Le temps à gauche de la barre est le temps écoulé du morceau en lecture, et le temps à droite est le temps complet du morceau
- La barre de volume gère le niveau sonore (en %), et augmente logarithmiquement (comme des dBs), il peut se changer en survolant la barre et en faisant tourner la roulette de la souris
- Le bouton 🔁/🔂, permet un mode boucle de tous les fichiers (🔁) ou d'un seul fichier (🔂)
- Le bouton 🔀/➡️, permet un mode aléatoire (🔀) dans le choix des fichiers ou continu (➡️), l'ordre des fichiers peut alors être changé en glissant déposant les fichiers dans la liste des fichiers ouverts dans le logiciel (Onglet "📋 Playlist")
- Les boutons "⏮" et "⏭" permettent de passer à la musique suivante ou précédente
- Le bouton "⏹" remet à 0 et en pause la musique, tandis que le bouton ▶️/⏸ permet de jouer/mettre en pause le fichier
- Animation jolie dans les tons orangés/jaunes, bougeant avec la musique en fonction de l'intensité de chaque fréquence. Activable/Désactivable en survolant et clic droit.

### Onglet "📋 Playlist"

- Visalisations des fichiers ouverts dans le logiciel sous forme de liste avec nom de la musique (nom du fichier si aucun titre de musique), suivi de l'interprète après un "-"
- Le fichier en cours de lecture est de la couleur jaune et en gras, et est précédé d'un triangle de la même couleur
- Le bouton **"Ajouter"** permet d'ajouter un ou plusieurs fichiers à la liste de fichiers ouverts dans le logiciel
- Le bouton **"Dossier"** permet d'ajouter toutes les musiques situées dans un dossier et ses sous-dossiers à la liste de fichiers ouverts dans le logiciel
- Le bouton **"Retirer"** permet de retirer un fichier de la liste de fichiers ouverts dans le logiciel
- Le bouton **"Vider"** permet de retirer l'entiereté des fichiers de la liste des fichiers ouverts dans le logiciel, une confirmation est demandée avant l'action
- Permet la création de playlist, enregistrables et réouvrables à l'aide de fichier .playlist (Boutons **"Enregistrer"** et **"Ouvrir"**)
- Double clic sur un fichier permet de le mettre directement en lecture
- Le bouton **CD Audio** permet l'ajout de toutes les musiques d'un CD dans la playlist, il est donc possible de créer une playlist mix avec des audios sur CD, mémoire flash, disque dur, ou même lecteur de floppy disque pourquoi pas !

### Onglet "🎬 Vidéo"

- Formats : **MP4, MKV, AVI, MOV, WMV, DTS** + M4V, FLV, WebM, MPEG, TS
- Vitesse variable : **0.25x → 10x**
- **Image par image** : touches `.` (suivant) et `,` (précédent), ou boutons `◁|` `|▷`
- **Sous-titres** : pistes embarquées + chargement externe SRT/ASS
- **Fenêtre détachable** : bouton ⧉ pour détacher, double-clic → plein écran (à régler le double clic plein écran appli direct et non pas double clic détachement de la fenêtre)
- **Playlists mixtes** : audio et vidéo dans la même liste de lecture

### Onglet "🔊 5.1"

- Réglage des niveaux de chaque enceinte de 0.0 à 2.0
- Doublement facade avant vers les enceintes arrières pour un son plus immersif, ratio réglable (problème de coupure total du mode à régler)
- Mixage mono vers le caisson de basse, avec fréquence de coupure réglable (40-300Hz) et Gain LFE réglable (0.0 à 2.0)
- Options stéréos (Inverser le stéréo, mixer en mono et angle de séparation de l'audio

### Onglet "🌀 Rotation"

- Rotation du son autour de l'auditeur avec vitesse de rotation réglable de 0.6 à 2.0 tours par secondes, avec presets de vitesse
- Réglage de l'étalement angulaire du son (son sur 1 seule enceinte ou sur 3)
- Réglage de l'angle entre source gauche et droite, 0° = Mono et 180° = stéréo parfait (Actuellement peu efficace)

### Onglet "💿 Vinyle"

- Effet "Vinyle", tentant de reproduire numériquement l'aléatoire et la qualité du son du vinyle (C'est assez expérimental quand même)
- 3 Presets "Neuf", "Usé" ou "Très usé"
- Des kilos d'options pour régler les effets de vitesses, bruit de fond, crépitements etc...

### Onglet "⚙ Paramètres"

- **Raccourcis clavier** : tous remappables, cliquer sur un champ puis appuyer
- **Couleurs** : chaque élément de l'interface personnalisable + 3 presets
- **Polices** : police principale + police monospace avec aperçu en temps réel

## Installation

L'installation du projet est disponible pour Windows, à l'aide de l'installateur dans le dossier /installateurL'installation du projet est disponible pour indows, à l'aide de l'installateur dans le dossier /installateur

## Raccourcis par défaut


| Action                      | Touche  |
| --------------------------- | ------- |
| Lecture/Pause               | Espace  |
| Stop                        | Échap  |
| Suivant                     | →      |
| Précédent                 | ←      |
| Image suivante (vidéo)     | .       |
| Image précédente (vidéo) | ,       |
| Accélérer                 | Ctrl+↑ |
| Ralentir                    | Ctrl+↓ |
| Vitesse normale             | Ctrl+0  |
| Avancer 5s                  | Ctrl+→ |
| Reculer 5s                  | Ctrl+← |
| Volume +                    | ↑      |
| Volume -                    | ↓      |
| Plein écran                | F       |
| Ouvrir fichier              | Ctrl+O  |
| Sauvegarder liste           | Ctrl+S  |
| Quitter                     | Ctrl+Q  |

Tous les raccourcis sont reconfigurables dans **⚙ Paramètres → Raccourcis**.
