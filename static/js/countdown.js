/**
 * Countdown.js - Gestion des compteurs à rebours pour les enchères
 * 
 * Fonctionnalités:
 * - Synchronisation avec l'horloge serveur via /api/time/
 * - Affichage format "2j 04h 12m 33s"
 * - Changement de couleur si < 5 minutes
 * - Re-synchronisation toutes les 30 secondes
 * - Événement custom 'countdown:ended' déclenché à zéro
 */

(function() {
    'use strict';

    // État global
    let serverTimeOffset = 0;
    let lastSync = null;
    const SYNC_INTERVAL = 30000; // 30 secondes

    /**
     * Récupère l'heure serveur et calcule le décalage
     */
    async function syncWithServer() {
        try {
            const response = await fetch('/api/time/');
            if (!response.ok) throw new Error('HTTP ' + response.status);
            
            const data = await response.json();
            const serverTime = new Date(data.server_time).getTime();
            const clientTime = Date.now();
            
            // Calcul du décalage (server - client)
            serverTimeOffset = serverTime - clientTime;
            lastSync = Date.now();
            
            console.log('[Countdown] Synced with server. Offset:', serverTimeOffset, 'ms');
            updateAllCountdowns();
        } catch (error) {
            console.warn('[Countdown] Failed to sync with server:', error.message);
            // Fallback: utiliser l'heure locale
            serverTimeOffset = 0;
            updateAllCountdowns();
        }
    }

    /**
     * Retourne l'heure actuelle corrigée avec le décalage serveur
     */
    function getCurrentTime() {
        if (lastSync) {
            // Utiliser le décalage calculé
            return Date.now() + serverTimeOffset;
        }
        // Fallback: heure locale
        return Date.now();
    }

    /**
     * Formate une durée en millisecondes en chaîne lisible
     * @param {number} ms - Durée en millisecondes
     * @returns {string} Format "2j 04h 12m 33s"
     */
    function formatDuration(ms) {
        if (ms <= 0) return "EXPIRÉ";

        const totalSeconds = Math.floor(ms / 1000);
        const days = Math.floor(totalSeconds / (24 * 3600));
        const hours = Math.floor((totalSeconds % (24 * 3600)) / 3600);
        const minutes = Math.floor((totalSeconds % 3600) / 60);
        const seconds = totalSeconds % 60;

        let parts = [];
        if (days > 0) parts.push(days + 'j');
        if (hours > 0 || days > 0) parts.push(String(hours).padStart(2, '0') + 'h');
        parts.push(String(minutes).padStart(2, '0') + 'm');
        parts.push(String(seconds).padStart(2, '0') + 's');

        return parts.join(' ');
    }

    /**
     * Met à jour un élément countdown individuel
     * @param {HTMLElement} element - L'élément DOM avec data-end
     */
    function updateCountdown(element) {
        const endTime = new Date(element.dataset.end).getTime();
        const now = getCurrentTime();
        const distance = endTime - now;

        if (distance <= 0) {
            element.innerHTML = "EXPIRÉ";
            element.classList.add('countdown-expired');
            element.classList.remove('countdown-soon', 'countdown-normal');
            
            // Déclencher l'événement seulement une fois
            if (!element.dataset.expired) {
                element.dataset.expired = 'true';
                element.dispatchEvent(new CustomEvent('countdown:ended', {
                    bubbles: true,
                    detail: { auctionId: element.dataset.auctionId }
                }));
            }
            return;
        }

        // Mise à jour de l'affichage
        element.innerHTML = formatDuration(distance);

        // Gestion des classes CSS selon le temps restant
        const fiveMinutes = 5 * 60 * 1000;
        element.classList.remove('countdown-expired', 'countdown-soon', 'countdown-normal');
        
        if (distance <= fiveMinutes) {
            element.classList.add('countdown-soon');
        } else {
            element.classList.add('countdown-normal');
        }
    }

    /**
     * Met à jour tous les compteurs de la page
     */
    function updateAllCountdowns() {
        const countdowns = document.querySelectorAll('.countdown');
        countdowns.forEach(updateCountdown);
    }

    /**
     * Initialise les compteurs sur la page
     */
    function init() {
        const countdowns = document.querySelectorAll('.countdown');
        
        if (countdowns.length === 0) {
            console.log('[Countdown] No countdown elements found on this page');
            return;
        }

        console.log('[Countdown] Found', countdowns.length, 'countdown element(s)');

        // Première synchronisation
        syncWithServer();

        // Mise à jour toutes les secondes
        const updateInterval = setInterval(updateAllCountdowns, 1000);

        // Re-synchronisation périodique
        const syncInterval = setInterval(syncWithServer, SYNC_INTERVAL);

        // Nettoyage si la page est déchargée
        window.addEventListener('beforeunload', () => {
            clearInterval(updateInterval);
            clearInterval(syncInterval);
        });
    }

    // Initialisation au chargement du DOM
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // Exposer certaines fonctions globalement pour débogage
    window.Countdown = {
        sync: syncWithServer,
        getTime: getCurrentTime,
        forceUpdate: updateAllCountdowns
    };

})();
