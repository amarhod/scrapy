import logging

from twisted.internet import task

from scrapy.exceptions import NotConfigured
from scrapy import signals

logger = logging.getLogger(__name__)


class LogStats:
    """Log basic scraping stats periodically"""

    def __init__(self, stats, interval=60.0):
        self.stats = stats
        self.interval = interval
        self.multiplier = 60.0 / self.interval
        self.task = None

    @classmethod
    def from_crawler(cls, crawler):
        interval = crawler.settings.getfloat('LOGSTATS_INTERVAL')
        if not interval:
            raise NotConfigured
        o = cls(crawler.stats, interval)
        crawler.signals.connect(o.spider_opened, signal=signals.spider_opened)
        crawler.signals.connect(o.spider_closed, signal=signals.spider_closed)
        return o

    def spider_opened(self, spider):
        self.pagesprev = 0
        self.itemsprev = 0
        self.response_bytesprev = 0.0
        self.task = task.LoopingCall(self.log, spider)
        self.task.start(self.interval)

    def log(self, spider):
        items = self.stats.get_value('item_scraped_count', 0)
        pages = self.stats.get_value('response_received_count', 0)
        response_bytes = self.stats.get_value('downloader/response_bytes', 0) / float(1000)
        irate = (items - self.itemsprev) * self.multiplier
        prate = (pages - self.pagesprev) * self.multiplier
        brate = (response_bytes - self.response_bytesprev)
        self.pagesprev, self.itemsprev, self.response_bytesprev = pages, items, response_bytes
        msg = ("Crawled %(pages)d pages (at %(pagerate)d pages/min), "
               "scraped %(items)d items (at %(itemrate)d items/min)")
        if self.stats.get_value('downloader/response_bytes') is not None:
            msg = msg + ", received %(response_bytes)d KB of response bytes (at %(brate)d KB/s)"
        log_args = {'pages': pages, 'pagerate': prate,
                    'items': items, 'itemrate': irate,
                    'response_bytes': response_bytes, 'brate': brate}
        logger.info(msg, log_args, extra={'spider': spider})

    def spider_closed(self, spider, reason):
        if self.task and self.task.running:
            self.task.stop()
