/**
 * VibeOps Toast Notification System
 *
 * Modern, accessible toast notifications to replace alert() calls.
 */

const ToastManager = {
    container: null,
    queue: [],
    maxVisible: 5,

    /**
     * Initialize the toast container
     */
    init() {
        if (this.container) return;

        this.container = document.createElement('div');
        this.container.className = 'toast-container';
        this.container.setAttribute('aria-live', 'polite');
        this.container.setAttribute('aria-label', 'Notifications');
        document.body.appendChild(this.container);

        // Add styles if not already present
        if (!document.getElementById('toast-styles')) {
            const style = document.createElement('style');
            style.id = 'toast-styles';
            style.textContent = `
                .toast-container {
                    position: fixed;
                    bottom: 1.5rem;
                    right: 1.5rem;
                    z-index: 10000;
                    display: flex;
                    flex-direction: column;
                    gap: 0.75rem;
                    max-width: 400px;
                    pointer-events: none;
                }

                .toast {
                    display: flex;
                    align-items: flex-start;
                    gap: 0.75rem;
                    padding: 1rem 1.25rem;
                    background: #1f2937;
                    color: white;
                    border-radius: 8px;
                    box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.2),
                                0 8px 10px -6px rgba(0, 0, 0, 0.1);
                    pointer-events: auto;
                    animation: toastSlideIn 0.3s ease-out;
                    max-width: 100%;
                    font-size: 0.875rem;
                    line-height: 1.5;
                }

                .toast.hiding {
                    animation: toastSlideOut 0.2s ease-in forwards;
                }

                @keyframes toastSlideIn {
                    from {
                        opacity: 0;
                        transform: translateX(100%);
                    }
                    to {
                        opacity: 1;
                        transform: translateX(0);
                    }
                }

                @keyframes toastSlideOut {
                    from {
                        opacity: 1;
                        transform: translateX(0);
                    }
                    to {
                        opacity: 0;
                        transform: translateX(100%);
                    }
                }

                .toast-icon {
                    flex-shrink: 0;
                    width: 20px;
                    height: 20px;
                    margin-top: 1px;
                }

                .toast-content {
                    flex: 1;
                    min-width: 0;
                }

                .toast-title {
                    font-weight: 600;
                    margin-bottom: 0.25rem;
                }

                .toast-message {
                    opacity: 0.9;
                    word-wrap: break-word;
                }

                .toast-close {
                    flex-shrink: 0;
                    padding: 0.25rem;
                    background: transparent;
                    border: none;
                    color: currentColor;
                    opacity: 0.6;
                    cursor: pointer;
                    border-radius: 4px;
                    transition: opacity 0.15s ease;
                }

                .toast-close:hover {
                    opacity: 1;
                    background: rgba(255, 255, 255, 0.1);
                }

                .toast-close:focus {
                    outline: 2px solid rgba(255, 255, 255, 0.5);
                    outline-offset: 2px;
                }

                /* Toast variants */
                .toast.success {
                    background: #059669;
                }

                .toast.error {
                    background: #dc2626;
                }

                .toast.warning {
                    background: #d97706;
                }

                .toast.info {
                    background: #2563eb;
                }

                /* Progress bar */
                .toast-progress {
                    position: absolute;
                    bottom: 0;
                    left: 0;
                    right: 0;
                    height: 3px;
                    background: rgba(255, 255, 255, 0.3);
                    border-radius: 0 0 8px 8px;
                    overflow: hidden;
                }

                .toast-progress-bar {
                    height: 100%;
                    background: rgba(255, 255, 255, 0.6);
                    transition: width linear;
                }

                /* Mobile responsive */
                @media (max-width: 480px) {
                    .toast-container {
                        left: 1rem;
                        right: 1rem;
                        bottom: 1rem;
                        max-width: none;
                    }
                }
            `;
            document.head.appendChild(style);
        }
    },

    /**
     * Show a toast notification
     * @param {string} message - The message to display
     * @param {object} options - Configuration options
     * @returns {object} Toast instance with close method
     */
    show(message, options = {}) {
        this.init();

        const {
            type = 'info',
            title = '',
            duration = 4000,
            closable = true,
            showProgress = true
        } = options;

        // Create toast element
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.setAttribute('role', 'alert');
        toast.style.position = 'relative';

        // Icon based on type
        const icons = {
            success: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>',
            error: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>',
            warning: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',
            info: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>'
        };

        // Build toast content
        let html = `
            <span class="toast-icon">${icons[type] || icons.info}</span>
            <div class="toast-content">
                ${title ? `<div class="toast-title">${this.escapeHtml(title)}</div>` : ''}
                <div class="toast-message">${this.escapeHtml(message)}</div>
            </div>
        `;

        if (closable) {
            html += `
                <button class="toast-close" aria-label="Close notification">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M18 6 6 18M6 6l12 12"/>
                    </svg>
                </button>
            `;
        }

        if (showProgress && duration > 0) {
            html += `
                <div class="toast-progress">
                    <div class="toast-progress-bar" style="width: 100%"></div>
                </div>
            `;
        }

        toast.innerHTML = html;
        this.container.appendChild(toast);

        // Limit visible toasts
        const toasts = this.container.querySelectorAll('.toast:not(.hiding)');
        if (toasts.length > this.maxVisible) {
            this.close(toasts[0]);
        }

        // Close button handler
        const closeBtn = toast.querySelector('.toast-close');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => this.close(toast));
        }

        // Progress bar animation
        if (showProgress && duration > 0) {
            const progressBar = toast.querySelector('.toast-progress-bar');
            if (progressBar) {
                progressBar.style.transitionDuration = `${duration}ms`;
                // Trigger reflow
                progressBar.offsetWidth;
                progressBar.style.width = '0%';
            }
        }

        // Auto close
        let timeout;
        if (duration > 0) {
            timeout = setTimeout(() => this.close(toast), duration);
        }

        // Return toast instance
        return {
            element: toast,
            close: () => this.close(toast),
            clearTimeout: () => {
                if (timeout) clearTimeout(timeout);
            }
        };
    },

    /**
     * Close a toast
     * @param {HTMLElement} toast - Toast element to close
     */
    close(toast) {
        if (!toast || toast.classList.contains('hiding')) return;

        toast.classList.add('hiding');
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 200);
    },

    /**
     * Shorthand methods
     */
    success(message, options = {}) {
        return this.show(message, { ...options, type: 'success' });
    },

    error(message, options = {}) {
        return this.show(message, { ...options, type: 'error', duration: 6000 });
    },

    warning(message, options = {}) {
        return this.show(message, { ...options, type: 'warning', duration: 5000 });
    },

    info(message, options = {}) {
        return this.show(message, { ...options, type: 'info' });
    },

    /**
     * Clear all toasts
     */
    clear() {
        if (!this.container) return;
        const toasts = this.container.querySelectorAll('.toast');
        toasts.forEach(toast => this.close(toast));
    },

    /**
     * Escape HTML to prevent XSS
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
};

// Global function for easy access (replaces alert())
function showNotification(message, type = 'info') {
    return ToastManager.show(message, { type });
}

// Also expose as toast() for convenience
function toast(message, type = 'info') {
    return ToastManager.show(message, { type });
}

// Initialize on DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => ToastManager.init());
} else {
    ToastManager.init();
}

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { ToastManager, showNotification, toast };
}
