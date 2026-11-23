import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { AlertTriangle, CheckCircle2, Circle, LoaderCircle, PackageCheck, RotateCw, ShieldCheck } from "lucide-react";
import { apiRequest } from "../services/api";

const COMPLETE = new Set(["COMPLETED"]);
const ACTIVE = new Set(["DISPENSING", "IN_PROGRESS", "STARTED"]);
const FAILED = new Set(["FAILED", "FAULT", "PARTIAL_FAILURE", "CANCELLED"]);

export default function OrderProgressPage() {
  const { orderId } = useParams();
  const [order, setOrder] = useState(null);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    const result = await apiRequest(`/api/orders/${encodeURIComponent(orderId)}/status`);
    setOrder(result);
    setError("");
  }, [orderId]);

  useEffect(() => {
    let active = true;
    let timeoutId;
    const poll = async () => {
      try {
        const result = await apiRequest(`/api/orders/${encodeURIComponent(orderId)}/status`);
        if (!active) return;
        setOrder(result);
        setError("");
      } catch (requestError) {
        if (active) setError(requestError.message);
      }
      if (active) timeoutId = window.setTimeout(poll, 2500);
    };
    poll();
    return () => { active = false; window.clearTimeout(timeoutId); };
  }, [orderId]);

  const statuses = (order?.items || []).map(item => (item.dispense_status || "QUEUED").toUpperCase());
  const finished = statuses.length > 0 && statuses.every(value => COMPLETE.has(value));
  const failedCount = statuses.filter(value => FAILED.has(value)).length;
  const completedCount = statuses.filter(value => COMPLETE.has(value)).length;
  const partialFailure = failedCount > 0 && completedCount > 0;
  const review = order?.order_status === "PAYMENT_REVIEW";

  return <section className="order-progress-screen">
    {finished ? <div className="order-terminal success-terminal"><span className="terminal-icon"><CheckCircle2 size={42}/></span><span className="screen-kicker">ORDER COMPLETE · {order.order_number}</span><h1>Take your products.</h1><p>Pickup tray</p><Link className="primary-touch-button" to="/" onClick={() => sessionStorage.removeItem("smartvend-active-order")}>DONE <PackageCheck size={21}/></Link></div>
      : review || failedCount > 0 ? <div className="order-terminal review-terminal"><span className="terminal-icon"><AlertTriangle size={42}/></span><span className="screen-kicker">{partialFailure ? "PARTIAL DISPENSE" : "ASSISTANCE NEEDED"} · {order?.order_number || "ORDER"}</span><h1>{review ? "We’re getting help." : partialFailure ? "Some items need help." : "Please ask for help."}</h1><p>{review ? "Payment confirmed. Show your order number to staff." : "Show your order number to staff."}</p>{order?.items?.length > 0 && <OrderItems items={order.items}/>}<span className="order-ref">ORDER {order?.order_number || orderId}</span></div>
      : <>
        <div className="progress-heading"><h1>{activeCount(statuses) > 0 ? "Dispensing" : "In queue"}</h1></div>
        <div className="progress-card"><div className="progress-card-title"><div><span className="progress-live-dot"/><b>ITEMS</b></div><button onClick={refresh} aria-label="Refresh order status"><RotateCw size={19}/></button></div>
          {order?.items?.length ? <OrderItems items={order.items}/> : <div className="progress-empty"><LoaderCircle className="spin" size={27}/><span>Loading...</span></div>}
          {error && <p className="progress-error" role="status">{error} · Retrying automatically.</p>}
        </div>
        <div className="collect-reminder"><ShieldCheck size={20}/><span>Collect after every item is confirmed.</span></div>
      </>}
  </section>;
}

function activeCount(statuses) {
  return statuses.filter(value => ACTIVE.has(value)).length;
}

function OrderItems({ items }) {
  return <div className="dispense-items">{items.map((item, index) => {
    const state = (item.dispense_status || "QUEUED").toUpperCase();
    const isComplete = COMPLETE.has(state);
    const isActive = ACTIVE.has(state);
    const isFailed = FAILED.has(state);
    const Icon = isComplete ? CheckCircle2 : isFailed ? AlertTriangle : isActive ? LoaderCircle : Circle;
    return <div className={`dispense-item ${isComplete ? "done" : isActive ? "active" : isFailed ? "failed" : "queued"}`} key={`${item.product_name}-${index}`}>
      <span className="dispense-item-icon"><Icon size={22} className={isActive ? "spin" : ""}/></span>
      <div><b>{item.product_name}</b><small>Quantity {item.quantity} · {isComplete ? "Ready" : isFailed ? "Needs help" : isActive ? "Dispensing" : "Waiting"}</small></div>
      <span className="dispense-item-status">{isComplete ? "DONE" : isFailed ? "HELP" : isActive ? "ACTIVE" : "NEXT"}</span>
    </div>;
  })}</div>;
}
