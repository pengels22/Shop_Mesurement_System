(function () {
    const { apiFetch, loadActiveProject, showToast } = window.ShopMeasurementSystem;

    const activeProjectSummary = document.getElementById('active-project-summary');
    const projectList = document.getElementById('project-list');
    const continueButton = document.getElementById('continue-project-button');
    const refreshButton = document.getElementById('refresh-projects-button');

    function projectCardMarkup(project, isActive) {
        return `
            <div class="project-card ${isActive ? 'active' : ''}" data-project-name="${project.project_name}">
                <div><strong>${project.project_name}</strong></div>
                <div class="muted">${project.project_description || 'No_description'}</div>
                <div class="muted">Directory: ${project.project_directory}</div>
                <div class="toolbar-row compact-row">
                    <button class="primary-button activate-project-button" type="button">${isActive ? 'Active' : 'Activate'}</button>
                    <a class="secondary-button" href="/measurement">Open Measurement</a>
                </div>
            </div>
        `;
    }

    function renderActiveProject(project) {
        if (!activeProjectSummary) {
            return;
        }
        if (!project) {
            activeProjectSummary.innerHTML = '<div>No active project is set.</div>';
            continueButton.disabled = true;
            return;
        }
        continueButton.disabled = false;
        activeProjectSummary.innerHTML = `
            <div><strong>${project.project_name}</strong></div>
            <div class="muted">${project.project_description || 'No_description'}</div>
            <div class="muted">Save_Location: ${project.default_save_location}</div>
            <div class="muted">CSV: ${project.csv_filename}</div>
        `;
    }

    async function renderProjects() {
        const projectPayload = await apiFetch('/api/projects');
        const activeProject = projectPayload.active_project;
        renderActiveProject(activeProject);
        if (!projectList) {
            return;
        }
        if (!projectPayload.projects.length) {
            projectList.innerHTML = '<div class="empty-state">No projects found yet.</div>';
            return;
        }
        projectList.innerHTML = projectPayload.projects
            .map((project) => projectCardMarkup(project, activeProject && activeProject.project_name === project.project_name))
            .join('');

        projectList.querySelectorAll('.activate-project-button').forEach((button) => {
            button.addEventListener('click', async (event) => {
                const card = event.currentTarget.closest('.project-card');
                if (!card) {
                    return;
                }
                const projectName = card.dataset.projectName;
                await apiFetch('/api/projects/activate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ project_name: projectName }),
                });
                showToast(`Activated ${projectName}`, 'success');
                await loadActiveProject();
                await renderProjects();
            });
        });
    }

    if (continueButton) {
        continueButton.addEventListener('click', () => {
            window.location.href = '/measurement';
        });
    }

    if (refreshButton) {
        refreshButton.addEventListener('click', async () => {
            await renderProjects();
            showToast('Project list refreshed', 'success');
        });
    }

    renderProjects().catch((error) => {
        showToast(error.message, 'error');
    });
})();
