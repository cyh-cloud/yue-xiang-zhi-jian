BOT_NAME = "dialect-org"
SPIDER_MODULES = ["dialect_org.spiders"]
NEWSPIDER_MODULE = "dialect_org.spiders"
ROBOTSTXT_OBEY = True
ITEM_PIPELINES = {
    "crawler_collection.pipelines.CollectionPipeline": 100,
}
