/* ═══════════════════════════════════════════════════
   Anki Vocabulary Builder — Shared JavaScript Utilities
   ═══════════════════════════════════════════════════

   This file contains utility functions used across
   multiple pages. It is loaded in base.html.
   ═══════════════════════════════════════════════════ */

// ═══════════════════════════════════════════════════
// CSRF Token Helper
// ═══════════════════════════════════════════════════

/**
* Get a cookie value by name.
* Used primarily to get the Django CSRF token.
*
 * @param {string} name - Cookie name
* @returns {string|null} Cookie value or null
*/
function getCookie(name) {
    var value = null;
    if (document.cookie && document.cookie !== '') {
        document.cookie.split(';').forEach(function(c) {
            c = c.trim();
            if (c.startsWith(name + '=')) {
                value = decodeURIComponent(c.substring(name.length + 1));
            }
        });
    }
    return value;
}

// ═══════════════════════════════════════════════════
// API Request Helper
// ═══════════════════════════════════════════════════

/**
* Make an authenticated API request.
* Automatically includes CSRF token and auth token.
*
 * @param {string} url - API endpoint URL
* @param {object} options - Fetch options (method, body, etc.)
* @returns {Promise<object>} Parsed JSON response
*/
async function apiRequest(url, options) {
    options = options || {};

    // Build headers
    var headers = options.headers || {};
    headers['X-CSRFToken'] = getCookie('csrftoken');

    // Add auth token if available
    var token = localStorage.getItem('authToken');
    if (token) {
        headers['Authorization'] = 'Token ' + token;
    }

    // Add content type for requests with body
    if (options.body && typeof options.body === 'string') {
        headers['Content-Type'] = 'application/json';
    }

    options.headers = headers;

    var response = await fetch(url, options);

    // Handle 401 Unauthorized — redirect to login
    if (response.status === 401) {
        localStorage.removeItem('authToken');
        window.location.href = '/accounts/login/';
        return null;
    }

    return response;
}

// ═══════════════════════════════════════════════════
// HTML Escaping (XSS Prevention)
// ═══════════════════════════════════════════════════

/**
* Escape HTML special characters to prevent XSS.
*
 * @param {string} text - Raw text
* @returns {string} Escaped HTML-safe text
*/
function escapeHtml(text) {
    if (!text) return '';
    var div = document.createElement('div');
    div.appendChild(document.createTextNode(text));
    return div.innerHTML;
}

// ═══════════════════════════════════════════════════
// Date Formatting
// ═══════════════════════════════════════════════════

/**
* Format an ISO date string to a readable format.
*
 * @param {string} dateString - ISO 8601 date string
* @returns {string} Formatted date string (YYYY-MM-DD HH:MM)
*/
function formatDate(dateString) {
    if (!dateString) return '-';
    var date = new Date(dateString);

    var year = date.getFullYear();
    var month = String(date.getMonth() + 1).padStart(2, '0');
    var day = String(date.getDate()).padStart(2, '0');
    var hours = String(date.getHours()).padStart(2, '0');
    var minutes = String(date.getMinutes()).padStart(2, '0');

    return year + '-' + month + '-' + day + ' ' + hours + ':' + minutes;
}

/**
* Format a date string to a relative time (e.g., "2 hours ago").
*
 * @param {string} dateString - ISO 8601 date string
* @returns {string} Relative time string
*/
function timeAgo(dateString) {
    if (!dateString) return '-';

    var date = new Date(dateString);
    var now = new Date();
    var seconds = Math.floor((now - date) / 1000);

    if (seconds < 60) return 'just now';
    if (seconds < 3600) return Math.floor(seconds / 60) + ' min ago';
    if (seconds < 86400) return Math.floor(seconds / 3600) + ' hr ago';
    if (seconds < 604800) return Math.floor(seconds / 86400) + ' days ago';

    return formatDate(dateString);
}

// ═══════════════════════════════════════════════════
// Status Badge Generator
// ═══════════════════════════════════════════════════

