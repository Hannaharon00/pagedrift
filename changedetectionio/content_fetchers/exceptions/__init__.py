from loguru import logger

class Non200ErrorCodeReceived(Exception):
    def __init__(self, status_code, url, screenshot=None, xpath_data=None, page_html=None):
        # Set this so we can use it in other parts of the app
        self.status_code = status_code
        self.url = url
        self.screenshot = screenshot
        self.xpath_data = xpath_data
        self.page_text = None

        if page_html:
            from changedetectionio import html_tools
            self.page_text = html_tools.html_to_text(page_html)
        return


class checksumFromPreviousCheckWasTheSame(Exception):
    def __init__(self):
        return


class JSActionExceptions(Exception):
    def __init__(self, status_code, url, screenshot, message=''):
        self.status_code = status_code
        self.url = url
        self.screenshot = screenshot
        self.message = message
        return

class BrowserConnectError(Exception):
    msg = ''
    def __init__(self, msg):
        self.msg = msg
        logger.error(f"Browser connection error {msg}")
        return

class BrowserFetchTimedOut(Exception):
    msg = ''
    def __init__(self, msg):
        self.msg = msg
        logger.error(f"Browser processing took too long - {msg}")
        return

