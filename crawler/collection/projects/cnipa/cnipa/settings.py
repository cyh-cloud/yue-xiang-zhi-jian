BOT_NAME = "cnipa"
SPIDER_MODULES = ["cnipa.spiders"]
NEWSPIDER_MODULE = "cnipa.spiders"
ROBOTSTXT_OBEY = True
ITEM_PIPELINES = {
    "crawler_collection.pipelines.CollectionPipeline": 100,
}
