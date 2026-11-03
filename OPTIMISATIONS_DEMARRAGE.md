# Optimisations du démarrage de SolarSound

## Problèmes identifiés

1. **Double chargement de la session** : La session était chargée deux fois (dans main.py et dans MainWindow.__init__)
2. **Initialisation synchrone des composants lourds** : AudioEngine, VideoEngine, PlaylistManager et PreviewPlayer étaient initialisés de manière synchrone dans le constructeur de MainWindow, bloquant l'affichage de l'interface
3. **Affichage tardif du splash screen** : Le splash screen était affiché après certains chargements
4. **Pas de feedback visuel pendant le chargement** : L'utilisateur ne voyait pas la progression du chargement des composants

## Optimisations implémentées

### 1. Chargement précoce de la session (main.py)
- **Avant** : La session était chargée après l'affichage du splash screen
- **Maintenant** : La session est chargée **avant** l'affichage du splash screen
- **Bénéfice** : La langue est définie avant la construction de l'UI, évitant les problèmes de traduction

### 2. Passage de la session à MainWindow
- **Avant** : MainWindow rechargeait la session dans son __init__
- **Maintenant** : La session est passée comme paramètre à MainWindow
- **Bénéfice** : Évite le double chargement de la session

### 3. Initialisation des composants avant la construction de l'interface
Les panneaux utilisent les moteurs et le gestionnaire de playlists pendant leur construction. `_init_components()` doit donc initialiser ces composants avant `_build_ui()` ; sinon, le démarrage échoue avec un moteur à `None`.

L'initialisation est lancée après l'affichage du splash screen. Celui-ci reste visible pendant le chargement et reçoit les étapes de progression.

### 4. Feedback visuel amélioré
- Le splash screen affiche maintenant la progression du chargement :
  - 15% : Chargement de l'interface
  - 40% : Initialisation du moteur audio
  - 60% : Chargement des playlists
  - 75% : Initialisation du lecteur de prévisualisation
  - 85% : Initialisation du moteur vidéo
  - 90% : Finalisation de l'interface
  - 100% : Prêt

### 5. Méthodes d'initialisation
`_init_components()` initialise tous les composants utilisés par l'interface. Les méthodes `_get_engine()`, `_get_video_engine()`, `_get_playlist_manager()` et `_get_preview_player()` les initialisent également si un appelant les sollicite avant leur initialisation.

## Fichiers modifiés

1. **main.py**
   - Chargement de la session avant l'affichage du splash
   - Définition de la langue avant la création de MainWindow
   - Passage de la session et du splash à MainWindow

2. **ui/main_window.py**
   - Ajout du paramètre `session` et `splash` dans `__init__`
   - Initialisation des composants avant la construction de l'interface
   - Mise à jour de la progression du splash

## Impact sur les performances

### Avant les optimisations :
1. L'utilisateur lance l'application
2. PyQt6 s'initialise
3. La session est chargée
4. Le splash screen s'affiche
5. **MainWindow est créé (BLOQUANT)**
   - AudioEngine est initialisé (lourd)
   - VideoEngine est initialisé (lourd)
   - PlaylistManager charge toutes les playlists (lourd)
   - PreviewPlayer est initialisé (lourd)
   - L'UI est construite
6. La fenêtre principale s'affiche

### Après les optimisations :
1. L'utilisateur lance l'application
2. PyQt6 s'initialise
3. **La session est chargée**
4. **La langue est définie**
5. **Le splash screen s'affiche IMMEDIATEMENT**
6. MainWindow initialise les composants dont ses panneaux dépendent
   - **Le splash screen montre la progression**
7. L'interface est construite avec les composants initialisés
8. La fenêtre principale s'affiche

## Résultat attendu

- **Démarrage visuellement plus rapide** : Le splash screen apparaît avant l'initialisation des composants
- **Feedback utilisateur amélioré** : L'utilisateur voit la progression du chargement
- **Temps de démarrage réel réduit** : Évite le double chargement de la session
- **Expérience utilisateur plus fluide** : Le splash screen reste visible pendant le chargement

## Recommandations supplémentaires (non implémentées)

1. **Cache des playlists** : Stocker les playlists dans un cache pour un chargement plus rapide
2. **Chargement asynchrone des playlists** : Charger les playlists dans un thread séparé
3. **Optimisation des imports** : Pré-compiler les imports avec des outils comme `py2exe` ou `PyInstaller`
4. **Profilage** : Utiliser `cProfile` pour identifier d'autres goulots d'étranglement
5. **Lazy loading des onglets** : Ne charger les onglets que lorsqu'ils sont affichés pour la première fois

## Test

Pour tester les optimisations :
```bash
cd /workspace/github__BalzaTer__SolarSound
python3 main.py
```

L'application devrait démarrer plus rapidement avec un feedback visuel amélioré.
