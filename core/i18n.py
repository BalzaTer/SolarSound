"""
Internationalisation légère de SolarSound.

Principe volontairement simple (pas de dépendance externe type Qt
Linguist/.ts) : un dictionnaire Python `clé -> {code_langue: texte}`,
une langue courante globale, et une fonction `tr(clé, **kwargs)` que
chaque widget appelle pour obtenir le texte dans la langue active.

Pour ajouter une clé : l'ajouter dans TRANSLATIONS avec au minimum les
entrées "fr" et "en" ; les langues manquantes retombent automatiquement
sur l'anglais, puis sur le français, puis sur la clé elle-même.

Pour changer la langue à chaud (sans redémarrer l'appli), les widgets
peuvent se connecter au signal `i18n_signals.language_changed` et
reconstruire leurs textes via `tr(...)`.
"""

from PyQt6.QtCore import QObject, pyqtSignal

# Langues disponibles : code ISO 639-1 -> nom natif affiché dans le sélecteur.
LANGUAGES = {
    "fr": "Français",
    "en": "English",
    "de": "Deutsch",
    "es": "Español",
    "it": "Italiano",
    "pt": "Português",
    "zh": "中文",
    "ja": "日本語",
    "co": "Corsu",
    "nl": "Nederlands",
    "hi": "हिन्दी",
}

DEFAULT_LANGUAGE = "fr"
FALLBACK_LANGUAGE = "en"

_current_language = DEFAULT_LANGUAGE


class _I18nSignals(QObject):
    """Signal global émis après un changement de langue (code ISO en argument)."""
    language_changed = pyqtSignal(str)


i18n_signals = _I18nSignals()


def get_language() -> str:
    return _current_language


def set_language(code: str):
    """Change la langue active et prévient les widgets abonnés."""
    global _current_language
    if code not in LANGUAGES:
        code = DEFAULT_LANGUAGE
    if code == _current_language:
        return
    _current_language = code
    i18n_signals.language_changed.emit(code)


def tr(key: str, **kwargs) -> str:
    """
    Renvoie le texte associé à `key` dans la langue active.
    `kwargs` permet le formatage type `tr("x.y", n=3)` si le texte
    contient des `{n}`.
    """
    entry = TRANSLATIONS.get(key)
    if entry is None:
        return key
    text = entry.get(_current_language) or entry.get(FALLBACK_LANGUAGE) or entry.get(DEFAULT_LANGUAGE) or key
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError):
            return text
    return text


def tr_tab(key: str) -> str:
    """Renvoie le libellé d'onglet sans son pictogramme intégré à la traduction."""
    text = tr(key)
    _, separator, label = text.partition("  ")
    return label if separator else text


