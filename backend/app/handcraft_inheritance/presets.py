from __future__ import annotations

from copy import deepcopy
from threading import RLock

from app.handcraft_inheritance.providers import (
    EmptyCraftPresetProvider,
    EmptyRewardCatalogProvider,
    EmptyTeachingVideoProvider,
    UnavailablePointsPolicyProvider,
)


PLACEHOLDER_CRAFTS = (
    {
        "craft_key": "guangxiu",
        "name": "广绣",
        "sort_order": 1,
        "introduction": (
            "广绣发源于广州及珠江三角洲地区，明清时期随岭南商贸发展而兴盛；"
            "其技术特征以针法细密、构图饱满、色彩明快和丝线光泽感鲜明为主。"
        ),
        "is_demo": True,
        "source_available": True,
        "steps": (
            {
                "step_key": "guangxiu-01",
                "step_no": 1,
                "title": "材料与绣线准备",
                "description": "确认绣布、绣线、绣针和绷架齐全，并按色系整理绣线。",
                "tips": ("先按图案色稿分组，再逐组准备绣线。",),
            },
            {
                "step_key": "guangxiu-02",
                "step_no": 2,
                "title": "描稿与绷架",
                "description": "将纹样准确描到绣布上，并将绣布平直绷紧。",
                "tips": ("绣布经纬线保持垂直，避免图案变形。",),
            },
            {
                "step_key": "guangxiu-03",
                "step_no": 3,
                "title": "起针与基础针法",
                "description": "练习起针、收针和基础平针，保持针脚均匀。",
                "tips": ("先用余布试针，确认线张力后再绣主图。",),
            },
            {
                "step_key": "guangxiu-04",
                "step_no": 4,
                "title": "花瓣层次绣制",
                "description": "按由浅到深的顺序绣制花瓣，建立清晰的层次关系。",
                "tips": ("每次换色先压住前一色线尾。",),
            },
            {
                "step_key": "guangxiu-05",
                "step_no": 5,
                "title": "枝叶与过渡色",
                "description": "补充枝叶，并用过渡色处理主体与背景的衔接。",
                "tips": ("过渡区域缩短针距，减少色块边界感。",),
            },
            {
                "step_key": "guangxiu-06",
                "step_no": 6,
                "title": "收针、整理与装裱",
                "description": "完成背面收线，熨烫整理并选择适合的装裱方式。",
                "tips": ("熨烫前确认绣线耐热范围。",),
            },
        ),
        "material_guide": (
            {
                "name": "真丝绣线",
                "reference_price": "20-40 元/束",
                "purchase_channel": "广州绣品市场或正规电商店铺",
                "precautions": "按色系分批采购，避免不同批次出现明显色差。",
                "taobao_keyword": "广绣真丝绣线",
            },
            {
                "name": "细密棉麻绣布",
                "reference_price": "15-35 元/米",
                "purchase_channel": "布艺市场或手工材料店",
                "precautions": "选择纹理紧密、经纬线清晰的浅色底布。",
                "taobao_keyword": "广绣绣布底料",
            },
            {
                "name": "绣绷与绣针套装",
                "reference_price": "25-60 元/套",
                "purchase_channel": "手工材料店或电商平台",
                "precautions": "检查绣绷边缘是否光滑，防止勾线。",
                "taobao_keyword": "广绣绣绷绣针",
            },
        ),
    },
    {
        "craft_key": "chaoshan-woodcarving",
        "name": "潮汕木雕",
        "sort_order": 2,
        "introduction": (
            "潮汕木雕发源于广东潮汕地区，唐宋以后吸收中原木作与闽南工艺脉络；"
            "其技术特征以多层镂通、构图饱满、刀法层次分明和装饰题材细密为主。"
        ),
        "is_demo": True,
        "source_available": True,
        "steps": (
            {
                "step_key": "chaoshan-woodcarving-01",
                "step_no": 1,
                "title": "木料选择与放样",
                "description": "选择纹理稳定的木料，并根据尺寸放大图样。",
                "tips": ("先检查木料裂纹和结疤位置。",),
            },
            {
                "step_key": "chaoshan-woodcarving-02",
                "step_no": 2,
                "title": "粗坯轮廓",
                "description": "沿图样外轮廓去除多余木料，建立主体体块。",
                "tips": ("顺木纹下刀，先用大刃建立大形。",),
            },
            {
                "step_key": "chaoshan-woodcarving-03",
                "step_no": 3,
                "title": "层次分区",
                "description": "根据前后景关系划分雕刻深度和层次。",
                "tips": ("每一层都预留后续修整空间。",),
            },
            {
                "step_key": "chaoshan-woodcarving-04",
                "step_no": 4,
                "title": "细部雕修",
                "description": "刻出叶片、衣纹或建筑构件等细节。",
                "tips": ("小刃修细部时保持手腕稳定。",),
            },
            {
                "step_key": "chaoshan-woodcarving-05",
                "step_no": 5,
                "title": "打磨与清理",
                "description": "由粗到细打磨表面，清理刀痕和木屑。",
                "tips": ("边角处减轻力度，避免磨圆结构。",),
            },
            {
                "step_key": "chaoshan-woodcarving-06",
                "step_no": 6,
                "title": "上油与养护",
                "description": "按木料状态薄涂木蜡油并完成日常养护说明。",
                "tips": ("上油后充分晾干，避免立即密封包装。",),
            },
        ),
        "material_guide": (
            {
                "name": "干燥樟木料",
                "reference_price": "30-80 元/块",
                "purchase_channel": "木工材料市场或木材商",
                "precautions": "选择干燥、无明显裂纹和虫蛀的木料。",
                "taobao_keyword": "潮汕木雕樟木料",
            },
            {
                "name": "木雕刀组",
                "reference_price": "80-200 元/套",
                "purchase_channel": "专业木工工具店",
                "precautions": "刀具必须保持锋利，操作时刀口朝外。",
                "taobao_keyword": "木雕刀套装",
            },
            {
                "name": "木蜡油",
                "reference_price": "35-90 元/瓶",
                "purchase_channel": "木器养护店或电商平台",
                "precautions": "在通风处薄涂，并遵守产品干燥时间。",
                "taobao_keyword": "木雕木蜡油",
            },
        ),
    },
    {
        "craft_key": "shiwan-ceramics",
        "name": "石湾陶艺",
        "sort_order": 3,
        "introduction": (
            "石湾陶艺源于佛山石湾，明清时期形成鲜明的民窑传统；"
            "其技术特征以陶塑造型朴拙生动、胎釉浑厚和人物动物题材见长。"
        ),
        "is_demo": True,
        "source_available": True,
        "steps": (
            {
                "step_key": "shiwan-ceramics-01",
                "step_no": 1,
                "title": "陶泥揉练",
                "description": "通过反复揉练排除泥料中的气泡，使湿度均匀。",
                "tips": ("采用菊花揉法，避免泥团内部夹气。",),
            },
            {
                "step_key": "shiwan-ceramics-02",
                "step_no": 2,
                "title": "主体塑形",
                "description": "用泥板、泥条或手捏方式建立作品主体。",
                "tips": ("连接处先打毛并加泥浆。",),
            },
            {
                "step_key": "shiwan-ceramics-03",
                "step_no": 3,
                "title": "结构加固",
                "description": "处理空心、支撑和内部结构，降低烧制开裂风险。",
                "tips": ("厚薄尽量均匀，底部预留透气孔。",),
            },
            {
                "step_key": "shiwan-ceramics-04",
                "step_no": 4,
                "title": "细节雕刻",
                "description": "刻画五官、衣纹或器物纹理，强化造型特征。",
                "tips": ("泥料半干时雕刻更容易保持边缘。",),
            },
            {
                "step_key": "shiwan-ceramics-05",
                "step_no": 5,
                "title": "干燥与素烧",
                "description": "分阶段阴干后进行素烧，并检查裂纹和变形。",
                "tips": ("禁止暴晒或快速烘干。",),
            },
            {
                "step_key": "shiwan-ceramics-06",
                "step_no": 6,
                "title": "施釉与烧成",
                "description": "根据作品效果选择釉色、施釉厚度和烧成制度。",
                "tips": ("施釉前清洁坯体表面浮尘。",),
            },
        ),
        "material_guide": (
            {
                "name": "石湾陶泥",
                "reference_price": "8-20 元/公斤",
                "purchase_channel": "陶艺工作室或陶泥供应商",
                "precautions": "按作品大小采购，并密封保存防止干硬。",
                "taobao_keyword": "石湾陶泥",
            },
            {
                "name": "陶艺塑形工具",
                "reference_price": "30-80 元/套",
                "purchase_channel": "陶艺材料店",
                "precautions": "工具使用后及时清洁，避免泥料硬化。",
                "taobao_keyword": "陶艺塑形工具套装",
            },
            {
                "name": "陶艺釉料",
                "reference_price": "20-60 元/罐",
                "purchase_channel": "陶艺材料商",
                "precautions": "按烧成温度匹配釉料，并做小样试烧。",
                "taobao_keyword": "石湾陶艺釉料",
            },
        ),
    },
    {
        "craft_key": "yangjiang-lacquerware",
        "name": "阳江漆器",
        "sort_order": 4,
        "introduction": (
            "阳江漆器起源于广东阳江，晚清民国时期逐步形成地方漆艺传统；"
            "其技术特征以木胎髹漆、描金彩绘、逐层打磨和推光温润为主。"
        ),
        "is_demo": True,
        "source_available": True,
        "steps": (
            {
                "step_key": "yangjiang-lacquerware-01",
                "step_no": 1,
                "title": "胎体处理",
                "description": "检查木胎或竹胎表面，完成修补和基础打磨。",
                "tips": ("胎体必须干燥、平整且无油污。",),
            },
            {
                "step_key": "yangjiang-lacquerware-02",
                "step_no": 2,
                "title": "底漆髹涂",
                "description": "薄而均匀地涂刷底漆，建立后续涂层基础。",
                "tips": ("少量多次涂刷，避免流挂。",),
            },
            {
                "step_key": "yangjiang-lacquerware-03",
                "step_no": 3,
                "title": "逐层打磨",
                "description": "在漆层干燥后逐层打磨，使表面平整细密。",
                "tips": ("使用与漆层状态匹配的砂纸目数。",),
            },
            {
                "step_key": "yangjiang-lacquerware-04",
                "step_no": 4,
                "title": "纹样装饰",
                "description": "通过描金、彩绘或镶嵌形成装饰纹样。",
                "tips": ("纹样定位前先轻划辅助线。",),
            },
            {
                "step_key": "yangjiang-lacquerware-05",
                "step_no": 5,
                "title": "罩漆与固化",
                "description": "涂罩透明漆，并在适宜温湿度环境中固化。",
                "tips": ("固化环境需防尘并保持稳定通风。",),
            },
            {
                "step_key": "yangjiang-lacquerware-06",
                "step_no": 6,
                "title": "推光与养护",
                "description": "完成推光、清洁和使用养护指导。",
                "tips": ("推光时避免使用粗糙纤维划伤漆面。",),
            },
        ),
        "material_guide": (
            {
                "name": "腰果漆或生漆",
                "reference_price": "50-120 元/罐",
                "purchase_channel": "专业漆艺材料店",
                "precautions": "生漆可能致敏，必须佩戴手套并在通风处操作。",
                "taobao_keyword": "阳江漆器生漆材料",
            },
            {
                "name": "漆刷与刮刀",
                "reference_price": "20-60 元/套",
                "purchase_channel": "漆艺工具店",
                "precautions": "工具专漆专用，使用后按材料说明清洗。",
                "taobao_keyword": "漆器漆刷刮刀",
            },
            {
                "name": "耐水打磨砂纸",
                "reference_price": "10-30 元/组",
                "purchase_channel": "五金店或电商平台",
                "precautions": "从粗目到细目逐级打磨，避免跳号。",
                "taobao_keyword": "漆器打磨砂纸",
            },
        ),
    },
)

