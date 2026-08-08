import { Waveform, formatTime, round3 } from './waveform.js';
import { LANGUAGES, getLang, setLang, t, translateTree, watch } from './i18n.js';

/* ------------------------------------------------------------------ etat */

const state = {
  boot: null,
  project: null,
  selectedClip: null,
  wave: null,
  playStopAt: null,
};

const player = document.getElementById('player');

/* ------------------------------------------------------------------- api */

async function api(path, options = {}) {
  const response = await fetch('/api' + path, {
    headers: options.body && !(options.body instanceof FormData)
      ? { 'Content-Type': 'application/json' } : undefined,
    ...options,
  });
  if (!response.ok) {
    let message = response.statusText;
    try { message = (await response.json()).detail || message; } catch { /* ignore */ }
    throw new Error(message);
  }
  const type = response.headers.get('content-type') || '';
  return type.includes('json') ? response.json() : response.text();
}

const post = (path, body) => api(path, { method: 'POST', body: JSON.stringify(body ?? {}) });
const patch = (path, body) => api(path, { method: 'PATCH', body: JSON.stringify(body) });
const del = (path) => api(path, { method: 'DELETE' });

function upload(path, file) {
  const form = new FormData();
  form.append('file', file);
  return api(path, { method: 'POST', body: form });
}

async function waitJob(jobId, onProgress) {
  for (;;) {
    const job = await api(`/jobs/${jobId}`);
    if (onProgress) onProgress(job);
    if (job.state === 'done') return job.result;
    if (job.state === 'error') throw new Error(job.error || 'Tache en echec');
    await new Promise((r) => setTimeout(r, 350));
  }
}

/* ---------------------------------------------------------------- toasts */

function toast(message, kind = '') {
  const host = document.getElementById('toasts');
  const el = document.createElement('div');
  el.className = 'toast ' + kind;
  el.textContent = message;
  host.appendChild(el);
  setTimeout(() => el.remove(), kind === 'error' ? 7000 : 3500);
}

const fail = (error) => toast(error.message || String(error), 'error');

/* ---------------------------------------------------------------- modale */

function modal(title, bodyHtml, { wide = false } = {}) {
  const backdrop = document.createElement('div');
  backdrop.className = 'modal-backdrop';
  backdrop.innerHTML = `<div class="modal" ${wide ? 'style="width:min(1000px,94vw)"' : ''}>
      <h3>${escapeHtml(title)}</h3>
      <div class="modal-body">${bodyHtml}</div>
    </div>`;
  backdrop.addEventListener('mousedown', (e) => { if (e.target === backdrop) close(); });
  document.body.appendChild(backdrop);
  const close = () => backdrop.remove();
  return { root: backdrop, body: backdrop.querySelector('.modal-body'), close };
}

function confirmDialog(title, message) {
  return new Promise((resolve) => {
    const dialog = modal(title, `
      <p>${escapeHtml(message)}</p>
      <div class="row" style="justify-content:flex-end;margin-top:16px">
        <button class="btn ghost" data-no>Annuler</button>
        <button class="btn primary" data-yes>Confirmer</button>
      </div>`);
    dialog.body.querySelector('[data-no]').onclick = () => { dialog.close(); resolve(false); };
    dialog.body.querySelector('[data-yes]').onclick = () => { dialog.close(); resolve(true); };
  });
}

/* ------------------------------------------------- explorateur de fichiers */

function browseFile(kind = 'media', startPath = '') {
  return new Promise((resolve) => {
    const dialog = modal('Choisir un fichier', `
      <div class="row" style="margin-bottom:10px">
        <input type="text" id="br-path" placeholder="Chemin" style="flex:1">
        <button class="btn" id="br-go">Aller</button>
        <button class="btn ghost" id="br-up">Dossier parent</button>
      </div>
      <div class="browser-list" id="br-list"></div>
      <div class="row" style="justify-content:flex-end;margin-top:12px">
        <button class="btn ghost" id="br-cancel">Annuler</button>
      </div>`, { wide: true });

    const list = dialog.body.querySelector('#br-list');
    const pathInput = dialog.body.querySelector('#br-path');
    let current = { parent: '' };

    async function load(path) {
      try {
        const data = await api(`/fs/list?kind=${kind}&path=${encodeURIComponent(path || '')}`);
        current = data;
        pathInput.value = data.path || '';
        list.innerHTML = '';
        for (const dir of data.dirs) {
          list.insertAdjacentHTML('beforeend',
            `<div class="browser-item" data-dir="${escapeAttr(dir.path)}">
               <span>&#128193;</span><span class="name">${escapeHtml(dir.name)}</span></div>`);
        }
        for (const file of data.files) {
          list.insertAdjacentHTML('beforeend',
            `<div class="browser-item" data-file="${escapeAttr(file.path)}">
               <span>&#127925;</span><span class="name">${escapeHtml(file.name)}</span>
               <span class="size">${formatBytes(file.size)}</span></div>`);
        }
        if (!data.dirs.length && !data.files.length) {
          list.innerHTML = '<div class="browser-item"><span class="name">Dossier vide</span></div>';
        }
      } catch (error) { fail(error); }
    }

    list.addEventListener('click', (e) => {
      const item = e.target.closest('.browser-item');
      if (!item) return;
      if (item.dataset.dir) load(item.dataset.dir);
      else if (item.dataset.file) { dialog.close(); resolve(item.dataset.file); }
    });
    dialog.body.querySelector('#br-go').onclick = () => load(pathInput.value);
    dialog.body.querySelector('#br-up').onclick = () => load(current.parent || '');
    dialog.body.querySelector('#br-cancel').onclick = () => { dialog.close(); resolve(null); };
    pathInput.onkeydown = (e) => { if (e.key === 'Enter') load(pathInput.value); };
    load(startPath);
  });
}

/* ----------------------------------------------------------------- utils */

const escapeHtml = (value) => String(value ?? '')
  .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const escapeAttr = (value) => escapeHtml(value).replace(/"/g, '&quot;');

function formatBytes(bytes) {
  if (!bytes) return '';
  const units = ['o', 'Ko', 'Mo', 'Go'].map((u) => t(u));
  let index = 0;
  while (bytes >= 1024 && index < units.length - 1) { bytes /= 1024; index++; }
  return `${bytes.toFixed(index ? 1 : 0)} ${units[index]}`;
}

function debounce(fn, delay = 500) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}

const saveProject = debounce(async () => {
  if (!state.project) return;
  try {
    await patch(`/projects/${state.project.id}`, {
      name: state.project.name,
      meta: state.project.meta,
      config: state.project.config,
      clips: state.project.clips,
      chatter: state.project.chatter,
      dub: state.project.dub,
      options: state.project.options || {},
      host_dialog: state.project.host_dialog,
    });
  } catch (error) { fail(error); }
}, 600);

/* -------------------------------------------------------------- routeur */

function show(view) {
  document.querySelectorAll('.view').forEach((el) => el.classList.remove('active'));
  document.getElementById('view-' + view)?.classList.add('active');
  document.querySelectorAll('nav button').forEach((b) =>
    b.classList.toggle('active', b.dataset.view === view));
  window.scrollTo(0, 0);
}

document.querySelectorAll('nav button').forEach((button) => {
  button.onclick = async () => {
    const view = button.dataset.view;
    // Page ouverte pendant un redemarrage du serveur : rien n'a pu etre
    // charge. On retente, plutot que d'echouer sur une reference vide.
    if (!state.boot && !await loadBoot()) return;
    renderView(view);
    show(view);
  };
});

function renderView(view) {
  if (!state.boot) return undefined;
  if (view === 'home') return renderHome();
  if (view === 'library') return renderLibrary();
  if (view === 'settings') return renderSettings();
  if (view === 'help') return renderHelp();
  if (view === 'editor' && state.project) return renderEditor();
  return undefined;
}

/* ------------------------------------------------------------- traduction */

function wireLanguage() {
  const root = document.getElementById('lang');
  const button = document.getElementById('lang-button');
  const menu = document.getElementById('lang-menu');

  const paint = () => {
    const active = LANGUAGES.find((l) => l.code === getLang()) || LANGUAGES[0];
    button.innerHTML = `${active.flag}<span>${active.short}</span><i>&#9662;</i>`;
    button.title = active.label;
    menu.innerHTML = LANGUAGES.map((language) => `
      <li role="option" data-lang="${language.code}"
          aria-selected="${language.code === active.code}"
          class="${language.code === active.code ? 'on' : ''}"
        >${language.flag}<span>${language.label}</span></li>`).join('');
  };

  const close = () => { menu.hidden = true; button.setAttribute('aria-expanded', 'false'); };
  const open = () => { menu.hidden = false; button.setAttribute('aria-expanded', 'true'); };

  button.onclick = (event) => {
    event.stopPropagation();
    if (menu.hidden) open(); else close();
  };
  document.addEventListener('click', (event) => {
    if (!root.contains(event.target)) close();
  });
  document.addEventListener('keydown', (event) => { if (event.key === 'Escape') close(); });

  menu.onclick = async (event) => {
    const item = event.target.closest('[data-lang]');
    if (!item) return;
    close();
    setLang(item.dataset.lang);
    paint();
    document.title = t('Createur de packs — The Choicer Voicer');
    // La vue courante est reconstruite en francais, puis retraduite d'un bloc :
    // c'est le seul moyen de revenir au francais sans recharger la page.
    await renderView(document.querySelector('.view.active')?.id.replace('view-', ''));
    translateTree(document.body);
  };

  paint();
}

/* ----------------------------------------------------------- vue accueil */

async function renderHome() {
  const host = document.getElementById('view-home');
  const specs = state.boot.specs;
  const { projects } = await api('/projects');

  const options = Object.values(specs)
    .map((s) => `<option value="${s.id}">${escapeHtml(s.label)}</option>`).join('');

  host.innerHTML = `
    <div class="card">
      <h2>Nouveau pack</h2>
      <p class="hint">Le nom devient le nom du dossier dans le jeu.</p>
      <div class="row">
        <input type="text" id="new-name" placeholder="Nom du pack" style="flex:2;min-width:220px">
        <select id="new-type" style="flex:1;min-width:200px">${options}</select>
        <button class="btn primary" id="new-go">Creer</button>
      </div>
      <p class="hint" id="new-desc"></p>
    </div>

    <div class="card">
      <h2>Mes projets <span class="tag">${projects.length}</span></h2>
      <div class="grid cards" id="project-list" style="margin-top:12px">
        ${projects.length ? '' : '<p class="hint">Aucun projet pour le moment.</p>'}
      </div>
    </div>`;

  const typeSelect = host.querySelector('#new-type');
  const description = host.querySelector('#new-desc');
  const updateDescription = () => {
    description.textContent = specs[typeSelect.value]?.description || '';
  };
  typeSelect.onchange = updateDescription;
  updateDescription();

  host.querySelector('#new-go').onclick = async () => {
    const name = host.querySelector('#new-name').value.trim();
    if (!name) return toast('Donne un nom au pack.', 'error');
    try {
      const project = await post('/projects', { name, type: typeSelect.value });
      toast('Projet cree.', 'success');
      openProject(project.id);
    } catch (error) { fail(error); }
  };

  const list = host.querySelector('#project-list');
  for (const project of projects) {
    const card = document.createElement('div');
    card.className = 'card project-card';
    card.style.marginBottom = '0';
    card.innerHTML = `
      <h3 data-notr>${escapeHtml(project.name)}</h3>
      <div class="row tight" style="margin-bottom:8px">
        <span class="tag">${escapeHtml(project.type_label)}</span>
        ${project.is_dub ? '<span class="tag dub">Dub</span>' : ''}
        ${project.clip_count ? `<span class="tag">${t('%s clips', project.clip_count)}</span>` : ''}
      </div>
      <p class="hint">${escapeHtml(t('Modifie le %s', project.updated.replace('T', ' ')))}</p>
      <div class="row tight" style="margin-top:10px">
        <button class="btn small" data-open>Ouvrir</button>
        <button class="btn small ghost" data-copy>Dupliquer</button>
        <button class="btn small ghost danger" data-del>Supprimer</button>
      </div>`;
    card.querySelector('[data-open]').onclick = () => openProject(project.id);
    card.querySelector('[data-copy]').onclick = async (e) => {
      e.stopPropagation();
      try {
        await post(`/projects/${project.id}/duplicate`, { name: project.name + ' (copie)' });
        renderHome();
      } catch (error) { fail(error); }
    };
    card.querySelector('[data-del]').onclick = async (e) => {
      e.stopPropagation();
      if (!await confirmDialog(t('Supprimer'),
        t('Supprimer definitivement « %s » ?', project.name))) return;
      await del(`/projects/${project.id}`);
      renderHome();
    };
    list.appendChild(card);
  }
}

