const syncSystemFavicon = () => {
    const favicon = document.querySelector("link[rel='icon']");
    if (!favicon) return;

    // Check if the user's OS is in Dark Mode
    const isDark = window.matchMedia("(prefers-color-scheme: dark)").matches;

    // Use absolute paths if your site is in a subfolder (like /mujoco-mojo/)
    const path = isDark ? "assets/dark-logo.svg" : "assets/light-logo.svg";

    // Force the browser to refresh the icon by clearing and re-setting
    favicon.href = "";
    favicon.href = path;
}

// Run once on load
syncSystemFavicon();

// Watch for changes to the System Theme (OS level)
window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", syncSystemFavicon);