/**
* Generate a Bootstrap badge HTML string for a status.
*
 * @param {string} status - Status string
* @returns {string} HTML badge
*/
function getStatusBadge(status) {
    var badges = {
        'completed':       '<span class="badge bg-success"><i class="bi bi-check-circle"></i> Completed</span>',
        'partial_failure': '<span class="badge bg-warning text-dark"><i class="bi bi-exclamation-triangle"></i> Partial</span>',
        'failed':          '<span class="badge bg-danger"><i class="bi bi-x-circle"></i> Failed</span>',
        'pending':         '<span class="badge bg-info"><i class="bi bi-clock"></i> Pending</span>',
        'translating':     '<span class="badge bg-info"><i class="bi bi-translate"></i> Translating</span>',
        'generating_tts':  '<span class="badge bg-info"><i class="bi bi-volume-up"></i> TTS</span>',
        'pushing_to_anki': '<span class="badge bg-info"><i class="bi bi-send"></i> Pushing</span>',
        'translated':      '<span class="badge bg-info"><i class="bi bi-translate"></i> Translated</span>',
        'tts_done':        '<span class="badge bg-info"><i class="bi bi-volume-up"></i> TTS Done</span>',
        'pushed':          '<span class="badge bg-success"><i class="bi bi-check-circle"></i> Pushed</span>',
    };
    return badges[status] || '<span class="badge bg-secondary">' + escapeHtml(status) + '</span>';
}

// ═══════════════════════════════════════════════════
// Toast Notifications
// ═══════════════════════════════════════════════════

/**
* Show a toast notification at the top of the page.
* Auto-creates the toast container if it doesn't exist.
*
 * @param {string} type - Alert type: 'success', 'danger', 'warning', 'info'
* @param {string} message - Message to display
* @param {number} duration - Auto-hide duration in ms (default: 5000)
*/
function showToast(type, message, duration) {
    duration = duration || 5000;

    // Create toast container if it doesn't exist
    var container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'position-fixed top-0 end-0 p-3';
        container.style.zIndex = '1080';
        document.body.appendChild(container);
    }

    // Icon map
    var icons = {
        'success': 'bi-check-circle-fill',
        'danger': 'bi-x-circle-fill',
        'warning': 'bi-exclamation-triangle-fill',
        'info': 'bi-info-circle-fill',
    };

    // Title map
    var titles = {
        'success': 'Success',
        'danger': 'Error',
        'warning': 'Warning',
        'info': 'Info',
    };

    // Create toast element
    var toastId = 'toast-' + Date.now();
    var toastHtml =
        '<div id="' + toastId + '" class="toast align-items-center text-bg-' + type + ' border-0" role="alert">' +
        '  <div class="d-flex">' +
        '    <div class="toast-body">' +
        '      <i class="bi ' + (icons[type] || 'bi-info-circle') + '"></i> ' +
        '      <strong>' + (titles[type] || 'Notice') + ':</strong> ' +
        '      ' + message +
        '    </div>' +
        '    <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>' +
        '  </div>' +
        '</div>';

    container.insertAdjacentHTML('beforeend', toastHtml);

    // Initialize and show toast
    var toastElement = document.getElementById(toastId);
    var toast = new bootstrap.Toast(toastElement, {
        autohide: true,
        delay: duration,
    });
    toast.show();

    // Remove from DOM after hidden
    toastElement.addEventListener('hidden.bs.toast', function() {
        toastElement.remove();
    });
}

// ═══════════════════════════════════════════════════
// Confirm Dialog
// ═══════════════════════════════════════════════════

