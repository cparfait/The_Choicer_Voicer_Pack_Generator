"""Description declarative de chaque type de pack.

Les specs servent a la fois au frontend (generation des formulaires) et au
backend (ecriture des fichiers de config). Sources :
  - documentation interne du jeu (extraite de TheChoicerVoicer_0-5-1 stable.exe)
  - https://thechoicervoicer.neocities.org/v2/content_guide
  - packs communautaires reels (Cartoon Network, Fortnite)
"""

from __future__ import annotations

IMAGE_EXTS = [".png", ".jpg", ".jpeg"]
AUDIO_EXTS = [".wav", ".mp3", ".ogg"]
VIDEO_EXTS = [".ogv"]
MODEL_EXTS = [".glb", ".gltf"]

# Formats sources acceptes en entree : on convertit avec ffmpeg.
SOURCE_VIDEO_EXTS = [".mp4", ".mkv", ".webm", ".mov", ".avi", ".m4v", ".ogv", ".wmv", ".flv"]
SOURCE_AUDIO_EXTS = [".wav", ".mp3", ".ogg", ".m4a", ".aac", ".flac", ".opus", ".wma"]


def _slot(name, label, kind, required=False, help="", exts=None):
    return {
        "name": name,
        "label": label,
        "kind": kind,
        "required": required,
        "help": help,
        "exts": exts or {
            "image": IMAGE_EXTS,
            "audio": AUDIO_EXTS,
            "video": VIDEO_EXTS,
            "model": MODEL_EXTS,
        }[kind],
    }


def _field(key, label, type_, default=None, help="", options=None, group=""):
    return {
        "key": key, "label": label, "type": type_, "default": default,
        "help": help, "options": options or [], "group": group,
    }


JUDGE_SLOTS = []
for i in range(1, 6):
    JUDGE_SLOTS.append(_slot(f"judge{i}", f"Juge {i} — image", "image", required=(i == 1),
                             help="~500x1000 px. Le bas de l'image touche le sol du studio."))
for i in range(1, 6):
    JUDGE_SLOTS.append(_slot(f"judge{i}_voice", f"Juge {i} — voix", "audio",
                             help="Joue quand ce juge vote pour vous."))
for i in range(1, 6):
    JUDGE_SLOTS.append(_slot(f"scoreblip{i}", f"Bip de score {i}", "audio",
                             help="Joue au i-eme vote, quel que soit le juge."))
JUDGE_SLOTS.append(_slot("success", "Panneau de vote (defaut)", "image",
                         help="Ratio 2:1, 512x256 par defaut."))
for i in range(1, 6):
    JUDGE_SLOTS.append(_slot(f"judge{i}_success", f"Panneau de vote — juge {i}", "image",
                             help="Optionnel, remplace le panneau par defaut pour ce juge."))

JUDGE_FIELDS = [
    _field(f"judge{i}.name", f"Nom du juge {i}", "text", "", group="Noms")
    for i in range(1, 6)
] + [
    _field("play_voices_with_blips", "Jouer les bips en meme temps que les voix",
           "bool", True, help="Decoche pour n'entendre que les voix des juges.",
           group="Options"),
]

PLAYER_AUDIO_SLOTS = [
    ("intro_greet", "Presentation par l'animateur"),
    ("game_winner", "Victoire"),
    ("game_loser", "Defaite"),
    ("score_0", "Note de 0"),
    ("score_1", "Note de 1"),
    ("score_2", "Note de 2"),
    ("score_3", "Note de 3"),
    ("score_4", "Note de 4"),
    ("score_5", "Note de 5"),
]

MENU_COLOR_FIELDS = []
for key, label in [("circles", "Cercles"), ("waves", "Vagues"),
                   ("top_gradient", "Degrade haut"), ("bottom_gradient", "Degrade bas")]:
    MENU_COLOR_FIELDS.append(_field(f"background.{key}.on", f"{label} — actif", "bool", False,
                                    group="Fond"))
    MENU_COLOR_FIELDS.append(_field(f"background.{key}.color", f"{label} — couleur", "color8",
                                    "ffffffff", group="Fond"))


