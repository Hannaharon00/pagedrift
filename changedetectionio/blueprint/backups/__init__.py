import datetime
import glob
import threading

BACKUP_FILENAME_FORMAT = "changedetection-backup-{}.zip"


def create_backup(datastore_path, watches: dict, tags: dict = None):
    logger.debug("Creating backup...")
    import zipfile
    from pathlib import Path

    # create a ZipFile object
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    backupname = BACKUP_FILENAME_FORMAT.format(timestamp)
    backup_filepath = os.path.join(datastore_path, backupname)

    with zipfile.ZipFile(backup_filepath.replace('.zip', '.tmp'), "w",
                         compression=zipfile.ZIP_DEFLATED,
                         compresslevel=8) as zipObj:

        # Add the settings file (supports both formats)
        # New format: changedetection.json
        changedetection_json = os.path.join(datastore_path, "changedetection.json")
        if os.path.isfile(changedetection_json):
            zipObj.write(changedetection_json, arcname="changedetection.json")
            logger.debug("Added changedetection.json to backup")

        # Legacy format: url-watches.json (for backward compatibility)
        url_watches_json = os.path.join(datastore_path, "url-watches.json")
        if os.path.isfile(url_watches_json):
            zipObj.write(url_watches_json, arcname="url-watches.json")
            logger.debug("Added url-watches.json to backup")

        # Add tag data directories (each tag has its own {uuid}/tag.json)
        for uuid, tag in (tags or {}).items():
            for f in Path(tag.data_dir).glob('*'):
                zipObj.write(f,
                             arcname=os.path.join(f.parts[-2], f.parts[-1]),
                             compress_type=zipfile.ZIP_DEFLATED,
                             compresslevel=8)
            logger.debug(f"Added tag '{tag.get('title')}' ({uuid}) to backup")

        # Add any data in the watch data directory.
        for uuid, w in watches.items():
            for f in Path(w.data_dir).glob('*'):
                zipObj.write(f,
                             # Use the full path to access the file, but make the file 'relative' in the Zip.
                             arcname=os.path.join(f.parts[-2], f.parts[-1]),
                             compress_type=zipfile.ZIP_DEFLATED,
                             compresslevel=8)

        # Create a list file with just the URLs, so it's easier to port somewhere else in the future
        list_file = "url-list.txt"
        with open(os.path.join(datastore_path, list_file), "w", encoding="utf-8") as f:
            for uuid in watches:
                url = watches[uuid]["url"]
                f.write("{}\r\n".format(url))
        list_with_tags_file = "url-list-with-tags.txt"
        with open(
                os.path.join(datastore_path, list_with_tags_file), "w", encoding="utf-8"
        ) as f:
            for uuid in watches:
                url = watches[uuid].get('url')
                tag = watches[uuid].get('tags', {})
                f.write("{} {}\r\n".format(url, tag))

        # Add it to the Zip
        zipObj.write(
            os.path.join(datastore_path, list_file),
            arcname=list_file,
            compress_type=zipfile.ZIP_DEFLATED,
            compresslevel=8,
        )
        zipObj.write(
            os.path.join(datastore_path, list_with_tags_file),
            arcname=list_with_tags_file,
            compress_type=zipfile.ZIP_DEFLATED,
            compresslevel=8,
        )

    # Now it's done, rename it so it shows up finally and its completed being written.
    os.rename(backup_filepath.replace('.zip', '.tmp'), backup_filepath.replace('.tmp', '.zip'))


