BOT_NAME = "nongmuhr"
SPIDER_MODULES = ["nongmuhr.spiders"]
NEWSPIDER_MODULE = "nongmuhr.spiders"
ROBOTSTXT_OBEY = True
ITEM_PIPELINES = {
    "crawler_collection.pipelines.CollectionPipeline": 100,
}
