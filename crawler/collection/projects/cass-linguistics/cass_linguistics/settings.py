BOT_NAME = "cass-linguistics"
SPIDER_MODULES = ["cass_linguistics.spiders"]
NEWSPIDER_MODULE = "cass_linguistics.spiders"
ROBOTSTXT_OBEY = True
ITEM_PIPELINES = {
    "crawler_collection.pipelines.CollectionPipeline": 100,
}
