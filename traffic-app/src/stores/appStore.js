/**
 * Svelte stores for shared application state
 */
import { writable, derived } from 'svelte/store';

// Posts and loading state
export const posts = writable([]);
export const loading = writable(true);
export const loadingMore = writable(false);
export const allPostsLoaded = writable(false);

// UI state
export const darkMode = writable(false);
export const condensedView = writable(false);
export const showEventCounters = writable(false);
export const expandedPostId = writable(null);

// Filters
export const selectedType = writable(null);
export const showActiveOnly = writable(false);
export const timeFilter = writable('day');

// Stats data
export const eventsToday = writable(0);
export const eventsLastHour = writable(0);
export const eventsActive = writable(0);
export const totalIncidents = writable(0);
export const incidentsByType = writable({});
export const topLocations = writable({});
export const hourlyData = writable([]);

// Toast notifications
export const toasts = writable([]);
let toastId = 0;

export function addToast(message, type = 'info', duration = 5000) {
    const id = ++toastId;
    toasts.update(t => [...t, { id, message, type }]);
    if (duration > 0) {
        setTimeout(() => removeToast(id), duration);
    }
    return id;
}

export function removeToast(id) {
    toasts.update(t => t.filter(toast => toast.id !== id));
}

// User info
export const currentUsername = writable('');

// Network status
export const isOnline = writable(true);

// Pagination
export const currentPage = writable(1);
export const postsPerPage = writable(30);
export const lastCursor = writable(null);

// Derived store for chart calculations
export const chartPath = derived(hourlyData, ($hourlyData) => {
    const VW = 288, VH = 120;
    const PADX = 8, PADY = 8;

    if (!$hourlyData || $hourlyData.length === 0) return '';

    const xStep = $hourlyData.length > 1 ? (VW - PADX * 2) / ($hourlyData.length - 1) : 0;
    const yMax = Math.max(1, ...$hourlyData);
    const y = v => PADY + (VH - PADY * 2) - (v / yMax) * (VH - PADY * 2);

    return `M ${PADX} ${VH - PADY} ${$hourlyData.map((v, i) => `L ${PADX + i * xStep} ${y(v)}`).join(' ')} L ${VW - PADX} ${VH - PADY} Z`;
});

export const linePath = derived(hourlyData, ($hourlyData) => {
    const VW = 288, VH = 120;
    const PADX = 8, PADY = 8;

    if (!$hourlyData || $hourlyData.length === 0) return '';

    const xStep = $hourlyData.length > 1 ? (VW - PADX * 2) / ($hourlyData.length - 1) : 0;
    const yMax = Math.max(1, ...$hourlyData);
    const y = v => PADY + (VH - PADY * 2) - (v / yMax) * (VH - PADY * 2);

    return $hourlyData.map((v, i) => `${i ? 'L' : 'M'} ${PADX + i * xStep} ${y(v)}`).join(' ');
});
