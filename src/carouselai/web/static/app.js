"use strict";

let currentCarousel = null;

const ideaText = document.getElementById("idea-text");
const templateSelect = document.getElementById("template-select");
const carouselTitle = document.getElementById("carousel-title");
const generateBtn = document.getElementById("generate-btn");
const createError = document.getElementById("create-error");

const carouselPanel = document.getElementById("carousel-panel");
const carouselIdLabel = document.getElementById("carousel-id-label");
const slidesGrid = document.getElementById("slides-grid");
const exportZipBtn = document.getElementById("export-zip-btn");
const saveTemplateName = document.getElementById("save-template-name");
const saveTemplateBtn = document.getElementById("save-template-btn");

async function api(path, options) {
  const response = await fetch(path, options);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `${response.status} ${response.statusText}`);
  }
  return response.json();
}

function bust(url) {
  if (!url) return url;
  return `${url}?t=${Date.now()}`;
}

async function loadTemplates(selectedId) {
  const templates = await api("/api/templates");
  templateSelect.innerHTML = "";
  for (const template of templates) {
    const option = document.createElement("option");
    option.value = template.id;
    option.textContent = `${template.name} (${template.id})`;
    templateSelect.appendChild(option);
  }
  if (selectedId) {
    templateSelect.value = selectedId;
  }
}

function slideCard(slide) {
  const card = document.createElement("div");
  card.className = "slide-card";
  card.dataset.index = String(slide.index);

  const img = document.createElement("img");
  img.src = bust(slide.image_url);
  img.alt = `Слайд ${slide.index + 1}`;
  card.appendChild(img);

  const textarea = document.createElement("textarea");
  textarea.value = slide.text;
  card.appendChild(textarea);

  const controls = document.createElement("div");
  controls.className = "slide-controls";

  const sizeLabel = document.createElement("label");
  sizeLabel.textContent = "Размер";
  const sizeInput = document.createElement("input");
  sizeInput.type = "number";
  sizeInput.min = "10";
  sizeInput.max = "200";
  sizeInput.value = String(slide.font_overrides?.size ?? 48);
  sizeLabel.appendChild(sizeInput);
  controls.appendChild(sizeLabel);

  const colorLabel = document.createElement("label");
  colorLabel.textContent = "Цвет";
  const colorInput = document.createElement("input");
  colorInput.type = "color";
  colorInput.value = slide.font_overrides?.color ?? "#111111";
  colorLabel.appendChild(colorInput);
  controls.appendChild(colorLabel);

  const alignLabel = document.createElement("label");
  alignLabel.textContent = "Выравнивание";
  const alignSelect = document.createElement("select");
  for (const [value, label] of [["left", "Слева"], ["center", "По центру"], ["right", "Справа"]]) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = label;
    alignSelect.appendChild(option);
  }
  alignSelect.value = slide.font_overrides?.align ?? "center";
  alignLabel.appendChild(alignSelect);
  controls.appendChild(alignLabel);

  card.appendChild(controls);

  const footer = document.createElement("div");
  footer.className = "slide-footer";

  const bgInput = document.createElement("input");
  bgInput.type = "file";
  bgInput.accept = "image/*";
  footer.appendChild(bgInput);

  const downloadLink = document.createElement("a");
  downloadLink.className = "download-link";
  downloadLink.textContent = "Скачать";
  downloadLink.href = slide.image_url;
  downloadLink.download = `slide_${String(slide.index + 1).padStart(2, "0")}.png`;
  footer.appendChild(downloadLink);

  card.appendChild(footer);

  async function pushEdit() {
    const carousel = await api(
      `/api/carousels/${currentCarousel.id}/slides/${slide.index}`,
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: textarea.value,
          font_size: Number(sizeInput.value) || undefined,
          font_color: colorInput.value,
          align: alignSelect.value,
        }),
      }
    );
    applyCarousel(carousel);
  }

  textarea.addEventListener("change", pushEdit);
  sizeInput.addEventListener("change", pushEdit);
  colorInput.addEventListener("change", pushEdit);
  alignSelect.addEventListener("change", pushEdit);

  bgInput.addEventListener("change", async () => {
    if (!bgInput.files || !bgInput.files[0]) return;
    const formData = new FormData();
    formData.append("file", bgInput.files[0]);
    const carousel = await api(
      `/api/carousels/${currentCarousel.id}/slides/${slide.index}/background`,
      { method: "POST", body: formData }
    );
    applyCarousel(carousel);
  });

  return card;
}

function applyCarousel(carousel) {
  currentCarousel = carousel;
  carouselIdLabel.textContent = `id: ${carousel.id} · шаблон: ${carousel.template_id}`;
  slidesGrid.innerHTML = "";
  for (const slide of carousel.slides) {
    slidesGrid.appendChild(slideCard(slide));
  }
  carouselPanel.hidden = false;
}

generateBtn.addEventListener("click", async () => {
  createError.hidden = true;
  const text = ideaText.value.trim();
  if (!text) {
    createError.textContent = "Сначала введи текст идеи.";
    createError.hidden = false;
    return;
  }
  generateBtn.disabled = true;
  try {
    const carousel = await api("/api/carousels", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text,
        template_id: templateSelect.value,
        title: carouselTitle.value.trim(),
      }),
    });
    applyCarousel(carousel);
  } catch (error) {
    createError.textContent = error.message;
    createError.hidden = false;
  } finally {
    generateBtn.disabled = false;
  }
});

exportZipBtn.addEventListener("click", () => {
  if (!currentCarousel) return;
  window.location.href = `/api/carousels/${currentCarousel.id}/export`;
});

saveTemplateBtn.addEventListener("click", async () => {
  if (!currentCarousel) return;
  const name = saveTemplateName.value.trim();
  if (!name) return;
  const template = await api(`/api/carousels/${currentCarousel.id}/save-as-template`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  saveTemplateName.value = "";
  await loadTemplates(template.id);
});

loadTemplates();
