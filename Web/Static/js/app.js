(function () {
    const toastContainer = document.getElementById('toast-container');

    function normalizeSpaces(value) {
        return String(value || '').trim().replace(/\s+/g, '_');
    }

    function sanitizeForFile(value) {
        return normalizeSpaces(value)
            .toLowerCase()
            .replace(/[^a-z0-9_]/g, '')
            .replace(/_+/g, '_')
            .replace(/^_+|_+$/g, '');
    }

    async function apiFetch(url, options = {}) {
        const response = await fetch(url, options);
        const contentType = response.headers.get('content-type') || '';
        const payload = contentType.includes('application/json') ? await response.json() : await response.text();
        if (!response.ok) {
            const message = payload && payload.message ? payload.message : `Request failed (${response.status})`;
            throw new Error(message);
        }
        return payload;
    }

    function showToast(message, type = 'info', timeoutMs = 3200) {
        if (!toastContainer) {
            return;
        }
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.textContent = message;
        toastContainer.appendChild(toast);
        window.setTimeout(() => {
            toast.remove();
        }, timeoutMs);
    }

    function setGlobalProjectChip(projectName) {
        const chip = document.getElementById('global-project-chip');
        if (chip) {
            chip.textContent = projectName || 'No_Active_Project';
        }
    }

    async function loadActiveProject() {
        try {
            const payload = await apiFetch('/api/projects/active');
            setGlobalProjectChip(payload.project.project_name);
            return payload.project;
        } catch (error) {
            setGlobalProjectChip('No_Active_Project');
            return null;
        }
    }

    document.addEventListener('input', (event) => {
        const target = event.target;
        if (!(target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement)) {
            return;
        }
        if (!target.dataset.normalizeSpaces) {
            target.value = normalizeSpaces(target.value);
        }
    });

    window.ShopMeasurementSystem = {
        apiFetch,
        loadActiveProject,
        normalizeSpaces,
        sanitizeForFile,
        setGlobalProjectChip,
        showToast,
    };

    loadActiveProject();
})();
