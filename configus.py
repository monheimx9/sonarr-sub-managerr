import logging
import os

logger = logging.getLogger("submanagerr")
handler = logging.FileHandler("logs.log")
console_handler = logging.StreamHandler()
console_formater = logging.Formatter("%(levelname)s - %(message)s")
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
console_handler.setFormatter(console_formater)
logger.addHandler(handler)
logger.addHandler(console_handler)
logger.setLevel(logging.DEBUG)
CONF_LOGGER = logger

host_url = os.getenv("HOST_URL", "http://10.100.3.2:8989")
sonarr_api = os.getenv("HOST_API", "6339d80ef2354a8dbdf3ce8fd4528d4d")
is_prod = True if os.getenv("ISDOCKER") == "docker" else False
CONF_LOGGER.info(f"HOST_URL={host_url}")
CONF_LOGGER.info(f"API={sonarr_api}")
CONF_SONARR_HOST_URL = host_url
CONF_SONARR_API = sonarr_api
CONF_TEMP_FOLDER = os.path.dirname(os.path.abspath(__file__)) + "/temp/"
CONF_GRABING_FOLDER = "./grabs/"
if is_prod:
    CONF_LOGGER.info("Running in production environement")
    CONF_SUBTITLE_PATH = "/subtitles/"
else:
    CONF_LOGGER.info("Running in development environement")
    CONF_SUBTITLE_PATH = "/home/monheim/Documents/subtitles/"
CONF_PROGRESS_FOLDER = "./progress/current.txt"
CONF_DEFAULT_LANG = "fr"
# Ressources for languages :
# https://partnerhub.warnermediagroup.com/metadata/languages
# https://www.techonthenet.com/js/language_tags.php
# You can add your own language_tags based on BCP 47
# https://datatracker.ietf.org/doc/html/rfc5646
COMMON_LANGUAGE_TAGS = {
    "en-US": "English as spoken in the United States",
    "en-GB": "English as spoken in the United Kingdom",
    "pt-BR": "Portuguese as spoken in Brazil",
    "pt-PT": "Portuguese as spoken in Portugal",
    "es-419": "Spanish as spoken in Latin America",
    "es-ES": "Castilian as spoken in Spain",
    "fr-FR": "French as spoken in France",
    "fr-CA": "French as spoken in Canada",
    "de-DE": "German as spoken in Germany",
    "de-CH": "German as spoken in Switzerland",
    "it-IT": "Italian as spoken in Italy",
    "pl-PL": "Polish as spoken in Poland",
    "nl-NL": "Dutch as spoken in The Netherlands",
    "nl-BE": "Dutch as spoken in Belgium (Flemish)",
    "no-NO": "Norwegian as spoken in Norway",
    "fi-FI": "Finnish as spoken in Finland",
    "fil-PH": "Filipino as spoken in the Philippines",
    "tr-TR": "Turkish as spoken in Turkey",
    "sv-SE": "Swedish as spoken in Sweden",
    "el-GR": "Greek (Modern, 1453-) as spoken in Greece",
    "ro-RO": "Romanian as spoken in Romania",
    "ko-KR": "Korean as spoken in South Korea",
    "da-DK": "Danish as spoken in Denmark",
    "zh-Hans-CN": "Chinese Simplified based on Mandarin",
    "hu-HU": "Hungarian as spoken in Hungary",
    "cs-CZ": "Czech as spoken in the Czech Republic",
    "sk-SK": "Slovakian as spoken in Slovakia",
    "ar-SA": "Arabic as spoken in Saudi Arabia",
    "ar": "Arabic",
    "ru-RU": "Russian as spoken in Russia",
}
