/**
 * storage-service.js
 * Resilient, safe localStorage service with quota protection, fallback memory cache,
 * and schema error handling for OPTCG-COACH.
 */
(function(global) {
    'use strict';

    const memoryFallback = new Map();

    const StorageService = {
        /**
         * Safely retrieves and parses an item from localStorage.
         * Falls back to memory cache if localStorage is disabled or corrupted.
         * @param {string} key
         * @param {*} defaultValue
         * @returns {*}
         */
        get(key, defaultValue = null) {
            try {
                if (typeof window !== 'undefined' && window.localStorage) {
                    const raw = window.localStorage.getItem(key);
                    if (raw === null) {
                        return defaultValue;
                    }
                    return JSON.parse(raw);
                }
            } catch (err) {
                console.warn(`[StorageService] Failed reading key "${key}":`, err);
            }
            if (memoryFallback.has(key)) {
                return memoryFallback.get(key);
            }
            return defaultValue;
        },

        /**
         * Safely serializes and saves an item into localStorage.
         * Catches QuotaExceededError and prevents unhandled crashes.
         * @param {string} key
         * @param {*} value
         * @returns {boolean} True if successfully stored, false otherwise.
         */
        set(key, value) {
            try {
                const serialized = JSON.stringify(value);
                if (typeof window !== 'undefined' && window.localStorage) {
                    window.localStorage.setItem(key, serialized);
                    return true;
                }
            } catch (err) {
                console.warn(`[StorageService] Failed saving key "${key}" (Quota/Storage issue):`, err);
                memoryFallback.set(key, value);
                return false;
            }
            memoryFallback.set(key, value);
            return true;
        },

        /**
         * Removes an item from localStorage and memory fallback.
         * @param {string} key
         */
        remove(key) {
            try {
                if (typeof window !== 'undefined' && window.localStorage) {
                    window.localStorage.removeItem(key);
                }
            } catch (err) {
                console.warn(`[StorageService] Failed removing key "${key}":`, err);
            }
            memoryFallback.delete(key);
        },

        /**
         * Checks if localStorage is available and functional.
         * @returns {boolean}
         */
        isAvailable() {
            try {
                if (typeof window === 'undefined' || !window.localStorage) return false;
                const testKey = '__optcg_test__';
                window.localStorage.setItem(testKey, '1');
                window.localStorage.removeItem(testKey);
                return true;
            } catch (e) {
                return false;
            }
        }
    };

    global.OPTCG_STORAGE = StorageService;
})(window);
