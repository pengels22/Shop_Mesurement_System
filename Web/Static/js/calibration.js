(function () {
    const { apiFetch, showToast } = window.ShopMeasurementSystem;

    const topSelect = document.getElementById('top-camera-select');
    const sideSelect = document.getElementById('side-camera-select');
    const topIndexInput = document.getElementById('top-camera-index');
    const sideIndexInput = document.getElementById('side-camera-index');
    const refreshDevicesButton = document.getElementById('refresh-devices-button');
    const saveCameraButton = document.getElementById('save-camera-button');
    const cameraStatus = document.getElementById('camera-status');
    const topPreview = document.getElementById('top-preview');
    const sidePreview = document.getElementById('side-preview');
    const refreshTopPreview = document.getElementById('refresh-top-preview');
    const refreshSidePreview = document.getElementById('refresh-side-preview');

    const topPpiInput = document.getElementById('top-ppi-input');
    const sidePpiInput = document.getElementById('side-ppi-input');
    const calibrateTopButton = document.getElementById('calibrate-top-button');
    const calibrateSideButton = document.getElementById('calibrate-side-button');
    const calibrationStatus = document.getElementById('calibration-status');

    // Bail out quietly if the calibration page isn't loaded
    if (!topSelect || !sideSelect) {
        return;
    }

    // Five-point calibration state
    const dotImage = document.getElementById('dot-image');
    const dotCanvas = document.getElementById('dot-canvas');
    const dotCaptureButton = document.getElementById('dot-capture-button');
    const dotResetButton = document.getElementById('dot-reset-button');
    const dotSolveButton = document.getElementById('dot-solve-button');
    const dotCameraSelect = document.getElementById('dot-camera-select');
    const dotInstructions = document.getElementById('dot-instructions');
    const dotStatus = document.getElementById('dot-status');

    const DOT_ORDER = ['Top', 'Right', 'Bottom', 'Left', 'Center'];
    const DOT_HINTS = [
        { label: '1', x: 0.5, y: 0.18 }, // Top
        { label: '2', x: 0.82, y: 0.5 }, // Right
        { label: '3', x: 0.5, y: 0.82 }, // Bottom
        { label: '4', x: 0.18, y: 0.5 }, // Left
        { label: '5', x: 0.5, y: 0.5 },  // Center
    ];
    let lastTopValue = topSelect.value || '';
    let lastSideValue = sideSelect.value || '';
    const dotState = {
        camera: 'top',
        frameId: null,
        imageWidth: 0,
        imageHeight: 0,
        points: [],
    };

    function updateDotInstruction() {
        const idx = dotState.points.length;
        if (idx < DOT_ORDER.length) {
            dotInstructions.textContent = `Click ${DOT_ORDER[idx]} point (${idx + 1}/5)`;
        } else {
            dotInstructions.textContent = 'All points captured. Click Solve & Save.';
        }
        dotSolveButton.disabled = dotState.points.length !== 5;
    }

    function resetDotState() {
        dotState.frameId = null;
        dotState.points = [];
        dotState.imageWidth = 0;
        dotState.imageHeight = 0;
        dotImage.src = '';
        const ctx = dotCanvas.getContext('2d');
        ctx.clearRect(0, 0, dotCanvas.width, dotCanvas.height);
        updateDotInstruction();
        dotStatus.textContent = '';
    }

    function resizeCanvasToImage() {
        if (!dotImage.naturalWidth) return;
        dotCanvas.width = dotImage.clientWidth;
        dotCanvas.height = dotImage.clientHeight;
        drawDotCanvas();
    }

    function imageToCanvas(point) {
        return {
            x: point.x * (dotCanvas.width / dotState.imageWidth),
            y: point.y * (dotCanvas.height / dotState.imageHeight),
        };
    }

    function canvasToImage(point) {
        return {
            x: point.x * (dotState.imageWidth / dotCanvas.width),
            y: point.y * (dotState.imageHeight / dotCanvas.height),
        };
    }

    function drawDotCanvas() {
        const ctx = dotCanvas.getContext('2d');
        ctx.clearRect(0, 0, dotCanvas.width, dotCanvas.height);
        // draw hint numbers on the canvas to guide clicking
        if (dotCanvas.width && dotCanvas.height) {
            ctx.save();
            ctx.globalAlpha = 0.28;
            ctx.fillStyle = '#fbbf24';
            ctx.strokeStyle = '#92400e';
            ctx.lineWidth = 1.5;
            ctx.font = 'bold 22px sans-serif';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            DOT_HINTS.forEach((hint) => {
                const hx = hint.x * dotCanvas.width;
                const hy = hint.y * dotCanvas.height;
                ctx.beginPath();
                ctx.arc(hx, hy, 16, 0, Math.PI * 2);
                ctx.fill();
                ctx.stroke();
                ctx.fillStyle = '#111827';
                ctx.fillText(hint.label, hx, hy);
                ctx.fillStyle = '#fbbf24';
            });
            ctx.restore();
        }
        dotState.points.forEach((p, i) => {
            const c = imageToCanvas(p);
            ctx.fillStyle = '#38bdf8';
            ctx.strokeStyle = '#0ea5e9';
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.arc(c.x, c.y, 8, 0, Math.PI * 2);
            ctx.fill();
            ctx.stroke();
            ctx.fillStyle = '#0f172a';
            ctx.font = 'bold 12px sans-serif';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(String(i + 1), c.x, c.y);
        });
    }

    function handleDotClick(event) {
        if (!dotState.frameId) {
            showToast('Capture an image first.', 'error');
            return;
        }
        if (dotState.points.length >= DOT_ORDER.length) {
            return;
        }
        const rect = dotCanvas.getBoundingClientRect();
        const canvasPoint = {
            x: event.clientX - rect.left,
            y: event.clientY - rect.top,
        };
        const imagePoint = canvasToImage(canvasPoint);
        dotState.points.push(imagePoint);
        drawDotCanvas();
        updateDotInstruction();
        dotStatus.textContent = `Captured ${DOT_ORDER[dotState.points.length - 1]} point`;
    }

    async function captureDotFrame() {
        dotState.camera = dotCameraSelect ? dotCameraSelect.value : 'top';
        resetDotState();
        try {
            const payload = await apiFetch(`/api/camera/capture?camera=${dotState.camera}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ camera: dotState.camera }),
            });
            dotState.frameId = payload.image_frame_id;
            dotState.imageWidth = payload.image_width;
            dotState.imageHeight = payload.image_height;
            dotImage.src = `/api/camera/capture/${payload.image_frame_id}?camera=${dotState.camera}&ts=${Date.now()}`;
            dotStatus.textContent = 'Captured frame. Click the five points.';
        } catch (error) {
            showToast(error.message, 'error');
            dotStatus.textContent = error.message;
        }
    }

    async function solveDots() {
        if (dotState.points.length !== 5) {
            showToast('Capture all 5 points first.', 'error');
            return;
        }
        try {
            const payload = await apiFetch('/api/calibration/solve', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ camera: dotState.camera, points: dotState.points }),
            });
            showToast(`Saved calibration for ${dotState.camera}. PPI=${payload.pixels_per_inch.toFixed(3)}`, 'success');
            dotStatus.textContent = 'Calibration saved. You can recapture to verify.';
            loadCalibration();
        } catch (error) {
            showToast(error.message, 'error');
            dotStatus.textContent = error.message;
        }
    }

    function optionMarkup(device, activeTop, activeSide) {
        const activeTag = device.index === activeTop || device.index === activeSide ? ' (active)' : '';
        return `<option value="${device.index}">${device.label}${activeTag}</option>`;
    }

    function syncInputsFromSelects() {
        if (topSelect.value !== '') {
            topIndexInput.value = topSelect.value;
        }
        if (sideSelect.value !== '') {
            sideIndexInput.value = sideSelect.value;
        }
    }

    async function loadDevices() {
        try {
            cameraStatus.textContent = 'Scanning for USB cameras...';
            const payload = await apiFetch('/api/camera/devices');
            const activeTop = (payload.active && payload.active.top) !== undefined ? payload.active.top : undefined;
            const activeSide = (payload.active && payload.active.side) !== undefined ? payload.active.side : undefined;
            const devices = Array.isArray(payload.devices) ? payload.devices : [];

            if (!devices.length && (activeTop !== undefined || activeSide !== undefined)) {
                // Fallback to active config when probing failed (e.g., already in use)
                const fallback = [];
                if (activeTop !== undefined) fallback.push({ index: activeTop, label: `Camera ${activeTop}`, available: true });
                if (activeSide !== undefined && activeSide !== activeTop) fallback.push({ index: activeSide, label: `Camera ${activeSide}`, available: true });
                topSelect.innerHTML = fallback.map((d) => optionMarkup(d, activeTop, activeSide)).join('');
                sideSelect.innerHTML = topSelect.innerHTML;
                if (activeTop !== undefined) topSelect.value = activeTop;
                if (activeSide !== undefined) sideSelect.value = activeSide;
                cameraStatus.textContent = 'Using configured cameras (probe unavailable while streams are open). You can still type indexes below.';
                syncInputsFromSelects();
                return;
            }

            const usable = devices.filter((d) => d.available);
            topSelect.innerHTML = usable.map((d) => optionMarkup(d, activeTop, activeSide)).join('');
            sideSelect.innerHTML = usable.map((d) => optionMarkup(d, activeTop, activeSide)).join('');
            if (activeTop !== undefined) {
                topSelect.value = activeTop;
            }
            if (activeSide !== undefined) {
                sideSelect.value = activeSide;
            }
            cameraStatus.textContent = `Found ${devices.length} camera(s).`;
            syncInputsFromSelects();
            refreshPreviews();
            lastTopValue = topSelect.value;
            lastSideValue = sideSelect.value;
        } catch (error) {
            cameraStatus.textContent = error.message;
            showToast(error.message, 'error');
        }
    }

    async function saveCameraSelection() {
        const topIndex = Number(topIndexInput.value !== '' ? topIndexInput.value : topSelect.value);
        const sideIndex = Number(sideIndexInput.value !== '' ? sideIndexInput.value : sideSelect.value);
        try {
            await apiFetch('/api/camera/profile', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ top_index: topIndex, side_index: sideIndex }),
            });
            showToast('Camera selections saved.', 'success');
            cameraStatus.textContent = `Top -> ${topIndex}, Side -> ${sideIndex}`;
            // keep selects aligned if those indexes exist in options
            if ([...topSelect.options].some((opt) => Number(opt.value) === topIndex)) {
                topSelect.value = String(topIndex);
            }
            if ([...sideSelect.options].some((opt) => Number(opt.value) === sideIndex)) {
                sideSelect.value = String(sideIndex);
            }
            refreshPreviews();
            lastTopValue = topSelect.value;
            lastSideValue = sideSelect.value;
        } catch (error) {
            showToast(error.message, 'error');
            cameraStatus.textContent = error.message;
        }
    }

    async function loadCalibration() {
        try {
            calibrationStatus.textContent = 'Loading calibration values...';
            const payload = await apiFetch('/api/calibration');
            const cal = payload.calibration || {};
            if (topPpiInput && cal.top && cal.top.pixels_per_inch) {
                topPpiInput.value = cal.top.pixels_per_inch;
            }
            if (sidePpiInput && cal.side && cal.side.pixels_per_inch) {
                sidePpiInput.value = cal.side.pixels_per_inch;
            }
            if (calibrationStatus) {
                calibrationStatus.textContent = `Top: ${topPpiInput.value || '—'} PPI, Side: ${sidePpiInput.value || '—'} PPI`;
            }
        } catch (error) {
            if (calibrationStatus) calibrationStatus.textContent = error.message;
            showToast(error.message, 'error');
        }
    }

    async function applyCalibration(camera) {
        const input = camera === 'top' ? topPpiInput : sidePpiInput;
        if (!input) return;
        const ppi = Number(input.value);
        if (!ppi || ppi <= 0) {
            showToast('Enter a valid pixels-per-inch value.', 'error');
            return;
        }
        try {
            await apiFetch('/api/calibration', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ camera, pixels_per_inch: ppi }),
            });
            showToast(`Saved ${camera} calibration.`, 'success');
            calibrationStatus.textContent = `Top: ${topPpiInput.value || '—'} PPI, Side: ${sidePpiInput.value || '—'} PPI`;
        } catch (error) {
            showToast(error.message, 'error');
            calibrationStatus.textContent = error.message;
        }
    }

    if (refreshDevicesButton) refreshDevicesButton.addEventListener('click', loadDevices);
    if (saveCameraButton) saveCameraButton.addEventListener('click', saveCameraSelection);
    topSelect.addEventListener('change', function () {
        const newTop = topSelect.value;
        if (newTop === sideSelect.value && sideSelect.value !== '') {
            sideSelect.value = lastTopValue || '';
        }
        syncInputsFromSelects();
        saveCameraSelection();
        lastTopValue = topSelect.value;
        lastSideValue = sideSelect.value;
    });
    sideSelect.addEventListener('change', function () {
        const newSide = sideSelect.value;
        if (newSide === topSelect.value && topSelect.value !== '') {
            topSelect.value = lastSideValue || '';
        }
        syncInputsFromSelects();
        saveCameraSelection();
        lastTopValue = topSelect.value;
        lastSideValue = sideSelect.value;
    });
    topIndexInput.addEventListener('input', function () {
        const value = topIndexInput.value;
        if (value === '') return;
        for (let i = 0; i < topSelect.options.length; i += 1) {
            if (topSelect.options[i].value === value) {
                topSelect.value = value;
                break;
            }
        }
    });
    sideIndexInput.addEventListener('input', function () {
        const value = sideIndexInput.value;
        if (value === '') return;
        for (let i = 0; i < sideSelect.options.length; i += 1) {
            if (sideSelect.options[i].value === value) {
                sideSelect.value = value;
                break;
            }
        }
    });
    if (calibrateTopButton) calibrateTopButton.addEventListener('click', function () { applyCalibration('top'); });
    if (calibrateSideButton) calibrateSideButton.addEventListener('click', function () { applyCalibration('side'); });

    function setLivePreview(imgEl, cameraId) {
        if (!imgEl || !cameraId) return;
        const ts = Date.now();
        // Bust cache and restart stream; cameraId is logical ('top' or 'side')
        imgEl.src = `/api/camera/stream?camera=${cameraId}&ts=${ts}`;
    }

    function refreshPreviews() {
        setLivePreview(topPreview, 'top');
        setLivePreview(sidePreview, 'side');
    }

    if (refreshTopPreview) refreshTopPreview.addEventListener('click', refreshPreviews);
    if (refreshSidePreview) refreshSidePreview.addEventListener('click', refreshPreviews);

    [topPreview, sidePreview].forEach(function (imgEl) {
        if (!imgEl) return;
        imgEl.addEventListener('error', function () {
            imgEl.alt = 'Preview not available (camera busy or index invalid)';
        });
    });

    // Five-point calibration hooks
    if (dotCanvas) {
        dotCanvas.addEventListener('click', handleDotClick);
    }
    if (dotCaptureButton) dotCaptureButton.addEventListener('click', captureDotFrame);
    if (dotResetButton) dotResetButton.addEventListener('click', resetDotState);
    if (dotSolveButton) dotSolveButton.addEventListener('click', solveDots);
    if (dotImage) {
        dotImage.addEventListener('load', resizeCanvasToImage);
    }
    window.addEventListener('resize', resizeCanvasToImage);

    // Initial load
    loadDevices();
    loadCalibration();
    resetDotState();
})();
