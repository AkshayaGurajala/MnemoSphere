function getPageContent() {
    const text = document.body.innerText || "";

    return {
        title: document.title,
        url: window.location.href,
        content: text.slice(0, 5000)
    };
}

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "getPageContent") {
        sendResponse(getPageContent());
    }
});