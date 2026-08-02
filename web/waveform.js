/* Forme d'onde sur canvas, sans dependance externe.
   Les pics sont calcules cote serveur (ffmpeg) et envoyes en JSON. */

const COLORS = {
  wave: '#3d6b80',
  waveTop: '#4fc3e8',
  bg: '#10151c',
  grid: '#1e2733',
  region: 'rgba(79, 195, 232, 0.16)',
  regionSelected: 'rgba(142, 224, 106, 0.22)',
  regionBorder: '#4fc3e8',
  regionBorderSelected: '#8ee06a',
  regionDisabled: 'rgba(147, 163, 182, 0.10)',
  playhead: '#f0b429',
  text: '#93a3b6',
};

const EDGE_PX = 6;

export class Waveform {
  constructor(canvas, ruler, handlers = {}) {
    this.canvas = canvas;
    this.ruler = ruler;
    this.ctx = canvas.getContext('2d');
    this.rulerCtx = ruler ? ruler.getContext('2d') : null;
    this.handlers = handlers;

    this.peaks = [];
    this.duration = 0;
    this.regions = [];
    this.selectedId = null;
    this.time = 0;
    this.zoom = 1;          // 1 = tout le fichier tient dans la vue
    this.scroll = 0;        // secondes, bord gauche de la vue
    this.drag = null;
    this.hover = null;

    canvas.addEventListener('mousedown', (e) => this.onDown(e));
    window.addEventListener('mousemove', (e) => this.onMove(e));
    window.addEventListener('mouseup', (e) => this.onUp(e));
    canvas.addEventListener('wheel', (e) => this.onWheel(e), { passive: false });
    canvas.addEventListener('dblclick', (e) => this.onDoubleClick(e));
    canvas.addEventListener('mouseleave', () => { this.hover = null; this.draw(); });

    this.resizeObserver = new ResizeObserver(() => this.resize());
    this.resizeObserver.observe(canvas);
    this.onWindowResize = () => this.resize();
    window.addEventListener('resize', this.onWindowResize);
    this.resize();
    // Le canvas peut encore etre cache au moment de la construction : on
    // remesure une fois la vue affichee.
    requestAnimationFrame(() => this.resize());
    setTimeout(() => this.resize(), 120);
  }

  destroy() {
    this.resizeObserver.disconnect();
    window.removeEventListener('resize', this.onWindowResize);
  }

  /* ------------------------------------------------------------- donnees */

  setPeaks(peaks, duration) {
    this.peaks = peaks || [];
    this.duration = duration || 0;
    this.clampScroll();
    this.draw();
  }

  setRegions(regions) {
    this.regions = (regions || []).map((r) => ({ ...r }));
    this.draw();
  }

  setSelected(id) { this.selectedId = id; this.draw(); }

  setTime(time) {
    this.time = time;
    if (this.following) {
      const view = this.viewDuration();
      if (time < this.scroll || time > this.scroll + view * 0.92) {
        this.scroll = Math.max(0, time - view * 0.15);
        this.clampScroll();
      }
    }
    this.draw();
  }

  /* -------------------------------------------------------------- geometrie */

  resize() {
    const ratio = window.devicePixelRatio || 1;
    for (const [el, ctx] of [[this.canvas, this.ctx], [this.ruler, this.rulerCtx]]) {
      if (!el || !ctx) continue;
      const width = el.clientWidth || 1;
      const height = el.clientHeight || 1;
      el.width = Math.round(width * ratio);
      el.height = Math.round(height * ratio);
      ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    }
    this.draw();
  }

  width() { return this.canvas.clientWidth || 1; }
  viewDuration() { return this.duration / this.zoom; }
  pps() { return this.width() / Math.max(0.001, this.viewDuration()); }
  timeToX(t) { return (t - this.scroll) * this.pps(); }
  xToTime(x) { return this.scroll + x / this.pps(); }

  clampScroll() {
    const max = Math.max(0, this.duration - this.viewDuration());
    this.scroll = Math.min(Math.max(0, this.scroll), max);
  }

  setZoom(zoom, anchorTime = null) {
    const previous = this.zoom;
    this.zoom = Math.min(600, Math.max(1, zoom));
    if (this.zoom !== previous) {
      const anchor = anchorTime === null ? this.scroll + this.viewDuration() / 2 : anchorTime;
      this.scroll = anchor - this.viewDuration() / 2;
      this.clampScroll();
      this.draw();
      if (this.handlers.onZoom) this.handlers.onZoom(this.zoom);
    }
  }

  scrollBy(seconds) { this.scroll += seconds; this.clampScroll(); this.draw(); }

  scrollToTime(t) {
    this.scroll = t - this.viewDuration() / 2;
    this.clampScroll();
    this.draw();
  }

  zoomToRegion(region) {
    const length = Math.max(0.2, region.end - region.start);
    this.zoom = Math.min(600, Math.max(1, this.duration / (length * 3)));
    this.scrollToTime((region.start + region.end) / 2);
  }

  /* ---------------------------------------------------------------- rendu */

