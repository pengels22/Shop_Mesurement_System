(function () {
    const { apiFetch, normalizeSpaces, showToast } = window.ShopMeasurementSystem;

    const COLOR_CSS = {
        red: '#dc2626',
        blue: '#2563eb',
        green: '#16a34a',
        yellow: '#ca8a04',
        purple: '#9333ea',
        orange: '#ea580c',
        cyan: '#0891b2',
        magenta: '#db2777',
        lime: '#65a30d',
        pink: '#ec4899',
    };
    const EXTRA_COLOR_NAMES = ['yellow', 'purple', 'orange', 'cyan', 'magenta', 'lime', 'pink'];
    const HANDLE_RADIUS = 8;
    const DELETE_ICON_SIZE = 18;
    const LINE_HIT_TOLERANCE = 12;

    const state = {
        activeProject: null,
        liveView: true,
        frameId: null,
        frameWidth: 0,
        frameHeight: 0,
        drawingMode: null,
        interactionLock: null,
        isPointerDown: false,
        dragThresholdPassed: false,
        dragStartCanvas: null,
        dragCurrentCanvas: null,
        pendingStartCanvas: null,
        measurements: [],
        selectedLabel: null,
        activeDragTarget: null,
        clickStartCanvas: null,
    };

    const cameraImage = document.getElementById('camera-image');
    const canvas = document.getElementById('measurement-canvas');
    const stage = canvas.parentElement;
    const context = canvas.getContext('2d');
    const MASK = {
        enabled: true,
        // Fractions of canvas width/height for the clear window.
        x0: 0.25,
        x1: 0.85,
        y0: 0.08,
        y1: 0.78,
        color: 'rgba(255, 68, 0, 0.75)', // vivid red/orange
    };
    const projectNameChip = document.getElementById('measurement-project-name');
    const partNameInput = document.getElementById('part-name-input');
    const modeSelect = document.getElementById('measurement-mode-select');
    const measurementList = document.getElementById('measurement-list');
    const statusBox = document.getElementById('measurement-status');
    const captureButton = document.getElementById('capture-button');
    const resumeLiveButton = document.getElementById('resume-live-button');
    const addXButton = document.getElementById('add-x-button');
    const addYButton = document.getElementById('add-y-button');
    const addZButton = document.getElementById('add-z-button');
    const addMButton = document.getElementById('add-m-button');
    const horizontalLockButton = document.getElementById('horizontal-lock-button');
    const verticalLockButton = document.getElementById('vertical-lock-button');
    const clearAllButton = document.getElementById('clear-all-button');
    const savePartButton = document.getElementById('save-part-button');

    function colorForName(name) {
        return COLOR_CSS[name] || '#475569';
    }

    function nextExtraColor(index) {
        return EXTRA_COLOR_NAMES[index % EXTRA_COLOR_NAMES.length];
    }

    function setStatus(message) {
        statusBox.textContent = message;
    }

    function updateCanvasSize() {
        const rect = cameraImage.getBoundingClientRect();
        canvas.width = Math.max(1, Math.round(rect.width));
        canvas.height = Math.max(1, Math.round(rect.height));
        drawCanvas();
    }

    function toCanvasPoint(event) {
        const rect = canvas.getBoundingClientRect();
        return {
            x: event.clientX - rect.left,
            y: event.clientY - rect.top,
        };
    }

    function toImagePoint(canvasPoint) {
        return {
            x: (canvasPoint.x / canvas.width) * state.frameWidth,
            y: (canvasPoint.y / canvas.height) * state.frameHeight,
        };
    }

    function toCanvasFromImage(imagePoint) {
        return {
            x: (imagePoint.x / state.frameWidth) * canvas.width,
            y: (imagePoint.y / state.frameHeight) * canvas.height,
        };
    }

    function distance(a, b) {
        return Math.hypot(a.x - b.x, a.y - b.y);
    }

    function distanceToSegment(point, start, end) {
        const dx = end.x - start.x;
        const dy = end.y - start.y;
        if (dx === 0 && dy === 0) {
            return distance(point, start);
        }
        const t = Math.max(0, Math.min(1, ((point.x - start.x) * dx + (point.y - start.y) * dy) / (dx * dx + dy * dy)));
        const projection = { x: start.x + t * dx, y: start.y + t * dy };
        return distance(point, projection);
    }

    function applyLock(start, current) {
        if (state.interactionLock === 'horizontal') {
            return { x: current.x, y: start.y };
        }
        if (state.interactionLock === 'vertical') {
            return { x: start.x, y: current.y };
        }
        return current;
    }

    function makeMeasurementTemplate(label) {
        const colorName = label === 'X' ? 'red' : label === 'Y' ? 'blue' : label === 'Z' ? 'green' : nextExtraColor(extraMeasurementCount());
        return {
            label,
            color: colorName,
            start_px: { x: 0, y: 0 },
            end_px: { x: 0, y: 0 },
            value_in: 0,
        };
    }

    function extraMeasurementCount() {
        return state.measurements.filter((measurement) => /^M\d+$/.test(measurement.label)).length;
    }

    function computeValueIn(measurement) {
        const dx = measurement.end_px.x - measurement.start_px.x;
        const dy = measurement.end_px.y - measurement.start_px.y;
        const pixelLength = Math.hypot(dx, dy);
        return pixelLength / 32.9;
    }

    function ensureUniqueAxis(label) {
        if (!['X', 'Y', 'Z'].includes(label)) {
            return;
        }
        state.measurements = state.measurements.filter((measurement) => measurement.label !== label);
    }

    function renumberExtras() {
        const fixed = [];
        const extras = [];
        for (const measurement of state.measurements) {
            if (['X', 'Y', 'Z'].includes(measurement.label)) {
                fixed.push(measurement);
            } else {
                extras.push(measurement);
            }
        }
        extras.forEach((measurement, index) => {
            measurement.label = `M${index + 1}`;
            measurement.color = nextExtraColor(index);
        });
        fixed.sort((a, b) => ['X', 'Y', 'Z'].indexOf(a.label) - ['X', 'Y', 'Z'].indexOf(b.label));
        state.measurements = [...fixed, ...extras];
    }

    function refreshMeasurementValues() {
        state.measurements.forEach((measurement) => {
            measurement.value_in = computeValueIn(measurement);
        });
    }

    function updateMeasurementList() {
        if (!state.measurements.length) {
            measurementList.innerHTML = '<div class="empty-state">No measurements added yet.</div>';
            return;
        }
        measurementList.innerHTML = state.measurements.map((measurement) => `
            <div class="measurement-row ${measurement.label === state.selectedLabel ? 'active' : ''}" data-label="${measurement.label}">
                <span class="measurement-swatch" style="background:${colorForName(measurement.color)}"></span>
                <div><span class="measurement-label" style="color:${colorForName(measurement.color)}">${measurement.label}</span> <span class="measurement-value">${measurement.value_in.toFixed(4)}</span></div>
                <button type="button" data-delete-label="${measurement.label}">Delete</button>
            </div>
        `).join('');

        measurementList.querySelectorAll('.measurement-row').forEach((row) => {
            row.addEventListener('click', (event) => {
                if (event.target instanceof HTMLButtonElement) {
                    return;
                }
                state.selectedLabel = row.dataset.label;
                updateMeasurementList();
                drawCanvas();
            });
        });
        measurementList.querySelectorAll('button[data-delete-label]').forEach((button) => {
            button.addEventListener('click', () => {
                deleteMeasurement(button.dataset.deleteLabel);
            });
        });
    }

    function drawDeleteIcon(anchor) {
        const x = anchor.x + 18;
        const y = anchor.y - 18;
        context.fillStyle = '#ffffff';
        context.strokeStyle = '#991b1b';
        context.lineWidth = 2;
        context.beginPath();
        context.roundRect(x - 8, y - 8, 16, 16, 4);
        context.fill();
        context.stroke();
        context.strokeStyle = '#991b1b';
        context.beginPath();
        context.moveTo(x - 4, y - 2);
        context.lineTo(x + 4, y - 2);
        context.moveTo(x - 3, y - 1);
        context.lineTo(x - 2, y + 4);
        context.moveTo(x, y - 1);
        context.lineTo(x, y + 4);
        context.moveTo(x + 3, y - 1);
        context.lineTo(x + 2, y + 4);
        context.moveTo(x - 5, y - 5);
        context.lineTo(x + 5, y - 5);
        context.stroke();
        return { x, y, size: DELETE_ICON_SIZE };
    }

    function drawCanvas() {
        context.clearRect(0, 0, canvas.width, canvas.height);

        if (MASK.enabled) {
            context.save();
            context.fillStyle = MASK.color;
            context.fillRect(0, 0, canvas.width, canvas.height);
            const x0 = MASK.x0 * canvas.width;
            const y0 = MASK.y0 * canvas.height;
            const w = (MASK.x1 - MASK.x0) * canvas.width;
            const h = (MASK.y1 - MASK.y0) * canvas.height;
            context.clearRect(x0, y0, w, h);
            context.restore();
        }

        state.measurements.forEach((measurement) => {
            const start = toCanvasFromImage(measurement.start_px);
            const end = toCanvasFromImage(measurement.end_px);
            context.strokeStyle = colorForName(measurement.color);
            context.lineWidth = measurement.label === state.selectedLabel ? 4 : 3;
            context.beginPath();
            context.moveTo(start.x, start.y);
            context.lineTo(end.x, end.y);
            context.stroke();
        });

        if (state.pendingStartCanvas && state.dragCurrentCanvas) {
            context.strokeStyle = '#ffffff';
            context.lineWidth = 2;
            context.setLineDash([8, 6]);
            context.beginPath();
            context.moveTo(state.pendingStartCanvas.x, state.pendingStartCanvas.y);
            context.lineTo(state.dragCurrentCanvas.x, state.dragCurrentCanvas.y);
            context.stroke();
            context.setLineDash([]);
        }

        const selected = state.measurements.find((measurement) => measurement.label === state.selectedLabel);
        if (selected) {
            const start = toCanvasFromImage(selected.start_px);
            const end = toCanvasFromImage(selected.end_px);
            context.fillStyle = '#ffffff';
            context.strokeStyle = colorForName(selected.color);
            context.lineWidth = 3;
            [start, end].forEach((point) => {
                context.beginPath();
                context.arc(point.x, point.y, HANDLE_RADIUS, 0, Math.PI * 2);
                context.fill();
                context.stroke();
            });
            state.deleteIconHitbox = drawDeleteIcon(end);
        } else {
            state.deleteIconHitbox = null;
        }
    }

    function deleteMeasurement(label) {
        state.measurements = state.measurements.filter((measurement) => measurement.label !== label);
        renumberExtras();
        refreshMeasurementValues();
        if (state.selectedLabel === label) {
            state.selectedLabel = null;
        }
        updateMeasurementList();
        drawCanvas();
    }

    function handleMeasurementCreation(startCanvas, endCanvas) {
        const lockedEnd = applyLock(startCanvas, endCanvas);
        const startImage = toImagePoint(startCanvas);
        const endImage = toImagePoint(lockedEnd);
        const pixelLength = Math.hypot(endImage.x - startImage.x, endImage.y - startImage.y);
        const minPixels = (1 / 25.4) * 100.0;
        if (pixelLength < minPixels) {
            showToast('Measurement must be at least 1 mm', 'error');
            setStatus('Measurement rejected because it is shorter than 1 mm.');
            return;
        }
        const template = makeMeasurementTemplate(state.drawingMode);
        template.start_px = startImage;
        template.end_px = endImage;
        template.value_in = computeValueIn(template);
        ensureUniqueAxis(template.label);
        state.measurements.push(template);
        renumberExtras();
        refreshMeasurementValues();
        state.selectedLabel = template.label;
        updateMeasurementList();
        drawCanvas();
        setStatus(`${template.label} measurement added.`);
    }

    function selectLineAt(point) {
        for (let index = state.measurements.length - 1; index >= 0; index -= 1) {
            const measurement = state.measurements[index];
            const start = toCanvasFromImage(measurement.start_px);
            const end = toCanvasFromImage(measurement.end_px);
            if (distanceToSegment(point, start, end) <= LINE_HIT_TOLERANCE) {
                state.selectedLabel = measurement.label;
                updateMeasurementList();
                drawCanvas();
                return true;
            }
        }
        return false;
    }

    function findHandleTarget(point) {
        const selected = state.measurements.find((measurement) => measurement.label === state.selectedLabel);
        if (!selected) {
            return null;
        }
        const start = toCanvasFromImage(selected.start_px);
        const end = toCanvasFromImage(selected.end_px);
        if (distance(point, start) <= HANDLE_RADIUS + 4) {
            return 'start';
        }
        if (distance(point, end) <= HANDLE_RADIUS + 4) {
            return 'end';
        }
        if (state.deleteIconHitbox) {
            const box = state.deleteIconHitbox;
            if (Math.abs(point.x - box.x) <= box.size && Math.abs(point.y - box.y) <= box.size) {
                return 'delete';
            }
        }
        return null;
    }

    function onPointerDown(event) {
        if (state.liveView || !state.frameId) {
            return;
        }
        const point = toCanvasPoint(event);
        const handleTarget = findHandleTarget(point);
        if (handleTarget === 'delete') {
            deleteMeasurement(state.selectedLabel);
            return;
        }
        if (handleTarget === 'start' || handleTarget === 'end') {
            state.activeDragTarget = handleTarget;
            state.isPointerDown = true;
            return;
        }
        if (selectLineAt(point)) {
            state.isPointerDown = false;
            return;
        }
        if (!state.drawingMode) {
            state.selectedLabel = null;
            updateMeasurementList();
            drawCanvas();
            return;
        }
        state.isPointerDown = true;
        state.dragThresholdPassed = false;
        state.dragStartCanvas = point;
        state.pendingStartCanvas = point;
        state.dragCurrentCanvas = point;
    }

    function onPointerMove(event) {
        if (state.liveView || !state.frameId) {
            return;
        }
        const point = toCanvasPoint(event);
        if (!state.isPointerDown && state.clickStartCanvas && state.drawingMode) {
            state.pendingStartCanvas = state.clickStartCanvas;
            state.dragCurrentCanvas = applyLock(state.clickStartCanvas, point);
            drawCanvas();
        }
        if (state.activeDragTarget && state.selectedLabel) {
            const measurement = state.measurements.find((entry) => entry.label === state.selectedLabel);
            if (!measurement) {
                return;
            }
            const adjustedPoint = applyLock(state.activeDragTarget === 'start' ? toCanvasFromImage(measurement.end_px) : toCanvasFromImage(measurement.start_px), point);
            if (state.activeDragTarget === 'start') {
                measurement.start_px = toImagePoint(adjustedPoint);
            } else {
                measurement.end_px = toImagePoint(adjustedPoint);
            }
            refreshMeasurementValues();
            updateMeasurementList();
            drawCanvas();
            return;
        }
        if (!state.isPointerDown || !state.pendingStartCanvas) {
            return;
        }
        state.dragCurrentCanvas = applyLock(state.pendingStartCanvas, point);
        if (distance(state.pendingStartCanvas, point) > 4) {
            state.dragThresholdPassed = true;
        }
        drawCanvas();
    }

    function onPointerUp(event) {
        if (state.activeDragTarget) {
            state.activeDragTarget = null;
            setStatus('Measurement updated.');
            return;
        }
        if (!state.isPointerDown || !state.pendingStartCanvas || !state.drawingMode) {
            state.isPointerDown = false;
            return;
        }
        const point = toCanvasPoint(event);
        if (state.dragThresholdPassed) {
            handleMeasurementCreation(state.pendingStartCanvas, point);
            state.pendingStartCanvas = null;
            state.dragCurrentCanvas = null;
            state.isPointerDown = false;
            state.dragThresholdPassed = false;
            return;
        }
        if (!state.clickStartCanvas) {
            state.clickStartCanvas = state.pendingStartCanvas;
            state.pendingStartCanvas = state.clickStartCanvas;
            state.dragCurrentCanvas = point;
            state.isPointerDown = false;
            setStatus('Start point set. Click the end point to finish the measurement.');
            drawCanvas();
            return;
        }
        handleMeasurementCreation(state.clickStartCanvas, point);
        state.clickStartCanvas = null;
        state.pendingStartCanvas = null;
        state.dragCurrentCanvas = null;
        state.isPointerDown = false;
        state.dragThresholdPassed = false;
    }

    function armMeasurement(label) {
        if (state.liveView) {
            showToast('Capture a frame before adding measurements', 'error');
            return;
        }
        state.drawingMode = label;
        state.clickStartCanvas = null;
        state.pendingStartCanvas = null;
        state.dragCurrentCanvas = null;
        setStatus(`Adding ${label}. Use click-click or click-drag.`);
    }

    async function captureFrame() {
        try {
            const payload = await apiFetch('/api/camera/capture', { method: 'POST' });
            state.frameId = payload.image_frame_id;
            state.frameWidth = payload.image_width;
            state.frameHeight = payload.image_height;
            state.liveView = false;
            cameraImage.src = `/api/camera/capture/${payload.image_frame_id}`;
            setStatus(`Captured ${payload.image_frame_id}`);
        } catch (error) {
            showToast(error.message, 'error');
            setStatus(error.message);
        }
    }

    function resumeLiveView() {
        state.liveView = true;
        state.frameId = null;
        state.measurements = [];
        state.selectedLabel = null;
        state.drawingMode = null;
        state.pendingStartCanvas = null;
        state.clickStartCanvas = null;
        cameraImage.src = `/api/camera/stream?ts=${Date.now()}`;
        updateMeasurementList();
        drawCanvas();
        setStatus('Returned to live view.');
    }

    async function savePart() {
        const partName = normalizeSpaces(partNameInput.value || '');
        if (!state.activeProject) {
            showToast('No active project is loaded', 'error');
            return;
        }
        if (!partName) {
            showToast('Part name is required', 'error');
            return;
        }
        if (!state.frameId) {
            showToast('Capture a frame before saving', 'error');
            return;
        }
        if (!state.measurements.length) {
            showToast('Add at least one measurement before saving', 'error');
            return;
        }

        const payload = {
            project_name: state.activeProject.project_name,
            part_name: partName,
            overwrite: false,
            image_frame_id: state.frameId,
            image_width: state.frameWidth,
            image_height: state.frameHeight,
            measurement_type: modeSelect.value,
            measurements: state.measurements.map((measurement) => ({
                label: measurement.label,
                color: measurement.color,
                start_px: measurement.start_px,
                end_px: measurement.end_px,
            })),
        };

        try {
            const result = await apiFetch('/api/parts/save', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            showToast(`Saved ${result.part_name}`, 'success');
            setStatus(`Saved ${result.part_name}`);
        } catch (error) {
            if (error.message.includes('already exists')) {
                const shouldOverwrite = window.confirm(`${partName} already exists. Overwrite it?`);
                if (!shouldOverwrite) {
                    setStatus('Save cancelled so the part can be renamed.');
                    return;
                }
                payload.overwrite = true;
                try {
                    const overwriteResult = await apiFetch('/api/parts/save', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(payload),
                    });
                    showToast(`Overwrote ${overwriteResult.part_name}`, 'success');
                    setStatus(`Overwrote ${overwriteResult.part_name}`);
                } catch (overwriteError) {
                    showToast(overwriteError.message, 'error');
                    setStatus(overwriteError.message);
                }
                return;
            }
            showToast(error.message, 'error');
            setStatus(error.message);
        }
    }

    async function loadProject() {
        try {
            const payload = await apiFetch('/api/projects/active');
            state.activeProject = payload.project;
            projectNameChip.textContent = payload.project.project_name;
        } catch (error) {
            projectNameChip.textContent = 'No_Active_Project';
            showToast(error.message, 'error');
        }
    }

    function clearAllMeasurements() {
        state.measurements = [];
        state.selectedLabel = null;
        state.drawingMode = null;
        state.clickStartCanvas = null;
        state.pendingStartCanvas = null;
        state.dragCurrentCanvas = null;
        updateMeasurementList();
        drawCanvas();
        setStatus('Cleared all measurements.');
    }

    function setLock(mode) {
        state.interactionLock = state.interactionLock === mode ? null : mode;
        horizontalLockButton.textContent = state.interactionLock === 'horizontal' ? 'Horizontal Lock On' : 'Horizontal Lock';
        verticalLockButton.textContent = state.interactionLock === 'vertical' ? 'Vertical Lock On' : 'Vertical Lock';
    }

    cameraImage.addEventListener('load', updateCanvasSize);
    window.addEventListener('resize', updateCanvasSize);
    canvas.addEventListener('pointerdown', onPointerDown);
    canvas.addEventListener('pointermove', onPointerMove);
    canvas.addEventListener('pointerup', onPointerUp);
    canvas.addEventListener('pointerleave', onPointerUp);

    captureButton.addEventListener('click', captureFrame);
    resumeLiveButton.addEventListener('click', resumeLiveView);
    addXButton.addEventListener('click', () => armMeasurement('X'));
    addYButton.addEventListener('click', () => armMeasurement('Y'));
    addZButton.addEventListener('click', () => armMeasurement('Z'));
    addMButton.addEventListener('click', () => armMeasurement(`M${extraMeasurementCount() + 1}`));
    horizontalLockButton.addEventListener('click', () => setLock('horizontal'));
    verticalLockButton.addEventListener('click', () => setLock('vertical'));
    clearAllButton.addEventListener('click', clearAllMeasurements);
    savePartButton.addEventListener('click', savePart);
    partNameInput.addEventListener('input', () => {
        partNameInput.value = normalizeSpaces(partNameInput.value);
    });

    updateMeasurementList();
    loadProject();
function cancelPendingMeasurementPoint() {
    if (!state.clickStartCanvas && !state.pendingStartCanvas) {
        return;
    }

    state.clickStartCanvas = null;
    state.pendingStartCanvas = null;
    state.dragCurrentCanvas = null;
    state.isPointerDown = false;
    state.dragThresholdPassed = false;

    drawCanvas();
    setStatus('Start point cleared. Click to begin again.');
}
function onKeyDown(event) {
    if (event.key === 'Escape') {
        if (state.clickStartCanvas || state.pendingStartCanvas) {
            event.preventDefault();
            cancelPendingMeasurementPoint();
        }
    }
}
window.addEventListener('keydown', onKeyDown);
})();
