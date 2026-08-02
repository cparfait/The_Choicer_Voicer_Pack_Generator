/* Traduction de l'interface — francais, anglais, espagnol.
 *
 * Le francais est la langue source : les cles du dictionnaire sont les phrases
 * telles qu'elles apparaissent dans le code et dans les reponses du serveur.
 * Rien n'est donc a traduire pour rester en francais, et une phrase absente du
 * dictionnaire s'affiche en francais plutot que de disparaitre.
 *
 * Deux chemins mènent ici :
 *   - `translateTree(element)` parcourt le DOM ; l'observateur installe par
 *     `watch()` le rappelle sur tout ce qui est ajoute ensuite, ce qui couvre
 *     les vues, les modales et les notifications sans toucher au rendu ;
 *   - `t('%s clips detectes.', 12)` sert aux phrases qui melent texte et
 *     donnees, que le DOM ne peut pas reconnaitre une fois assemblees.
 *
 * Les nombres sont normalises avant recherche : « Clip 3/12 » trouve la cle
 * « Clip %s/%s », puis les nombres sont remis en place.
 */

/* Drapeaux dessines a la main : Windows n'a pas de glyphes pour les emojis
 * de drapeau, qui s'y afficheraient en deux lettres. */
const FLAGS = {
  fr: '<svg viewBox="0 0 60 30" aria-hidden="true"><rect width="20" height="30" fill="#0055A4"/>'
    + '<rect x="20" width="20" height="30" fill="#fff"/><rect x="40" width="20" height="30" fill="#EF4135"/></svg>',
  en: '<svg viewBox="0 0 60 30" aria-hidden="true"><rect width="60" height="30" fill="#012169"/>'
    + '<path d="M0 0 60 30 M60 0 0 30" stroke="#fff" stroke-width="7"/>'
    + '<path d="M0 0 60 30 M60 0 0 30" stroke="#C8102E" stroke-width="4"/>'
    + '<path d="M30 0V30 M0 15H60" stroke="#fff" stroke-width="11"/>'
    + '<path d="M30 0V30 M0 15H60" stroke="#C8102E" stroke-width="6"/></svg>',
  es: '<svg viewBox="0 0 60 30" aria-hidden="true"><rect width="60" height="30" fill="#AA151B"/>'
    + '<rect y="7.5" width="60" height="15" fill="#F1BF00"/></svg>',
};

export const LANGUAGES = [
  { code: 'fr', label: 'Francais', short: 'FR', flag: FLAGS.fr },
  { code: 'en', label: 'English', short: 'EN', flag: FLAGS.en },
  { code: 'es', label: 'Espanol', short: 'ES', flag: FLAGS.es },
];

const COLUMN = { en: 0, es: 1 };
const STORAGE_KEY = 'cv-lang';

