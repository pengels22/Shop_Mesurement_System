from __future__ import annotations

from flask import Blueprint, render_template

page_blueprint = Blueprint('pages', __name__)


@page_blueprint.get('/')
def home_page():
    return render_template('index.html')


@page_blueprint.get('/project-settings')
def project_settings_page():
    return render_template('project_settings.html')


@page_blueprint.get('/measurement')
def measurement_page():
    return render_template('measurement.html')


@page_blueprint.get('/parts-browser')
def parts_browser_page():
    return render_template('parts_browser.html')


@page_blueprint.get('/calibration')
def calibration_page():
    return render_template('calibration.html')
