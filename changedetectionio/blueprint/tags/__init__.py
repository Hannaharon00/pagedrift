import threading
from flask import Blueprint, request, render_template, flash, url_for, redirect
from flask_babel import gettext
from loguru import logger

from changedetectionio.blueprint.tags.colour import safe_css_colour
from changedetectionio.store import ChangeDetectionStore
from changedetectionio.flask_app import login_optionally_required
from changedetectionio.llm.evaluator import get_llm_config as _get_llm_config


def construct_blueprint(datastore: ChangeDetectionStore):
    tags_blueprint = Blueprint('tags', __name__, template_folder="templates")

    # Used by any template that writes a tag colour into a <style> block
    tags_blueprint.add_app_template_filter(safe_css_colour, 'safe_css_colour')

    @tags_blueprint.route("/list", methods=['GET'])
    @login_optionally_required
    def tags_overview_page():
        from .form import SingleTag
        add_form = SingleTag(request.form)

        sorted_tags = sorted(datastore.data['settings']['application'].get('tags').items(), key=lambda x: x[1]['title'])

        from collections import Counter

        tag_count = Counter(tag for watch in datastore.data['watching'].values() if watch.get('tags') for tag in watch['tags'])

        from changedetectionio import processors
        output = render_template("groups-overview.html",
                                 app_rss_token=datastore.data['settings']['application'].get('rss_access_token'),
                                 available_tags=sorted_tags,
                                 form=add_form,
                                 generate_tag_colors=processors.generate_processor_badge_colors,
                                 tag_count=tag_count,
                                 wcag_text_color=processors.wcag_text_color,
                                 )

        return output

    @tags_blueprint.route("/add", methods=['POST'])
    @login_optionally_required
    def form_tag_add():
        from .form import SingleTag
        add_form = SingleTag(request.form)

        if not add_form.validate():
            for widget, l in add_form.errors.items():
                flash(','.join(l), 'error')
            return redirect(url_for('tags.tags_overview_page'))

        title = request.form.get('name').strip()

        if datastore.tag_exists_by_name(title):
            flash(gettext('The tag "{}" already exists').format(title), "error")
            return redirect(url_for('tags.tags_overview_page'))

