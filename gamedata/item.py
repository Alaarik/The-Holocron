"""
entity types and ids

RPGAdventuringGear    adventuring-gear   2103445194
RPGArmor              armor              701257905
RPGMagicItem          magic-item         112130694
RPGWeapon             weapon             1782728300
"""

import abc

from .mixins import DescribableMixin
from .shared import Sourced


class Item(DescribableMixin, Sourced, abc.ABC):
    def __init__(
        self, name: str, desc: str, attunement: bool | str, meta: str | None = None, image: str | None = None, **kwargs
    ):
        super().__init__(**kwargs)
        self.name = name
        self.desc = desc
        self.attunement = attunement
        self.meta = meta
        self.image = image

    @classmethod
    def from_data(cls, d):
        # Determine item entity_type and type_id dynamically based on equipmentCategory
        cat = d.get("equipmentCategory", "Unknown")
        entity_type = "magic-item"
        type_id = 112130694
        if cat == "Weapon":
            entity_type = "weapon"
            type_id = 1782728300
        elif cat == "Armor":
            entity_type = "armor"
            type_id = 701257905
        else:
            entity_type = "adventuring-gear"
            type_id = 2103445194
            
        instance = cls(
            d.get("name", "Unknown Item"),
            d.get("description") or "",
            False, # no attunement field natively in sw5e equipment yet
            None,
            None,
            homebrew=False,
            source=d.get("contentSource", "PHB"),
            entity_id=d.get("name"),
            page=0,
            url="",
            is_free=True,
            is_legacy=False,
        )
        instance.entity_type = entity_type
        instance.type_id = type_id
        instance.properties_map = d.get("propertiesMap") or {}
        return instance

    @classmethod
    def from_homebrew(cls, d, source):
        return cls(d["name"], d["desc"], False, d.get("meta"), d.get("image"), source=source, homebrew=True)

    @property
    def description(self):
        return self.desc


class AdventuringGear(Item):
    entity_type = "adventuring-gear"
    type_id = 2103445194


class Armor(Item):
    entity_type = "armor"
    type_id = 701257905


class MagicItem(Item):
    entity_type = "magic-item"
    type_id = 112130694


class Weapon(Item):
    entity_type = "weapon"
    type_id = 1782728300


class HomebrewItem(MagicItem):
    """
    Avrae homebrew items don't really care about their item type - we just call them all magic items but give them their
    own class to separate them
    """

    pass