PLACEHOLDER_CRAFT_BY_KEY = {
    craft["craft_key"]: craft
    for craft in PLACEHOLDER_CRAFTS
}

PLACEHOLDER_VIDEOS = tuple(
    {
        "video_id": f"demo-{craft['craft_key']}-approved",
        "craft_key": craft["craft_key"],
        "title": f"{craft['name']}安全演示教学（占位）",
        "review_status": "approved",
        "is_demo": True,
        "source_available": True,
        "media_url": (
            f"https://example.test/handcraft/{craft['craft_key']}.mp4"
        ),
        "version": 1,
        "rejection_opinion": None,
        "published_at": "2026-09-17T00:00:00+08:00",
        "created_at": "2026-09-17T00:00:00+08:00",
        "updated_at": "2026-09-17T00:00:00+08:00",
    }
    for craft in PLACEHOLDER_CRAFTS
)

PLACEHOLDER_REWARDS = (
    {
        "reward_id": "reward-guangxiu-bookmark",
        "name": "广绣书签",
        "points_cost": 30,
        "stock": 10,
        "is_online": True,
        "is_demo": True,
        "source_available": True,
    },
    {
        "reward_id": "reward-chaoshan-woodcarving-coaster",
        "name": "潮汕木雕杯垫",
        "points_cost": 40,
        "stock": 8,
        "is_online": True,
        "is_demo": True,
        "source_available": True,
    },
    {
        "reward_id": "reward-shiwan-ceramics-teacup",
        "name": "石湾陶艺茶杯",
        "points_cost": 50,
        "stock": 6,
        "is_online": True,
        "is_demo": True,
        "source_available": True,
    },
    {
        "reward_id": "reward-yangjiang-lacquerware-keychain",
        "name": "阳江漆器钥匙扣",
        "points_cost": 35,
        "stock": 8,
        "is_online": True,
        "is_demo": True,
        "source_available": True,
    },
)

