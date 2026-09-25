/**
 * storage-service.js
 * High-performance, resilient storage service for OPTCG-COACH.
 * Seamlessly integrates IndexedDB for large datasets (decks, versions, logs)
 * with synchronous localStorage and in-memory cache fallbacks.
 */
(function(global) {
    'use strict';

    const DB_NAME = 'OPTCG_COACH_DB';
    const DB_VERSION = 1;
    const STORE_NAME = 'keyval';

    const memoryFallback = new Map();
    let dbPromise = null;

    function getDB() {
        if (!dbPromise) {
            dbPromise = new Promise((resolve) => {
                if (typeof window === 'undefined' || !window.indexedDB) {
                    return resolve(null);
                }
                try {
                    const req = window.indexedDB.open(DB_NAME, DB_VERSION);
                    req.onupgradeneeded = function(e) {
                        const db = e.target.result;
                        if (!db.objectStoreNames.contains(STORE_NAME)) {
                            db.createObjectStore(STORE_NAME);
                        }
                    };
                    req.onsuccess = function(e) {
                        resolve(e.target.result);
                    };
                    req.onerror = function(err) {
                        console.warn('[StorageService] IndexedDB open error, falling back:', err);
                        resolve(null);
                    };
                } catch (e) {
                    resolve(null);
                }
            });
        }
        return dbPromise;
    }

    const StorageService = {
        /**
         * Synchronous get (reads from localStorage, memory cache fallback).
         */
        get(key, defaultValue = null) {
            try {
                if (typeof window !== 'undefined' && window.localStorage) {
                    const raw = window.localStorage.getItem(key);
                    if (raw !== null) {
                        return JSON.parse(raw);
                    }
                }
            } catch (err) {
                console.warn(`[StorageService] Sync read error "${key}":`, err);
            }
            if (memoryFallback.has(key)) {
                return memoryFallback.get(key);
            }
            return defaultValue;
        },

        /**
         * Synchronous set (saves to localStorage and memory, queues async IndexedDB sync).
         */
        set(key, value) {
            memoryFallback.set(key, value);
            let savedSync = false;
            try {
                if (typeof window !== 'undefined' && window.localStorage) {
                    window.localStorage.setItem(key, JSON.stringify(value));
                    savedSync = true;
                }
            } catch (err) {
                console.warn(`[StorageService] localStorage quota exceeded for "${key}", relying on IndexedDB:`, err);
            }

            // Sync to IndexedDB in background
            this.setAsync(key, value).catch(() => {});
            return savedSync;
        },

        /**
         * Synchronous remove.
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
            this.removeAsync(key).catch(() => {});
        },

        /**
         * Asynchronous get via IndexedDB, with localStorage fallback.
         */
        async getAsync(key, defaultValue = null) {
            const db = await getDB();
            if (!db) {
                return this.get(key, defaultValue);
            }
            return new Promise((resolve) => {
                try {
                    const tx = db.transaction(STORE_NAME, 'readonly');
                    const store = tx.objectStore(STORE_NAME);
                    const req = store.get(key);
                    req.onsuccess = () => {
                        if (req.result !== undefined) {
                            resolve(req.result);
                        } else {
                            resolve(StorageService.get(key, defaultValue));
                        }
                    };
                    req.onerror = () => {
                        resolve(StorageService.get(key, defaultValue));
                    };
                } catch (e) {
                    resolve(StorageService.get(key, defaultValue));
                }
            });
        },

        /**
         * Asynchronous set directly to IndexedDB.
         */
        async setAsync(key, value) {
            memoryFallback.set(key, value);
            const db = await getDB();
            if (!db) {
                return this.set(key, value);
            }
            return new Promise((resolve) => {
                try {
                    const tx = db.transaction(STORE_NAME, 'readwrite');
                    const store = tx.objectStore(STORE_NAME);
                    store.put(value, key);
                    tx.oncomplete = () => resolve(true);
                    tx.onerror = () => resolve(false);
                } catch (e) {
                    resolve(false);
                }
            });
        },

        /**
         * Asynchronous remove from IndexedDB.
         */
        async removeAsync(key) {
            memoryFallback.delete(key);
            const db = await getDB();
            if (!db) {
                return this.remove(key);
            }
            return new Promise((resolve) => {
                try {
                    const tx = db.transaction(STORE_NAME, 'readwrite');
                    const store = tx.objectStore(STORE_NAME);
                    store.delete(key);
                    tx.oncomplete = () => resolve(true);
                    tx.onerror = () => resolve(false);
                } catch (e) {
                    resolve(false);
                }
            });
        },

        /**
         * Checks if storage (localStorage or IndexedDB) is available.
         */
        isAvailable() {
            return (typeof window !== 'undefined' && (!!window.localStorage || !!window.indexedDB));
        }
    };

    global.OPTCG_STORAGE = StorageService;
})(window);
