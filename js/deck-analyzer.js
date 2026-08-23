/**
 * deck-analyzer.js
 * Client-side core logic module for OPTCG deck validation,
 * statistics calculation, meta alignment, synergy evaluation, and smart replacements.
 */
(function(global) {
    'use strict';

    /**
     * Validates whether a card is color-compatible with the chosen leader.
     * Supports single and dual color leaders (e.g., "Red/Green").
     * @param {string} leaderColor
     * @param {string} cardColor
     * @returns {boolean}
     */
    function validateDeckColor(leaderColor, cardColor) {
        if (!leaderColor || !cardColor) return false;
        if (cardColor === 'DON!!') return true;

        const leaderColors = leaderColor.split(/[\s/]+/).map(c => c.trim().toLowerCase()).filter(Boolean);
        const cardColors = cardColor.split(/[\s/]+/).map(c => c.trim().toLowerCase()).filter(Boolean);

        return cardColors.some(c => leaderColors.includes(c));
    }

    /**
     * Calculates deck statistics (counters, blockers, removal count, cost distribution).
     * @param {Array<{card: Object, quantity: number}>} deckCards
     * @returns {Object}
     */
    function calculateDeckStats(deckCards) {
        const stats = {
            total_cards: 0,
            counter_2000_count: 0,
            counter_1000_count: 0,
            blockers_count: 0,
            removal_count: 0,
            cost_distribution: { 0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0, 7: 0, 8: 0, 9: 0, 10: 0 }
        };

        if (!Array.isArray(deckCards)) return stats;

        for (const item of deckCards) {
            const card = item.card || item;
            const qty = typeof item.quantity === 'number' ? item.quantity : 1;
            stats.total_cards += qty;

            // Cost distribution
            try {
                const cost = parseInt(card.card_cost, 10);
                if (!isNaN(cost) && cost >= 0 && cost <= 10) {
                    stats.cost_distribution[cost] += qty;
                }
            } catch (e) {
                // Ignore parse errors
            }

            // Counters
            try {
                const counter = parseInt(card.counter_amount, 10);
                if (counter === 2000) stats.counter_2000_count += qty;
                else if (counter === 1000) stats.counter_1000_count += qty;
            } catch (e) {
                // Ignore parse errors
            }

            // Blockers
            const text = (card.card_text || '').toLowerCase();
            if (text.includes('[blocker]')) {
                stats.blockers_count += qty;
            }

            // Removals
            const isEvent = (card.card_type || '').toLowerCase() === 'event';
            const hasKoEffect = text.includes('k.o.') || text.includes('trash') || text.includes('place into');
            if (isEvent && hasKoEffect) {
                stats.removal_count += qty;
            }
        }

        return stats;
    }

    /**
     * Calculates alignment percentage between user deck and tournament meta lists.
     * @param {Array<string>} userDeckIds
     * @param {Array<{card_id: string, inclusion_percentage: number}>} leaderMetaCards
     * @returns {number} Alignment percentage (0.0 to 100.0)
     */
    function calculateMetaAlignment(userDeckIds, leaderMetaCards) {
        if (!Array.isArray(leaderMetaCards) || leaderMetaCards.length === 0) return 50.0;
        if (!Array.isArray(userDeckIds) || userDeckIds.length === 0) return 0.0;

        const metaCore = {};
        let totalWeight = 0.0;

        for (const c of leaderMetaCards) {
            const inc = c.inclusion_percentage || 0;
            if (inc >= 50.0 && c.card_id) {
                metaCore[c.card_id.toUpperCase().trim()] = inc;
                totalWeight += inc;
            }
        }

        if (totalWeight <= 0) return 50.0;

        let matchedWeight = 0.0;
        const userSet = new Set(userDeckIds.map(id => (id || '').toUpperCase().trim()));

        for (const [cardId, weight] of Object.entries(metaCore)) {
            if (userSet.has(cardId)) {
                matchedWeight += weight;
            }
        }

        return Math.min(100.0, (matchedWeight / totalWeight) * 100.0);
    }

    global.OPTCG_ANALYZER = {
        validateDeckColor,
        calculateDeckStats,
        calculateMetaAlignment
    };
})(window);