/**
* Show a confirmation dialog using Bootstrap modal.
* Returns a Promise that resolves to true/false.
*
 * @param {string} title - Dialog title
* @param {string} message - Dialog message
* @param {string} confirmText - Confirm button text (default: 'Confirm')
* @param {string} confirmClass - Confirm button CSS class (default: 'btn-danger')
* @returns {Promise<boolean>} True if confirmed, false if cancelled
*/
function confirmDialog(title, message, confirmText, confirmClass) {
    confirmText = confirmText || 'Confirm';
    confirmClass = confirmClass || 'btn-danger';

    return new Promise(function(resolve) {
        // Create modal if it doesn't exist
        var modalId = 'confirm-dialog-modal';
        var existingModal = document.getElementById(modalId);
        if (existingModal) {
            existingModal.remove();
        }

        var modalHtml =
            '<div class="modal fade" id="' + modalId + '" tabindex="-1">' +
            '  <div class="modal-dialog modal-dialog-centered">' +
            '    <div class="modal-content">' +
            '      <div class="modal-header">' +
            '        <h5 class="modal-title">' + escapeHtml(title) + '</h5>' +
            '        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>' +
            '      </div>' +
            '      <div class="modal-body">' +
            '        <p>' + escapeHtml(message) + '</p>' +
            '      </div>' +
            '      <div class="modal-footer">' +
            '        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>' +
            '        <button type="button" class="btn ' + confirmClass + '" id="confirm-dialog-yes">' +
            '          ' + escapeHtml(confirmText) +
            '        </button>' +
            '      </div>' +
            '    </div>' +
            '  </div>' +
            '</div>';

        document.body.insertAdjacentHTML('beforeend', modalHtml);

        var modalElement = document.getElementById(modalId);
        var modal = new bootstrap.Modal(modalElement);

        // Handle confirm
        document.getElementById('confirm-dialog-yes').addEventListener('click', function() {
            modal.hide();
            resolve(true);
        });

        // Handle cancel / close
        modalElement.addEventListener('hidden.bs.modal', function() {
            modalElement.remove();
            resolve(false);
        });

        modal.show();
    });
}

// ═══════════════════════════════════════════════════
// Button Loading State Helper
// ═══════════════════════════════════════════════════

/**
* Toggle a button between normal and loading states.
*
 * @param {HTMLElement} btn - The button element
* @param {boolean} loading - True to show loading, false to restore
* @param {string} originalHTML - Original button innerHTML to restore
*/
function setButtonLoading(btn, loading, originalHTML) {
    if (loading) {
        btn.disabled = true;
        btn.setAttribute('data-original-html', btn.innerHTML);
        btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Processing...';
    } else {
        btn.disabled = false;
        btn.innerHTML = originalHTML || btn.getAttribute('data-original-html') || 'Submit';
    }
}

// ═══════════════════════════════════════════════════
// Audio Player Helper
// ═══════════════════════════════════════════════════

/**
* Build an HTML5 audio player element.
*
 * @param {string} filePath - Relative path to the audio file
* @returns {string} HTML string for the audio player
*/
function buildAudioPlayer(filePath) {
    if (!filePath) {
        return '<span class="text-muted"><i class="bi bi-volume-mute"></i> No audio</span>';
    }
    var url = '/media/' + filePath;
    return '<audio controls preload="none" style="height:30px; max-width:250px;">' +
           '  <source src="' + escapeHtml(url) + '" type="audio/mpeg">' +
           '  Your browser does not support audio playback.' +
           '</audio>';
}

// ═══════════════════════════════════════════════════
// Local Storage Helpers
// ═══════════════════════════════════════════════════

/**
* Save a value to localStorage with JSON serialization.
*
 * @param {string} key - Storage key
* @param {*} value - Value to store
*/
function storageSet(key, value) {
    try {
        localStorage.setItem(key, JSON.stringify(value));
    } catch (e) {
        console.warn('localStorage set failed:', e);
    }
}

/**
* Get a value from localStorage with JSON deserialization.
*
 * @param {string} key - Storage key
* @param {*} defaultValue - Default value if key not found
* @returns {*} Stored value or default
*/
function storageGet(key, defaultValue) {
    try {
        var item = localStorage.getItem(key);
        return item ? JSON.parse(item) : defaultValue;
    } catch (e) {
        console.warn('localStorage get failed:', e);
        return defaultValue;
    }
}

// ═══════════════════════════════════════════════════
// Keyboard Shortcuts
// ═══════════════════════════════════════════════════

document.addEventListener('keydown', function(e) {
    // Ctrl+Enter or Cmd+Enter → Submit batch (on batch create page)
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        var submitBtn = document.getElementById('submit-batch-btn');
        if (submitBtn && !submitBtn.disabled) {
            e.preventDefault();
            submitBtn.click();
        }
    }

    // Escape → Close any open modal
    if (e.key === 'Escape') {
        var openModals = document.querySelectorAll('.modal.show');
        openModals.forEach(function(modal) {
            var bsModal = bootstrap.Modal.getInstance(modal);
            if (bsModal) {
                bsModal.hide();
            }
        });
    }
});

