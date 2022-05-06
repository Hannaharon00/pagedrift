from abc import abstractmethod
import time
from wtforms import ValidationError
from loguru import logger
from flask_babel import gettext

from changedetectionio.forms import validate_url


class Importer():
    remaining_data = []
    new_uuids = []
    good = 0

    def __init__(self):
        self.new_uuids = []
        self.good = 0
        self.remaining_data = []
        self.import_profile = None
        self.limit_reported = False

    @abstractmethod
    def run(self,
            data,
            flash,
            datastore):
        pass

    def watch_limit_hit(self, datastore, flash):
        """True once PAGE_WATCH_LIMIT leaves no room - the caller must then stop importing.

        Asked before each add_watch() so the limit is reported once for the whole file.
        add_watch() would otherwise flash the same error again for every remaining row.
        """
        if not datastore.watch_limit_reached():
            return False

        if not self.limit_reported:
            self.limit_reported = True
            flash(datastore.watch_limit_message(), 'error')

        return True


class import_url_list(Importer):
    """
    Imports a list, can be in <code>https://example.com tag1, tag2, last tag</code> format
    """
    def run(self,
            data,
            flash,
            datastore,
            processor=None
            ):

        urls = data.split("\n")
        good = 0
        now = time.time()

        if (len(urls) > 5000):
            flash(gettext("Importing 5,000 of the first URLs from your list, the rest can be imported again."))

        for idx, url in enumerate(urls):
            url = url.strip()
            if not len(url):
                continue

            tags = ""

            # 'tags' should be a csv list after the URL
            if ' ' in url:
                url, tags = url.split(" ", 1)

            # Flask wtform validators wont work with basic auth, use validators package
            # Up to 5000 per batch so we dont flood the server
            # @todo validators.url will fail when you add your own IP etc
            if len(url) and 'http' in url.lower() and good < 5000:
                if self.watch_limit_hit(datastore, flash):
                    # Hand back every line we didn't get to (originals, tags included) so they
                    # land in the textarea to retry once there's room
                    self.remaining_data.extend(u.strip() for u in urls[idx:] if u.strip())
                    break

                extras = None
                if processor:
                    extras = {'processor': processor}
                new_uuid = datastore.add_watch(url=url.strip(), tag=tags, save_immediately=False, extras=extras)

                if new_uuid:
                    # Straight into the queue.
                    self.new_uuids.append(new_uuid)
                    good += 1
                    continue

            # Worked past the 'continue' above, append it to the bad list
            if self.remaining_data is None:
                self.remaining_data = []
            self.remaining_data.append(url)

        flash(gettext("{count} Imported from list in {duration}s, {skipped_count} Skipped.").format(count=good, duration=f"{time.time() - now:.2f}", skipped_count=len(self.remaining_data)))


class import_distill_io_json(Importer):
    def run(self,
            data,
            flash,
            datastore,
            ):

        import json
        good = 0
        now = time.time()
        self.new_uuids=[]

        # @todo Use JSONSchema like in the API to validate here.
        
        try:
            data = json.loads(data.strip())
        except json.decoder.JSONDecodeError:
            flash(gettext("Unable to read JSON file, was it broken?"), 'error')
            return

        if not data.get('data'):
            flash(gettext("JSON structure looks invalid, was it broken?"), 'error')
            return

        for d in data.get('data'):
            d_config = json.loads(d['config'])
            extras = {'title': d.get('name', None)}

            if len(d['uri']) and good < 5000:
                if self.watch_limit_hit(datastore, flash):
                    break

                try:
                    # @todo we only support CSS ones at the moment
                    if d_config['selections'][0]['frames'][0]['excludes'][0]['type'] == 'css':
                        extras['subtractive_selectors'] = d_config['selections'][0]['frames'][0]['excludes'][0]['expr']
                except KeyError:
                    pass
                except IndexError:
                    pass
                extras['include_filters'] = []
                try:
                    if d_config['selections'][0]['frames'][0]['includes'][0]['type'] == 'xpath':
                        extras['include_filters'].append('xpath:' + d_config['selections'][0]['frames'][0]['includes'][0]['expr'])
                    else:
                        extras['include_filters'].append(d_config['selections'][0]['frames'][0]['includes'][0]['expr'])
                except KeyError:
                    pass
                except IndexError:
                    pass

                new_uuid = datastore.add_watch(url=d['uri'].strip(),
                                               tag=",".join(d.get('tags', [])),
                                               extras=extras,
                                               save_immediately=False)

                if new_uuid:
                    # Straight into the queue.
                    self.new_uuids.append(new_uuid)
                    good += 1

        flash(gettext("{count} Imported from Distill.io in {duration}s, {skipped_count} Skipped.").format(count=len(self.new_uuids), duration=f"{time.time() - now:.2f}", skipped_count=len(self.remaining_data)))


