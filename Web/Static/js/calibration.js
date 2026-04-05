(function () {
    const { apiFetch, showToast } = window.ShopMeasurementSystem;

    const topSelect = document.getElementById('top-camera-select');
    const sideSelect = document.getElementById('side-camera-select');
    const refreshDevicesButton = document.getElementById('refresh-devices-button');
    const saveCameraButton = document.getElementById('save-camera-button');
    const cameraStatus = document.getElementById('camera-status');

    const topPpiInput = document.getElementById('top-ppi-input');
    const sidePpiInput = document.getElementById('side-ppi-input');
    const calibrateTopButton = document.getElementById('calibrate-top-button');
    const calibrateSideButton = document.getElementById('calibrate-side-button');
    const calibrationStatus = document.getElementById('calibration-status');

    function optionMarkup(device) {
        return `<option value="${device.index}">${device.label}</option>`;
    }

    async function loadDevices() {
        try {
            cameraStatus.textContent = 'Scanning for USB cameras...';
            const payload = await apiFetch('/api/camera/devices');
            if (!payload.devices.length) {
                cameraStatus.textContent = 'No cameras detected. Plug in a USB camera and refresh.';
                topSelect.innerHTML = '';
                sideSelect.innerHTML = '';
                return;
            }
            topSelect.innerHTML = payload.devices.map(optionMarkup).join('');
            sideSelect.innerHTML = payload.devices.map(optionMarkup).join('');
            if (payload.active?.top !== undefined) {
                topSelect.value = payload.active.top;
            }
            if (payload.active?.side !== undefined) {
                sideSelect.value = payload.active.side;
            }
            cameraStatus.textContent = `Found ${payload.devices.length} camera(s).`;
        } catch (error) {
            cameraStatus.textContent = error.message;
            showToast(error.message, 'error');
        }
    }

    async function saveCameraSelection() {
        const topIndex = Number(topSelect.value);
        const sideIndex = Number(sideSelect.value);
        try {
            await apiFetch('/api/camera/profile', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ top_index: topIndex, side_index: sideIndex }),
            });
            showToast('Camera selections saved.', 'success');
            cameraStatus.textContent = `Top → ${topIndex}, Side → ${sideIndex}`;
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
    calibrateTopButton.addEventListener('click', () => applyCalibration('top'));
    calibrateSideButton.addEventListener('click', () => applyCalibration('side'));

    // Initial load
    loadDevices();
    loadCalibration();
})();
