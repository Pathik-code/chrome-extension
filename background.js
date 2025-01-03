let schedule = {};

async function checkReminders() {
    const currentTime = new Date().toLocaleTimeString('en-US', {
        hour12: false,
        hour: '2-digit',
        minute: '2-digit'
    });

    for (const [period, task] of Object.entries(schedule)) {
        if (currentTime === task.start_time) {
            chrome.notifications.create({
                type: 'basic',
                iconUrl: 'icon48.png',
                title: `Time for ${task.name}`,
                message: task.subtasks.join('\n'),
                priority: 2
            });
        }
    }
}

// Check every minute
setInterval(checkReminders, 60000);

// Fetch schedule from Python server
async function fetchSchedule() {
    const response = await fetch('http://localhost:5000/schedule');
    schedule = await response.json();
}

// Initial fetch
fetchSchedule();

// Listen for refresh requests
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === 'refreshSchedule') {
        fetchSchedule();
    }
});
