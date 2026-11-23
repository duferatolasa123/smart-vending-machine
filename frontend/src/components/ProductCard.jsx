import { useState } from "react";
import { Check, Package, Plus } from "lucide-react";
import { API_BASE_URL } from "../services/api";

function imageUrls(product) {
  if (!product.image_path) return product.kioskImage ? [product.kioskImage] : [];
  const databaseImage = /^https?:\/\//i.test(product.image_path)
    ? product.image_path
    : product.image_path.startsWith("/assets/products/")
      ? product.image_path
      : `${API_BASE_URL.replace(/\/$/, "")}/${product.image_path.replace(/^\//, "")}`;
  return [databaseImage, product.kioskImage].filter((url, index, urls) => url && urls.indexOf(url) === index);
}

export default function ProductCard({ product, onAdd }) {
  const [added, setAdded] = useState(false);
  const [imageIndex, setImageIndex] = useState(0);
  const available = product.available_quantity > 0;
  const images = imageUrls(product);
  const image = images[imageIndex];

  function add() {
    if (!available) return;
    onAdd(product);
    setAdded(true);
    window.setTimeout(() => setAdded(false), 700);
  }

  return <button
    className={`product-tile tile-${product.kioskColor} ${available ? "" : "sold-out"} ${added ? "is-added" : ""}`}
    type="button"
    onClick={add}
    disabled={!available}
    aria-label={`${available ? "Add" : "Unavailable"} ${product.name}, ETB ${product.price}`}
  >
    <span className="product-tile-image">
      {image
        ? <img src={image} alt={product.name} loading="lazy" onError={() => setImageIndex(index => index + 1)}/>
        : <Package size={64} strokeWidth={1.3} aria-hidden="true"/>}
      {added && <i className="product-added-mark"><Check size={20}/></i>}
      {!available && <i className="product-sold-label">SOLD OUT</i>}
    </span>
    <span className="product-tile-info"><b>{product.name}</b><strong>ETB {Number(product.price).toFixed(0)}</strong><small className="product-stock">Stock: {Number(product.available_quantity) || 0}</small></span>
    <span className="product-tile-add" aria-hidden="true">{added ? <Check size={20}/> : <Plus size={20}/>}</span>
  </button>;
}
