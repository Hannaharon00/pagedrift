def construct_tag_routes(rss_blueprint, datastore):
    """
    Construct RSS feed routes for tags.

    Args:
        rss_blueprint: The Flask blueprint to add routes to
        datastore: The ChangeDetectionStore instance
    """

    @rss_blueprint.route("/tag/<uuid_str:tag_uuid>", methods=['GET'])
    def rss_tag_feed(tag_uuid):

        from flask import make_response, request, url_for
        from feedgen.feed import FeedGenerator

        from . import RSS_TEMPLATE_HTML_DEFAULT, RSS_TEMPLATE_PLAINTEXT_DEFAULT
        from ._util import (validate_rss_token, generate_watch_guid, get_rss_template,
                           get_watch_label, build_notification_context, render_notification,
                           populate_feed_entry, add_watch_categories)
        from ...notification_service import NotificationService

        """
        Display an RSS feed for all unviewed watches that belong to a specific tag.
        Returns RSS XML with entries for each unviewed watch with sufficient history.
        """
        # Validate token
        is_valid, error = validate_rss_token(datastore, request)
        if not is_valid:
            return error

        rss_content_format = datastore.data['settings']['application'].get('rss_content_format')

        # Verify tag exists
        tag = datastore.data['settings']['application'].get('tags', {}).get(tag_uuid)
        if not tag:
            return f"Tag with UUID {tag_uuid} not found", 404

        tag_title = tag.get('title', 'Unknown Tag')

        # Create RSS feed
        fg = FeedGenerator()
        fg.title(f'changedetection.io - {tag_title}')
        fg.description(f'Changes for watches tagged with {tag_title}')
        fg.link(href='https://changedetection.io')
        notification_service = NotificationService(datastore=datastore, notification_q=False)
        # Find all watches with this tag
        for uuid, watch in datastore.data['watching'].items():
            #@todo  This is wrong, it needs to sort by most recently changed and then limit it  datastore.data['watching'].items().sorted(?)
            # So get all watches in this tag then sort

            # Skip if watch doesn't have this tag
            if tag_uuid not in watch.get('tags', []):
                continue

