/**
 * optcg-utils.js
 * Pure utility functions for OPTCG-COACH (no reactive dependencies).
 * Exposed on window.OPTCG_UTILS for use inside Vue setup().
 */
(function(global) {
    'use strict';

    function getLeaderCardId(leader) {
        if (!leader) return 'UNKNOWN';
        if (leader.leader_card_id && leader.leader_card_id !== 'UNKNOWN') return leader.leader_card_id;
        if (leader.archetype_code && leader.archetype_code.includes('||')) {
            return leader.archetype_code.split('||')[0].trim().toUpperCase();
        }
        if (leader.image) {
            const match = leader.image.match(/\/([A-Z0-9\-]+)\.(png|jpg|jpeg|webp)/i);
            if (match) return match[1].split('-r17')[0].toUpperCase();
        }
        return 'UNKNOWN';
    }

    function getMetaCardId(metaCard) {
        if (!metaCard) return 'UNKNOWN';
        if (metaCard.card_id && metaCard.card_id !== 'UNKNOWN') return metaCard.card_id;
        if (metaCard.image) {
            const match = metaCard.image.match(/\/([A-Z0-9\-]+)\.(png|jpg|jpeg|webp)/i);
            if (match) return match[1].split('-r17')[0].toUpperCase();
        }
        return 'UNKNOWN';
    }

    function getColors(colorStr) {
        if (!colorStr || colorStr === 'NULL') return [];
        return colorStr.split('/');
    }

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

    function translateColor(color) {
        const dic = { 'red': 'Vermelho', 'green': 'Verde', 'blue': 'Azul', 'purple': 'Roxo', 'black': 'Preto', 'yellow': 'Amarelo' };
        return dic[(color || '').toLowerCase().trim()] || color;
    }

    function isColorCompatible(leaderCard, card) {
        if (!leaderCard || !card) return false;
        if (card.card_color === 'DON!!') return true;
        const lc = getColors(leaderCard.card_color).map(c => c.toLowerCase().trim());
        const cc = getColors(card.card_color).map(c => c.toLowerCase().trim());
        return cc.some(c => lc.includes(c));
    }

    function formatPrice(price) {
        if (price === undefined || price === null || price === 'NULL' || price === 0) return 'Indisponivel';
        return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(price);
    }

    function getLigaOnePieceUrl(card) {
        if (!card) return 'https://www.ligaonepiece.com.br/';
        let query = '';
        if (card.card_set_id && card.card_set_id !== 'NULL' && card.card_set_id !== 'DON!!') { query = card.card_set_id; }
        else if (card.card_id && card.card_id !== 'UNKNOWN' && card.card_id !== 'NULL') { query = card.card_id; }
        else if (card.card_name) { query = card.card_name; }
        query = query.trim();
        if (!query) return 'https://www.ligaonepiece.com.br/';
        return 'https://www.ligaonepiece.com.br/?view=cards/search&card=' + encodeURIComponent(query);
    }

    function parseTxtLine(rawLine) {
        const line = rawLine.trim();
        if (!line || line.startsWith('//') || line.startsWith('#')) return null;
        let qty = 1;
        let m = line.match(/^(\d+)\s*[xX]/);
        if (m) { qty = parseInt(m[1]); }
        else { m = line.match(/[xX]\s*(\d+)\s*$/); if (m) { qty = parseInt(m[1]); }
        else { m = line.match(/^(\d+)\s+/); if (m) { qty = parseInt(m[1]); } } }
        const idMatch = line.match(/([A-Za-z]{1,4}-?\d{1,3}-[A-Za-z0-9]{1,4})/i) || line.match(/([A-Za-z0-9]+-[A-Za-z0-9]+)/i);
        if (!idMatch) return null;
        return { qty, id: idMatch[1].toUpperCase().trim() };
    }

    global.OPTCG_UTILS = { getLeaderCardId, getMetaCardId, getColors, getColorClass, translateColor, isColorCompatible, formatPrice, getLigaOnePieceUrl, parseTxtLine };
})(window);
