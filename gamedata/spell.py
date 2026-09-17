import logging
import re

from .mixins import AutomatibleMixin, DescribableMixin
from .shared import Sourced

log = logging.getLogger(__name__)


class Spell(AutomatibleMixin, DescribableMixin, Sourced):
    entity_type = "spell"
    type_id = 1118725998

    def __init__(
        self,
        name: str,
        level: int,
        school: str,
        casttime: str,
        range_: str,
        components: str,
        duration: str,
        description: str,
        homebrew: bool,
        classes=None,
        subclasses=None,
        ritual: bool = False,
        higherlevels: str = None,
        concentration: bool = False,
        image: str = None,
        **kwargs,
    ):
        if classes is None:
            classes = []
        if isinstance(classes, str):
            classes = [cls.strip() for cls in classes.split(",") if cls.strip()]
        if subclasses is None:
            subclasses = []
        if isinstance(subclasses, str):
            subclasses = [cls.strip() for cls in subclasses.split(",") if cls.strip()]

        super().__init__(homebrew=homebrew, **kwargs)

        self.name = name
        self.level = level
        self.school = school
        self.classes = classes
        self.subclasses = subclasses
        self.time = casttime
        self.range = range_
        self.components = components
        self.duration = duration
        self.ritual = ritual
        self.description = description
        self.higherlevels = higherlevels
        self.concentration = concentration
        self.image = image
        
        # SW5e attributes
        self.power_type = school.lower() # "tech" or "force"
        self.point_cost = level + 1 if level > 0 else 0

        if self.concentration and "Concentration" not in self.duration:
            self.duration = f"Concentration, up to {self.duration}"

    @classmethod
    def from_data(cls, d):  # local JSON
        return cls(
            d.get("name", "Unknown Power"),
            d.get("level", 0),
            d.get("powerType", "Unknown"),  # maps to school
            d.get("castingPeriodText", "1 action"),
            d.get("range", "Self"),
            d.get("forceAlignment", "None"),  # using alignment as components proxy
            d.get("duration", "Instantaneous"),
            d.get("description", ""),
            rulesVersion="SW5e",
            homebrew=False,
            classes=[],  # SW5e doesn't explicitly restrict powers by class in this payload
            subclasses=[],
            ritual=False,
            higherlevels=d.get("higherLevelDescription"),
            concentration=d.get("concentration", False),
            source=d.get("contentSource", "PHB"),
            entity_id=d.get("rowKey", d.get("name")),
            page=0,
            url="",
            is_free=True,
        ).initialize_automation(d)

    @classmethod
    def from_homebrew(cls, data, source):  # homebrew spells
        data["components"] = parse_homebrew_components(data["components"])
        data["range_"] = data.pop("range")
        data["automation"] = data.get("automation")
        data["rulesVersion"] = "Homebrew"
        return cls(homebrew=True, source=source, **data).initialize_automation(data)

    def get_school(self):
        return {
            "A": "Abjuration",
            "V": "Evocation",
            "E": "Enchantment",
            "I": "Illusion",
            "D": "Divination",
            "N": "Necromancy",
            "T": "Transmutation",
            "C": "Conjuration",
        }.get(self.school, self.school)

    def get_level(self):
        if self.level == 0:
            return "cantrip"
        if self.level == 1:
            return "1st-level"
        if self.level == 2:
            return "2nd-level"
        if self.level == 3:
            return "3rd-level"
        return f"{self.level}th-level"

    def get_combat_duration(self):
        match = re.match(r"(?:Concentration, up to )?(\d+) (\w+)", self.duration)
        if match:
            num = int(match.group(1))
            unit = match.group(2)
            if "round" in unit:
                return num
            elif "minute" in unit:
                return 10 * num
            elif "hour" in unit:
                return 600 * num
        return -1

    def to_dicecloud(self):
        mat = re.search(r"\(([^()]+)\)", self.components)
        text = self.description.replace("\n", "\n  ")
        if self.higherlevels:
            text += f"\n\n**At Higher Levels**: {self.higherlevels}"
        return {
            "name": self.name,
            "description": text,
            "castingTime": self.time,
            "range": self.range,
            "duration": self.duration,
            "components": {
                "verbal": "V" in self.components,
                "somatic": "S" in self.components,
                "concentration": self.concentration,
                "material": mat.group(1) if mat else None,
            },
            "ritual": self.ritual,
            "level": int(self.level),
            "school": self.get_school(),
            "prepared": "prepared",
        }


def parse_homebrew_components(components):
    v = components.get("verbal")
    s = components.get("somatic")
    m = components.get("material")
    if isinstance(m, bool):
        parsedm = "M"
    else:
        parsedm = f"M ({m})"

    comps = []
    if v:
        comps.append("V")
    if s:
        comps.append("S")
    if m:
        comps.append(parsedm)
    return ", ".join(comps)
