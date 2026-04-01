function normalizeSpaces(value) {
    return value.trim().replace(/\s+/g, '_');
}

document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('project-form');
    if (!form) {
        return;
    }

    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        const formData = new FormData(form);
        const payload = {};

        for (const [key, value] of formData.entries()) {
            payload[key] = normalizeSpaces(String(value));
        }

        const response = await fetch('/api/projects', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload),
        });

        const result = await response.json();
        if (result.ok) {
            alert('Project saved');
        } else {
            alert(result.message || 'Save failed');
        }
    });
});