/* ------------------------------------------------------------ vue editeur */

async function openProject(id) {
  try {
    state.project = await api(`/projects/${id}`);
    state.selectedClip = null;
    // La vue doit etre visible avant le rendu : le canvas de la forme d'onde
    // se mesure a la construction.
    show('editor');
    renderEditor();
  } catch (error) { fail(error); }
}

function editorHeader() {
  const project = state.project;
  const spec = state.boot.specs[project.type];
  return `
    <div class="card">
      <div class="row">
        <button class="btn ghost" id="back">&larr; Projets</button>
        <input type="text" id="pack-name" value="${escapeAttr(project.name)}"
               style="flex:1;min-width:240px;font-size:16px;font-weight:600">
        <span class="tag">${escapeHtml(spec.label)}</span>
        ${project.dub?.enabled ? '<span class="tag dub">Mode Dub</span>' : ''}
      </div>
      <p class="hint">${escapeHtml(spec.description)}</p>
    </div>`;
}

function wireHeader(host) {
  host.querySelector('#back').onclick = () => { renderHome(); show('home'); };
  const nameInput = host.querySelector('#pack-name');
  nameInput.oninput = () => { state.project.name = nameInput.value; saveProject(); };
}

function buildPanel() {
  return `
    <div class="card">
      <h2>Generation</h2>
      <p class="hint">Le pack est d'abord genere dans le dossier de travail, puis installe dans le jeu.</p>
      <div class="row" style="margin:12px 0">
        <button class="btn" id="btn-validate">Verifier</button>
        <button class="btn primary" id="btn-build">Generer</button>
        <button class="btn" id="btn-install">Installer dans le jeu</button>
        <button class="btn ghost" id="btn-zip">Exporter en .zip</button>
        <button class="btn ghost" id="btn-preview-config">Voir la config</button>
        <div class="spacer"></div>
        <button class="btn ghost" id="btn-open-build">Ouvrir le dossier</button>
      </div>
      <div class="progress" id="build-progress" style="display:none"><div></div></div>
      <p class="hint" id="build-message"></p>
      <div id="build-issues"></div>
    </div>`;
}

function wireBuildPanel(host) {
  const project = state.project;
  const progress = host.querySelector('#build-progress');
  const bar = progress.querySelector('div');
  const message = host.querySelector('#build-message');
  const issues = host.querySelector('#build-issues');

  const showIssues = (list) => {
    issues.innerHTML = list.length
      ? list.map((i) => `<div class="issue ${i.level}">${escapeHtml(i.message)}</div>`).join('')
      : '<div class="issue info">Aucun probleme detecte.</div>';
  };

  host.querySelector('#btn-validate').onclick = async () => {
    try {
      const result = await api(`/projects/${project.id}/validate`);
      showIssues(result.issues);
      message.textContent = t('Sera installe dans : %s', result.install_path);
    } catch (error) { fail(error); }
  };

  host.querySelector('#btn-build').onclick = async () => {
    await saveNow();
    progress.style.display = '';
    bar.style.width = '0%';
    try {
      const { job } = await post(`/projects/${project.id}/build`);
      const report = await waitJob(job, (j) => {
        bar.style.width = Math.round(j.progress * 100) + '%';
        message.textContent = j.message || '';
      });
      message.textContent = t('%s fichiers ecrits dans %s', report.file_count, report.path);
      showIssues((report.warnings || []).map((w) => ({ level: 'warning', message: w })));
      state.project.build = { path: report.path };
      toast('Pack genere.', 'success');
    } catch (error) { fail(error); message.textContent = ''; }
    finally { setTimeout(() => { progress.style.display = 'none'; }, 900); }
  };

  host.querySelector('#btn-install').onclick = async () => {
    try {
      let result = await post(`/projects/${project.id}/install`, {});
      if (result.exists) {
        if (!await confirmDialog(t('Ecraser ?'),
          t('Le dossier %s existe deja. Le remplacer ?', result.path))) return;
        result = await post(`/projects/${project.id}/install`, { overwrite: true });
      }
      message.textContent = t('Installe dans %s', result.path);
      toast('Pack installe. Relance le jeu pour le voir.', 'success');
    } catch (error) { fail(error); }
  };

  host.querySelector('#btn-zip').onclick = () => {
    window.location.href = `/api/projects/${project.id}/zip`;
  };

  host.querySelector('#btn-preview-config').onclick = async () => {
    try {
      const data = await api(`/projects/${project.id}/preview-config`);
      const dialog = modal(data.filename || t('Configuration'), '<pre class="code"></pre>', { wide: true });
      dialog.body.querySelector('pre').textContent = data.content;
    } catch (error) { fail(error); }
  };

  host.querySelector('#btn-open-build').onclick = async () => {
    const path = state.project.build?.path;
    if (!path) return toast('Genere le pack d\'abord.', 'error');
    try { await post('/open-folder', { path }); } catch (error) { fail(error); }
  };
}

async function saveNow() {
  if (!state.project) return;
  await patch(`/projects/${state.project.id}`, {
    name: state.project.name,
    meta: state.project.meta,
    config: state.project.config,
    clips: state.project.clips,
    chatter: state.project.chatter,
    dub: state.project.dub,
    options: state.project.options || {},
    host_dialog: state.project.host_dialog,
  });
}

function renderEditor() {
  const spec = state.boot.specs[state.project.type];
  if (spec.editor === 'voice') return renderVoiceEditor();
  if (spec.editor === 'host') return renderHostEditor();
  if (spec.editor === 'chatter') return renderChatterEditor();
  return renderSimpleEditor();
}

/* --------------------------------------------------- emplacements assets */

function slotHtml(slot, project) {
  const stored = project.assets?.[slot.name];
  const filename = project.asset_names?.[slot.name] || stored || '';
  const isImage = slot.kind === 'image' && stored;
  const thumb = isImage
    ? `style="background-image:url('/api/projects/${project.id}/assets/${slot.name}/file?t=${Date.now()}')"`
    : '';
  const icon = { image: '&#128444;', audio: '&#127925;', video: '&#127916;', model: '&#127922;' }[slot.kind];
  return `
    <div class="slot ${stored ? 'filled' : ''}" data-slot="${escapeAttr(slot.name)}">
      <div class="thumb" ${thumb}>${isImage ? '' : icon}</div>
      <div class="info">
        <strong>${escapeHtml(slot.label)}</strong>${slot.required ? '<strong> *</strong>' : ''}
        <small>${escapeHtml(filename || slot.help || 'Aucun fichier')}</small>
        ${slot.kind === 'audio' && stored
          ? `<audio controls preload="none" style="width:100%;height:28px;margin-top:4px"
                 src="/api/projects/${project.id}/assets/${slot.name}/file"></audio>` : ''}
      </div>
      <div class="actions">
        <button class="btn small" data-pick>Choisir</button>
        ${slot.stage ? `
          <button class="btn small ghost" data-from-video
                  title="Prendre une image dans une video">Depuis une video</button>
          ${stored ? `
            <button class="btn small ghost" data-cutout
                    title="Enlever le fond et poser le personnage sur le sol">Detourer</button>
            <button class="btn small ghost" data-restore
                    title="Revenir a l'image d'origine">&#8634;</button>` : ''}` : ''}
        ${stored ? '<button class="btn small ghost danger" data-clear>Retirer</button>' : ''}
      </div>
    </div>`;
}

function wireSlots(host) {
  const project = state.project;
  host.querySelectorAll('[data-slot]').forEach((element) => {
    const name = element.dataset.slot;
    const slot = state.boot.specs[project.type].slots.find((s) => s.name === name);
    element.querySelector('[data-pick]').onclick = () => {
      const input = document.createElement('input');
      input.type = 'file';
      input.accept = slot.exts.join(',');
      input.onchange = async () => {
        if (!input.files.length) return;
        try {
          const result = await upload(`/projects/${project.id}/assets/${name}`, input.files[0]);
          project.assets = result.assets;
          project.asset_names = result.asset_names;
          renderEditor();
          toast('Fichier ajoute.', 'success');
        } catch (error) { fail(error); }
      };
      input.click();
    };
    element.querySelector('[data-clear]')?.addEventListener('click', async () => {
      try {
        const result = await del(`/projects/${project.id}/assets/${name}`);
        project.assets = result.assets;
        renderEditor();
      } catch (error) { fail(error); }
    });

    // Personnages du plateau : detourage et image tiree d'une video.
    const applyAssets = (result) => {
      project.assets = result.assets;
      project.asset_names = result.asset_names || project.asset_names;
      renderEditor();
    };
    element.querySelector('[data-cutout]')?.addEventListener('click', async (event) => {
      const button = event.currentTarget;
      button.disabled = true;
      button.textContent = t('Detourage...');
      try {
        const { job } = await post(`/projects/${project.id}/assets/${name}/cutout`);
        applyAssets(await waitJob(job));
        toast(t('Personnage detoure.'), 'success');
      } catch (error) { fail(error); button.disabled = false; button.textContent = t('Detourer'); }
    });
    element.querySelector('[data-restore]')?.addEventListener('click', async () => {
      try {
        applyAssets(await post(`/projects/${project.id}/assets/${name}/restore`));
        toast(t('Image d\'origine retablie.'), 'success');
      } catch (error) { fail(error); }
    });
    element.querySelector('[data-from-video]')?.addEventListener('click', async () => {
      const path = await browseFile('video');
      if (!path) return;
      try {
        const { job } = await post(`/projects/${project.id}/assets/${name}/from-video`, { path });
        applyAssets(await waitJob(job));
        toast(t('Image extraite de la video.'), 'success');
      } catch (error) { fail(error); }
    });
  });
}

/* ------------------------------------------------------- champs de config */

function fieldHtml(field, value) {
  const id = 'f_' + field.key.replace(/\./g, '_');
  const help = field.help ? `<p class="hint">${escapeHtml(field.help)}</p>` : '';
  if (field.type === 'bool') {
    return `<label class="field"><span>&nbsp;</span>
      <span style="display:flex;gap:8px;align-items:center;color:var(--fg)">
        <input type="checkbox" id="${id}" data-field="${escapeAttr(field.key)}"
               ${value ? 'checked' : ''}> ${escapeHtml(field.label)}</span>${help}</label>`;
  }
  if (field.type === 'select') {
    const options = field.options.map((o) =>
      `<option value="${escapeAttr(o.value)}" ${o.value === value ? 'selected' : ''}>${escapeHtml(o.label)}</option>`).join('');
    return `<label class="field"><span>${escapeHtml(field.label)}</span>
      <select id="${id}" data-field="${escapeAttr(field.key)}" data-kind="select">${options}</select>${help}</label>`;
  }
  if (field.type === 'number') {
    return `<label class="field"><span>${escapeHtml(field.label)}</span>
      <input type="number" step="any" id="${id}" data-field="${escapeAttr(field.key)}"
             value="${escapeAttr(value ?? 0)}">${help}</label>`;
  }
  if (field.type === 'color' || field.type === 'color8') {
    const hex = String(value || '').replace('#', '');
    const rgb = '#' + (hex.slice(0, 6).padEnd(6, '0'));
    return `<label class="field"><span>${escapeHtml(field.label)}</span>
      <span class="row tight">
        <input type="color" value="${escapeAttr(rgb)}" data-color-for="${escapeAttr(field.key)}">
        <input type="text" id="${id}" data-field="${escapeAttr(field.key)}"
               value="${escapeAttr(hex)}" style="flex:1;font-family:var(--mono)"
               placeholder="${field.type === 'color8' ? 'rrggbbaa' : 'rrggbb'}">
      </span>${help}</label>`;
  }
  return `<label class="field"><span>${escapeHtml(field.label)}</span>
    <input type="text" id="${id}" data-field="${escapeAttr(field.key)}"
           value="${escapeAttr(value ?? '')}">${help}</label>`;
}

