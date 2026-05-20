export function formatTimeAgo(seconds: number): string {
  if (!seconds || seconds < 60) return `${seconds || 0}s ago`;
  const mins = Math.floor(seconds / 60);
  return mins < 60 ? `${mins}m ago` : `${Math.floor(mins / 60)}h ago`;
}

// Takes an absolute ms timestamp + an optional tick value (ignored, but its
// presence in the Alpine expression causes the template to re-evaluate when
// $store.dojo.notifTick changes every minute).
export function notifTimeAgo(timestamp: number, _tick?: number): string {
  const diff = Math.floor((Date.now() - timestamp) / 1000);
  if (diff < 60) return 'Just now';
  const mins = Math.floor(diff / 60);
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}
