"""
Base data extraction module for all processors.

This module handles extracting data from watch history using regex patterns
and exporting to CSV format. This is the default extractor that all processors
(text_json_diff, restock_diff, etc.) can use by default or override.
"""

def process_extraction(watch, datastore, request, url_for, make_response, send_from_directory, flash, redirect, extract_form=None):
    """
    Process the data extraction request and return CSV file.

    Args:
        watch: The watch object
        datastore: The ChangeDetectionStore instance
        request: Flask request object
        url_for: Flask url_for function
        make_response: Flask make_response function
        send_from_directory: Flask send_from_directory function
        flash: Flask flash function
        redirect: Flask redirect function
        extract_form: Optional pre-built extract form

    Returns:
        CSV file download response or redirect to form on error
    """
    from changedetectionio import forms

    uuid = watch.get('uuid')

    # Use provided form or create a new one
    if extract_form is None:
        extract_form = forms.extractDataForm(
            formdata=request.form,
            data={'extract_regex': request.form.get('extract_regex', '')}
        )

    if not extract_form.validate():
        flash(gettext("An error occurred, please see below."), "error")
        # render_template needs to be imported from Flask for this to work
        from flask import render_template as flask_render_template
        return render_form(
            watch=watch,
            datastore=datastore,
            request=request,
            url_for=url_for,
            render_template=flask_render_template,
            flash=flash,
            redirect=redirect,
            extract_form=extract_form
        )

    extract_regex = request.form.get('extract_regex', '').strip()
    output = watch.extract_regex_from_all_history(extract_regex)

    if output:
        watch_dir = os.path.join(datastore.datastore_path, uuid)
        response = make_response(send_from_directory(directory=watch_dir, path=output, as_attachment=True))
        response.headers['Content-type'] = 'text/csv'
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = "0"
        return response

    flash(gettext('No matches found while scanning all of the watch history for that RegEx.'), 'error')
    return redirect(url_for('ui.ui_diff.diff_history_page_extract_GET', uuid=uuid))