// ═══════════════════════════════════════════════════
// Auto-resize Textarea
// ═══════════════════════════════════════════════════

/**
* Auto-resize a textarea to fit its content.
*
 * @param {HTMLElement} textarea - The textarea element
* @param {number} minHeight - Minimum height in pixels (default: 200)
* @param {number} maxHeight - Maximum height in pixels (default: 600)
*/
function autoResizeTextarea(textarea, minHeight, maxHeight) {
    minHeight = minHeight || 200;
    maxHeight = maxHeight || 600;

    textarea.addEventListener('input', function() {
        this.style.height = 'auto';
        var newHeight = Math.min(Math.max(this.scrollHeight, minHeight), maxHeight);
        this.style.height = newHeight + 'px';
    });
}

// Apply auto-resize to vocabulary input if it exists
document.addEventListener('DOMContentLoaded', function() {
    var vocabInput = document.getElementById('vocabulary-input');
    if (vocabInput) {
        autoResizeTextarea(vocabInput, 200, 600);
    }
});

// ═══════════════════════════════════════════════════
// Copy to Clipboard
// ═══════════════════════════════════════════════════

/**
* Copy text to clipboard and show a toast notification.
*
 * @param {string} text - Text to copy
* @param {string} label - Label for the toast message (e.g., "Batch ID")
*/
async function copyToClipboard(text, label) {
    label = label || 'Text';

    try {
        await navigator.clipboard.writeText(text);
        showToast('success', label + ' copied to clipboard!', 2000);
    } catch (e) {
        // Fallback for older browsers
        var textArea = document.createElement('textarea');
        textArea.value = text;
        textArea.style.position = 'fixed';
        textArea.style.left = '-9999px';
        document.body.appendChild(textArea);
        textArea.select();

        try {
            document.execCommand('copy');
            showToast('success', label + ' copied to clipboard!', 2000);
        } catch (err) {
            showToast('danger', 'Failed to copy to clipboard.', 3000);
        }

        document.body.removeChild(textArea);
    }
}

// ═══════════════════════════════════════════════════
// Network Status Detection
// ═══════════════════════════════════════════════════

window.addEventListener('online', function() {
    showToast('success', 'You are back online.', 3000);
});

window.addEventListener('offline', function() {
    showToast('warning', 'You are offline. Some features may not work.', 5000);
});

// ═══════════════════════════════════════════════════
// Page Visibility — Refresh Data When Tab Becomes Active
// ═══════════════════════════════════════════════════

document.addEventListener('visibilitychange', function() {
    if (document.visibilityState === 'visible') {
        // If we're on the batch list page, refresh the data
        var batchesBody = document.getElementById('batches-body');
        if (batchesBody && typeof loadBatches === 'function') {
            loadBatches(currentPage || 1, currentFilter || '');
        }
    }
});

// ═══════════════════════════════════════════════════
// Debounce Utility
// ═══════════════════════════════════════════════════

/**
* Create a debounced version of a function.
* The function will only be called after it stops being
* invoked for the specified delay.
*
 * @param {Function} func - Function to debounce
* @param {number} delay - Delay in milliseconds
* @returns {Function} Debounced function
*/
function debounce(func, delay) {
    var timer = null;
    return function() {
        var context = this;
        var args = arguments;
        clearTimeout(timer);
        timer = setTimeout(function() {
            func.apply(context, args);
        }, delay);
    };
}

// ═══════════════════════════════════════════════════
// Form Dirty State Warning
// ═══════════════════════════════════════════════════

/**
* Warn the user if they try to leave a page with unsaved changes.
* Call this on pages with forms.
*
 * @param {string} formId - The ID of the form to watch
*/
function enableDirtyFormWarning(formId) {
    var form = document.getElementById(formId);
    if (!form) return;

    var isDirty = false;

    // Mark form as dirty when any input changes
    form.addEventListener('input', function() {
        isDirty = true;
    });

    form.addEventListener('change', function() {
        isDirty = true;
    });

    // Clear dirty flag on submit
    form.addEventListener('submit', function() {
        isDirty = false;
    });

    // Warn on page leave
    window.addEventListener('beforeunload', function(e) {
        if (isDirty) {
            e.preventDefault();
            e.returnValue = 'You have unsaved changes. Are you sure you want to leave?';
            return e.returnValue;
        }
    });
}

