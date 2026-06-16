let currentTab = null;

const usefulKeywords = [
    "tutorial", "documentation", "docs", "guide", "learn", "course",
    "research", "paper", "study", "education", "history", "science",
    "biology", "chemistry", "physics", "mathematics", "geography",
    "economics", "music", "singer", "artist", "biography", "culture",
    "literature", "language", "exam", "career", "job", "certification",
    "python", "flask", "programming", "database", "cloud", "aws",
    "machine learning", "artificial intelligence", "ai"
];

document.addEventListener("DOMContentLoaded", function () {
    const tokenInput = document.getElementById("tokenInput");
    const saveTokenBtn = document.getElementById("saveTokenBtn");
    const tokenStatus = document.getElementById("tokenStatus");
    const googleLoginBtn = document.getElementById("googleLoginBtn");
    const saveBtn = document.getElementById("saveBtn");

    if (!tokenInput || !saveTokenBtn || !tokenStatus || !googleLoginBtn || !saveBtn) {
        console.error("Required popup elements missing in popup.html");
        return;
    }

    const savedToken = localStorage.getItem("mnemo_token");

    if (savedToken) {
        tokenInput.value = savedToken;
        tokenStatus.innerText = "Account connected.";
        tokenStatus.style.color = "green";
    }

    saveTokenBtn.addEventListener("click", function () {
        const manualToken = tokenInput.value.trim();

        if (!manualToken) {
            tokenStatus.innerText = "Please paste your token.";
            tokenStatus.style.color = "red";
            return;
        }

        localStorage.setItem("mnemo_token", manualToken);
        tokenStatus.innerText = "Token saved. Account connected.";
        tokenStatus.style.color = "green";
    });

    googleLoginBtn.addEventListener("click", function () {
        tokenStatus.innerText = "Connecting with Google...";
        tokenStatus.style.color = "#2563eb";

        chrome.identity.getAuthToken({ interactive: true }, function (googleToken) {
            if (chrome.runtime.lastError || !googleToken) {
                tokenStatus.innerText = chrome.runtime.lastError
                    ? chrome.runtime.lastError.message
                    : "Google login failed.";
                tokenStatus.style.color = "red";
                console.error("Chrome identity error:", chrome.runtime.lastError);
                return;
            }

            fetch("https://mnemosphere.onrender.com/api/extension-google-login", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    access_token: googleToken
                })
            })
            .then(response => response.json())
            .then(data => {
                if (!data.success) {
                    tokenStatus.innerText = data.message || "Connection failed.";
                    tokenStatus.style.color = "red";
                    return;
                }

                localStorage.setItem("mnemo_token", data.token);
                tokenInput.value = data.token;

                tokenStatus.innerText = "Connected as " + data.email;
                tokenStatus.style.color = "green";
            })
            .catch(error => {
                tokenStatus.innerText = "Connection error.";
                tokenStatus.style.color = "red";
                console.error("Backend connection error:", error);
            });
        });
    });

    chrome.tabs.query({ active: true, currentWindow: true }, function (tabs) {
        currentTab = tabs[0];

        const title = currentTab.title;
        const url = currentTab.url;

        document.getElementById("pageTitle").innerText = title;

        const suggestedTopic = suggestTopic(title, url);
        document.getElementById("topic").value = suggestedTopic;

        const useful = isUsefulPage(title, url);

        chrome.storage.local.get(["memoryMode"], function (result) {
            const mode = result.memoryMode || "manual";
            document.getElementById("memoryMode").value = mode;
            updateModeUI(mode, useful);
        });

        document.getElementById("memoryMode").addEventListener("change", function () {
            const selectedMode = this.value;

            chrome.storage.local.set({
                memoryMode: selectedMode
            });

            updateModeUI(selectedMode, useful);
        });
    });

    saveBtn.addEventListener("click", saveMemory);
});

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

function isUsefulPage(title, url) {
    const text = (title + " " + url).toLowerCase();
    return usefulKeywords.some(keyword => text.includes(keyword));
}

function updateModeUI(mode, useful) {
    const suggestText = document.getElementById("suggestText");
    const suggestBox = document.getElementById("suggestBox");
    const saveBtn = document.getElementById("saveBtn");

    suggestBox.className = "suggest-box";

    if (mode === "manual") {
        suggestText.innerText = "Manual Mode: You choose when to save this page.";
        suggestBox.classList.add("neutral");
        saveBtn.innerText = "Save Memory";
    } else if (mode === "suggest") {
        if (useful) {
            suggestText.innerText = "Suggest Mode: This page looks useful. Review the details and save it.";
            suggestBox.classList.add("useful");
        } else {
            suggestText.innerText = "Suggest Mode: This page is not clearly educational, but you can still save it.";
            suggestBox.classList.add("neutral");
        }
        saveBtn.innerText = "Save Suggested Memory";
    } else if (mode === "auto") {
        if (useful) {
            suggestText.innerText = "Auto Preview Mode: This page would be auto-saved in full auto mode.";
            suggestBox.classList.add("useful");
        } else {
            suggestText.innerText = "Auto Preview Mode: This page would be ignored in full auto mode.";
            suggestBox.classList.add("neutral");
        }
        saveBtn.innerText = "Save Now";
    }
}

function saveMemory() {
    const topic = document.getElementById("topic").value;
    const notes = document.getElementById("notes").value;
    const difficulty = document.getElementById("difficulty").value;
    const status = document.getElementById("status");

    const token = localStorage.getItem("mnemo_token") || "";

    if (!token) {
        status.innerText = "Please connect your MnemoSphere account first.";
        status.style.color = "red";
        return;
    }

    if (!topic) {
        status.innerText = "Please enter a topic.";
        status.style.color = "red";
        return;
    }

    const memoryData = {
        title: currentTab.title,
        url: currentTab.url,
        topic: topic,
        notes: notes,
        difficulty: difficulty
    };

    fetch("https://mnemosphere.onrender.com/api/add-memory", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "X-Mnemo-Token": token
        },
        body: JSON.stringify(memoryData)
    })
    .then(async response => {
        const data = await response.json();

        if (!response.ok || data.success === false) {
            status.innerText = data.message || "Memory was not saved.";
            status.style.color = "red";
            return;
        }

        status.innerText = data.message;
        status.style.color = "green";
    })
    .catch(error => {
        status.innerText = "Error saving memory.";
        status.style.color = "red";
        console.error(error);
    });
}