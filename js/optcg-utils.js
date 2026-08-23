/**
 * optcg-utils.js
 * Pure utility functions for OPTCG-COACH (no reactive dependencies).
 * Exposed on window.OPTCG_UTILS for consumption in Vue setup() and external modules.
 */
(function(global) {
    'use strict';

    /**
     * Extracts a normalized leader card ID from various leader object structures.
     * @param {Object} leader
     * @returns {string} Normalized card set ID (e.g. "OP01-001") or "UNKNOWN"
     */
    function getLeaderCardId(leader) {
        if (!leader) return 'UNKNOWN';
        if (leader.card_set_id && leader.card_set_id !== 'UNKNOWN') return leader.card_set_id.toUpperCase().trim();
        if (leader.leader_card_id && leader.leader_card_id !== 'UNKNOWN') return leader.leader_card_id.toUpperCase().trim();
        if (leader.archetype_code && leader.archetype_code.includes('||')) {
            return leader.archetype_code.split('||')[0].trim().toUpperCase();
        }
        if (leader.image) {
            const match = leader.image.match(/\/([A-Z0-9\-]+)\.(png|jpg|jpeg|webp)/i);
            if (match) return match[1].split('-r17')[0].toUpperCase();
        }
        return 'UNKNOWN';
    }

    /**
     * Extracts a normalized card ID from a meta card entry.
     * @param {Object} metaCard
     * @returns {string}
     */
    function getMetaCardId(metaCard) {
        if (!metaCard) return 'UNKNOWN';
        if (metaCard.card_id && metaCard.card_id !== 'UNKNOWN') return metaCard.card_id.toUpperCase().trim();
        if (metaCard.image) {
            const match = metaCard.image.match(/\/([A-Z0-9\-]+)\.(png|jpg|jpeg|webp)/i);
            if (match) return match[1].split('-r17')[0].toUpperCase();
        }
        return 'UNKNOWN';
    }

    /**
     * Splits a card color string into an array of individual colors.
     * @param {string} colorStr
     * @returns {Array<string>}
     */
    function getColors(colorStr) {
        if (!colorStr || colorStr === 'NULL') return [];
        return colorStr.split(/[\s/]+/).map(c => c.trim()).filter(Boolean);
    }

    /**
     * Returns Tailwind CSS classes matching a specific One Piece card color.
     * @param {string} color
     * @returns {string}
     */
    function getColorClass(color) {
        const base = 'bg-slate-900 text-slate-100';
        switch ((color || '').toLowerCase().trim()) {
            case 'red':    return 'bg-red-600 text-white border-red-500';
            case 'green':  return 'bg-emerald-600 text-white border-emerald-500';
            case 'blue':   return 'bg-blue-600 text-white border-blue-500';
            case 'purple': return 'bg-purple-600 text-white border-purple-500';
            case 'black':  return 'bg-zinc-800 text-slate-200 border-zinc-700';
            case 'yellow': return 'bg-amber-400 text-slate-950 border-amber-300 font-extrabold';
            default:       return base;
        }
    }

    /**
     * Translates English color names to Portuguese for localized UI rendering.
     * @param {string} color
     * @returns {string}
     */
    function translateColor(color) {
        const dictionary = {
            'red': 'Vermelho',
            'green': 'Verde',
            'blue': 'Azul',
            'purple': 'Roxo',
            'black': 'Preto',
            'yellow': 'Amarelo'
        };
        return dictionary[(color || '').toLowerCase().trim()] || color;
    }

    /**
     * Checks if a card's color is compatible with a leader's allowed colors.
     * @param {Object} leaderCard
     * @param {Object} card
     * @returns {boolean}
     */
    function isColorCompatible(leaderCard, card) {
        if (!leaderCard || !card) return false;
        if (card.card_color === 'DON!!') return true;
        const leaderColors = getColors(leaderCard.card_color).map(c => c.toLowerCase().trim());
        const cardColors = getColors(card.card_color).map(c => c.toLowerCase().trim());
        return cardColors.some(c => leaderColors.includes(c));
    }

    /**
     * Formats a monetary price in USD currency style.
     * @param {number|string} price
     * @returns {string}
     */
    function formatPrice(price) {
        if (price === undefined || price === null || price === 'NULL' || price === 0) return 'Indisponivel';
        return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(price);
    }

    /**
     * Builds the external search URL for Liga One Piece marketplace.
     * @param {Object} card
     * @returns {string}
     */
    function getLigaOnePieceUrl(card) {
        if (!card) return 'https://www.ligaonepiece.com.br/';
        let query = '';
        if (card.card_set_id && card.card_set_id !== 'NULL' && card.card_set_id !== 'DON!!') {
            query = card.card_set_id;
        } else if (card.card_id && card.card_id !== 'UNKNOWN' && card.card_id !== 'NULL') {
            query = card.card_id;
        } else if (card.card_name) {
            query = card.card_name;
        }
        query = query.trim();
        if (!query) return 'https://www.ligaonepiece.com.br/';
        return 'https://www.ligaonepiece.com.br/?view=cards/search&card=' + encodeURIComponent(query);
    }

    /**
     * Parses a single line from an imported decklist text format.
     * Supports formats like "4x OP01-001", "4 OP01-001", "OP01-001 4x".
     * @param {string} rawLine
     * @returns {{qty: number, id: string}|null}
     */
    function parseTxtLine(rawLine) {
        const line = (rawLine || '').trim();
        if (!line || line.startsWith('//') || line.startsWith('#')) return null;

        let qty = 1;
        let m = line.match(/^(\d+)\s*[xX]/);
        if (m) {
            qty = parseInt(m[1], 10);
        } else {
            m = line.match(/[xX]\s*(\d+)\s*$/);
            if (m) {
                qty = parseInt(m[1], 10);
            } else {
                m = line.match(/^(\d+)\s+/);
                if (m) {
                    qty = parseInt(m[1], 10);
                }
            }
        }

        const idMatch = line.match(/([A-Za-z]{1,4}-?\d{1,3}-[A-Za-z0-9]{1,4})/i) || line.match(/([A-Za-z0-9]+-[A-Za-z0-9]+)/i);
        if (!idMatch) return null;

        return { qty, id: idMatch[1].toUpperCase().trim() };
    }

    global.OPTCG_UTILS = {
        getLeaderCardId,
        getMetaCardId,
        getColors,
        getColorClass,
        translateColor,
        isColorCompatible,
        formatPrice,
        getLigaOnePieceUrl,
        parseTxtLine
    };
})(window);