// ═══════════════════════════════════════════════════
// Console Welcome Message
// ═══════════════════════════════════════════════════

console.log(
    '%c🎴 Anki Vocabulary Builder',
    'font-size: 20px; font-weight: bold; color: #0d6efd;'
);
console.log(
    '%cBuild vocabulary flashcards with AI-powered translations and Azure TTS.',
    'font-size: 12px; color: #6c757d;'
);

function pollBatchStatus(batchId) {
    const interval = setInterval(async () => {
        try {
            const response = await apiRequest(`/api/v1/cards/batches/${batchId}/`);
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            const batch = await response.json();

            // Update progress bar
            const progress = batch.summary.pushed + batch.summary.failed;
            const total = batch.summary.total;
            const percentage = total > 0 ? (progress / total) * 100 : 0;
            
            const progressBar = document.getElementById('progress-bar');
            const progressText = document.getElementById('progress-text');
            if (progressBar && progressText) {
                progressBar.style.width = `${percentage}%`;
                progressBar.setAttribute('aria-valuenow', percentage);
                progressText.textContent = `Processing: ${progress} / ${total}`;
            }

            // Check if batch is complete
            if (batch.status === 'completed' || batch.status === 'partial_failure' || batch.status === 'failed') {
                clearInterval(interval);
                setButtonLoading(document.getElementById('submit-batch-btn'), false);
                
                // Show completion modal
                showCompletionModal(batch);

                // Send OS-level desktop notification
                if ('Notification' in window && Notification.permission === 'granted') {
                    var title = batch.status === 'completed' ? '\u2705 Batch Complete' : '\u26A0\uFE0F Batch Finished';
                    var body = batch.status === 'completed'
                        ? 'All ' + batch.summary.total + ' cards pushed to Anki!'
                        : batch.summary.pushed + '/' + batch.summary.total + ' pushed, ' + batch.summary.failed + ' failed.';
                    if (typeof sendDesktopNotification === 'function') {
                        sendDesktopNotification(title, body);
                    } else {
                        try { new Notification(title, { body: body, tag: 'batch-' + Date.now(), requireInteraction: true }); } catch(e) {}
                    }
                }
            }
        } catch (error) {
            console.error('Error polling batch status:', error);
            clearInterval(interval);
            setButtonLoading(document.getElementById('submit-batch-btn'), false);
            const batchMessage = document.getElementById('batch-message');
            batchMessage.className = 'alert alert-danger';
            batchMessage.textContent = 'Error checking batch status. Please check the batch list for details.';
            batchMessage.classList.remove('d-none');
        }
    }, 2000); // Poll every 2 seconds
}

