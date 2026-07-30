"""
Mojang 官方翻译词汇表 — 配置
"""

from pathlib import Path

# === Mojang API 端点 ===
URL_MANIFEST_V2 = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
URL_RESOURCE_FORMAT = "https://resources.download.minecraft.net/{0}/{1}"
LANG_FORMAT = "minecraft/lang/{0}.json"

# === 路径（基于本文件位置推导项目根） ===
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent  # config.py → mojang_glossary/ → scripts/ → project root
GLOSSARY_OUTPUT_DIR = PROJECT_ROOT / ".cache" / "mojang"
GLOSSARY_VERSION_PATH = GLOSSARY_OUTPUT_DIR / "MC_version.txt"

# 工具内部下载缓存（中间产物：JAR、JSON 等，非项目知识）
DOWNLOAD_TEMP = GLOSSARY_OUTPUT_DIR / "_download_tmp"
CACHE_VERSION_DIR = DOWNLOAD_TEMP / "versions"
CACHE_ASSET_INDEX_DIR = DOWNLOAD_TEMP / "asset_index"
CACHE_LANG_DIR = DOWNLOAD_TEMP / "lang"

# === 下载参数 ===
TIMEOUT = 10
MAX_RETRIES = 3

# === 语言配置 ===
JAR_LANG = "en_us"
LANG_LIST = ["zh_cn"]
JAR_LANG_LOCATION = f"assets/minecraft/lang/{JAR_LANG}.json"
LANG_ORDER = ["en_us", "zh_cn"]

# === 翻译键分类正则 ===
TRANSLATION_KEY_REGEX = {
    "blocks": [
        "block\.minecraft(?!\.(banner|(?:waxed_)?(?:exposed|oxidized|weathered)?_)).*"
    ],
    "misc": [
        "biome\.minecraft.*",
        "color\.minecraft.*",
        "effect\.minecraft.*",
        "enchantment\.minecraft.*",
        "gamerule\.[^.]*",
    ],
    "entities": [
        "entity\.minecraft.*",
    ],
    "items": [
        "item\.minecraft(?!\.(music_disc|(lingering_|splash_|)potion|smithing_template)).*",
        "item\.minecraft\.smithing_template",
    ],
    "redstone": [
        "block.minecraft.activator_rail",
        "block.minecraft.amethyst_block",
        "block.minecraft.barrel",
        "block.minecraft.bell",
        "block.minecraft.big_dripleaf",
        "block.minecraft.calibrated_sculk_sensor",
        "block.minecraft.cauldron",
        "block.minecraft.chest",
        "block.minecraft.chiseled_bookshelf",
        "block.minecraft.comparator",
        "block.minecraft.composter",
        "block.minecraft.crafter",
        "block.minecraft.daylight_detector",
        "block.minecraft.decorated_pot",
        "block.minecraft.detector_rail",
        "block.minecraft.dispenser",
        "block.minecraft.dropper",
        "block.minecraft.furnace",
        "block.minecraft.heavy_weighted_pressure_plate",
        "block.minecraft.honey_block",
        "block.minecraft.hopper",
        "block.minecraft.iron_door",
        "block.minecraft.iron_trapdoor",
        "block.minecraft.jukebox",
        "block.minecraft.lectern",
        "block.minecraft.lever",
        "block.minecraft.light_weighted_pressure_plate",
        "block.minecraft.note_block",
        "block.minecraft.oak_button",
        "block.minecraft.oak_door",
        "block.minecraft.oak_fence_gate",
        "block.minecraft.oak_hanging_sign",
        "block.minecraft.oak_pressure_plate",
        "block.minecraft.oak_shelf",
        "block.minecraft.oak_trapdoor",
        "block.minecraft.observer",
        "block.minecraft.piston",
        "block.minecraft.powered_rail",
        "block.minecraft.rail",
        "block.minecraft.redstone_block",
        "block.minecraft.redstone_lamp",
        "block.minecraft.redstone_ore",
        "block.minecraft.redstone_torch",
        "block.minecraft.redstone_wall_torch",
        "block.minecraft.redstone_wire",
        "block.minecraft.repeater",
        "block.minecraft.sculk_sensor",
        "block.minecraft.sculk_shrieker",
        "block.minecraft.slime_block",
        "block.minecraft.sticky_piston",
        "block.minecraft.stone_button",
        "block.minecraft.stone_pressure_plate",
        "block.minecraft.target",
        "block.minecraft.tnt",
        "block.minecraft.trapped_chest",
        "block.minecraft.tripwire_hook",
        "block.minecraft.waxed_copper_bulb",
        "block.minecraft.waxed_copper_chest",
        "block.minecraft.waxed_exposed_copper_bulb",
        "block.minecraft.waxed_lightning_rod",
        "block.minecraft.waxed_oxidized_copper_bulb",
        "block.minecraft.waxed_weathered_copper_bulb",
        "block.minecraft.white_wool",
        "item.minecraft.armor_stand",
        "item.minecraft.bamboo_chest_raft",
        "item.minecraft.chest_minecart",
        "item.minecraft.furnace_minecart",
        "item.minecraft.hopper_minecart",
        "item.minecraft.minecart",
        "item.minecraft.redstone",
        "item.minecraft.string",
        "item.minecraft.tnt_minecart",
    ],
}
