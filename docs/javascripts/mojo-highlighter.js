// /* --- MuJoCo Mojo Auto-Highlighter --- */

// function highlightMojo() {
//     // 1. Target the main content area specifically
//     const content = document.querySelector(".md-content");
//     if (!content) return;

//     const walk = document.createTreeWalker(
//         content,
//         NodeFilter.SHOW_TEXT,
//         null,
//         false
//     );

//     let node;
//     const nodesToReplace = [];

//     // 2. Identify text nodes that contain our brand names
//     while ((node = walk.nextNode())) {
//         const parent = node.parentElement;
//         if (
//             parent.tagName !== "SCRIPT" &&
//             parent.tagName !== "STYLE" &&
//             parent.tagName !== "NOSCRIPT" &&
//             !parent.classList.contains("mojo-text-highlight")
//         ) {
//             if (node.nodeValue.includes("MuJoCo Mojo")) {
//                 nodesToReplace.push(node);
//             }
//         }
//     }

//     // 3. Perform the swap
//     nodesToReplace.forEach((textNode) => {
//         const span = document.createElement("span");
//         span.innerHTML = textNode.nodeValue.replace(
//             /MuJoCo Mojo/g,
//             '<span class="mojo-text-highlight">MuJoCo Mojo</span>'
//         );
//         textNode.parentNode.replaceChild(span, textNode);
//     });

//     // 4. Handle Inline Code Highlights
//     document.querySelectorAll("code").forEach((code) => {
//         const text = code.textContent.trim();
//         if (text === "mujoco-mojo" || text === "mujoco_mojo") {
//             code.classList.add("mojo-code-highlight");
//         }
//     });
// }

// /* --- THE INSTANT NAVIGATION HOOK --- */

// // Run on initial load
// document.addEventListener("DOMContentLoaded", highlightMojo);

// // Run every time the Material theme swaps content (Instant Navigation)
// if (typeof app !== "undefined") {
//     app.location$.subscribe(() => {
//         // We use a tiny timeout to ensure the DOM has finished swapping
//         setTimeout(highlightMojo, 50);
//     });
// }
