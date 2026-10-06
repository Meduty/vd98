// UI controller. Talks to Python via window.pywebview.api; polls state every 500 ms.
// Titles and errors come from remote sites: only ever render them via textContent.
(() => {
  const $ = (id) => document.getElementById(id);
  const STATUS_LABEL = {
    queued: "Queued",
    downloading: "Downloading",
    processing: "Converting",
    done: "Done",
    error: "Error",
    cancelled: "Cancelled",
  };
  const TERMINAL = new Set(["done", "error", "cancelled"]);

  let api = null;
  let settings = { sound: true };
  let selectedId = null;
  let lastStatus = new Map();
  let maximized = false;

  // ---------- helpers ----------
  function fmtSpeed(bps) {
    if (!bps) return "";
    const units = ["B/s", "KB/s", "MB/s", "GB/s"];
    let i = 0;
    while (bps >= 1024 && i < units.length - 1) { bps /= 1024; i++; }
    return `${bps.toFixed(i ? 1 : 0)} ${units[i]}`;
  }

  function fmtEta(sec) {
    if (sec == null) return "";
    const m = Math.floor(sec / 60), s = Math.floor(sec % 60);
    return `${m}:${String(s).padStart(2, "0")}`;
  }

  function sound(name) {
    if (settings.sound) Sounds[name]();
  }

  function setStatus(text) {
    $("status").textContent = text;
  }

  function showDialog(title, text, kind = "info") {
    $("dialog-title").textContent = title;
    $("dialog-text").textContent = text;
    $("dialog-icon").className = `dialog-icon ${kind}`;
    $("dialog").hidden = false;
    $("dialog-ok").focus();
  }

  function hideDialog() {
    $("dialog").hidden = true;
    $("url").focus();
  }

  // ---------- queue rendering ----------
  function cell(text, cls) {
    const td = document.createElement("td");
    if (cls) td.className = cls;
    td.textContent = text;
    td.title = text;
    return td;
  }

  function progressCell(job) {
    const td = document.createElement("td");
    const outer = document.createElement("div");
    outer.className = "progress-indicator segmented";
    const bar = document.createElement("span");
    bar.className = "progress-indicator-bar";
    bar.style.width = `${Math.max(0, Math.min(100, job.percent || 0))}%`;
    outer.appendChild(bar);
    td.appendChild(outer);
    return td;
  }

  function render(jobs) {
    const body = $("queue-body");
    const rows = jobs.map((job) => {
      const tr = document.createElement("tr");
      tr.dataset.id = job.id;
      tr.className = job.status;
      if (job.id === selectedId) tr.classList.add("highlighted");
      const status = job.status === "error" ? `Error` : STATUS_LABEL[job.status] || job.status;
      tr.append(
        cell(job.title || job.url),
        cell(status, "status-cell"),
        progressCell(job),
        cell(job.status === "downloading" ? fmtSpeed(job.speed) : ""),
        cell(job.status === "downloading" ? fmtEta(job.eta) : ""),
      );
      if (job.status === "error") tr.title = job.error;
      return tr;
    });
    body.replaceChildren(...rows);
    $("empty").hidden = jobs.length > 0;

    if (selectedId != null && !jobs.some((j) => j.id === selectedId)) selectedId = null;
    const sel = jobs.find((j) => j.id === selectedId);
    $("cancel").disabled = !sel || TERMINAL.has(sel.status);
    $("remove").disabled = !sel || !TERMINAL.has(sel.status);

    const pending = jobs.filter((j) => !TERMINAL.has(j.status)).length;
    const done = jobs.filter((j) => j.status === "done").length;
    $("counts").textContent = `${pending} queued, ${done} done`;
  }

  function announce(jobs) {
    for (const job of jobs) {
      const prev = lastStatus.get(job.id);
      if (prev === job.status) continue;
      const name = job.title || job.url;
      if (job.status === "downloading" && prev !== "downloading") setStatus(`Downloading ${name}...`);
      if (job.status === "processing") setStatus(`Converting ${name}...`);
      if (prev !== undefined && job.status === "done") {
        sound("done");
        setStatus(`Finished: ${name}`);
      }
      if (prev !== undefined && job.status === "error") {
        sound("error");
        setStatus("Download failed.");
        showDialog("Download Error", `Could not download:\n${job.url}\n\n${job.error}`, "error");
      }
      if (prev !== undefined && job.status === "cancelled") setStatus(`Cancelled: ${name}`);
    }
    lastStatus = new Map(jobs.map((j) => [j.id, j.status]));
  }

  async function refresh() {
    try {
      const state = await api.get_state();
      settings = state.settings;
      announce(state.jobs);
      render(state.jobs);
    } catch (e) {
      console.error(e);
    }
  }

  // ---------- actions ----------
  async function addUrl() {
    const input = $("url");
    const url = input.value.trim();
    if (!url) {
      sound("error");
      showDialog("Video Downloader 98", "Please enter the address of a video first.", "warn");
      return;
    }
    const res = await api.add(url, $("preset").value);
    if (res && res.error) {
      sound("error");
      showDialog("Invalid Address", res.error, "warn");
      return;
    }
    sound("start");
    input.value = "";
    selectedId = res.id;
    setStatus("Added to queue.");
    refresh();
  }

  async function browse() {
    const res = await api.choose_folder();
    if (res && res.download_dir) {
      settings = res;
      $("folder").value = res.download_dir;
      setStatus(`Saving to ${res.download_dir}`);
    }
  }

  async function pasteUrl() {
    try {
      const text = await navigator.clipboard.readText();
      if (text) $("url").value = text.trim();
    } catch {
      setStatus("Clipboard not available - use Ctrl+V in the URL box.");
    }
    $("url").focus();
  }

  async function about() {
    const info = await api.about();
    showDialog(
      "About Video Downloader 98",
      `Video Downloader 98\nVersion ${info.app}\n\nDownload engine: yt-dlp ${info.yt_dlp}\nStyle: 98.css\n\nOnly download videos you have the right to save.`,
      "info",
    );
  }

  const ACTIONS = {
    "open-folder": () => api.open_folder(),
    browse,
    exit: () => api.close(),
    paste: pasteUrl,
    clear: () => api.clear_finished().then(refresh),
    about,
  };

  // ---------- menus ----------
  function closeMenus() {
    document.querySelectorAll(".menu-list.open").forEach((m) => m.classList.remove("open"));
    document.querySelectorAll(".menu-title.open").forEach((m) => m.classList.remove("open"));
  }

  function wireMenus() {
    let menuActive = false;
    document.querySelectorAll(".menu-title").forEach((btn) => {
      const list = $(`menu-${btn.dataset.menu}`);
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const wasOpen = list.classList.contains("open");
        closeMenus();
        menuActive = !wasOpen;
        if (!wasOpen) { list.classList.add("open"); btn.classList.add("open"); }
      });
      btn.addEventListener("mouseenter", () => {
        if (!menuActive) return;
        closeMenus();
        list.classList.add("open");
        btn.classList.add("open");
      });
    });
    document.querySelectorAll(".menu-list li[data-action]").forEach((li) => {
      li.addEventListener("click", (e) => {
        e.stopPropagation();
        closeMenus();
        menuActive = false;
        ACTIONS[li.dataset.action]();
      });
    });
    document.addEventListener("click", () => { closeMenus(); menuActive = false; });
  }

  // ---------- wiring ----------
  function wire() {
    wireMenus();

    // Title bar buttons sit inside the drag region; keep mousedown from starting a drag.
    document.querySelectorAll(".title-bar-controls button").forEach((b) =>
      b.addEventListener("mousedown", (e) => e.stopPropagation()),
    );
    $("btn-min").onclick = () => api.minimize();
    $("btn-max").onclick = () => {
      maximized = !maximized;
      $("btn-max").setAttribute("aria-label", maximized ? "Restore" : "Maximize");
      api.maximize(maximized);
    };
    $("btn-close").onclick = () => api.close();

    $("add").onclick = addUrl;
    $("url").addEventListener("keydown", (e) => { if (e.key === "Enter") addUrl(); });
    $("browse").onclick = browse;
    $("open").onclick = () => api.open_folder();
    $("clear").onclick = ACTIONS.clear;
    $("preset").onchange = () => api.save_settings({ preset: $("preset").value });
    $("sound").onchange = async () => {
      settings = await api.save_settings({ sound: $("sound").checked });
      if (settings.sound) Sounds.click();
    };
    $("cancel").onclick = async () => {
      if (selectedId == null) return;
      await api.cancel(selectedId);
      refresh();
    };
    $("remove").onclick = async () => {
      if (selectedId == null) return;
      await api.remove(selectedId);
      selectedId = null;
      refresh();
    };
    $("queue-body").addEventListener("click", (e) => {
      const tr = e.target.closest("tr");
      if (!tr) return;
      selectedId = Number(tr.dataset.id);
      refresh();
    });
    $("queue-body").addEventListener("dblclick", (e) => {
      const tr = e.target.closest("tr");
      if (tr && tr.classList.contains("done")) api.open_folder();
    });

    document.querySelectorAll("#dialog [data-close]").forEach((b) => (b.onclick = hideDialog));
    document.addEventListener("keydown", (e) => {
      if (!$("dialog").hidden && (e.key === "Escape" || e.key === "Enter")) {
        e.preventDefault();
        hideDialog();
      } else if (e.key === "Escape") {
        closeMenus();
      } else if (e.ctrlKey && e.shiftKey && e.key.toLowerCase() === "v") {
        e.preventDefault();
        pasteUrl();
      } else if (e.key === "Delete" && document.activeElement !== $("url") && !$("remove").disabled) {
        $("remove").click();
      }
    });
  }

  async function start() {
    api = window.pywebview.api;
    const init = await api.init();
    settings = init.settings;
    const select = $("preset");
    for (const p of init.presets) select.add(new Option(p.label, p.key));
    select.value = settings.preset;
    $("folder").value = settings.download_dir;
    $("sound").checked = settings.sound;
    const about = await api.about();
    $("engine").textContent = `yt-dlp ${about.yt_dlp}`;
    lastStatus = new Map(init.jobs.map((j) => [j.id, j.status]));
    render(init.jobs);
    wire();
    $("url").focus();
    if (!init.ffmpeg) {
      showDialog(
        "FFmpeg Not Found",
        "ffmpeg was not found on your PATH. Merging high-quality video and audio conversion will not work. Install it with your package manager (e.g. sudo dnf install ffmpeg).",
        "warn",
      );
    }
    setInterval(refresh, 500);
  }

  if (window.pywebview && window.pywebview.api) start();
  else window.addEventListener("pywebviewready", start);
})();