/* Cle francaise : [anglais, espagnol]. */
const DICT = {
  /* -- cadre general ---------------------------------------------------- */
  'Createur de packs': ['Pack maker', 'Creador de packs'],
  'Createur de packs — The Choicer Voicer': ['Pack maker — The Choicer Voicer',
    'Creador de packs — The Choicer Voicer'],
  'Projets': ['Projects', 'Proyectos'],
  'Packs installes': ['Installed packs', 'Packs instalados'],
  'Reglages': ['Settings', 'Ajustes'],
  'Aide': ['Help', 'Ayuda'],
  'Langue': ['Language', 'Idioma'],
  '← Projets': ['← Projects', '← Proyectos'],
  'Annuler': ['Cancel', 'Cancelar'],
  'Confirmer': ['Confirm', 'Confirmar'],
  'Ouvrir': ['Open', 'Abrir'],
  'Dupliquer': ['Duplicate', 'Duplicar'],
  'Supprimer': ['Delete', 'Eliminar'],
  'Choisir': ['Choose', 'Elegir'],
  'Retirer': ['Remove', 'Quitar'],
  'Voir': ['View', 'Ver'],
  'Enregistrer': ['Save', 'Guardar'],
  'Rafraichir': ['Refresh', 'Actualizar'],
  'Chargement...': ['Loading...', 'Cargando...'],
  'Aucun fichier': ['No file', 'Sin archivo'],
  'Le serveur ne repond pas': ['The server is not responding', 'El servidor no responde'],
  'Tache en echec': ['Task failed', 'Tarea fallida'],
  'Ecouter': ['Play', 'Escuchar'],
  'Zoomer': ['Zoom in', 'Ampliar'],
  'Configuration': ['Configuration', 'Configuracion'],
  'Options': ['Options', 'Opciones'],
  'Identite': ['Identity', 'Identidad'],
  'Fichiers': ['Files', 'Archivos'],
  'Credits': ['Credits', 'Creditos'],
  'Dub': ['Dub', 'Dub'],
  'Mode Dub': ['Dub mode', 'Modo Dub'],

  /* -- explorateur de fichiers ------------------------------------------ */
  'Choisir un fichier': ['Choose a file', 'Elegir un archivo'],
  'Chemin': ['Path', 'Ruta'],
  'Aller': ['Go', 'Ir'],
  'Dossier parent': ['Parent folder', 'Carpeta principal'],
  'Dossier vide': ['Empty folder', 'Carpeta vacia'],

  /* -- accueil ----------------------------------------------------------- */
  'Nouveau pack': ['New pack', 'Nuevo pack'],
  'Le nom devient le nom du dossier dans le jeu.':
    ['The name becomes the folder name in the game.',
      'El nombre pasa a ser el de la carpeta en el juego.'],
  'Nom du pack': ['Pack name', 'Nombre del pack'],
  'Creer': ['Create', 'Crear'],
  'Mes projets': ['My projects', 'Mis proyectos'],
  'Aucun projet pour le moment.': ['No projects yet.', 'Aun no hay proyectos.'],
  'Modifie le %s': ['Modified %s', 'Modificado el %s'],
  'Donne un nom au pack.': ['Give the pack a name.', 'Ponle un nombre al pack.'],
  'Projet cree.': ['Project created.', 'Proyecto creado.'],
  'Supprimer definitivement « %s » ?': ['Permanently delete "%s"?', '¿Eliminar «%s» definitivamente?'],
  '%s clips': ['%s clips', '%s clips'],

  /* -- generation -------------------------------------------------------- */
  'Generation': ['Build', 'Generacion'],
  'Le pack est d\'abord genere dans le dossier de travail, puis installe dans le jeu.':
    ['The pack is first built in the working folder, then installed in the game.',
      'El pack se genera primero en la carpeta de trabajo y luego se instala en el juego.'],
  'Verifier': ['Check', 'Comprobar'],
  'Generer': ['Build', 'Generar'],
  'Installer dans le jeu': ['Install in the game', 'Instalar en el juego'],
  'Exporter en .zip': ['Export as .zip', 'Exportar en .zip'],
  'Voir la config': ['View config', 'Ver la config'],
  'Ouvrir le dossier': ['Open folder', 'Abrir la carpeta'],
  'Aucun probleme detecte.': ['No problem found.', 'No se detecto ningun problema.'],
  'Sera installe dans : %s': ['Will be installed in: %s', 'Se instalara en: %s'],
  '%s fichiers ecrits dans %s': ['%s files written to %s', '%s archivos escritos en %s'],
  'Pack genere.': ['Pack built.', 'Pack generado.'],
  'Ecraser ?': ['Overwrite?', '¿Sobrescribir?'],
  'Le dossier %s existe deja. Le remplacer ?':
    ['The folder %s already exists. Replace it?', 'La carpeta %s ya existe. ¿Reemplazarla?'],
  'Installe dans %s': ['Installed in %s', 'Instalado en %s'],
  'Pack installe. Relance le jeu pour le voir.':
    ['Pack installed. Restart the game to see it.',
      'Pack instalado. Reinicia el juego para verlo.'],
  'Genere le pack d\'abord.': ['Build the pack first.', 'Genera el pack primero.'],
  'Fichier ajoute.': ['File added.', 'Archivo anadido.'],

  /* -- informations du pack ---------------------------------------------- */
  'Informations du pack': ['Pack information', 'Informacion del pack'],
  'Ecrites dans': ['Written to', 'Se escriben en'],
  'Ecrite dans': ['Written to', 'Se escribe en'],
  'Ecrit dans': ['Written to', 'Se escribe en'],
  '(et en doublon dans _author.txt / _subtitle.txt).':
    ['(and duplicated in _author.txt / _subtitle.txt).',
      '(y por duplicado en _author.txt / _subtitle.txt).'],
  'Titre affiche dans le jeu': ['Title shown in the game', 'Titulo mostrado en el juego'],
  'Sous-titre': ['Subtitle', 'Subtitulo'],
  'Par defaut : nom du dossier': ['Default: folder name', 'Por defecto: nombre de la carpeta'],
  'Auteurs (separes par des virgules)': ['Authors (comma separated)', 'Autores (separados por comas)'],
  'Description / readme': ['Description / readme', 'Descripcion / readme'],
  'Images proposees': ['Suggested images', 'Imagenes propuestas'],
  'Extraites de la video a l\'import. Clique pour definir l\'icone du pack ; le bouton « fond » en fait l\'image par defaut des clips.':
    ['Extracted from the video on import. Click to set the pack icon; the "filler" button makes it the default clip image.',
      'Extraidas del video al importar. Haz clic para definir el icono del pack; el boton «fondo» la convierte en imagen por defecto de los clips.'],
  'Regenerer les propositions': ['Regenerate suggestions', 'Regenerar las propuestas'],
  'Aucune image : la source doit contenir une piste video.':
    ['No image: the source must contain a video track.',
      'Sin imagenes: la fuente debe tener pista de video.'],
  'Icone': ['Icon', 'Icono'],
  'Fond': ['Filler', 'Fondo'],
  'Definir comme icone du pack': ['Set as pack icon', 'Definir como icono del pack'],
  'Icone definie.': ['Icon set.', 'Icono definido.'],
  'Image de fond definie.': ['Filler image set.', 'Imagen de fondo definida.'],
  'Extraction...': ['Extracting...', 'Extrayendo...'],
  '%s images': ['%s images', '%s imagenes'],
  'Fichiers du pack': ['Pack files', 'Archivos del pack'],
  'Les extensions non acceptees par le jeu (video autre qu\'OGV) sont converties a la generation.':
    ['Formats the game does not accept (video other than OGV) are converted at build time.',
      'Los formatos que el juego no acepta (video que no sea OGV) se convierten al generar.'],

  /* -- editeur animateur -------------------------------------------------- */
  'Repartir du modele francais': ['Reset to the French template', 'Volver a la plantilla francesa'],
  'Repartir du modele anglais d\'origine':
    ['Reset to the original English template', 'Volver a la plantilla inglesa original'],
  'Dialogues': ['Dialogue', 'Dialogos'],
  'Une ligne par replique alternative : le jeu en tire une au hasard. Utilise':
    ['One line per alternative: the game picks one at random. Use',
      'Una linea por variante: el juego elige una al azar. Usa'],
  'ou un retour a la ligne dans le champ pour un saut de ligne.':
    ['or a line break in the field for a new line.',
      'o un salto de linea en el campo para partir la frase.'],
  'Variables :': ['Variables:', 'Variables:'],
  'Reinitialiser': ['Reset', 'Reiniciar'],
  'Tous les dialogues personnalises seront perdus. Continuer ?':
    ['All customised dialogue will be lost. Continue?',
      'Se perderan todos los dialogos personalizados. ¿Continuar?'],

  /* -- editeur chatter ---------------------------------------------------- */
  'Sons du chat': ['Chat sounds', 'Sonidos del chat'],
  'Les mots-cles « larges » se declenchent si le mot les contient (insensible a la casse). Les mots-cles « exacts » exigent le mot identique, casse comprise — pratique pour les emotes.':
    ['"Broad" keywords fire when the word contains them (case insensitive). "Exact" keywords require the identical word, case included — handy for emotes.',
      'Las palabras clave «amplias» se activan si la palabra las contiene (sin distinguir mayusculas). Las «exactas» exigen la palabra identica, mayusculas incluidas — util para los emotes.'],
  'Glisse ici tes fichiers audio, ou': ['Drop your audio files here, or', 'Arrastra aqui tus audios, o'],
  'parcourir': ['browse', 'explorar'],
  'Fichier': ['File', 'Archivo'],
  'Type': ['Type', 'Tipo'],
  'Mots-cles': ['Keywords', 'Palabras clave'],
  'Ecoute': ['Preview', 'Escucha'],
  'Large': ['Broad', 'Amplia'],
  'Exact': ['Exact', 'Exacta'],
  'Aucun son.': ['No sound.', 'Ningun sonido.'],
  'clap, bravo': ['clap, bravo', 'clap, bravo'],

  /* -- editeur voix : source ---------------------------------------------- */
  'Source': ['Source', 'Fuente'],
  'Une video ou un fichier audio. Tout est converti par ffmpeg : aucun format a preparer.':
    ['A video or an audio file. ffmpeg converts everything: no format to prepare.',
      'Un video o un archivo de audio. ffmpeg lo convierte todo: no hay que preparar ningun formato.'],
  'Importer un fichier': ['Import a file', 'Importar un archivo'],
  'Choisir sur le disque (sans copie)': ['Pick on disk (no copy)', 'Elegir en el disco (sin copiar)'],
  'Aucune source': ['No source', 'Sin fuente'],
  ' — video': [' — video', ' — video'],
  'Depuis YouTube (ou tout site gere par yt-dlp)':
    ['From YouTube (or any site yt-dlp handles)',
      'Desde YouTube (o cualquier sitio compatible con yt-dlp)'],
  'Video + audio (pour le mode Dub)': ['Video + audio (for Dub mode)', 'Video + audio (para el modo Dub)'],
  'Audio seul (plus rapide)': ['Audio only (faster)', 'Solo audio (mas rapido)'],
  'Importer': ['Import', 'Importar'],
  'La video est telechargee dans le projet, puis traitee comme n\'importe quelle source.':
    ['The video is downloaded into the project, then handled like any other source.',
      'El video se descarga en el proyecto y luego se trata como cualquier fuente.'],
  'A n\'utiliser que sur du contenu que tu as le droit de reutiliser.':
    ['Only use content you have the right to reuse.',
      'Usalo solo con contenido que tengas derecho a reutilizar.'],
  'yt-dlp n\'est pas installe. Dans le dossier de l\'outil :':
    ['yt-dlp is not installed. In the tool folder:',
      'yt-dlp no esta instalado. En la carpeta de la herramienta:'],
  'Source actuelle :': ['Current source:', 'Fuente actual:'],
  'Colle une adresse de video.': ['Paste a video address.', 'Pega la direccion de un video.'],
  'Lecture des informations...': ['Reading information...', 'Leyendo la informacion...'],
  'direct, non importable': ['live stream, cannot be imported', 'directo, no importable'],
  'Telechargement...': ['Downloading...', 'Descargando...'],
  'Envoi du fichier...': ['Uploading the file...', 'Enviando el archivo...'],
  'Source prete.': ['Source ready.', 'Fuente lista.'],
  'Clips de l\'ancienne source': ['Clips from the previous source', 'Clips de la fuente anterior'],
  'Ce projet contient encore %s clip(s) decoupes dans la source precedente. Les supprimer ? (Annuler les conserve tels quels.)':
    ['This project still has %s clip(s) cut from the previous source. Delete them? (Cancel keeps them as they are.)',
      'Este proyecto conserva %s clip(s) cortados de la fuente anterior. ¿Eliminarlos? (Cancelar los mantiene tal cual.)'],

  /* -- editeur voix : decoupe --------------------------------------------- */
  'Decoupe automatique': ['Automatic splitting', 'Corte automatico'],
  'Detecte les silences et fabrique un clip par prise de parole. Tu peux ensuite tout ajuster a la souris.':
    ['Detects silences and makes one clip per utterance. You can then adjust everything with the mouse.',
      'Detecta los silencios y crea un clip por intervencion. Despues puedes ajustarlo todo con el raton.'],
  'Seuil de silence (dB)': ['Silence threshold (dB)', 'Umbral de silencio (dB)'],
  'Silence minimum (s)': ['Minimum silence (s)', 'Silencio minimo (s)'],
  'Duree mini d\'un clip (s)': ['Minimum clip length (s)', 'Duracion minima de un clip (s)'],
  'Duree maxi d\'un clip (s)': ['Maximum clip length (s)', 'Duracion maxima de un clip (s)'],
  'Marge autour (s)': ['Padding (s)', 'Margen alrededor (s)'],
  'Prefixe des noms': ['Name prefix', 'Prefijo de los nombres'],
  'Decouper': ['Split', 'Cortar'],
  'Remplacer les clips existants': ['Replace existing clips', 'Reemplazar los clips existentes'],
  'Extraire une image par clip depuis la video':
    ['Extract one image per clip from the video',
      'Extraer una imagen por clip del video'],
  '%s clips detectes.': ['%s clips detected.', '%s clips detectados.'],

  /* -- editeur voix : sous-titres ----------------------------------------- */
  'Sous-titres de la source': ['Source subtitles', 'Subtitulos de la fuente'],
  'Quand la video en propose (officiels ou automatiques), ils sont recuperes a l\'import. Ils donnent des decoupes plus propres que la detection de silences, et les sous-titres sont deja ecrits.':
    ['When the video offers them (official or automatic), they are fetched on import. They give cleaner cuts than silence detection, and the subtitles are already written.',
      'Cuando el video los ofrece (oficiales o automaticos), se descargan al importar. Dan cortes mas limpios que la deteccion de silencios, y los subtitulos ya vienen escritos.'],
  'Decouper sur les sous-titres': ['Split on subtitles', 'Cortar por los subtitulos'],
  'Remplir les sous-titres des clips': ['Fill in the clip subtitles', 'Rellenar los subtitulos de los clips'],
  'Ecraser les sous-titres deja saisis': ['Overwrite subtitles already entered', 'Sobrescribir los subtitulos ya escritos'],
  'Importer un .srt / .vtt': ['Import a .srt / .vtt', 'Importar un .srt / .vtt'],
  'Sous-titres': ['Subtitles', 'Subtitulos'],
  'sous-titre': ['subtitle', 'subtitulo'],
  '%s repliques — source : %s': ['%s lines — source: %s', '%s replicas — fuente: %s'],
  ' — langue :': [' — language:', ' — idioma:'],
  'Aucun sous-titre pour cette source. Utilise la decoupe par silences, la transcription Whisper, ou importe un fichier .srt / .vtt.':
    ['No subtitles for this source. Use silence splitting, Whisper transcription, or import a .srt / .vtt file.',
      'No hay subtitulos para esta fuente. Usa el corte por silencios, la transcripcion con Whisper, o importa un archivo .srt / .vtt.'],
  '%s clips crees, sous-titres inclus.': ['%s clips created, subtitles included.', '%s clips creados, subtitulos incluidos.'],
  '%s clips crees depuis les sous-titres.': ['%s clips created from the subtitles.', '%s clips creados a partir de los subtitulos.'],
  '%s sous-titres remplis.': ['%s subtitles filled in.', '%s subtitulos rellenados.'],
  '%s repliques importees.': ['%s lines imported.', '%s replicas importadas.'],
  'sous-titres de la video': ['video subtitles', 'subtitulos del video'],

  /* -- editeur voix : clips ------------------------------------------------ */
  'Clips': ['Clips', 'Clips'],
  'Lire / Pause': ['Play / Pause', 'Reproducir / Pausa'],
  'Lire le clip': ['Play the clip', 'Reproducir el clip'],
  'Ajouter un clip ici': ['Add a clip here', 'Anadir un clip aqui'],
  'Tout voir': ['Fit all', 'Ver todo'],
  'Suivre la lecture': ['Follow playback', 'Seguir la reproduccion'],
  'Voir la video': ['Show the video', 'Ver el video'],
  'L\'image suit la tete de lecture : le son vient de l\'apercu audio, l\'image de la video d\'origine.':
    ['The picture follows the playhead: the sound comes from the audio preview, the picture from the original video.',
      'La imagen sigue al cabezal: el sonido viene de la vista previa de audio y la imagen del video original.'],
  'Le navigateur ne sait pas lire cette video : image indisponible.':
    ['The browser cannot play this video: no picture available.',
      'El navegador no puede reproducir este video: imagen no disponible.'],
  'Clic = deplacer la tete de lecture · Alt+glisser sur une zone vide = creer un clip · glisser un bord = ajuster · Maj+glisser = deplacer le clip · double-clic = ecouter · Ctrl+molette = zoom.':
    ['Click = move the playhead · Alt+drag on an empty area = create a clip · drag an edge = adjust · Shift+drag = move the clip · double-click = listen · Ctrl+wheel = zoom.',
      'Clic = mover el cabezal · Alt+arrastrar en una zona vacia = crear un clip · arrastrar un borde = ajustar · Mayus+arrastrar = mover el clip · doble clic = escuchar · Ctrl+rueda = zoom.'],
  'Transcrire en francais': ['Transcribe in French', 'Transcribir en frances'],
  'Ecraser les sous-titres existants': ['Overwrite existing subtitles', 'Sobrescribir los subtitulos existentes'],
  'faster-whisper non installe — voir Reglages':
    ['faster-whisper not installed — see Settings', 'faster-whisper no instalado — ver Ajustes'],
  'Chargement du modele (premiere fois : telechargement)...':
    ['Loading the model (first time: download)...',
      'Cargando el modelo (la primera vez, se descarga)...'],
  '%s clips transcrits.': ['%s clips transcribed.', '%s clips transcritos.'],
  'Nom du fichier': ['File name', 'Nombre del archivo'],
  'Debut': ['Start', 'Inicio'],
  'Fin': ['End', 'Fin'],
  'Duree': ['Length', 'Duracion'],
  'Image': ['Image', 'Imagen'],
  'Personnage': ['Character', 'Personaje'],
  'personnage': ['character', 'personaje'],
  'Dub seul': ['Dub only', 'Solo Dub'],
  'Uniquement en mode Dub': ['Dub mode only', 'Solo en modo Dub'],
  'Image de la video a cet instant': ['Frame of the video at this point', 'Imagen del video en este momento'],
  'Aucun clip. Importe une source puis lance la decoupe.':
    ['No clips. Import a source then run the splitting.',
      'Sin clips. Importa una fuente y lanza el corte.'],
  '%s clips actifs — %s au total': ['%s active clips — %s in total', '%s clips activos — %s en total'],
  ' — %s depassent %s s': [' — %s exceed %s s', ' — %s superan %s s'],
  'Images depuis la video': ['Images from the video', 'Imagenes desde el video'],
  'Images %s': ['Images %s', 'Imagenes %s'],
  'Images...': ['Images...', 'Imagenes...'],
  'Images extraites.': ['Images extracted.', 'Imagenes extraidas.'],
  'Renommer en serie': ['Rename in series', 'Renombrar en serie'],
  'Tout supprimer': ['Delete all', 'Eliminar todo'],
  'Supprimer tous les clips de ce projet ?':
    ['Delete every clip in this project?', '¿Eliminar todos los clips de este proyecto?'],
  'Selectionne un clip.': ['Select a clip.', 'Selecciona un clip.'],

  /* -- editeur voix : mode dub --------------------------------------------- */
  'Un pack devient un pack Dub des qu\'il contient':
    ['A pack becomes a Dub pack as soon as it contains',
      'Un pack se convierte en pack Dub en cuanto contiene'],
  '. La video source est convertie en OGV/Theora — le seul format lu par Godot. Limite conseillee : 6 s par clip.':
    ['. The source video is converted to OGV/Theora — the only format Godot reads. Recommended limit: 6 s per clip.',
      '. El video fuente se convierte a OGV/Theora, el unico formato que lee Godot. Limite recomendado: 6 s por clip.'],
  'Generer un pack Dub a partir de la video source':
    ['Build a Dub pack from the source video', 'Generar un pack Dub a partir del video fuente'],
  'Qualite OGV (0-10)': ['OGV quality (0-10)', 'Calidad OGV (0-10)'],
  'Hauteur maxi (px)': ['Maximum height (px)', 'Altura maxima (px)'],
  'Personnages (separes par des virgules)': ['Characters (comma separated)', 'Personajes (separados por comas)'],
  'Narrateur, Heros': ['Narrator, Hero', 'Narrador, Heroe'],
  'Ajouter le timestamp au nom du fichier (ex. 07_MonClip_44-048)':
    ['Add the timestamp to the file name (e.g. 07_MyClip_44-048)',
      'Anadir la marca de tiempo al nombre del archivo (ej. 07_MiClip_44-048)'],
  'La source actuelle n\'a pas de piste video : ajoute une video pour le mode Dub.':
    ['The current source has no video track: add a video for Dub mode.',
      'La fuente actual no tiene pista de video: anade un video para el modo Dub.'],

  /* -- packs installes ------------------------------------------------------ */
  'Dossier du jeu :': ['Game folder:', 'Carpeta del juego:'],
  'Creer les dossiers manquants': ['Create the missing folders', 'Crear las carpetas que faltan'],
  'Aucun pack.': ['No pack.', 'Ningun pack.'],
  '%s fichiers': ['%s files', '%s archivos'],
  ' — pack Dub': [' — Dub pack', ' — pack Dub'],
  ' — dossier absent': [' — folder missing', ' — carpeta ausente'],
  'Cree : %s': ['Created: %s', 'Creado: %s'],
  'Rien a creer.': ['Nothing to create.', 'Nada que crear.'],

  /* -- reglages -------------------------------------------------------------- */
  'Dossier des packs du jeu': ['Game pack folder', 'Carpeta de packs del juego'],
  'Emplacement standard sous Windows :': ['Standard location on Windows:', 'Ubicacion estandar en Windows:'],
  '. Depuis le jeu : menu principal, bouton d\'ouverture du dossier.':
    ['. From the game: main menu, folder button.',
      '. Desde el juego: menu principal, boton para abrir la carpeta.'],
  'Dossiers detectes : %s': ['Folders found: %s', 'Carpetas detectadas: %s'],
  'Aucun dossier packs_* detecte a cet emplacement.':
    ['No packs_* folder found at this location.',
      'No se detecto ninguna carpeta packs_* en esta ubicacion.'],
  'Indispensable : toutes les conversions passent par lui. Laisse vide pour utiliser celui du PATH. Tu peux indiquer soit l\'executable, soit le dossier qui le contient.':
    ['Required: every conversion goes through it. Leave empty to use the one from PATH. You can give either the executable or the folder holding it.',
      'Imprescindible: todas las conversiones pasan por el. Dejalo vacio para usar el del PATH. Puedes indicar el ejecutable o la carpeta que lo contiene.'],
  'Chemin de ffmpeg (vide = PATH)': ['ffmpeg path (empty = PATH)', 'Ruta de ffmpeg (vacio = PATH)'],
  'Chemin de ffprobe (vide = PATH)': ['ffprobe path (empty = PATH)', 'Ruta de ffprobe (vacio = PATH)'],
  'introuvable': ['not found', 'no encontrado'],
  'Export audio': ['Audio export', 'Exportacion de audio'],
  'Format des clips': ['Clip format', 'Formato de los clips'],
  'Volume cible (LUFS)': ['Target loudness (LUFS)', 'Volumen objetivo (LUFS)'],
  'Normaliser le volume': ['Normalise the volume', 'Normalizar el volumen'],
  'La documentation du jeu insiste : un audio fort marche mieux que l\'inverse, l\'algorithme de notation gere mal les faibles amplitudes.':
    ['The game documentation insists: loud audio works better than quiet, the scoring algorithm handles low amplitudes badly.',
      'La documentacion del juego insiste: un audio fuerte funciona mejor que uno bajo, el algoritmo de puntuacion lleva mal las amplitudes debiles.'],
  'Transcription (faster-whisper)': ['Transcription (faster-whisper)', 'Transcripcion (faster-whisper)'],
  'Installe.': ['Installed.', 'Instalado.'],
  'Non installe. Dans le dossier de l\'outil, lance :':
    ['Not installed. In the tool folder, run:', 'No instalado. En la carpeta de la herramienta, ejecuta:'],
  'Modele': ['Model', 'Modelo'],
  'Materiel': ['Hardware', 'Hardware'],
  '« small » suffit largement pour des sous-titres courts ; « medium » est plus fidele mais nettement plus lent sur CPU.':
    ['"small" is plenty for short subtitles; "medium" is more faithful but much slower on CPU.',
      '«small» basta de sobra para subtitulos cortos; «medium» es mas fiel pero mucho mas lento en CPU.'],
  'Import depuis le web (yt-dlp)': ['Web import (yt-dlp)', 'Importacion desde la web (yt-dlp)'],
  'Disponible': ['Available', 'Disponible'],
  ' — version %s': [' — version %s', ' — version %s'],
  ' (module Python)': [' (Python module)', ' (modulo de Python)'],
  ' (executable)': [' (executable)', ' (ejecutable)'],
  'Non installe. Lance :': ['Not installed. Run:', 'No instalado. Ejecuta:'],
  'yt-dlp evolue vite : si un telechargement echoue,':
    ['yt-dlp moves fast: if a download fails,', 'yt-dlp evoluciona rapido: si falla una descarga,'],
  'resout la plupart des cas.': ['fixes most cases.', 'resuelve la mayoria de los casos.'],
  'Auteur par defaut des nouveaux packs': ['Default author for new packs', 'Autor por defecto de los nuevos packs'],
  'Reglages enregistres.': ['Settings saved.', 'Ajustes guardados.'],
  'ffmpeg est introuvable : les conversions echoueront. Voir Reglages.':
    ['ffmpeg cannot be found: conversions will fail. See Settings.',
      'No se encuentra ffmpeg: las conversiones fallaran. Consulta Ajustes.'],

  /* -- aide -------------------------------------------------------------------- */
  'Comment ca marche': ['How it works', 'Como funciona'],
  'Cree un projet du type voulu (voix, juges, candidat, animateur, studio, menu, chatter).':
    ['Create a project of the type you want (voice, judges, contestant, host, studio, menu, chatter).',
      'Crea un proyecto del tipo que quieras (voz, jueces, concursante, presentador, estudio, menu, chatter).'],
  'Pour un pack voix : importe une video ou un audio, lance la decoupe automatique, ajuste les clips a la souris, puis transcris les sous-titres.':
    ['For a voice pack: import a video or an audio file, run the automatic splitting, adjust the clips with the mouse, then transcribe the subtitles.',
      'Para un pack de voz: importa un video o un audio, lanza el corte automatico, ajusta los clips con el raton y transcribe los subtitulos.'],
  'Genere le pack, puis installe-le : l\'outil ecrit directement dans le dossier du jeu.':
    ['Build the pack, then install it: the tool writes straight into the game folder.',
      'Genera el pack y luego instalalo: la herramienta escribe directamente en la carpeta del juego.'],
  'Relance The Choicer Voicer — le pack apparait dans le menu de personnalisation.':
    ['Restart The Choicer Voicer — the pack appears in the customisation menu.',
      'Reinicia The Choicer Voicer: el pack aparece en el menu de personalizacion.'],
  'Regles imposees par le jeu': ['Rules imposed by the game', 'Reglas que impone el juego'],
  'Element': ['Item', 'Elemento'],
  'Regle': ['Rule', 'Regla'],
  'Audio': ['Audio', 'Audio'],
  'WAV, MP3 ou OGG. Moins de 60 s par clip (6 s conseillees en mode Dub).':
    ['WAV, MP3 or OGG. Under 60 s per clip (6 s recommended in Dub mode).',
      'WAV, MP3 u OGG. Menos de 60 s por clip (6 s recomendados en modo Dub).'],
  'Video': ['Video', 'Video'],
  'OGV / Theora uniquement — Godot ne lit rien d\'autre.':
    ['OGV / Theora only — Godot reads nothing else.',
      'Solo OGV / Theora: Godot no lee nada mas.'],
  'Images': ['Images', 'Imagenes'],
  'PNG ou JPG. PNG conseille pour la transparence.':
    ['PNG or JPG. PNG recommended for transparency.',
      'PNG o JPG. PNG recomendado para la transparencia.'],
  'Modele 3D': ['3D model', 'Modelo 3D'],
  'GLB ou GLTF (packs studio).': ['GLB or GLTF (studio packs).', 'GLB o GLTF (packs de estudio).'],
  'Personnages': ['Characters', 'Personajes'],
  '~500 x 1000 px, non redimensionnes, poses sur le sol du plateau.':
    ['~500 x 1000 px, not resized, standing on the stage floor.',
      '~500 x 1000 px, sin redimensionar, apoyados en el suelo del plato.'],
  'Volume': ['Volume', 'Volumen'],
  'Fort plutot que faible : la notation gere mal les signaux trop discrets.':
    ['Loud rather than quiet: scoring handles faint signals badly.',
      'Mejor fuerte que bajo: la puntuacion lleva mal las senales demasiado debiles.'],
  'Configs': ['Configs', 'Configs'],
  'pour les packs voix et chatter,': ['for voice and chatter packs,', 'para los packs de voz y chatter,'],
  'pour juges, candidat, animateur, studio et menu.':
    ['for judges, contestant, host, studio and menu.',
      'para jueces, concursante, presentador, estudio y menu.'],
  'Fichiers ecrits par l\'outil': ['Files the tool writes', 'Archivos que escribe la herramienta'],
  'Raccourcis de la forme d\'onde': ['Waveform shortcuts', 'Atajos de la forma de onda'],
  'Clic': ['Click', 'Clic'],
  '— deplacer la tete de lecture': ['— move the playhead', '— mover el cabezal'],
  'Alt + glisser': ['Alt + drag', 'Alt + arrastrar'],
  'sur une zone vide — creer un clip': ['on an empty area — create a clip', 'en una zona vacia — crear un clip'],
  'Glisser un bord': ['Drag an edge', 'Arrastrar un borde'],
  '— ajuster le debut ou la fin': ['— adjust the start or the end', '— ajustar el inicio o el final'],
  'Maj + glisser': ['Shift + drag', 'Mayus + arrastrar'],
  'dans un clip — le deplacer': ['inside a clip — move it', 'dentro de un clip — moverlo'],
  'Double-clic': ['Double-click', 'Doble clic'],
  '— ecouter le clip': ['— listen to the clip', '— escuchar el clip'],
  'Ctrl + molette': ['Ctrl + wheel', 'Ctrl + rueda'],
  '— zoomer ·': ['— zoom ·', '— ampliar ·'],
  'molette': ['wheel', 'rueda'],
  '— defiler': ['— scroll', '— desplazar'],
  'Sources': ['Sources', 'Fuentes'],
  'Soutenir le projet': ['Support the project', 'Apoyar el proyecto'],
  'L\'outil est gratuit et le restera. S\'il t\'a evite trois heures d\'Audacity, tu peux offrir un cafe :':
    ['The tool is free and will stay free. If it saved you three hours of Audacity, you can buy me a coffee:',
      'La herramienta es gratuita y lo seguira siendo. Si te ha ahorrado tres horas de Audacity, puedes invitarme a un cafe:'],
  '☕ Buy me a coffee': ['☕ Buy me a coffee', '☕ Invitame a un cafe'],
  'Guide officiel :': ['Official guide:', 'Guia oficial:'],
  'Documentation interne du jeu : menu Extras, ecrans de format.':
    ['The game\'s own documentation: Extras menu, format screens.',
      'Documentacion interna del juego: menu Extras, pantallas de formato.'],

  /* -- unites ------------------------------------------------------------------- */
  'o': ['B', 'B'],
  'Ko': ['KB', 'KB'],
  'Mo': ['MB', 'MB'],
  'Go': ['GB', 'GB'],

  /* -- messages de taches (serveur) ---------------------------------------------- */
  'Analyse du fichier': ['Analysing the file', 'Analizando el archivo'],
  'Extraction de la piste audio': ['Extracting the audio track', 'Extrayendo la pista de audio'],
  'Generation de l\'apercu': ['Generating the preview', 'Generando la vista previa'],
  'Calcul de la forme d\'onde': ['Computing the waveform', 'Calculando la forma de onda'],
  'Extraction d\'images candidates': ['Extracting candidate images', 'Extrayendo imagenes candidatas'],
  'Pret': ['Ready', 'Listo'],
  'Lecture des informations': ['Reading the information', 'Leyendo la informacion'],
  'Recherche des sous-titres': ['Looking for subtitles', 'Buscando los subtitulos'],
  'Detection des silences': ['Detecting silences', 'Detectando los silencios'],
  'Construction des segments': ['Building the segments', 'Construyendo los segmentos'],
  'Construction des clips': ['Building the clips', 'Construyendo los clips'],
  'Chargement du modele': ['Loading the model', 'Cargando el modelo'],
  'Telechargement': ['Downloading', 'Descargando'],
  'Assemblage': ['Merging', 'Ensamblando'],
  'Image %s/%s': ['Image %s/%s', 'Imagen %s/%s'],
  'Clip %s/%s': ['Clip %s/%s', 'Clip %s/%s'],
  'Conversion de la video (OGV)': ['Converting the video (OGV)', 'Convirtiendo el video (OGV)'],
  'Conversion OGV %s %': ['OGV conversion %s %', 'Conversion OGV %s %'],
  'Metadonnees du pack': ['Pack metadata', 'Metadatos del pack'],
  'Piste d\'ambiance': ['Backing track', 'Pista de ambiente'],
  'Transcription %s/%s': ['Transcription %s/%s', 'Transcripcion %s/%s'],

  /* -- erreurs (serveur) ----------------------------------------------------------- */
  'Projet introuvable': ['Project not found', 'Proyecto no encontrado'],
  'Fichier introuvable': ['File not found', 'Archivo no encontrado'],
  'Dossier introuvable': ['Folder not found', 'Carpeta no encontrada'],
  'Image introuvable': ['Image not found', 'Imagen no encontrada'],
  'Clip introuvable': ['Clip not found', 'Clip no encontrado'],
  'Son introuvable': ['Sound not found', 'Sonido no encontrado'],
  'Tache inconnue': ['Unknown task', 'Tarea desconocida'],
  'Type de pack inconnu': ['Unknown pack type', 'Tipo de pack desconocido'],
  'Adresse manquante': ['Missing address', 'Falta la direccion'],
  'Pas de video': ['No video', 'Sin video'],
  'Pas d\'image': ['No image', 'Sin imagen'],
  'Ce chemin n\'est pas un dossier': ['This path is not a folder', 'Esta ruta no es una carpeta'],
  'Acces refuse a ce dossier': ['Access denied to this folder', 'Acceso denegado a esta carpeta'],
  'Aucune source importee.': ['No source imported.', 'No se ha importado ninguna fuente.'],
  'Aucun fichier pour cet emplacement': ['No file for this slot', 'No hay archivo para esta ranura'],
  'La source n\'a pas de piste video.': ['The source has no video track.', 'La fuente no tiene pista de video.'],
  'La source n\'a pas de piste video : aucune image a extraire.':
    ['The source has no video track: no image to extract.',
      'La fuente no tiene pista de video: no hay imagenes que extraer.'],
  'Duree de la source inconnue.': ['Source length unknown.', 'Duracion de la fuente desconocida.'],
  'Aucune image n\'a pu etre extraite.': ['No image could be extracted.', 'No se pudo extraer ninguna imagen.'],
  'Aucun sous-titre exploitable dans ce fichier.':
    ['No usable subtitle in this file.', 'No hay subtitulos utilizables en este archivo.'],
  'Aucun transcript disponible.': ['No transcript available.', 'No hay transcripcion disponible.'],
  'Aucun transcript disponible pour ce projet.':
    ['No transcript available for this project.', 'No hay transcripcion disponible para este proyecto.'],
  'Aucune source a analyser': ['No source to analyse', 'No hay fuente que analizar'],
  'Fichier source introuvable': ['Source file not found', 'Archivo fuente no encontrado'],
  'Les directs ne peuvent pas etre importes.':
    ['Live streams cannot be imported.', 'Los directos no se pueden importar.'],
  'Cette URL ne contient aucune video.': ['This URL contains no video.', 'Esta URL no contiene ningun video.'],
  'Le telechargement n\'a produit aucun fichier.':
    ['The download produced no file.', 'La descarga no genero ningun archivo.'],
  'yt-dlp n\'est pas installe. Lance : pip install yt-dlp':
    ['yt-dlp is not installed. Run: pip install yt-dlp',
      'yt-dlp no esta instalado. Ejecuta: pip install yt-dlp'],
  'faster-whisper n\'est pas installe. Lance : pip install faster-whisper':
    ['faster-whisper is not installed. Run: pip install faster-whisper',
      'faster-whisper no esta instalado. Ejecuta: pip install faster-whisper'],
  'Ce fichier ne contient aucune piste audio : impossible d\'en tirer des clips.':
    ['This file has no audio track: no clips can be made from it.',
      'Este archivo no tiene pista de audio: no se pueden sacar clips de el.'],
  'Le fichier source est introuvable : reimporte-le avant de generer.':
    ['The source file cannot be found: import it again before building.',
      'No se encuentra el archivo fuente: vuelve a importarlo antes de generar.'],
  'Mode Dub actif mais aucune video source (dub_video.ogv requis).':
    ['Dub mode on but no source video (dub_video.ogv required).',
      'Modo Dub activo pero sin video fuente (se requiere dub_video.ogv).'],
  'Mode Dub actif mais aucune video source : le pack ne sera pas reconnu comme pack Dub tant que dub_video.ogv est absent.':
    ['Dub mode on but no source video: the pack will not count as a Dub pack while dub_video.ogv is missing.',
      'Modo Dub activo pero sin video fuente: el pack no se reconocera como pack Dub mientras falte dub_video.ogv.'],

  /* -- types de packs (specs) --------------------------------------------------------- */
  'Pack Voix / Dub': ['Voice / Dub pack', 'Pack de Voz / Dub'],
  'Pack Juges': ['Judges pack', 'Pack de Jueces'],
  'Pack Candidat': ['Contestant pack', 'Pack de Concursante'],
  'Pack Animateur': ['Host pack', 'Pack de Presentador'],
  'Pack Studio': ['Studio pack', 'Pack de Estudio'],
  'Pack Menu': ['Menu pack', 'Pack de Menu'],
  'Pack Chatter (Twitch)': ['Chatter pack (Twitch)', 'Pack de Chatter (Twitch)'],
  'Le coeur du jeu : une collection d\'extraits audio a imiter. Devient un pack Dub des qu\'un fichier dub_video.ogv est present.':
    ['The heart of the game: a collection of audio clips to imitate. Becomes a Dub pack as soon as a dub_video.ogv file is there.',
      'El corazon del juego: una coleccion de extractos de audio para imitar. Se convierte en pack Dub en cuanto hay un archivo dub_video.ogv.'],
  'Les cinq juges qui notent vos performances, de gauche a droite (1 a 5).':
    ['The five judges who score your performances, left to right (1 to 5).',
      'Los cinco jueces que puntuan tus actuaciones, de izquierda a derecha (1 a 5).'],
  'Le personnage que vous incarnez sur le plateau.':
    ['The character you play on stage.', 'El personaje que encarnas en el plato.'],
  'L\'animateur qui commente la partie. Tous ses dialogues sont modifiables — ideal pour une version entierement francaise.':
    ['The host who comments on the game. All the dialogue can be edited — ideal for a fully localised version.',
      'El presentador que comenta la partida. Todos sus dialogos son editables: ideal para una version totalmente localizada.'],
  'L\'environnement du plateau : musique, modele 3D, ecrans.':
    ['The stage environment: music, 3D model, screens.',
      'El entorno del plato: musica, modelo 3D, pantallas.'],
  'L\'habillage du menu principal : fond, musique, sons de boutons.':
    ['The main menu dressing: background, music, button sounds.',
      'La ambientacion del menu principal: fondo, musica, sonidos de botones.'],
  'Sons declenches par les mots-cles du chat Twitch.':
    ['Sounds triggered by Twitch chat keywords.',
      'Sonidos que disparan las palabras clave del chat de Twitch.'],

  /* -- emplacements et champs (specs) --------------------------------------------------- */
  'Icone du pack': ['Pack icon', 'Icono del pack'],
  'Affichee quand le pack est selectionne.': ['Shown when the pack is selected.', 'Se muestra al seleccionar el pack.'],
  'Image par defaut des clips': ['Default clip image', 'Imagen por defecto de los clips'],
  'Utilisee pour tous les clips sans image propre.':
    ['Used for every clip without its own image.', 'Se usa en todos los clips sin imagen propia.'],
  'Piste d\'ambiance (dub)': ['Backing track (dub)', 'Pista de ambiente (dub)'],
  'Musique/bruitages sans les voix, joues pendant le mode Dub.':
    ['Music/effects without the voices, played during Dub mode.',
      'Musica y efectos sin las voces, sonando durante el modo Dub.'],
  'Optionnel.': ['Optional.', 'Opcional.'],
  'Image du candidat': ['Contestant image', 'Imagen del concursante'],
  '~500x1000 px, le bas touche le sol. Une image d\'une autre hauteur est mise a l\'echelle a la generation, sinon le personnage reste derriere le pupitre.':
    ['~500x1000 px, the bottom touches the floor. An image of another height is scaled at build time, otherwise the character stays behind the desk.',
      '~500x1000 px, la base toca el suelo. Una imagen de otra altura se escala al generar, si no el personaje se queda detras del atril.'],
  '~500x1000 px, le bas de l\'image touche le sol du studio. Une image d\'une autre hauteur est mise a l\'echelle a la generation, sinon le personnage reste derriere le pupitre.':
    ['~500x1000 px, the bottom of the image touches the studio floor. An image of another height is scaled at build time, otherwise the character stays behind the desk.',
      '~500x1000 px, la base de la imagen toca el suelo del estudio. Una imagen de otra altura se escala al generar, si no el personaje se queda detras del atril.'],
  'Image de l\'animateur': ['Host image', 'Imagen del presentador'],
  'Nom du candidat': ['Contestant name', 'Nombre del concursante'],
  'Nom de l\'animateur': ['Host name', 'Nombre del presentador'],
  'Phrase de presentation': ['Introduction line', 'Frase de presentacion'],
  'L\'animateur dit cette phrase suivie du nom.':
    ['The host says this line followed by the name.',
      'El presentador dice esta frase seguida del nombre.'],
  'Presentation par l\'animateur': ['Host introduction', 'Presentacion del presentador'],
  'Noms': ['Names', 'Nombres'],
  'Couleurs': ['Colours', 'Colores'],
  'Interface': ['Interface', 'Interfaz'],
  'Rendu': ['Rendering', 'Renderizado'],
  'Juge %s — image': ['Judge %s — image', 'Juez %s — imagen'],
  'Juge %s — voix': ['Judge %s — voice', 'Juez %s — voz'],
  'Nom du juge %s': ['Judge %s name', 'Nombre del juez %s'],
  'Panneau de vote (defaut)': ['Vote panel (default)', 'Panel de voto (por defecto)'],
  'Panneau de vote — juge %s': ['Vote panel — judge %s', 'Panel de voto — juez %s'],
  'Optionnel, remplace le panneau par defaut pour ce juge.':
    ['Optional, replaces the default panel for this judge.',
      'Opcional, sustituye al panel por defecto de ese juez.'],
  'Joue quand ce juge vote pour vous.': ['Plays when this judge votes for you.', 'Suena cuando ese juez vota por ti.'],
  'Bip de score %s': ['Score blip %s', 'Bip de puntuacion %s'],
  'Joue au i-eme vote, quel que soit le juge.':
    ['Plays on the i-th vote, whichever judge it is.',
      'Suena en el i-esimo voto, sea cual sea el juez.'],
  'Jouer les bips en meme temps que les voix':
    ['Play the blips together with the voices', 'Reproducir los bips junto con las voces'],
  'Decoche pour n\'entendre que les voix des juges.':
    ['Untick to hear only the judges\' voices.', 'Desmarca para oir solo las voces de los jueces.'],
  'Volume des extraits': ['Clip volume', 'Volumen de los extractos'],
  '1.0 = 100 %.': ['1.0 = 100 %.', '1.0 = 100 %.'],
  'Musique du plateau': ['Stage music', 'Musica del plato'],
  'Musique du menu': ['Menu music', 'Musica del menu'],
  'Debut de boucle de la musique': ['Music loop start', 'Inicio del bucle de la musica'],
  'Echantillon de depart pour un WAV, secondes pour un MP3/OGG.':
    ['Start sample for a WAV, seconds for an MP3/OGG.',
      'Muestra inicial para un WAV, segundos para un MP3/OGG.'],
  'Echantillon pour un WAV, secondes pour un MP3/OGG.':
    ['Sample for a WAV, seconds for an MP3/OGG.', 'Muestra para un WAV, segundos para un MP3/OGG.'],
  'Modele 3D du studio': ['Studio 3D model', 'Modelo 3D del estudio'],
  'GLB ou GLTF. Un gabarit est genere par le jeu a la creation du dossier.':
    ['GLB or GLTF. The game generates a template when the folder is created.',
      'GLB o GLTF. El juego genera una plantilla al crear la carpeta.'],
  'Utiliser l\'eclairage integre': ['Use built-in lighting', 'Usar la iluminacion integrada'],
  'Decoche si ton modele 3D apporte son propre eclairage. Cle documentee sur le site mais absente du binaire 0.5.1 : sans effet si ta version ne la lit pas.':
    ['Untick if your 3D model brings its own lighting. Documented on the site but missing from the 0.5.1 binary: no effect if your version does not read it.',
      'Desmarca si tu modelo 3D trae su propia iluminacion. Documentada en la web pero ausente del binario 0.5.1: sin efecto si tu version no la lee.'],
  'Video de l\'ecran de score': ['Score screen video', 'Video de la pantalla de puntuacion'],
  'OGV uniquement. Jouee en boucle et muette.': ['OGV only. Looped and muted.', 'Solo OGV. En bucle y sin sonido.'],
  'Image de fond': ['Background image', 'Imagen de fondo'],
  'Mode de l\'image de fond': ['Background image mode', 'Modo de la imagen de fondo'],
  '0 — etiree': ['0 — stretched', '0 — estirada'],
  '1 — mosaique / defilement': ['1 — tiled / scrolling', '1 — mosaico / desplazamiento'],
  'Toujours etire a la taille de la fenetre.': ['Always stretched to the window.', 'Siempre estirada al tamano de la ventana.'],
  'Redimensionnee a la hauteur de la fenetre, ratio conserve.':
    ['Scaled to the window height, ratio kept.', 'Escalada a la altura de la ventana, manteniendo la proporcion.'],
  'Video de fond': ['Background video', 'Video de fondo'],
  'Utiliser la video de fond': ['Use the background video', 'Usar el video de fondo'],
  'OGV uniquement. Remplace l\'image de fond et tourne en boucle.':
    ['OGV only. Replaces the background image and loops.',
      'Solo OGV. Sustituye a la imagen de fondo y se repite en bucle.'],
  'Defilement X': ['Scroll X', 'Desplazamiento X'],
  'Defilement Y': ['Scroll Y', 'Desplazamiento Y'],
  'Son — bouton valider': ['Sound — confirm button', 'Sonido — boton aceptar'],
  'Son — bouton retour': ['Sound — back button', 'Sonido — boton volver'],
  'Son — bouton secondaire': ['Sound — secondary button', 'Sonido — boton secundario'],
  'Son — survol': ['Sound — hover', 'Sonido — al pasar por encima'],
  'Boutons — couleur 1': ['Buttons — colour 1', 'Botones — color 1'],
  'Boutons — couleur 2': ['Buttons — colour 2', 'Botones — color 2'],
  'Boutons — inverser': ['Buttons — invert', 'Botones — invertir'],
  'Calque par-dessus le menu': ['Layer above the menu', 'Capa por encima del menu'],
  'Calque overlay actif': ['Overlay layer on', 'Capa overlay activa'],
  'Couleur 1 (pupitre)': ['Colour 1 (desk)', 'Color 1 (atril)'],
  'Couleur 2 (accent)': ['Colour 2 (accent)', 'Color 2 (acento)'],
  'Couleurs de l\'overlay d\'enregistrement': ['Recording overlay colours', 'Colores del overlay de grabacion'],
  'Overlay — corps': ['Overlay — body', 'Overlay — cuerpo'],
  'Overlay — bordure': ['Overlay — border', 'Overlay — borde'],
  'Overlay — temoin': ['Overlay — indicator', 'Overlay — testigo'],
  'Overlay — halo du temoin': ['Overlay — indicator glow', 'Overlay — halo del testigo'],
  'Overlay — barre de lecture': ['Overlay — playback bar', 'Overlay — barra de reproduccion'],
  'Overlay — voix du clip': ['Overlay — clip voice', 'Overlay — voz del clip'],
  'Overlay — voix du joueur': ['Overlay — player voice', 'Overlay — voz del jugador'],
  'Bandes laterales — actives': ['Side bands — on', 'Bandas laterales — activas'],
  'Bandes laterales — couleur': ['Side bands — colour', 'Bandas laterales — color'],
  'Bandes laterales — accent': ['Side bands — accent', 'Bandas laterales — acento'],
  'Cercles — actif': ['Circles — on', 'Circulos — activo'],
  'Cercles — couleur': ['Circles — colour', 'Circulos — color'],
  'Vagues — actif': ['Waves — on', 'Olas — activo'],
  'Vagues — couleur': ['Waves — colour', 'Olas — color'],
  'Degrade haut — actif': ['Top gradient — on', 'Degradado superior — activo'],
  'Degrade haut — couleur': ['Top gradient — colour', 'Degradado superior — color'],
  'Degrade bas — actif': ['Bottom gradient — on', 'Degradado inferior — activo'],
  'Degrade bas — couleur': ['Bottom gradient — colour', 'Degradado inferior — color'],
  'Disque de clip — couleur': ['Clip disc — colour', 'Disco de clip — color'],
  'Disque de clip — etat': ['Clip disc — state', 'Disco de clip — estado'],
  'Image « clip jamais entendu »': ['"Never heard clip" image', 'Imagen «clip nunca escuchado»'],
  'Image « absolute » (score 6/5)': ['"Absolute" image (score 6/5)', 'Imagen «absolute» (puntuacion 6/5)'],
  'Image de remplacement des clips': ['Clip fallback image', 'Imagen de reemplazo de los clips'],
  'Ratio 2:1, 512x256 par defaut.': ['2:1 ratio, 512x256 by default.', 'Proporcion 2:1, 512x256 por defecto.'],
  'Note de %s': ['Score of %s', 'Puntuacion de %s'],
  'Victoire': ['Win', 'Victoria'],
  'Defaite': ['Loss', 'Derrota'],

  /* -- dialogues de l'animateur (specs) ------------------------------------------------- */
  'Partie solo': ['Single player game', 'Partida en solitario'],
  'Partie multijoueur': ['Multiplayer game', 'Partida multijugador'],
  'Mode Twitch': ['Twitch mode', 'Modo Twitch'],
  'Introduction': ['Introduction', 'Introduccion'],
  'Deroulement des manches': ['Round flow', 'Desarrollo de las rondas'],
  'Notation': ['Scoring', 'Puntuacion'],
  'Fin de partie': ['End of game', 'Fin de la partida'],
  'Accueil': ['Welcome', 'Bienvenida'],
  'Presentation du candidat': ['Contestant introduction', 'Presentacion del concursante'],
  'Presentation des candidats': ['Contestants introduction', 'Presentacion de los concursantes'],
  'Presentation du jury': ['Panel introduction', 'Presentacion del jurado'],
  'Explication des regles': ['Rules explanation', 'Explicacion de las reglas'],
  'C\'est a vous': ['Your turn', 'Te toca'],
  'Apres l\'enregistrement': ['After recording', 'Despues de grabar'],
  'Apres l\'ecoute': ['After listening', 'Despues de escuchar'],
  'Manche suivante': ['Next round', 'Siguiente ronda'],
  'Derniere manche': ['Final round', 'Ultima ronda'],
  'Points attribues': ['Points awarded', 'Puntos otorgados'],
  'Apres la notation': ['After scoring', 'Despues de puntuar'],
  'Note %s': ['Score %s', 'Puntuacion %s'],
  'Note 6 (match exact)': ['Score 6 (exact match)', 'Puntuacion 6 (coincidencia exacta)'],
  'Score final': ['Final score', 'Puntuacion final'],
  'Victoire de justesse': ['Narrow win', 'Victoria ajustada'],
  'Sans-faute': ['Flawless', 'Sin fallos'],
  'Defaite de justesse': ['Narrow loss', 'Derrota ajustada'],
  'Defaite totale': ['Total loss', 'Derrota total'],
  'Vainqueur': ['Winner', 'Ganador'],
  'Egalite': ['Tie', 'Empate'],
  'Egalite — debut': ['Tie — start', 'Empate — inicio'],
  'Egalite — fin': ['Tie — end', 'Empate — final'],
  'Felicitations et au revoir': ['Congratulations and goodbye', 'Felicidades y hasta luego'],
  'Presentation du public': ['Audience introduction', 'Presentacion del publico'],
  'Ouverture des votes': ['Voting opens', 'Apertura de las votaciones'],
  'Appel au vote': ['Call to vote', 'Llamada al voto'],
  'Cloture des votes': ['Voting closes', 'Cierre de las votaciones'],
  'nom du candidat': ['contestant name', 'nombre del concursante'],
  'nom de l\'animateur': ['host name', 'nombre del presentador'],
  'numero de la manche': ['round number', 'numero de ronda'],
  'points obtenus': ['points scored', 'puntos obtenidos'],
  'phrase de presentation du candidat': ['contestant introduction line', 'frase de presentacion del concursante'],
};