function showCompletionModal(batch) {
    const vocabInput = document.getElementById('vocabulary-input');
    if (vocabInput) {
        vocabInput.value = '';
        const countSpan = document.getElementById('word-count');
        if (countSpan) {
            countSpan.textContent = '0 words';
            countSpan.className = 'text-muted';
        }
        const submitBtn = document.getElementById('submit-batch-btn');
        if (submitBtn) {
            submitBtn.disabled = true;
        }
    }
    const modal = new bootstrap.Modal(document.getElementById('batchCompleteModal'));
    const modalHeader = document.getElementById('modal-header');
    const modalBody = document.getElementById('modal-body');
    const viewBatchBtn = document.getElementById('view-batch-btn');

    viewBatchBtn.href = `/cards/batches/${batch.id}/`;

    if (batch.status === 'completed') {
        modalHeader.className = 'modal-header bg-success text-white';
        modalBody.innerHTML = `
            <div class="text-center">
                <i class="bi bi-check-circle-fill text-success" style="font-size: 3rem;"></i>
                <h4 class="mt-3">Batch Completed Successfully!</h4>
                <p>All <strong>${batch.summary.total}</strong> cards were processed and pushed to Anki.</p>
            </div>
        `;
    } else { // partial_failure or failed
        modalHeader.className = 'modal-header bg-danger text-white';

        // Build per-card error detail with staggered animations
        let cardErrors = '';
        if (batch.cards && batch.cards.length > 0) {
            let failedCards = batch.cards.filter(c => c.status === 'failed');
            if (failedCards.length > 0) {
                cardErrors = '<div class="mt-3 animate-fade-in"><strong><i class="bi bi-exclamation-diamond"></i> Failed cards:</strong></div><ul class="list-group mt-2">';
                failedCards.forEach((c, idx) => {
                    cardErrors += `<li class="list-group-item list-group-item-danger animate-slide-in" style="animation-delay: ${0.15 * (idx + 1)}s;">
                        <div class="d-flex align-items-start">
                            <i class="bi bi-x-octagon-fill text-danger me-2 mt-1 animate-shake"></i>
                            <div>
                                <strong>${escapeHtml(c.input_text)}</strong>
                                <br><small class="text-muted"><i class="bi bi-arrow-return-right"></i> ${escapeHtml(c.error_message || 'Unknown error')}</small>
                            </div>
                        </div>
                    </li>`;
                });
                cardErrors += '</ul>';
            }
        }

        let errorMessage = `
            <style>
                @keyframes modalShake { 0%,100%{transform:translateX(0)} 15%{transform:translateX(-8px)} 30%{transform:translateX(8px)} 45%{transform:translateX(-5px)} 60%{transform:translateX(5px)} 75%{transform:translateX(-2px)} 90%{transform:translateX(2px)} }
                @keyframes fadeIn { from{opacity:0;transform:translateY(-10px)} to{opacity:1;transform:translateY(0)} }
                @keyframes slideIn { from{opacity:0;transform:translateX(-20px)} to{opacity:1;transform:translateX(0)} }
                @keyframes pulse { 0%,100%{transform:scale(1)} 50%{transform:scale(1.15)} }
                @keyframes shake { 0%,100%{transform:rotate(0)} 25%{transform:rotate(-10deg)} 75%{transform:rotate(10deg)} }
                .animate-modal-shake { animation: modalShake 0.5s ease-in-out; }
                .animate-fade-in { animation: fadeIn 0.4s ease-out both; }
                .animate-slide-in { animation: slideIn 0.4s ease-out both; }
                .animate-pulse { animation: pulse 1.5s ease-in-out infinite; }
                .animate-shake { animation: shake 0.4s ease-in-out 0.5s both; }
                .error-icon-big { font-size: 3.5rem; }
                .summary-item { transition: background-color 0.3s ease; }
                .summary-item:hover { background-color: #f8f9fa; }
            </style>
            <div class="text-center animate-modal-shake">
                <i class="bi bi-x-circle-fill text-danger error-icon-big animate-pulse"></i>
                <h4 class="mt-3 animate-fade-in">Batch Processing Issues</h4>
            </div>
            <ul class="list-group mt-3">
                <li class="list-group-item d-flex justify-content-between align-items-center summary-item animate-slide-in" style="animation-delay:0.1s;">
                    <span><i class="bi bi-check-circle text-success"></i> Successfully pushed:</span>
                    <span class="badge bg-success rounded-pill">${batch.summary.pushed}</span>
                </li>
                <li class="list-group-item d-flex justify-content-between align-items-center summary-item animate-slide-in" style="animation-delay:0.2s;">
                    <span><i class="bi bi-x-circle text-danger"></i> Failed:</span>
                    <span class="badge bg-danger rounded-pill">${batch.summary.failed}</span>
                </li>
                <li class="list-group-item d-flex justify-content-between align-items-center summary-item animate-slide-in" style="animation-delay:0.3s;">
                    <span><i class="bi bi-collection text-secondary"></i> Total:</span>
                    <span class="badge bg-secondary rounded-pill">${batch.summary.total}</span>
                </li>
            </ul>
            ${cardErrors}
        `;
        modalBody.innerHTML = errorMessage;
    }

    modal.show();
}

document.addEventListener('DOMContentLoaded', function() {
    var vocabInput = document.getElementById('vocabulary-input');
    if (vocabInput) {
        autoResizeTextarea(vocabInput, 200, 600);
    }
});