PLACEHOLDER_POINTS_POLICY = {
    "version": "demo-v1",
    "seconds_per_point": 600,
    "training_weights": {
        "default": 10,
        "live_script": 10,
        "simulation": 10,
        "copy_training": 10,
        "customer_service": 10,
    },
    "daily_limit": 60,
    "expiry_mode": "permanent",
    "is_demo": True,
    "source_available": True,
}


class PlaceholderCraftPresetProvider(EmptyCraftPresetProvider):
    def list_crafts(self) -> list[dict]:
        return deepcopy(
            sorted(
                PLACEHOLDER_CRAFTS,
                key=lambda craft: (
                    craft["sort_order"],
                    craft["craft_key"],
                ),
            )
        )

    def get_craft(self, craft_key: str) -> dict | None:
        craft = PLACEHOLDER_CRAFT_BY_KEY.get(craft_key)
        return deepcopy(craft) if craft is not None else None


class PlaceholderTeachingVideoProvider(EmptyTeachingVideoProvider):
    def list_videos(self, craft_key: str | None = None) -> list[dict]:
        return [
            deepcopy(video)
            for video in PLACEHOLDER_VIDEOS
            if craft_key is None or video["craft_key"] == craft_key
        ]

    def get_video(self, video_id: str) -> dict | None:
        video = next(
            (
                item
                for item in PLACEHOLDER_VIDEOS
                if item["video_id"] == video_id
            ),
            None,
        )
        return deepcopy(video) if video is not None else None

    def get_review_status(self, video_id: str) -> str | None:
        video = self.get_video(video_id)
        return video["review_status"] if video is not None else None


