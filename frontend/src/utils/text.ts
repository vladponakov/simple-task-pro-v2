export function toTitleCase(s?: string) {
  if (!s) return "";
  return s.replace(/\w\S*/g, (t) => t[0].toUpperCase() + t.slice(1).toLowerCase());
}
