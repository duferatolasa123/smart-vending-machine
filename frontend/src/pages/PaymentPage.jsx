import { useCallback, useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { AlertTriangle, LoaderCircle, ShieldCheck } from "lucide-react";
import { QRCodeSVG } from "qrcode.react";
import { apiRequest } from "../services/api";

function getSavedOrder() {
  try { return JSON.parse(sessionStorage.getItem("smartvend-active-order") || "null"); }
  catch { return null; }
}

export default function PaymentPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const orderId = searchParams.get("orderId");
  const [order] = useState(getSavedOrder);
  const [orderStatus, setOrderStatus] = useState(null);
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState("");

  const loadOrderStatus = useCallback(async () => {
    if (!orderId) return;
    const result = await apiRequest(`/api/orders/${encodeURIComponent(orderId)}/status`);
    setOrderStatus(result);
    if (result.order_status === "PAID") navigate(`/order/${encodeURIComponent(orderId)}`, { replace: true });
  }, [orderId, navigate]);

  useEffect(() => {
    if (!orderId || !order?.checkoutUrl || order.orderId !== orderId) {
      navigate("/", { replace: true });
      return undefined;
    }
    let active = true;
    let timeoutId;
    const poll = async () => {
      try {
        const result = await apiRequest(`/api/orders/${encodeURIComponent(orderId)}/status`);
        if (!active) return;
        setOrderStatus(result);
        setError("");
        if (result.order_status === "PAID") {
          navigate(`/order/${encodeURIComponent(orderId)}`, { replace: true });
          return;
        }
        if (result.order_status === "PAYMENT_REVIEW") return;
      } catch (requestError) {
        if (active) setError(requestError.message);
      }
      if (active) timeoutId = window.setTimeout(poll, 3500);
    };
    poll();
    return () => { active = false; window.clearTimeout(timeoutId); };
  }, [orderId, order, navigate]);

  async function verifyNow() {
    if (checking) return;
    setChecking(true);
    setError("");
    try {
      await apiRequest("/api/payments/chapa/verify", {
        method: "POST",
        body: JSON.stringify({ order_id: orderId }),
      });
      await loadOrderStatus();
    } catch (requestError) {
      setError(requestError.message || "Could not check the payment yet.");
    } finally {
      setChecking(false);
    }
  }

  const needsReview = orderStatus?.order_status === "PAYMENT_REVIEW";

  return <section className="payment-kiosk-screen payment-minimal">
    <div className="payment-step-heading">
      <h1>Scan to pay</h1>
      <strong>{order.currency || "ETB"} {Number(order.total).toFixed(0)}</strong>
      <span>Order {order.orderNumber}</span>
    </div>
    <div className="payment-scan-layout">
      <div className="qr-frame">
        {needsReview
          ? <div className="qr-state-icon review"><AlertTriangle size={48}/></div>
          : <QRCodeSVG value={order.checkoutUrl} size={270} level="H" includeMargin bgColor="#ffffff" fgColor="#29233e" aria-label="Chapa payment QR code"/>}
      </div>
      <div className="payment-instructions">
        <div className={`payment-wait-state ${needsReview ? "review" : ""}`} aria-live="polite">
          {needsReview ? <AlertTriangle size={20}/> : <LoaderCircle size={20} className="spin"/>}
          <span>{needsReview ? "Ask staff for help" : "Waiting for payment"}</span>
        </div>
        {error && <p className="payment-error" role="status">{error}</p>}
        <button className="check-payment-button" onClick={verifyNow} disabled={checking || needsReview}>
          {checking ? "CHECKING..." : "CHECK PAYMENT"}<ShieldCheck size={18}/>
        </button>
      </div>
    </div>
  </section>;
}