  draw() {
    const ctx = this.ctx;
    if (!ctx) return;
    const width = this.width();
    const height = this.canvas.clientHeight;
    ctx.clearRect(0, 0, width, height);
    ctx.fillStyle = COLORS.bg;
    ctx.fillRect(0, 0, width, height);

    if (!this.duration) {
      ctx.fillStyle = COLORS.text;
      ctx.font = '13px "Segoe UI", sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('Aucune source chargee', width / 2, height / 2);
      this.drawRuler();
      return;
    }

    const middle = height / 2;

    // Regions (fond)
    for (const region of this.regions) {
      const x1 = this.timeToX(region.start);
      const x2 = this.timeToX(region.end);
      if (x2 < 0 || x1 > width) continue;
      const selected = region.id === this.selectedId;
      ctx.fillStyle = region.enabled === false
        ? COLORS.regionDisabled
        : (selected ? COLORS.regionSelected : COLORS.region);
      ctx.fillRect(x1, 0, Math.max(1, x2 - x1), height);
    }

    // Onde
    const count = this.peaks.length;
    if (count) {
      ctx.fillStyle = COLORS.wave;
      const startFraction = this.scroll / this.duration;
      const endFraction = (this.scroll + this.viewDuration()) / this.duration;
      for (let px = 0; px < width; px++) {
        const a = (startFraction + (endFraction - startFraction) * (px / width)) * count;
        const b = (startFraction + (endFraction - startFraction) * ((px + 1) / width)) * count;
        let peak = 0;
        for (let i = Math.floor(a); i < Math.max(Math.floor(a) + 1, Math.ceil(b)); i++) {
          if (i >= 0 && i < count && this.peaks[i] > peak) peak = this.peaks[i];
        }
        const h = Math.max(1, peak * (height / 2 - 6));
        ctx.fillRect(px, middle - h, 1, h * 2);
      }
    }

    // Ligne mediane
    ctx.strokeStyle = COLORS.grid;
    ctx.beginPath();
    ctx.moveTo(0, middle);
    ctx.lineTo(width, middle);
    ctx.stroke();

    // Bordures + libelles des regions
    ctx.font = '11px "Segoe UI", sans-serif';
    ctx.textAlign = 'left';
    for (const region of this.regions) {
      const x1 = this.timeToX(region.start);
      const x2 = this.timeToX(region.end);
      if (x2 < -40 || x1 > width + 40) continue;
      const selected = region.id === this.selectedId;
      ctx.strokeStyle = selected ? COLORS.regionBorderSelected : COLORS.regionBorder;
      ctx.lineWidth = selected ? 2 : 1;
      ctx.globalAlpha = region.enabled === false ? 0.35 : 1;
      ctx.beginPath();
      ctx.moveTo(x1, 0); ctx.lineTo(x1, height);
      ctx.moveTo(x2, 0); ctx.lineTo(x2, height);
      ctx.stroke();
      if (x2 - x1 > 34) {
        ctx.fillStyle = selected ? COLORS.regionBorderSelected : COLORS.text;
        ctx.save();
        ctx.beginPath();
        ctx.rect(x1 + 3, 0, x2 - x1 - 6, 16);
        ctx.clip();
        ctx.fillText(region.name || '', x1 + 5, 12);
        ctx.restore();
      }
      ctx.globalAlpha = 1;
    }
    ctx.lineWidth = 1;

    // Creation en cours
    if (this.drag && this.drag.mode === 'create') {
      const x1 = this.timeToX(Math.min(this.drag.from, this.drag.to));
      const x2 = this.timeToX(Math.max(this.drag.from, this.drag.to));
      ctx.fillStyle = 'rgba(240, 180, 41, 0.2)';
      ctx.fillRect(x1, 0, x2 - x1, height);
    }

    // Tete de lecture
    const playX = this.timeToX(this.time);
    if (playX >= 0 && playX <= width) {
      ctx.strokeStyle = COLORS.playhead;
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(playX, 0); ctx.lineTo(playX, height);
      ctx.stroke();
      ctx.lineWidth = 1;
    }

    this.drawRuler();
  }

  drawRuler() {
    const ctx = this.rulerCtx;
    if (!ctx) return;
    const width = this.ruler.clientWidth;
    const height = this.ruler.clientHeight;
    ctx.clearRect(0, 0, width, height);
    if (!this.duration) return;

    const view = this.viewDuration();
    const targets = [0.1, 0.25, 0.5, 1, 2, 5, 10, 15, 30, 60, 120, 300, 600];
    const step = targets.find((t) => (t / view) * width > 70) || 900;

    ctx.strokeStyle = COLORS.grid;
    ctx.fillStyle = COLORS.text;
    ctx.font = '10px var(--mono), monospace';
    ctx.textAlign = 'left';
    const first = Math.floor(this.scroll / step) * step;
    for (let t = first; t < this.scroll + view + step; t += step) {
      const x = this.timeToX(t);
      if (x < -50 || x > width + 50) continue;
      ctx.beginPath();
      ctx.moveTo(x, height - 6);
      ctx.lineTo(x, height);
      ctx.stroke();
      ctx.fillText(formatTime(t), x + 3, height - 8);
    }
  }