function fieldsHtml(spec, config) {
  const groups = new Map();
  for (const field of spec.fields) {
    const group = field.group || 'Configuration';
    if (!groups.has(group)) groups.set(group, []);
    groups.get(group).push(field);
  }
  let html = '';
  for (const [group, fields] of groups) {
    html += `<div class="group-title">${escapeHtml(group)}</div><div class="grid three">`;
    html += fields.map((f) => fieldHtml(f, config[f.key] ?? f.default)).join('');
    html += '</div>';
  }
  return html;
}

function wireFields(host) {
  const project = state.project;
  host.querySelectorAll('[data-field]').forEach((input) => {
    const key = input.dataset.field;
    const handler = () => {
      let value;
      if (input.type === 'checkbox') value = input.checked;
      else if (input.type === 'number') value = parseFloat(input.value) || 0;
      else if (input.dataset.kind === 'select') {
        const raw = input.value;
        value = isNaN(Number(raw)) ? raw : Number(raw);
      } else value = input.value;
      project.config[key] = value;
      saveProject();
    };
    input.oninput = handler;
    input.onchange = handler;
  });
  host.querySelectorAll('[data-color-for]').forEach((picker) => {
    picker.oninput = () => {
      const key = picker.dataset.colorFor;
      const text = host.querySelector(`[data-field="${CSS.escape(key)}"]`);
      const previous = String(project.config[key] || '');
      const alpha = previous.length === 8 ? previous.slice(6) : '';
      text.value = picker.value.replace('#', '') + alpha;
      project.config[key] = text.value;
      saveProject();
    };
  });
}

/* ------------------------------------------------------ metadonnees pack */

function metaHtml(project, { withIcon = true } = {}) {
  const meta = project.meta || {};
  return `
    <div class="card">
      <h2>Informations du pack</h2>
      <p class="hint">Ecrites dans <code>_pack_info.ini</code> (et en doublon dans _author.txt / _subtitle.txt).</p>
      <div class="grid two" style="margin-top:12px">
        <div>
          <label class="field"><span>Titre affiche dans le jeu</span>
            <input type="text" data-meta="title" value="${escapeAttr(meta.title || '')}"
                   placeholder="Par defaut : nom du dossier"></label>
          <label class="field"><span>Sous-titre</span>
            <input type="text" data-meta="subtitle" value="${escapeAttr(meta.subtitle || '')}"></label>
          <label class="field"><span>Auteurs (separes par des virgules)</span>
            <input type="text" data-meta="authors" value="${escapeAttr((meta.authors || []).join(', '))}"></label>
        </div>
        <div>
          <label class="field"><span>Description / readme</span>
            <textarea data-meta="readme" rows="6">${escapeHtml(meta.readme || '')}</textarea></label>
        </div>
      </div>
      ${withIcon ? `<div class="grid two" style="margin-top:6px">
        ${slotHtml(state.boot.specs[project.type].slots.find((s) => s.name === '_icon'), project)}
        ${state.boot.specs[project.type].slots.find((s) => s.name === '_pack_filler_image')
          ? slotHtml(state.boot.specs[project.type].slots.find((s) => s.name === '_pack_filler_image'), project) : ''}
      </div>
      <div class="group-title">Images proposees</div>
      <p class="hint">Extraites de la video a l'import. Clique pour definir l'icone du pack ;
         le bouton « fond » en fait l'image par defaut des clips.</p>
      <div class="row tight" style="margin:10px 0">
        <button class="btn small" id="frames-refresh">Regenerer les propositions</button>
        <span class="hint" id="frames-status"></span>
      </div>
      <div id="frames-grid" class="grid"
           style="grid-template-columns:repeat(auto-fill,minmax(150px,1fr))"></div>` : ''}
    </div>`;
}

function wireMeta(host) {
  const project = state.project;
  host.querySelectorAll('[data-meta]').forEach((input) => {
    input.oninput = () => {
      const key = input.dataset.meta;
      project.meta[key] = key === 'authors'
        ? input.value.split(',').map((s) => s.trim()).filter(Boolean)
        : input.value;
      saveProject();
    };
  });

  const grid = host.querySelector('#frames-grid');
  if (!grid) return;
  const status = host.querySelector('#frames-status');

  const paint = (frames) => {
    if (!frames.length) {
      grid.innerHTML = '<p class="hint">Aucune image : la source doit contenir une piste video.</p>';
      return;
    }
    grid.innerHTML = frames.map((frame) => `
      <div class="slot filled" style="flex-direction:column;align-items:stretch;padding:6px">
        <img src="/api/projects/${project.id}/frames/${encodeURIComponent(frame.name)}"
             style="width:100%;border-radius:6px;cursor:pointer" data-frame="${escapeAttr(frame.name)}"
             title="Definir comme icone du pack">
        <div class="row tight" style="margin-top:6px">
          <button class="btn small ghost" data-icon="${escapeAttr(frame.name)}">Icone</button>
          <button class="btn small ghost" data-filler="${escapeAttr(frame.name)}">Fond</button>
        </div>
      </div>`).join('');

    const assign = async (slot, frame) => {
      try {
        const result = await api(
          `/projects/${project.id}/assets/${slot}/from-frame`,
          { method: 'POST', body: JSON.stringify({ frame }) });
        project.assets = result.assets;
        project.asset_names = result.asset_names;
        toast(slot === '_icon' ? 'Icone definie.' : 'Image de fond definie.', 'success');
        renderEditor();
      } catch (error) { fail(error); }
    };
    grid.querySelectorAll('[data-frame]').forEach((img) =>
      img.onclick = () => assign('_icon', img.dataset.frame));
    grid.querySelectorAll('[data-icon]').forEach((b) =>
      b.onclick = () => assign('_icon', b.dataset.icon));
    grid.querySelectorAll('[data-filler]').forEach((b) =>
      b.onclick = () => assign('_pack_filler_image', b.dataset.filler));
  };

  api(`/projects/${project.id}/frames`).then((d) => paint(d.frames)).catch(() => paint([]));

  host.querySelector('#frames-refresh').onclick = async () => {
    status.textContent = t('Extraction...');
    try {
      const result = await post(`/projects/${project.id}/frames`, { count: 12 });
      paint(result.frames);
      status.textContent = t('%s images', result.made.length);
    } catch (error) { fail(error); status.textContent = ''; }
  };
}

/* -------------------------------------------------------- editeur simple */

function renderSimpleEditor() {
  const host = document.getElementById('view-editor');
  const project = state.project;
  const spec = state.boot.specs[project.type];

  host.innerHTML = editorHeader() + `
    <div class="card">
      <h2>Fichiers du pack</h2>
      <p class="hint">Les extensions non acceptees par le jeu (video autre qu'OGV) sont converties a la generation.</p>
      <div class="grid two" style="margin-top:12px">
        ${spec.slots.map((slot) => slotHtml(slot, project)).join('')}
      </div>
    </div>
    <div class="card">
      <h2>Configuration</h2>
      <p class="hint">Ecrite dans <code>${escapeHtml(spec.config_file || '')}</code>.</p>
      ${fieldsHtml(spec, project.config || {})}
    </div>
    ${metaAuthorsOnly(project)}
    ` + buildPanel();

  wireHeader(host);
  wireSlots(host);
  wireFields(host);
  wireMeta(host);
  wireBuildPanel(host);
}

function metaAuthorsOnly(project) {
  return `
    <div class="card">
      <h2>Credits</h2>
      <label class="field" style="max-width:520px"><span>Auteurs (separes par des virgules)</span>
        <input type="text" data-meta="authors"
               value="${escapeAttr((project.meta?.authors || []).join(', '))}"></label>
      <p class="hint">Ecrit dans <code>_author.txt</code>.</p>
    </div>`;
}

/* ---------------------------------------------------- editeur animateur */

function renderHostEditor() {
  const host = document.getElementById('view-editor');
  const project = state.project;
  const spec = state.boot.specs[project.type];
  const labels = spec.host_labels || {};
  const dialog = project.host_dialog || {};

  const sections = ['match_singleplayer', 'match_multiplayer', 'twitch_standard']
    .filter((key) => dialog[key])
    .map((key) => hostSectionHtml(key, dialog[key], labels))
    .join('');

  const placeholders = (spec.host_placeholders || [])
    .map(([token, meaning]) =>
      `<span class="tag"><code>${escapeHtml(token)}</code> — ${escapeHtml(t(meaning))}</span>`)
    .join(' ');

  host.innerHTML = editorHeader() + `
    <div class="card">
      <h2>Fichiers</h2>
      <div class="grid two" style="margin-top:12px">
        ${spec.slots.map((slot) => slotHtml(slot, project)).join('')}
      </div>
    </div>
    <div class="card">
      <h2>Identite</h2>
      ${fieldsHtml(spec, project.config || {})}
      <div class="row tight" style="margin-top:8px">
        <button class="btn ghost" id="host-fr">Repartir du modele francais</button>
        <button class="btn ghost" id="host-en">Repartir du modele anglais d'origine</button>
      </div>
    </div>
    <div class="card">
      <h2>Dialogues</h2>
      <p class="hint">Une ligne par replique alternative : le jeu en tire une au hasard.
        Utilise <code>\\n</code> ou un retour a la ligne dans le champ pour un saut de ligne.</p>
      <p class="hint" style="margin-top:8px">Variables : ${placeholders}</p>
      <div style="margin-top:14px">${sections}</div>
    </div>
    ${metaAuthorsOnly(project)}
    ` + buildPanel();

  wireHeader(host);
  wireSlots(host);
  wireFields(host);
  wireMeta(host);
  wireBuildPanel(host);

  host.querySelectorAll('[data-dialog]').forEach((textarea) => {
    textarea.oninput = () => {
      const [section, group, key] = textarea.dataset.dialog.split('|');
      const lines = textarea.value.split('\n').map((s) => s.trim()).filter(Boolean);
      if (key) project.host_dialog[section][group][key] = lines;
      else project.host_dialog[section][group] = lines;
      saveProject();
    };
  });

  const reset = async (which) => {
    if (!await confirmDialog('Reinitialiser',
      'Tous les dialogues personnalises seront perdus. Continuer ?')) return;
    project.host_dialog = JSON.parse(JSON.stringify(
      which === 'fr' ? spec.host_template_fr : spec.host_template_en));
    await saveNow();
    renderHostEditor();
  };
  host.querySelector('#host-fr').onclick = () => reset('fr');
  host.querySelector('#host-en').onclick = () => reset('en');
}

function hostSectionHtml(sectionKey, section, labels) {
  let inner = '';
  for (const [groupKey, group] of Object.entries(section)) {
    if (Array.isArray(group)) {
      inner += hostFieldHtml(sectionKey, groupKey, '', group, labels);
      continue;
    }
    inner += `<div class="group-title">${escapeHtml(labels[groupKey] || groupKey)}</div>`;
    inner += '<div class="grid two">';
    for (const [key, lines] of Object.entries(group)) {
      inner += hostFieldHtml(sectionKey, groupKey, key, lines, labels);
    }
    inner += '</div>';
  }
  return `<details class="host-section">
      <summary>${escapeHtml(labels[sectionKey] || sectionKey)}</summary>
      <div class="body">${inner}</div>
    </details>`;
}

function hostFieldHtml(sectionKey, groupKey, key, lines, labels) {
  const label = labels[key || groupKey] || key || groupKey;
  const value = (Array.isArray(lines) ? lines : [String(lines)]).join('\n');
  const rows = Math.min(6, Math.max(2, value.split('\n').length + 1));
  return `<label class="field"><span>${escapeHtml(label)}</span>
    <textarea rows="${rows}" data-dialog="${escapeAttr(`${sectionKey}|${groupKey}|${key}`)}">${escapeHtml(value)}</textarea></label>`;
}

/* ------------------------------------------------------ editeur chatter */