SPECS: dict[str, dict] = {
    "voice": {
        "id": "voice",
        "label": "Pack Voix / Dub",
        "folder": "packs_voice",
        "editor": "voice",
        "description": (
            "Le coeur du jeu : une collection d'extraits audio a imiter. "
            "Devient un pack Dub des qu'un fichier dub_video.ogv est present."
        ),
        "slots": [
            _slot("_icon", "Icone du pack", "image",
                  help="Affichee quand le pack est selectionne."),
            _slot("_pack_filler_image", "Image par defaut des clips", "image",
                  help="Utilisee pour tous les clips sans image propre."),
            _slot("_backing_track", "Piste d'ambiance (dub)", "audio",
                  help="Musique/bruitages sans les voix, joues pendant le mode Dub."),
        ],
        "fields": [],
        "config_file": None,
    },
    "judges": {
        "id": "judges",
        "label": "Pack Juges",
        "folder": "packs_judges",
        "editor": "simple",
        "description": "Les cinq juges qui notent vos performances, de gauche a droite (1 a 5).",
        "slots": JUDGE_SLOTS,
        "fields": JUDGE_FIELDS,
        "config_file": "config_judges.json",
    },
    "player": {
        "id": "player",
        "label": "Pack Candidat",
        "folder": "packs_player",
        "editor": "simple",
        "description": "Le personnage que vous incarnez sur le plateau.",
        "slots": [
            _slot("player", "Image du candidat", "image", required=True,
                  help="~500x1000 px, non redimensionnee. Le bas touche le sol."),
        ] + [
            _slot(f"audio_{key}", label, "audio", help="Optionnel.")
            for key, label in PLAYER_AUDIO_SLOTS
        ],
        "fields": [
            _field("name", "Nom du candidat", "text", "Candidat", group="Identite"),
            _field("introduction", "Phrase de presentation", "text",
                   "Le meilleur imitateur du pays :",
                   help="L'animateur dit cette phrase suivie du nom.", group="Identite"),
            _field("color1", "Couleur 1 (pupitre)", "color", "accbd1", group="Couleurs"),
            _field("color2", "Couleur 2 (accent)", "color", "ffffff", group="Couleurs"),
        ],
        "config_file": "config_player.json",
    },
    "host": {
        "id": "host",
        "label": "Pack Animateur",
        "folder": "packs_host",
        "editor": "host",
        "description": (
            "L'animateur qui commente la partie. Tous ses dialogues sont modifiables "
            "— ideal pour une version entierement francaise."
        ),
        "slots": [
            _slot("host", "Image de l'animateur", "image", required=True,
                  help="Redimensionnee a la hauteur de la fenetre, ratio conserve."),
        ],
        "fields": [
            _field("name", "Nom de l'animateur", "text", "Animateur", group="Identite"),
        ],
        "config_file": "config_host.json",
    },
    "studio": {
        "id": "studio",
        "label": "Pack Studio",
        "folder": "packs_studio",
        "editor": "simple",
        "description": "L'environnement du plateau : musique, modele 3D, ecrans.",
        "slots": [
            _slot("music_studio", "Musique du plateau", "audio"),
            _slot("screen", "Video de l'ecran de score", "video",
                  help="OGV uniquement. Jouee en boucle et muette."),
            _slot("model", "Modele 3D du studio", "model",
                  help="GLB ou GLTF. Un gabarit est genere par le jeu a la creation du dossier."),
            _slot("absolute_image", "Image « absolute » (score 6/5)", "image"),
        ],
        "fields": [
            _field("audio.music_studio_loop_start", "Debut de boucle de la musique", "number", 0.0,
                   help="Echantillon de depart pour un WAV, secondes pour un MP3/OGG.",
                   group="Audio"),
            _field("use_builtin_light", "Utiliser l'eclairage integre", "bool", True,
                   help="Decoche si ton modele 3D apporte son propre eclairage. "
                        "Cle documentee sur le site mais absente du binaire 0.5.1 : sans effet "
                        "si ta version ne la lit pas.",
                   group="Rendu"),
            _field("recording_overlay_colors.body", "Overlay — corps", "color", "d1f6ff",
                   group="Couleurs de l'overlay d'enregistrement"),
            _field("recording_overlay_colors.block_border", "Overlay — bordure", "color", "fde700",
                   group="Couleurs de l'overlay d'enregistrement"),
            _field("recording_overlay_colors.playbar", "Overlay — barre de lecture", "color", "cc0000",
                   group="Couleurs de l'overlay d'enregistrement"),
            _field("recording_overlay_colors.record_light", "Overlay — temoin", "color", "7dcde3",
                   group="Couleurs de l'overlay d'enregistrement"),
            _field("recording_overlay_colors.record_backlight", "Overlay — halo du temoin", "color", "b0d8e3",
                   group="Couleurs de l'overlay d'enregistrement"),
            _field("recording_overlay_colors.user_color", "Overlay — voix du joueur", "color", "00ffff",
                   group="Couleurs de l'overlay d'enregistrement"),
            _field("recording_overlay_colors.voice_color", "Overlay — voix du clip", "color", "ff00ff",
                   group="Couleurs de l'overlay d'enregistrement"),
        ],
        "config_file": "config_studio.json",
    },
    "menu": {
        "id": "menu",
        "label": "Pack Menu",
        "folder": "packs_menu",
        "editor": "simple",
        "description": "L'habillage du menu principal : fond, musique, sons de boutons.",
        "slots": [
            _slot("background", "Image de fond", "image"),
            _slot("overlay", "Calque par-dessus le menu", "image",
                  help="Toujours etire a la taille de la fenetre."),
            _slot("unseen_image", "Image « clip jamais entendu »", "image"),
            _slot("no_image", "Image de remplacement des clips", "image"),
            _slot("music_menu", "Musique du menu", "audio"),
            _slot("button_sfx_select", "Son — bouton valider", "audio"),
            _slot("button_sfx_back", "Son — bouton retour", "audio"),
            _slot("button_sfx_hover", "Son — survol", "audio"),
            _slot("button_sfx_decrease", "Son — bouton secondaire", "audio"),
            _slot("video", "Video de fond", "video",
                  help="OGV uniquement. Remplace l'image de fond et tourne en boucle."),
        ],
        "fields": [
            _field("audio.music_menu_loop_start", "Debut de boucle de la musique", "number", 0.0,
                   help="Echantillon pour un WAV, secondes pour un MP3/OGG.", group="Audio"),
            _field("audio.use_video", "Utiliser la video de fond", "bool", True, group="Audio"),
            _field("background.image.use_type", "Mode de l'image de fond", "select", 1,
                   options=[{"value": 0, "label": "0 — etiree"},
                            {"value": 1, "label": "1 — mosaique / defilement"}],
                   group="Fond"),
            _field("background.image.scroll.x", "Defilement X", "number", 0.0, group="Fond"),
            _field("background.image.scroll.y", "Defilement Y", "number", 0.0, group="Fond"),
        ] + MENU_COLOR_FIELDS + [
            _field("background.letterbox.on", "Bandes laterales — actives", "bool", False, group="Fond"),
            _field("background.letterbox.color", "Bandes laterales — couleur", "color", "000095", group="Fond"),
            _field("background.letterbox.accent", "Bandes laterales — accent", "color", "00d5ff", group="Fond"),
            _field("background.overlay.on", "Calque overlay actif", "bool", True, group="Fond"),
            _field("background.clip_disc.state", "Disque de clip — etat", "number", 0, group="Fond"),
            _field("background.clip_disc.color", "Disque de clip — couleur", "color8", "6db8faff", group="Fond"),
            _field("ui.button.color1", "Boutons — couleur 1", "color8", "9dd6f2ff", group="Interface"),
            _field("ui.button.color2", "Boutons — couleur 2", "color8", "cee6f2ff", group="Interface"),
            _field("ui.button.invert", "Boutons — inverser", "bool", False, group="Interface"),
        ],
        "config_file": "config_menu.json",
    },
    "chatter": {
        "id": "chatter",
        "label": "Pack Chatter (Twitch)",
        "folder": "packs_chatter",
        "editor": "chatter",
        "description": "Sons declenches par les mots-cles du chat Twitch.",
        "slots": [
            _slot("_icon", "Icone du pack", "image"),
        ],
        "fields": [
            _field("volume", "Volume des extraits", "number", 1.0,
                   help="1.0 = 100 %.", group="Options"),
        ],
        "config_file": "config_chatter.ini",
    },
}


