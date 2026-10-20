BOT_NAME = "nzrc"
SPIDER_MODULES = ["nzrc.spiders"]
NEWSPIDER_MODULE = "nzrc.spiders"
ROBOTSTXT_OBEY = True
ITEM_PIPELINES = {
    "crawler_collection.pipelines.CollectionPipeline": 100,
}