function renderChatterEditor() {
  const host = document.getElementById('view-editor');
  const project = state.project;
  const spec = state.boot.specs[project.type];
  const entries = project.chatter || [];

  host.innerHTML = editorHeader() + `
    <div class="card">
      <h2>Sons du chat</h2>
      <p class="hint">Les mots-cles « larges » se declenchent si le mot les contient (insensible a la casse).
         Les mots-cles « exacts » exigent le mot identique, casse comprise — pratique pour les emotes.</p>
      <div class="dropzone" id="chatter-drop" style="margin:12px 0">
        Glisse ici tes fichiers audio, ou <button class="btn small" id="chatter-add">parcourir</button>
      </div>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Fichier</th><th style="width:110px">Type</th>
            <th>Mots-cles</th><th style="width:150px">Ecoute</th><th style="width:60px"></th></tr></thead>
          <tbody id="chatter-body"></tbody>
        </table>
      </div>
    </div>
    <div class="card">
      <h2>Options</h2>
      ${fieldsHtml(spec, project.config || {})}
      <div class="grid two">${slotHtml(spec.slots[0], project)}</div>
    </div>
    ${metaAuthorsOnly(project)}
    ` + buildPanel();

  wireHeader(host);
  wireSlots(host);
  wireFields(host);
  wireMeta(host);
  wireBuildPanel(host);

  const body = host.querySelector('#chatter-body');
  body.innerHTML = entries.map((entry) => `
    <tr data-entry="${escapeAttr(entry.id)}">
      <td><input type="text" data-name value="${escapeAttr(entry.name)}"></td>
      <td><select data-mode>
        <option value="broad" ${entry.mode !== 'exact' ? 'selected' : ''}>Large</option>
        <option value="exact" ${entry.mode === 'exact' ? 'selected' : ''}>Exact</option>
      </select></td>
      <td><input type="text" data-keywords value="${escapeAttr((entry.keywords || []).join(', '))}"
                 placeholder="clap, bravo"></td>
      <td><audio controls preload="none" style="width:100%;height:30px"
                 src="/api/projects/${project.id}/chatter/${entry.id}/file"></audio></td>
      <td><button class="btn small ghost danger" data-del>&times;</button></td>
    </tr>`).join('') || '<tr><td colspan="5" class="hint">Aucun son.</td></tr>';

  body.querySelectorAll('[data-entry]').forEach((row) => {
    const entry = entries.find((e) => e.id === row.dataset.entry);
    row.querySelector('[data-name]').oninput = (e) => { entry.name = e.target.value; saveProject(); };
    row.querySelector('[data-mode]').onchange = (e) => { entry.mode = e.target.value; saveProject(); };
    row.querySelector('[data-keywords]').oninput = (e) => {
      entry.keywords = e.target.value.split(',').map((s) => s.trim()).filter(Boolean);
      saveProject();
    };
    row.querySelector('[data-del]').onclick = async () => {
      const result = await del(`/projects/${project.id}/chatter/${entry.id}`);
      project.chatter = result.chatter;
      renderChatterEditor();
    };
  });

  const addFiles = async (files) => {
    for (const file of files) {
      try {
        const result = await upload(`/projects/${project.id}/chatter`, file);
        project.chatter = result.chatter;
      } catch (error) { fail(error); }
    }
    renderChatterEditor();
  };

  host.querySelector('#chatter-add').onclick = () => {
    const input = document.createElement('input');
    input.type = 'file';
    input.multiple = true;
    input.accept = '.wav,.mp3,.ogg,.m4a,.flac';
    input.onchange = () => addFiles([...input.files]);
    input.click();
  };
  const drop = host.querySelector('#chatter-drop');
  drop.ondragover = (e) => { e.preventDefault(); drop.classList.add('over'); };
  drop.ondragleave = () => drop.classList.remove('over');
  drop.ondrop = (e) => {
    e.preventDefault();
    drop.classList.remove('over');
    addFiles([...e.dataTransfer.files]);
  };
}

/* --------------------------------------------------------- editeur voix */

function renderVoiceEditor() {
  const host = document.getElementById('view-editor');
  const project = state.project;
  const spec = state.boot.specs[project.type];
  const source = project.source || {};
  const options = project.options || (project.options = {});

  host.innerHTML = editorHeader() + `
    <div class="card">
      <h2>Source</h2>
      <p class="hint">Une video ou un fichier audio. Tout est converti par ffmpeg : aucun format a preparer.</p>
      <div class="row" style="margin:12px 0">
        <button class="btn" id="src-upload">Importer un fichier</button>
        <button class="btn ghost" id="src-browse">Choisir sur le disque (sans copie)</button>
        <div class="spacer"></div>
        <span class="hint" id="src-info" data-notr>${source.filename
          ? `${escapeHtml(source.filename)} — ${formatTime(source.duration || 0)}${source.has_video ? t(' — video') : ''}`
          : t('Aucune source')}</span>
      </div>

      <div class="group-title">Depuis YouTube (ou tout site gere par yt-dlp)</div>
      <div class="row">
        <input type="text" id="src-url" placeholder="https://www.youtube.com/watch?v=..."
               style="flex:2;min-width:280px" ${state.boot.ytdl.available ? '' : 'disabled'}>
        <select id="src-url-mode" style="flex:0 0 210px">
          <option value="video">Video + audio (pour le mode Dub)</option>
          <option value="audio">Audio seul (plus rapide)</option>
        </select>
        <button class="btn" id="src-url-probe" ${state.boot.ytdl.available ? '' : 'disabled'}>Verifier</button>
        <button class="btn primary" id="src-url-go" ${state.boot.ytdl.available ? '' : 'disabled'}>Importer</button>
      </div>
      <p class="hint">${state.boot.ytdl.available
        ? t('La video est telechargee dans le projet, puis traitee comme n\'importe quelle source.')
          + ' ' + t('A n\'utiliser que sur du contenu que tu as le droit de reutiliser.')
        : t('yt-dlp n\'est pas installe. Dans le dossier de l\'outil :')
          + ' <code>pip install yt-dlp</code>'}</p>
      ${source.origin ? `<p class="hint">Source actuelle :
        <a href="${escapeAttr(source.origin.url)}" target="_blank" rel="noopener"
           data-notr>${escapeHtml(source.origin.title)}</a>
        ${source.origin.uploader ? `<span data-notr>— ${escapeHtml(source.origin.uploader)}</span>` : ''}</p>` : ''}

      <div class="progress" id="src-progress" style="display:none"><div></div></div>
      <p class="hint" id="src-message"></p>
    </div>

    <div class="card">
      <h2>Decoupe automatique</h2>
      <p class="hint">Detecte les silences et fabrique un clip par prise de parole.
         Tu peux ensuite tout ajuster a la souris.</p>
      <div class="grid three" style="margin-top:12px">
        <label class="field"><span>Seuil de silence (dB)</span>
          <input type="number" id="sp-noise" value="${options.noise_db ?? -32}" step="1"></label>
        <label class="field"><span>Silence minimum (s)</span>
          <input type="number" id="sp-silence" value="${options.min_silence ?? 0.35}" step="0.05"></label>
        <label class="field"><span>Duree mini d'un clip (s)</span>
          <input type="number" id="sp-min" value="${options.min_len ?? 0.7}" step="0.1"></label>
        <label class="field"><span>Duree maxi d'un clip (s)</span>
          <input type="number" id="sp-max" value="${options.max_len ?? 6}" step="0.5"></label>
        <label class="field"><span>Marge autour (s)</span>
          <input type="number" id="sp-pad" value="${options.pad ?? 0.08}" step="0.01"></label>
        <label class="field"><span>Prefixe des noms</span>
          <input type="text" id="sp-base" value="${escapeAttr(options.base_name || project.name)}"></label>
      </div>
      <div class="row">
        <button class="btn primary" id="sp-run">Decouper</button>
        <label class="row tight" style="margin:0"><input type="checkbox" id="sp-replace" checked>
          <span class="hint">Remplacer les clips existants</span></label>
        <label class="row tight" style="margin:0"><input type="checkbox" id="sp-images"
          ${source.has_video ? 'checked' : 'disabled'}>
          <span class="hint">Extraire une image par clip depuis la video</span></label>
      </div>
      <div class="progress" id="sp-progress" style="display:none"><div></div></div>
      <p class="hint" id="sp-message"></p>
    </div>

    <div class="card">
      <h2>Sous-titres de la source</h2>
      <p class="hint">Quand la video en propose (officiels ou automatiques), ils sont recuperes
         a l'import. Ils donnent des decoupes plus propres que la detection de silences,
         et les sous-titres sont deja ecrits.</p>
      <p class="hint" id="tx-status" style="margin-top:10px">Chargement...</p>
      <div class="row" style="margin-top:10px">
        <button class="btn primary" id="tx-segment">Decouper sur les sous-titres</button>
        <button class="btn" id="tx-apply">Remplir les sous-titres des clips</button>
        <label class="row tight" style="margin:0"><input type="checkbox" id="tx-overwrite">
          <span class="hint">Ecraser les sous-titres deja saisis</span></label>
        <div class="spacer"></div>
        <button class="btn ghost" id="tx-import">Importer un .srt / .vtt</button>
        <button class="btn ghost" id="tx-export">Exporter les clips en .srt</button>
        <button class="btn ghost" id="tx-view">Voir</button>
      </div>
      <div class="progress" id="tx-progress2" style="display:none"><div></div></div>
      <p class="hint" id="tx-message2"></p>
    </div>

    <div class="card">
      <h2>Clips</h2>
      <div class="wave-toolbar">
        <button class="btn small" id="w-play">Lire / Pause</button>
        <button class="btn small ghost" id="w-play-region">Lire le clip</button>
        <button class="btn small ghost" id="w-add">Ajouter un clip ici</button>
        <button class="btn small ghost" id="w-zoom-in">+</button>
        <button class="btn small ghost" id="w-zoom-out">&minus;</button>
        <button class="btn small ghost" id="w-zoom-fit">Tout voir</button>
        <label class="row tight" style="margin:0"><input type="checkbox" id="w-follow" checked>
          <span class="hint">Suivre la lecture</span></label>
        ${source.has_video ? `<label class="row tight" style="margin:0">
          <input type="checkbox" id="w-video" ${options.show_video === false ? '' : 'checked'}>
          <span class="hint">Voir la video</span></label>` : ''}
        <div class="spacer"></div>
        <span class="wave-time" id="w-time">0:00.00</span>
      </div>
      ${source.has_video ? `<div id="viewer-box" ${options.show_video === false ? 'hidden' : ''}>
        <video id="viewer" muted playsinline preload="metadata"></video>
        <p class="hint" id="viewer-note">L'image suit la tete de lecture : le son vient
          de l'apercu audio, l'image de la video d'origine.</p>
      </div>` : ''}
      <div id="wave-host">
        <canvas id="wave-canvas"></canvas>
        <canvas id="wave-ruler"></canvas>
      </div>
      <p class="hint" style="margin-top:6px">
        Clic = deplacer la tete de lecture &middot; Alt+glisser sur une zone vide = creer un clip &middot;
        glisser un bord = ajuster &middot; Maj+glisser = deplacer le clip &middot; double-clic = ecouter &middot;
        Ctrl+molette = zoom.</p>

      <div class="row" style="margin:12px 0">
        <button class="btn" id="tr-run" ${state.boot.whisper.available ? '' : 'disabled'}>
          Transcrire en francais</button>
        <label class="row tight" style="margin:0"><input type="checkbox" id="tr-overwrite">
          <span class="hint">Ecraser les sous-titres existants</span></label>
        <div class="spacer"></div>
        <span class="hint">${state.boot.whisper.available
          ? `Whisper ${escapeHtml(state.boot.whisper.model)} (${escapeHtml(state.boot.whisper.device)})`
          : 'faster-whisper non installe — voir Reglages'}</span>
      </div>
      <div class="progress" id="tr-progress" style="display:none"><div></div></div>
      <p class="hint" id="tr-message"></p>

      <div class="table-wrap" style="margin-top:12px">
        <table>
          <thead><tr>
            <th style="width:34px"></th><th style="width:44px">#</th>
            <th>Nom du fichier</th>
            <th class="num" style="width:80px">Debut</th>
            <th class="num" style="width:80px">Fin</th>
            <th class="num" style="width:66px">Duree</th>
            <th>Sous-titre</th>
            <th style="width:70px">Image</th>
            <th style="width:120px"></th>
          </tr></thead>
          <tbody id="clip-body"></tbody>
        </table>
      </div>
      <div class="row" style="margin-top:10px">
        <span class="hint" id="clip-stats"></span>
        <div class="spacer"></div>
        <button class="btn small ghost" id="clip-images">Images depuis la video</button>
        <button class="btn small ghost" id="clip-renumber">Renommer en serie</button>
        <button class="btn small ghost danger" id="clip-clear">Tout supprimer</button>
      </div>
    </div>

    <div class="card">
      <h2>Mode Dub</h2>
      <p class="hint">Un pack devient un pack Dub des qu'il contient <code>dub_video.ogv</code>.
        La video source est convertie en OGV/Theora — le seul format lu par Godot.
        Limite conseillee : 6 s par clip. La video ne s'affiche pas pendant
        l'enregistrement : le jeu la joue a la fin de la manche, doublee avec tes prises.</p>
      <label class="row tight" style="margin:12px 0">
        <input type="checkbox" id="dub-enabled" ${project.dub?.enabled ? 'checked' : ''}>
        <span>Generer un pack Dub a partir de la video source</span>
      </label>
      <div id="dub-options" style="${project.dub?.enabled ? '' : 'display:none'}">
        <div class="grid three">
          <label class="field"><span>Qualite OGV (0-10)</span>
            <input type="number" id="dub-quality" min="0" max="10" value="${options.ogv_quality ?? 7}"></label>
          <label class="field"><span>Hauteur maxi (px)</span>
            <input type="number" id="dub-height" value="${options.ogv_height ?? 720}"></label>
          <label class="field"><span>Personnages (separes par des virgules)</span>
            <input type="text" id="dub-characters"
                   value="${escapeAttr((project.dub?.characters || []).join(', '))}"
                   placeholder="Narrateur, Heros"></label>
        </div>
        <label class="row tight" style="margin:0 0 12px">
          <input type="checkbox" id="dub-suffix" ${options.timestamp_suffix ? 'checked' : ''}>
          <span class="hint">Ajouter le timestamp au nom du fichier (ex. 07_MonClip_44-048)</span>
        </label>
        <label class="row tight" style="margin:0 0 12px">
          <input type="checkbox" id="dub-clip-images"
                 ${options.dub_clip_images === false ? '' : 'checked'}>
          <span class="hint">Joindre une image a chaque clip (les packs Dub de la communaute
            n'y mettent souvent que des portraits de personnages)</span>
        </label>

        <div class="group-title">Detection des locuteurs</div>
        <p class="hint">Repartit les clips entre les voix de la source, pour remplir la
          colonne Personnage sans tout saisir a la main.</p>
        <div class="row" style="margin:10px 0">
          <button class="btn" id="dub-diarize"
                  ${state.boot.diarize.available && state.boot.diarize.token ? '' : 'disabled'}>
            Detecter les locuteurs</button>
          <label class="row tight" style="margin:0"><input type="checkbox" id="dub-diarize-overwrite">
            <span class="hint">Ecraser les personnages deja attribues</span></label>
          <div class="spacer"></div>
          <span class="hint">${!state.boot.diarize.available
            ? 'pyannote.audio non installe — voir Reglages'
            : (state.boot.diarize.token ? 'Pret' : 'Jeton Hugging Face manquant — voir Reglages')}</span>
        </div>

        <div class="group-title">Piste d'ambiance</div>
        <p class="hint">La bande son sans les voix, jouee pendant que tu doubles.
          Demucs la fabrique depuis la source.</p>
        <div class="row" style="margin:10px 0">
          <button class="btn" id="dub-backing"
                  ${state.boot.demucs.available ? '' : 'disabled'}>
            Separer les voix de la musique</button>
          <div class="spacer"></div>
          <span class="hint">${state.boot.demucs.available
            ? `demucs ${escapeHtml(state.boot.demucs.model)}`
            : 'demucs non installe — voir Reglages'}</span>
        </div>
        <div class="row" style="margin:10px 0">
          <select id="dub-rename-from" style="flex:0 0 200px"></select>
          <span class="hint">&rarr;</span>
          <input type="text" id="dub-rename-to" placeholder="Tonton" style="flex:0 0 200px">
          <button class="btn ghost" id="dub-rename">Renommer partout</button>
          <span class="hint">Remplace le nom dans tous les clips concernes.</span>
        </div>
        <div class="progress" id="dub-progress" style="display:none"><div></div></div>
        <p class="hint" id="dub-message"></p>

        <div class="grid two">
          ${slotHtml(spec.slots.find((s) => s.name === '_backing_track'), project)}
        </div>
      </div>
    </div>

    ${metaHtml(project)}
    ` + buildPanel();

  wireHeader(host);
  wireSlots(host);
  wireMeta(host);
  wireBuildPanel(host);
  wireVoiceSource(host);
  wireVoiceSplit(host);
  wireVoiceTranscript(host);
  wireVoiceWave(host);
  wireVoiceDub(host);
  renderClipTable();
}