/* ------------------------------------------------------------------ moteur */

let current = 'fr';
try {
  current = localStorage.getItem(STORAGE_KEY) || 'fr';
} catch { /* stockage refuse : on reste en francais */ }
if (!LANGUAGES.some((l) => l.code === current)) current = 'fr';

export const getLang = () => current;

export function setLang(code) {
  current = LANGUAGES.some((l) => l.code === code) ? code : 'fr';
  try { localStorage.setItem(STORAGE_KEY, current); } catch { /* sans importance */ }
  document.documentElement.lang = current;
}

const NUMBER = /\d+(?:[.,:]\d+)*/g;

/** Traduction d'une phrase entiere, ou null si elle n'est pas au dictionnaire. */
function lookup(text) {
  if (current === 'fr' || !text) return null;
  const column = COLUMN[current];
  const direct = DICT[text];
  if (direct) return direct[column] || null;
  // « Clip 3/12 » -> cle « Clip %s/%s », puis les nombres reviennent en place.
  const numbers = text.match(NUMBER);
  if (!numbers) return null;
  const pattern = DICT[text.replace(NUMBER, '%s')];
  if (!pattern || !pattern[column]) return null;
  let index = 0;
  return pattern[column].replace(/%s/g, () => numbers[index++] ?? '');
}

