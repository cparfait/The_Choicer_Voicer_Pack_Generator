# 🎙️ The Choicer Voicer — Createur de packs

*[English version](README.en.md)*

[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20me%20a%20coffee-cristof-FFDD00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black)](https://buymeacoffee.com/cristof)

**Transforme n'importe quelle video en pack jouable, sans jamais ouvrir un terminal
apres le premier lancement.**

Tu colles une adresse YouTube. L'outil telecharge la video, en extrait le son,
la decoupe en repliques sur les sous-titres, sort une image par clip, convertit
la video pour le moteur du jeu, et depose le tout dans le dossier de
[The Choicer Voicer](https://yeahmaybe.itch.io/the-choicer-voicer). Tu relances
le jeu : ton pack est la, avec les sous-titres deja ecrits.

Le reste du temps, tu regardes une forme d'onde et tu deplaces des bords a la
souris. C'est etonnamment satisfaisant.

---

## 🎬 Ca sert a quoi, au juste

**The Choicer Voicer** est un jeu ou l'on imite des extraits audio devant un jury
qui note la performance. Tout son contenu tient dans des **content packs** :
des dossiers de fichiers, avec des regles precises sur les formats, les noms et
les fichiers de configuration.

Fabriquer un pack a la main, c'est decouper des dizaines de clips dans Audacity,
les renommer un par un, ecrire les sous-titres, redimensionner les images,
convertir la video en OGV/Theora — le seul format que Godot accepte — et taper
un `.ini` sans faute de frappe. Pour vingt clips.

Cet outil fait tout ca. Toi, tu choisis la video et tu ajustes les bords.

| Sans l'outil | Avec l'outil |
| --- | --- |
| Telecharger la video a la main | Coller une adresse |
| Reperer les repliques a l'oreille | Decoupe sur les sous-titres ou les silences |
| Taper chaque sous-titre | Deja ecrits, corrigeables en un clic |
| Capturer les images une par une | Une image par clip, prise au milieu |
| `ffmpeg -i ... -c:v libtheora ...` | Case a cocher |
| Renommer 40 fichiers | Bouton « Renommer en serie » |
| Copier dans `%APPDATA%\...` | Bouton « Installer dans le jeu » |

---

## 🚀 Demarrage

```bash
run.bat
```

C'est tout. Le script cree l'environnement Python, installe les dependances et
ouvre <http://127.0.0.1:8730> dans ton navigateur.

Sans le `.bat` :

```bash
python -m venv .venv && .venv\Scripts\pip install -r requirements.txt && .venv\Scripts\python server.py
```

L'interface est une page web, mais **rien ne sort de ta machine** : le serveur
tourne en local, tes projets restent dans `data/`.

### Ce qu'il te faut

| Outil | Role | Obligatoire |
| --- | --- | --- |
| Python 3.10+ | le serveur | oui |
| ffmpeg / ffprobe | toutes les conversions | **oui** |
| yt-dlp | import depuis YouTube et compagnie | installe avec les dependances |
| faster-whisper | transcription automatique | optionnel — `pip install faster-whisper` |
| demucs | piste d'ambiance sans les voix | optionnel — `pip install demucs` |
| rembg + OpenCV | detourage des personnages, image tiree d'une video | optionnel — `pip install rembg onnxruntime opencv-python-headless` |
| pyannote.audio | detection des locuteurs | optionnel — `pip install pyannote.audio` |

Les quatre dernieres ne sont jamais indispensables : sans elles le bouton
correspondant reste grise, et te dit quoi installer.

Le chemin de ffmpeg se regle dans **Reglages**. Le champ accepte l'executable
ou le dossier qui le contient ; vide, l'outil prend celui du `PATH`.

### 🌍 Trois langues

Le selecteur en haut a droite bascule l'interface entre **francais**, **anglais**
et **espagnol** — y compris les messages du serveur et les libelles des packs.
L'outil demarre en anglais, comme le jeu ; le choix est ensuite retenu d'une
session a l'autre.

---

## 🎧 Fabriquer un pack voix, etape par etape

### 1. Importer une source

Trois entrees possibles : un fichier local, un chemin sur le disque (sans copie,
pratique pour un gros fichier), ou **une adresse YouTube**.

A l'import, l'outil ne se contente pas de telecharger. Il extrait la piste audio,
calcule la forme d'onde, sort douze images candidates pour l'icone, recupere la
miniature de la video, et **telecharge les sous-titres** s'il y en a — les
officiels de preference, les automatiques sinon.

> **Si la source a une piste video, le mode Dub s'active tout seul.** Le pack
> embarquera `dub_video.ogv`, que le jeu joue a la fin de la manche avec tes
> prises par-dessus. La case du bloc *Mode Dub* le coupe si tu n'en veux pas,
> et ce choix-la est retenu.

### 2. Decouper

Deux methodes, un bouton chacune :

- **Sur les sous-titres** — un clip par replique, sous-titre deja rempli. La
  plus propre, et de loin. Les sous-titres automatiques de YouTube defilent
  (chaque ligne reste affichee pendant les suivantes) : l'outil recadre chaque
  replique sur la suivante et supprime les repetitions, sinon les clips se
  recouvriraient et chacun heriterait du texte du voisin.
- **Sur les silences** — reglages seuil, duree mini, duree maxi, marge. Utile
  quand la video n'a pas de sous-titres. Les sous-titres disponibles remplissent
  quand meme les clips obtenus.

Dans les deux cas, une image est extraite de la video au milieu de chaque clip :
chaque son arrive avec son image. Et deux details qui changent la qualite du
resultat :

- **une replique trop longue est coupee dans un silence**, jamais au milieu
  d'un mot : l'outil cherche la plus large respiration du passage ;
- **en mode Dub, une replique qui revient plusieurs fois devient un seul clip**
  portant plusieurs `dub_timestamps`. Le format le prevoit, et le jeu doublera
  la meme prise a chacune de ses apparitions.

### 3. Ajuster a la souris

La forme d'onde est le coeur de l'outil. L'apercu video, juste au-dessus, suit
la tete de lecture — tu vois ce que tu entends.

| Geste | Effet |
| --- | --- |
| Clic | deplacer la tete de lecture |
| Alt + glisser (zone vide) | creer un clip |
| Glisser un bord | ajuster le debut / la fin |
| Maj + glisser dans un clip | deplacer le clip |
| Double-clic | ecouter le clip |
| Ctrl + molette | zoomer &middot; molette : defiler |

### 4. Les sous-titres

Par ordre de paresse decroissante :

1. **Ceux de la video** — deja la, deja places, rien a faire ;
2. **Whisper** — transcription francaise locale, si `faster-whisper` est installe ;
3. **Un fichier `.srt` / `.vtt`** que tu importes ;
4. **Au clavier**, dans le tableau des clips.

### 5. Generer, installer, jouer

**Generer** ecrit le pack dans le dossier de travail. **Verifier** liste ce qui
cloche avant. **Installer dans le jeu** copie le tout au bon endroit. Il ne
reste qu'a relancer The Choicer Voicer : le pack apparait dans le menu de
personnalisation.

Un bouton **Exporter en .zip** produit une archive prete a partager.

---

## 📦 Les sept types de packs

Tout est couvert, pas seulement les voix.

| Type | Ce que tu remplaces |
| --- | --- |
| 🎤 **Voix / Dub** | les extraits a imiter — le coeur du jeu |
| ⚖️ **Juges** | les cinq juges : images, voix, bips de score |
| 🧍 **Candidat** | le personnage que tu incarnes sur le plateau |
| 🎩 **Animateur** | l'hote et **ses ~43 repliques**, traduites et editables une par une |
| 🏛️ **Studio** | le decor : musique, modele 3D, ecrans |
| 🖥️ **Menu** | l'habillage du menu principal, jusqu'aux couleurs de l'overlay |
| 💬 **Chatter** | les sons declenches par les mots-cles du chat Twitch |

> **Les personnages posent sur le sol du plateau.** Le jeu ne redimensionne ni
> les juges ni le candidat, et pose le bas de l'image sur le sol. Deux pieges,
> que l'outil corrige a la generation :
>
> - **image trop courte** — la tete passe sous le pupitre. Elle est ramenee a
>   **1000 px de haut**, ratio conserve ;
> - **marge transparente sous les pieds** — le personnage flotte, ou disparait.
>   Les marges vides sont rognees avant la mise a l'echelle.
>
> Reste le **detourage** : une photo rectangulaire s'affiche en entier, fond
> compris. Le bouton *Verifier* te le signale, et le bouton **Detourer**
> (rembg) s'en charge — sur une photo de juge, on passe de 0 % a ~58 % de
> transparence, le profil des packs qui s'affichent bien.
>
> Le bouton **Depuis une video** va meme chercher l'image directement dans un
> film : OpenCV retient le passage ou le visage est le plus net, l'outil
> recadre au format du plateau et detoure dans la foulee.

Le pack **animateur** part d'un modele francais complet : les repliques du
`config_host.json` d'origine sont traduites, avec plusieurs variantes possibles
par ligne (le jeu en tire une au hasard). Variables disponibles :
`<player>`, `<host_name>`, `<round>`, `<points>`, `<character_introduction>`.

---

## 🎥 Le mode Dub

Un pack devient un **pack Dub** des qu'il contient `dub_video.ogv`.

**Quand la video s'affiche-t-elle ?** Pas pendant l'enregistrement : la, le jeu
montre l'image du clip, packs de la communaute compris. La video arrive **a la
fin de la manche**, une fois toutes les repliques enregistrees — le jeu la joue
en entier et pose tes prises dessus, chacune a l'instant de son
`dub_timestamps`. La scene rejouee avec ta voix : c'est le but du mode Dub. Il
faut donc lancer la partie en **Dub Mode**, pas en mode normal.

L'outil s'en charge : conversion en OGV/Theora (qualite et hauteur reglables),
un `.ini` par clip avec son sous-titre et ses timestamps, et un
`_dub_timestamps.md` recapitulatif. Tu peux aussi nommer les personnages et
marquer certains clips comme « Dub seul ».

Deux boutons rendent le mode Dub moins fastidieux, chacun avec sa dependance
optionnelle :

- **Separer les voix de la musique** (demucs) fabrique `_backing_track` depuis
  la source : la bande son d'origine sans les voix, qui passe pendant que tu
  doubles ;
- **Detecter les locuteurs** (pyannote) repartit les clips entre les voix de la
  video et remplit la colonne Personnage. Le modele est sous conditions : il
  faut les accepter sur **les deux** pages du modele
  ([segmentation-3.0](https://hf.co/pyannote/segmentation-3.0) et
  [speaker-diarization-3.1](https://hf.co/pyannote/speaker-diarization-3.1)),
  puis coller dans les Reglages un jeton *read* cree sur
  [hf.co/settings/tokens](https://hf.co/settings/tokens). Il reste sur ta
  machine, dans `data/settings.json`.

Limite conseillee par le jeu : **6 secondes par clip** en mode Dub.

---

## 📐 Ce que le jeu accepte

| Element | Regle |
| --- | --- |
| Audio | WAV, MP3, OGG — moins de 60 s par clip (6 s conseillees en mode Dub) |
| Video | **OGV / Theora uniquement** (limite du moteur Godot) — la conversion est automatique |
| Images | PNG ou JPG, PNG conseille pour la transparence |
| Modele 3D | GLB ou GLTF (packs studio) |
| Personnages | ~500 x 1000 px, non redimensionnes, poses sur le sol du plateau |
| Volume | fort plutot que faible : la notation gere mal les signaux discrets |

L'outil normalise le volume des clips (loudnorm, cible reglable) parce que la
documentation du jeu insiste : un audio trop discret est mal note.

---

## 📁 Ou vont les packs

| OS | Dossier |
| --- | --- |
| Windows | `%APPDATA%\YeahMaybe\ChoicerVoicer\game` |
| macOS | `~/Library/Application Support/YeahMaybe/ChoicerVoicer/game` |
| Linux | `~/.local/share/YeahMaybe/ChoicerVoicer/game` |

L'onglet **Packs installes** liste ce qui s'y trouve deja et cree les dossiers
`packs_*` manquants.

### Fichiers generes

```
packs_voice/<Nom>/
  01_clip.ogg            extrait audio normalise (loudnorm)
  01_clip.txt            sous-titre en clair
  01_clip.ini            metadonnees, en mode Dub (caption, dub_timestamps, dub_characters)
  01_clip.png            image du clip
  _pack_info.ini         title, subtitle, icon, authors, readme
  _author.txt            doublon lu par toutes les versions du jeu
  _subtitle.txt
  _icon.png
  _pack_filler_image.png
  dub_video.ogv          packs Dub
  _backing_track.ogg     ambiance sans les voix
  _dub_timestamps.md     recapitulatif des timestamps
```

Les autres types recoivent leurs fichiers nommes (`judge1..5`, `scoreblip1..5`,
`player`, `host`, `music_studio`, `background`...) et leur `config_*.json` /
`config_chatter.ini`.

---

## 🔧 Quand ca coince

| Symptome | Cause probable |
| --- | --- |
| « Impossible de lancer ffmpeg » | chemin ffmpeg vide **et** absent du PATH — va dans Reglages |
| Un telechargement YouTube echoue | yt-dlp vieillit vite : `pip install -U yt-dlp` |
| Aucun sous-titre trouve | la video n'en a pas ; utilise Whisper ou la decoupe par silences |
| Pas de video dans le jeu | mode Dub decoche : le pack n'a pas de `dub_video.ogv` |
| Les images des clips manquent | la source est un audio seul, ou « Audio seul » a ete choisi a l'import |
| L'apercu video reste noir | le navigateur ne sait pas lire ce codec ; le pack, lui, sera bien converti |
| Le pack n'apparait pas | il faut relancer le jeu, il ne relit pas le dossier a chaud |

---

## 🧩 Organisation du code

```
server.py            point d'entree (FastAPI + uvicorn)
cvpack/
  settings.py        reglages, localisation du dossier de jeu
  specs.py           description de chaque type de pack + modeles de dialogue
  media.py           ffmpeg : analyse, silences, decoupe, normalisation, OGV, images
  subs.py            SRT / WebVTT / JSON3 -> repliques exploitables
  clips.py           fusion des repliques repetees
  ytdl.py            import et sous-titres via yt-dlp
  transcribe.py      faster-whisper (optionnel)
  separate.py        piste d'ambiance par demucs (optionnel)
  portrait.py        detourage rembg, image tiree d'une video (optionnel)
  diarize.py         detection des locuteurs par pyannote (optionnel)
  inifmt.py          format INI « a la Godot » des packs
  project.py         projets sur disque
  build.py           generation, installation, export zip, validation
  jobs.py            taches de fond avec progression
  api.py             routes HTTP
web/
  index.html, style.css
  app.js             interface
  i18n.js            traduction fr / en / es
  waveform.js        forme d'onde canvas (sans dependance externe)
data/                projets et reglages (local, non versionne)
```

Aucune dependance front : pas de build, pas de `node_modules`. Tu modifies
`app.js`, tu rafraichis la page.

---

## 📚 Sources de la specification

- documentation interne du jeu (menu **Extras**, ecrans de format), la plus complete ;
- [guide officiel](https://thechoicervoicer.neocities.org/v2/content_guide) ;
- packs communautaires reels, pour les usages que la doc ne mentionne pas.

En cas de divergence, la doc interne fait foi sur ce qui est **supporte**, les
packs reels sur ce qui est **repandu**.

---

## ☕ Soutenir le projet

L'outil est gratuit et le restera. S'il t'a evite trois heures d'Audacity, tu
peux offrir un cafe :

[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20me%20a%20coffee-cristof-FFDD00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black)](https://buymeacoffee.com/cristof)

---

## ⚖️ Une derniere chose

Cet outil telecharge ce que tu lui demandes de telecharger. **N'utilise que des
contenus que tu as le droit de reutiliser**, et cite les auteurs dans le pack —
le champ est prevu pour ca.

Projet non officiel, sans lien avec YeahMaybe.
