import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { AlertTriangle, CheckCircle2, Clock3, ShieldCheck } from "lucide-react";
import { apiRequest } from "../services/api";

export default function PaymentResultPage() {
  const [searchParams] = useSearchParams();
  const orderId = searchParams.get("order_id");
  const [state, setState] = useState("checking");

  useEffect(() => {
    let active = true;
    async function check() {
      if (!orderId) { setState("unknown"); return; }
      try {
        await apiRequest("/api/payments/chapa/verify", {
          method: "POST",
          body: JSON.stringify({ order_id: orderId }),
        });
        const result = await apiRequest(`/api/orders/${encodeURIComponent(orderId)}/status`);
        if (!active) return;
        setState(result.order_status === "PAID" ? "paid" : result.order_status === "PAYMENT_REVIEW" ? "review" : "pending");
      } catch { if (active) setState("pending"); }
    }
    check();
    return () => { active = false; };
  }, [orderId]);

  const paid = state === "paid";
  const review = state === "review";
  const Icon = paid ? CheckCircle2 : review ? AlertTriangle : Clock3;
  const title = paid ? "Paid" : review ? "Ask for help" : state === "checking" ? "Checking payment" : "Payment pending";
  const message = paid
    ? "Return to the machine."
    : review
      ? "Show the order number to staff."
      : "Continue at the machine.";

  return <div className="payment-result-page"><div className="payment-result-card">
    <span className={`result-icon ${paid ? "paid" : review ? "review" : "pending"}`}><Icon size={38}/></span>
    <h1>{title}</h1>
    <p aria-live="polite">{message}</p>
    {orderId && <div className="result-reference"><small>ORDER</small><b>{orderId}</b></div>}
    <Link to="/" className="secondary-touch-button">Return</Link>
  </div></div>;
}
