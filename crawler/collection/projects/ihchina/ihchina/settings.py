BOT_NAME = "ihchina"
SPIDER_MODULES = ["ihchina.spiders"]
NEWSPIDER_MODULE = "ihchina.spiders"
ROBOTSTXT_OBEY = True
ITEM_PIPELINES = {
    "crawler_collection.pipelines.CollectionPipeline": 100,
}
