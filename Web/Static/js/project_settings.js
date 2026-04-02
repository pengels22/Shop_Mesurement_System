(function () {
    const { apiFetch, normalizeSpaces, showToast } = window.ShopMeasurementSystem;

    const form = document.getElementById('project-form');
    const statusBox = document.getElementById('project-settings-status');
    const loadButton = document.getElementById('load-active-project-button');
    const projectNameInput = document.getElementById('project_name');
    const projectDirectoryInput = document.getElementById('project_directory');
    const defaultSaveLocationInput = document.getElementById('default_save_location');

    function setStatus(message) {
        if (statusBox) {
            statusBox.textContent = message;
        }
    }

    function syncDerivedFields() {
        const normalizedName = normalizeSpaces(projectNameInput.value || '');
        if (!normalizedName) {
            return;
        }
        if (!projectDirectoryInput.dataset.userEdited) {
            projectDirectoryInput.value = normalizedName;
        }
        if (!defaultSaveLocationInput.dataset.userEdited) {
            defaultSaveLocationInput.value = 'parts';
        }
    }

    async function populateFromProject(project) {
        projectNameInput.value = project.project_name || '';
        projectDirectoryInput.value = project.project_directory ? project.project_directory.split('/').pop() : '';
        projectDirectoryInput.dataset.userEdited = 'true';
        document.getElementById('project_description').value = project.project_description || '';
        defaultSaveLocationInput.value = project.default_save_location ? project.default_save_location.split('/').pop() : 'parts';
        defaultSaveLocationInput.dataset.userEdited = 'true';
        document.getElementById('notes').value = project.notes || '';
        document.getElementById('csv_filename').value = project.csv_filename || 'measurements.csv';
        setStatus(`Loaded active project ${project.project_name}`);
    }

    [projectDirectoryInput, defaultSaveLocationInput].forEach((input) => {
        input.addEventListener('input', () => {
            input.dataset.userEdited = 'true';
        });
    });

    projectNameInput.addEventListener('input', syncDerivedFields);

    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        const formData = new FormData(form);
        const payload = {};
        for (const [key, value] of formData.entries()) {
            payload[key] = normalizeSpaces(String(value));
        }
        try {
            const result = await apiFetch('/api/projects', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            setStatus(`Saved project ${result.project.project_name}`);
            showToast(`Saved ${result.project.project_name}`, 'success');
        } catch (error) {
            setStatus(error.message);
            showToast(error.message, 'error');
        }
    });

    loadButton.addEventListener('click', async () => {
        try {
            const payload = await apiFetch('/api/projects/active');
            await populateFromProject(payload.project);
            showToast('Loaded active project', 'success');
        } catch (error) {
            setStatus(error.message);
            showToast(error.message, 'error');
        }
    });
})();
