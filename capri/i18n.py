"""The interface's own words, in her eight languages.

Her chat already answers in whatever language you talk to her in (persona.py). This module is for the *interface*:
the right-click menu, the tray tooltip, the dialogs. Pick a language in her menu (Language -> ...), or leave it on
Auto and it follows the system's language when that's one of the eight; anything else falls back to English.
"""
from __future__ import annotations

LANGS = {
    "en": "English",
    "es": "Español",
    "pt": "Português",
    "fr": "Français",
    "ru": "Русский",
    "it": "Italiano",
    "de": "Deutsch",
    "pl": "Polski",
}

STRINGS: dict[str, dict[str, str]] = {
    "menu.talk": {
        "en": "Talk to her", "es": "Habla con ella", "pt": "Falar com ela", "fr": "Lui parler",
        "ru": "Поговорить с ней", "it": "Parlale", "de": "Mit ihr reden", "pl": "Porozmawiaj z nią",
    },
    "menu.mini": {
        "en": "Go mini", "es": "Modo mini", "pt": "Modo mini", "fr": "Mode mini",
        "ru": "Мини-режим", "it": "Modalità mini", "de": "Mini-Modus", "pl": "Tryb mini",
    },
    "menu.full": {
        "en": "Back to full size", "es": "Volver al tamaño completo", "pt": "Voltar ao tamanho normal",
        "fr": "Revenir à la taille normale", "ru": "Вернуть полный размер", "it": "Torna alla dimensione piena",
        "de": "Zurück zur vollen Größe", "pl": "Wróć do pełnego rozmiaru",
    },
    "menu.roam": {
        "en": "Roam the grid", "es": "Rondar por la pantalla", "pt": "Passear pela tela",
        "fr": "Se balader à l'écran", "ru": "Гулять по экрану", "it": "Gira per lo schermo",
        "de": "Auf dem Bildschirm wandern", "pl": "Wędruj po ekranie",
    },
    "menu.quit": {
        "en": "Quit", "es": "Salir", "pt": "Sair", "fr": "Quitter", "ru": "Выход", "it": "Esci",
        "de": "Beenden", "pl": "Wyjdź",
    },
    "tray.tip": {
        "en": "Capri  //  click: go mini / back to full size",
        "es": "Capri  //  clic: modo mini / tamaño completo",
        "pt": "Capri  //  clique: modo mini / tamanho normal",
        "fr": "Capri  //  clic : mode mini / taille normale",
        "ru": "Capri  //  клик: мини-режим / полный размер",
        "it": "Capri  //  clic: modalità mini / dimensione piena",
        "de": "Capri  //  Klick: Mini-Modus / volle Größe",
        "pl": "Capri  //  klik: tryb mini / pełny rozmiar",
    },
    "menu.ears": {
        "en": "Ears", "es": "Oídos", "pt": "Ouvidos", "fr": "Oreilles", "ru": "Уши", "it": "Orecchie",
        "de": "Ohren", "pl": "Uszy",
    },
    "ears.hold": {
        "en": "Hold to talk", "es": "Mantener para hablar", "pt": "Segurar para falar",
        "fr": "Maintenir pour parler", "ru": "Удерживать, чтобы говорить", "it": "Tieni premuto per parlare",
        "de": "Zum Sprechen halten", "pl": "Przytrzymaj, aby mówić",
    },
    "ears.auto": {
        "en": "Auto (always listening)", "es": "Auto (siempre escuchando)", "pt": "Auto (sempre ouvindo)",
        "fr": "Auto (toujours à l'écoute)", "ru": "Авто (всегда слушает)", "it": "Auto (sempre in ascolto)",
        "de": "Auto (hört immer zu)", "pl": "Auto (zawsze słucha)",
    },
    "ears.off": {
        "en": "Off", "es": "Apagado", "pt": "Desligado", "fr": "Désactivé", "ru": "Выкл", "it": "Spento",
        "de": "Aus", "pl": "Wyłączone",
    },
    "ears.key": {
        "en": "Change talk key  (now {combo})", "es": "Cambiar tecla de voz  (ahora {combo})",
        "pt": "Mudar tecla de fala  (agora {combo})", "fr": "Changer la touche  (actuellement {combo})",
        "ru": "Сменить клавишу  (сейчас {combo})", "it": "Cambia tasto  (ora {combo})",
        "de": "Sprechtaste ändern  (jetzt {combo})", "pl": "Zmień klawisz  (teraz {combo})",
    },
    "ears.mic": {
        "en": "Mic", "es": "Micrófono", "pt": "Microfone", "fr": "Micro", "ru": "Микрофон",
        "it": "Microfono", "de": "Mikrofon", "pl": "Mikrofon",
    },
    "ears.model": {
        "en": "Model", "es": "Modelo", "pt": "Modelo", "fr": "Modèle", "ru": "Модель", "it": "Modello",
        "de": "Modell", "pl": "Model",
    },
    "ears.default": {
        "en": "System default", "es": "Predeterminado del sistema", "pt": "Padrão do sistema",
        "fr": "Par défaut du système", "ru": "Системный по умолчанию", "it": "Predefinito di sistema",
        "de": "Systemstandard", "pl": "Domyślny systemowy",
    },
    "toggle.vibe": {
        "en": "Vibe to the music", "es": "Vibrar con la música", "pt": "Vibrar com a música",
        "fr": "Vibrer sur la musique", "ru": "Вибрация под музыку", "it": "Vibrare con la musica",
        "de": "Zur Musik wippen", "pl": "Wibruj do muzyki",
    },
    "toggle.eyes": {
        "en": "Watch my screen", "es": "Mirar mi pantalla", "pt": "Ver minha tela",
        "fr": "Regarder mon écran", "ru": "Смотреть на мой экран", "it": "Guarda il mio schermo",
        "de": "Auf meinen Bildschirm schauen", "pl": "Patrz na mój ekran",
    },
    "toggle.chatter": {
        "en": "Chatter / react  (she talks on her own)", "es": "Charlar / reaccionar  (habla por su cuenta)",
        "pt": "Papear / reagir  (ela fala sozinha)", "fr": "Papoter / réagir  (elle parle toute seule)",
        "ru": "Болтать / реагировать  (говорит сама)", "it": "Chiacchiera / reagisci  (parla da sola)",
        "de": "Plappern / reagieren  (sie redet von selbst)", "pl": "Gadaj / reaguj  (mówi sama)",
    },
    "toggle.reactions": {
        "en": "React to videos, chats && what I type",
        "es": "Reaccionar a vídeos, chats y lo que escribo",
        "pt": "Reagir a vídeos, chats e ao que eu digito",
        "fr": "Réagir aux vidéos, chats et à ce que je tape",
        "ru": "Реагировать на видео, чаты и мой ввод",
        "it": "Reagisci a video, chat e a ciò che scrivo",
        "de": "Auf Videos, Chats und mein Tippen reagieren",
        "pl": "Reaguj na filmy, czaty i to, co piszę",
    },
    "toggle.game": {
        "en": "Game mode  (quiet while I play)", "es": "Modo juego  (callada mientras juego)",
        "pt": "Modo jogo  (quieta enquanto jogo)", "fr": "Mode jeu  (silencieuse pendant que je joue)",
        "ru": "Игровой режим  (молчит, пока я играю)", "it": "Modalità gioco  (silenziosa mentre gioco)",
        "de": "Spielmodus  (still, während ich spiele)", "pl": "Tryb gry  (cicho, gdy gram)",
    },
    "toggle.quiet": {
        "en": "Leave me alone  (no watching, no chatter)", "es": "Déjame en paz  (sin mirar, sin charla)",
        "pt": "Me deixa em paz  (sem olhar, sem papear)", "fr": "Fiche-moi la paix  (pas de regard, pas de blabla)",
        "ru": "Оставь меня в покое  (не смотрит, не болтает)", "it": "Lasciami in pace  (niente sguardi, niente chiacchiere)",
        "de": "Lass mich in Ruhe  (kein Schauen, kein Plappern)", "pl": "Zostaw mnie w spokoju  (bez patrzenia, bez gadania)",
    },
    "menu.skins": {
        "en": "Skins", "es": "Aspecto", "pt": "Aparência", "fr": "Apparence", "ru": "Внешний вид",
        "it": "Aspetto", "de": "Aussehen", "pl": "Wygląd",
    },
    "menu.size": {
        "en": "Size", "es": "Tamaño", "pt": "Tamanho", "fr": "Taille", "ru": "Размер", "it": "Dimensione",
        "de": "Größe", "pl": "Rozmiar",
    },
    "size.tiny": {
        "en": "Tiny", "es": "Diminuta", "pt": "Minúscula", "fr": "Minuscule", "ru": "Крошка", "it": "Minuscola",
        "de": "Winzig", "pl": "Malutka",
    },
    "size.small": {
        "en": "Small", "es": "Pequeña", "pt": "Pequena", "fr": "Petite", "ru": "Маленькая", "it": "Piccola",
        "de": "Klein", "pl": "Mała",
    },
    "size.medium": {
        "en": "Medium", "es": "Mediana", "pt": "Média", "fr": "Moyenne", "ru": "Средняя", "it": "Media",
        "de": "Mittel", "pl": "Średnia",
    },
    "size.large": {
        "en": "Large", "es": "Grande", "pt": "Grande", "fr": "Grande", "ru": "Большая", "it": "Grande",
        "de": "Groß", "pl": "Duża",
    },
    "size.huge": {
        "en": "Huge", "es": "Enorme", "pt": "Gigante", "fr": "Énorme", "ru": "Огромная", "it": "Enorme",
        "de": "Riesig", "pl": "Ogromna",
    },
    "menu.brain": {
        "en": "Brain", "es": "Cerebro", "pt": "Cérebro", "fr": "Cerveau", "ru": "Мозг", "it": "Cervello",
        "de": "Gehirn", "pl": "Mózg",
    },
    "brain.none": {
        "en": "No AI  (just her: apps, timers, music... no chatting)",
        "es": "Sin IA  (solo ella: apps, temporizadores, música... sin charla)",
        "pt": "Sem IA  (só ela: apps, timers, música... sem conversa)",
        "fr": "Sans IA  (juste elle : applis, minuteurs, musique... pas de discussion)",
        "ru": "Без ИИ  (только она: приложения, таймеры, музыка... без болтовни)",
        "it": "Niente IA  (solo lei: app, timer, musica... niente chiacchiere)",
        "de": "Keine KI  (nur sie: Apps, Timer, Musik... kein Geplauder)",
        "pl": "Bez AI  (tylko ona: aplikacje, timery, muzyka... bez gadania)",
    },
    "brain.getting": {
        "en": "Getting {what}...", "es": "Descargando {what}...", "pt": "Baixando {what}...",
        "fr": "Téléchargement de {what}...", "ru": "Скачиваю {what}...", "it": "Scaricando {what}...",
        "de": "Lade {what}...", "pl": "Pobieram {what}...",
    },
    "brain.getting.pct": {
        "en": "Getting {what}: {pct}%", "es": "Descargando {what}: {pct}%", "pt": "Baixando {what}: {pct}%",
        "fr": "Téléchargement de {what} : {pct} %", "ru": "Скачиваю {what}: {pct}%", "it": "Scaricando {what}: {pct}%",
        "de": "Lade {what}: {pct}%", "pl": "Pobieram {what}: {pct}%",
    },
    "menu.memory": {
        "en": "Memory", "es": "Memoria", "pt": "Memória", "fr": "Mémoire", "ru": "Память", "it": "Memoria",
        "de": "Gedächtnis", "pl": "Pamięć",
    },
    "memory.see": {
        "en": "See memories", "es": "Ver memorias", "pt": "Ver memórias", "fr": "Voir les souvenirs",
        "ru": "Посмотреть воспоминания", "it": "Vedi ricordi", "de": "Erinnerungen ansehen", "pl": "Zobacz wspomnienia",
    },
    "memory.wipe": {
        "en": "Wipe memory", "es": "Borrar memoria", "pt": "Apagar memória", "fr": "Effacer la mémoire",
        "ru": "Стереть память", "it": "Cancella memoria", "de": "Gedächtnis löschen", "pl": "Wyczyść pamięć",
    },
    "memory.wipe.title": {
        "en": "Wipe her memory?", "es": "¿Borrar su memoria?", "pt": "Apagar a memória dela?",
        "fr": "Effacer sa mémoire ?", "ru": "Стереть её память?", "it": "Cancellare la sua memoria?",
        "de": "Ihr Gedächtnis löschen?", "pl": "Wyczyścić jej pamięć?",
    },
    "memory.wipe.text": {
        "en": "This erases every fact she saved about you and the recent chat she remembers.",
        "es": "Esto borra todos los datos que guardó sobre ti y el chat reciente que recuerda.",
        "pt": "Isto apaga tudo o que ela guardou sobre você e o chat recente que ela lembra.",
        "fr": "Cela efface tous les faits qu'elle a enregistrés sur vous et le chat récent dont elle se souvient.",
        "ru": "Это удалит все факты, которые она сохранила о тебе, и недавний чат.",
        "it": "Questo cancella tutti i fatti che ha salvato su di te e la chat recente che ricorda.",
        "de": "Das löscht alle Fakten, die sie über dich gespeichert hat, und den letzten Chat.",
        "pl": "To usuwa wszystkie fakty, które o tobie zapisała, i ostatni czat.",
    },
    "memory.wipe.info": {
        "en": "{file}  —  it can't be undone.", "es": "{file}  —  no se puede deshacer.",
        "pt": "{file}  —  não dá para desfazer.", "fr": "{file}  —  irréversible.",
        "ru": "{file}  —  это не отменить.", "it": "{file}  —  non si può annullare.",
        "de": "{file}  —  das lässt sich nicht rückgängig machen.", "pl": "{file}  —  tego nie da się cofnąć.",
    },
    "memory.wiped": {
        "en": "Wiped. I don't know you from a hole in the wall now... mostly kidding, choom.",
        "es": "Borrado. Ahora no te conozco ni de vista... es broma, choom.",
        "pt": "Apagado. Agora não te conheço de lugar nenhum... brincadeira, choom.",
        "fr": "Effacé. Je ne te connais plus du tout maintenant... je rigole, choom.",
        "ru": "Стёрто. Теперь я тебя вообще не знаю... шучу, чoom.",
        "it": "Cancellato. Ora non ti conosco più... scherzo, choom.",
        "de": "Gelöscht. Jetzt kenne ich dich überhaupt nicht mehr... war nur Spaß, choom.",
        "pl": "Wyczyszczone. Teraz cię w ogóle nie znam... żartuję, choom.",
    },
    "memory.open_fail": {
        "en": "Couldn't open the shard, choom ({err}). It lives at {path}.",
        "es": "No pude abrir el archivo, choom ({err}). Está en {path}.",
        "pt": "Não consegui abrir o arquivo, choom ({err}). Ele está em {path}.",
        "fr": "Impossible d'ouvrir le fichier, choom ({err}). Il est dans {path}.",
        "ru": "Не смогла открыть файл, чoom ({err}). Он лежит в {path}.",
        "it": "Non sono riuscita ad aprire il file, choom ({err}). È in {path}.",
        "de": "Konnte die Datei nicht öffnen, choom ({err}). Sie liegt in {path}.",
        "pl": "Nie mogłam otworzyć pliku, choom ({err}). Jest w {path}.",
    },
    "menu.credits": {
        "en": "Credits", "es": "Créditos", "pt": "Créditos", "fr": "Crédits", "ru": "Авторы", "it": "Crediti",
        "de": "Credits", "pl": "Autorzy",
    },
    "menu.language": {
        "en": "Language", "es": "Idioma", "pt": "Idioma", "fr": "Langue", "ru": "Язык", "it": "Lingua",
        "de": "Sprache", "pl": "Język",
    },
    "language.auto": {
        "en": "Auto (system)", "es": "Auto (sistema)", "pt": "Auto (sistema)", "fr": "Auto (système)",
        "ru": "Авто (системный)", "it": "Auto (sistema)", "de": "Auto (System)", "pl": "Auto (system)",
    },
    "yes": {
        "en": "Yes", "es": "Sí", "pt": "Sim", "fr": "Oui", "ru": "Да", "it": "Sì", "de": "Ja", "pl": "Tak",
    },
    "no": {
        "en": "No", "es": "No", "pt": "Não", "fr": "Non", "ru": "Нет", "it": "No", "de": "Nein", "pl": "Nie",
    },
}

_lang = "en"


def pick(code: str = "auto") -> str:
    """'auto' -> the system's language when it's one of her eight; anything else -> English."""
    code = (code or "auto").lower()
    if code in LANGS:
        return code
    if code != "auto":  # an explicit code she doesn't speak: English, never the system's
        return "en"
    try:
        from PySide6.QtCore import QLocale

        code = QLocale.system().name().split("_")[0].lower()  # es_ES -> es
    except Exception:
        import locale

        code = (locale.getlocale()[0] or "en").split("_")[0].lower()
    return code if code in LANGS else "en"


def set_lang(code: str = "auto") -> str:
    """Pick the interface language (Auto follows the system). Returns the one in use."""
    global _lang
    _lang = pick(code)
    return _lang


def lang() -> str:
    return _lang


def t(key: str, **kw) -> str:
    """The text for this key in the current language (English when a translation is missing)."""
    row = STRINGS.get(key) or {}
    text = row.get(_lang) or row.get("en") or key
    return text.format(**kw) if kw else text
