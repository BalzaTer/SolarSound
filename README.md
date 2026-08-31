# 🎬 SolarSound — Lecteur Audio & Vidéo 5.1

<img width="1266" height="132" alt="image" src="https://github.com/user-attachments/assets/577b6e43-399f-44c7-9453-27f54e5f63e8" />


Tout est en Python, et tout est généré par IA, mais ça marche plutôt bien donc soyons heureux 😀. J'ai créé ce logiciel dans le but de pouvoir écouter de la musique en surround sur mon PC avec les options dont j'avais besoin, car je n'ai rien trouvé d'interessant et de pratique sur VLC permettant le réglage d'un système 5.1. C'est donc un besoin à la base personnel, mais qui pourrait servir à d'autres ! Pour la diffusion du logiciel, voir la licence

## Fonctionnalités

### Lecteur Audio

<img width="1916" height="237" alt="image" src="https://github.com/user-attachments/assets/f3b46b82-de06-47a8-8bb7-0ed3213694ff" />

- Lit de nombreux formats audios dont WAV, MP3 etc...
- La musique en cours est affichée en gros avec son titre, l'interprète et l'album. La vignette s'affiche si disponible, sinon un carré uniforme.
- La barre de lecture permet de choisir et de visualiser l'avancement de la lecture du fichier audio. Le temps à gauche de la barre est le temps écoulé du morceau en lecture, et le temps à droite est le temps complet du morceau
- La barre de volume gère le niveau sonore (en %), et augmente logarithmiquement (comme des dBs), il peut se changer en survolant la barre et en faisant tourner la roulette de la souris
- Le bouton `🔁`/`🔂`, permet un mode boucle de tous les fichiers (`🔁`) ou d'un seul fichier (`🔂`)
- Le bouton `🔀`/`➡️`, permet un mode aléatoire (`🔀`) dans le choix des fichiers ou continu (`➡️`), l'ordre des fichiers peut alors être changé en glissant déposant les fichiers dans la liste des fichiers ouverts dans le logiciel (Onglet `📋 Playlist`)
- Les boutons `⏮` et `⏭` permettent de passer à la musique suivante ou précédente
- Le bouton `⏹` remet à 0 et en pause la musique, tandis que le bouton `▶️`/`⏸` permet de jouer/mettre en pause le fichier
- Animation jolie dans les tons orangés/jaunes, bougeant avec la musique en fonction de l'intensité de chaque fréquence. Activable/Désactivable en survolant et clic droit.

### Onglet `📋Playlist`

<img width="1910" height="531" alt="image" src="https://github.com/user-attachments/assets/bd827bf2-d755-4ec6-abdb-6e6241c01ac4" />

- Visalisations des fichiers ouverts dans le logiciel sous forme de liste avec nom de la musique (nom du fichier si aucun titre de musique), suivi de l'interprète après un `-`
- Le fichier en cours de lecture est de la couleur jaune et en gras, et est précédé d'un triangle de la même couleur
- Le bouton `+ Ajouter` permet d'ajouter un ou plusieurs fichiers à la liste de fichiers ouverts dans le logiciel
- Le bouton `📁 Dossier` permet d'ajouter toutes les musiques situées dans un dossier et ses sous-dossiers à la liste de fichiers ouverts dans le logiciel
- Le bouton `X Retirer` permet de retirer un fichier de la liste de fichiers ouverts dans le logiciel
- Le bouton `🗑️ Vider` permet de retirer l'entiereté des fichiers de la liste des fichiers ouverts dans le logiciel, une confirmation est demandée avant l'action
- Permet la création de playlist, enregistrables et réouvrables à l'aide de fichier .playlist (Boutons `💾 Enregistrer` et `📁 Ouvrir`)
- Double clic sur un fichier permet de le mettre directement en lecture
- Le bouton `💿 CD Audio` permet l'ajout de toutes les musiques d'un CD dans la playlist, choix du lecteur lors de l'appui sur le bouton. Il est donc possible de créer une playlist mix avec des audios sur CD, mémoire flash, disque dur, ou même lecteur de floppy disc pourquoi pas !

### Onglet `🎬 Vidéo`

<img width="1910" height="665" alt="image" src="https://github.com/user-attachments/assets/27dfb5c8-c66f-4024-a657-2305c4085932" />
<img width="1919" height="1079" alt="image" src="https://github.com/user-attachments/assets/77a0808e-ed85-43cf-8f50-e2d5dbfdb672" />


