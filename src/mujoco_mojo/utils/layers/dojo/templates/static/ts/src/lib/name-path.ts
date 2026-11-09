// each path segment of a name encoded on its own, so a nested name like
// 'project/name' stays 'project/name' in the URL (not 'project%2Fname'),
// matching the {name:path} FastAPI routes for labs and profiles
export function encodeNamePath(name: string): string {
  return name.split("/").map(encodeURIComponent).join("/");
}
