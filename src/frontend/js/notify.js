export async function ensureNotifyPermission() {
  if (!("Notification" in window)) return false;
  if (Notification.permission === "granted") return true;
  if (Notification.permission === "denied") return false;
  const res = await Notification.requestPermission();
  return res === "granted";
}

export function notify(opts = {}) {
  if (Notification.permission !== "granted") return;
  const n = new Notification(opts.title || "Update", {
    body: opts.body || "",
    icon: opts.icon || "/assets/icons/notify.svg",
    tag: opts.tag || "app-event",
    requireInteraction: !!opts.sticky
  });
  if (opts.onclick) n.addEventListener("click", opts.onclick);
}