/* ------- source ------------------------------------------------------- */

function wireVoiceSource(host) {
  const project = state.project;
  const progress = host.querySelector('#src-progress');
  const bar = progress.querySelector('div');
  const message = host.querySelector('#src-message');

  const run = async (starter) => {
    const previousClips = (project.clips || []).length;
    progress.style.display = '';
    bar.style.width = '0%';
    try {
      const { job } = await starter();
      await waitJob(job, (j) => {
        bar.style.width = Math.round(j.progress * 100) + '%';
        message.textContent = j.message || '';
      });
      state.project = await api(`/projects/${project.id}`);
      // Les clips designent des instants de l'ancienne source : les garder
      // apres un changement de source donne des extraits incoherents.
      if (previousClips) {
        const keep = await confirmDialog(
          t('Clips de l\'ancienne source'),
          t('Ce projet contient encore %s clip(s) decoupes dans la source precedente. '
            + 'Les supprimer ? (Annuler les conserve tels quels.)', previousClips));
        if (keep) {
          state.project.clips = [];
          await saveNow();
        }
      }
      toast('Source prete.', 'success');
      renderVoiceEditor();
    } catch (error) { fail(error); }
    finally { progress.style.display = 'none'; }
  };

  host.querySelector('#src-upload').onclick = () => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.mp4,.mkv,.webm,.mov,.avi,.m4v,.ogv,.wav,.mp3,.ogg,.m4a,.aac,.flac,.opus';
    input.onchange = () => {
      if (!input.files.length) return;
      message.textContent = 'Envoi du fichier...';
      run(() => upload(`/projects/${project.id}/source/upload`, input.files[0]));
    };
    input.click();
  };

  host.querySelector('#src-browse').onclick = async () => {
    const path = await browseFile('media');
    if (!path) return;
    run(() => post(`/projects/${project.id}/source/path`, { path }));
  };

  const urlInput = host.querySelector('#src-url');
  const modeSelect = host.querySelector('#src-url-mode');

  host.querySelector('#src-url-probe').onclick = async () => {
    const url = urlInput.value.trim();
    if (!url) return toast('Colle une adresse de video.', 'error');
    message.textContent = 'Lecture des informations...';
    try {
      const info = await post(`/projects/${project.id}/source/youtube/probe`, { url });
      message.innerHTML = `<b>${escapeHtml(info.title)}</b> — ${formatTime(info.duration)}`
        + (info.uploader ? ` — ${escapeHtml(info.uploader)}` : '')
        + (info.is_live ? ' — <span style="color:var(--error)">direct, non importable</span>' : '');
    } catch (error) { fail(error); message.textContent = ''; }
  };

  host.querySelector('#src-url-go').onclick = () => {
    const url = urlInput.value.trim();
    if (!url) return toast('Colle une adresse de video.', 'error');
    message.textContent = 'Telechargement...';
    run(() => post(`/projects/${project.id}/source/youtube`,
                   { url, mode: modeSelect.value }));
  };

  urlInput.onkeydown = (e) => {
    if (e.key === 'Enter') host.querySelector('#src-url-go').click();
  };
}

/* ------- decoupe ------------------------------------------------------ */

function wireVoiceSplit(host) {
  const project = state.project;
  const progress = host.querySelector('#sp-progress');
  const bar = progress.querySelector('div');
  const message = host.querySelector('#sp-message');

  host.querySelector('#sp-run').onclick = async () => {
    const params = {
      noise_db: parseFloat(host.querySelector('#sp-noise').value),
      min_silence: parseFloat(host.querySelector('#sp-silence').value),
      min_len: parseFloat(host.querySelector('#sp-min').value),
      max_len: parseFloat(host.querySelector('#sp-max').value),
      pad: parseFloat(host.querySelector('#sp-pad').value),
      base_name: host.querySelector('#sp-base').value,
      replace: host.querySelector('#sp-replace').checked,
      clip_images: host.querySelector('#sp-images').checked,
    };
    Object.assign(project.options, params);
    await saveNow();
    progress.style.display = '';
    bar.style.width = '0%';
    try {
      const { job } = await post(`/projects/${project.id}/autosplit`, params);
      const result = await waitJob(job, (j) => {
        bar.style.width = Math.round(j.progress * 100) + '%';
        message.textContent = j.message || '';
      });
      project.clips = result.clips;
      message.textContent = t('%s clips detectes.', result.count)
        + (result.merged ? ' ' + t('%s repliques repetees fusionnees.', result.merged) : '');
      state.wave?.setRegions(project.clips);
      renderClipTable();
      toast(t('%s clips detectes.', result.count), 'success');
    } catch (error) { fail(error); }
    finally { setTimeout(() => { progress.style.display = 'none'; }, 700); }
  };
}

/* ------- sous-titres de la source ------------------------------------- */

async function wireVoiceTranscript(host) {
  const project = state.project;
  const status = host.querySelector('#tx-status');
  const progress = host.querySelector('#tx-progress2');
  const bar = progress.querySelector('div');
  const message = host.querySelector('#tx-message2');
  const buttons = ['#tx-segment', '#tx-apply', '#tx-view'].map((s) => host.querySelector(s));
  let transcript = { count: 0 };

  const refresh = async () => {
    try {
      transcript = await api(`/projects/${project.id}/transcript`);
    } catch { transcript = { count: 0 }; }
    const has = transcript.count > 0;
    buttons.forEach((b) => { b.disabled = !has; });
    status.innerHTML = has
      ? escapeHtml(t('%s repliques — source : %s', transcript.count, t(transcript.source)))
        + (transcript.lang ? `${t(' — langue :')} <code>${escapeHtml(transcript.lang)}</code>` : '')
      : t('Aucun sous-titre pour cette source. Utilise la decoupe par silences, '
        + 'la transcription Whisper, ou importe un fichier .srt / .vtt.');
  };
  await refresh();

  host.querySelector('#tx-segment').onclick = async () => {
    const options = project.options || {};
    progress.style.display = '';
    bar.style.width = '0%';
    try {
      const { job } = await post(`/projects/${project.id}/transcript/segment`, {
        min_len: options.min_len ?? 0.7,
        max_len: options.max_len ?? 6,
        merge_gap: 0.35,
        pad: options.pad ?? 0.05,
        base_name: options.base_name || project.name,
        replace: true,
        clip_images: !!project.source?.has_video,
      });
      const result = await waitJob(job, (j) => {
        bar.style.width = Math.round(j.progress * 100) + '%';
        message.textContent = j.message || '';
      });
      project.clips = result.clips;
      state.wave?.setRegions(project.clips);
      renderClipTable();
      message.textContent = t('%s clips crees, sous-titres inclus.', result.count)
        + (result.merged ? ' ' + t('%s repliques repetees fusionnees.', result.merged) : '');
      toast(t('%s clips crees depuis les sous-titres.', result.count), 'success');
    } catch (error) { fail(error); }
    finally { setTimeout(() => { progress.style.display = 'none'; }, 700); }
  };

  host.querySelector('#tx-apply').onclick = async () => {
    try {
      await saveNow();
      const result = await post(`/projects/${project.id}/transcript/apply`,
        { overwrite: host.querySelector('#tx-overwrite').checked });
      project.clips = result.clips;
      renderClipTable();
      toast(t('%s sous-titres remplis.', result.filled), 'success');
    } catch (error) { fail(error); }
  };

  host.querySelector('#tx-view').onclick = () => {
    const dialog = modal('Sous-titres', '<pre class="code"></pre>', { wide: true });
    dialog.body.querySelector('pre').textContent = (transcript.cues || [])
      .map((c) => `${formatTime(c.start)} → ${formatTime(c.end)}  ${c.text}`).join('\n');
  };

  host.querySelector('#tx-export').onclick = async () => {
    // Les sous-titres exportes sont ceux des clips, pas ceux de la source :
    // c'est le travail fait dans le tableau que l'on recupere.
    await saveNow();
    window.location.href = `/api/projects/${project.id}/subtitles.srt`;
  };

  host.querySelector('#tx-import').onclick = () => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.srt,.vtt,.json3,.json';
    input.onchange = async () => {
      if (!input.files.length) return;
      try {
        const result = await upload(
          `/projects/${project.id}/transcript/upload`, input.files[0]);
        toast(t('%s repliques importees.', result.count), 'success');
        await refresh();
      } catch (error) { fail(error); }
    };
    input.click();
  };
}