# --------------------------------------------------------------------------
# Dialogues de l'animateur
# --------------------------------------------------------------------------

# Structure exacte du config_host.json par defaut du jeu (extraite du binaire),
# avec les repliques traduites en francais.
HOST_TEMPLATE_FR = {
    "host_type": "basic",
    "name": "Animateur",
    "match_singleplayer": {
        "intro": {
            "a_welcome": ["Bienvenue dans The Choicer Voicer !\nJe suis <host_name>, et je serai votre animateur pour la partie d'aujourd'hui !"],
            "b_contestant": ["<character_introduction> <player> !"],
            "c_judges": ["...et dans ce coin, nous avons un magnifique jury ! J'ai hate de voir ce que ca va donner."],
            "d_explanation": [
                "Pour ceux qui nous rejoignent, le but est d'imiter le plus fidelement possible des extraits audio, avec sa propre voix.",
                "Les presentations sont faites : place a la premiere manche !",
            ],
        },
        "round": {
            "b_post_record": ["Beau travail ! Ecoutons ce que ca donne."],
            "c_post_listen": ["J'aime bien ! Mais lequel de nos juges votera pour cette performance ?"],
            "round_next": ["Place a la manche <round>. Preparez-vous !"],
            "round_final": ["C'est la derniere manche. Il va falloir tout donner. C'est parti !"],
        },
        "judging": {
            "score_0": ["Le jury n'a pas ete convaincu...\nMais ca ira mieux a la prochaine manche !"],
            "score_1": ["Le jury n'a pas ete convaincu...\nMais ca ira mieux a la prochaine manche !"],
            "score_2": ["Ce score est correct, mais il faudra tout donner pour l'emporter !"],
            "score_3": ["Belle performance ! Le jury est d'accord."],
            "score_4": ["Belle performance ! Le jury est d'accord."],
            "score_5": ["Un score parfait ! Formidable !"],
            "score_6": ["Qu-quoi ?! Votre performance...\nLe jury la declare\nEXACTEMENT identique ! Incroyable !"],
        },
        "end": {
            "final_score": ["Et voila, cette partie est terminee ! Voyons votre score final !"],
            "win_standard": ["Felicitations ! Vous avez gagne la partie ! Excellent travail !"],
            "win_barely": ["Ouah, c'est passe de justesse ! Bien joue !"],
            "win_100": ["Incroyable ! Un sans-faute du debut a la fin ! Vous etes vraiment notre Choicer Voicer !"],
            "lose_standard": ["Pas assez cette fois-ci. Mais on espere vous revoir bientot !"],
            "lose_barely": ["Aie, et c'etait si pres !\nCa fait mal a voir..."],
            "lose_0": ["Ah, hmm...\nEh bien, merci d'etre venu aujourd'hui !"],
        },
    },
    "match_multiplayer": {
        "intro": {
            "a_welcome": ["Bienvenue dans The Choicer Voicer !\nJe suis <host_name>, et je serai votre animateur pour la partie d'aujourd'hui !"],
            "b_contestants": ["Public, un tonnerre d'applaudissements pour nos candidats du jour !"],
            "c_judges": ["...et dans ce coin, nous avons un magnifique jury ! J'ai hate de voir ce que ca va donner."],
            "d_explanation": [
                "Pour ceux qui nous rejoignent, le but du jeu est d'imiter le plus fidelement possible des extraits audio, avec sa propre voix.",
                "Les presentations sont faites : place a la premiere manche !",
            ],
        },
        "round": {
            "a_get_ready": ["<player>,\npreparez-vous, c'est a vous !"],
            "b_post_record": ["Excellent travail a tous ! Ecoutons chacune de vos performances."],
            "c_post_listen": ["Vous avez tous ete formidables ! Mais nos juges seront-ils d'accord ?"],
            "round_next": ["Tres bien, candidats, preparez-vous pour la manche <round> !"],
            "round_final": ["Derniere chance, candidats ! C'est la manche finale. C'est parti !"],
        },
        "judging": {
            "judged_player": ["<points> pour <player> !"],
            "post_judging": ["...et voila le resultat !"],
        },
        "end": {
            "winner": ["Et le vainqueur du jour est <player> !"],
            "tie_win": ["Ca alors, on dirait bien qu'il y a egalite !"],
            "tie_win_start": ["Nos vainqueurs du jour sont <player>..."],
            "tie_win_end": ["...et <player> !"],
            "congrats_goodbye": ["Felicitations ! Nous esperons tous vous revoir dans The Choicer Voicer !"],
            "final_score": ["Et c'est termine, candidats ! Alors, quelle performance sort du lot ?"],
        },
    },
    "twitch_standard": {
        "intro_audience": ["...et <player> va etre juge par VOUS, le public !\nRestez avec nous, ca promet !"],
        "a_audience_turn_1": ["Tres bien, spectateurs, c'est a votre tour !\nLes votes vont ouvrir, preparez-vous !"],
        "b_audience_turn_2": ["Que pensez-vous de cette performance de <player> ? Son sort est entre vos mains !"],
        "c_polls_closed": ["...et les votes sont clos !\nVoyons ce que le public en pense !"],
    },
}