# ────────────────────────────────────────────────────────────────────
# Dictionnaire de traductions.
#
# ⚠ Couverture actuelle : infrastructure complète + textes de la barre
# de statut, de l'onglet "Mes Playlists" (arbre/détails/icônes) et des
# onglets/panneau de Paramètres. Le reste de l'interface (lecteur,
# 5.1, égaliseur, rotation, vinyle...) utilise encore ses textes en
# dur ; ajoutez-y des clés ici et remplacez les chaînes littérales par
# des appels à `tr(...)` au fur et à mesure, panneau par panneau.
# ────────────────────────────────────────────────────────────────────
TRANSLATIONS = {
    # ── Onglets principaux ─────────────────────────────────────────
    "tab.playlist": {
        "fr": "📋  Playlist", "en": "📋  Playlist", "de": "📋  Wiedergabeliste",
        "es": "📋  Lista de reproducción", "it": "📋  Playlist", "pt": "📋  Lista de reprodução",
        "zh": "📋  播放列表", "ja": "📋  プレイリスト", "co": "📋  Lista di lettura",
        "nl": "📋  Afspeellijst", "hi": "📋  प्लेलिस्ट",
    },
    "tab.video": {
        "fr": "🎬  Vidéo", "en": "🎬  Video", "de": "🎬  Video", "es": "🎬  Vídeo",
        "it": "🎬  Video", "pt": "🎬  Vídeo", "zh": "🎬  视频", "ja": "🎬  ビデオ",
        "co": "🎬  Video", "nl": "🎬  Video", "hi": "🎬  वीडियो",
    },
    "tab.my_playlists": {
        "fr": "💾  Mes Playlists", "en": "💾  My Playlists", "de": "💾  Meine Playlists",
        "es": "💾  Mis listas", "it": "💾  Le mie playlist", "pt": "💾  Minhas playlists",
        "zh": "💾  我的播放列表", "ja": "💾  マイプレイリスト", "co": "💾  E mio liste",
        "nl": "💾  Mijn afspeellijsten", "hi": "💾  मेरी प्लेलिस्ट",
    },
    "tab.surround": {
        "fr": "🔊  5.1", "en": "🔊  5.1", "de": "🔊  5.1", "es": "🔊  5.1", "it": "🔊  5.1",
        "pt": "🔊  5.1", "zh": "🔊  5.1", "ja": "🔊  5.1", "co": "🔊  5.1", "nl": "🔊  5.1", "hi": "🔊  5.1",
    },
    "tab.equalizer": {
        "fr": "〽  Égaliseur", "en": "〽  Equalizer", "de": "〽  Equalizer", "es": "〽  Ecualizador",
        "it": "〽  Equalizzatore", "pt": "〽  Equalizador", "zh": "〽  均衡器", "ja": "〽  イコライザー",
        "co": "〽  Equalizatore", "nl": "〽  Equalizer", "hi": "〽  इक्वलाइज़र",
    },
    "tab.rotation": {
        "fr": "🌀  Rotation", "en": "🌀  Rotation", "de": "🌀  Rotation", "es": "🌀  Rotación",
        "it": "🌀  Rotazione", "pt": "🌀  Rotação", "zh": "🌀  旋转", "ja": "🌀  回転",
        "co": "🌀  Rutazione", "nl": "🌀  Rotatie", "hi": "🌀  घूर्णन",
    },
    "tab.vinyl": {
        "fr": "💿  Vinyle", "en": "💿  Vinyl", "de": "💿  Vinyl", "es": "💿  Vinilo",
        "it": "💿  Vinile", "pt": "💿  Vinil", "zh": "💿  黑胶", "ja": "💿  レコード",
        "co": "💿  Vinile", "nl": "💿  Vinyl", "hi": "💿  विनाइल",
    },
    "tab.settings": {
        "fr": "⚙  Paramètres", "en": "⚙  Settings", "de": "⚙  Einstellungen", "es": "⚙  Ajustes",
        "it": "⚙  Impostazioni", "pt": "⚙  Definições", "zh": "⚙  设置", "ja": "⚙  設定",
        "co": "⚙  Parametri", "nl": "⚙  Instellingen", "hi": "⚙  सेटिंग्स",
    },

    # ── Barre de statut ────────────────────────────────────────────
    "status.ready": {
        "fr": "Prêt", "en": "Ready", "de": "Bereit", "es": "Listo", "it": "Pronto",
        "pt": "Pronto", "zh": "就绪", "ja": "準備完了", "co": "Prontu", "nl": "Gereed", "hi": "तैयार",
    },
    "library.indexing": {
        "fr": "Indexation de la bibliothèque…", "en": "Indexing library…", "de": "Bibliothek wird indiziert…",
        "es": "Indexando la biblioteca…", "it": "Indicizzazione della libreria…",
        "pt": "A indexar a biblioteca…", "zh": "正在索引音乐库…", "ja": "ライブラリを索引中…",
        "co": "Indicizazione di a biblioteca…", "nl": "Bibliotheek indexeren…", "hi": "लाइब्रेरी को इंडेक्स किया जा रहा है…",
    },
    # Variante avec compteur : le « … » est remplacé par « 120/480 ».
    "library.indexing_count": {
        "fr": "Indexation de la bibliothèque {current}/{total}",
        "en": "Indexing library {current}/{total}",
        "de": "Bibliothek wird indiziert {current}/{total}",
        "es": "Indexando la biblioteca {current}/{total}",
        "it": "Indicizzazione della libreria {current}/{total}",
        "pt": "A indexar a biblioteca {current}/{total}",
        "zh": "正在索引音乐库 {current}/{total}",
        "ja": "ライブラリを索引中 {current}/{total}",
        "co": "Indicizazione di a biblioteca {current}/{total}",
        "nl": "Bibliotheek indexeren {current}/{total}",
        "hi": "लाइब्रेरी इंडेक्सिंग {current}/{total}",
    },
    "library.index_failed": {
        "fr": "Indexation de la bibliothèque échouée", "en": "Library indexing failed",
        "de": "Indizierung der Bibliothek fehlgeschlagen", "es": "Fallo al indexar la biblioteca",
        "it": "Indicizzazione della libreria non riuscita", "pt": "Falha ao indexar a biblioteca",
        "zh": "音乐库索引失败", "ja": "ライブラリの索引作成に失敗しました",
        "co": "Indicizazione fiascata", "nl": "Bibliotheek indexeren mislukt",
        "hi": "लाइब्रेरी इंडेक्सिंग विफल रही",
    },

    # ── Panneau "Mes Playlists" : mode d'affichage ──────────────────
    "playlists.view.tree": {
        "fr": "🌳 Arbre", "en": "🌳 Tree", "de": "🌳 Baum", "es": "🌳 Árbol", "it": "🌳 Albero",
        "pt": "🌳 Árvore", "zh": "🌳 树状", "ja": "🌳 ツリー", "co": "🌳 Arburu", "nl": "🌳 Boom", "hi": "🌳 ट्री",
    },
    "playlists.view.details": {
        "fr": "📋 Détails", "en": "📋 Details", "de": "📋 Details", "es": "📋 Detalles", "it": "📋 Dettagli",
        "pt": "📋 Detalhes", "zh": "📋 详细信息", "ja": "📋 詳細", "co": "📋 Dettagli", "nl": "📋 Details", "hi": "📋 विवरण",
    },
    "playlists.view.icons": {
        "fr": "🔲 Icônes", "en": "🔲 Icons", "de": "🔲 Symbole", "es": "🔲 Iconos", "it": "🔲 Icone",
        "pt": "🔲 Ícones", "zh": "🔲 图标", "ja": "🔲 アイコン", "co": "🔲 Iconi", "nl": "🔲 Pictogrammen", "hi": "🔲 आइकन",
    },
    "playlists.root": {
        "fr": "🏠 Racine", "en": "🏠 Root", "de": "🏠 Stammverzeichnis", "es": "🏠 Raíz", "it": "🏠 Radice",
        "pt": "🏠 Raiz", "zh": "🏠 根目录", "ja": "🏠 ルート", "co": "🏠 Radica", "nl": "🏠 Basis", "hi": "🏠 रूट",
    },

    "playlists.up_tooltip": {
        "fr": "Remonter au dossier parent", "en": "Go to parent folder", "de": "Zum übergeordneten Ordner",
        "es": "Ir a la carpeta superior", "it": "Vai alla cartella superiore", "pt": "Ir para a pasta superior",
        "zh": "返回上级文件夹", "ja": "親フォルダーへ移動", "co": "Cullà à u cartulare parente",
        "nl": "Naar bovenliggende map", "hi": "मूल फ़ोल्डर पर जाएँ",
    },
    "playlists.col.name": {
        "fr": "Nom", "en": "Name", "de": "Name", "es": "Nombre", "it": "Nome", "pt": "Nome",
        "zh": "名称", "ja": "名前", "co": "Nome", "nl": "Naam", "hi": "नाम",
    },
    "playlists.col.type": {
        "fr": "Type", "en": "Type", "de": "Typ", "es": "Tipo", "it": "Tipo", "pt": "Tipo",
        "zh": "类型", "ja": "種類", "co": "Tipu", "nl": "Type", "hi": "प्रकार",
    },
    "playlists.col.tracks": {
        "fr": "Pistes", "en": "Tracks", "de": "Titel", "es": "Pistas", "it": "Tracce", "pt": "Faixas",
        "zh": "曲目", "ja": "トラック", "co": "Traccie", "nl": "Nummers", "hi": "ट्रैक",
    },
    "playlists.type.folder": {
        "fr": "Dossier", "en": "Folder", "de": "Ordner", "es": "Carpeta", "it": "Cartella", "pt": "Pasta",
        "zh": "文件夹", "ja": "フォルダー", "co": "Cartulare", "nl": "Map", "hi": "फ़ोल्डर",
    },
    "playlists.type.playlist": {
        "fr": "Playlist", "en": "Playlist", "de": "Playlist", "es": "Lista", "it": "Playlist",
        "pt": "Playlist", "zh": "播放列表", "ja": "プレイリスト", "co": "Lista", "nl": "Afspeellijst",
        "hi": "प्लेलिस्ट",
    },
    "playlists.unnamed": {
        "fr": "(Sans nom)", "en": "(Untitled)", "de": "(Ohne Namen)", "es": "(Sin nombre)",
        "it": "(Senza nome)", "pt": "(Sem nome)", "zh": "（未命名）", "ja": "（名称未設定）",
        "co": "(Senza nome)", "nl": "(Naamloos)", "hi": "(अनाम)",
    },

    # ── Panneau Paramètres : onglets ────────────────────────────────
    "settings.tab.audio": {
        "fr": "🔉  Audio", "en": "🔉  Audio", "de": "🔉  Audio", "es": "🔉  Audio", "it": "🔉  Audio",
        "pt": "🔉  Áudio", "zh": "🔉  音频", "ja": "🔉  オーディオ", "co": "🔉  Audio", "nl": "🔉  Audio", "hi": "🔉  ऑडियो",
    },
    "settings.tab.shortcuts": {
        "fr": "⌨  Raccourcis", "en": "⌨  Shortcuts", "de": "⌨  Tastenkürzel", "es": "⌨  Atajos",
        "it": "⌨  Scorciatoie", "pt": "⌨  Atalhos", "zh": "⌨  快捷键", "ja": "⌨  ショートカット",
        "co": "⌨  Scurciatoghji", "nl": "⌨  Sneltoetsen", "hi": "⌨  शॉर्टकट",
    },
    "settings.tab.colors": {
        "fr": "🎨  Couleurs", "en": "🎨  Colors", "de": "🎨  Farben", "es": "🎨  Colores", "it": "🎨  Colori",
        "pt": "🎨  Cores", "zh": "🎨  颜色", "ja": "🎨  カラー", "co": "🎨  Culori", "nl": "🎨  Kleuren", "hi": "🎨  रंग",
    },
    "settings.tab.fonts": {
        "fr": "🔤  Polices", "en": "🔤  Fonts", "de": "🔤  Schriftarten", "es": "🔤  Fuentes", "it": "🔤  Caratteri",
        "pt": "🔤  Fontes", "zh": "🔤  字体", "ja": "🔤  フォント", "co": "🔤  Caratteri", "nl": "🔤  Lettertypen", "hi": "🔤  फ़ॉन्ट",
    },
    "settings.tab.library": {
        "fr": "📁  Bibliothèque", "en": "📁  Library", "de": "📁  Bibliothek", "es": "📁  Biblioteca",
        "it": "📁  Libreria", "pt": "📁  Biblioteca", "zh": "📁  音乐库", "ja": "📁  ライブラリ",
        "co": "📁  Biblioteca", "nl": "📁  Bibliotheek", "hi": "📁  लाइब्रेरी",
    },
    "settings.tab.language": {
        "fr": "🌐  Langue", "en": "🌐  Language", "de": "🌐  Sprache", "es": "🌐  Idioma", "it": "🌐  Lingua",
        "pt": "🌐  Idioma", "zh": "🌐  语言", "ja": "🌐  言語", "co": "🌐  Lingua", "nl": "🌐  Taal", "hi": "🌐  भाषा",
    },
    "settings.language.label": {
        "fr": "Langue de l'interface :", "en": "Interface language:", "de": "Sprache der Oberfläche:",
        "es": "Idioma de la interfaz:", "it": "Lingua dell'interfaccia:", "pt": "Idioma da interface:",
        "zh": "界面语言：", "ja": "インターフェース言語：", "co": "Lingua di l'interfaccia:",
        "nl": "Taal van de interface:", "hi": "इंटरफ़ेस भाषा:",
    },
    "settings.language.restart_notice": {
        "fr": "Certains textes ne changeront qu'au prochain redémarrage.",
        "en": "Some text will only update after restarting the app.",
        "de": "Einige Texte werden erst nach einem Neustart aktualisiert.",
        "es": "Algunos textos solo se actualizarán al reiniciar la aplicación.",
        "it": "Alcuni testi verranno aggiornati solo al riavvio dell'app.",
        "pt": "Alguns textos só serão atualizados após reiniciar a aplicação.",
        "zh": "部分文字需要重新启动应用后才会更新。",
        "ja": "一部のテキストはアプリを再起動すると更新されます。",
        "co": "Certi testi seranu aghjurnati solu à u prossimu riavviu.",
        "nl": "Sommige tekst wordt pas bijgewerkt na het herstarten van de app.",
        "hi": "कुछ टेक्स्ट ऐप को फिर से शुरू करने के बाद ही अपडेट होंगे।",
    },
}
