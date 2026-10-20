BOT_NAME = "feiyiw"
SPIDER_MODULES = ["feiyiw.spiders"]
NEWSPIDER_MODULE = "feiyiw.spiders"
ROBOTSTXT_OBEY = True
ITEM_PIPELINES = {
    "crawler_collection.pipelines.CollectionPipeline": 100,
}
