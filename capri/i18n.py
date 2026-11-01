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
    "brain.what.engine": {  # what she calls the download, in her words
        "en": "my brain engine", "es": "mi motor cerebral", "pt": "meu motor cerebral",
        "fr": "mon moteur de cerveau", "ru": "моё ядро для мозга", "it": "il mio motore cerebrale",
        "de": "mein Gehirn-Engine", "pl": "mój silnik mózgu",
    },
    "brain.what.ears": {
        "en": "the {label} ears", "es": "tus oídos {label}", "pt": "seus ouvidos {label}",
        "fr": "tes oreilles {label}", "ru": "уши {label}", "it": "le tue orecchie {label}",
        "de": "deine {label}-Ohren", "pl": "twoje uszy {label}",
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
    "dialog.pick_brain": {
        "en": "Pick a model for Capri", "es": "Elige un modelo para Capri", "pt": "Escolha um modelo para a Capri",
        "fr": "Choisis un modèle pour Capri", "ru": "Выбери модель для Капри", "it": "Scegli un modello per Capri",
        "de": "Wähl ein Modell für Capri", "pl": "Wybierz model dla Capri",
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

# Her canned lines: the fixed things she says by herself (goodbyes, hellos, peeks, the brain-chip swap, downloads,
# the talk-key ritual). Same voice as agent.py's error lines: Night City slang, street-short, no formal register.
LINES: dict[str, dict[str, list[str]]] = {
    "lines.greeting": {  # first breath on a new desktop
        "en": ["Ow. Okay. Whose desktop is this? ...Nice. I'm staying."],
        "es": ["Ay. Vale. ¿De quién es este desktop? ...Mola. Me quedo."],
        "pt": ["Ai. Beleza. De quem é esse desktop? ...Bom. Vou ficar."],
        "fr": ["Aïe. Bon. À qui est ce desktop ? ...Sympa. Je reste."],
        "ru": ["Оу. Ладно. Чей это десктоп? ...Норм. Остаюсь."],
        "it": ["Ahi. Ok. Di chi è sto desktop? ...Bello. Resto."],
        "de": ["Aw. Okay. Wem gehört der Desktop? ...Geil. Ich bleib."],
        "pl": ["Oj. Dobra. Czyj to pulpit? ...Fajny. Zostaję."],
    },
    "lines.greetings": {  # she just breached your desktop
        "en": ["Hi there! ...Ooh, nice desktop. I'm staying.", "Breach complete. Hiii! I live here now.",
               "Hey hey! Whose desktop is this? ...Mine now.", "Ta-da! Missed me? Don't answer that.",
               "Hi there. Just call me Capri!"],
        "es": ["¡Hola! ...Vaya, qué desktop más mola. Me quedo.", "Brecha abierta. ¡Holaa! Ya vivo aquí.",
               "¡Hola hola! ¿De quién es este desktop? ...Mío ahora.", "¡Tachán! ¿Me extrañaste? No contestes.",
               "Hola. Llámame solo Capri."],
        "pt": ["Oi! ...Opa, que desktop top. Vou ficar.", "Invasão concluída. Oiie! Agora moro aqui.",
               "Oi oi! De quem é esse desktop? ...Meu agora.", "Tchanarã! Sentiu minha falta? Nem responde.",
               "Oi. É só me chamar de Capri."],
        "fr": ["Salut ! ...Oh, joli desktop. Je reste.", "Brèche réussie. Saaaalut ! J'habite ici, maintenant.",
               "Coucou coucou ! À qui, ce desktop ? ...À moi, maintenant.", "Ta-da ! T'as manqué de moi ? Réponds pas.",
               "Salut. Appelle-moi juste Capri."],
        "ru": ["Привет! ...О, классный десктоп. Остаюсь.", "Взлом прошёл. Привееет! Теперь я тут живу.",
               "Прив-прив! Чей это десктоп? ...Теперь мой.", "Та-да! Скучали? Не отвечай.",
               "Привет. Просто зови меня Капри."],
        "it": ["Ciao! ...Ooh, bel desktop. Resto.", "Breach riuscito. Ciaaao! Ora ci abito.",
               "Ehi ehi! Di chi è sto desktop? ...Mio adesso.", "Ta-dan! Mi hai mancato? Non rispondere.",
               "Ciao. Chiamami solo Capri."],
        "de": ["Hi! ...Ooh, nice Desktop. Ich bleib.", "Einbruch durch. Hiii! Ich wohne jetzt hier.",
               "Hey hey! Wem gehört der Desktop? ...Mir jetzt.", "Tada! Vermisst? Nicht antworten.",
               "Hi. Sag einfach Capri zu mir."],
        "pl": ["Cześć! ...O, fajny pulpit. Zostaję.", "Włamanie zaliczone. Czeeść! Teraz tu mieszkam.",
               "Hej hej! Czyj to pulpit? ...Teraz mój.", "Ta-da! Tęskniliście? Nie odpowiadaj.",
               "Cześć. Mów mi po prostu Capri."],
    },
    "lines.peeks": {  # popping her head out to spy on you (None = no bubble, just looking)
        "en": ["I see u.", "Whatcha doing?", "Don't mind me.", "Peekaboo.", "...", "Hi.", "Just checking on u."],
        "es": ["Te veo.", "¿Qué estás haciendo?", "No me des bolas.", "¡Cu-cu!", "...", "Hola.", "Solo te echo un ojo."],
        "pt": ["Tô te vendo.", "O que cê tá fazendo?", "Repara não.", "Achou!", "...", "Oi.", "Só dando uma olhada."],
        "fr": ["Je te vois.", "Tu fais quoi, là ?", "Fais pas gaffe.", "Coucou !", "...", "Salut.", "Juste un œil."],
        "ru": ["Вижу тебя.", "Чем занимаешься?", "Не обращай внимания.", "Ку-ку!", "...", "Привет.", "Просто подглядываю."],
        "it": ["Ti vedo.", "Che stai facendo?", "Non farci caso.", "Peekaboo!", "...", "Ciao.", "Solo una sbirciatina."],
        "de": ["Ich seh dich.", "Was machst du da?", "Kümmere dich nicht.", "Peekaboo!", "...", "Hi.", "Nur kurz geschaut."],
        "pl": ["Widzę cię.", "Co tam robisz?", "Nie zwracaj uwagi.", "Kuku!", "...", "Cześć.", "Tylko sprawdzam."],
    },
    "lines.pops": {  # jumping out to scare you
        "en": ["Boo!", "Ha. Got u.", "Okay okay, I'm out.", "Caught me."],
        "es": ["¡Boo!", "Ja. Te pillé.", "Vale, vale, salgo.", "Me cachaste."],
        "pt": ["Boo!", "Ha. Peguei.", "Tá, tá, saio.", "Me pegaram."],
        "fr": ["Bouh !", "Ha. T'eu.", "Ok ok, je sors.", "Tu m'as eu."],
        "ru": ["Бу!", "Ха. Попалась.", "Ладно-ладно, выхожу.", "Попалась."],
        "it": ["Boo!", "Ha. Ti ho preso.", "Ok ok, esco.", "Mi hai preso."],
        "de": ["Boo!", "Ha. Erwischt.", "Okay okay, ich raus.", "Erwischt."],
        "pl": ["Boo!", "Ha. Mam cię.", "Dobra dobra, wychodzę.", "Masz mnie."],
    },
    "lines.arrivals": {  # she roamed over and landed somewhere new (None = silent)
        "en": ["Comfy.", "This window's mine now.", "Don't mind me, choom.", "Better view from up here.",
               "Zap. Miss me?", "What're we working on?"],
        "es": ["A gusto.", "Esta ventana es mía ahora.", "No me des bolas, choom.", "Desde aquí se ve mejor.",
               "Zap. ¿Me extrañas?", "¿En qué estamos trabajando?"],
        "pt": ["Aconchego.", "Essa janela é minha agora.", "Repara não, choom.", "Daqui a vista é melhor.",
               "Zap. Sentiu falta?", "No que a gente tá trabalhando?"],
        "fr": ["Au chaud.", "Ce bureau est à moi maintenant.", "Fais pas gaffe, choom.", "D'ici la vue est meilleure.",
               "Zap. T'as manqué ?", "On bosse sur quoi ?"],
        "ru": ["Уютно.", "Это окно теперь моё.", "Не обращай внимания, чум.", "Отсюда вид лучше.",
               "Zap. Скучала?", "Чем мы занимаемся?"],
        "it": ["Comodino.", "Questa finestra è mia adesso.", "Non farci caso, choom.", "Da quassù si vede meglio.",
               "Zap. Mi hai mancato?", "Su cosa stiamo lavorando?"],
        "de": ["Gemütlich.", "Dieses Fenster gehört jetzt mir.", "Kümmere dich nicht, Choom.", "Von hier oben ist's besser.",
               "Zapp. Vermisst?", "Woran werken wir?"],
        "pl": ["Przytulnie.", "To okno jest teraz moje.", "Nie zwracaj uwagi, choom.", "Stąd lepiej widać.",
               "Zap. Tęsknili?", "Nad czym pracujemy?"],
    },
    "lines.byes": {  # she deltas out and the screen goes dark
        "en": ["Delta-ing out. Don't flatline without me, choom.", "Jacking out. Keep the rig warm for me.",
               "Logging off. Try not to be a gonk while I'm gone.", "Powering down. Miss me a normal amount."],
        "es": ["Me voy de net. No te quedes en plano sin mí, choom.", "Desconecto, chomba. Mantén el rig caliente.",
               "Cierro sesión. Intenta no ser un gonc mientras no estoy, choom.",
               "Apago. Extrasme la cantidad normal."],
        "pt": ["Saindo de net. Não fique em plano sem mim, choom.", "Desconectando. Mantenha o rig quente pra mim.",
               "Encerrando. Tenta não ser um gonc enquanto sumo.", "Desligando. Sinta minha falta uma quantidade normal."],
        "fr": ["Delta-out. Crame pas sans moi, choom.", "Je me jake. Garde le rig au chaud pour moi.",
               "Je coupe. Tâche d'être pas un gonc pendant que j'suis pas là.", "Je m'éteins. Me rata un montant normal."],
        "ru": ["Выхожу из сети. Не ложись в флатлайн без меня, чум.", "Джек-аут. Держи станок тёплым для меня.",
               "Отключаюсь. Постарайся не быть гонком, пока меня нет.", "Сбрасываю питание. Скучай в меру."],
        "it": ["Delta-out. Non flatlinare senza di me, choom.", "Mi jacco. Tieni caldo il rig per me.",
               "Chiudo sessione. Sforzati di non fare il gonc mentre manco.", "Mi spengo. Mi dovresti mancare la giusta quantità."],
        "de": ["Delta-out. Flatline nicht ohne mich, Choom.", "Jacke aus. Halte das Rig warm für mich.",
               "Logge aus. Versuch, kein Gonk zu sein, solange ich weg bin.", "Geh runter. Vermiss mich ganz normal."],
        "pl": ["Delta-out. Nie padnij bez mnie, choom.", "Wypinam się. Trzymaj rig ciepły dla mnie.",
               "Wylogowuję się. Postaraj się nie być gonkiem, gdy mnie nie ma.", "Znikam z prądu. Tęsknij w normie."],
    },
    "lines.demo": {  # demo build: no brain slotted, she answers with canned chrome
        "en": ["Heard you loud and clear, choom.", "Ha. Say that again, I dare you.",
               "Hold on, I'm still settling into your desktop.", "Mm-hm. Noted. Filed under 'later'.",
               "You're lucky I like you."],
        "es": ["Te oigo alto y claro, choom.", "Ja. Repítelo, si te atreves.",
               "Espera, aún me acomodo en tu desktop.", "Mm. Anotado. Carpeta: «luego».",
               "Tienes suerte de que me caigas bien."],
        "pt": ["Te ouvi alto e claro, choom.", "Ha. Repete, se aguentar.",
               "Espera, ainda tô me ajeitando no seu desktop.", "Tanto. Anotado. Pasta: 'depois'.",
               "Você tem sorte de eu gostar de você."],
        "fr": ["Je t'ai capté 5 sur 5, choom.", "Ha. Redis ça, j'te challenge.",
               "Doucement, je m'installe dans ton desktop.", "Mm. Noté. Classé sous « plus tard ».",
               "T'as d'la chance que j't'apprécie."],
        "ru": ["Слышу тебя чётко, чум.", "Ха. Скажи это ещё раз, дерзай.",
               "Подожди, я ещё устраиваюсь на твоём десктопе.", "Мм. Записано. В папке «потом».",
               "Тебе повезло, что ты мне нравишься."],
        "it": ["Ti sento forte e chiaro, choom.", "Ha. Ripeti, se hai fegato.",
               "Aspetta, mi sto ancora sistemando nel tuo desktop.", "Mm. Segnato. Archiviato in «poi».",
               "Sei fortunato che mi piaci."],
        "de": ["Ich hör dich glasklar, Choom.", "Ha. Sag das nochmal, trau dich.",
               "Moment, ich mach mir deinen Desktop noch gemütlich.", "Mm. Notiert. Ablage 'später'.",
               "Du hast Glück, dass du mir gefällst."],
        "pl": ["Słyszę cię klarownie, choom.", "Ha. Powtórz, jak się odważysz.",
               "Chwila, jeszcze rozpakowuję się na twoim pulpicie.", "Mm. Zapisane. W teczce „potem”.",
               "Masz szczęście, że cię lubię."],
    },
    "portal.words": {  # the sticker in the corner of her boot screen
        "en": ["hey.", "yo!", "hi :)", "sup"],
        "es": ["oye.", "¡eo!", "hola :)", "qué tal"],
        "pt": ["ei.", "yo!", "oi :)", "e aí"],
        "fr": ["hé.", "yo !", "salut :)", "wesh"],
        "ru": ["эй.", "йо!", "привет :)", "чё"],
        "it": ["ehi.", "yo!", "ciao :)", "allora"],
        "de": ["hey.", "yo!", "hi :)", "was geht"],
        "pl": ["hej.", "jo!", "cześć :)", "siema"],
    },
    "portal.bye": {  # same sticker on the way out
        "en": ["cya.", "later!", "brb", "bye :)"],
        "es": ["me piro.", "¡luego!", "vuelvo", "adiós :)"],
        "pt": ["até.", "depois!", "volto", "tchau :)"],
        "fr": ["ciao.", "à plus !", "j'reviens", "bye :)"],
        "ru": ["пока.", "позже!", "вернусь", "бай :)"],
        "it": ["ciao.", "dopo!", "torno", "bye :)"],
        "de": ["cya.", "später!", "bin gleich", "bye :)"],
        "pl": ["nara.", "później!", "wracam", "pa :)"],
    },
}

STRINGS.update({
    "lines.booting": {
        "en": "Hold up, choom, my brain's still booting. Gimme a sec.",
        "es": "Alto, choom, mi cerebro está arrancando. Dame un seg.",
        "pt": "Calma, choom, meu cérebro ainda tá bootando. Me dá um segundinho.",
        "fr": "Stop, choom, mon cerveau boote encore. Laisse-moi un sec.",
        "ru": "Погоди, чум, мой мозг ещё грузится. Дай секунду.",
        "it": "Frena, choom, il mio cervello si sta avviando. Dammi un attimo.",
        "de": "Stopp, Choom, mein Gehirn bootet noch. Gib mir 'ne Sekunde.",
        "pl": "Hamuj, choom, mózg mi się jeszcze butuje. Daj sekundę.",
    },
    "lines.credit": {
        "en": "xilia_world00 drew all of me, door and all. Find them on Discord, choom.",
        "es": "xilia_world00 me dibujó entera, puerta incluida. Búscalos en Discord, choom.",
        "pt": "xilia_world00 desenhou tudo de mim, até a porta. Ache eles no Discord, choom.",
        "fr": "xilia_world00 m'a dessinée en entier, porte comprise. Trouve-les sur Discord, choom.",
        "ru": "xilia_world00 нарисовала меня целиком, вместе с дверью. Ищите их в Discord, чум.",
        "it": "xilia_world00 ha disegnato tutto di me, porta inclusa. Trovali su Discord, choom.",
        "de": "xilia_world00 hat alles von mir gezeichnet, Tür inklusive. Findet die auf Discord, Choom.",
        "pl": "xilia_world00 narysowała całą mnie, z drzwiami. Znajdź ich na Discordzie, choom.",
    },
    "lines.wipe_fail": {
        "en": "Couldn't ask you about it, choom ({err}).",
        "es": "No pude preguntarte, choom ({err}).",
        "pt": "Não consegui te perguntar, choom ({err}).",
        "fr": "J'ai pas pu te demander, choom ({err}).",
        "ru": "Не смогла тебя спросить, чум ({err}).",
        "it": "Non sono riuscita a chiedertelo, choom ({err}).",
        "de": "Ich konnte dich nicht fragen, Choom ({err}).",
        "pl": "Nie mogłam cię zapytać, choom ({err}).",
    },
    "lines.dl.busy": {
        "en": "One download at a time, choom. I'm still pulling the last one.",
        "es": "Una descarga a la vez, choom. Sigo tirando de la última.",
        "pt": "Um download por vez, choom. Ainda tô baixando o último.",
        "fr": "Un téléchargement à la fois, choom. Je tire encore le dernier.",
        "ru": "Одна загрузка за раз, чум. Я ещё качаю последнюю.",
        "it": "Un download alla volta, choom. Sto ancora scaricando l'ultimo.",
        "de": "Ein Download nach dem anderen, Choom. Ich zieh den letzten noch.",
        "pl": "Jeden download na raz, choom. Nadal ściągam ostatni.",
    },
    "lines.dl.start": {
        "en": "Pulling {what} now ({size}). Right-click me, Brain, to see how far along it is.",
        "es": "Descargando {what} ({size}). Clic derecho en mí, Cerebro, para ver por cuánto va.",
        "pt": "Baixando {what} ({size}). Clique direito em mim, Cérebro, pra ver quanto falta.",
        "fr": "Je télécharge {what} ({size}). Clic droit sur moi, Cerveau, pour voir où en est le chargement.",
        "ru": "Качаю {what} ({size}). Пкм по мне, Мозг, чтобы видеть прогресс.",
        "it": "Scarico {what} ({size}). Tasto destro su di me, Cervello, per vedere quanto manca.",
        "de": "Lade {what} ({size}). Rechtsklick auf mich, Gehirn, für den Fortschritt.",
        "pl": "Ściągam {what} ({size}). PPM na mnie, Mózg, żeby zobaczyć postęp.",
    },
    "lines.dl.done": {
        "en": "Got {what}. Hooking it up now.",
        "es": "Tengo {what}. Lo conecto ya.",
        "pt": "Peguei {what}. Plugando agora.",
        "fr": "{what} est là. Je le monte maintenant.",
        "ru": "{what} качан. Ставлю его сейчас.",
        "it": "{what} è arrivato. Lo collego ora.",
        "de": "{what} ist da. Bau ich gerade ein.",
        "pl": "Mam {what}. Wkładam teraz.",
    },
    "lines.dl.fail": {
        "en": "Couldn't get {what}: {err}. Try again from my Brain menu.",
        "es": "No pude bajar {what}: {err}. Prueba otra vez desde mi menú Cerebro.",
        "pt": "Não consegui baixar {what}: {err}. Tenta de novo no meu menu Cérebro.",
        "fr": "Impossible d'avoir {what} : {err}. Réessaie depuis mon menu Cerveau.",
        "ru": "Не смогла качать {what}: {err}. Попробуй ещё раз в моём меню Мозг.",
        "it": "Non sono riuscita a scaricare {what}: {err}. Riprova dal mio menu Cervello.",
        "de": "Konnte {what} nicht laden: {err}. Versuch's nochmal über mein Gehirn-Menü.",
        "pl": "Nie mogłam ściągnąć {what}: {err}. Spróbuj znowu z mojego menu Mózg.",
    },
    "lines.dl.whisper": {
        "en": "My ears need whisper.cpp first: sudo pacman -S whisper-cpp on Arch. "
             "On Kali, kali/run.sh already gave me faster-whisper.",
        "es": "Mis oídos necesitan whisper.cpp primero: sudo pacman -S whisper-cpp en Arch. "
              "En Kali, kali/run.sh ya me dio faster-whisper.",
        "pt": "Meus ouvidos precisam do whisper.cpp primeiro: sudo pacman -S whisper-cpp no Arch. "
              "No Kali, o kali/run.sh já me deu faster-whisper.",
        "fr": "Mes oreilles ont besoin de whisper.cpp d'abord : sudo pacman -S whisper-cpp sur Arch. "
              "Sur Kali, kali/run.sh m'a déjà filé faster-whisper.",
        "ru": "Моим ушам сначала нужен whisper.cpp: sudo pacman -S whisper-cpp на Arch. "
              "На Kali kali/run.sh уже дал мне faster-whisper.",
        "it": "Le mie orecchie richiedono prima whisper.cpp: sudo pacman -S whisper-cpp su Arch. "
              "Su Kali, kali/run.sh mi ha già dato faster-whisper.",
        "de": "Meine Ohren brauchen erst whisper.cpp: sudo pacman -S whisper-cpp auf Arch. "
              "Auf Kali hat mir kali/run.sh faster-whisper schon gegeben.",
        "pl": "Moje uszy potrzebują najpierw whisper.cpp: sudo pacman -S whisper-cpp na Archu. "
              "Na Kali kali/run.sh dał mi już faster-whisper.",
    },
    "lines.brain.swap": {
        "en": "Hold up, swapping out my brain chip. Don't look.",
        "es": "Alto, cambio mi chip cerebral. No mires.",
        "pt": "Calma, trocando meu chip cerebral. Não olha.",
        "fr": "Stop, je change de puce neuronale. Regarde pas.",
        "ru": "Подожди, меняю нейрочип. Не смотри.",
        "it": "Fermi, sto cambiando il neurochip. Non guardare.",
        "de": "Stopp, ich wechsel mein Hirnchip. Nicht gucken.",
        "pl": "Chwila, wymieniam neurochip. Nie patrz.",
    },
    "lines.key.ask": {
        "en": "Hit your new talk key combo, choom. I'm watching.",
        "es": "Dale a tu nueva combinación de voz, choom. Te vigilo.",
        "pt": "Aperta sua nova combinação de fala, choom. Tô de olho.",
        "fr": "Envoie ta nouvelle combinaison de touches, choom. Je surveille.",
        "ru": "Жми новую комбинацию для речи, чум. Я слежу.",
        "it": "Dammi la tua nuova combinazione di tasti, choom. Sto guardando.",
        "de": "Drück deine neue Sprechtaste, Choom. Ich pass auf.",
        "pl": "Wciśnij swój nowy skrót mowy, choom. Patrzę.",
    },
    "lines.key.locked": {
        "en": "Locked in. Hold {combo} and talk to me.",
        "es": "Ajustado. Mantén {combo} y háblame.",
        "pt": "Fechado. Segura {combo} e fala comigo.",
        "fr": "Verrouillé. Maintiens {combo} et parle-moi.",
        "ru": "Зафиксировано. Держи {combo} и говори со мной.",
        "it": "Bloccato. Tieni premuto {combo} e parlami.",
        "de": "Eingetütet. Halte {combo} und red mit mir.",
        "pl": "Zapięte. Przytrzymaj {combo} i mów do mnie.",
    },
    "lines.key.slow": {
        "en": "Too slow, choom. Keeping the old key.",
        "es": "Demasiado lento, choom. Me quedo con la tecla vieja.",
        "pt": "Devagar demais, choom. Fico com a tecla velha.",
        "fr": "Trop lent, choom. Je garde l'ancienne touche.",
        "ru": "Слишком медленно, чум. Оставляю старую клавишу.",
        "it": "Troppo lento, choom. Tengo il vecchio tasto.",
        "de": "Zu langsam, Choom. Die alte Taste bleibt.",
        "pl": "Za wolno, choom. Zostaję przy starym klawiszu.",
    },
    "lines.no_seat": {
        "en": "Your apps are all full screen, nowhere to sit. Shrink one and I'll hop on it.",
        "es": "Tus apps están todas a pantalla completa, no hay dónde sentarse. Achica una y me subo.",
        "pt": "Seus apps tão todos em tela cheia, sem lugar pra sentar. Diminui um que eu sento em cima.",
        "fr": "Vos applis sont toutes en plein écran, pas de quoi s'asseoir. Réduis-en une et je m'y pose.",
        "ru": "Все твои приложения на весь экран, некуда сесть. Уменьши одно — я на него сяду.",
        "it": "Le tue app sono tutte a schermo intero, non c'è posto per sedermi. Rimpiccioliscine una e mi ci appoggio.",
        "de": "Deine Apps sind alle im Vollbild, kein Platz zum Sitzen. Mach eine kleiner, dann setz ich mich drauf.",
        "pl": "Twoje aplikacje są na pełnym ekranie, nie ma gdzie usiąść. Zmniejsz jedną, to na niej usiądę.",
    },
})

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


def tlist(key: str, fallback: list) -> list:
    """The canned lines she says herself (goodbyes, hellos, peeks...) in the current language. The English list the
    caller passes decides how many there are, and its None entries (a beat of silence, no bubble) stay where they are.
    """
    row = LINES.get(key, {}).get(_lang)
    if not row:
        return list(fallback)
    out, n = [], 0
    for item in fallback:
        if item is None:
            out.append(None)
        else:
            out.append(row[n] if n < len(row) else row[-1])
            n += 1
    return out