/* ------- forme d'onde ------------------------------------------------- */

async function wireVoiceWave(host) {
  const project = state.project;
  const canvas = host.querySelector('#wave-canvas');
  const ruler = host.querySelector('#wave-ruler');
  const timeLabel = host.querySelector('#w-time');
  state.wave?.destroy();
  state.wave = null;

  const wave = new Waveform(canvas, ruler, {
    onSeek: (t) => { player.currentTime = t; timeLabel.textContent = formatTime(t); },
    onRegionSelect: (id) => { state.selectedClip = id; highlightClipRow(id); },
    onRegionChange: (id, start, end) => {
      const clip = project.clips.find((c) => c.id === id);
      if (!clip) return;
      clip.start = start;
      clip.end = end;
      saveProject();
      renderClipTable();
    },
    onRegionCreate: (start, end) => {
      const clip = {
        id: Math.random().toString(36).slice(2, 10),
        name: `${project.name}_${(project.clips.length + 1).toString().padStart(3, '0')}`,
        start, end, caption: '', image: null, characters: [],
        dub_only: false, dub_timestamps: [], gain_db: 0, enabled: true,
      };
      project.clips.push(clip);
      project.clips.sort((a, b) => a.start - b.start);
      saveProject();
      state.selectedClip = clip.id;
      wave.setRegions(project.clips);
      wave.setSelected(clip.id);
      renderClipTable();
    },
    onRegionPlay: (id) => playClip(id),
  });
  state.wave = wave;
  wave.following = true;

  player.src = `/api/projects/${project.id}/audio?t=${Date.now()}`;
  player.load();

  const viewer = wireViewer(host, project);

  try {
    const data = await api(`/projects/${project.id}/peaks`);
    wave.setPeaks(data.peaks, data.duration);
  } catch { /* pas encore de source */ }
  wave.setRegions(project.clips || []);

  const tick = () => {
    if (!player.paused) {
      wave.setTime(player.currentTime);
      timeLabel.textContent = formatTime(player.currentTime);
      viewer.sync(false);
      if (state.playStopAt !== null && player.currentTime >= state.playStopAt) {
        player.pause();
        state.playStopAt = null;
      }
    }
    if (state.wave === wave) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);

  host.querySelector('#w-play').onclick = () => {
    state.playStopAt = null;
    if (player.paused) player.play().catch(() => {}); else player.pause();
  };
  host.querySelector('#w-play-region').onclick = () => playClip(state.selectedClip);
  host.querySelector('#w-zoom-in').onclick = () => wave.setZoom(wave.zoom * 1.6, wave.time);
  host.querySelector('#w-zoom-out').onclick = () => wave.setZoom(wave.zoom / 1.6, wave.time);
  host.querySelector('#w-zoom-fit').onclick = () => wave.setZoom(1);
  host.querySelector('#w-follow').onchange = (e) => { wave.following = e.target.checked; };
  host.querySelector('#w-add').onclick = () => {
    const start = wave.time;
    const end = Math.min(wave.duration, start + 2);
    wave.handlers.onRegionCreate(round3(start), round3(end));
  };

  host.querySelector('#tr-run').onclick = () => runTranscription(host);
}

/* ------- image de la video, calee sur la lecture ---------------------- */

function wireViewer(host, project) {
  const box = host.querySelector('#viewer-box');
  const video = host.querySelector('#viewer');
  const toggle = host.querySelector('#w-video');
  player.onplay = player.onpause = player.onseeked = null;
  if (!box || !video) return { sync: () => {} };

  video.src = `/api/projects/${project.id}/video`;
  video.load();

  // Le son reste celui de l'apercu : la video, muette, se contente de
  // suivre. Deux lecteurs derivent toujours un peu, d'ou le recalage.
  const sync = (force) => {
    if (!video.isConnected || box.hidden || !video.duration) return;
    const time = Math.max(0, Math.min(player.currentTime, video.duration - 0.05));
    if (force || Math.abs(video.currentTime - time) > 0.25) {
      try { video.currentTime = time; } catch { /* pas encore pret */ }
    }
  };

  video.onloadedmetadata = () => sync(true);
  video.onerror = () => {
    box.hidden = true;
    if (toggle) { toggle.checked = false; toggle.disabled = true; }
    toast('Le navigateur ne sait pas lire cette video : image indisponible.', 'error');
  };

  player.onplay = () => {
    sync(true);
    if (video.isConnected && !box.hidden) video.play().catch(() => {});
  };
  player.onpause = () => { if (video.isConnected) video.pause(); };
  player.onseeked = () => sync(true);

  if (toggle) {
    toggle.onchange = () => {
      box.hidden = !toggle.checked;
      (project.options || (project.options = {})).show_video = toggle.checked;
      saveProject();
      if (!toggle.checked) return video.pause();
      sync(true);
      if (!player.paused) video.play().catch(() => {});
    };
  }
  return { sync };
}

function playClip(id) {
  const clip = state.project.clips.find((c) => c.id === id);
  if (!clip) return toast('Selectionne un clip.', 'error');
  player.currentTime = clip.start;
  state.playStopAt = clip.end;
  player.play().catch(() => {});
}

async function runTranscription(host) {
  const project = state.project;
  const progress = host.querySelector('#tr-progress');
  const bar = progress.querySelector('div');
  const message = host.querySelector('#tr-message');
  progress.style.display = '';
  bar.style.width = '0%';
  message.textContent = 'Chargement du modele (premiere fois : telechargement)...';
  try {
    await saveNow();
    const { job } = await post(`/projects/${project.id}/transcribe`, {
      language: 'fr',
      overwrite: host.querySelector('#tr-overwrite').checked,
    });
    const result = await waitJob(job, (j) => {
      bar.style.width = Math.round(j.progress * 100) + '%';
      message.textContent = j.message || '';
    });
    project.clips = result.clips;
    renderClipTable();
    toast(t('%s clips transcrits.', result.transcribed), 'success');
  } catch (error) { fail(error); }
  finally { setTimeout(() => { progress.style.display = 'none'; }, 700); }
}

/* ------- tableau des clips -------------------------------------------- */

function renderClipTable() {
  const project = state.project;
  const body = document.getElementById('clip-body');
  if (!body) return;
  const clips = project.clips || [];
  const isDub = !!project.dub?.enabled;
  const hasVideo = !!project.source?.has_video;
  const limit = isDub ? 6 : 60;

  body.innerHTML = clips.map((clip, index) => {
    const length = clip.end - clip.start;
    const over = length > limit;
    return `
    <tr data-clip="${escapeAttr(clip.id)}" class="${clip.enabled === false ? 'disabled' : ''}">
      <td><input type="checkbox" data-enabled ${clip.enabled === false ? '' : 'checked'}></td>
      <td class="num">${index + 1}</td>
      <td><input type="text" data-name value="${escapeAttr(clip.name)}"></td>
      <td class="num">${clip.start.toFixed(2)}</td>
      <td class="num">${clip.end.toFixed(2)}</td>
      <td class="num" style="${over ? 'color:var(--error)' : ''}">${length.toFixed(2)}</td>
      <td><input type="text" data-caption value="${escapeAttr(clip.caption || '')}"
                 placeholder="sous-titre"></td>
      ${isDub ? `<td><input type="text" data-character list="dub-characters"
                 value="${escapeAttr((clip.characters || [])[0] || '')}" placeholder="personnage"></td>
        <td style="text-align:center"><input type="checkbox" data-dubonly
                 ${clip.dub_only ? 'checked' : ''} title="Uniquement en mode Dub"></td>` : ''}
      <td class="row tight" style="border:0">
        ${clip.image
          ? `<img src="/api/projects/${project.id}/clips/${clip.id}/image?t=${clip._v || 0}"
                  style="height:26px;border-radius:4px">` : ''}
        ${hasVideo ? '<button class="btn small ghost" data-from-video title="Image de la video a cet instant">&#127916;</button>' : ''}
        <button class="btn small ghost" data-image title="Choisir un fichier">&#128193;</button>
      </td>
      <td class="row tight" style="border:0">
        <button class="btn small ghost" data-play title="Ecouter">&#9654;</button>
        <button class="btn small ghost" data-zoom title="Zoomer">&#128269;</button>
        <button class="btn small ghost danger" data-del title="Supprimer">&times;</button>
      </td>
    </tr>`;
  }).join('') || `<tr><td colspan="${isDub ? 11 : 9}" class="hint">Aucun clip. Importe une source puis lance la decoupe.</td></tr>`;

  // En-tetes supplementaires du mode Dub + liste des personnages connus.
  const head = document.querySelector('#clip-body')?.previousElementSibling?.querySelector('tr');
  if (head) {
    const extra = head.querySelectorAll('.dub-col').length > 0;
    if (isDub && !extra) {
      head.children[6].insertAdjacentHTML('afterend',
        '<th class="dub-col">Personnage</th><th class="dub-col" style="width:56px">Dub seul</th>');
    } else if (!isDub && extra) {
      head.querySelectorAll('.dub-col').forEach((el) => el.remove());
    }
  }
  let datalist = document.getElementById('dub-characters');
  if (!datalist) {
    datalist = document.createElement('datalist');
    datalist.id = 'dub-characters';
    document.body.appendChild(datalist);
  }
  datalist.innerHTML = (project.dub?.characters || [])
    .map((c) => `<option value="${escapeAttr(c)}">`).join('');

  const active = clips.filter((c) => c.enabled !== false);
  const total = active.reduce((sum, c) => sum + (c.end - c.start), 0);
  const over = active.filter((c) => c.end - c.start > limit).length;
  document.getElementById('clip-stats').textContent =
    t('%s clips actifs — %s au total', active.length, formatTime(total))
    + (over ? t(' — %s depassent %s s', over, limit) : '');

  body.querySelectorAll('[data-clip]').forEach((row) => {
    const clip = clips.find((c) => c.id === row.dataset.clip);
    row.onclick = (e) => {
      if (e.target.closest('button') || e.target.closest('input')) return;
      state.selectedClip = clip.id;
      state.wave?.setSelected(clip.id);
      highlightClipRow(clip.id);
    };
    row.querySelector('[data-name]').oninput = (e) => { clip.name = e.target.value; saveProject(); };
    row.querySelector('[data-caption]').oninput = (e) => { clip.caption = e.target.value; saveProject(); };
    row.querySelector('[data-enabled]').onchange = (e) => {
      clip.enabled = e.target.checked;
      saveProject();
      state.wave?.setRegions(clips);
      renderClipTable();
    };
    row.querySelector('[data-character]')?.addEventListener('input', (e) => {
      const value = e.target.value.trim();
      clip.characters = value ? [value] : [];
      saveProject();
    });
    row.querySelector('[data-dubonly]')?.addEventListener('change', (e) => {
      clip.dub_only = e.target.checked;
      saveProject();
    });
    row.querySelector('[data-play]').onclick = () => playClip(clip.id);
    row.querySelector('[data-zoom]').onclick = () => {
      state.selectedClip = clip.id;
      state.wave?.setSelected(clip.id);
      state.wave?.zoomToRegion(clip);
    };
    row.querySelector('[data-del]').onclick = () => {
      project.clips = clips.filter((c) => c.id !== clip.id);
      saveProject();
      state.wave?.setRegions(project.clips);
      renderClipTable();
    };
    row.querySelector('[data-from-video]')?.addEventListener('click', async () => {
      try {
        const result = await post(
          `/projects/${project.id}/clips/${clip.id}/image/from-frame`, {});
        Object.assign(clip, result.clip);
        clip._v = Date.now();
        renderClipTable();
      } catch (error) { fail(error); }
    });
    row.querySelector('[data-image]').onclick = () => {
      const input = document.createElement('input');
      input.type = 'file';
      input.accept = '.png,.jpg,.jpeg';
      input.onchange = async () => {
        if (!input.files.length) return;
        try {
          const result = await upload(
            `/projects/${project.id}/clips/${clip.id}/image`, input.files[0]);
          Object.assign(clip, result.clip);
          renderClipTable();
        } catch (error) { fail(error); }
      };
      input.click();
    };
  });

  highlightClipRow(state.selectedClip);

  const imagesButton = document.getElementById('clip-images');
  imagesButton.disabled = !hasVideo || !clips.length;
  imagesButton.onclick = async () => {
    try {
      const { job } = await post(`/projects/${project.id}/clips/images/from-video`);
      const result = await waitJob(job, (j) => {
        imagesButton.textContent = j.message ? t('Images %s', t(j.message)) : t('Images...');
      });
      project.clips = result.clips;
      project.clips.forEach((c) => { c._v = Date.now(); });
      renderClipTable();
      toast('Images extraites.', 'success');
    } catch (error) { fail(error); }
    finally { imagesButton.textContent = t('Images depuis la video'); }
  };

  document.getElementById('clip-renumber').onclick = () => {
    const base = (project.options?.base_name || project.name).trim();
    project.clips.forEach((clip, index) => {
      clip.name = `${base}_${(index + 1).toString().padStart(3, '0')}`;
    });
    saveProject();
    state.wave?.setRegions(project.clips);
    renderClipTable();
  };
  document.getElementById('clip-clear').onclick = async () => {
    if (!await confirmDialog('Tout supprimer', 'Supprimer tous les clips de ce projet ?')) return;
    project.clips = [];
    saveProject();
    state.wave?.setRegions([]);
    renderClipTable();
  };
}