class PlaceholderRewardCatalogProvider(EmptyRewardCatalogProvider):
    def __init__(self) -> None:
        self._lock = RLock()
        self._database_backed = False
        self._stock = {
            reward["reward_id"]: int(reward["stock"])
            for reward in PLACEHOLDER_REWARDS
        }
        self._reservations: dict[str, tuple[str, int]] = {}
        self._released: set[str] = set()

    @staticmethod
    def _base_stock(reward_id: str) -> int | None:
        reward = next(
            (
                item
                for item in PLACEHOLDER_REWARDS
                if item["reward_id"] == reward_id
            ),
            None,
        )
        return int(reward["stock"]) if reward is not None else None

    @staticmethod
    def _get_db():
        try:
            from flask import current_app

            if not current_app:
                return None
            from app.db import get_db

            return get_db()
        except RuntimeError:
            return None

    @staticmethod
    def _run_db_write(db, operation):
        owns_transaction = not db.in_transaction
        if owns_transaction:
            db.execute("BEGIN IMMEDIATE")
        try:
            result = operation()
        except Exception:
            if owns_transaction:
                db.rollback()
            raise
        if owns_transaction:
            db.commit()
        return result

    def _database_has_state(self, db) -> bool:
        try:
            row = db.execute(
                """
                SELECT
                    EXISTS(
                        SELECT 1 FROM reward_stock_reservations
                    ) OR EXISTS(
                        SELECT 1 FROM redemptions
                    ) AS has_state
                """
            ).fetchone()
            return bool(row["has_state"])
        except Exception:
            return False

    def _database_stock(self, db, reward_id: str) -> int | None:
        base_stock = self._base_stock(reward_id)
        if base_stock is None:
            return None
        try:
            row = db.execute(
                """
                SELECT COALESCE(SUM(quantity), 0) AS reserved
                FROM reward_stock_reservations
                WHERE reward_id = ? AND status = 'reserved'
                """,
                (reward_id,),
            ).fetchone()
        except Exception:
            return None
        return max(0, base_stock - int(row["reserved"]))

    @staticmethod
    def _redemption_id(db, reservation_id: str) -> int | None:
        normalized = str(reservation_id).strip()
        if normalized.startswith("redemption:"):
            normalized = normalized.split(":", 1)[1]
        if not normalized.isdigit():
            return None
        try:
            row = db.execute(
                """
                SELECT id
                FROM redemptions
                WHERE id = ?
                """,
                (int(normalized),),
            ).fetchone()
        except Exception:
            return None
        return int(row["id"]) if row else None

    def list_rewards(self) -> list[dict]:
        db = self._get_db()
        if db is not None and (
            self._database_backed or self._database_has_state(db)
        ):
            self._database_backed = True
            return [
                {
                    **deepcopy(reward),
                    "stock": self._database_stock(
                        db,
                        reward["reward_id"],
                    ),
                }
                for reward in PLACEHOLDER_REWARDS
            ]
        with self._lock:
            return [
                {
                    **deepcopy(reward),
                    "stock": self._stock[reward["reward_id"]],
                }
                for reward in PLACEHOLDER_REWARDS
            ]

    def reserve_stock(
        self,
        reward_id: str,
        quantity: int,
        reservation_id: str,
    ) -> str | None:
        if (
            not reward_id
            or not reservation_id
            or not isinstance(quantity, int)
            or isinstance(quantity, bool)
            or quantity <= 0
        ):
            return None

        db = self._get_db()
        redemption_id = (
            self._redemption_id(db, reservation_id)
            if db is not None
            else None
        )
        if db is not None and (
            redemption_id is not None or self._database_backed
        ):
            self._database_backed = True

            def reserve_database():
                existing = db.execute(
                    """
                    SELECT reward_id, quantity, status
                    FROM reward_stock_reservations
                    WHERE reservation_id = ?
                    """,
                    (reservation_id,),
                ).fetchone()
                if existing is not None:
                    return (
                        str(reservation_id)
                        if (
                            existing["status"] == "reserved"
                            and str(existing["reward_id"]) == reward_id
                            and int(existing["quantity"]) == quantity
                        )
                        else None
                    )
                available = self._database_stock(db, reward_id)
                if available is None or available < quantity:
                    return None
                db.execute(
                    """
                    INSERT INTO reward_stock_reservations (
                        reservation_id, redemption_id, reward_id,
                        quantity, status, created_at
                    )
                    VALUES (?, ?, ?, ?, 'reserved', ?)
                    """,
                    (
                        reservation_id,
                        redemption_id,
                        reward_id,
                        quantity,
                        _utc_now_iso(),
                    ),
                )
                return str(reservation_id)

            return self._run_db_write(db, reserve_database)

        with self._lock:
            existing = self._reservations.get(reservation_id)
            if existing is not None:
                return (
                    str(reservation_id)
                    if existing == (reward_id, quantity)
                    else None
                )
            if reservation_id in self._released:
                return None
            available = self._stock.get(reward_id)
            if available is None or available < quantity:
                return None
            self._stock[reward_id] = available - quantity
            self._reservations[reservation_id] = (reward_id, quantity)
            return str(reservation_id)

    def release_stock(self, reservation_id: str) -> bool:
        db = self._get_db()
        if db is not None:
            existing = None
            try:
                existing = db.execute(
                    """
                    SELECT status
                    FROM reward_stock_reservations
                    WHERE reservation_id = ?
                    """,
                    (reservation_id,),
                ).fetchone()
            except Exception:
                existing = None
            if existing is not None or self._database_backed:
                self._database_backed = True

                def release_database():
                    row = db.execute(
                        """
                        SELECT status
                        FROM reward_stock_reservations
                        WHERE reservation_id = ?
                        """,
                        (reservation_id,),
                    ).fetchone()
                    if row is None:
                        return False
                    if row["status"] == "released":
                        return True
                    db.execute(
                        """
                        UPDATE reward_stock_reservations
                        SET status = 'released', released_at = ?
                        WHERE reservation_id = ? AND status = 'reserved'
                        """,
                        (_utc_now_iso(), reservation_id),
                    )
                    return True

                return self._run_db_write(db, release_database)

        with self._lock:
            if reservation_id in self._released:
                return True
            reservation = self._reservations.pop(reservation_id, None)
            if reservation is None:
                return False
            reward_id, quantity = reservation
            self._stock[reward_id] += quantity
            self._released.add(reservation_id)
            return True


def _utc_now_iso() -> str:
    from app.session_manager import utc_now_iso

    return utc_now_iso()


class PlaceholderPointsPolicyProvider(UnavailablePointsPolicyProvider):
    def get_policy(self) -> dict | None:
        return deepcopy(PLACEHOLDER_POINTS_POLICY)
