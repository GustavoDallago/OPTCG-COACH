/**
 * deck-diff.js
 * Deck Versioning & Visual Diff Engine for OPTCG-COACH.
 * Calculates card additions, removals, quantity differences, and curve shifts between two deck versions.
 */
(function(global) {
    'use strict';

    const DeckDiff = {
        /**
         * Normalizes a deck card array into a map of card_id -> { count, card }
         */
        normalizeDeckMap(cardList = []) {
            const map = new Map();
            for (const item of cardList) {
                const id = item.card_id || item.id;
                if (!id) continue;
                const qty = Number(item.count || item.qty || 1);
                if (map.has(id)) {
                    const existing = map.get(id);
                    existing.qty += qty;
                } else {
                    map.set(id, {
                        id,
                        name: item.card_name || item.name || id,
                        image: item.image || '',
                        cost: item.cost,
                        counter: item.counter,
                        card_type: item.card_type,
                        qty
                    });
                }
            }
            return map;
        },

        /**
         * Compares two deck lists.
         * @param {Array} listA Original / Previous Version
         * @param {Array} listB New / Updated Version
         * @returns {Object} Diff report with added, removed, modified, and unchanged cards.
         */
        compare(listA = [], listB = []) {
            const mapA = this.normalizeDeckMap(listA);
            const mapB = this.normalizeDeckMap(listB);

            const allIds = new Set([...mapA.keys(), ...mapB.keys()]);
            const additions = [];
            const removals = [];
            const changes = [];
            const unchanged = [];

            let addedCount = 0;
            let removedCount = 0;

            allIds.forEach(id => {
                const inA = mapA.get(id);
                const inB = mapB.get(id);

                if (!inA && inB) {
                    // New card added
                    additions.push({ ...inB, delta: inB.qty });
                    addedCount += inB.qty;
                } else if (inA && !inB) {
                    // Card removed entirely
                    removals.push({ ...inA, delta: -inA.qty });
                    removedCount += inA.qty;
                } else if (inA && inB) {
                    const delta = inB.qty - inA.qty;
                    if (delta > 0) {
                        changes.push({ ...inB, oldQty: inA.qty, newQty: inB.qty, delta: `+${delta}`, isIncrease: true });
                        addedCount += delta;
                    } else if (delta < 0) {
                        changes.push({ ...inB, oldQty: inA.qty, newQty: inB.qty, delta: `${delta}`, isIncrease: false });
                        removedCount += Math.abs(delta);
                    } else {
                        unchanged.push(inB);
                    }
                }
            });

            return {
                additions,
                removals,
                changes,
                unchanged,
                addedCount,
                removedCount,
                totalChanged: addedCount + removedCount,
                hasDifferences: (addedCount > 0 || removedCount > 0)
            };
        }
    };

    global.OPTCG_DeckDiff = DeckDiff;
})(window);