function highlightClipRow(id) {
  document.querySelectorAll('#clip-body tr').forEach((row) => {
    row.classList.toggle('selected', row.dataset.clip === id);
  });
}

/* ------- dub ---------------------------------------------------------- */

function wireVoiceDub(host) {
  const project = state.project;
  const toggle = host.querySelector('#dub-enabled');
  const options = host.querySelector('#dub-options');
  toggle.onchange = () => {
    project.dub = project.dub || {};
    project.dub.enabled = toggle.checked;
    // Choix explicite : un reimport de la source ne le remettra pas d'office.
    project.dub.chosen = true;
    options.style.display = toggle.checked ? '' : 'none';
    if (toggle.checked && !project.source?.has_video) {
      toast('La source actuelle n\'a pas de piste video : ajoute une video pour le mode Dub.', 'error');
    }
    saveProject();
    renderClipTable();
  };
  host.querySelector('#dub-quality').oninput = (e) => {
    project.options.ogv_quality = parseInt(e.target.value, 10) || 7;
    saveProject();
  };
  host.querySelector('#dub-height').oninput = (e) => {
    project.options.ogv_height = parseInt(e.target.value, 10) || 720;
    saveProject();
  };
  host.querySelector('#dub-suffix').onchange = (e) => {
    project.options.timestamp_suffix = e.target.checked;
    saveProject();
  };
  host.querySelector('#dub-characters').oninput = (e) => {
    project.dub.characters = e.target.value.split(',').map((s) => s.trim()).filter(Boolean);
    saveProject();
  };
  host.querySelector('#dub-clip-images').onchange = (e) => {
    project.options.dub_clip_images = e.target.checked;
    saveProject();
  };

  const progress = host.querySelector('#dub-progress');
  const bar = progress.querySelector('div');
  const message = host.querySelector('#dub-message');
  const run = async (button, label, starter, done) => {
    button.disabled = true;
    progress.style.display = '';
    bar.style.width = '0%';
    message.textContent = label;
    try {
      const { job } = await starter();
      const result = await waitJob(job, (j) => {
        bar.style.width = Math.round(j.progress * 100) + '%';
        message.textContent = t(j.message || '') || label;
      });
      done(result);
    } catch (error) { fail(error); message.textContent = ''; }
    finally {
      button.disabled = false;
      setTimeout(() => { progress.style.display = 'none'; }, 900);
    }
  };

  // Renommage en bloc : la diarisation ne sort que « Locuteur 1 », « 2 »...
  const renameFrom = host.querySelector('#dub-rename-from');
  const renameTo = host.querySelector('#dub-rename-to');
  const paintCharacters = () => {
    const noms = project.dub?.characters || [];
    renameFrom.innerHTML = noms.length
      ? noms.map((n) => `<option>${escapeHtml(n)}</option>`).join('')
      : `<option value="">${escapeHtml(t('Aucun personnage'))}</option>`;
    host.querySelector('#dub-rename').disabled = !noms.length;
  };
  paintCharacters();
  host.querySelector('#dub-rename').onclick = async () => {
    const before = renameFrom.value;
    const after = renameTo.value.trim();
    if (!before || !after) return toast(t('Choisis un personnage et son nouveau nom.'), 'error');
    try {
      await saveNow();
      const result = await post(`/projects/${project.id}/characters/rename`,
                                { from: before, to: after });
      project.clips = result.clips;
      project.dub.characters = result.characters;
      renameTo.value = '';
      paintCharacters();
      host.querySelector('#dub-characters').value = result.characters.join(', ');
      renderClipTable();
      toast(t('%s clips renommes.', result.renamed), 'success');
    } catch (error) { fail(error); }
  };

  const diarizeButton = host.querySelector('#dub-diarize');
  diarizeButton.onclick = () => run(diarizeButton, t('Detection des locuteurs'),
    async () => {
      await saveNow();
      return post(`/projects/${project.id}/diarize`, {
        overwrite: host.querySelector('#dub-diarize-overwrite').checked,
      });
    },
    (result) => {
      project.clips = result.clips;
      project.dub.characters = [...new Set([...(project.dub.characters || []), ...result.names])];
      host.querySelector('#dub-characters').value = project.dub.characters.join(', ');
      paintCharacters();
      renderClipTable();
      message.textContent = t('%s voix trouvees, %s clips attribues.',
                              result.speakers, result.filled);
      toast(t('%s voix trouvees, %s clips attribues.', result.speakers, result.filled), 'success');
    });

  const backingButton = host.querySelector('#dub-backing');
  backingButton.onclick = () => run(backingButton, t('Separation des voix'),
    () => post(`/projects/${project.id}/backing-track`),
    (result) => {
      project.assets = result.assets;
      project.asset_names = result.asset_names;
      renderVoiceEditor();
      toast(t('Piste d\'ambiance prete.'), 'success');
    });
}

/* --------------------------------------------------- vue packs installes */

async function renderLibrary() {
  const host = document.getElementById('view-library');
  host.innerHTML = '<div class="card"><h2>Chargement...</h2></div>';
  try {
    const data = await api('/gamedata/packs');
    const specs = state.boot.specs;
    let html = `<div class="card">
        <h2>Packs installes</h2>
        <p class="hint">Dossier du jeu : <code>${escapeHtml(state.boot.game.path)}</code></p>
        <div class="row" style="margin-top:10px">
          <button class="btn" id="lib-open">Ouvrir le dossier</button>
          <button class="btn ghost" id="lib-ensure">Creer les dossiers manquants</button>
          <button class="btn ghost" id="lib-refresh">Rafraichir</button>
        </div>
      </div>`;
    for (const [type, info] of Object.entries(data)) {
      html += `<div class="card">
        <h2>${escapeHtml(specs[type].label)}
          <span class="tag">${info.packs.length}</span></h2>
        <p class="hint"><code>${escapeHtml(info.folder)}</code>${info.exists ? '' : ' — dossier absent'}</p>
        ${info.packs.length ? `<div class="grid three" style="margin-top:10px">${info.packs.map((p) => `
          <div class="slot filled">
            <div class="info">
              <strong data-notr>${escapeHtml(p.name)}</strong>
              <small>${t('%s fichiers', p.file_count)}${p.is_dub ? t(' — pack Dub') : ''}</small>
            </div>
            <div class="actions">
              <button class="btn small ghost" data-open="${escapeAttr(p.path)}">Ouvrir</button>
            </div>
          </div>`).join('')}</div>` : '<p class="hint">Aucun pack.</p>'}
      </div>`;
    }
    host.innerHTML = html;
    host.querySelector('#lib-open').onclick = () =>
      post('/open-folder', { path: state.boot.game.path }).catch(fail);
    host.querySelector('#lib-ensure').onclick = async () => {
      const result = await post('/gamedata/ensure');
      state.boot.game = result.game;
      toast(result.created.length
        ? t('Cree : %s', result.created.join(', ')) : t('Rien a creer.'), 'success');
      renderLibrary();
    };
    host.querySelector('#lib-refresh').onclick = renderLibrary;
    host.querySelectorAll('[data-open]').forEach((button) => {
      button.onclick = () => post('/open-folder', { path: button.dataset.open }).catch(fail);
    });
  } catch (error) { fail(error); }
}

/* --------------------------------------------------------- vue reglages */

/** Comment obtenir une dependance absente, selon la facon dont l'outil tourne. */
function installHint(command) {
  return state.boot.frozen
    ? t('Cette version .exe n\'embarque pas les fonctions IA : prends la version '
        + 'Python de l\'outil pour en profiter.')
    : t('Non installe. Dans le dossier de l\'outil, lance :')
      + ` <code>${escapeHtml(command)}</code>`;
}