/**
 * Traduit puis remplit une phrase : `t('%s clips detectes.', 12)`.
 * En francais, la phrase source sert telle quelle — les %s sont remplis pareil.
 */
export function t(text, ...values) {
  const source = String(text ?? '');
  const translated = lookup(source) ?? source;
  if (!values.length) return translated;
  let index = 0;
  return translated.replace(/%s/g, () => {
    const value = values[index++];
    return value === undefined ? '%s' : String(value);
  });
}

/* Contenu a ne jamais traduire : code, saisies, et tout ce qui porte une
 * donnee de l'utilisateur (nom de projet, de pack, de fichier). */
const SKIP = 'code, pre, script, style, textarea, [data-notr]';

/* Le texte francais d'origine est garde sur le noeud : sans lui, passer de
 * l'espagnol au francais n'aurait plus rien a quoi se raccrocher — la phrase
 * affichee n'est plus une cle du dictionnaire. */
function translateNode(node) {
  const raw = node.nodeValue;
  if (!raw || !raw.trim()) return;
  const [, before, text, after] = raw.match(/^(\s*)([\s\S]*?)(\s*)$/);
  const source = node.i18nSource ?? text.replace(/\s+/g, ' ');
  const target = current === 'fr' ? source : (lookup(source) ?? source);
  if (target === text) return;
  node.i18nSource = source;
  node.nodeValue = before + target + after;
}

