import { useState } from "react";
import { ArrowRight, LockKeyhole, Minus, Plus } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useCart } from "../context/CartContext";
import { apiRequest, API_BASE_URL } from "../services/api";

const ACTIVE_ORDER_KEY = "smartvend-active-order";

function readActiveOrder() {
  try { return JSON.parse(sessionStorage.getItem(ACTIVE_ORDER_KEY) || "null"); }
  catch { return null; }
}

function backendProductImage(item) {
  if (!item.image_path) return "";
  if (/^https?:\/\//i.test(item.image_path)) return item.image_path;
  return `${API_BASE_URL.replace(/\/$/, "")}/${item.image_path.replace(/^\//, "")}`;
}

function productImage(item) {
  return item.kioskImage || backendProductImage(item);
}

export default function CheckoutPage() {
  const { items, machine, setQuantity, total, clearCart } = useCart();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [activeOrder, setActiveOrder] = useState(readActiveOrder);
  const activeOrderId = activeOrder?.orderId || "";
  const displayedTotal = activeOrder ? Number(activeOrder.total) : total;
  const displayedCount = activeOrder?.itemCount ?? items.reduce((sum, item) => sum + item.quantity, 0);
  const navigate = useNavigate();

  async function beginPayment(event) {
    event.preventDefault();
    if (busy || (!activeOrderId && (!items.length || !machine?.id))) return;
    setBusy(true);
    sessionStorage.setItem("smartvend-checkout-busy", "true");
    setError("");
    try {
      let orderState = readActiveOrder();
      if (!orderState?.orderId) {
        const order = await apiRequest("/api/orders/", {
          method: "POST",
          body: JSON.stringify({
            machine_id: machine.id,
            items: items.map(item => ({
              product_id: item.product_id,
              machine_slot_id: item.machine_slot_id,
              quantity: item.quantity,
            })),
          }),
        });
        orderState = {
          orderId: order.id,
          orderNumber: order.order_number,
          total: order.total_amount,
          currency: order.currency,
          machineCode: machine.machine_code,
          itemCount: items.reduce((sum, item) => sum + item.quantity, 0),
        };
        sessionStorage.setItem(ACTIVE_ORDER_KEY, JSON.stringify(orderState));
        setActiveOrder(orderState);
        clearCart();
      }

      const payment = await apiRequest("/api/payments/chapa/initialize", {
        method: "POST",
        body: JSON.stringify({ order_id: orderState.orderId }),
      });
      const checkoutUrl = new URL(payment.payment_url);
      if (checkoutUrl.protocol !== "https:" || checkoutUrl.hostname !== "checkout.chapa.co") {
        throw new Error("Invalid payment link");
      }
      orderState = { ...orderState, checkoutUrl: checkoutUrl.toString() };
      sessionStorage.setItem(ACTIVE_ORDER_KEY, JSON.stringify(orderState));
      setActiveOrder(orderState);
      clearCart();
      navigate(`/payment?orderId=${encodeURIComponent(orderState.orderId)}`);
    } catch (requestError) {
      setError(requestError.message || "Payment is unavailable");
    } finally {
      sessionStorage.removeItem("smartvend-checkout-busy");
      setBusy(false);
    }
  }

  return <section className="cart-screen checkout-minimal">
    <div className="screen-title-row"><h1>Cart</h1></div>
    {!items.length && !activeOrderId
      ? <div className="cart-empty"><p>Cart is empty</p><button className="primary-touch-button" onClick={() => navigate("/shop")}>ADD PRODUCTS <ArrowRight size={20}/></button></div>
      : <div className="cart-layout">
        <section className="cart-lines" aria-label="Cart">
          {items.map(item => <article className="cart-line" key={item.machine_slot_id}>
            <div className={`cart-line-image tile-${item.kioskColor || "water"}`}>
              {productImage(item) ? <img src={productImage(item)} alt="" onError={event => {
                const fallback = backendProductImage(item);
                if (fallback && event.currentTarget.src !== fallback) event.currentTarget.src = fallback;
                else event.currentTarget.style.display = "none";
              }}/> : item.name.slice(0, 1)}
            </div>
            <div className="cart-line-name"><b>{item.name}</b><small>ETB {Number(item.price).toFixed(0)} each</small></div>
            <div className="cart-quantity-control">
              <button type="button" aria-label={`Remove one ${item.name}`} onClick={() => setQuantity(item.machine_slot_id, item.quantity - 1)}><Minus size={18}/></button>
              <b>{item.quantity}</b>
              <button type="button" aria-label={`Add one ${item.name}`} disabled={item.quantity >= item.available_quantity} onClick={() => setQuantity(item.machine_slot_id, item.quantity + 1)}><Plus size={18}/></button>
            </div>
            <strong className="line-total">ETB {(Number(item.price) * item.quantity).toFixed(0)}</strong>
          </article>)}
          {activeOrderId && !items.length && <div className="order-reserved-note">Order saved</div>}
        </section>
        <aside className="cart-summary">
          <div className="summary-row"><span>{displayedCount} items</span><strong>ETB {displayedTotal.toFixed(0)}</strong></div>
          {error && <p className="payment-error" role="alert">{error}</p>}
          <button className="primary-touch-button" onClick={beginPayment} disabled={busy || (!items.length && !activeOrderId) || (!machine && !activeOrderId)}>
            <span>{busy ? "OPENING PAYMENT..." : activeOrderId ? "RETRY PAYMENT" : `PAY ETB ${displayedTotal.toFixed(0)}`}</span><ArrowRight size={21}/>
          </button>
          <div className="secure-caption"><LockKeyhole size={16}/> Secure Chapa payment</div>
        </aside>
      </div>}
  </section>;
}
