/* M4 Web Proxy — UI */
(() => {
  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => [...document.querySelectorAll(sel)];

  let currPath = "/";
  let statusTimer = null;

  function msg(el, text, kind) {
    const node = typeof el === "string" ? $(el) : el;
    if (!node) return;
    node.textContent = text || "";
    node.className = "msg" + (kind ? " " + kind : "");
  }

  async function api(path, opts = {}) {
    const res = await fetch(path, opts);
    const ctype = res.headers.get("content-type") || "";
    if (ctype.includes("application/json")) {
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || res.statusText);
      return data;
    }
    if (!res.ok) throw new Error(res.statusText);
    return res;
  }

  async function refreshStatus() {
    try {
      const st = await api("/api/status");
      const dot = $("#dot");
      const text = $("#statusText");
      const banner = $("#banner");
      if (st.ok) {
        dot.classList.add("ok");
        text.textContent = "M4 OK — " + st.host;
        banner.classList.remove("show");
        banner.textContent = "";
      } else {
        dot.classList.remove("ok");
        text.textContent = "Sin conexion — " + (st.host || "");
        banner.textContent = st.error || "No se puede contactar con la M4";
        banner.classList.add("show");
      }
    } catch (e) {
      $("#dot").classList.remove("ok");
      $("#statusText").textContent = "Proxy error";
      $("#banner").textContent = String(e.message || e);
      $("#banner").classList.add("show");
    }
  }

  function joinPath(dir, name) {
    let d = dir.replace(/\\/g, "/");
    if (!d.endsWith("/")) d += "/";
    // normalizar //
    if (d === "//") return "//" + name;
    return d + name;
  }

  function parentPath(path) {
    let p = path.replace(/\\/g, "/");
    if (p === "/" || p === "//") return "/";
    if (p.endsWith("/")) p = p.slice(0, -1);
    const i = p.lastIndexOf("/");
    if (i <= 0) return "/";
    return p.slice(0, i + 1);
  }

  async function loadFiles(path) {
    msg("#filesMsg", "Cargando…");
    try {
      const data = await api("/api/files?path=" + encodeURIComponent(path || "/"));
      currPath = data.path || path;
      $("#currPath").textContent = currPath;
      const body = $("#fileBody");
      body.innerHTML = "";
      for (const e of data.entries || []) {
        const tr = document.createElement("tr");
        const full = joinPath(currPath, e.name);
        const nameTd = document.createElement("td");
        nameTd.textContent = e.is_dir ? "[" + e.name + "]" : e.name;
        nameTd.className = e.is_dir ? "name-dir" : "name-file";
        if (e.is_dir) {
          nameTd.onclick = () => loadFiles(full.endsWith("/") ? full : full + "/");
        } else {
          nameTd.onclick = () => {
            window.location.href =
              "/api/files/download?path=" + encodeURIComponent(full);
          };
        }
        const sizeTd = document.createElement("td");
        sizeTd.textContent = e.size || "";
        const runTd = document.createElement("td");
        if (!e.is_dir) {
          const b = document.createElement("button");
          b.className = "btn small";
          b.textContent = "Run";
          b.onclick = async () => {
            if (!confirm("Run en CPC:\n" + full + "?")) return;
            try {
              await api("/api/files/run", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ path: full }),
              });
              msg("#filesMsg", "Run enviado: " + full, "ok");
            } catch (err) {
              msg("#filesMsg", String(err.message || err), "error");
            }
          };
          runTd.appendChild(b);
        }
        const delTd = document.createElement("td");
        const db = document.createElement("button");
        db.className = "btn small danger";
        db.textContent = "Delete";
        db.onclick = async () => {
          if (!confirm("Borrar " + full + " ?")) return;
          try {
            await api("/api/files/delete", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ path: full }),
            });
            msg("#filesMsg", "Borrado: " + full, "ok");
            loadFiles(currPath);
          } catch (err) {
            msg("#filesMsg", String(err.message || err), "error");
          }
        };
        delTd.appendChild(db);
        tr.append(nameTd, sizeTd, runTd, delTd);
        body.appendChild(tr);
      }
      msg("#filesMsg", (data.entries || []).length + " entradas", "ok");
    } catch (err) {
      msg("#filesMsg", String(err.message || err), "error");
    }
  }

  async function uploadFiles(fileList) {
    const files = [...fileList];
    if (!files.length) return;
    const bar = $("#upProgress");
    const fill = bar.querySelector("span");
    bar.style.display = "block";
    fill.style.width = "0%";
    let done = 0;
    for (const file of files) {
      const fd = new FormData();
      fd.append("path", currPath);
      fd.append("file", file, file.name);
      try {
        await api("/api/files/upload", { method: "POST", body: fd });
        done += 1;
        fill.style.width = Math.round((done / files.length) * 100) + "%";
      } catch (err) {
        msg("#filesMsg", "Error subiendo " + file.name + ": " + err.message, "error");
        break;
      }
    }
    msg("#filesMsg", "Subidos " + done + "/" + files.length, done ? "ok" : "error");
    setTimeout(() => {
      bar.style.display = "none";
    }, 800);
    loadFiles(currPath);
  }

  // Tabs
  $$(".tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      $$(".tab").forEach((b) => b.classList.remove("active"));
      $$(".panel").forEach((p) => p.classList.remove("active"));
      btn.classList.add("active");
      const id = "panel-" + btn.dataset.tab;
      $("#" + id).classList.add("active");
      if (btn.dataset.tab === "files") loadFiles(currPath);
      if (btn.dataset.tab === "roms") loadRoms();
      if (btn.dataset.tab === "settings") loadSettings();
    });
  });

  $("#btnRefresh").onclick = () => loadFiles(currPath);
  $("#btnBack").onclick = () => loadFiles(parentPath(currPath));
  $("#btnUpload").onclick = () => {
    const input = $("#fileInput");
    if (!input.files.length) {
      msg("#filesMsg", "Elige ficheros primero", "error");
      return;
    }
    uploadFiles(input.files);
  };
  $("#btnMkdir").onclick = async () => {
    const name = $("#mkdirName").value.trim();
    if (!name) return;
    const path = joinPath(currPath, name);
    try {
      await api("/api/files/mkdir", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path }),
      });
      $("#mkdirName").value = "";
      loadFiles(currPath);
    } catch (err) {
      msg("#filesMsg", String(err.message || err), "error");
    }
  };
  $("#btnCdCpc").onclick = async () => {
    try {
      await api("/api/files/cd", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: currPath }),
      });
      msg("#filesMsg", "CD on CPC → " + currPath, "ok");
    } catch (err) {
      msg("#filesMsg", String(err.message || err), "error");
    }
  };

  const dropZone = $("#panel-files");
  dropZone.addEventListener("dragover", (e) => {
    e.preventDefault();
  });
  dropZone.addEventListener("drop", (e) => {
    e.preventDefault();
    if (e.dataTransfer.files.length) uploadFiles(e.dataTransfer.files);
  });

  // Control
  $$("[data-ctrl]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const action = btn.dataset.ctrl;
      if (
        (action === "m4_reset" || action === "cpc_reset") &&
        !confirm("Confirmas " + action + "?")
      ) {
        return;
      }
      try {
        await api("/api/control", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action }),
        });
        msg("#controlMsg", action + " OK", "ok");
      } catch (err) {
        msg("#controlMsg", String(err.message || err), "error");
      }
    });
  });
  $("#btnCtrlRun").onclick = async () => {
    const value = $("#ctrlRunPath").value.trim();
    if (!value) return;
    try {
      await api("/api/control", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "run", value }),
      });
      msg("#controlMsg", "Run " + value, "ok");
    } catch (err) {
      msg("#controlMsg", String(err.message || err), "error");
    }
  };
  $("#btnCtrlCd").onclick = async () => {
    const value = $("#ctrlCdPath").value.trim();
    if (!value) return;
    try {
      await api("/api/control", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "cd", value }),
      });
      msg("#controlMsg", "CD " + value, "ok");
    } catch (err) {
      msg("#controlMsg", String(err.message || err), "error");
    }
  };

  // Settings
  async function loadSettings() {
    msg("#settingsMsg", "Cargando…");
    try {
      const s = await api("/api/settings");
      $("#setTime").textContent = s.time || "";
      $("#setVer").textContent = s.version || "";
      $("#setMac").textContent = s.mac || "";
      $("#setZone").value = s.timezone || "";
      $("#setNtp").value = s.ntp || "";
      $("#setName").value = s.netbios || "";
      $("#setSsid").value = s.ssid || "";
      $("#setPw").value = s.password || "";
      $("#setDhcp").checked = !!s.dhcp;
      $("#setIp").value = s.ip || "";
      $("#setNm").value = s.subnet || "";
      $("#setGw").value = s.gateway || "";
      $("#setDns1").value = s.dns1 || "";
      $("#setDns2").value = s.dns2 || "";
      msg("#settingsMsg", "OK", "ok");
    } catch (err) {
      msg("#settingsMsg", String(err.message || err), "error");
    }
  }

  $("#btnSettingsReload").onclick = loadSettings;
  $("#btnTogglePw").onclick = () => {
    const inp = $("#setPw");
    const show = inp.type === "password";
    inp.type = show ? "text" : "password";
    $("#btnTogglePw").textContent = show ? "Hide" : "Show";
  };

  $$("[data-set]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const kind = btn.dataset.set;
      const patch = {};
      if (kind === "timezone") patch.timezone = $("#setZone").value;
      if (kind === "ntp") patch.ntp = $("#setNtp").value;
      if (kind === "netbios") patch.netbios = $("#setName").value;
      if (kind === "wifi") {
        if (!confirm("¿Guardar SSID/password en la M4?")) return;
        patch.ssid = $("#setSsid").value;
        patch.password = $("#setPw").value;
      }
      if (kind === "dhcp") patch.dhcp = $("#setDhcp").checked;
      if (kind === "network") {
        if (!confirm("¿Guardar IP/subnet/gateway?")) return;
        patch.ip = $("#setIp").value;
        patch.subnet = $("#setNm").value;
        patch.gateway = $("#setGw").value;
      }
      if (kind === "dns") {
        patch.dns1 = $("#setDns1").value;
        patch.dns2 = $("#setDns2").value;
      }
      try {
        await api("/api/settings", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(patch),
        });
        msg("#settingsMsg", "Guardado (" + kind + ")", "ok");
        loadSettings();
      } catch (err) {
        msg("#settingsMsg", String(err.message || err), "error");
      }
    });
  });

  // Roms
  async function loadRoms() {
    msg("#romsMsg", "Cargando…");
    try {
      const r = await api("/api/roms");
      $("#m4en").checked = !!r.m4_enabled;
      $("#m4rm").value = r.m4_rom || "";
      $("#m4rb").value = r.romboard_start || "";
      $("#lwen").checked = !!r.lower_enabled;
      $("#lwsl").value = r.lower_slot || "";
      $("#rs16").checked = !!r.only_16;
      const body = $("#romBody");
      body.innerHTML = "";
      for (const s of r.slots || []) {
        const tr = document.createElement("tr");
        tr.innerHTML =
          "<td>" +
          s.slot +
          "</td><td>" +
          (s.name || "") +
          '</td><td><button class="btn small danger" data-rm="' +
          s.slot +
          '">Remove</button></td>';
        body.appendChild(tr);
      }
      body.querySelectorAll("[data-rm]").forEach((b) => {
        b.onclick = async () => {
          const slot = b.getAttribute("data-rm");
          if (!confirm("Quitar ROM slot " + slot + "?")) return;
          try {
            await api("/api/roms/remove", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ slot: Number(slot) }),
            });
            loadRoms();
          } catch (err) {
            msg("#romsMsg", String(err.message || err), "error");
          }
        };
      });
      msg("#romsMsg", "OK", "ok");
    } catch (err) {
      msg("#romsMsg", String(err.message || err), "error");
    }
  }

  $("#btnRomsRefresh").onclick = loadRoms;
  $$("[data-rom-set]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const key = btn.dataset.romSet;
      const patch = {};
      if (key === "m4_enabled") patch.m4_enabled = $("#m4en").checked;
      if (key === "m4_rom") patch.m4_rom = $("#m4rm").value;
      if (key === "romboard_start") patch.romboard_start = $("#m4rb").value;
      if (key === "lower_enabled") patch.lower_enabled = $("#lwen").checked;
      if (key === "lower_slot") patch.lower_slot = $("#lwsl").value;
      if (key === "only_16") patch.only_16 = $("#rs16").checked;
      try {
        await api("/api/roms/config", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(patch),
        });
        msg("#romsMsg", "Config OK", "ok");
        loadRoms();
      } catch (err) {
        msg("#romsMsg", String(err.message || err), "error");
      }
    });
  });

  $("#btnRomUpload").onclick = async () => {
    const f = $("#romFile").files[0];
    if (!f) {
      msg("#romsMsg", "Elige un ROM", "error");
      return;
    }
    const fd = new FormData();
    fd.append("slot", $("#romSlot").value);
    fd.append("slotname", $("#romSlotName").value || f.name);
    fd.append("file", f, f.name);
    try {
      await api("/api/roms/upload", { method: "POST", body: fd });
      msg("#romsMsg", "ROM subida", "ok");
      loadRoms();
    } catch (err) {
      msg("#romsMsg", String(err.message || err), "error");
    }
  };

  $("#btnCartUpload").onclick = async () => {
    const f = $("#cartFile").files[0];
    if (!f) return;
    if (!confirm("Subir cartucho " + f.name + "?")) return;
    const fd = new FormData();
    fd.append("file", f, f.name);
    try {
      await api("/api/roms/upload_cart", { method: "POST", body: fd });
      msg("#romsMsg", "Cartucho subido", "ok");
    } catch (err) {
      msg("#romsMsg", String(err.message || err), "error");
    }
  };

  refreshStatus();
  statusTimer = setInterval(refreshStatus, 8000);
  loadFiles("/");
})();
