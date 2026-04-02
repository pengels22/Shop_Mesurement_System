(function () {
    const { apiFetch, showToast } = window.ShopMeasurementSystem;

    const partsGrid = document.getElementById('parts-grid');
    const refreshButton = document.getElementById('refresh-parts-button');
    const modal = document.getElementById('image-modal');
    const modalImage = document.getElementById('modal-image');
    const modalName = document.getElementById('modal-part-name');
    const modalMeasurementList = document.getElementById('modal-measurement-list');
    const closeModalButton = document.getElementById('close-modal-button');

    function measurementMarkup(measurement) {
        return `
            <div class="measurement-row">
                <span class="measurement-swatch" style="background:${measurement.color || '#475569'}"></span>
                <div><span class="measurement-label">${measurement.label}</span> <span class="measurement-value">${Number(measurement.value_in).toFixed(4)}</span></div>
            </div>
        `;
    }

    function partCardMarkup(part) {
        const measurements = part.measurements.map((measurement) => `
            <div class="measurement-row">
                <span class="measurement-swatch" style="background:${measurement.color || '#475569'}"></span>
                <div><span class="measurement-label">${measurement.label}</span> <span class="measurement-value">${Number(measurement.value_in).toFixed(4)}</span></div>
            </div>
        `).join('');
        const thumbMarkup = part.measurement_type === 'complex'
            ? `<img class="part-thumb" data-image="${part.image_filename}" src="/api/parts/image/${part.image_filename}" alt="${part.part_name}">`
            : '';
        return `
            <div class="part-card" data-part-name="${part.part_name}">
                <div class="card-header-row small-gap">
                    <strong>${part.part_name}</strong>
                    <button class="danger-button delete-part-button" type="button">Remove</button>
                </div>
                ${thumbMarkup}
                <div class="measurement-list">${measurements}</div>
            </div>
        `;
    }

    function openModal(part) {
        modalName.textContent = part.part_name;
        modalImage.src = `/api/parts/image/${part.image_filename}`;
        modalMeasurementList.innerHTML = part.measurements.map(measurementMarkup).join('');
        modal.classList.remove('hidden');
    }

    function closeModal() {
        modal.classList.add('hidden');
        modalImage.src = '';
        modalMeasurementList.innerHTML = '';
    }

    async function renderParts() {
        try {
            const payload = await apiFetch('/api/projects/active/parts');
            if (!payload.parts.length) {
                partsGrid.innerHTML = '<div class="empty-state">No parts are saved in the active project.</div>';
                return;
            }
            partsGrid.innerHTML = payload.parts.map(partCardMarkup).join('');
            partsGrid.querySelectorAll('.delete-part-button').forEach((button) => {
                button.addEventListener('click', async (event) => {
                    const card = event.currentTarget.closest('.part-card');
                    const partName = card.dataset.partName;
                    const shouldDelete = window.confirm(`Delete ${partName}?`);
                    if (!shouldDelete) {
                        return;
                    }
                    await apiFetch('/api/parts/delete', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ part_name: partName }),
                    });
                    showToast(`Deleted ${partName}`, 'success');
                    await renderParts();
                });
            });
            partsGrid.querySelectorAll('.part-thumb').forEach((thumb) => {
                thumb.addEventListener('click', async (event) => {
                    const card = event.currentTarget.closest('.part-card');
                    const payload = await apiFetch('/api/projects/active/parts');
                    const part = payload.parts.find((entry) => entry.part_name === card.dataset.partName);
                    if (part) {
                        openModal(part);
                    }
                });
            });
        } catch (error) {
            partsGrid.innerHTML = `<div class="empty-state">${error.message}</div>`;
            showToast(error.message, 'error');
        }
    }

    refreshButton.addEventListener('click', renderParts);
    closeModalButton.addEventListener('click', closeModal);
    modal.addEventListener('click', (event) => {
        if (event.target === modal) {
            closeModal();
        }
    });

    renderParts();
})();
