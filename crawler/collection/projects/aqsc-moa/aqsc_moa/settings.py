BOT_NAME = "aqsc-moa"
SPIDER_MODULES = ["aqsc_moa.spiders"]
NEWSPIDER_MODULE = "aqsc_moa.spiders"
ROBOTSTXT_OBEY = True
ITEM_PIPELINES = {
    "crawler_collection.pipelines.CollectionPipeline": 100,
}
