document.addEventListener("DOMContentLoaded", function () {
    const walk = document.createTreeWalker(
        document.querySelector('.md-content'), // Only scan the main content
        NodeFilter.SHOW_TEXT,
        null,
        false
    );

    let node;
    const terms = [
        { regex: /MuJoCo Mojo/g, class: 'mojo-text-highlight' },
        { regex: /`mujoco[-_]mojo`/g, class: 'mojo-code-highlight' }
    ];

    const nodesToReplace = [];
    while (node = walk.nextNode()) {
        if (node.parentElement.tagName !== 'SCRIPT' && node.parentElement.tagName !== 'STYLE') {
            nodesToReplace.push(node);
        }
    }

    nodesToReplace.forEach(textNode => {
        let html = textNode.nodeValue;
        let modified = false;

        // Handle standard text
        if (html.includes("MuJoCo Mojo")) {
            html = html.replace(/MuJoCo Mojo/g, '<span class="mojo-text-highlight">MuJoCo Mojo</span>');
            modified = true;
        }

        if (modified) {
            const span = document.createElement('span');
            span.innerHTML = html;
            textNode.parentNode.replaceChild(span, textNode);
        }
    });

    // Handle Code Blocks separately for better precision
    document.querySelectorAll('code').forEach(code => {
        if (code.textContent === "mujoco-mojo" || code.textContent === "mujoco_mojo") {
            code.classList.add('mojo-code-highlight');
        }
    });
});
