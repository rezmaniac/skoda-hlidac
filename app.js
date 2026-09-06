const state = {
  offers: [],
  location: "all",
  dealer: "all",
  make: "all",
  model: "all",
  minPrice: "all",
  maxPrice: "all",
  minMileage: "all",
  maxMileage: "all",
  onlyChanges: false,
  sort: "newest",
  compareIds: new Set(loadStoredArray("comparedCars").slice(0, 3)),
};

const elements = {
  grid: document.querySelector("#carGrid"),
  template: document.querySelector("#carCardTemplate"),
  empty: document.querySelector("#emptyState"),
  dealer: document.querySelector("#dealerFilter"),
  make: document.querySelector("#makeFilter"),
  model: document.querySelector("#modelFilter"),
  minPrice: document.querySelector("#minPriceFilter"),
  maxPrice: document.querySelector("#maxPriceFilter"),
  minMileage: document.querySelector("#minMileageFilter"),
  maxMileage: document.querySelector("#maxMileageFilter"),
  onlyChanges: document.querySelector("#onlyChanges"),
  sort: document.querySelector("#sortFilter"),
  compareBar: document.querySelector("#compareBar"),
  compareHint: document.querySelector("#compareHint"),
  compareChips: document.querySelector("#compareChips"),
  compareCount: document.querySelector("#compareCount"),
  openCompare: document.querySelector("#openCompare"),
  compareDialog: document.querySelector("#compareDialog"),
  compareTable: document.querySelector("#compareTable"),
  equipmentDifferencesOnly: document.querySelector("#equipmentDifferencesOnly"),
};

function loadStoredArray(key) {
  try {
    const value = JSON.parse(localStorage.getItem(key) || "[]");
    return Array.isArray(value) ? value : [];
  } catch {
    return [];
  }
}

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
    .filter(matchesLocation)
    .filter(offer => state.dealer === "all" || offer.dealerId === state.dealer)
    .filter(offer => state.make === "all" || offer.make === state.make)
    .filter(offer => state.model === "all" || offer.model === state.model)
    .filter(offer => state.minPrice === "all" || offer.price >= Number(state.minPrice))
    .filter(offer => state.maxPrice === "all" || offer.price <= Number(state.maxPrice))
    .filter(offer => state.minMileage === "all" || offer.mileage >= Number(state.minMileage))
    .filter(offer => state.maxMileage === "all" || offer.mileage <= Number(state.maxMileage))
    .filter(offer => !state.onlyChanges || offer.isNew || offer.previousPrice > offer.price)
    .sort((a, b) => {
      if (state.sort === "price-asc") return a.price - b.price;
      if (state.sort === "price-desc") return b.price - a.price;
      if (state.sort === "mileage") return a.mileage - b.mileage;
      return new Date(b.firstSeen) - new Date(a.firstSeen);
    });
}