- Formats : **MP4, MKV, AVI, MOV, WMV, DTS** + M4V, FLV, WebM, MPEG, TS
- Vitesse variable : **0.25x → 10x**
- **Image par image** : touches `.` (suivant) et `,` (précédent), ou boutons `◁|` `|▷`
- **Sous-titres** : pistes embarquées + chargement externe SRT/ASS
- **Fenêtre détachable** : bouton `⧉` pour détacher, double-clic → plein écran (à régler le double clic plein écran appli direct et non pas double clic détachement de la fenêtre)
- **Playlists mixtes** : audio et vidéo dans la même liste de lecture

### Onglet `🔊 5.1`

<img width="1275" height="594" alt="image" src="https://github.com/user-attachments/assets/dd66bb01-9fff-442c-8602-f2db14395c25" />
<img width="1253" height="159" alt="image" src="https://github.com/user-attachments/assets/9191467b-a811-42cf-84a2-78bf51792de0" />

- Réglage des niveaux de chaque enceinte de 0.0 à 2.0
- Doublement facade avant vers les enceintes arrières pour un son plus immersif, ratio réglable (problème de coupure total du mode à régler)
- Mixage mono vers le caisson de basse, avec fréquence de coupure réglable (40-300Hz) et Gain LFE réglable (0.0 à 2.0)
- Options stéréos (Inverser le stéréo, mixer en mono et angle de séparation de l'audio
- Effet phase avant/arrière : le signal en phase reste à l'avant et le signal hors phase est envoyé aux surrounds, avec intensité réglable

### Onglet `〽Égaliseur`

<img width="1249" height="333" alt="image" src="https://github.com/user-attachments/assets/36af0f51-c9d3-4155-be14-53073b38e924" />
<img width="1247" height="333" alt="image" src="https://github.com/user-attachments/assets/f31be93e-bfd2-41d0-81fe-261a5276d2cd" />

- Égaliseur : On/Off
- 4 Presets : Plat, Bass Boost, Vocal, Rock
- Enregistrement/suppression de preset personnalisés
- 2 Modes de courbe : par bande avec 8 bandes différentes de 20Hz à 16kHz, ou "libre" avec ajout/suppression de points et déplacement pour créer une courbe plus précise

### Onglet `🌀 Rotation`

<img width="1914" height="667" alt="image" src="https://github.com/user-attachments/assets/52b0d3c7-043a-4162-a89e-a1fef8445127" />

- Rotation du son autour de l'auditeur avec vitesse de rotation réglable de 0.6 à 2.0 tours par secondes, avec presets de vitesse
- Réglage de l'étalement angulaire du son (son sur 1 seule enceinte ou sur 3)
- Réglage de l'angle entre source gauche et droite, 0° = Mono et 180° = stéréo parfait (Actuellement peu efficace)

### Onglet `💿 Vinyle`

<img width="1899" height="615" alt="image" src="https://github.com/user-attachments/assets/29ff8c49-d563-4ff9-8c04-1ba60b2402d5" />

- Effet "Vinyle", tentant de reproduire numériquement l'aléatoire et la qualité du son du vinyle (C'est assez expérimental quand même)
- 3 Presets "Neuf", "Usé" ou "Très usé"
- Des kilos d'options pour régler les effets de vitesses, bruit de fond, crépitements etc...

### Onglet `⚙ Paramètres`
**🔉  Audio**
<img width="1908" height="189" alt="image" src="https://github.com/user-attachments/assets/61ba473c-f55d-4979-881c-e11c7ae963a0" />
**⌨  Raccourcis**
<img width="1905" height="624" alt="image" src="https://github.com/user-attachments/assets/6463dbfe-7b48-4892-9f51-23ef4a7c9c72" />
**🎨  Couleurs**
<img width="1903" height="625" alt="image" src="https://github.com/user-attachments/assets/f0177bb7-c1c9-417d-81d4-cad3c5ea4b04" />
**🔤  Polices**
<img width="1893" height="404" alt="image" src="https://github.com/user-attachments/assets/19a12a66-f9ee-4626-99de-60ad3bd388fd" />

- **Raccourcis clavier** : tous remappables, cliquer sur un champ puis appuyer
- **Couleurs** : chaque élément de l'interface personnalisable + 8 presets
- **Polices** : police principale + police monospace avec aperçu en temps réel
- **Audio** : Choix du périphérique de sortie et de la barre de progression (Classique, intensité posée, intensité centrée)

## Installation

L'installation du projet est disponible pour Windows, voir les releases du projet. Il y a un installateur InoSetup, et l'exe de l'appli pour une utilisation portable par ex.

### Au démarrage, l'application vous accueillera avec un joli logo :
<img width="425" height="296" alt="image" src="https://github.com/user-attachments/assets/14aa71e9-b30e-49b9-90d7-e7aaaf894bcd" />