function renderSettings() {
  const host = document.getElementById('view-settings');
  const s = state.boot.settings;
  const tools = state.boot.tools;
  const game = state.boot.game;
  const aide = state.boot.helper || {};

  host.innerHTML = `
    <div class="card">
      <h2>Dossier des packs du jeu</h2>
      <p class="hint">Emplacement standard sous Windows :
        <code>%APPDATA%\\YeahMaybe\\ChoicerVoicer\\game</code>.
        Depuis le jeu : menu principal, bouton d'ouverture du dossier.</p>
      <label class="field" style="margin-top:12px"><span>Chemin</span>
        <input type="text" id="set-game" value="${escapeAttr(s.game_dir)}"></label>
      <div class="issue ${game.looks_valid ? 'info' : 'warning'}">
        ${game.looks_valid
          ? t('Dossiers detectes : %s', game.pack_folders.join(', '))
          : 'Aucun dossier packs_* detecte a cet emplacement.'}
      </div>
    </div>

    <div class="card">
      <h2>ffmpeg</h2>
      <p class="hint">Indispensable : toutes les conversions passent par lui.
        Laisse vide pour utiliser celui du PATH. Tu peux indiquer soit l'executable,
        soit le dossier qui le contient.</p>
      <div class="grid two" style="margin-top:12px">
        <label class="field"><span>Chemin de ffmpeg (vide = PATH)</span>
          <input type="text" id="set-ffmpeg" value="${escapeAttr(s.ffmpeg)}"></label>
        <label class="field"><span>Chemin de ffprobe (vide = PATH)</span>
          <input type="text" id="set-ffprobe" value="${escapeAttr(s.ffprobe)}"></label>
      </div>
      ${['ffmpeg', 'ffprobe'].map((name) => `
        <div class="issue ${tools[name].ok ? 'info' : 'error'}">
          <b>${name}</b> — <code>${escapeHtml(tools[name].path)}</code><br>
          ${escapeHtml(tools[name].version || 'introuvable')}
        </div>`).join('')}
    </div>

    <div class="card">
      <h2>Export audio</h2>
      <div class="grid three" style="margin-top:12px">
        <label class="field"><span>Format des clips</span>
          <select id="set-format">
            ${['ogg', 'wav', 'mp3'].map((f) =>
              `<option ${s.clip_format === f ? 'selected' : ''}>${f}</option>`).join('')}
          </select></label>
        <label class="field"><span>Volume cible (LUFS)</span>
          <input type="number" id="set-lufs" value="${s.target_lufs}" step="1"></label>
        <label class="field"><span>&nbsp;</span>
          <span style="display:flex;gap:8px;align-items:center">
            <input type="checkbox" id="set-normalize" ${s.normalize ? 'checked' : ''}>
            Normaliser le volume</span></label>
      </div>
      <p class="hint">La documentation du jeu insiste : un audio fort marche mieux que
        l'inverse, l'algorithme de notation gere mal les faibles amplitudes.</p>
    </div>

    <div class="card">
      <h2>Fonctions IA : Python exterieur</h2>
      <p class="hint">Transcription, piste d'ambiance, locuteurs et detourage reposent sur
        des bibliotheques de plus d'un giga. ${state.boot.frozen
          ? t('La version .exe ne les embarque pas : indique ici un Python qui les a, '
              + 'et l\'outil lui confiera le travail.')
          : t('Elles sont utilisees directement si elles sont installees ici ; sinon '
              + 'l\'outil peut les demander a un autre Python.')}</p>
      <label class="field" style="margin-top:12px"><span>Chemin du Python (vide = detection automatique)</span>
        <input type="text" id="set-python" value="${escapeAttr(s.python_ai || '')}"
               placeholder="C:\Python310\python.exe"></label>
      <div class="issue ${aide.python ? 'info' : 'warning'}">
        ${aide.python
          ? escapeHtml(t('Trouve : %s', aide.python)) + '<br>'
            + ['whisper', 'demucs', 'diarize', 'cutout', 'face']
              .map((k) => `${k} ${aide[k] ? '&#10003;' : '&#10007;'}`).join(' &middot; ')
          : t('Aucun Python capable trouve.')}
      </div>
    </div>

    <div class="card">
      <h2>Transcription (faster-whisper)</h2>
      <p class="hint">${state.boot.whisper.available
        ? 'Installe.' : installHint('pip install faster-whisper')}</p>
      <div class="grid three" style="margin-top:12px">
        <label class="field"><span>Modele</span>
          <select id="set-model">
            ${['tiny', 'base', 'small', 'medium', 'large-v3'].map((m) =>
              `<option ${s.whisper_model === m ? 'selected' : ''}>${m}</option>`).join('')}
          </select></label>
        <label class="field"><span>Materiel</span>
          <select id="set-device">
            ${['auto', 'cpu', 'cuda'].map((d) =>
              `<option ${s.whisper_device === d ? 'selected' : ''}>${d}</option>`).join('')}
          </select></label>
      </div>
      <p class="hint">« small » suffit largement pour des sous-titres courts ;
        « medium » est plus fidele mais nettement plus lent sur CPU.</p>
    </div>

    <div class="card">
      <h2>Piste d'ambiance (demucs)</h2>
      <p class="hint">${state.boot.demucs.available
        ? t('Installe.') + ` demucs ${escapeHtml(state.boot.demucs.version || '')}`
        : installHint('pip install demucs')}</p>
      <p class="hint">Separe les voix de la musique pour fabriquer
        <code>_backing_track</code> automatiquement. Tire PyTorch avec lui : compter
        plusieurs Go.</p>
    </div>

    <div class="card">
      <h2>Personnages (rembg, OpenCV)</h2>
      <p class="hint">${state.boot.portrait.cutout
        ? t('Installe.') + ' rembg'
        : installHint('pip install rembg onnxruntime')}
        &middot; ${state.boot.portrait.face
          ? 'OpenCV ' + t('Installe.')
          : '<code>pip install opencv-python-headless</code>'}</p>
      <p class="hint">rembg detoure un juge ou le candidat, OpenCV va chercher dans une
        video l'image ou le visage est le plus net.</p>
    </div>

    <div class="card">
      <h2>Detection des locuteurs (pyannote)</h2>
      <p class="hint">${state.boot.diarize.available
        ? t('Installe.')
        : installHint('pip install pyannote.audio')}</p>
      <p class="hint">Le modele est sous conditions. Accepte-les sur les deux pages —
        <a href="https://hf.co/pyannote/segmentation-3.0" target="_blank"
           rel="noopener">segmentation-3.0</a> et
        <a href="https://hf.co/pyannote/speaker-diarization-3.1" target="_blank"
           rel="noopener">speaker-diarization-3.1</a> — puis colle ici un jeton de type
        <em>read</em> cree sur
        <a href="https://hf.co/settings/tokens" target="_blank" rel="noopener">hf.co/settings/tokens</a>.</p>
      <label class="field" style="max-width:520px;margin-top:12px"><span>Jeton Hugging Face</span>
        <input type="password" id="set-hf" value="${escapeAttr(s.hf_token || '')}"
               placeholder="hf_..."></label>
    </div>

    <div class="card">
      <h2>Import depuis le web (yt-dlp)</h2>
      <div class="issue ${state.boot.ytdl.available ? 'info' : 'warning'}">
        ${state.boot.ytdl.available
          ? t('Disponible')
            + (state.boot.ytdl.version ? t(' — version %s', escapeHtml(state.boot.ytdl.version)) : '')
            + (state.boot.ytdl.module ? t(' (module Python)') : t(' (executable)'))
          : 'Non installe. Lance : <code>pip install yt-dlp</code>'}
      </div>
      <p class="hint">yt-dlp evolue vite : si un telechargement echoue,
        <code>pip install -U yt-dlp</code> resout la plupart des cas.</p>
    </div>

    <div class="card">
      <h2>Identite</h2>
      <label class="field" style="max-width:420px"><span>Auteur par defaut des nouveaux packs</span>
        <input type="text" id="set-author" value="${escapeAttr(s.author)}"></label>
    </div>

    <div class="row"><button class="btn primary" id="set-save">Enregistrer</button></div>`;

  host.querySelector('#set-save').onclick = async () => {
    try {
      const result = await post('/settings', {
        game_dir: host.querySelector('#set-game').value.trim(),
        ffmpeg: host.querySelector('#set-ffmpeg').value.trim(),
        ffprobe: host.querySelector('#set-ffprobe').value.trim(),
        clip_format: host.querySelector('#set-format').value,
        target_lufs: parseFloat(host.querySelector('#set-lufs').value),
        normalize: host.querySelector('#set-normalize').checked,
        whisper_model: host.querySelector('#set-model').value,
        whisper_device: host.querySelector('#set-device').value,
        hf_token: host.querySelector('#set-hf').value.trim(),
        python_ai: host.querySelector('#set-python').value.trim(),
        author: host.querySelector('#set-author').value.trim(),
      });
      Object.assign(state.boot, result);
      toast('Reglages enregistres.', 'success');
      renderSettings();
    } catch (error) { fail(error); }
  };
}

/* ------------------------------------------------------------- vue aide */

function renderHelp() {
  const host = document.getElementById('view-help');
  host.innerHTML = `
    <div class="card">
      <h2>Comment ca marche</h2>
      <ol class="hint" style="line-height:1.8">
        <li>Cree un projet du type voulu (voix, juges, candidat, animateur, studio, menu, chatter).</li>
        <li>Pour un pack voix : importe une video ou un audio, lance la decoupe automatique,
            ajuste les clips a la souris, puis transcris les sous-titres.</li>
        <li>Genere le pack, puis installe-le : l'outil ecrit directement dans le dossier du jeu.</li>
        <li>Relance The Choicer Voicer — le pack apparait dans le menu de personnalisation.</li>
      </ol>
    </div>

    <div class="card">
      <h2>Regles imposees par le jeu</h2>
      <table>
        <thead><tr><th>Element</th><th>Regle</th></tr></thead>
        <tbody>
          <tr><td>Audio</td><td>WAV, MP3 ou OGG. Moins de 60 s par clip (6 s conseillees en mode Dub).</td></tr>
          <tr><td>Video</td><td>OGV / Theora uniquement — Godot ne lit rien d'autre.</td></tr>
          <tr><td>Images</td><td>PNG ou JPG. PNG conseille pour la transparence.</td></tr>
          <tr><td>Modele 3D</td><td>GLB ou GLTF (packs studio).</td></tr>
          <tr><td>Personnages</td><td>~500 x 1000 px, non redimensionnes, poses sur le sol du plateau.</td></tr>
          <tr><td>Volume</td><td>Fort plutot que faible : la notation gere mal les signaux trop discrets.</td></tr>
          <tr><td>Configs</td><td><code>.ini</code> / <code>.cfg</code> pour les packs voix et chatter,
              <code>.json</code> pour juges, candidat, animateur, studio et menu.</td></tr>
        </tbody>
      </table>
    </div>

    <div class="card">
      <h2>Fichiers ecrits par l'outil</h2>
      <pre class="code">packs_voice/&lt;Nom&gt;/
  01_clip.ogg          extrait audio normalise
  01_clip.txt          sous-titre en clair
  01_clip.ini          metadonnees (utilise a la place du .txt en mode Dub)
  01_clip.png          image du clip (optionnelle)
  _pack_info.ini       titre, sous-titre, auteurs, icone, readme
  _author.txt          doublon lu par toutes les versions du jeu
  _icon.png            icone du pack
  _pack_filler_image.png
  dub_video.ogv        packs Dub uniquement
  _backing_track.ogg   ambiance sans les voix</pre>
    </div>

    <div class="card">
      <h2>Raccourcis de la forme d'onde</h2>
      <ul class="hint" style="line-height:1.8">
        <li><b>Clic</b> — deplacer la tete de lecture</li>
        <li><b>Alt + glisser</b> sur une zone vide — creer un clip</li>
        <li><b>Glisser un bord</b> — ajuster le debut ou la fin</li>
        <li><b>Maj + glisser</b> dans un clip — le deplacer</li>
        <li><b>Double-clic</b> — ecouter le clip</li>
        <li><b>Ctrl + molette</b> — zoomer &middot; <b>molette</b> — defiler</li>
      </ul>
    </div>

    <div class="card">
      <h2>Sources</h2>
      <p class="hint">
        Guide officiel : <a href="https://thechoicervoicer.neocities.org/v2/content_guide" target="_blank"
          rel="noopener">thechoicervoicer.neocities.org</a><br>
        Documentation interne du jeu : menu Extras, ecrans de format.
      </p>
    </div>

    <div class="card">
      <h2>Soutenir le projet</h2>
      <p class="hint">L'outil est gratuit et le restera. S'il t'a evite trois heures
        d'Audacity, tu peux offrir un cafe :</p>
      <p style="margin-top:10px">
        <a class="btn" href="https://buymeacoffee.com/cristof" target="_blank" rel="noopener"
           style="display:inline-block;text-decoration:none;background:#FFDD00;border-color:#FFDD00;color:#111">
          &#9749; Buy me a coffee</a>
      </p>
    </div>`;
}

/* ------------------------------------------------------------ demarrage */

/**
 * Charge la description du serveur. En cas d'echec, propose de reessayer :
 * le serveur est peut-etre simplement en train de redemarrer, et nettoyer la
 * page entiere obligerait a la recharger a la main.
 */
async function loadBoot() {
  try {
    state.boot = await api('/bootstrap');
    return true;
  } catch (error) {
    const host = document.getElementById('view-home');
    host.innerHTML = `
      <div class="card">
        <h2>Le serveur ne repond pas</h2>
        <p class="hint">${escapeHtml(error.message)}</p>
        <p class="hint">Il redemarre peut-etre : laisse-lui un instant, puis reessaie.</p>
        <div class="row" style="margin-top:12px">
          <button class="btn primary" id="boot-retry">Reessayer</button>
        </div>
      </div>`;
    show('home');
    host.querySelector('#boot-retry').onclick = async () => {
      if (await loadBoot()) await renderHome();
    };
    return false;
  }
}

(async function start() {
  setLang(getLang());
  document.title = t('Createur de packs — The Choicer Voicer');
  wireLanguage();
  // Tout ce qui sera ajoute ensuite — vues, modales, notifications — passe
  // par l'observateur : le reste du code n'a pas a s'en soucier.
  watch(document.body);
  translateTree(document.body);

  if (!await loadBoot()) return;
  if (!state.boot.tools.ffmpeg.ok) {
    toast('ffmpeg est introuvable : les conversions echoueront. Voir Reglages.', 'error');
  }
  await renderHome();
})();
