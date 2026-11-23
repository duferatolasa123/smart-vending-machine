import { useEffect, useMemo, useState } from "react";
import { ArrowRight, ShoppingBag } from "lucide-react";
import { Link } from "react-router-dom";
import ProductCard from "../components/ProductCard";
import { useCart } from "../context/CartContext";
import { apiRequest } from "../services/api";
import { sortKioskProducts, toKioskProduct } from "../data/kioskProducts";

export default function StorePage() {
  const [catalog, setCatalog] = useState([]);
  const [loading, setLoading] = useState(true);
  const [catalogError, setCatalogError] = useState("");
  const { machine, chooseMachine, addItem, itemCount, total } = useCart();

  useEffect(() => {
    if (!machine?.id) {
      setCatalog([]);
      setCatalogError("");
      setLoading(true);
      let active = true;
      apiRequest("/api/machines/")
        .then(machines => {
          if (!active) return;
          const selected = machines.find(item => item.status === "online" && item.is_active) || null;
          if (selected) chooseMachine(selected);
          else {
            setCatalogError("No machine available");
            setLoading(false);
          }
        })
        .catch(() => {
          if (active) {
            setCatalogError("Could not load products");
            setLoading(false);
          }
        });
      return () => { active = false; };
    }
    let active = true;
    setLoading(true);
    apiRequest(`/api/store/catalog?machine_id=${encodeURIComponent(machine.id)}`)
      .then(data => {
        if (active) {
          setCatalog(data.products);
          setCatalogError("");
        }
      })
      .catch(() => { if (active) setCatalogError("Could not load products"); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [machine?.id, chooseMachine]);

  const products = useMemo(
    () => sortKioskProducts(catalog.map(toKioskProduct).filter(Boolean)),
    [catalog],
  );

  return <section className="catalogue-screen kiosk-store-minimal">
    <div className="catalogue-heading"><h1>Choose a treat</h1></div>
    {loading && <div className="catalogue-message">Loading...</div>}
    {!loading && catalogError && <div className="catalogue-message"><strong>{catalogError}</strong><Link to="/" className="secondary-touch-button">Back</Link></div>}
    {!loading && !catalogError && products.length > 0 && <div className="kiosk-product-grid">{products.map(product => <ProductCard key={`${product.product_id}-${product.machine_slot_id}`} product={product} onAdd={addItem}/>)}</div>}
    {!loading && !catalogError && products.length === 0 && <div className="catalogue-message"><strong>No products available</strong></div>}
    {itemCount > 0 && <Link className="cart-dock kiosk-cart-dock" to="/checkout"><span className="cart-dock-icon"><ShoppingBag size={21}/><i>{itemCount}</i></span><strong>ETB {total.toFixed(0)}</strong><span className="cart-dock-action">VIEW CART <ArrowRight size={17}/></span></Link>}
  </section>;
}
