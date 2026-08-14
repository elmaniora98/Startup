/**
 * Compte à rebours pour les enchères
 * Synchronisé avec l'heure serveur
 */

// Récupérer l'heure serveur au chargement
let serverTimeOffset = 0;

function syncServerTime() {
    fetch('/api/time/')
        .then(response => response.json())
        .then(data => {
            const serverTime = new Date(data.server_time).getTime();
            const localTime = new Date().getTime();
            serverTimeOffset = serverTime - localTime;
            updateAllCountdowns();
        })
        .catch(err => {
            console.error('Erreur de synchronisation:', err);
            updateAllCountdowns();
        });
}

function getServerTime() {
    return new Date().getTime() + serverTimeOffset;
}

function updateAllCountdowns() {
    document.querySelectorAll('[data-end-at]').forEach(function(container) {
        const timerElement = container.querySelector('.countdown-timer, .timer');
        if (!timerElement) return;
        
        const endTime = new Date(container.dataset.endAt).getTime();
        const now = getServerTime();
        const distance = endTime - now;
        
        if (distance <= 0) {
            timerElement.textContent = 'Terminé';
            timerElement.classList.add('text-red-600', 'font-bold');
            container.classList.add('ended');
            return;
        }
        
        const hours = Math.floor(distance / (1000 * 60 * 60));
        const minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
        const seconds = Math.floor((distance % (1000 * 60)) / 1000);
        
        // Format HH:MM:SS
        timerElement.textContent = 
            (hours < 10 ? '0' + hours : hours) + ':' +
            (minutes < 10 ? '0' + minutes : minutes) + ':' +
            (seconds < 10 ? '0' + seconds : seconds);
        
        // Changer la couleur selon le temps restant
        if (distance < 60000) { // Moins d'1 minute
            timerElement.classList.add('text-red-600', 'font-bold');
        } else if (distance < 300000) { // Moins de 5 minutes
            timerElement.classList.add('text-orange-600');
        }
    });
}

// Initialisation
document.addEventListener('DOMContentLoaded', function() {
    const countdownElements = document.querySelectorAll('[data-end-at]');
    if (countdownElements.length > 0) {
        syncServerTime();
        setInterval(updateAllCountdowns, 1000);
    }
});

// Export pour utilisation globale
window.countdownUtils = {
    syncServerTime,
    updateAllCountdowns,
    getServerTime
};