# Version anglaise d'origine, proposee comme point de depart alternatif.
HOST_TEMPLATE_EN = {
    "host_type": "basic",
    "name": "Shae",
    "match_singleplayer": {
        "intro": {
            "a_welcome": ["Welcome to The Choicer Voicer!\nI'm <host_name>, and I'll be your host for today's game!"],
            "b_contestant": ["<character_introduction> <player>!"],
            "c_judges": ["...and in this corner, we have a wonderful panel of judges! I'm excited to see how this pans out."],
            "d_explanation": [
                "For any new viewers at home, the goal is for contestants to expertly match various audio clips, using their own voice.",
                "Now, with introductions out of the way, let's jump into the first round!",
            ],
        },
        "round": {
            "b_post_record": ["Good job! Let's hear how that turned out."],
            "c_post_listen": ["I like it! But which of our judges will vote for your performance?"],
            "round_next": ["It's now time for round <round>. Get ready!"],
            "round_final": ["It's the final round. Time to give it your all. Let's see what we've got!"],
        },
        "judging": {
            "score_0": ["Seems the judges weren't impressed...\nBut you'll do better next round!"],
            "score_1": ["Seems the judges weren't impressed...\nBut you'll do better next round!"],
            "score_2": ["That score's okay, but you'll need to go all-out if you want to win!"],
            "score_3": ["It was a great performance! The judges agree."],
            "score_4": ["It was a great performance! The judges agree."],
            "score_5": ["A perfect score from the judges! Fantastic work!"],
            "score_6": ["Wh-what?! Your performance...\nThe judges have declared it\nan EXACT match! Wow!"],
        },
        "end": {
            "final_score": ["And with that, this match has concluded! Let's see what your final score comes up to!"],
            "win_standard": ["Congratulations! You won the match! Excellent work!"],
            "win_barely": ["Wow, just barely made it! Well done!"],
            "win_100": ["Incredible! You managed a perfect score throughout! You truly are our Choicer Voicer!"],
            "lose_standard": ["Not enough this time around. But we hope to see you again!"],
            "lose_barely": ["Agh, and you were so close, too!\nYou hate to see it..."],
            "lose_0": ["Ah, hmm...\nWell, thank you for coming today!"],
        },
    },
    "match_multiplayer": {
        "intro": {
            "a_welcome": ["Welcome to The Choicer Voicer!\nI'm <host_name>, and I'll be your host for today's game!"],
            "b_contestants": ["Audience, please give a round of applause for today's contestants!"],
            "c_judges": ["...and in this corner, we have a wonderful panel of judges! I'm excited to see how this pans out."],
            "d_explanation": [
                "For any new viewers at home, the goal of the game is for them to expertly match various audio clips, using their own voice.",
                "Now, with introductions out of the way, let's jump into the first round!",
            ],
        },
        "round": {
            "a_get_ready": ["<player>,\nget ready, it's your turn!"],
            "b_post_record": ["Excellent work, everyone! Let's hear each of your performances."],
            "c_post_listen": ["I think you each did wonderfully! But which of our judges will agree?"],
            "round_next": ["Alright contestants, get ready for round <round>!"],
            "round_final": ["Last chance, contestants! It's the final round. Let's see what we've got!"],
        },
        "judging": {
            "judged_player": ["<points> for <player>!"],
            "post_judging": ["...and there you have it!"],
        },
        "end": {
            "winner": ["And it looks like today's winner is <player>!"],
            "tie_win": ["Goodness, it appears we have a tie!"],
            "tie_win_start": ["Our winners for today are <player>..."],
            "tie_win_end": ["...and <player>!"],
            "congrats_goodbye": ["Congratulations! We hope to see you all again on The Choicer Voicer!"],
            "final_score": ["And that's a wrap, contestants! Now, whose performance came out on top?"],
        },
    },
    "twitch_standard": {
        "intro_audience": ["...and <player> is going to be judged by YOU, the audience!\nStay tuned, it's sure to be fun!"],
        "a_audience_turn_1": ["Alright, viewers, now it's your turn!\nThe polls are about to open, so get ready to send in your votes!"],
        "b_audience_turn_2": ["How was this performance by <player>? Their fate is in your hands!"],
        "c_polls_closed": ["...and the polls have closed!\nIt's time to see what the audience thinks!"],
    },
}

