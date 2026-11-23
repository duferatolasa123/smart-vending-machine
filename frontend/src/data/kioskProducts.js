const products = [
  { key: "water", name: "Water 1 L", price: 60, asset: "water-1l", color: "water" },
  { key: "mirinda", name: "Mirinda", price: 80, asset: "mirinda", color: "mirinda" },
  { key: "cocacola", name: "Coca-Cola", price: 80, asset: "cocacola", color: "cola" },
  { key: "chips", name: "Chips", price: 40, asset: "sunchips", color: "chips" },
  { key: "chocolate", name: "Chocolate", price: 60, asset: "chocolate", color: "chocolate" },
  { key: "cappuccino", name: "Cappuccino", price: 20, asset: "cappuchino", color: "cappuccino" },
];

const productAssetUrls = import.meta.glob("../assets/products/*.{png,jpg,jpeg,webp}", {
  eager: true,
  import: "default",
  query: "?url",
});

function normalizeName(value) {
  return value.toLowerCase().normalize("NFKD").replace(/[\u0300-\u036f]/g, "").replace(/[^a-z0-9]/g, "");
}

function productProfile(productName) {
  const name = normalizeName(productName);
  return products.find(product => {
    if (product.key === "cocacola") return name.includes("cocacola") || name === "coke" || name.includes("cola");
    if (product.key === "cappuccino") return name.includes("cappuccino") || name.includes("cappucino") || name.includes("cappuchino");
    return name.includes(product.key);
  }) || null;
}

export function toKioskProduct(product) {
  const profile = productProfile(product.name);
  if (!profile) return null;
  return {
    ...product,
    // Product name and price come from the catalog API (database). This profile
    // supplies only kiosk presentation and the bundled photo.
    name: product.name,
    price: product.price,
    kioskImage: productAssetUrls[`../assets/products/${profile.asset}.png`]
      || productAssetUrls[`../assets/products/${profile.asset}.jpg`]
      || productAssetUrls[`../assets/products/${profile.asset}.jpeg`]
      || productAssetUrls[`../assets/products/${profile.asset}.webp`]
      || "",
    kioskColor: profile.color,
    kioskOrder: products.indexOf(profile),
  };
}

export function sortKioskProducts(items) {
  return [...items].sort((left, right) => left.kioskOrder - right.kioskOrder);
}
