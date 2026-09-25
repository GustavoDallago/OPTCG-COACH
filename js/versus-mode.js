/**
 * versus-mode.js
 * Matchup X-Ray / Head-to-Head Tactical Comparator for OPTCG-COACH.
 * Evaluates real Limitless tournament statistics between two leaders,
 * identifies reciprocal threat cards, key counters, and gives strategic advice.
 */
(function(global) {
    'use strict';

    const VersusMode = {
        /**
         * Analyzes the head-to-head matchup between two leaders from meta data.
         * @param {Object} leaderA The user's leader
         * @param {Object} leaderB The opposing leader
         * @returns {Object} Analytical matchup report
         */
        analyze(leaderA, leaderB) {
            if (!leaderA || !leaderB) return null;

            const idA = leaderA.leader_card_id || '';
            const idB = leaderB.leader_card_id || '';

            // Retrieve matchup stats from Leader A's data
            let directStatsA = null;
            if (leaderA.matchups && leaderA.matchups[idB]) {
                directStatsA = leaderA.matchups[idB];
            }

            // Also check inverse from Leader B's data
            let directStatsB = null;
            if (leaderB.matchups && leaderB.matchups[idA]) {
                directStatsB = leaderB.matchups[idA];
            }

            let wins = 0;
            let losses = 0;
            let ties = 0;
            let total = 0;
            let winrateA = 50.0;

            if (directStatsA && directStatsA.total_matches > 0) {
                wins = directStatsA.wins || 0;
                losses = directStatsA.losses || 0;
                ties = directStatsA.ties || 0;
                total = directStatsA.total_matches || 0;
                winrateA = directStatsA.winrate !== undefined ? Number(directStatsA.winrate) : 50.0;
            } else if (directStatsB && directStatsB.total_matches > 0) {
                // Invert stats from B
                wins = directStatsB.losses || 0;
                losses = directStatsB.wins || 0;
                ties = directStatsB.ties || 0;
                total = directStatsB.total_matches || 0;
                winrateA = total > 0 ? Number(((wins / total) * 100).toFixed(1)) : 50.0;
            }

            // Identify key threat cards in Opponent's deck (high cost / power / removal)
            const bCards = leaderB.cards || [];
            const threatCards = bCards
                .filter(c => {
                    const cost = parseInt(c.cost || 0, 10);
                    const pwr = parseInt(c.power || 0, 10);
                    return cost >= 6 || pwr >= 7000 || (c.category === 'core' && c.card_type === 'Event');
                })
                .slice(0, 5);

            // Identify Leader A's key defensive or removal cards
            const aCards = leaderA.cards || [];
            const counterCards = aCards
                .filter(c => c.counter === '+2000' || c.category === 'core')
                .slice(0, 5);

            // Stance & turn recommendation
            let favorable = 'Equilibrado (50/50)';
            let favorableColor = 'text-amber-400';
            let stance = 'Foco em equilibrar presença de mesa e gerenciar recursos.';

            if (total >= 5) {
                if (winrateA >= 55.0) {
                    favorable = `Favorável para ${leaderA.name} (${winrateA}% WR)`;
                    favorableColor = 'text-emerald-400';
                    stance = 'Mantenha pressão constante e force o oponente a gastar contadores da mão.';
                } else if (winrateA <= 45.0) {
                    favorable = `Desfavorável contra ${leaderB.name} (${winrateA}% WR)`;
                    favorableColor = 'text-rose-400';
                    stance = 'Jogue defensivo no early game, economize vidas e guarde remoções para os chefões do oponente.';
                }
            } else {
                favorable = 'Amostra pequena no meta recente';
                favorableColor = 'text-slate-400';
            }

            return {
                leaderA,
                leaderB,
                totalMatches: total,
                wins,
                losses,
                ties,
                winrateA,
                winrateB: Number((100 - winrateA).toFixed(1)),
                favorable,
                favorableColor,
                stance,
                threatCards,
                counterCards
            };
        }
    };

    global.OPTCG_VersusMode = VersusMode;
})(window);
