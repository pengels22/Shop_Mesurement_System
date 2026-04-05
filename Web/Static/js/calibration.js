(function () {
    const { apiFetch, showToast } = window.ShopMeasurementSystem;

    const topSelect = document.getElementById('top-camera-select');
    const sideSelect = document.getElementById('side-camera-select');
    const topIndexInput = document.getElementById('top-camera-index');
    const sideIndexInput = document.getElementById('side-camera-index');
    const refreshDevicesButton = document.getElementById('refresh-devices-button');
    const saveCameraButton = document.getElementById('save-camera-button');
    const cameraStatus = document.getElementById('camera-status');

    const topPpiInput = document.getElementById('top-ppi-input');
    const sidePpiInput = document.getElementById('side-ppi-input');
    const calibrateTopButton = document.getElementById('calibrate-top-button');
    const calibrateSideButton = document.getElementById('calibrate-side-button');
    const calibrationStatus = document.getElementById('calibration-status');

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
            const activeTop = payload.active?.top;
            const activeSide = payload.active?.side;
            const devices = payload.devices || [];

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
            if (cal.top?.pixels_per_inch) {
                topPpiInput.value = cal.top.pixels_per_inch;
            }
            if (cal.side?.pixels_per_inch) {
                sidePpiInput.value = cal.side.pixels_per_inch;
            }
            calibrationStatus.textContent = `Top: ${topPpiInput.value || '—'} PPI, Side: ${sidePpiInput.value || '—'} PPI`;
        } catch (error) {
            calibrationStatus.textContent = error.message;
            showToast(error.message, 'error');
        }
    }

    async function applyCalibration(camera) {
        const input = camera === 'top' ? topPpiInput : sidePpiInput;
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

    refreshDevicesButton.addEventListener('click', loadDevices);
    saveCameraButton.addEventListener('click', saveCameraSelection);
    topSelect.addEventListener('change', syncInputsFromSelects);
    sideSelect.addEventListener('change', syncInputsFromSelects);
    topIndexInput.addEventListener('input', () => {
        const value = topIndexInput.value;
        if (value === '') return;
        const opt = [...topSelect.options].find((o) => o.value === value);
        if (opt) topSelect.value = value;
    });
    sideIndexInput.addEventListener('input', () => {
        const value = sideIndexInput.value;
        if (value === '') return;
        const opt = [...sideSelect.options].find((o) => o.value === value);
        if (opt) sideSelect.value = value;
    });
    calibrateTopButton.addEventListener('click', () => applyCalibration('top'));
    calibrateSideButton.addEventListener('click', () => applyCalibration('side'));

    // Initial load
    loadDevices();
    loadCalibration();
})();
