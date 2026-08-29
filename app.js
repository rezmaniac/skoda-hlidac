const state = {
  offers: [],
  city: "all",
  model: "all",
  maxPrice: "all",
  onlyChanges: false,
  sort: "newest",
};

const elements = {
  grid: document.querySelector("#carGrid"),
  template: document.querySelector("#carCardTemplate"),
  empty: document.querySelector("#emptyState"),
  model: document.querySelector("#modelFilter"),
  price: document.querySelector("#priceFilter"),
  onlyChanges: document.querySelector("#onlyChanges"),
  sort: document.querySelector("#sortFilter"),
};

const formatPrice = value => new Intl.NumberFormat("cs-CZ", {
  style: "currency",
  currency: "CZK",
  maximumFractionDigits: 0,
}).format(value);

const formatNumber = value => new Intl.NumberFormat("cs-CZ").format(value);

const carCountLabel = count => {
  if (count === 1) return "1 vůz odpovídá výběru";
  if (count >= 2 && count <= 4) return `${count} vozy odpovídají výběru`;
  return `${count} vozů odpovídá výběru`;
};

function filteredOffers() {
  return state.offers
    .filter(offer => state.city === "all" || offer.city === state.city)
    .filter(offer => state.model === "all" || offer.model === state.model)
    .filter(offer => state.maxPrice === "all" || offer.price <= Number(state.maxPrice))
    .filter(offer => !state.onlyChanges || offer.isNew || offer.previousPrice > offer.price)
    .sort((a, b) => {
      if (state.sort === "price-asc") return a.price - b.price;
      if (state.sort === "price-desc") return b.price - a.price;
      if (state.sort === "mileage") return a.mileage - b.mileage;
      return new Date(b.firstSeen) - new Date(a.firstSeen);
    });
}

function updateStats(offers) {
  const newCars = offers.filter(offer => offer.isNew).length;
  const discounted = offers.filter(offer => offer.previousPrice > offer.price).length;
  const average = offers.length ? Math.round(offers.reduce((sum, offer) => sum + offer.price, 0) / offers.length) : 0;
  document.querySelector("#totalCount").textContent = offers.length;
  document.querySelector("#newCount").textContent = `+${newCars}`;
  document.querySelector("#discountCount").textContent = discounted;
  document.querySelector("#averagePrice").textContent = offers.length ? formatPrice(average) : "—";
  document.querySelector("#resultHeading").textContent = carCountLabel(offers.length);
}

function makeBadge(text, className) {
  const badge = document.createElement("span");
  badge.className = `badge ${className}`;
  badge.textContent = text;
  return badge;
}

function normalImageUrl(url) {
  return url?.replace(/__thumbnail\.jpg(?:$|\?)/, match => match.replace("__thumbnail", "__normal"));
}

function renderCard(offer) {
  const fragment = elements.template.content.cloneNode(true);
  const card = fragment.querySelector(".car-card");
  card.style.setProperty("--car-color", offer.color || "#3a6155");
  const photo = fragment.querySelector(".car-photo");
  if (offer.imageUrl) {
    photo.src = normalImageUrl(offer.imageUrl);
    photo.alt = `${offer.make} ${offer.model} ${offer.trim}`.trim();
  }
  fragment.querySelector(".location-badge").textContent = offer.city;
  fragment.querySelector(".car-make").textContent = offer.make;
  fragment.querySelector(".car-name").textContent = `${offer.model} ${offer.trim}`;
  fragment.querySelector(".car-engine").textContent = `${offer.engine} · ${offer.powerKw} kW · ${offer.fuel}`;
  fragment.querySelector(".car-year").textContent = offer.year;
  fragment.querySelector(".car-mileage").textContent = `${formatNumber(offer.mileage)} km`;
  fragment.querySelector(".car-transmission").textContent = offer.transmission;
  fragment.querySelector(".current-price").textContent = formatPrice(offer.price);
  fragment.querySelector(".dealer-name").textContent = offer.dealer;
  const previous = fragment.querySelector(".previous-price");
  if (offer.previousPrice > offer.price) previous.textContent = formatPrice(offer.previousPrice);
  const badges = fragment.querySelector(".card-badges");
  if (offer.isNew) badges.append(makeBadge("Novinka", "badge-new"));
  if (offer.previousPrice > offer.price) {
    const saving = Math.round((1 - offer.price / offer.previousPrice) * 100);
    badges.append(makeBadge(`−${saving} %`, "badge-discount"));
  }
  const link = fragment.querySelector(".detail-link");
  link.href = offer.url;
  const saveButton = fragment.querySelector(".save-button");
  const saved = JSON.parse(localStorage.getItem("savedCars") || "[]");
  if (saved.includes(offer.id)) saveButton.classList.add("saved");
  saveButton.addEventListener("click", () => toggleSaved(offer.id, saveButton));
  return fragment;
}

function toggleSaved(id, button) {
  const saved = new Set(JSON.parse(localStorage.getItem("savedCars") || "[]"));
  saved.has(id) ? saved.delete(id) : saved.add(id);
  localStorage.setItem("savedCars", JSON.stringify([...saved]));
  button.classList.toggle("saved", saved.has(id));
}

function render() {
  const offers = filteredOffers();
  elements.grid.replaceChildren(...offers.map(renderCard));
  elements.empty.hidden = offers.length > 0;
  elements.grid.hidden = offers.length === 0;
  updateStats(offers);
  document.querySelectorAll(".location-tab").forEach(button => button.classList.toggle("active", button.dataset.city === state.city));
}

function resetFilters() {
  state.city = "all";
  state.model = "all";
  state.maxPrice = "all";
  state.onlyChanges = false;
  state.sort = "newest";
  elements.model.value = "all";
  elements.price.value = "all";
  elements.onlyChanges.checked = false;
  elements.sort.value = "newest";
  render();
}

function bindControls() {
  document.querySelectorAll(".location-tab").forEach(button => button.addEventListener("click", () => {
    state.city = button.dataset.city;
    render();
  }));
  elements.model.addEventListener("change", event => { state.model = event.target.value; render(); });
  elements.price.addEventListener("change", event => { state.maxPrice = event.target.value; render(); });
  elements.onlyChanges.addEventListener("change", event => { state.onlyChanges = event.target.checked; render(); });
  elements.sort.addEventListener("change", event => { state.sort = event.target.value; render(); });
  document.querySelector("#resetFilters").addEventListener("click", resetFilters);
  document.querySelector("#themeButton").addEventListener("click", () => {
    const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    localStorage.setItem("theme", next);
  });
}

async function initialize() {
  try {
    const response = await fetch("data/latest.json", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    state.offers = data.offers;
    document.querySelector("#lastUpdated").textContent = new Intl.DateTimeFormat("cs-CZ", {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(data.generatedAt));
    document.querySelector("#demoBadge").hidden = !data.demo;
    const models = [...new Set(state.offers.map(offer => offer.model))].sort((a, b) => a.localeCompare(b, "cs"));
    models.forEach(model => elements.model.add(new Option(model, model)));
    document.querySelector("#allTabCount").textContent = state.offers.length;
    document.querySelector("#ivanciceTabCount").textContent = state.offers.filter(offer => offer.city === "Ivančice").length;
    document.querySelector("#brnoTabCount").textContent = state.offers.filter(offer => offer.city === "Brno").length;
    render();
  } catch (error) {
    elements.grid.innerHTML = `<p class="load-error">Data se nepodařilo načíst. Spusťte stránku přes lokální HTTP server.</p>`;
    console.error(error);
  }
}

document.documentElement.dataset.theme = localStorage.getItem("theme") || "light";
bindControls();
initialize();
