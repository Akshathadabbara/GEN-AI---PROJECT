document.addEventListener('DOMContentLoaded', () => {
    // ---------------------------------------------------------
    // Existing Portal Elements
    // ---------------------------------------------------------
    const lostItemsContainer = document.getElementById('lost-items-container');
    const foundItemsContainer = document.getElementById('found-items-container');
    const itemReportForm = document.getElementById('item-report-form');
    const formMessage = document.getElementById('form-message');

    // ---------------------------------------------------------
    // AI Natural Language Search Elements
    // ---------------------------------------------------------
    const aiSearchInput = document.getElementById('ai-search-input');
    const aiSearchBtn = document.getElementById('ai-search-btn');
    const aiClearBtn = document.getElementById('ai-clear-btn');
    const aiLoading = document.getElementById('ai-loading');
    const aiSetupNotice = document.getElementById('ai-setup-notice');
    const aiErrorNotice = document.getElementById('ai-error-notice');
    const aiErrorText = document.getElementById('ai-error-text');
    const aiSummaryCard = document.getElementById('ai-summary-card');
    const aiSummaryText = document.getElementById('ai-summary-text');
    const aiResultsWrapper = document.getElementById('ai-results-wrapper');
    const aiResultsContainer = document.getElementById('ai-results-container');
    const aiResultsCount = document.getElementById('ai-results-count');
    const aiResetResultsBtn = document.getElementById('ai-reset-results-btn');
    const aiEmptyState = document.getElementById('ai-empty-state');
    const aiEmptyText = document.getElementById('ai-empty-text');

    // ---------------------------------------------------------
    // Admin Controls Elements
    // ---------------------------------------------------------
    const adminNavBtn = document.getElementById('admin-nav-btn');
    const adminBanner = document.getElementById('admin-banner');
    const adminLogoutBtn = document.getElementById('admin-logout-btn');

    const adminModal = document.getElementById('admin-modal');
    const adminModalClose = document.getElementById('admin-modal-close');
    const adminModalCancel = document.getElementById('admin-modal-cancel');
    const adminModalSubmit = document.getElementById('admin-modal-submit');
    const adminKeyInput = document.getElementById('admin-key-input');
    const adminModalError = document.getElementById('admin-modal-error');

    const deleteModal = document.getElementById('delete-modal');
    const deleteModalClose = document.getElementById('delete-modal-close');
    const deleteModalCancel = document.getElementById('delete-modal-cancel');
    const deleteModalConfirm = document.getElementById('delete-modal-confirm');
    const deleteItemName = document.getElementById('delete-item-name');
    const deleteItemId = document.getElementById('delete-item-id');
    const deleteModalError = document.getElementById('delete-modal-error');
    const toastContainer = document.getElementById('toast-container');

    // State for pending deletion
    let pendingDeletion = null;

    // ---------------------------------------------------------
    // Safe HTTP / JSON Fetch Utility
    // ---------------------------------------------------------
    /**
     * Resilient fetch wrapper that checks HTTP response status and content-type
     * before attempting to parse JSON, preventing "Unexpected end of JSON input".
     */
    async function safeFetchJson(url, options = {}) {
        const fetchOptions = { ...options };
        fetchOptions.headers = { ...fetchOptions.headers };

        // Attach admin credentials if logged in and not already provided
        const adminKey = getAdminKey();
        if (adminKey && !fetchOptions.headers['X-Admin-Key']) {
            fetchOptions.headers['X-Admin-Key'] = adminKey;
        }

        let response;
        try {
            response = await fetch(url, fetchOptions);
        } catch (networkError) {
            console.error('Network request failed:', networkError);
            throw new Error('Unable to connect to the server. Please check your network connection.');
        }

        const contentType = response.headers.get('content-type') || '';
        let data = null;

        if (contentType.toLowerCase().includes('application/json')) {
            try {
                data = await response.json();
            } catch (jsonParseError) {
                console.warn('Response declared JSON but failed to parse:', jsonParseError);
                data = null;
            }
        } else {
            // Read response text safely for logging if not JSON
            const textContent = await response.text().catch(() => '');
            if (textContent) {
                console.warn('Received non-JSON response from server:', textContent.substring(0, 150));
            }
        }

        if (!response.ok) {
            const errorMsg = (data && data.message)
                ? data.message
                : `Server error (${response.status}: ${response.statusText || 'Request failed'})`;
            const error = new Error(errorMsg);
            error.status = response.status;
            error.data = data;
            throw error;
        }

        if (data === null) {
            throw new Error('Server returned an empty or unreadable response.');
        }

        return data;
    }

    // ---------------------------------------------------------
    // Toast Notification System
    // ---------------------------------------------------------
    function showToast(message, type = 'info') {
        if (!toastContainer) return;

        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        
        let icon = 'ℹ️';
        if (type === 'success') icon = '✅';
        if (type === 'error') icon = '❌';
        if (type === 'warning') icon = '⚠️';

        toast.innerHTML = `<span class="toast-icon">${icon}</span> <span class="toast-msg">${escapeHtml(message)}</span>`;
        toastContainer.appendChild(toast);

        setTimeout(() => {
            toast.classList.add('fade-out');
            setTimeout(() => toast.remove(), 400);
        }, 3600);
    }

    // ---------------------------------------------------------
    // Admin Session Management
    // ---------------------------------------------------------
    function getAdminKey() {
        return sessionStorage.getItem('campus_admin_key') || null;
    }

    function isAdmin() {
        return Boolean(getAdminKey());
    }

    function setAdminSession(key) {
        sessionStorage.setItem('campus_admin_key', key);
        updateAdminUI();
    }

    function clearAdminSession() {
        sessionStorage.removeItem('campus_admin_key');
        updateAdminUI();
    }

    function updateAdminUI() {
        const authenticated = isAdmin();
        if (adminBanner) {
            if (authenticated) {
                adminBanner.classList.remove('hidden');
            } else {
                adminBanner.classList.add('hidden');
            }
        }

        if (adminNavBtn) {
            if (authenticated) {
                adminNavBtn.textContent = '🛡️ Staff Mode: Active';
                adminNavBtn.classList.add('active');
            } else {
                adminNavBtn.textContent = '🛡️ Staff Admin';
                adminNavBtn.classList.remove('active');
            }
        }
    }

    // Modal helpers
    function openModal(modalEl) {
        if (modalEl) {
            modalEl.classList.remove('hidden');
            document.body.style.overflow = 'hidden';
        }
    }

    function closeModal(modalEl) {
        if (modalEl) {
            modalEl.classList.add('hidden');
            document.body.style.overflow = '';
        }
    }

    // ---------------------------------------------------------
    // Admin Login Modal Handlers
    // ---------------------------------------------------------
    if (adminNavBtn) {
        adminNavBtn.addEventListener('click', () => {
            if (isAdmin()) {
                showToast('Administrator session is already active.', 'info');
                if (adminBanner) {
                    adminBanner.scrollIntoView({ behavior: 'smooth' });
                }
            } else {
                adminModalError.classList.add('hidden');
                adminModalError.textContent = '';
                adminKeyInput.value = '';
                openModal(adminModal);
                setTimeout(() => adminKeyInput.focus(), 100);
            }
        });
    }

    if (adminModalClose) {
        adminModalClose.addEventListener('click', () => closeModal(adminModal));
    }
    if (adminModalCancel) {
        adminModalCancel.addEventListener('click', () => closeModal(adminModal));
    }

    if (adminModalSubmit) {
        adminModalSubmit.addEventListener('click', handleAdminLogin);
    }

    if (adminKeyInput) {
        adminKeyInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                handleAdminLogin();
            }
        });
    }

    async function handleAdminLogin() {
        const key = adminKeyInput.value.trim();
        if (!key) {
            adminModalError.textContent = 'Please enter your administrator access key.';
            adminModalError.classList.remove('hidden');
            adminKeyInput.focus();
            return;
        }

        adminModalError.classList.add('hidden');
        adminModalSubmit.disabled = true;
        adminModalSubmit.textContent = 'Verifying...';

        try {
            const data = await safeFetchJson('/api/admin/verify', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Admin-Key': key
                }
            });

            if (data && data.authenticated) {
                setAdminSession(key);
                closeModal(adminModal);
                showToast('Administrator mode unlocked successfully.', 'success');
                fetchItems();
            } else {
                adminModalError.textContent = 'Invalid administrator key. Access denied.';
                adminModalError.classList.remove('hidden');
            }
        } catch (error) {
            adminModalError.textContent = error.message || 'Authorization failed. Please check credentials.';
            adminModalError.classList.remove('hidden');
        } finally {
            adminModalSubmit.disabled = false;
            adminModalSubmit.textContent = 'Authenticate';
        }
    }

    if (adminLogoutBtn) {
        adminLogoutBtn.addEventListener('click', () => {
            clearAdminSession();
            showToast('Logged out from Administrator mode.', 'info');
            fetchItems();
        });
    }

    // ---------------------------------------------------------
    // Item Deletion Confirmation Handlers
    // ---------------------------------------------------------
    function promptDeleteItem(itemId, itemName) {
        if (!isAdmin()) {
            showToast('Unauthorized: Only administrators may delete items.', 'error');
            return;
        }

        pendingDeletion = { id: itemId, name: itemName };
        deleteItemName.textContent = itemName || 'Selected Item';
        deleteItemId.textContent = `ID #${itemId}`;
        deleteModalError.classList.add('hidden');
        deleteModalError.textContent = '';
        deleteModalConfirm.disabled = false;
        deleteModalConfirm.textContent = '🗑️ Permanently Delete';

        openModal(deleteModal);
        deleteModalConfirm.focus();
    }

    if (deleteModalClose) {
        deleteModalClose.addEventListener('click', () => {
            closeModal(deleteModal);
            pendingDeletion = null;
        });
    }

    if (deleteModalCancel) {
        deleteModalCancel.addEventListener('click', () => {
            closeModal(deleteModal);
            pendingDeletion = null;
        });
    }

    if (deleteModalConfirm) {
        deleteModalConfirm.addEventListener('click', async () => {
            if (!pendingDeletion) return;

            const { id: itemId, name: itemName } = pendingDeletion;
            deleteModalConfirm.disabled = true;
            deleteModalConfirm.textContent = 'Deleting...';
            deleteModalError.classList.add('hidden');

            try {
                const result = await safeFetchJson(`/api/items/${itemId}`, {
                    method: 'DELETE',
                    headers: {
                        'X-Admin-Key': getAdminKey()
                    }
                });

                closeModal(deleteModal);
                showToast(result.message || `Item "${itemName}" deleted successfully.`, 'success');

                // Animate removal from DOM without full page reload
                removeCardFromDOM(itemId);

            } catch (error) {
                console.error('Delete item failed:', error);
                deleteModalError.textContent = error.message || 'Failed to delete item. Please try again.';
                deleteModalError.classList.remove('hidden');
                deleteModalConfirm.disabled = false;
                deleteModalConfirm.textContent = '🗑️ Permanently Delete';
            }
        });
    }

    function removeCardFromDOM(itemId) {
        const cards = document.querySelectorAll(`[data-item-id="${itemId}"]`);
        cards.forEach(card => {
            card.classList.add('card-deleting');
            setTimeout(() => {
                card.remove();
                checkContainerEmpty(lostItemsContainer, 'No lost items currently listed.');
                checkContainerEmpty(foundItemsContainer, 'No found items currently listed.');
            }, 300);
        });
    }

    function checkContainerEmpty(container, emptyMessage) {
        if (container && container.querySelectorAll('.item-card').length === 0) {
            container.innerHTML = `<div class="empty-state-card"><p>${emptyMessage}</p></div>`;
        }
    }

    // Close modals on Escape key or backdrop click
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeModal(adminModal);
            closeModal(deleteModal);
            pendingDeletion = null;
        }
    });

    [adminModal, deleteModal].forEach(modal => {
        if (modal) {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    closeModal(modal);
                    pendingDeletion = null;
                }
            });
        }
    });

    // ---------------------------------------------------------
    // AI Natural Search Functions
    // ---------------------------------------------------------
    function updateClearButtonVisibility() {
        if (aiSearchInput.value.trim().length > 0) {
            aiClearBtn.classList.remove('hidden');
        } else {
            aiClearBtn.classList.add('hidden');
        }
    }

    function clearAISearch() {
        aiSearchInput.value = '';
        updateClearButtonVisibility();
        aiLoading.classList.add('hidden');
        aiSetupNotice.classList.add('hidden');
        aiErrorNotice.classList.add('hidden');
        aiSummaryCard.classList.add('hidden');
        aiResultsWrapper.classList.add('hidden');
        aiEmptyState.classList.add('hidden');
        aiResultsContainer.innerHTML = '';
        aiSearchInput.focus();
    }

    async function executeAISearch() {
        const query = aiSearchInput.value.trim();
        if (!query) {
            aiSearchInput.focus();
            aiSearchInput.style.borderColor = '#ef4444';
            setTimeout(() => {
                aiSearchInput.style.borderColor = '';
            }, 1200);
            return;
        }

        const scopeRadio = document.querySelector('input[name="search-scope"]:checked');
        const scope = scopeRadio ? scopeRadio.value : 'all';

        // Reset UI states
        aiErrorNotice.classList.add('hidden');
        aiSetupNotice.classList.add('hidden');
        aiSummaryCard.classList.add('hidden');
        aiResultsWrapper.classList.add('hidden');
        aiEmptyState.classList.add('hidden');
        aiResultsContainer.innerHTML = '';

        // Show loading state
        aiLoading.classList.remove('hidden');
        aiSearchBtn.disabled = true;

        try {
            const data = await safeFetchJson('/api/ai/search', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    query: query,
                    scope: scope,
                    limit: 6
                })
            });

            // 1. Check API Key and summary status
            if (!data.api_key_configured) {
                aiSetupNotice.classList.remove('hidden');
            }
            if (data.llm_response) {
                aiSummaryText.textContent = data.llm_response;
                aiSummaryCard.classList.remove('hidden');
            }

            // 2. Render Results
            const items = data.results || [];
            if (items.length > 0) {
                aiResultsWrapper.classList.remove('hidden');
                aiResultsCount.textContent = `${items.length} Potential Match${items.length > 1 ? 'es' : ''} Retrieved from Database`;

                items.forEach(item => {
                    const card = createResultCard(item);
                    aiResultsContainer.appendChild(card);
                });
            } else {
                aiEmptyState.classList.remove('hidden');
                aiEmptyText.textContent = `No active items in the database match "${query}".`;
            }

        } catch (error) {
            console.error('AI search failed:', error);
            if (error.status === 502) {
                aiErrorText.textContent = 'Server is currently warming up or restarting. Please try your search again in a few seconds.';
            } else {
                aiErrorText.textContent = error.message || 'An error occurred while connecting to the AI search service.';
            }
            aiErrorNotice.classList.remove('hidden');
        } finally {
            aiLoading.classList.add('hidden');
            aiSearchBtn.disabled = false;
        }
    }

    function createResultCard(item) {
        const card = document.createElement('div');
        card.classList.add('item-card');
        card.setAttribute('data-item-id', item.id);

        // Score badge calculation
        const scorePct = Math.round((item.similarity_score || 0) * 100);
        let badgeClass = 'low';
        let badgeIcon = 'ℹ️';

        if (scorePct >= 65) {
            badgeClass = 'strong';
            badgeIcon = '🔥';
        } else if (scorePct >= 40) {
            badgeClass = 'possible';
            badgeIcon = '⚡';
        }

        const confidenceLabel = item.confidence || 'Possible match';
        const evidenceList = item.evidence || [];
        const evidenceHtml = evidenceList.length > 0 
            ? `<div class="evidence-box">
                <strong>Matching Evidence:</strong>
                ${evidenceList.map(ev => `<span class="evidence-pill">✓ ${escapeHtml(ev)}</span>`).join('')}
               </div>`
            : '';

        const typeLabel = item.type === 'lost' ? '📱 Lost Report' : '🔍 Found Item';
        const dateStr = item.item_date || (item.reported_at ? item.reported_at.substring(0, 10) : 'Not specified');

        // Admin delete button
        const adminDeleteBtnHtml = isAdmin()
            ? `<div class="card-admin-bar">
                <button class="card-delete-btn" data-id="${item.id}" data-name="${escapeHtml(item.item_name || 'Item')}">
                    🗑️ Delete Item
                </button>
               </div>`
            : '';

        card.innerHTML = `
            <div class="match-score-badge ${badgeClass}">
                ${badgeIcon} ${scorePct}% Match · ${confidenceLabel}
            </div>
            <h3>${escapeHtml(item.item_name || 'Unknown Item')}</h3>
            <p><strong>Type:</strong> ${typeLabel}</p>
            <p><strong>Category:</strong> ${escapeHtml(item.category || 'Other')}</p>
            <p><strong>Description:</strong> ${escapeHtml(item.description || 'No description provided')}</p>
            <p><strong>Location:</strong> ${escapeHtml(item.location || 'Not specified')}</p>
            <p><strong>Date:</strong> ${escapeHtml(dateStr)}</p>
            <p><strong>Status:</strong> <span style="text-transform: capitalize; color: #15803d; font-weight: bold;">${escapeHtml(item.status || 'active')}</span></p>
            ${evidenceHtml}
            ${adminDeleteBtnHtml}
        `;

        if (isAdmin()) {
            const deleteBtn = card.querySelector('.card-delete-btn');
            if (deleteBtn) {
                deleteBtn.addEventListener('click', () => {
                    promptDeleteItem(item.id, item.item_name || 'Item');
                });
            }
        }

        return card;
    }

    function escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    // AI Search Event Listeners
    aiSearchBtn.addEventListener('click', executeAISearch);

    aiSearchInput.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') {
            event.preventDefault();
            executeAISearch();
        }
    });

    aiSearchInput.addEventListener('input', updateClearButtonVisibility);
    aiClearBtn.addEventListener('click', clearAISearch);
    aiResetResultsBtn.addEventListener('click', clearAISearch);

    // ---------------------------------------------------------
    // Existing Items Browsing & Reporting
    // ---------------------------------------------------------
    async function fetchItems() {
        try {
            const items = await safeFetchJson('/api/items');

            lostItemsContainer.innerHTML = '';
            foundItemsContainer.innerHTML = '';

            let lostCount = 0;
            let foundCount = 0;

            items.forEach(item => {
                const itemCard = document.createElement('div');
                itemCard.classList.add('item-card');
                itemCard.setAttribute('data-item-id', item.id);
                const dateStr = item.reported_at ? new Date(item.reported_at).toLocaleDateString() : 'Not specified';

                // Admin delete button
                const adminActionHtml = isAdmin()
                    ? `<div class="card-admin-bar">
                        <button class="card-delete-btn" data-id="${item.id}" data-name="${escapeHtml(item.item_name || item.name || 'Item')}">
                            🗑️ Delete Item
                        </button>
                       </div>`
                    : '';

                itemCard.innerHTML = `
                    <h3>${escapeHtml(item.item_name || item.name || 'Unknown Item')}</h3>
                    <p><strong>Type:</strong> ${item.type === 'lost' ? '📱 Lost Item' : '🔍 Found Item'}</p>
                    <p><strong>Category:</strong> ${escapeHtml(item.category || 'Other')}</p>
                    <p><strong>Description:</strong> ${escapeHtml(item.description || 'No description provided')}</p>
                    <p><strong>Location:</strong> ${escapeHtml(item.location || 'Not specified')}</p>
                    <p><strong>Student:</strong> ${escapeHtml(item.student_name || 'Protected')}</p>
                    <p><strong>Department:</strong> ${escapeHtml(item.department || 'Not specified')}</p>
                    <p><strong>Year:</strong> ${escapeHtml(item.year_of_study || 'Not specified')}</p>
                    <p><strong>Reported:</strong> ${escapeHtml(dateStr)}</p>
                    <p><em>📞 Contact: ${escapeHtml(item.contact_number || 'Protected')}</em></p>
                    <p><em>📧 Email: ${escapeHtml(item.contact_email || 'Protected')}</em></p>
                    ${adminActionHtml}
                `;

                if (isAdmin()) {
                    const deleteBtn = itemCard.querySelector('.card-delete-btn');
                    if (deleteBtn) {
                        deleteBtn.addEventListener('click', () => {
                            promptDeleteItem(item.id, item.item_name || item.name || 'Item');
                        });
                    }
                }

                if (item.type === 'lost') {
                    lostItemsContainer.appendChild(itemCard);
                    lostCount++;
                } else {
                    foundItemsContainer.appendChild(itemCard);
                    foundCount++;
                }
            });

            if (lostCount === 0) {
                lostItemsContainer.innerHTML = '<div class="empty-state-card"><p>No lost items currently reported.</p></div>';
            }
            if (foundCount === 0) {
                foundItemsContainer.innerHTML = '<div class="empty-state-card"><p>No found items currently reported.</p></div>';
            }

        } catch (error) {
            console.error('Error fetching items:', error);
            lostItemsContainer.innerHTML = '<div class="item-card"><p style="text-align: center; color: #dc3545;">❌ Could not load lost items. Please try again later.</p></div>';
            foundItemsContainer.innerHTML = '<div class="item-card"><p style="text-align: center; color: #dc3545;">❌ Could not load found items. Please try again later.</p></div>';
        }
    }

    // Function to handle form submission
    itemReportForm.addEventListener('submit', async (event) => {
        event.preventDefault();

        const formData = new FormData(itemReportForm);
        const itemData = Object.fromEntries(formData.entries());

        formMessage.textContent = 'Submitting report...';
        formMessage.style.color = '#475569';

        try {
            const result = await safeFetchJson('/api/items', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(itemData)
            });

            formMessage.textContent = '✅ Item reported successfully! Your report has been saved and indexed for AI search.';
            formMessage.style.color = 'green';
            itemReportForm.reset();
            fetchItems();
            showToast('Item report saved successfully.', 'success');

        } catch (error) {
            console.error('Error submitting report:', error);
            formMessage.textContent = `❌ Error: ${error.message || 'Something went wrong. Please try again.'}`;
            formMessage.style.color = 'red';
            showToast(error.message || 'Error submitting report.', 'error');
        }
    });

    // Initialize Admin UI from existing session
    updateAdminUI();

    // Initial fetch of items when the page loads
    fetchItems();
});