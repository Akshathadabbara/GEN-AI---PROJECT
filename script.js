document.addEventListener('DOMContentLoaded', () => {
    const lostItemsContainer = document.getElementById('lost-items-container');
    const foundItemsContainer = document.getElementById('found-items-container');
    const itemReportForm = document.getElementById('item-report-form');
    const formMessage = document.getElementById('form-message');

    // Function to fetch and display items
    async function fetchItems() {
        try {
            const response = await fetch('/api/items');
            const items = await response.json();

            lostItemsContainer.innerHTML = ''; // Clear previous items
            foundItemsContainer.innerHTML = ''; // Clear previous items

            items.forEach(item => {
                const itemCard = document.createElement('div');
                itemCard.classList.add('item-card');
                itemCard.innerHTML = `
                    <h3>${item.item_name || item.name || 'Unknown Item'}</h3>
                    <p><strong>Type:</strong> ${item.type === 'lost' ? '📱 Lost Item' : '🔍 Found Item'}</p>
                    <p><strong>Description:</strong> ${item.description || 'No description provided'}</p>
                    <p><strong>Location:</strong> ${item.location || 'Not specified'}</p>
                    <p><strong>Student:</strong> ${item.student_name || 'Unknown Student'}</p>
                    <p><strong>Registration No:</strong> ${item.registration_number || 'Not provided'}</p>
                    <p><strong>Department:</strong> ${item.department || 'Not specified'}</p>
                    <p><strong>Year:</strong> ${item.year_of_study || 'Not specified'}</p>
                    <p><strong>Reported:</strong> ${new Date(item.reported_at).toLocaleDateString()}</p>
                    <p><em>📞 Contact: ${item.contact_number || 'Not provided'}</em></p>
                    <p><em>📧 Email: ${item.contact_email || 'Not provided'}</em></p>
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
        event.preventDefault(); // Prevent default form submission

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
                formMessage.textContent = '✅ Item reported successfully! Your report has been submitted.';
                formMessage.style.color = 'green';
                itemReportForm.reset(); // Clear the form
                fetchItems(); // Refresh the item list
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