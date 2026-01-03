/**
 * Utility helper functions for the Traffic App
 */

// Generate a random username for anonymous users
const adjectives = ['Cool', 'Happy', 'Swift', 'Brave', 'Clever', 'Lucky'];
const nouns = ['Panda', 'Tiger', 'Eagle', 'Fox', 'Wolf', 'Bear'];

export function generateRandomUsername() {
    const adj = adjectives[Math.floor(Math.random() * adjectives.length)];
    const noun = nouns[Math.floor(Math.random() * nouns.length)];
    const num = Math.floor(Math.random() * 100);
    return `${adj}${noun}${num}`;
}

// Debounce utility
export function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Retry utility with exponential backoff
export async function retryWithBackoff(fn, maxRetries = 3, baseDelay = 1000) {
    for (let attempt = 0; attempt <= maxRetries; attempt++) {
        try {
            return await fn();
        } catch (error) {
            if (attempt === maxRetries) throw error;
            const delay = baseDelay * Math.pow(2, attempt);
            await new Promise(resolve => setTimeout(resolve, delay));
        }
    }
}

// Format timestamp for display
export function formatTimestamp(timestamp) {
    if (!timestamp) return "Recent";
    const date = new Date(timestamp);
    return date.toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        hour12: true
    });
}

// Format time only (for compact display)
export function formatTimeOnly(timestamp) {
    if (!timestamp) return "Recent";
    const date = new Date(timestamp);
    return date.toLocaleString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
        hour12: true
    });
}

// Format comment timestamp (relative time)
export function formatCommentTimestamp(timestamp) {
    if (!timestamp) return "";
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now.getTime() - date.getTime();

    if (diff < 60000) return "just now";
    if (diff < 3600000) {
        const minutes = Math.floor(diff / 60000);
        return `${minutes}m ago`;
    }
    if (diff < 86400000) {
        const hours = Math.floor(diff / 3600000);
        return `${hours}h ago`;
    }
    if (diff < 604800000) {
        const days = Math.floor(diff / 86400000);
        return `${days}d ago`;
    }

    return date.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric'
    });
}

// Truncate description text
export function truncateDescription(text, length = 150) {
    if (!text) return '';
    if (text.length <= 200) return text;

    const lastSpaceIndex = text.lastIndexOf(' ', length);
    if (lastSpaceIndex === -1) return text.substring(0, length);

    return text.substring(0, lastSpaceIndex);
}

// Get emoji icon for incident type
export function getIconForIncidentType(type) {
    const types = {
        "Aircraft Emergency": "🛩️",
        "Animal Hazard": "🐾",
        "Assist CT with Maintenance": "🔧",
        "Road Closure": "🚧",
        "Car Fire": "🔥",
        "Construction": "🏗️",
        "Defective Traffic Signals": "🚦",
        "Fatality": "☠️",
        "Hit and Run No Injuries": "🚗💨",
        "JUMPER": "🧍‍♂️",
        "Live or Dead Animal": "🦌",
        "Maintenance": "🛠️",
        "Debris From Vehicle": "📦",
        "Provide Traffic Control": "🚓",
        "Report of Fire": "🔥",
        "Request CalTrans Notify": "📞",
        "Road Conditions": "🛣️",
        "SIG Alert": "📢",
        "SPINOUT": "↩️",
        "Traffic Break": "✋",
        "Traffic Collision": "🚘",
        "Traffic Hazard": "⚠️",
        "Wrong Way Driver": "↪️"
    };
    return types[type] || "🚨";
}

// Calculate nice step size for chart Y axis
export function calculateNiceStepSize(data) {
    if (!data || data.length === 0) return 1;
    const max = Math.max(...data.filter(n => n > 0));
    if (max === 0) return 1;

    const roughStep = max / 5;
    const magnitude = Math.pow(10, Math.floor(Math.log10(roughStep)));
    const normalized = roughStep / magnitude;

    let niceStep;
    if (normalized <= 1) niceStep = 1;
    else if (normalized <= 2) niceStep = 2;
    else if (normalized <= 5) niceStep = 5;
    else niceStep = 10;

    return niceStep * magnitude;
}
