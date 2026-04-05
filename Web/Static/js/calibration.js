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

    function optionMarkup(device, activeTop, activeSide) {
        const suffix = device.available ? '' : ' (in use/unavailable)';
        const activeTag = device.index === activeTop || device.index === activeSide ? ' (active)' : '';
        return `<option value="${device.index}">${device.label}${activeTag}${suffix}</option>`;
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

            topSelect.innerHTML = devices.map((d) => optionMarkup(d, activeTop, activeSide)).join('');
            sideSelect.innerHTML = devices.map((d) => optionMarkup(d, activeTop, activeSide)).join('');
            if (activeTop !== undefined) {
                topSelect.value = activeTop;
            }
            if (activeSide !== undefined) {
                sideSelect.value = activeSide;
            }
            cameraStatus.textContent = `Found ${devices.length} camera(s).`;
            syncInputsFromSelects();
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
    topSelect.addEventListener('change', syncInputsFromSelects);
    sideSelect.addEventListener('change', syncInputsFromSelects);
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

    function setPreview(imgEl, index) {
        if (!imgEl || index === undefined || index === null || index === '') {
            return;
        }
        const ts = Date.now();
        imgEl.src = `/api/camera/preview?index=${index}&ts=${ts}`;
    }

    function refreshPreviews() {
        const topIndex = topIndexInput.value !== '' ? topIndexInput.value : topSelect.value;
        const sideIndex = sideIndexInput.value !== '' ? sideIndexInput.value : sideSelect.value;
        setPreview(topPreview, topIndex);
        setPreview(sidePreview, sideIndex);
    }

    if (refreshTopPreview) refreshTopPreview.addEventListener('click', refreshPreviews);
    if (refreshSidePreview) refreshSidePreview.addEventListener('click', refreshPreviews);

    [topPreview, sidePreview].forEach(function (imgEl) {
        if (!imgEl) return;
        imgEl.addEventListener('error', function () {
            imgEl.alt = 'Preview not available (camera busy or index invalid)';
        });
    });

    // Initial load
    loadDevices();
    loadCalibration();
})();