  /* -------------------------------------------------------------- souris */

  localX(event) {
    const rect = this.canvas.getBoundingClientRect();
    return event.clientX - rect.left;
  }

  hitTest(x) {
    for (let i = this.regions.length - 1; i >= 0; i--) {
      const region = this.regions[i];
      const x1 = this.timeToX(region.start);
      const x2 = this.timeToX(region.end);
      if (Math.abs(x - x1) <= EDGE_PX) return { region, edge: 'start' };
      if (Math.abs(x - x2) <= EDGE_PX) return { region, edge: 'end' };
      if (x > x1 && x < x2) return { region, edge: null };
    }
    return null;
  }

  onDown(event) {
    if (!this.duration || event.button !== 0) return;
    const x = this.localX(event);
    const hit = this.hitTest(x);
    if (hit) {
      if (this.selectedId !== hit.region.id) {
        this.selectedId = hit.region.id;
        if (this.handlers.onRegionSelect) this.handlers.onRegionSelect(hit.region.id);
      }
      this.drag = {
        mode: hit.edge ? 'resize' : (event.shiftKey ? 'move' : 'maybe-seek'),
        edge: hit.edge,
        id: hit.region.id,
        grabTime: this.xToTime(x),
        start: hit.region.start,
        end: hit.region.end,
        moved: false,
      };
    } else if (event.altKey || event.shiftKey) {
      const t = this.xToTime(x);
      this.drag = { mode: 'create', from: t, to: t };
    } else {
      this.seekTo(this.xToTime(x));
      this.drag = { mode: 'scrub' };
    }
    this.draw();
  }

  onMove(event) {
    if (!this.duration) return;
    const x = this.localX(event);

    if (!this.drag) {
      const hit = this.hitTest(x);
      this.canvas.style.cursor = hit ? (hit.edge ? 'ew-resize' : 'pointer') : 'text';
      return;
    }

    const time = Math.max(0, Math.min(this.duration, this.xToTime(x)));
    if (this.drag.mode === 'scrub') {
      this.seekTo(time);
      return;
    }
    if (this.drag.mode === 'create') {
      this.drag.to = time;
      this.draw();
      return;
    }
    const region = this.regions.find((r) => r.id === this.drag.id);
    if (!region) return;

    if (this.drag.mode === 'maybe-seek') {
      if (Math.abs(time - this.drag.grabTime) * this.pps() < 4) return;
      this.drag.mode = 'move';
    }
    this.drag.moved = true;

    if (this.drag.mode === 'resize') {
      if (this.drag.edge === 'start') region.start = Math.min(time, region.end - 0.05);
      else region.end = Math.max(time, region.start + 0.05);
    } else if (this.drag.mode === 'move') {
      const delta = time - this.drag.grabTime;
      const length = this.drag.end - this.drag.start;
      region.start = Math.max(0, Math.min(this.duration - length, this.drag.start + delta));
      region.end = region.start + length;
    }
    this.draw();
  }

  onUp() {
    if (!this.drag) return;
    const drag = this.drag;
    this.drag = null;

    if (drag.mode === 'create') {
      const start = Math.min(drag.from, drag.to);
      const end = Math.max(drag.from, drag.to);
      if (end - start > 0.08 && this.handlers.onRegionCreate) {
        this.handlers.onRegionCreate(round3(start), round3(end));
      }
    } else if ((drag.mode === 'resize' || drag.mode === 'move') && drag.moved) {
      const region = this.regions.find((r) => r.id === drag.id);
      if (region && this.handlers.onRegionChange) {
        this.handlers.onRegionChange(region.id, round3(region.start), round3(region.end));
      }
    } else if (drag.mode === 'maybe-seek') {
      this.seekTo(drag.grabTime);
    }
    this.draw();
  }

  onDoubleClick(event) {
    const hit = this.hitTest(this.localX(event));
    if (hit && this.handlers.onRegionPlay) this.handlers.onRegionPlay(hit.region.id);
  }

  onWheel(event) {
    if (!this.duration) return;
    event.preventDefault();
    if (event.ctrlKey || event.metaKey) {
      const anchor = this.xToTime(this.localX(event));
      this.setZoom(this.zoom * (event.deltaY < 0 ? 1.25 : 0.8), anchor);
    } else {
      const amount = (event.deltaY || event.deltaX) / 400;
      this.scrollBy(amount * this.viewDuration());
    }
  }

  seekTo(time) {
    this.time = Math.max(0, Math.min(this.duration, time));
    if (this.handlers.onSeek) this.handlers.onSeek(this.time);
    this.draw();
  }
}

export function formatTime(seconds) {
  if (!isFinite(seconds)) return '0:00';
  const sign = seconds < 0 ? '-' : '';
  seconds = Math.abs(seconds);
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${sign}${m}:${s.toFixed(s < 10 ? 2 : 2).padStart(5, '0')}`;
}

export function round3(value) { return Math.round(value * 1000) / 1000; }
