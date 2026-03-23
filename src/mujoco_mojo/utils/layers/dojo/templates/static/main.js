// Global Helpers
const formatTimeAgo = (seconds) => {
    if (!seconds || seconds < 60) return `${seconds || 0}s ago`;
    const mins = Math.floor(seconds / 60);
    return mins < 60 ? `${mins}m ago` : `${Math.floor(mins / 60)}h ago`;
};

// Global Alpine Initialization
document.addEventListener('alpine:init', () => {
    Alpine.store('dojo', {
        isPageReady: false,
        isComplete: false,

        isMuted: localStorage.getItem('mojo_muted') === 'true',
        isAutoRefresh: localStorage.getItem('mojo_auto') !== 'false',

        isSyncing: false,
        syncProgress: 0,

        secondsSinceUpdate: 0,
        lastUpdate: null,

        setPageReady(val) { this.isPageReady = val; },
        toggleMute() {
            this.isMuted = !this.isMuted;
            console.log(`Mute toggled: ${this.isMuted}`);
            localStorage.setItem('mojo_muted', this.isMuted);
        },
        toggleAuto() {
            this.isAutoRefresh = !this.isAutoRefresh;
            console.log(`Auto-refresh toggled: ${this.isAutoRefresh}`);
            localStorage.setItem('mojo_auto', this.isAutoRefresh);
            window.dispatchEvent(new CustomEvent('auto-refresh-toggled', {
                detail: this.isAutoRefresh
            }));
        },
        startSync() {
            this.isSyncing = true;
            this.syncProgress = 0;
        },
        setSyncProgress(val) {
            this.syncProgress = val;
        },
        endSync(timestamp, isComplete) {
            this.syncProgress = 100;

            this.lastUpdate = timestamp;
            this.secondsSinceUpdate = 0;
            this.isComplete = isComplete;
            if (!this.isPageReady) this.isPageReady = true;

            this.isSyncing = false;

            // WAIT for the fade to fully finish before resetting the width.
            // Since your CSS transition is 500ms, we wait 700ms to be safe.
            setTimeout(() => {
                // Now that it's invisible, we reset it for the next "shot"
                this.syncProgress = 0;
            }, 700);
        },
        updateSync(timestamp, isComplete = false) {
            this.lastUpdate = timestamp;
            this.secondsSinceUpdate = 0;
            this.isComplete = isComplete;
            if (!this.isPageReady) this.isPageReady = true;
        }
    });

    // Global Timer
    setInterval(() => {
        if (Alpine.store('dojo').lastUpdate) {
            Alpine.store('dojo').secondsSinceUpdate = Math.floor((Date.now() - Alpine.store('dojo').lastUpdate) / 1000);
        }
    }, 1000);
});

// Watch for theme changes globally
window.addEventListener("DOMContentLoaded", () => {
    syncMojoLogos();
    new MutationObserver(() => syncMojoLogos()).observe(document.documentElement, { attributes: true });
});
