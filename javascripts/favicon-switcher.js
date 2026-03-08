// Function to swap the favicon based on the active palette
const syncFavicon = () => {
    const palette = document.body.getAttribute("data-md-color-scheme")
    const favicon = document.querySelector("link[rel='icon']")

    if (!favicon) return

    if (palette === "slate") {
        favicon.href = "assets/dark-logo.png"
    } else {
        favicon.href = "assets/light-logo.png"
    }
}

// 1. Run on initial load
document.addEventListener("DOMContentLoaded", syncFavicon)

// 2. Watch for theme toggles without a page reload
const observer = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
        if (mutation.type === "attributes" && mutation.attributeName === "data-md-color-scheme") {
            syncFavicon()
        }
    })
})

observer.observe(document.body, { attributes: true })
