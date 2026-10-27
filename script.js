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
            const response = await fetch('/api/ai/search', {
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

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.message || `Server responded with status ${response.status}`);
            }

            // 1. Check OpenAI API Key status
            if (!data.api_key_configured) {
                aiSetupNotice.classList.remove('hidden');
            } else if (data.llm_response) {
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
            aiErrorText.textContent = error.message || 'An error occurred while connecting to the AI search service.';
            aiErrorNotice.classList.remove('hidden');
        } finally {
            aiLoading.classList.add('hidden');
            aiSearchBtn.disabled = false;
        }
    }

    function createResultCard(item) {
        const card = document.createElement('div');
        card.classList.add('item-card');

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
        `;
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
            const response = await fetch('/api/items');
            const items = await response.json();

            lostItemsContainer.innerHTML = '';
            foundItemsContainer.innerHTML = '';

            items.forEach(item => {
                const itemCard = document.createElement('div');
                itemCard.classList.add('item-card');
                const dateStr = item.reported_at ? new Date(item.reported_at).toLocaleDateString() : 'Not specified';

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
                `;

                if (item.type === 'lost') {
                    lostItemsContainer.appendChild(itemCard);
                } else {
                    foundItemsContainer.appendChild(itemCard);
                }
            });
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

        try {
            const response = await fetch('/api/items', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(itemData)
            });

            const result = await response.json();

            if (response.ok) {
                formMessage.textContent = '✅ Item reported successfully! Your report has been saved and indexed for AI search.';
                formMessage.style.color = 'green';
                itemReportForm.reset();
                fetchItems();
            } else {
                formMessage.textContent = `❌ Error: ${result.message || 'Something went wrong. Please try again.'}`;
                formMessage.style.color = 'red';
            }
        } catch (error) {
            console.error('Error submitting report:', error);
            formMessage.textContent = '🌐 Network error. Please check your connection and try again.';
            formMessage.style.color = 'red';
        }
    });

    // Initial fetch of items when the page loads
    fetchItems();
});