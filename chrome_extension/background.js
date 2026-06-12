const usefulKeywords = [
    "tutorial", "documentation", "docs", "guide", "learn", "course",
    "research", "paper", "study", "education", "history", "science",
    "biology", "chemistry", "physics", "mathematics", "geography",
    "economics", "music", "singer", "artist", "biography", "culture",
    "literature", "language", "exam", "career", "job", "certification",
    "python", "flask", "programming", "database", "cloud", "aws",
    "machine learning", "artificial intelligence", "ai"
];

function isUsefulPage(title, url) {
    const text = (title + " " + url).toLowerCase();
    return usefulKeywords.some(keyword => text.includes(keyword));
}

function suggestTopic(title, url) {
    const text = (title + " " + url).toLowerCase();

    if (text.includes("python")) return "Python";
    if (text.includes("flask")) return "Flask";
    if (text.includes("artificial intelligence") || text.includes(" ai ")) return "Artificial Intelligence";
    if (text.includes("machine learning")) return "Machine Learning";
    if (text.includes("aws") || text.includes("cloud")) return "Cloud Computing";
    if (text.includes("job") || text.includes("career") || text.includes("exam")) return "Career";
    if (text.includes("cricket") || text.includes("sport")) return "Sports";
    if (text.includes("singer") || text.includes("music") || text.includes("artist")) return "Music";
    if (text.includes("history")) return "History";
    if (text.includes("biology")) return "Biology";
    if (text.includes("physics")) return "Physics";
    if (text.includes("chemistry")) return "Chemistry";
    if (text.includes("wikipedia")) return "General Knowledge";

    return "General Knowledge";
}

function shouldIgnoreUrl(url) {
    return (
        url.startsWith("chrome://") ||
        url.startsWith("edge://") ||
        url.startsWith("about:") ||
        url.includes("google.com/search") ||
        url.includes("bing.com/search") ||
        url.includes("duckduckgo.com") ||
        url.includes("search?q=") ||
        url.includes("accounts.google.com") ||
        url.includes("mail.google.com") ||
        url.includes("bank") ||
        url.includes("payment") ||
        url.includes("checkout") ||
        url.includes("login")
    );
}

chrome.tabs.onUpdated.addListener(function(tabId, changeInfo, tab) {
    if (changeInfo.status !== "complete") return;
    if (!tab.url || !tab.title) return;

    chrome.storage.local.get(["memoryMode", "autoSavedUrls"], function(result) {
        const mode = result.memoryMode || "manual";

        if (mode !== "auto") return;
        if (shouldIgnoreUrl(tab.url)) return;
        if (!isUsefulPage(tab.title, tab.url)) return;

        const savedUrls = result.autoSavedUrls || [];

        if (savedUrls.includes(tab.url)) return;

        const memoryData = {
            title: tab.title,
            url: tab.url,
            topic: suggestTopic(tab.title, tab.url),
            notes: "Auto-saved by MnemoSphere Auto Mode.",
            difficulty: "Medium"
        };

        fetch("http://127.0.0.1:5000/api/add-memory", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(memoryData)
        })
        .then(response => response.json())
        .then(data => {
            savedUrls.push(tab.url);

            chrome.storage.local.set({
                autoSavedUrls: savedUrls
            });

            console.log("MnemoSphere Auto Save:", data.message);
        })
        .catch(error => {
            console.error("MnemoSphere Auto Save Error:", error);
        });
    });
});