function translateAttributes(element) {
  for (const name of ['placeholder', 'title']) {
    const value = element.getAttribute?.(name);
    if (!value) continue;
    const sources = element.i18nAttrs ?? (element.i18nAttrs = {});
    const source = sources[name] ?? value.replace(/\s+/g, ' ').trim();
    const target = current === 'fr' ? source : (lookup(source) ?? source);
    if (target === value) continue;
    sources[name] = source;
    element.setAttribute(name, target);
  }
}

export function translateTree(root) {
  if (!root) return;
  if (root.nodeType === Node.TEXT_NODE) return translateNode(root);
  if (root.nodeType !== Node.ELEMENT_NODE && root.nodeType !== Node.DOCUMENT_FRAGMENT_NODE) return;
  if (root.closest?.(SKIP)) return;

  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      if (!node.nodeValue.trim()) return NodeFilter.FILTER_REJECT;
      return node.parentElement?.closest(SKIP)
        ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT;
    },
  });
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  nodes.forEach(translateNode);

  if (root.matches?.('[placeholder], [title]')) translateAttributes(root);
  root.querySelectorAll?.('[placeholder], [title]').forEach(translateAttributes);
}

/**
 * Traduit tout ce qui arrive dans `root` par la suite. Le rendu de
 * l'application n'a ainsi rien a savoir de la traduction.
 */
export function watch(root) {
  const observer = new MutationObserver((records) => {
    if (current === 'fr') return;
    for (const record of records) {
      if (record.type === 'characterData') translateNode(record.target);
      else if (record.type === 'attributes') translateAttributes(record.target);
      else record.addedNodes.forEach(translateTree);
    }
  });
  observer.observe(root, {
    subtree: true, childList: true, characterData: true,
    attributes: true, attributeFilter: ['placeholder', 'title'],
  });
}

/** Liste les phrases affichees qui ne sont pas au dictionnaire (mise au point). */
export function audit(root = document.body) {
  const missing = new Set();
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode: (node) => (node.nodeValue.trim() && !node.parentElement?.closest(SKIP)
      ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT),
  });
  while (walker.nextNode()) {
    const node = walker.currentNode;
    const key = node.i18nSource ?? node.nodeValue.replace(/\s+/g, ' ').trim();
    if (!DICT[key] && !DICT[key.replace(NUMBER, '%s')]) missing.add(key);
  }
  return [...missing];
}
