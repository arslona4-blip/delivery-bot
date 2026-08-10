(() => {
  const tg = window.Telegram?.WebApp;
  if (tg) {
    tg.ready();
    tg.expand();
  }

  const params = new URLSearchParams(window.location.search);
  const mode = (params.get("mode") || "sale").toLowerCase();
  const isSale = mode === "sale";

  const titleEl = document.getElementById("title");
  const hintEl = document.getElementById("hint");
  const statusEl = document.getElementById("status");
  const torchBtn = document.getElementById("torchBtn");
  const listEl = document.getElementById("list");
  let scanner = null;
  let torchOn = false;
  let sent = false;
  const cart = [];
  let lastCode = "";
  let lastAt = 0;

  if (titleEl) {
    titleEl.textContent = isSale ? "📷 Sotish skaner" : "📷 Mahsulot kodi";
  }
  if (hintEl) {
    hintEl.textContent = isSale
      ? "Kodlarni ketma-ket skanerlang, oxirida savatga yuboring"
      : "Shtrix-kodni ramkaga tuting — avtomatik yuboriladi";
  }

  function setStatus(text) {
    statusEl.textContent = text;
  }

  function renderList() {
    if (!listEl) return;
    if (!cart.length) {
      listEl.innerHTML = "";
      return;
    }
    const counts = {};
    cart.forEach((c) => {
      counts[c] = (counts[c] || 0) + 1;
    });
    listEl.innerHTML = Object.entries(counts)
      .map(([code, n]) => `<div class="item">${code} ×${n}</div>`)
      .join("");
  }

  function updateMainButton() {
    if (!tg?.MainButton || !isSale) return;
    if (!cart.length) {
      tg.MainButton.hide();
      return;
    }
    tg.MainButton.setText(`Savatga yuborish (${cart.length})`);
    tg.MainButton.show();
  }

  function sendAdd(code) {
    if (sent || !tg) return;
    sent = true;
    if (tg.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
    setStatus(`Yuborilmoqda: ${code}`);
    tg.sendData(JSON.stringify({ action: "scan", barcode: code, mode: "add" }));
  }

  function addSaleCode(code) {
    const now = Date.now();
    if (code === lastCode && now - lastAt < 1500) return;
    lastCode = code;
    lastAt = now;
    cart.push(code);
    if (tg?.HapticFeedback) tg.HapticFeedback.impactOccurred("light");
    setStatus(`Qo‘shildi: ${code}  |  Jami: ${cart.length}`);
    renderList();
    updateMainButton();
  }

  if (isSale && tg?.MainButton) {
    tg.MainButton.onClick(() => {
      if (!cart.length) return;
      tg.sendData(
        JSON.stringify({
          action: "scan_many",
          barcodes: cart.slice(),
          mode: "sale",
        })
      );
    });
  }

  async function start() {
    scanner = new Html5Qrcode("reader");
    const cameras = await Html5Qrcode.getCameras();
    if (!cameras.length) {
      setStatus("Kamera topilmadi");
      return;
    }
    const back =
      cameras.find((c) => /back|rear|environment/i.test(c.label)) ||
      cameras[cameras.length - 1];
    await scanner.start(
      back.id,
      { fps: 10, qrbox: { width: 260, height: 140 }, aspectRatio: 1.3 },
      (decoded) => {
        const code = String(decoded || "").trim();
        if (!code) return;
        if (isSale) addSaleCode(code);
        else sendAdd(code);
      },
      () => {}
    );
    setStatus(
      isSale
        ? "Sotish: kodlarni ketma-ket skanerlang, keyin «Savatga yuborish»"
        : "Kodni ramkaga tuting…"
    );
    torchBtn.hidden = false;
  }

  torchBtn.addEventListener("click", async () => {
    if (!scanner) return;
    try {
      torchOn = !torchOn;
      await scanner.applyVideoConstraints({
        advanced: [{ torch: torchOn }],
      });
      torchBtn.textContent = torchOn ? "💡 Chiroq o‘chiq" : "💡 Chiroq";
    } catch {
      setStatus("Bu telefonda chiroq qo‘llab-quvvatlanmaydi");
    }
  });

  start().catch((err) => {
    console.error(err);
    setStatus("Kameraga ruxsat bering va qayta oching");
  });
})();
