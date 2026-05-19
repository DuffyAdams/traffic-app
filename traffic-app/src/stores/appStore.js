/**
 * Svelte stores for shared application state
 */
import { writable } from 'svelte/store';

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

export const activeMarkerId = writable(null);
export const mapPanTo = writable(null);