function matchesLocation(offer) {
  if (state.location === "all") return true;
  const [type, value] = state.location.split(":");
  return offer[type] === value;
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

function highResolutionImageUrl(url) {
  return url?.replace(/__(?:thumbnail|normal)\.jpg(?:$|\?)/, match => match.replace(/__(?:thumbnail|normal)/, "__big"));
}

function renderCard(offer) {
  const fragment = elements.template.content.cloneNode(true);
  const card = fragment.querySelector(".car-card");
  card.style.setProperty("--car-color", offer.color || "#3a6155");
  const photo = fragment.querySelector(".car-photo");
  if (offer.imageUrl) {
    photo.src = highResolutionImageUrl(offer.imageUrl);
    photo.alt = `${offer.make} ${offer.model} ${offer.trim}`.trim();
  }
  fragment.querySelector(".location-badge").textContent = offer.city;
  fragment.querySelector(".car-make").textContent = offer.make;
  fragment.querySelector(".car-name").textContent = `${offer.model} ${offer.trim}`;
  fragment.querySelector(".car-engine").textContent = `${offer.engine} · ${offer.powerKw} kW · ${offer.fuel}`;
  fragment.querySelector(".car-year").textContent = offer.year;
  fragment.querySelector(".car-mileage").textContent = `${formatNumber(offer.mileage)} km`;
  fragment.querySelector(".car-transmission").textContent = offer.transmission;
  const compareButton = fragment.querySelector(".compare-button");
  compareButton.dataset.offerId = offer.id;
  compareButton.addEventListener("click", () => toggleCompare(offer.id));
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

function selectedOffers() {
  return [...state.compareIds]
    .map(id => state.offers.find(offer => offer.id === id))
    .filter(Boolean);
}

function toggleCompare(id) {
  if (state.compareIds.has(id)) {
    state.compareIds.delete(id);
  } else if (state.compareIds.size < 3) {
    state.compareIds.add(id);
  }
  localStorage.setItem("comparedCars", JSON.stringify([...state.compareIds]));
  syncCompareUi();
}

function syncCompareUi() {
  const offers = selectedOffers();
  const isFull = offers.length >= 3;
  elements.compareBar.hidden = offers.length === 0;
  elements.compareCount.textContent = offers.length;
  elements.openCompare.disabled = offers.length < 2;
  elements.compareHint.textContent = offers.length < 2
    ? "Vyberte ještě jeden vůz"
    : `${offers.length} ze 3 vozů vybráno`;

  const chips = offers.map(offer => {
    const button = document.createElement("button");
    button.className = "compare-chip";
    button.type = "button";
    button.textContent = `${offer.model} · ${formatPrice(offer.price)} ×`;
    button.setAttribute("aria-label", `Odebrat ${offer.make} ${offer.model} z porovnání`);
    button.addEventListener("click", () => toggleCompare(offer.id));
    return button;
  });
  elements.compareChips.replaceChildren(...chips);

  document.querySelectorAll(".compare-button").forEach(button => {
    const selected = state.compareIds.has(button.dataset.offerId);
    button.classList.toggle("selected", selected);
    button.disabled = isFull && !selected;
    button.setAttribute("aria-pressed", String(selected));
    button.innerHTML = selected
      ? '<span aria-hidden="true">✓</span> Vybráno'
      : '<span aria-hidden="true">＋</span> Přidat do porovnání';
  });
}

function comparisonHeader(offer) {
  const wrapper = document.createElement("div");
  wrapper.className = "compare-car-heading";
  if (offer.imageUrl) {
    const image = document.createElement("img");
    image.src = highResolutionImageUrl(offer.imageUrl);
    image.alt = "";
    wrapper.append(image);
  } else {
    wrapper.classList.add("no-image");
  }
  const title = document.createElement("strong");
  title.textContent = `${offer.make} ${offer.model}`;
  const trim = document.createElement("span");
  trim.textContent = offer.trim || offer.engine;
  const link = document.createElement("a");
  link.href = offer.url;
  link.target = "_blank";
  link.rel = "noopener";
  link.textContent = "Otevřít nabídku ↗";
  wrapper.append(title, trim, link);
  return wrapper;
}

function equipmentKey(name) {
  return name.normalize("NFKC").toLocaleLowerCase("cs-CZ").replace(/\s+/g, " ").trim();
}

function comparisonEquipment(offers) {
  const displayNames = new Map();
  const equipmentSets = offers.map(offer => {
    const names = Array.isArray(offer.equipment) ? offer.equipment : [];
    const set = new Set();
    names.forEach(name => {
      const key = equipmentKey(name);
      if (!key) return;
      set.add(key);
      if (!displayNames.has(key)) displayNames.set(key, name);
    });
    return set;
  });
  return [...displayNames]
    .map(([key, name]) => {
      const presence = equipmentSets.map(set => set.has(key));
      return { key, name, presence, isDifferent: presence.some(Boolean) && !presence.every(Boolean) };
    })
    .sort((a, b) => a.name.localeCompare(b.name, "cs"));
}

function appendEquipmentComparison(tbody, offers) {
  const allEquipment = comparisonEquipment(offers);
  const differentEquipment = allEquipment.filter(item => item.isDifferent);
  const equipment = elements.equipmentDifferencesOnly.checked ? differentEquipment : allEquipment;

  const sectionRow = document.createElement("tr");
  sectionRow.className = "compare-section-row";
  const sectionHeading = document.createElement("th");
  sectionHeading.colSpan = offers.length + 1;
  sectionHeading.textContent = `Výbavové prvky · ${allEquipment.length} položek · ${differentEquipment.length} rozdílů`;
  sectionRow.append(sectionHeading);
  tbody.append(sectionRow);

  if (!equipment.length) {
    const emptyRow = document.createElement("tr");
    const emptyCell = document.createElement("td");
    emptyCell.colSpan = offers.length + 1;
    emptyCell.className = "compare-equipment-empty";
    emptyCell.textContent = allEquipment.length
      ? "Podle údajů prodejců mají vybrané vozy shodnou uvedenou výbavu. Vypněte volbu „Jen rozdíly“, chcete-li ji zobrazit celou."
      : "Prodejci u těchto nabídek neposkytli seznam jednotlivých prvků výbavy.";
    emptyRow.append(emptyCell);
    tbody.append(emptyRow);
    return;
  }

  equipment.forEach(item => {
    const row = document.createElement("tr");
    row.className = item.isDifferent ? "equipment-difference" : "equipment-common";
    const label = document.createElement("th");
    label.scope = "row";
    label.textContent = item.name;
    row.append(label);
    item.presence.forEach(isPresent => {
      const cell = document.createElement("td");
      cell.className = isPresent ? "equipment-present" : "equipment-absent";
      cell.textContent = isPresent ? "✓ Ano" : "—";
      row.append(cell);
    });
    tbody.append(row);
  });
}

function renderComparison() {
  const offers = selectedOffers();
  const lowestPrice = Math.min(...offers.map(offer => offer.price));
  const lowestMileage = Math.min(...offers.map(offer => offer.mileage));
  const newestYear = Math.max(...offers.map(offer => offer.year));
  const highestPower = Math.max(...offers.map(offer => offer.powerKw));
  const rows = [
    { label: "Cena", value: offer => `${formatPrice(offer.price)}${offer.price > lowestPrice ? ` (+${formatPrice(offer.price - lowestPrice)})` : ""}`, best: offer => offer.price === lowestPrice },
    { label: "Rok", value: offer => offer.year || "—", best: offer => offer.year === newestYear },
    { label: "Nájezd", value: offer => `${formatNumber(offer.mileage)} km`, best: offer => offer.mileage === lowestMileage },
    { label: "Motor", value: offer => offer.engine || "—" },
    { label: "Výkon", value: offer => `${formatNumber(offer.powerKw)} kW`, best: offer => offer.powerKw === highestPower },
    { label: "Palivo", value: offer => offer.fuel || "—" },
    { label: "Převodovka", value: offer => offer.transmission || "—" },
    { label: "Výbava", value: offer => offer.trim || "—" },
    { label: "Pobočka", value: offer => `${offer.city} · ${offer.dealer}` },
  ];

  const headRow = document.createElement("tr");
  const corner = document.createElement("th");
  corner.scope = "col";
  corner.textContent = "Parametr";
  headRow.append(corner);
  offers.forEach(offer => {
    const heading = document.createElement("th");
    heading.scope = "col";
    heading.append(comparisonHeader(offer));
    headRow.append(heading);
  });
  const thead = document.createElement("thead");
  thead.append(headRow);

  const tbody = document.createElement("tbody");
  rows.forEach(row => {
    const tableRow = document.createElement("tr");
    const label = document.createElement("th");
    label.scope = "row";
    label.textContent = row.label;
    tableRow.append(label);
    offers.forEach(offer => {
      const value = document.createElement("td");
      value.textContent = row.value(offer);
      if (row.best?.(offer)) value.classList.add("compare-best");
      tableRow.append(value);
    });
    tbody.append(tableRow);
  });
  appendEquipmentComparison(tbody, offers);
  elements.compareTable.replaceChildren(thead, tbody);
}

function openComparison() {
  if (selectedOffers().length < 2) return;
  renderComparison();
  if (typeof elements.compareDialog.showModal === "function") {
    elements.compareDialog.showModal();
  } else {
    elements.compareDialog.setAttribute("open", "");
  }
}

function render() {
  const offers = filteredOffers();
  elements.grid.replaceChildren(...offers.map(renderCard));
  elements.empty.hidden = offers.length > 0;
  elements.grid.hidden = offers.length === 0;
  updateStats(offers);
  document.querySelectorAll(".location-tab").forEach(button => button.classList.toggle("active", button.dataset.location === state.location));
  syncCompareUi();
}

function resetFilters() {
  state.location = "all";
  state.dealer = "all";
  state.make = "all";
  state.model = "all";
  state.minPrice = "all";
  state.maxPrice = "all";
  state.minMileage = "all";
  state.maxMileage = "all";
  state.onlyChanges = false;
  state.sort = "newest";
  elements.make.value = "all";
  elements.dealer.value = "all";
  populateModelOptions();
  elements.model.value = "all";
  elements.minPrice.value = "all";
  elements.maxPrice.value = "all";
  elements.minMileage.value = "all";
  elements.maxMileage.value = "all";
  elements.onlyChanges.checked = false;
  elements.sort.value = "newest";
  render();
}

function populateModelOptions() {
  const currentModel = state.model;
  const models = [...new Set(
    state.offers
      .filter(offer => state.make === "all" || offer.make === state.make)
      .map(offer => offer.model),
  )].sort((a, b) => a.localeCompare(b, "cs"));
  elements.model.replaceChildren(new Option("Všechny modely", "all"));
  models.forEach(model => elements.model.add(new Option(model, model)));
  state.model = models.includes(currentModel) ? currentModel : "all";
  elements.model.value = state.model;
}

function populateDealerOptions() {
  const currentDealer = state.dealer;
  const dealers = [...new Map(state.offers.map(offer => [offer.dealerId, offer])).values()]
    .sort((a, b) => `${a.city} ${a.dealer}`.localeCompare(`${b.city} ${b.dealer}`, "cs"));
  elements.dealer.replaceChildren(new Option("Všechny pobočky", "all"));
  dealers.forEach(offer => elements.dealer.add(new Option(`${offer.city} · ${offer.dealer}`, offer.dealerId)));
  state.dealer = dealers.some(offer => offer.dealerId === currentDealer) ? currentDealer : "all";
  elements.dealer.value = state.dealer;
}

function populateRange(select, start, end, step, formatter) {
  for (let value = start; value <= end; value += step) {
    select.add(new Option(formatter(value), String(value)));
  }
}

function updateRange(kind, changedBound) {
  const minKey = `min${kind}`;
  const maxKey = `max${kind}`;
  const minElement = elements[minKey];
  const maxElement = elements[maxKey];
  state[minKey] = minElement.value;
  state[maxKey] = maxElement.value;
  if (state[minKey] !== "all" && state[maxKey] !== "all" && Number(state[minKey]) > Number(state[maxKey])) {
    if (changedBound === "min") {
      state[maxKey] = state[minKey];
      maxElement.value = state[maxKey];
    } else {
      state[minKey] = state[maxKey];
      minElement.value = state[minKey];
    }
  }
  render();
}

function bindControls() {
  document.querySelectorAll(".location-tab").forEach(button => button.addEventListener("click", () => {
    state.location = button.dataset.location;
    render();
  }));
  elements.dealer.addEventListener("change", event => { state.dealer = event.target.value; render(); });
  elements.make.addEventListener("change", event => {
    state.make = event.target.value;
    populateModelOptions();
    render();
  });
  elements.model.addEventListener("change", event => { state.model = event.target.value; render(); });
  elements.minPrice.addEventListener("change", () => updateRange("Price", "min"));
  elements.maxPrice.addEventListener("change", () => updateRange("Price", "max"));
  elements.minMileage.addEventListener("change", () => updateRange("Mileage", "min"));
  elements.maxMileage.addEventListener("change", () => updateRange("Mileage", "max"));
  elements.onlyChanges.addEventListener("change", event => { state.onlyChanges = event.target.checked; render(); });
  elements.sort.addEventListener("change", event => { state.sort = event.target.value; render(); });
  document.querySelector("#resetFilters").addEventListener("click", resetFilters);
  document.querySelector("#clearCompare").addEventListener("click", () => {
    state.compareIds.clear();
    localStorage.removeItem("comparedCars");
    syncCompareUi();
  });
  elements.openCompare.addEventListener("click", openComparison);
  elements.equipmentDifferencesOnly.addEventListener("change", () => {
    if (elements.compareDialog.open) renderComparison();
  });
  document.querySelector("#closeCompare").addEventListener("click", () => elements.compareDialog.close());
  elements.compareDialog.addEventListener("click", event => {
    if (event.target === elements.compareDialog) elements.compareDialog.close();
  });
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
    state.compareIds = new Set([...state.compareIds].filter(id => state.offers.some(offer => offer.id === id)).slice(0, 3));
    localStorage.setItem("comparedCars", JSON.stringify([...state.compareIds]));
    document.querySelector("#lastUpdated").textContent = new Intl.DateTimeFormat("cs-CZ", {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(data.generatedAt));
    document.querySelector("#demoBadge").hidden = !data.demo;
    const makes = [...new Set(state.offers.map(offer => offer.make))].sort((a, b) => a.localeCompare(b, "cs"));
    makes.forEach(make => elements.make.add(new Option(make, make)));
    populateDealerOptions();
    populateModelOptions();
    const maximumPrice = Math.ceil(Math.max(...state.offers.map(offer => offer.price), 100000) / 50000) * 50000;
    populateRange(elements.minPrice, 100000, maximumPrice, 50000, value => `Od ${formatNumber(value)} Kč`);
    populateRange(elements.maxPrice, 100000, maximumPrice, 50000, value => `Do ${formatNumber(value)} Kč`);
    const maximumMileage = Math.ceil(Math.max(...state.offers.map(offer => offer.mileage), 0) / 25000) * 25000;
    populateRange(elements.minMileage, 0, maximumMileage, 25000, value => `Od ${formatNumber(value)} km`);
    populateRange(elements.maxMileage, 0, maximumMileage, 25000, value => `Do ${formatNumber(value)} km`);
    document.querySelector("#allTabCount").textContent = state.offers.length;
    document.querySelector("#brnoTabCount").textContent = state.offers.filter(offer => offer.area === "Brno").length;
    document.querySelector("#ivanciceTabCount").textContent = state.offers.filter(offer => offer.city === "Ivančice").length;
    document.querySelector("#nearbyTabCount").textContent = state.offers.filter(offer => offer.area === "Okolí Brna").length;
    render();
  } catch (error) {
    elements.grid.innerHTML = `<p class="load-error">Data se nepodařilo načíst. Spusťte stránku přes lokální HTTP server.</p>`;
    console.error(error);
  }
}

document.documentElement.dataset.theme = localStorage.getItem("theme") || "light";
bindControls();
initialize();