# Libelles francais des sections et cles de dialogue, pour l'editeur.
HOST_LABELS = {
    "match_singleplayer": "Partie solo",
    "match_multiplayer": "Partie multijoueur",
    "twitch_standard": "Mode Twitch",
    "intro": "Introduction",
    "round": "Deroulement des manches",
    "judging": "Notation",
    "end": "Fin de partie",
    "a_welcome": "Accueil",
    "b_contestant": "Presentation du candidat",
    "b_contestants": "Presentation des candidats",
    "c_judges": "Presentation du jury",
    "d_explanation": "Explication des regles",
    "a_get_ready": "C'est a vous",
    "b_post_record": "Apres l'enregistrement",
    "c_post_listen": "Apres l'ecoute",
    "round_next": "Manche suivante",
    "round_final": "Derniere manche",
    "judged_player": "Points attribues",
    "post_judging": "Apres la notation",
    "score_0": "Note 0",
    "score_1": "Note 1",
    "score_2": "Note 2",
    "score_3": "Note 3",
    "score_4": "Note 4",
    "score_5": "Note 5",
    "score_6": "Note 6 (match exact)",
    "final_score": "Score final",
    "win_standard": "Victoire",
    "win_barely": "Victoire de justesse",
    "win_100": "Sans-faute",
    "lose_standard": "Defaite",
    "lose_barely": "Defaite de justesse",
    "lose_0": "Defaite totale",
    "winner": "Vainqueur",
    "tie_win": "Egalite",
    "tie_win_start": "Egalite — debut",
    "tie_win_end": "Egalite — fin",
    "congrats_goodbye": "Felicitations et au revoir",
    "intro_audience": "Presentation du public",
    "a_audience_turn_1": "Ouverture des votes",
    "b_audience_turn_2": "Appel au vote",
    "c_polls_closed": "Cloture des votes",
}

HOST_PLACEHOLDERS = [
    ("<player>", "nom du candidat"),
    ("<host_name>", "nom de l'animateur"),
    ("<round>", "numero de la manche"),
    ("<points>", "points obtenus"),
    ("<character_introduction>", "phrase de presentation du candidat"),
]


def public_specs() -> dict:
    """Version envoyee au frontend (avec les extras de l'animateur)."""
    data = {k: dict(v) for k, v in SPECS.items()}
    data["host"]["host_template_fr"] = HOST_TEMPLATE_FR
    data["host"]["host_template_en"] = HOST_TEMPLATE_EN
    data["host"]["host_labels"] = HOST_LABELS
    data["host"]["host_placeholders"] = HOST_PLACEHOLDERS
    data["player"]["audio_assignment_slots"] = PLAYER_AUDIO_SLOTS
    return data
