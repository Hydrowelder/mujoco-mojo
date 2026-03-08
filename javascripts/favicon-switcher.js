/* --- MuJoCo Mojo: System-Level Favicon Sync --- */

const syncFaviconToSystem = () => {
    const favicon = document.querySelector("link[rel='icon']");
    if (!favicon) return;

    // 1. Check OS Preference (ignores MkDocs palette)
    const isSystemDark = window.matchMedia("(prefers-color-scheme: dark)").matches;

    // 2. Identify the base path from the current favicon
    const currentHref = favicon.href;
    const baseDir = currentHref.substring(0, currentHref.lastIndexOf('/assets/') + 1);

    // 3. Select logo based purely on system theme
    const logoName = isSystemDark ? "dark-logo.svg" : "light-logo.svg";
    const newPath = `${baseDir}assets/${logoName}`;

    // 4. Update the link tag
    if (favicon.getAttribute("href") !== newPath) {
        favicon.href = newPath;
    }
}

// Initial Run
syncFaviconToSystem();

// Listen for System Theme changes (e.g., sunset/sunrise auto-toggles)
window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", syncFaviconToSystem);
